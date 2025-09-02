#!/usr/bin/env python3
"""
ci_people_finder.py
Bottom-up CI lead discovery from GitHub.

What it does
------------
1) Uses GitHub code search with your queries to find repos with CI + tests signals.
2) Keeps repos pushed since --since (default 90 days).
3) For each repo, gathers:
   - Committers to `.github/workflows/**` (since --since)
   - Top committers to `tests/**` (since --since)
   - CODEOWNERS for `.github/workflows/**` or tests paths
4) Maps GitHub users -> profile/company/bio and heuristically classifies:
   - "director" (decider) vs "maintainer" (practitioner)
5) Outputs:
   - directors.csv
   - maintainers.csv
   - people_signals.json  (raw signals + repos they came from)

Usage
-----
export GITHUB_TOKEN=ghp_xxx
python ci_people_finder.py \
  --since 2024-06-01 \
  --max-code-results 300 \
  --outdir ./out

Notes
-----
- Rate limits: handles Link pagination and sleeps on rate limit reset.
- Teams in CODEOWNERS are included as "team:org/team"; resolving members requires org perms and is skipped by default.
- No LinkedIn scraping: we generate a `linkedin_query` string for each person.
"""

import argparse
import collections
import csv
import datetime as dt
import json
import os
import re
import sys
import time
from urllib.parse import urlencode

import requests

GITHUB_API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
TOKEN = os.getenv("GITHUB_TOKEN")
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

# --- Config defaults ---------------------------------------------------------

DEFAULT_SINCE_DAYS = 90
DEFAULT_QUERIES = [
    # Simplified queries that work with GitHub search
    'path:.github/workflows language:YAML pytest',
    'path:.github/workflows language:YAML tox', 
    'filename:CODEOWNERS path:.github',
    'filename:CODEOWNERS tests',
]
TEST_DIR_HINTS = ["tests", "test", "testing", "src/test", "integration", "e2e", "spec"]
CODEOWNERS_LOCATIONS = [
    "CODEOWNERS",
    ".github/CODEOWNERS",
    "docs/CODEOWNERS",
]

DIRECTOR_KEYWORDS = [
    "cto", "chief technology officer", "vp", "vice president", "director",
    "head of", "head, ", "engineering manager", "manager", "lead",
    "principal", "staff engineer", "founder", "co-founder", "cofounder",
    "architect", "distinguished", "sr. director", "senior director",
]
MAINTAINER_KEYWORDS = [
    "sre", "devops", "ci", "ci/cd", "platform", "build", "release",
    "infra", "infrastructure", "reliability", "pipeline", "github actions",
    "buildkite", "travis", "circleci", "jenkins", "tox", "pytest",
    "maintainer", "committer", "pmc",
]
BOT_HINTS = ["[bot]", "bot", "actions-user", "gardener", "dependabot", "weblate", "transbot", "travis"]

# --- Helpers ----------------------------------------------------------------

def iso_now() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def parse_date(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))

def since_to_iso(since_str: str | None, default_days=DEFAULT_SINCE_DAYS) -> str:
    if since_str:
        # YYYY-MM-DD
        return dt.datetime.fromisoformat(since_str).isoformat() + "Z"
    return (dt.datetime.utcnow() - dt.timedelta(days=default_days)).replace(microsecond=0).isoformat() + "Z"

def sleep_until(reset_epoch: int):
    wait = max(0, reset_epoch - int(time.time())) + 1
    time.sleep(wait)

def gh_get(url, params=None):
    """GET with rate-limit handling; returns (json, resp)."""
    while True:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=60)
        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            reset = int(resp.headers.get("X-RateLimit-Reset", "0"))
            sleep_until(reset)
            continue
        if resp.status_code >= 400:
            raise RuntimeError(f"GitHub GET {url} failed {resp.status_code}: {resp.text[:200]}")
        try:
            return resp.json(), resp
        except Exception:
            return None, resp

def gh_get_all(url, params=None, max_pages=15):
    out = []
    page = 1
    params = dict(params or {})
    while page <= max_pages:
        params["per_page"] = params.get("per_page", 100)
        params["page"] = page
        j, resp = gh_get(url, params=params)
        if isinstance(j, dict) and "items" in j:  # search
            out.extend(j["items"])
            # GitHub search caps ~1000 results
            if len(out) >= j.get("total_count", 0) or len(out) >= 1000:
                break
        elif isinstance(j, list):
            out.extend(j)
            if "next" not in (resp.links or {}):
                break
        else:
            break
        if "next" not in (resp.links or {}):
            break
        page += 1
    return out

def is_probable_bot(login: str, bio: str | None, acct_type: str | None) -> bool:
    bio_l = (bio or "").lower()
    login_l = (login or "").lower()
    if acct_type and acct_type.lower() == "bot":
        return True
    return any(b in login_l for b in BOT_HINTS) or ("bot" in bio_l)

def clean_company(raw: str | None) -> str:
    if not raw:
        return ""
    c = raw.strip()
    c = re.sub(r"^@+", "", c)  # remove leading @
    c = re.sub(r"\s+", " ", c)
    return c

def make_linkedin_query(name: str, company: str, location: str) -> str:
    parts = []
    if name: parts.append(f'"{name}"')
    if company: parts.append(f'"{company}"')
    if location: parts.append(location)
    return " ".join(parts)

# --- Search phase ------------------------------------------------------------

def search_code_repos(queries: list[str], max_code_results: int, since_iso: str) -> set[str]:
    repos: set[str] = set()
    for q in queries:
        print(f"  Searching: {q}")
        # We cannot rely on pushed: qualifier in code search; post-filter by repo pushed_at
        params = {"q": q, "per_page": 100}
        items = gh_get_all(f"{GITHUB_API}/search/code", params=params)
        for it in items[:max_code_results]:  # soft cap per query
            repo = it.get("repository", {}).get("full_name")
            if not repo:
                continue
            # Filter by pushed_at
            rj, _ = gh_get(f"{GITHUB_API}/repos/{repo}")
            pushed_at = rj.get("pushed_at") if rj else None
            if pushed_at and parse_date(pushed_at) >= parse_date(since_iso):
                repos.add(repo)
        print(f"    Found {len([r for r in repos if any(q_repo in str(r) for q_repo in [repo])])} repos from this query")
    return repos

# --- Repo analysis -----------------------------------------------------------

def list_committers_since(repo: str, path: str, since_iso: str) -> dict:
    """Return {login_or_email: count} for commits touching path since date."""
    url = f"{GITHUB_API}/repos/{repo}/commits"
    committers = collections.Counter()
    items = gh_get_all(url, params={"path": path, "since": since_iso})
    for c in items:
        # Prefer GitHub user login; fallback to committer/author emails
        user_login = None
        if c.get("author") and c["author"].get("login"):
            user_login = c["author"]["login"]
        elif c.get("committer") and c["committer"].get("login"):
            user_login = c["committer"]["login"]
        else:
            # fallback: email key to not lose signal; mark as email:<email>
            email = (c.get("commit", {}).get("author", {}) or {}).get("email") \
                    or (c.get("commit", {}).get("committer", {}) or {}).get("email")
            if email:
                user_login = f"email:{email}"
        if user_login:
            committers[user_login] += 1
    return dict(committers)

def fetch_codeowners(repo: str) -> tuple[str, str]:
    """Return (location, content) if found; else ('','')."""
    for loc in CODEOWNERS_LOCATIONS:
        url = f"{GITHUB_API}/repos/{repo}/contents/{loc}"
        j, resp = gh_get(url)
        if resp.status_code == 404:
            continue
        if j and j.get("encoding") == "base64" and j.get("content"):
            import base64
            try:
                txt = base64.b64decode(j["content"]).decode("utf-8", errors="replace")
                return loc, txt
            except Exception:
                pass
    return "", ""

def parse_codeowners_for_paths(text: str) -> dict:
    """Return {path_pattern: [@owners]} for path lines that mention workflows/tests."""
    owners_by_path = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Split like: <pattern> <owner1> <owner2> ...
        parts = re.split(r"\s+", line)
        if len(parts) < 2:
            continue
        pattern, owners = parts[0], parts[1:]
        # Heuristic focus
        if (".github/workflows" in pattern) or ("tests" in pattern) or ("/test" in pattern):
            owners_by_path.setdefault(pattern, [])
            owners_by_path[pattern].extend(owners)
    return owners_by_path

# --- People aggregation ------------------------------------------------------

def normalize_owner_token(tok: str) -> str:
    # Keep @username as username; teams as team:org/team
    tok = tok.strip()
    if not tok.startswith("@"):
        return ""
    tok = tok[1:]
    if "/" in tok:
        return f"team:{tok}"
    return tok

def collect_people_from_repo(repo: str, since_iso: str) -> dict:
    """
    Returns a dict keyed by handle with accumulated signals:
    {
      handle: {
        "signals": set([...]),
        "repos": set([...]),
        "counts": {"workflows_commits": N, "tests_commits": M}
      }
    }
    """
    people = {}

    # Workflows committers
    wf_committers = list_committers_since(repo, ".github/workflows", since_iso)
    for handle, n in wf_committers.items():
        if handle.startswith("email:"):
            # we'll keep emails as contact signals, but won't fetch profile for them
            ppl = people.setdefault(handle, {"signals": set(), "repos": set(), "counts": collections.Counter()})
            ppl["signals"].add("committed_workflows")
            ppl["repos"].add(repo)
            ppl["counts"]["workflows_commits"] += n
            continue
        ppl = people.setdefault(handle, {"signals": set(), "repos": set(), "counts": collections.Counter()})
        ppl["signals"].add("committed_workflows")
        ppl["repos"].add(repo)
        ppl["counts"]["workflows_commits"] += n

    # Tests committers (aggregate across common dirs)
    tests_counts = collections.Counter()
    for p in TEST_DIR_HINTS:
        c = list_committers_since(repo, p, since_iso)
        for h, n in c.items():
            tests_counts[h] += n
    for handle, n in tests_counts.items():
        ppl = people.setdefault(handle, {"signals": set(), "repos": set(), "counts": collections.Counter()})
        ppl["signals"].add("committed_tests")
        ppl["repos"].add(repo)
        ppl["counts"]["tests_commits"] += n

    # CODEOWNERS
    loc, text = fetch_codeowners(repo)
    if text:
        by_path = parse_codeowners_for_paths(text)
        for pattern, owners in by_path.items():
            for raw in owners:
                norm = normalize_owner_token(raw)
                if not norm:
                    continue
                ppl = people.setdefault(norm, {"signals": set(), "repos": set(), "counts": collections.Counter()})
                if ".github/workflows" in pattern:
                    ppl["signals"].add("codeowner_workflows")
                if ("tests" in pattern) or ("/test" in pattern):
                    ppl["signals"].add("codeowner_tests")
                ppl["repos"].add(repo)

    return people

def fetch_user_profile(login: str) -> dict:
    """Return GitHub user metadata (empty dict if not found)."""
    j, _ = gh_get(f"{GITHUB_API}/users/{login}")
    if not j or "message" in j:
        return {}
    return j

def classify_role(bio: str | None, signals: set[str]) -> str:
    b = (bio or "").lower()
    # Practitioners first: if they have concrete CI ownership signals, treat as maintainer
    if {"committed_workflows", "codeowner_workflows"} & signals:
        return "maintainer"
    if {"committed_tests", "codeowner_tests"} & signals:
        return "maintainer"
    # Else use titles
    if any(k in b for k in DIRECTOR_KEYWORDS):
        return "director"
    if any(k in b for k in MAINTAINER_KEYWORDS):
        return "maintainer"
    # Default to maintainer if they have any signal at all
    return "maintainer" if signals else "contributor"

def looks_like_director(bio: str | None, company: str | None) -> bool:
    b = (bio or "").lower()
    c = (company or "").lower()
    if any(k in b for k in DIRECTOR_KEYWORDS):
        return True
    # light heuristic: principal/staff w/ company present -> decider-ish
    return (("principal" in b or "staff" in b) and bool(company))

# --- Main --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="ISO date YYYY-MM-DD (default: 90 days ago)")
    ap.add_argument("--max-code-results", type=int, default=300, help="Max code search results to consider per query")
    ap.add_argument("--queries", nargs="*", help="Override code search queries")
    ap.add_argument("--outdir", default="./out", help="Output directory")
    args = ap.parse_args()

    if not TOKEN:
        print("ERROR: set GITHUB_TOKEN env var.", file=sys.stderr)
        sys.exit(1)

    since_iso = since_to_iso(args.since)
    queries = args.queries if args.queries else DEFAULT_QUERIES
    os.makedirs(args.outdir, exist_ok=True)

    print(f"[info] since = {since_iso}")
    print(f"[info] queries =")
    for q in queries:
        print(f"       - {q}")

    print("[step] searching code...")
    repos = search_code_repos(queries, args.max_code_results, since_iso)
    print(f"[info] repos after pushed_at filter: {len(repos)}")

    # Per-repo collection
    aggregated: dict[str, dict] = {}
    for i, repo in enumerate(sorted(repos)):
        print(f"[repo {i+1}/{len(repos)}] {repo}")
        try:
            ppl = collect_people_from_repo(repo, since_iso)
            for handle, payload in ppl.items():
                agg = aggregated.setdefault(handle, {"signals": set(), "repos": set(), "counts": collections.Counter()})
                agg["signals"] |= payload["signals"]
                agg["repos"] |= payload["repos"]
                agg["counts"].update(payload["counts"])
        except Exception as e:
            print(f"  ! error on {repo}: {e}")

    # Prepare user profiles (only for handles that are not raw emails or teams)
    people_rows = []
    for handle, payload in aggregated.items():
        if handle.startswith("email:"):
            email = handle.split("email:", 1)[1]
            row = {
                "login": "",
                "name": "",
                "email": email,
                "company": "",
                "location": "",
                "bio": "",
                "followers": 0,
                "public_repos": 0,
                "html_url": "",
                "signals": "; ".join(sorted(payload["signals"])),
                "source_repos": "; ".join(sorted(payload["repos"])),
                "role_type": "contributor",
                "linkedin_query": email,
            }
            people_rows.append(row)
            continue

        if handle.startswith("team:"):
            row = {
                "login": handle,
                "name": "",
                "email": "",
                "company": "",
                "location": "",
                "bio": "",
                "followers": 0,
                "public_repos": 0,
                "html_url": "",
                "signals": "; ".join(sorted(payload["signals"])) + "; team",
                "source_repos": "; ".join(sorted(payload["repos"])),
                "role_type": "maintainer",  # conservative
                "linkedin_query": handle.replace("team:", "").replace("/", " "),
            }
            people_rows.append(row)
            continue

        prof = fetch_user_profile(handle)
        if not prof:
            # keep the handle with minimal info
            prof = {"login": handle, "bio": "", "company": "", "location": "",
                    "followers": 0, "public_repos": 0, "html_url": "", "type": "User", "name": ""}

        # Filter bots
        if is_probable_bot(prof.get("login",""), prof.get("bio",""), prof.get("type","")):
            continue

        name = prof.get("name") or ""
        company = clean_company(prof.get("company"))
        location = prof.get("location") or ""
        role_type = classify_role(prof.get("bio") or "", payload["signals"])

        row = {
            "login": prof.get("login",""),
            "name": name,
            "email": prof.get("email") or "",
            "company": company,
            "location": location,
            "bio": prof.get("bio") or "",
            "followers": int(prof.get("followers") or 0),
            "public_repos": int(prof.get("public_repos") or 0),
            "html_url": prof.get("html_url") or "",
            "signals": "; ".join(sorted(payload["signals"])),
            "source_repos": "; ".join(sorted(payload["repos"])),
            "role_type": role_type,
            "linkedin_query": make_linkedin_query(name, company, location),
        }
        people_rows.append(row)

    # Split directors vs maintainers
    directors, maintainers = [], []
    for r in people_rows:
        # If they have strong CI signals, they are maintainers. Promote to director if bio/company looks senior.
        if r["role_type"] == "director" or looks_like_director(r["bio"], r["company"]):
            directors.append(r)
        else:
            maintainers.append(r)

    def write_csv(path, rows):
        cols = ["login","name","email","company","location","bio","followers","public_repos",
                "html_url","signals","source_repos","role_type","linkedin_query"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for row in rows:
                w.writerow(row)

    # Save
    directors_path = os.path.join(args.outdir, "directors.csv")
    maintainers_path = os.path.join(args.outdir, "maintainers.csv")
    signals_path = os.path.join(args.outdir, "people_signals.json")

    write_csv(directors_path, directors)
    write_csv(maintainers_path, maintainers)
    with open(signals_path, "w", encoding="utf-8") as f:
        json.dump(aggregated, f, indent=2, default=lambda x: list(x) if isinstance(x, (set,)) else x)

    print(f"[done] wrote {directors_path} ({len(directors)} rows)")
    print(f"[done] wrote {maintainers_path} ({len(maintainers)} rows)")
    print(f"[done] wrote {signals_path}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
