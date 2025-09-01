"""
GitHub discovery and enrichment tools
"""
import logging
import sys
import os
import re
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from .base import GitHubTool, ToolResult
    try:
        from ..core.monitoring import record_api_call, record_error
    except ImportError:
        # Monitoring not available
        record_api_call = lambda: None
        record_error = lambda *args: None
except ImportError:
    try:
        from base import GitHubTool, ToolResult
        # Monitoring not available in standalone mode
        record_api_call = lambda: None
        record_error = lambda *args: None
    except ImportError:
        # Create minimal fallback classes
        class ToolResult:
            def __init__(self, success: bool, data: Any = None, error: str = None, metadata: Dict = None):
                self.success = success
                self.data = data or {}
                self.error = error
                self.metadata = metadata or {}

            def to_dict(self) -> Dict[str, Any]:
                return {
                    "success": self.success,
                    "data": self.data,
                    "error": self.error,
                    "metadata": self.metadata,
                }

        class GitHubTool:
            def __init__(self, name: str, description: str, github_token: str):
                self.name = name
                self.description = description
                self.github_token = github_token

logger = logging.getLogger(__name__)

# Detect obviously placeholder usernames often produced by mocks or bad scrapes
def _is_placeholder_login(login: str) -> bool:
    if not isinstance(login, str):
        return False
    s = login.strip().lower()
    # Patterns like user1, user_12, user-003, test5, demo42
    return bool(re.fullmatch(r"(user|test|demo)[-_]?\d{1,6}", s))

# === Email helpers ===
NOREPLY_SUFFIXES = ("@users.noreply.github.com", "@noreply.github.com")

def _normalize_email(em: str) -> str:
    return (em or "").strip().lower()

def _is_noreply_email(em: str) -> bool:
    em = _normalize_email(em)
    return any(em.endswith(sfx) for sfx in NOREPLY_SUFFIXES)

def _is_valid_commit_email(em: str) -> bool:
    em = _normalize_email(em)
    if not em or "@" not in em or _is_noreply_email(em):
        return False
    return True


class SearchGitHubRepos(GitHubTool):
    """Search GitHub repositories tool"""

    def __init__(self, github_token: str, default_icp: Dict[str, Any] | None = None):
        super().__init__(
            name="search_github_repos",
            description="Search GitHub repositories by query and return matching repos",
            github_token=github_token
        )
        self.default_icp: Dict[str, Any] = default_icp or {}

    async def execute(self, q: str, max_repos: int = 200, **kwargs) -> ToolResult:
        """Execute repository search that respects caller's qualifiers.

        Notes:
        - Do NOT pre-encode q; let the HTTP client encode params.
        - Add sensible defaults only if missing in q.
        - Provide deterministic sorting.
        """
        try:
            raw_q = (q or "").strip()

            # Optional structured constraints (when ICP was not inlined in q)
            language: str = (kwargs.get("language") or "").strip()
            stars_range: str = (kwargs.get("stars_range") or "").strip()
            activity_days: int = int(kwargs.get("activity_days", 90))
            # Allow passing an icp dict and derive structured constraints from it
            icp = kwargs.get("icp") or self.default_icp or {}
            try:
                # Support both singular and plural forms from ICP
                if not language:
                    if isinstance(icp.get("language"), str):
                        language = icp.get("language").strip()
                    elif isinstance(icp.get("languages"), list) and icp.get("languages"):
                        language = str(icp.get("languages")[0]).strip()
                if not stars_range:
                    if isinstance(icp.get("stars_range"), str):
                        stars_range = icp.get("stars_range").strip()
                    else:
                        stars_min = icp.get("stars_min")
                        stars_max = icp.get("stars_max")
                        if stars_min is not None and stars_max is not None:
                            stars_range = f"{int(stars_min)}..{int(stars_max)}"
                        elif stars_min is not None:
                            stars_range = f">={int(stars_min)}"
                if ("activity_days" in icp) and not kwargs.get("activity_days"):
                    activity_days = int(icp.get("activity_days"))
                elif "pushed_within_days" in icp and not kwargs.get("activity_days"):
                    activity_days = int(icp.get("pushed_within_days"))
                elif "window_days" in icp and not kwargs.get("activity_days"):
                    activity_days = int(icp.get("window_days"))
            except Exception:
                pass

            # If no explicit query provided, build one from ICP for safety
            if not raw_q:
                parts: List[str] = []
                if language:
                    parts.append(f"language:{language}")
                if stars_range:
                    parts.append(f"stars:{stars_range}")
                try:
                    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, activity_days))).date().isoformat()
                    parts.append(f"pushed:>={cutoff}")
                except Exception:
                    pass
                # Add topics if present
                try:
                    topics = icp.get("topics") or icp.get("include_topics") or []
                    if isinstance(topics, list):
                        for t in topics:
                            if isinstance(t, str) and t.strip():
                                parts.append(f"topic:{t.strip()}")
                except Exception:
                    pass
                # Always include safe defaults
                parts.append("archived:false")
                parts.append("fork:false")
                parts.append("is:public")
                raw_q = " ".join(parts)

            # Add default qualifiers only if the caller didn't specify them
            def _ensure(qualifier: str) -> None:
                nonlocal raw_q
                if qualifier not in raw_q:
                    raw_q += (" " if raw_q else "") + qualifier

            # Defaults: public, not archived, not forks
            _ensure("is:public")
            _ensure("archived:false")
            _ensure("fork:false")

            # Apply structured qualifiers only if caller didn't provide them
            if language and ("language:" not in raw_q):
                raw_q += (" " if raw_q else "") + f"language:{language}"
            if stars_range and ("stars:" not in raw_q):
                raw_q += (" " if raw_q else "") + f"stars:{stars_range}"
            if ("pushed:" not in raw_q) and ("created:" not in raw_q):
                try:
                    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, activity_days))).date().isoformat()
                    raw_q += (" " if raw_q else "") + f"pushed:>={cutoff}"
                except Exception:
                    pass

            params = {
                "q": raw_q,
                "sort": "stars",
                "order": "desc",
                "per_page": min(max_repos, 100),  # GitHub API limit
            }

            repos = []
            page = 1

            # Simple retry/backoff wrapper for GitHub requests
            async def _safe_search(params: Dict[str, Any]):
                import asyncio
                last_err = None
                for attempt in range(3):
                    try:
                        result = await self._github_request("/search/repositories", params=params)
                        record_api_call()
                        return result
                    except Exception as e:
                        last_err = e
                        await asyncio.sleep(0.5 * (2 ** attempt))
                record_error("github_search")
                raise last_err

            while len(repos) < max_repos:
                params["page"] = page
                result = await _safe_search(params)

                if not result.get("items"):
                    break

                for item in result["items"]:
                    if len(repos) >= max_repos:
                        break

                    repo_data = {
                        "id": item["id"],
                        "full_name": item["full_name"],
                        "name": item["name"],
                        "owner_login": item["owner"]["login"],
                        "description": item.get("description", ""),
                        "topics": item.get("topics", []),
                        "language": item.get("language"),
                        "stars": item["stargazers_count"],
                        "forks": item["forks_count"],
                        "open_issues": item["open_issues_count"],
                        "pushed_at": item["pushed_at"],
                        "created_at": item["created_at"],
                        "updated_at": item["updated_at"],
                        "html_url": item["html_url"],
                        "api_url": item["url"],
                        "is_archived": item["archived"],
                        "is_fork": item["fork"],
                    }
                    # Post-filter obvious non-target/meta repos
                    if language and repo_data.get("language") and str(repo_data.get("language")).lower() != language.lower():
                        continue
                    if str(repo_data.get("name") or "").lower() == ".github":
                        continue
                    # Enforce recency window (activity_days) on pushed_at
                    try:
                        if activity_days and repo_data.get("pushed_at"):
                            s = str(repo_data.get("pushed_at"))
                            if s.endswith("Z"):
                                s = s.replace("Z", "+00:00")
                            pushed_dt = datetime.fromisoformat(s)
                            if pushed_dt.tzinfo is None:
                                pushed_dt = pushed_dt.replace(tzinfo=timezone.utc)
                            cutoff_dt = datetime.now(timezone.utc) - timedelta(days=max(1, activity_days))
                            if pushed_dt < cutoff_dt:
                                continue
                    except Exception:
                        pass
                    repos.append(repo_data)

                page += 1
                # Small pause between pages to avoid secondary rate limits
                try:
                    import asyncio
                    await asyncio.sleep(0.2)
                except Exception:
                    pass
                if page > 10:  # Safety limit
                    break

            return ToolResult(
                success=True,
                data={"repos": repos, "count": len(repos), "query": q},
                metadata={"pages_searched": page - 1, "max_requested": max_repos}
            )

        except Exception as e:
            logger.error(f"GitHub repo search failed: {e}")
            return ToolResult(success=False, error=str(e))


class ExtractPeople(GitHubTool):
    """Extract people from GitHub repositories tool"""

    def __init__(self, github_token: str):
        super().__init__(
            name="extract_people",
            description="Extract top contributors from GitHub repositories",
            github_token=github_token
        )

    async def execute(self, repos: List[Dict], top_authors_per_repo: int = 5, **kwargs) -> ToolResult:
        """Extract people from repositories"""
        try:
            all_candidates = []

            for repo in repos[:50]:  # Limit to avoid rate limits
                try:
                    # Tolerate minimal/malformed repo inputs
                    repo_full_name = repo.get("full_name") or repo.get("repo_full_name")
                    if not repo_full_name:
                        continue
                    repo_name = repo.get("name") or repo_full_name.split("/")[-1]
                    repo_stars = repo.get("stars", 0)
                    repo_language = repo.get("language")
                    repo_topics = repo.get("topics", []) or []
                    repo_description = repo.get("description", "")

                    # Get contributors for this repo
                    contributors_response = await self._github_request(
                        f"/repos/{repo_full_name}/contributors",
                        params={"per_page": top_authors_per_repo * 2}  # Get more to filter bots
                    )

                    # Handle empty or malformed responses
                    if not contributors_response or not isinstance(contributors_response, (list, dict)):
                        logger.warning(f"Empty or invalid contributors response for {repo_full_name}")
                        continue

                    # If response is a dict (e.g., error response), extract list if available
                    contributors = contributors_response if isinstance(contributors_response, list) else contributors_response.get("contributors", [])

                    if not contributors:
                        logger.info(f"No contributors found for {repo_full_name}")
                        continue

                    # Filter out bots and get top contributors
                    human_contributors = [
                        c for c in contributors
                        if isinstance(c, dict)
                        and isinstance(c.get("login", ""), str)
                        and (c.get("type") == "User")
                        and not c["login"].endswith("[bot]")
                        and not c["login"].endswith("-bot")
                    ][:top_authors_per_repo]

                    for contributor in human_contributors:
                        candidate = {
                            "login": contributor["login"],
                            "from_repo": repo_full_name,
                            "signal": f"contributor to {repo_name}",
                            "contributions": contributor.get("contributions", 0),
                            "repo_stars": repo_stars,
                            "repo_language": repo_language,
                            "repo_topics": repo_topics,
                            "repo_description": repo_description,
                        }
                        all_candidates.append(candidate)

                except Exception as e:
                    logger.warning(f"Failed to get contributors for {repo_full_name or 'unknown'}: {e}")
                    continue

            # Remove duplicates by login
            unique_candidates = []
            seen_logins = set()
            for candidate in all_candidates:
                if candidate["login"] not in seen_logins:
                    unique_candidates.append(candidate)
                    seen_logins.add(candidate["login"])

            # Also return user-repo pairs for downstream email discovery
            user_repo_pairs = [
                {"login": c["login"], "repo_full_name": c["from_repo"]}
                for c in unique_candidates
            ]

            return ToolResult(
                success=True,
                data={
                    "candidates": unique_candidates,
                    "count": len(unique_candidates),
                    "user_repo_pairs": user_repo_pairs,
                },
                metadata={"repos_processed": len(repos), "duplicates_removed": len(all_candidates) - len(unique_candidates)}
            )

        except Exception as e:
            logger.error(f"People extraction failed: {e}")
            return ToolResult(success=False, error=str(e))


class EnrichGitHubUser(GitHubTool):
    """Enrich GitHub user profile tool"""

    def __init__(self, github_token: str):
        super().__init__(
            name="enrich_github_user",
            description="Get detailed GitHub user profile information",
            github_token=github_token
        )

    async def execute(self, login: str, **kwargs) -> ToolResult:
        """Enrich user profile"""
        try:
            # Get user profile
            user_data = await self._github_request(f"/users/{login}")

            profile = {
                "login": user_data["login"],
                "id": user_data["id"],
                "name": user_data.get("name"),
                "company": user_data.get("company"),
                "location": user_data.get("location"),
                "email": user_data.get("email"),
                "bio": user_data.get("bio"),
                "blog": user_data.get("blog"),
                "twitter_username": user_data.get("twitter_username"),
                "public_repos": user_data["public_repos"],
                "public_gists": user_data["public_gists"],
                "followers": user_data["followers"],
                "following": user_data["following"],
                "created_at": user_data["created_at"],
                "updated_at": user_data["updated_at"],
                "html_url": user_data["html_url"],
                "api_url": user_data["url"],
            }

            return ToolResult(success=True, data={"profile": {**profile, "enriched": True}})

        except Exception as e:
            logger.error(f"User enrichment failed for {login}: {e}")
            return ToolResult(success=False, error=str(e))


class FindCommitEmails(GitHubTool):
    """Find commit emails for GitHub user tool"""

    def __init__(self, github_token: str):
        super().__init__(
            name="find_commit_emails",
            description="Find email addresses from user's commit history",
            github_token=github_token
        )

    async def execute(self, login: str, repos: List[Dict], days: int = 180, **kwargs) -> ToolResult:
        """Find commit emails"""
        try:
            emails = set()
            noreply_suffix = "@users.noreply.github.com"
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")
            include_committer_email = bool(kwargs.get("include_committer_email", True))

            # Process all provided repos, don't rely on contributors attachment
            user_repos = []
            for r in repos:
                repo_full_name = r.get("full_name") or r.get("repo_full_name")
                if isinstance(repo_full_name, str):
                    pushed_at = r.get("pushed_at")
                    # Skip inactive repos outside the lookback window if timestamp available
                    try:
                        if pushed_at:
                            s = str(pushed_at)
                            if s.endswith("Z"):
                                s = s.replace("Z", "+00:00")
                            pushed_dt = datetime.fromisoformat(s)
                            if pushed_dt.tzinfo is None:
                                pushed_dt = pushed_dt.replace(tzinfo=timezone.utc)
                            cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)
                            if pushed_dt < cutoff_dt:
                                continue
                    except Exception:
                        pass
                    user_repos.append({"full_name": repo_full_name, "pushed_at": pushed_at})

            # Prefer recently pushed repos; expand surface area modestly
            try:
                user_repos.sort(key=lambda r: r.get("pushed_at", ""), reverse=True)
            except Exception:
                pass
            user_repos = user_repos[:15]  # Slightly larger surface area

            for repo in user_repos:
                try:
                    # Page through commits, try author then committer
                    for mode in (("author", login), ("committer", login)):
                        page = 1
                        while True:
                            params = {
                                mode[0]: mode[1],
                                "since": cutoff_date,
                                "per_page": 50,
                                "page": page,
                            }
                            commits = await self._github_request(
                                f"/repos/{repo['full_name']}/commits", params=params
                            )
                            if not commits:
                                break
                            for commit in commits:
                                c = commit.get("commit", {})
                                a = (c.get("author") or {})
                                m = (c.get("committer") or {})
                                ae = a.get("email")
                                me = m.get("email")
                                if ae and "@" in ae and not ae.endswith(noreply_suffix):
                                    emails.add(ae.strip().lower())
                                if include_committer_email and me and "@" in me and not me.endswith(noreply_suffix):
                                    emails.add(me.strip().lower())
                            if len(commits) < params["per_page"]:
                                break
                            page += 1
                except Exception as e:
                    logger.warning(f"Failed to get commits for {repo['full_name']}: {e}")
                    continue

            return ToolResult(
                success=True,
                data={"emails": list(emails), "count": len(emails)},
                metadata={"repos_searched": len(user_repos), "days_back": days}
            )

        except Exception as e:
            logger.error(f"Commit email search failed for {login}: {e}")
            return ToolResult(success=False, error=str(e))


class EnrichGitHubUsers(GitHubTool):
    """Batch enrich GitHub user profiles tool"""

    def __init__(self, github_token: str):
        super().__init__(
            name="enrich_github_users",
            description="Get detailed GitHub user profile information for multiple users",
            github_token=github_token
        )

    async def execute(self, logins: List[str], **kwargs) -> ToolResult:
        """Enrich multiple user profiles"""
        try:
            # Guardrail: detect placeholder usernames and fail fast if batch looks synthetic
            placeholders = [l for l in (logins or []) if _is_placeholder_login(l)]
            if placeholders and len(placeholders) >= max(3, int(0.5 * max(1, len(logins)))):
                return ToolResult(
                    success=False,
                    error="Detected placeholder usernames (e.g., user1, user2). Aborting enrichment due to likely mock or buggy data.",
                    metadata={
                        "error_code": "placeholder_usernames_detected",
                        "total_requested": len(logins or []),
                        "total_placeholders": len(placeholders),
                        "sample": placeholders[:10],
                    },
                )

            profiles = []
            batch_size = kwargs.get("batch_size", 10)  # Process in smaller batches to avoid rate limits

            # Setup progress tracking
            beautiful_logger = kwargs.get('beautiful_logger')
            if beautiful_logger:
                progress_tracker = beautiful_logger.start_progress(
                    f"👤 Enriching {len(logins)} user profiles",
                    total=len(logins),
                    show_emails=False
                )
            else:
                progress_tracker = None

            for i in range(0, len(logins), batch_size):
                batch_logins = logins[i:i + batch_size]

                for login in batch_logins:
                    try:
                        # Get user profile
                        user_data = await self._github_request(f"/users/{login}")

                        profile = {
                            "login": user_data["login"],
                            "id": user_data["id"],
                            "name": user_data.get("name"),
                            "company": user_data.get("company"),
                            "location": user_data.get("location"),
                            "email": user_data.get("email"),  # Profile email as fallback
                            "bio": user_data.get("bio"),
                            "blog": user_data.get("blog"),
                            "twitter_username": user_data.get("twitter_username"),
                            "public_repos": user_data["public_repos"],
                            "public_gists": user_data["public_gists"],
                            "followers": user_data["followers"],
                            "following": user_data["following"],
                            "created_at": user_data["created_at"],
                            "updated_at": user_data["updated_at"],
                            "html_url": user_data["html_url"],
                            "api_url": user_data["url"],
                        }
                        profiles.append(profile)

                        # Update progress
                        if progress_tracker:
                            progress_tracker.update(1)

                    except Exception as e:
                        logger.warning(f"Failed to enrich user {login}: {e}")
                        # Add minimal profile for failed users
                        profiles.append({
                            "login": login,
                            "error": str(e),
                            "enriched": False
                        })

                        # Update progress even on error
                        if progress_tracker:
                            progress_tracker.update(1)
                        continue

            # Close progress tracker
            if progress_tracker:
                progress_tracker.close()

            return ToolResult(
                success=True,
                data={"profiles": profiles, "count": len(profiles), "requested": len(logins)},
                metadata={"batch_size": batch_size, "successful": len([p for p in profiles if p.get("enriched") != False])}
            )

        except Exception as e:
            logger.error(f"Batch user enrichment failed: {e}")
            return ToolResult(success=False, error=str(e))


class FindCommitEmailsBatch(GitHubTool):
    """Batch find commit emails for multiple GitHub users tool"""

    def __init__(self, github_token: str):
        super().__init__(
            name="find_commit_emails_batch",
            description="Find email addresses from multiple users' commit history",
            github_token=github_token
        )

    async def execute(self, user_repo_pairs: List[Dict[str, Any]], days: int = 180, **kwargs) -> ToolResult:
        """Find commit emails for multiple users across their repos"""
        try:
            user_emails: Dict[str, Any] = {}
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")
            batch_size = int(kwargs.get("batch_size", 5))          # users per batch
            repos_per_user = int(kwargs.get("repos_per_user", 10))  # repos per user (increased)
            max_commits = int(kwargs.get("commits_per_repo", 120))  # scan deeper per repo
            include_committer_email = bool(kwargs.get("include_committer_email", True))
            also_try_committer = bool(kwargs.get("also_try_committer", True))
            noreply_suffix = "@users.noreply.github.com"

            # Group by user to avoid duplicate work
            user_to_repos: Dict[str, List[str]] = {}
            for pair in user_repo_pairs:
                login = pair["login"]
                repo_full_name = pair["repo_full_name"]
                if login not in user_to_repos:
                    user_to_repos[login] = []
                user_to_repos[login].append(repo_full_name)

            # Setup progress tracking with live email count
            logins = list(user_to_repos.keys())
            total_users = len(logins)

            # Try to get beautiful logger from kwargs for progress tracking
            beautiful_logger = kwargs.get('beautiful_logger')
            if beautiful_logger:
                progress_tracker = beautiful_logger.start_progress(
                    f"🔍 Finding emails for {total_users} users",
                    total=total_users,
                    show_emails=True
                )
            else:
                progress_tracker = None

            total_emails_found = 0

            # Process users in batches
            for i in range(0, len(logins), batch_size):
                batch_logins = logins[i:i + batch_size]

                for login in batch_logins:
                    try:
                        emails: set = set()
                        stats = {
                            "repos_scanned": 0,
                            "pages_scanned": 0,
                            "noreply_skipped": 0,
                            "author_mode_hits": 0,
                            "committer_mode_hits": 0,
                        }
                        # Prefer recently pushed repos first
                        repos = user_to_repos[login][:]
                        try:
                            # If we have pushed_at info in pairs, sort; otherwise keep insertion
                            repos.sort(key=lambda rn: 0, reverse=True)  # placeholder sort stable
                        except Exception:
                            pass
                        repos = repos[:repos_per_user]

                        for repo_full_name in repos:
                            try:
                                stats["repos_scanned"] += 1
                                scanned = 0
                                # Try author mode then optional committer mode
                                modes = [("author", login)] + (([("committer", login)]) if also_try_committer else [])
                                for mode in modes:
                                    page = 1
                                    while scanned < max_commits:
                                        params = {
                                            mode[0]: mode[1],
                                            "since": cutoff_date,
                                            "per_page": min(100, max_commits - scanned),
                                            "page": page,
                                        }
                                        commits = await self._github_request(
                                            f"/repos/{repo_full_name}/commits", params=params
                                        )
                                        if not commits:
                                            break
                                        stats["pages_scanned"] += 1
                                        for commit in commits:
                                            c = commit.get("commit", {})
                                            a = (c.get("author") or {})
                                            m = (c.get("committer") or {})
                                            ae = a.get("email")
                                            me = m.get("email")
                                            if ae and "@" in ae:
                                                if ae.endswith(noreply_suffix):
                                                    stats["noreply_skipped"] += 1
                                                else:
                                                    emails.add(ae.strip().lower())
                                                    stats["author_mode_hits"] += 1
                                            if include_committer_email and me and "@" in me:
                                                if me.endswith(noreply_suffix):
                                                    stats["noreply_skipped"] += 1
                                                else:
                                                    emails.add(me.strip().lower())
                                                    stats["committer_mode_hits"] += 1
                                        scanned += len(commits)
                                        if len(commits) < params["per_page"]:
                                            break
                                        page += 1

                            except Exception as e:
                                logger.warning(f"Failed to get commits for {login} in {repo_full_name}: {e}")
                                continue

                        user_emails[login] = {
                            "emails": list(emails),
                            "count": len(emails),
                            "repos_searched": len(repos),
                            "stats": stats,
                        }

                        # Update progress tracker with email count
                        emails_found = len(emails)
                        if emails_found > 0:
                            total_emails_found += emails_found

                        if progress_tracker:
                            progress_tracker.update(1, emails_found)

                    except Exception as e:
                        logger.warning(f"Failed to find emails for {login}: {e}")
                        user_emails[login] = {"emails": [], "count": 0, "error": str(e)}

                        # Still update progress even on error
                        if progress_tracker:
                            progress_tracker.update(1, 0)
                        continue

            # Close progress tracker
            if progress_tracker:
                progress_tracker.close()

            return ToolResult(
                success=True,
                data={"user_emails": user_emails, "total_users": len(logins), "total_emails_found": total_emails_found},
                metadata={"days_back": days, "batch_size": batch_size, "committer_fallback": also_try_committer}
            )

        except Exception as e:
            logger.error(f"Batch commit email search failed: {e}")
            return ToolResult(success=False, error=str(e))
