#!/usr/bin/env python3
"""
github_ci_people_scraper.py

Bottom-up GitHub CI maintainer finder:
- Code-search workflow YAMLs for pytest/tox (no pushed/fork in code search → avoids 422)
- Deduplicate to repos; fetch repo metadata and filter by pushed_at >= --since
- For each repo:
    • recent committers to .github/workflows/ (last 90d)
    • top committers to tests/ (last 180d)
    • CODEOWNERS owners for workflows/tests
- Enrich each user from GitHub profile; optionally try to extract public commit emails
- Heuristically flag "director-like" titles from bio/company
- Output one CSV (role column: Maintainer, Practitioner, Director-like)

Auth: GITHUB_TOKEN (supports rotation via GITHUB_TOKEN_2.._9)
"""

import argparse
import base64
import csv
import os
import re
import sys
import time
from collections import defaultdict, Counter
from tqdm import tqdm
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------- Utils

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")

def parse_date(s: str) -> datetime:
    # Accept YYYY-MM-DD
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)

def short(s: Optional[str], n: int = 160) -> str:
    if not s:
        return ""
    s = s.strip()
    return s if len(s) <= n else s[: n - 1] + "…"

def human_sleep(sec: float):
    if sec > 0:
        time.sleep(sec)

# ---------- Session + Auth

def build_session(timeout: int = 15) -> requests.Session:
    sess = requests.Session()
    retry = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    sess.request = _with_timeout(sess.request, timeout)
    return sess

def _with_timeout(request_func, default_timeout):
    def wrapped(method, url, **kwargs):
        kwargs.setdefault("timeout", default_timeout)
        return request_func(method, url, **kwargs)
    return wrapped

def auth_header_for(token: str) -> str:
    t = token.strip()
    if t.startswith("ghp_") or t.startswith("ghs_"):  # classic or app installation
        return f"token {t}"
    return f"Bearer {t}"  # fine-grained or unknown → works

def collect_tokens() -> List[str]:
    tokens = []
    if os.getenv("GITHUB_TOKEN"):
        tokens.append(os.getenv("GITHUB_TOKEN").strip().strip('"').strip("'"))
    for i in range(2, 10):
        v = os.getenv(f"GITHUB_TOKEN_{i}")
        if v:
            v = v.strip().strip('"').strip("'")
            if v and v not in tokens:
                tokens.append(v)
    return [t for t in tokens if t]

class GHClient:
    def __init__(self, tokens: List[str], timeout: int = 15, user_agent: str = "ci-people-scraper/1.0"):
        if not tokens:
            print("❌ No GitHub token found. Set GITHUB_TOKEN (and optionally GITHUB_TOKEN_2.._9).", file=sys.stderr)
            sys.exit(1)
        self.tokens = tokens
        self.idx = 0
        self.sess = build_session(timeout)
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": user_agent,
            "Authorization": auth_header_for(self.tokens[self.idx]),
        }

    def _rotate_if_needed(self) -> bool:
        # Check rate for current token; if near empty, try others
        url = "https://api.github.com/rate_limit"
        try:
            r = self.sess.get(url, headers=self.headers)
            if r.status_code == 200:
                core = (r.json().get("resources", {}) or {}).get("core", {}) or {}
                if core.get("remaining", 0) > 100:
                    return False
        except Exception:
            return False

        # rotate
        for j, tok in enumerate(self.tokens):
            if j == self.idx:
                continue
            hdrs = dict(self.headers)
            hdrs["Authorization"] = auth_header_for(tok)
            try:
                rr = self.sess.get(url, headers=hdrs)
                if rr.status_code == 200:
                    core = (rr.json().get("resources", {}) or {}).get("core", {}) or {}
                    if core.get("remaining", 0) > 300:
                        self.idx = j
                        self.headers = hdrs
                        print(f"🔄 Switched to backup token #{j+1} with {core.get('remaining')} remaining")
                        return True
            except Exception:
                continue
        return False

    def get(self, url: str, params: Optional[Dict] = None, allow_404: bool = False) -> Optional[requests.Response]:
        while True:
            r = self.sess.get(url, headers=self.headers, params=params or {})
            if r.status_code == 403 and "rate limit" in r.text.lower():
                reset = int(r.headers.get("X-RateLimit-Reset", "0"))
                wait = max(0, reset - int(time.time()) + 3)
                if self._rotate_if_needed():
                    continue
                print(f"⏳ Rate limited. Sleeping {wait}s …")
                human_sleep(wait)
                continue
            if allow_404 and r.status_code == 404:
                return None
            return r

# ---------- Search: code search for CI signals, then repo filter by pushed_at

CODE_SEARCH_QUERIES = [
    'path:.github/workflows language:YAML (pytest OR tox) (uses: actions/setup-python OR "python-version:")',
]

def code_search_repos(gh: GHClient, max_repos: int, sleep: float = 0.5) -> Set[str]:
    repos: Set[str] = set()
    url = "https://api.github.com/search/code"
    for q in CODE_SEARCH_QUERIES:
        page = 1
        while len(repos) < max_repos and page <= 10:
            params = {"q": q, "per_page": 100, "page": page}
            r = gh.get(url, params=params)
            if r.status_code == 422:
                # validation error (rare now, but be defensive)
                break
            if r.status_code != 200:
                break
            items = (r.json() or {}).get("items", [])
            if not items:
                break
            for it in items:
                repo = (it.get("repository") or {}).get("full_name")
                if repo:
                    repos.add(repo)
                    if len(repos) >= max_repos:
                        break
            if len(items) < 100:
                break
            page += 1
            human_sleep(sleep)
    return repos

def get_repo(gh: GHClient, full_name: str) -> Optional[Dict]:
    r = gh.get(f"https://api.github.com/repos/{full_name}")
    if r.status_code == 200:
        return r.json()
    return None

# ---------- People extraction per repo

def list_commit_authors(gh: GHClient, full_name: str, path: str, since_iso: str, per_page: int = 100) -> List[Dict]:
    """Return list of commit dicts (API response) limited to path+since."""
    out = []
    url = f"https://api.github.com/repos/{full_name}/commits"
    page = 1
    while page <= 10:
        params = {"path": path, "since": since_iso, "per_page": per_page, "page": page}
        r = gh.get(url, params=params)
        if r.status_code != 200:
            break
        page_items = r.json() or []
        if not page_items:
            break
        out.extend(page_items)
        if len(page_items) < per_page:
            break
        page += 1
    return out

def top_test_committers(gh: GHClient, full_name: str, since_iso: str) -> List[Tuple[str, int]]:
    commits = list_commit_authors(gh, full_name, "tests", since_iso)
    ctr: Counter = Counter()
    for c in commits:
        author = (c.get("author") or {})
        login = author.get("login")
        if login:
            ctr[login] += 1
    return ctr.most_common(5)

def workflow_committers(gh: GHClient, full_name: str, since_iso: str) -> Set[str]:
    commits = list_commit_authors(gh, full_name, ".github/workflows", since_iso)
    out: Set[str] = set()
    for c in commits:
        author = (c.get("author") or {})
        login = author.get("login")
        if login:
            out.add(login)
    return out

def read_codeowners_text(gh: GHClient, full_name: str) -> Optional[str]:
    for path in ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"):
        r = gh.get(f"https://api.github.com/repos/{full_name}/contents/{path}", allow_404=True)
        if r is None:
            continue
        if r.status_code == 200:
            data = r.json() or {}
            content = data.get("content")
            if content:
                try:
                    return base64.b64decode(content).decode("utf-8", errors="ignore")
                except Exception:
                    pass
    return None

def owners_from_codeowners(text: str) -> Set[str]:
    owners: Set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # strip trailing inline comment
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        parts = line.split()
        if len(parts) < 2:
            continue
        pattern, handles = parts[0], parts[1:]
        if any(k in pattern for k in (".github/workflows", "tests")):
            for h in handles:
                h = h.lstrip("@").strip()
                if "/" in h:  # org/team; skip individual resolution here
                    continue
                if h:
                    owners.add(h)
    return owners

def fetch_user(gh: GHClient, login: str) -> Optional[Dict]:
    r = gh.get(f"https://api.github.com/users/{login}")
    if r.status_code == 200:
        return r.json()
    return None

def try_commit_emails_for_user(gh: GHClient, full_name: str, login: str, since_iso: str, max_commits: int = 30) -> Optional[str]:
    """Search commits authored by login since date for a non-noreply email."""
    url = f"https://api.github.com/repos/{full_name}/commits"
    r = gh.get(url, params={"author": login, "since": since_iso, "per_page": max_commits})
    if r.status_code != 200:
        return None
    for c in r.json() or []:
        email = (((c.get("commit") or {}).get("author") or {}).get("email")) or ""
        if email and "@users.noreply.github.com" not in email and "@" in email:
            return email
    return None

TITLE_KEYS = ("head of", "director", "vp", "vice president", "chief", "cto", "ceo", "manager", "lead", "engineering manager")

def guess_role(bio: str, company: str) -> str:
    blob = f"{bio or ''} {company or ''}".lower()
    if any(k in blob for k in TITLE_KEYS):
        return "Director-like"
    return "Maintainer"  # default; we'll keep a separate flag for pure practitioners if needed

# ---------- AI/Python Detection Functions

STAR_BUCKETS = [
    (10000, "10k+"),
    (5000, "5k–9.9k"),
    (1000, "1k–4.9k"),
    (100, "100–999"),
    (0, "<100"),
]

AI_KEYWORDS = [
    "torch", "torchvision", "torchaudio", "transformers", "diffusers", "accelerate", "trl",
    "sentencepiece", "jax", "flax", "tensorflow", "keras", "onnx", "onnxruntime",
    "lightgbm", "xgboost", "catboost", "scikit-learn", "faiss", "chromadb", "qdrant",
    "langchain", "llama-index", "vllm", "triton", "bitsandbytes"
]
DEP_FILES = ["pyproject.toml", "requirements.txt", "setup.cfg", "setup.py"]

def is_python_workflow(yaml_text: str) -> bool:
    s = (yaml_text or "").lower()
    return ("uses: actions/setup-python" in s) or ("python-version:" in s)

def looks_python_repo(repo: dict) -> bool:
    if (repo.get("language") or "").lower() == "python":
        return True
    # Let content checks decide if not labeled as Python
    return False

def repo_has_python_files(gh, full_name: str) -> bool:
    # Any of the classic python config files present?
    for fname in DEP_FILES + ["tox.ini"]:
        try:
            r = gh.get(f"/repos/{full_name}/contents/{fname}")
            if isinstance(r, dict) and r.get("name") == fname:
                return True
        except Exception:
            continue
    return False

def _has_file(gh_session, headers, full_name: str, path: str) -> bool:
    try:
        r = gh_session.get(f"https://api.github.com/repos/{full_name}/contents/{path}", headers=headers, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

def _code_search_total(gh_session, headers, q: str) -> int:
    try:
        r = gh_session.get("https://api.github.com/search/code", headers=headers, params={"q": q, "per_page": 1}, timeout=10)
        if r.status_code == 200:
            return (r.json() or {}).get("total_count", 0)
    except Exception:
        pass
    return 0

def detect_dependabot(gh_session, headers, full_name: str) -> bool:
    return _has_file(gh_session, headers, full_name, ".github/dependabot.yml")

def detect_renovate(gh_session, headers, full_name: str) -> bool:
    return (_has_file(gh_session, headers, full_name, "renovate.json") or 
            _has_file(gh_session, headers, full_name, ".github/renovate.json") or 
            _has_file(gh_session, headers, full_name, ".github/renovate.json5"))

def detect_notebooks(gh_session, headers, full_name: str) -> bool:
    q = f'repo:{full_name} extension:ipynb'
    return _code_search_total(gh_session, headers, q) > 0

def detect_gpu_ci_hints(gh_session, headers, full_name: str) -> bool:
    q = (
        f'repo:{full_name} path:.github/workflows '
        f'(cuda OR "nvidia-smi" OR cudatoolkit OR "pip install torch --index-url")'
    )
    return _code_search_total(gh_session, headers, q) > 0

def detect_ai_signals(gh_session, headers, full_name: str) -> int:
    # count how many distinct AI keywords appear in common dependency files
    kw_query = " OR ".join(AI_KEYWORDS)
    q = (
        f'repo:{full_name} '
        f'filename:requirements.txt filename:pyproject.toml filename:setup.cfg filename:setup.py '
        f'({kw_query})'
    )
    return min(10, _code_search_total(gh_session, headers, q))  # cap for sanity

def detect_copilot_hint(gh_session, headers, full_name: str) -> bool:
    # There's no public API to see Copilot enablement; use light heuristics.
    q = f'repo:{full_name} (copilot) (in:file OR in:readme OR path:.github/workflows)'
    return _code_search_total(gh_session, headers, q) > 0

def score_repo(repo: dict, signals: dict) -> float:
    # small, explainable score to rank preview list with AI/LLM bias
    import math
    stars = repo.get("stargazers_count", 0)
    pushed = repo.get("pushed_at")
    recency = 0.0
    try:
        if pushed:
            dt = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
            days = max(1, (datetime.utcnow().replace(tzinfo=timezone.utc) - dt).days)
            recency = 1.0 / math.log2(days + 1.5)  # more weight if recently pushed
    except Exception:
        pass
    
    base_score = (
        1.8 * math.log10(max(1, stars)) +
        2.2 * min(1, signals["ai_hits"]/3) +
        1.0 * (1 if signals["gpu_ci"] else 0) +
        0.5 * (1 if signals["notebooks"] else 0) +
        0.4 * (1 if signals["dependabot"] else 0) +
        0.2 * (1 if signals["renovate"] else 0) +
        1.5 * recency
    )
    
    # LLM stack weighting - extra bias toward LLM infra
    llm_boost = 0
    if signals["ai_hits"] >= 2:  # Strong AI signal
        llm_boost = 0.5
    
    # Extra boost for high-value LLM keywords
    llm_keywords = ["transformers", "vllm", "llama-index", "langchain", "bitsandbytes", "triton"]
    # Note: In a real implementation, you'd re-check the repo content for these specific keywords
    # For now, we'll use the ai_hits count as a proxy
    if signals["ai_hits"] >= 3:  # Very strong AI signal likely includes LLM keywords
        llm_boost += 0.3
    
    return base_score + llm_boost

def discovery_preview(session, headers, repos, top_n=150):
    rows = []
    for r in repos[:top_n]:
        full = r["full_name"]
        sig = {
            "dependabot": detect_dependabot(session, headers, full),
            "renovate": detect_renovate(session, headers, full),
            "notebooks": detect_notebooks(session, headers, full),
            "gpu_ci": detect_gpu_ci_hints(session, headers, full),
            "ai_hits": detect_ai_signals(session, headers, full),
            "copilot_hint": detect_copilot_hint(session, headers, full),  # heuristic
        }
        s = score_repo(r, sig)
        rows.append((s, r, sig))

    # Rank by score
    rows.sort(key=lambda x: x[0], reverse=True)

    # Bucket by stars for display
    buckets = {b[1]: [] for b in STAR_BUCKETS}
    for score, repo, sig in rows:
        st = repo.get("stargazers_count", 0)
        label = "<100"
        for thresh, name in STAR_BUCKETS:
            if st >= thresh:
                label = name
                break
        buckets[label].append((score, repo, sig))

    print("\n🔎 Discovery preview (ranked within star buckets):")
    for label in ["10k+", "5k–9.9k", "1k–4.9k", "100–999", "<100"]:
        items = buckets[label][:15]  # show top few per bucket
        if not items:
            continue
        print(f"\n⭐ {label} — {len(buckets[label])} repos")
        for score, repo, sig in items:
            lang = repo.get("language") or ""
            stars = repo.get("stargazers_count", 0)
            name = repo["full_name"]
            flags = []
            if sig["ai_hits"]: flags.append(f"AIx{sig['ai_hits']}")
            if sig["gpu_ci"]: flags.append("GPU-CI")
            if sig["notebooks"]: flags.append("NB")
            if sig["dependabot"]: flags.append("Dependabot")
            if sig["renovate"]: flags.append("Renovate")
            if sig["copilot_hint"]: flags.append("Copilot(?)")
            print(f"• {name:50} ⭐ {stars:>6}  ({lang})  [{', '.join(flags) or '—'}]")

def write_discovery_csv(rows, path="data/discovery_repos.csv"):
    import csv, os
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "full_name","stars","language","updated_at","score",
            "ai_hits","gpu_ci","notebooks","dependabot","renovate","copilot_hint","html_url"
        ])
        w.writeheader()
        for score, repo, sig in rows:
            w.writerow({
                "full_name": repo["full_name"],
                "stars": repo.get("stargazers_count", 0),
                "language": repo.get("language") or "",
                "updated_at": repo.get("pushed_at"),
                "score": round(score, 3),
                "ai_hits": sig["ai_hits"],
                "gpu_ci": sig["gpu_ci"],
                "notebooks": sig["notebooks"],
                "dependabot": sig["dependabot"],
                "renovate": sig["renovate"],
                "copilot_hint": sig["copilot_hint"],
                "html_url": repo.get("html_url"),
            })
    print(f"\n💾 Wrote discovery CSV → {path}")

def repo_has_ai_signals(gh, full_name: str) -> bool:
    # Check dependency files for AI keywords (fast, low rate impact)
    for fname in DEP_FILES:
        try:
            r = gh.get(f"/repos/{full_name}/contents/{fname}")
            if isinstance(r, dict) and r.get("content"):
                import base64
                content = base64.b64decode(r["content"]).decode("utf-8", errors="ignore").lower()
                if any(keyword in content for keyword in AI_KEYWORDS):
                    return True
        except Exception:
            continue
    return False

# ---------- Main pipeline

def run(
    since: datetime,
    max_repos: int,
    out_csv: str,
    include_personal_repos: bool,
    min_stars: int,
    find_emails: bool,
    verbose: bool,
    target_leads: int = 0,
    discover_only: bool = False,
    discover_top: int = 150,
):
    tokens = collect_tokens()
    gh = GHClient(tokens)

    print("🔎 Code-searching for workflow YAMLs mentioning pytest/tox …")
    repos = code_search_repos(gh, max_repos=max_repos)
    print(f"• Code search yielded {len(repos)} unique repos")

    # Fetch repo metadata + filter: pushed_at >= since, not archived, not fork (unless personal included)
    picked: List[Dict] = []
    since_iso_date = since.date()
    for full in repos:
        repo = get_repo(gh, full)
        if not repo:
            continue
        if repo.get("archived"):
            continue
        if (not include_personal_repos) and (repo.get("owner", {}).get("type") != "Organization"):
            continue
        if repo.get("fork"):
            continue
        if (repo.get("stargazers_count") or 0) < min_stars:
            continue
        pushed_at = repo.get("pushed_at")
        if not pushed_at:
            continue
        try:
            pushed_dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        except Exception:
            continue
        if pushed_dt.date() < since_iso_date:
            continue
        picked.append(repo)

    print(f"• After repo filters (stars≥{min_stars}, pushed≥{since_iso_date}, not-archived, not-fork{'' if include_personal_repos else ', orgs only'}): {len(picked)} repos")

    # Apply Python+AI filtering to picked repos
    print("🔍 Applying Python+AI filters...")
    filtered = []
    for repo in picked:
        # Python validation
        py_ok = looks_python_repo(repo) or repo_has_python_files(gh, repo["full_name"])
        if not py_ok:
            continue

        # AI signals validation
        if not repo_has_ai_signals(gh, repo["full_name"]):
            continue

        filtered.append(repo)

    picked = filtered[:max_repos]
    print(f"• After Python+AI filters: {len(picked)} repos")

    # Discovery preview mode
    if discover_only or discover_top:
        print("\n🔍 Running discovery preview...")
        # Build session for discovery functions
        session = build_session()
        headers = HEADERS.copy()
        
        # Build ranked rows for discovery
        ranked = []
        for r in picked[:discover_top]:
            full = r["full_name"]
            sig = {
                "dependabot": detect_dependabot(session, headers, full),
                "renovate": detect_renovate(session, headers, full),
                "notebooks": detect_notebooks(session, headers, full),
                "gpu_ci": detect_gpu_ci_hints(session, headers, full),
                "ai_hits": detect_ai_signals(session, headers, full),
                "copilot_hint": detect_copilot_hint(session, headers, full),
            }
            ranked.append((score_repo(r, sig), r, sig))

        # Sort by score and show preview
        ranked.sort(key=lambda x: x[0], reverse=True)
        discovery_preview(session, headers, [r for _, r, _ in ranked], top_n=len(ranked))
        write_discovery_csv(ranked, path="data/discovery_repos.csv")

        if discover_only:
            print("\n🏁 Discovery complete. Use without --discover-only to scrape people.")
            return

    # Prepare CSV
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    fieldnames = [
        "org", "repo", "repo_url", "repo_stars", "repo_language", "repo_pushed_at",
        "login", "name", "company", "location", "bio_short",
        "email", "profile_url",
        "signals", "is_codeowner", "role",
    ]
    f = open(out_csv, "w", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()

    # Process repos
    people_seen_repo_user: Set[Tuple[str, str]] = set()  # (repo_full_name, login)
    unique_people_global: Set[str] = set()

    # Initialize leads progress bar
    leads_with_email_count = 0
    target_for_progress = target_leads if target_leads > 0 else 100
    leads_bar = tqdm(total=target_for_progress, desc="Leads 0%", position=0, leave=True)

    def _tick_leads_bar(current):
        pct = int(100 * min(1.0, current / max(1, target_for_progress)))
        leads_bar.set_description(f"Leads {current}/{target_for_progress} ({pct}%)")
        leads_bar.n = min(current, target_for_progress)
        leads_bar.refresh()

    pbar = tqdm(picked, desc=f"Processing repos ({len(picked)})", unit="repo", position=1)

    def _update_postfix():
        if target_leads and target_leads > 0:
            pct = int(min(100, round(100 * len(unique_people_global) / target_leads)))
            pbar.set_postfix_str(f"leads {len(unique_people_global)}/{target_leads} ({pct}%)")
        else:
            pbar.set_postfix_str(f"leads {len(unique_people_global)}")

    for repo in pbar:
        full = repo["full_name"]
        org = repo.get("owner", {}).get("login", "")
        print(f"\n📦 {full}  ⭐ {repo.get('stargazers_count',0)}  ({repo.get('language')})")

        since_workflows_iso = to_iso(utc_now() - timedelta(days=90))
        since_tests_iso = to_iso(utc_now() - timedelta(days=180))

        wf_committers = workflow_committers(gh, full, since_workflows_iso)
        top_test = top_test_committers(gh, full, since_tests_iso)
        codeowners_raw = read_codeowners_text(gh, full)
        codeowners = owners_from_codeowners(codeowners_raw) if codeowners_raw else set()

        if verbose:
            print(f"  • workflow committers (90d): {len(wf_committers)}  |  top test committers (180d): {len(top_test)}  |  codeowners: {len(codeowners)}")

        signals: Dict[str, List[str]] = defaultdict(list)
        for u in wf_committers:
            signals[u].append("workflow_committer")
        for u, n in top_test:
            signals[u].append(f"tests_committer:{n}")
        for u in codeowners:
            signals[u].append("codeowner")

        for login, sigs in signals.items():
            key = (full, login)
            if key in people_seen_repo_user:
                continue
            people_seen_repo_user.add(key)

            user = fetch_user(gh, login) or {}
            name = user.get("name") or ""
            company = user.get("company") or ""
            loc = user.get("location") or ""
            bio = user.get("bio") or ""
            is_codeowner = any(s.startswith("codeowner") for s in sigs)
            role = guess_role(bio, company)
            email = None
            if find_emails:
                email = try_commit_emails_for_user(gh, full, login, since_tests_iso) or user.get("email")

            # write row
            w.writerow({
                "org": org,
                "repo": full,
                "repo_url": repo.get("html_url"),
                "repo_stars": repo.get("stargazers_count"),
                "repo_language": repo.get("language") or "",
                "repo_pushed_at": repo.get("pushed_at"),
                "login": login,
                "name": name,
                "company": (company or "").strip(),
                "location": (loc or "").strip(),
                "bio_short": short(bio, 140),
                "email": email or "",
                "profile_url": user.get("html_url") or f"https://github.com/{login}",
                "signals": ";".join(sigs),
                "is_codeowner": "yes" if is_codeowner else "no",
                "role": role,
            })
            f.flush()

            # update unique people + progress % / early stop
            if login not in unique_people_global:
                unique_people_global.add(login)
                _update_postfix()
                
                # Update leads with email progress
                if email and email.strip() and 'noreply' not in email.lower():
                    leads_with_email_count += 1
                    _tick_leads_bar(leads_with_email_count)
                
                if target_leads and len(unique_people_global) >= target_leads:
                    print(f"\n✅ Target reached: {target_leads} unique people.")
                    leads_bar.close()
                    f.close()
                    return

        human_sleep(0.4)

    leads_bar.close()
    f.close()
    print(f"\n✅ Done. Wrote {out_csv}")

def main():
    p = argparse.ArgumentParser(description="Find CI maintainers/director-like contacts from GitHub only.")
    p.add_argument("--since", default=None, help="Only include repos pushed on/after this date (YYYY-MM-DD). Default: 90 days ago.")
    p.add_argument("--max-repos", type=int, default=250, help="Max repos to consider from code search.")
    p.add_argument("--out", default="data/ci_people.csv", help="Output CSV path.")
    p.add_argument("--include-personal-repos", action="store_true", help="Include user-owned repos (defaults to orgs only).")
    p.add_argument("--min-stars", type=int, default=30, help="Minimum repo stars.")
    p.add_argument("--no-email", dest="find_emails", action="store_false", help="Do not try to pull commit/profile emails.")
    p.add_argument("--target-leads", type=int, default=0, help="Stop once this many unique people have been found (shows % progress).")
    p.add_argument("--discover-only", action="store_true", help="Show AI/Python repo preview and exit")
    p.add_argument("--discover-top", type=int, default=150, help="How many repos to preview before scraping people")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    since = parse_date(args.since) if args.since else utc_now() - timedelta(days=90)
    run(
        since=since,
        max_repos=args.max_repos,
        out_csv=args.out,
        include_personal_repos=args.include_personal_repos,
        min_stars=args.min_stars,
        find_emails=args.find_emails,
        verbose=args.verbose,
        target_leads=args.target_leads,
        discover_only=args.discover_only,
        discover_top=args.discover_top,
    )

if __name__ == "__main__":
    main()
