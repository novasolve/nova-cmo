"""
GitHub discovery and enrichment tools
"""
import logging
from typing import List, Dict, Any
try:
    from .base import GitHubTool, ToolResult
    from ..core.monitoring import record_api_call, record_error
except ImportError:
    from base import GitHubTool, ToolResult
    # Monitoring not available in standalone mode

logger = logging.getLogger(__name__)


class SearchGitHubRepos(GitHubTool):
    """Search GitHub repositories tool"""

    def __init__(self, github_token: str):
        super().__init__(
            name="search_github_repos",
            description="Search GitHub repositories by query and return matching repos",
            github_token=github_token
        )

    async def execute(self, q: str, max_repos: int = 200, **kwargs) -> ToolResult:
        """Execute repository search"""
        try:
            # Build search query with sorting and filtering
            search_query = f"{q} stars:>100 is:public archived:false"
            params = {
                "q": search_query,
                "sort": "updated",
                "order": "desc",
                "per_page": min(max_repos, 100),  # GitHub API limit
            }

            repos = []
            page = 1

            while len(repos) < max_repos:
                params["page"] = page
                result = await self._github_request("/search/repositories", params=params)

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
                    repos.append(repo_data)

                page += 1
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
                    # Get contributors for this repo
                    contributors = await self._github_request(
                        f"/repos/{repo['full_name']}/contributors",
                        params={"per_page": top_authors_per_repo * 2}  # Get more to filter bots
                    )

                    # Filter out bots and get top contributors
                    human_contributors = [
                        c for c in contributors
                        if not c["login"].endswith("[bot]") and not c["login"].endswith("-bot")
                    ][:top_authors_per_repo]

                    for contributor in human_contributors:
                        candidate = {
                            "login": contributor["login"],
                            "from_repo": repo["full_name"],
                            "signal": f"contributor to {repo['name']}",
                            "contributions": contributor["contributions"],
                            "repo_stars": repo["stars"],
                            "repo_language": repo.get("language"),
                            "repo_topics": repo.get("topics", []),
                        }
                        all_candidates.append(candidate)

                except Exception as e:
                    logger.warning(f"Failed to get contributors for {repo['full_name']}: {e}")
                    continue

            # Remove duplicates by login
            unique_candidates = []
            seen_logins = set()
            for candidate in all_candidates:
                if candidate["login"] not in seen_logins:
                    unique_candidates.append(candidate)
                    seen_logins.add(candidate["login"])

            return ToolResult(
                success=True,
                data={"candidates": unique_candidates, "count": len(unique_candidates)},
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

            return ToolResult(success=True, data={"profile": profile})

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

    async def execute(self, login: str, repos: List[Dict], days: int = 90, **kwargs) -> ToolResult:
        """Find commit emails"""
        try:
            emails = set()
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            # Process repos this user contributed to
            user_repos = [r for r in repos if any(c.get("login") == login for c in r.get("contributors", []))]

            for repo in user_repos[:10]:  # Limit to avoid rate limits
                try:
                    # Get recent commits from this user
                    commits = await self._github_request(
                        f"/repos/{repo['full_name']}/commits",
                        params={
                            "author": login,
                            "since": cutoff_date,
                            "per_page": 20
                        }
                    )

                    for commit in commits:
                        if commit.get("commit", {}).get("author", {}).get("email"):
                            email = commit["commit"]["author"]["email"]
                            if "@" in email and not email.endswith("@users.noreply.github.com"):
                                emails.add(email)

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
