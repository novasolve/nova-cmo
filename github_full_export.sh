#!/usr/bin/env bash
# GitHub "Everything" Exporter + Attio-ready CSVs
# ------------------------------------------------
# Requirements: bash, curl, jq, python3
# Token: export GITHUB_TOKEN=ghp_xxx
# Usage:
#   ./github_full_export.sh --account <org-or-user> [--out ./data] [--include-commits] [--max-commits-per-repo N] [--attio]
# Examples:
#   ./github_full_export.sh --account vercel --attio
#   ./github_full_export.sh --account octocat --include-commits --max-commits-per-repo 500

set -euo pipefail
IFS=$'\n\t'

# ---------- Config / Defaults ----------
: "${GITHUB_TOKEN:=}"
ACCOUNT=""
OUT_BASE="./data"
INCLUDE_COMMITS="false"
MAX_COMMITS_PER_REPO=""
DO_ATTIO="false"

API="https://api.github.com"
API_VERSION="2022-11-28"
UA="github-full-exporter/1.0"

# ---------- Helpers ----------
usage() {
  cat <<EOF
GitHub "Everything" Exporter + Attio-ready CSVs

Required:
  --account NAME            GitHub org or user

Optional:
  --out DIR                 Base output dir (default: ./data)
  --include-commits         Also export commits for every repo (can be huge)
  --max-commits-per-repo N  Limit number of commits per repo when exporting
  --attio                   Emit Attio-ready CSVs (People.csv, Companies.csv)
  -h, --help                Show this help

Environment:
  GITHUB_TOKEN              Required (classic PAT or fine-grained) with read access

Examples:
  ./github_full_export.sh --account vercel --attio
  ./github_full_export.sh --account octocat --include-commits --max-commits-per-repo 1000
EOF
}

need() { command -v "$1" >/dev/null 2>&1 || { echo "❌ Missing required tool: $1"; exit 1; }; }

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --account) ACCOUNT="${2:-}"; shift 2 ;;
      --out) OUT_BASE="${2:-}"; shift 2 ;;
      --include-commits) INCLUDE_COMMITS="true"; shift 1 ;;
      --max-commits-per-repo) MAX_COMMITS_PER_REPO="${2:-}"; shift 2 ;;
      --attio) DO_ATTIO="true"; shift 1 ;;
      -h|--help) usage; exit 0 ;;
      *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
  done
  if [[ -z "$ACCOUNT" ]]; then echo "❌ --account is required"; usage; exit 1; fi
  if [[ -z "$GITHUB_TOKEN" ]]; then
    echo "❌ GITHUB_TOKEN not set"
    echo "   export GITHUB_TOKEN=ghp_yourtoken   (classic) or a fine-grained token with read access"
    exit 1
  fi
}

TMP_DIR="$(mktemp -d)"
TMP_LAST_HEADERS="$TMP_DIR/last_headers.txt"

cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

header_val_ci() {
  local key_lc="$1"
  awk -F': ' -v k="$key_lc" 'tolower($1)==k {gsub("\r",""); print $2}' "$TMP_LAST_HEADERS" | tail -n1
}

parse_next_link() {
  awk 'BEGIN{IGNORECASE=1} /^Link:/ {print}' "$TMP_LAST_HEADERS" \
  | tr -d '\r' \
  | awk -F',' '{for(i=1;i<=NF;i++) print $i}' \
  | awk -F';' '/rel="next"/ {gsub(/[<>]/,"",$1); gsub(/^[[:space:]]+|[[:space:]]+$/,"",$1); print $1; exit}'
}

api_call() {
  local url="$1"
  local accept="${2:-application/vnd.github+json}"
  local hdr="$TMP_LAST_HEADERS"
  curl -sS -D "$hdr" \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H "Accept: $accept" \
    -H "X-GitHub-Api-Version: $API_VERSION" \
    -H "User-Agent: $UA" \
    "$url"
  local remain reset now sleepfor
  remain=$(header_val_ci "x-ratelimit-remaining" || echo "")
  reset=$(header_val_ci "x-ratelimit-reset" || echo "")
  if [[ "$remain" =~ ^0$ ]] && [[ -n "$reset" ]]; then
    now=$(date +%s)
    sleepfor=$(( reset - now + 3 ))
    if (( sleepfor > 0 )); then
      echo "⏳ Rate limit reached. Sleeping ${sleepfor}s until $(date -r "$reset" 2>/dev/null || date -u -d "@$reset")."
      sleep "$sleepfor"
    fi
  fi
}

paginate() {
  local url="$1" dest="$2" accept="${3:-application/vnd.github+json}"
  : > "$dest"
  while : ; do
    local body
    body="$(api_call "$url" "$accept")"
    if echo "$body" | jq -e . >/dev/null 2>&1; then
      if echo "$body" | jq -e 'type=="array"' >/dev/null 2>&1; then
        echo "$body" | jq -c '.[]' >> "$dest"
      else
        echo "$body" | jq -c '.' >> "$dest"
      fi
    else
      echo "⚠️  Non-JSON response for $url (skipping)"; break
    fi
    local next
    next="$(parse_next_link || true)"
    [[ -n "$next" ]] || break
    url="$next"
  done
}

append_repo_scoped() {
  local repo="$1" dest="$2"
  jq -c --arg r "$repo" 'if type=="array" then .[] | . + {repo_full_name:$r} else . + {repo_full_name:$r} end' >> "$dest"
}

# ---------- Start ----------
parse_args "$@"
need curl
need jq
need python3

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${OUT_BASE%/}/export_${ACCOUNT}_${STAMP}"
RAW_DIR="$OUT_DIR/raw"
CSV_DIR="$OUT_DIR/csv"
ATTIO_DIR="$OUT_DIR/attio"

mkdir -p "$RAW_DIR" "$CSV_DIR" "$ATTIO_DIR"

echo "🚀 GitHub Full Export"
echo "====================="
echo "🧑‍💻 Account:  $ACCOUNT"
echo "📂 Output:    $OUT_DIR"
echo "🧾 Commits:   $INCLUDE_COMMITS${MAX_COMMITS_PER_REPO:+ (max $MAX_COMMITS_PER_REPO per repo)}"
echo "🏷️  Attio:     $DO_ATTIO"
echo ""

# ---------- Detect USER vs ORG, fetch profile ----------
PROFILE_JSON="$RAW_DIR/account_profile.json"
echo "🔎 Fetching account profile..."
api_call "$API/users/$ACCOUNT" > "$PROFILE_JSON"
TYPE=$(jq -r '.type' "$PROFILE_JSON")
if [[ "$TYPE" != "User" && "$TYPE" != "Organization" ]]; then
  echo "❌ Could not determine type for $ACCOUNT (got: $TYPE)"; exit 1
fi
echo "   → Type: $TYPE"

# ---------- Fetch user/org specific lists ----------
if [[ "$TYPE" == "Organization" ]]; then
  echo "🏢 Org members & teams..."
  paginate "$API/orgs/$ACCOUNT/members?per_page=100" "$RAW_DIR/org_members.jsonl" || true
  paginate "$API/orgs/$ACCOUNT/teams?per_page=100" "$RAW_DIR/org_teams.jsonl" || true
  paginate "$API/orgs/$ACCOUNT/outside_collaborators?per_page=100" "$RAW_DIR/org_outside_collaborators.jsonl" || true
  echo "📦 Org repos..."
  paginate "$API/orgs/$ACCOUNT/repos?type=all&per_page=100" "$RAW_DIR/repositories.jsonl"
else
  echo "👤 User relations..."
  paginate "$API/users/$ACCOUNT/followers?per_page=100" "$RAW_DIR/user_followers.jsonl" || true
  paginate "$API/users/$ACCOUNT/following?per_page=100" "$RAW_DIR/user_following.jsonl" || true
  paginate "$API/users/$ACCOUNT/gists?per_page=100" "$RAW_DIR/user_gists.jsonl" || true
  paginate "$API/users/$ACCOUNT/starred?per_page=100" "$RAW_DIR/user_starred_repos.jsonl" || true
  echo "📦 User repos..."
  paginate "$API/users/$ACCOUNT/repos?type=all&per_page=100" "$RAW_DIR/repositories.jsonl"
fi

# ---------- Per-repo data ----------
echo "🧩 Per‑repo data (topics, languages, branches, tags, releases, issues, pulls, contributors, stargazers)..."
: > "$RAW_DIR/repo_topics.jsonl"
: > "$RAW_DIR/repo_languages.jsonl"
: > "$RAW_DIR/repo_branches.jsonl"
: > "$RAW_DIR/repo_tags.jsonl"
: > "$RAW_DIR/repo_releases.jsonl"
: > "$RAW_DIR/repo_issues.jsonl"
: > "$RAW_DIR/repo_pulls.jsonl"
: > "$RAW_DIR/repo_contributors.jsonl"
: > "$RAW_DIR/repo_stargazers.jsonl"
: > "$RAW_DIR/repo_commits.jsonl"

REPO_NAMES=($(jq -r '.full_name' "$RAW_DIR/repositories.jsonl"))
TOTAL_REPOS=${#REPO_NAMES[@]}
idx=0
for full in "${REPO_NAMES[@]}"; do
  idx=$((idx+1))
  echo "   [$idx/$TOTAL_REPOS] $full"

  body="$(api_call "$API/repos/$full/topics")"
  echo "$body" | jq -c --arg r "$full" '{repo_full_name:$r, names:(.names // [])}' >> "$RAW_DIR/repo_topics.jsonl"

  body="$(api_call "$API/repos/$full/languages")"
  echo "$body" | jq -c --arg r "$full" '{repo_full_name:$r, languages:.}' >> "$RAW_DIR/repo_languages.jsonl"

  paginate "$API/repos/$full/branches?per_page=100" "$TMP_DIR/_branches.jsonl"
  cat "$TMP_DIR/_branches.jsonl" | jq -c --arg r "$full" '. + {repo_full_name:$r}' >> "$RAW_DIR/repo_branches.jsonl"

  paginate "$API/repos/$full/tags?per_page=100" "$TMP_DIR/_tags.jsonl"
  cat "$TMP_DIR/_tags.jsonl" | jq -c --arg r "$full" '. + {repo_full_name:$r}' >> "$RAW_DIR/repo_tags.jsonl"

  paginate "$API/repos/$full/releases?per_page=100" "$TMP_DIR/_releases.jsonl"
  cat "$TMP_DIR/_releases.jsonl" | jq -c --arg r "$full" '. + {repo_full_name:$r}' >> "$RAW_DIR/repo_releases.jsonl"

  paginate "$API/repos/$full/issues?state=all&per_page=100" "$TMP_DIR/_issues.jsonl"
  cat "$TMP_DIR/_issues.jsonl" | jq -c --arg r "$full" '. + {repo_full_name:$r}' >> "$RAW_DIR/repo_issues.jsonl"

  paginate "$API/repos/$full/pulls?state=all&per_page=100" "$TMP_DIR/_pulls.jsonl"
  cat "$TMP_DIR/_pulls.jsonl" | jq -c --arg r "$full" '. + {repo_full_name:$r}' >> "$RAW_DIR/repo_pulls.jsonl"

  paginate "$API/repos/$full/contributors?per_page=100&anon=1" "$TMP_DIR/_contributors.jsonl"
  cat "$TMP_DIR/_contributors.jsonl" | jq -c --arg r "$full" '. + {repo_full_name:$r}' >> "$RAW_DIR/repo_contributors.jsonl"

  paginate "$API/repos/$full/stargazers?per_page=100" "$TMP_DIR/_stargazers.jsonl" "application/vnd.github.star+json"
  cat "$TMP_DIR/_stargazers.jsonl" | jq -c --arg r "$full" '. + {repo_full_name:$r}' >> "$RAW_DIR/repo_stargazers.jsonl"

  if [[ "$INCLUDE_COMMITS" == "true" ]]; then
    page_url="$API/repos/$full/commits?per_page=100"
    fetched=0
    while : ; do
      body="$(api_call "$page_url")"
      if echo "$body" | jq -e 'type=="array"' >/dev/null 2>&1; then
        count=$(echo "$body" | jq 'length')
        (( count == 0 )) && break
        echo "$body" | jq -c --arg r "$full" '.[] | . + {repo_full_name:$r}' >> "$RAW_DIR/repo_commits.jsonl"
        fetched=$((fetched + count))
        if [[ -n "$MAX_COMMITS_PER_REPO" ]] && (( fetched >= MAX_COMMITS_PER_REPO )); then
          break
        fi
      fi
      next="$(parse_next_link || true)"
      [[ -n "$next" ]] || break
      page_url="$next"
    done
  fi
done

echo "👥 Resolving unique users and fetching full profiles..."
: > "$RAW_DIR/users_full_profiles.jsonl"

jq_sources=()
[[ -f "$RAW_DIR/org_members.jsonl" ]] && jq_sources+=("$RAW_DIR/org_members.jsonl")
[[ -f "$RAW_DIR/org_outside_collaborators.jsonl" ]] && jq_sources+=("$RAW_DIR/org_outside_collaborators.jsonl")
[[ -f "$RAW_DIR/user_followers.jsonl" ]] && jq_sources+=("$RAW_DIR/user_followers.jsonl")
[[ -f "$RAW_DIR/user_following.jsonl" ]] && jq_sources+=("$RAW_DIR/user_following.jsonl")
[[ -f "$RAW_DIR/repo_contributors.jsonl" ]] && jq_sources+=("$RAW_DIR/repo_contributors.jsonl")
[[ -f "$RAW_DIR/repo_stargazers.jsonl" ]] && jq_sources+=("$RAW_DIR/repo_stargazers.jsonl")
[[ -f "$RAW_DIR/repo_issues.jsonl" ]] && jq_sources+=("$RAW_DIR/repo_issues.jsonl")
[[ -f "$RAW_DIR/repo_pulls.jsonl" ]] && jq_sources+=("$RAW_DIR/repo_pulls.jsonl")
[[ -f "$RAW_DIR/user_gists.jsonl" ]] && jq_sources+=("$RAW_DIR/user_gists.jsonl")
[[ -f "$RAW_DIR/repositories.jsonl" ]] && jq_sources+=("$RAW_DIR/repositories.jsonl")

LOGINS=$(jq -r '
  def try_login: if has("login") and .login != null then .login
                 elif has("user") and .user!=null and .user.login!=null then .user.login
                 elif has("owner") and .owner!=null and .owner.login!=null then .owner.login
                 elif has("author") and .author!=null and .author.login!=null then .author.login
                 elif has("user") and .user==null then empty
                 else empty end;
  [inputs | try_login] | unique[]' "${jq_sources[@]}" 2>/dev/null || true)

if [[ "$TYPE" == "User" ]]; then
  LOGINS="$ACCOUNT"$'\n'"$LOGINS"
fi

LOGINS=$(echo "$LOGINS" | awk 'NF' | sort -u)

COUNT_LOGINS=$(echo "$LOGINS" | wc -l | tr -d ' ')
if [[ -z "$COUNT_LOGINS" || "$COUNT_LOGINS" == "0" ]]; then
  echo "   (no additional user profiles found)"
else
  idx=0
  while IFS= read -r login; do
    [[ -n "$login" ]] || continue
    idx=$((idx+1))
    printf "   [%d/%d] %s\r" "$idx" "$COUNT_LOGINS" "$login"
    api_call "$API/users/$login" | jq -c '.' >> "$RAW_DIR/users_full_profiles.jsonl" || true
  done <<< "$LOGINS"
  echo ""
fi

echo "📄 Building CSV summaries (and Attio files if requested)..."

python3 - "$RAW_DIR" "$CSV_DIR" "$ATTIO_DIR" "$TYPE" "$ACCOUNT" "$DO_ATTIO" <<'PYCODE'
import sys, os, json, csv, pathlib, urllib.parse

raw_dir   = sys.argv[1]
csv_dir   = sys.argv[2]
attio_dir = sys.argv[3]
acct_type = sys.argv[4]  # "User" or "Organization"
account   = sys.argv[5]
do_attio  = sys.argv[6].lower() == "true"

def load_jsonl(path):
    arr=[]
    if not os.path.exists(path): return arr
    with open(path,"r",encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try:
                arr.append(json.loads(line))
            except Exception:
                pass
    return arr

def load_json(path):
    if not os.path.exists(path): return None
    with open(path,"r",encoding="utf-8") as f:
        return json.load(f)

def write_csv(path, rows, headers):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow({k: (r.get(k,"") if r.get(k) is not None else "") for k in headers})

def dom(url):
    if not url: return ""
    try:
        u=urllib.parse.urlparse(url if url.startswith("http") else "http://"+url)
        return u.hostname or ""
    except Exception:
        return ""

profile = load_json(os.path.join(raw_dir, "account_profile.json"))
repos   = load_jsonl(os.path.join(raw_dir, "repositories.jsonl"))
topics  = load_jsonl(os.path.join(raw_dir, "repo_topics.jsonl"))
langs   = load_jsonl(os.path.join(raw_dir, "repo_languages.jsonl"))
branches= load_jsonl(os.path.join(raw_dir, "repo_branches.jsonl"))
tags    = load_jsonl(os.path.join(raw_dir, "repo_tags.jsonl"))
rels    = load_jsonl(os.path.join(raw_dir, "repo_releases.jsonl"))
issues  = load_jsonl(os.path.join(raw_dir, "repo_issues.jsonl"))
pulls   = load_jsonl(os.path.join(raw_dir, "repo_pulls.jsonl"))
contrs  = load_jsonl(os.path.join(raw_dir, "repo_contributors.jsonl"))
stars   = load_jsonl(os.path.join(raw_dir, "repo_stargazers.jsonl"))
commits = load_jsonl(os.path.join(raw_dir, "repo_commits.jsonl"))
users   = load_jsonl(os.path.join(raw_dir, "users_full_profiles.jsonl"))

org_members = load_jsonl(os.path.join(raw_dir, "org_members.jsonl"))
org_teams   = load_jsonl(os.path.join(raw_dir, "org_teams.jsonl"))

followers = load_jsonl(os.path.join(raw_dir, "user_followers.jsonl"))
following = load_jsonl(os.path.join(raw_dir, "user_following.jsonl"))
gists     = load_jsonl(os.path.join(raw_dir, "user_gists.jsonl"))
starred   = load_jsonl(os.path.join(raw_dir, "user_starred_repos.jsonl"))

topics_by_repo = {t["repo_full_name"]: t.get("names",[]) for t in topics}
langs_by_repo  = {t["repo_full_name"]: t.get("languages",{}) for t in langs}

repo_rows=[]
for r in repos:
    lic = (r.get("license") or {}).get("key") if isinstance(r.get("license"), dict) else ""
    repo_rows.append({
        "repo_full_name": r.get("full_name",""),
        "name": r.get("name",""),
        "private": r.get("private",""),
        "visibility": r.get("visibility",""),
        "fork": r.get("fork",""),
        "archived": r.get("archived",""),
        "disabled": r.get("disabled",""),
        "description": r.get("description",""),
        "homepage": r.get("homepage",""),
        "html_url": r.get("html_url",""),
        "default_branch": r.get("default_branch",""),
        "license_key": lic or "",
        "language": r.get("language",""),
        "topics": ";".join(topics_by_repo.get(r.get("full_name",""), [])),
        "size": r.get("size",""),
        "open_issues_count": r.get("open_issues_count",""),
        "forks_count": r.get("forks_count",""),
        "stargazers_count": r.get("stargazers_count",""),
        "watchers_count": r.get("watchers_count",""),
        "created_at": r.get("created_at",""),
        "updated_at": r.get("updated_at",""),
        "pushed_at": r.get("pushed_at",""),
    })
write_csv(os.path.join(csv_dir,"repositories.csv"), repo_rows, list(repo_rows[0].keys()) if repo_rows else
          ["repo_full_name","name","private","visibility","fork","archived","disabled","description","homepage","html_url","default_branch","license_key","language","topics","size","open_issues_count","forks_count","stargazers_count","watchers_count","created_at","updated_at","pushed_at"])

lang_rows=[]
for rf, mp in langs_by_repo.items():
    for k,v in (mp or {}).items():
        lang_rows.append({"repo_full_name":rf,"language":k,"bytes":v})
write_csv(os.path.join(csv_dir,"repo_languages.csv"), lang_rows, ["repo_full_name","language","bytes"])

topic_rows=[]
for rf, arr in topics_by_repo.items():
    for t in arr:
        topic_rows.append({"repo_full_name":rf,"topic":t})
write_csv(os.path.join(csv_dir,"repo_topics.csv"), topic_rows, ["repo_full_name","topic"])

br_rows=[ {"repo_full_name":b.get("repo_full_name",""), "name":b.get("name",""), "protected":b.get("protected",""), "sha":(b.get("commit") or {}).get("sha","")} for b in branches ]
write_csv(os.path.join(csv_dir,"repo_branches.csv"), br_rows, ["repo_full_name","name","protected","sha"])

tag_rows=[ {"repo_full_name":t.get("repo_full_name",""), "name":t.get("name",""), "sha":(t.get("commit") or {}).get("sha","")} for t in tags ]
write_csv(os.path.join(csv_dir,"repo_tags.csv"), tag_rows, ["repo_full_name","name","sha"])

rel_rows=[]
for r in rels:
    rel_rows.append({
        "repo_full_name": r.get("repo_full_name",""),
        "id": r.get("id",""),
        "tag_name": r.get("tag_name",""),
        "name": r.get("name",""),
        "draft": r.get("draft",""),
        "prerelease": r.get("prerelease",""),
        "created_at": r.get("created_at",""),
        "published_at": r.get("published_at",""),
        "author_login": (r.get("author") or {}).get("login",""),
        "html_url": r.get("html_url",""),
    })
write_csv(os.path.join(csv_dir,"releases.csv"), rel_rows, ["repo_full_name","id","tag_name","name","draft","prerelease","created_at","published_at","author_login","html_url"])

iss_rows=[]
for i in issues:
    iss_rows.append({
        "repo_full_name": i.get("repo_full_name",""),
        "id": i.get("id",""),
        "number": i.get("number",""),
        "state": i.get("state",""),
        "title": i.get("title",""),
        "user_login": (i.get("user") or {}).get("login",""),
        "is_pull_request": "pull_request" in i,
        "comments": i.get("comments",""),
        "created_at": i.get("created_at",""),
        "updated_at": i.get("updated_at",""),
        "closed_at": i.get("closed_at",""),
        "html_url": i.get("html_url",""),
    })
write_csv(os.path.join(csv_dir,"issues.csv"), iss_rows, ["repo_full_name","id","number","state","title","user_login","is_pull_request","comments","created_at","updated_at","closed_at","html_url"])

pr_rows=[]
for p in pulls:
    pr_rows.append({
        "repo_full_name": p.get("repo_full_name",""),
        "id": p.get("id",""),
        "number": p.get("number",""),
        "state": p.get("state",""),
        "title": p.get("title",""),
        "user_login": (p.get("user") or {}).get("login",""),
        "draft": p.get("draft",""),
        "merged_at": p.get("merged_at",""),
        "created_at": p.get("created_at",""),
        "updated_at": p.get("updated_at",""),
        "closed_at": p.get("closed_at",""),
        "html_url": p.get("html_url",""),
    })
write_csv(os.path.join(csv_dir,"pulls.csv"), pr_rows, ["repo_full_name","id","number","state","title","user_login","draft","merged_at","created_at","updated_at","closed_at","html_url"])

con_rows=[]
for c in contrs:
    login = c.get("login")
    con_rows.append({
        "repo_full_name": c.get("repo_full_name",""),
        "login": login or "",
        "type": c.get("type",""),
        "name": c.get("name",""),
        "contributions": c.get("contributions",""),
        "html_url": c.get("html_url",""),
    })
write_csv(os.path.join(csv_dir,"contributors.csv"), con_rows, ["repo_full_name","login","type","name","contributions","html_url"])

star_rows=[]
for s in stars:
    u = s.get("user") or {}
    star_rows.append({
        "repo_full_name": s.get("repo_full_name",""),
        "starred_at": s.get("starred_at",""),
        "login": u.get("login",""),
        "html_url": u.get("html_url",""),
        "type": u.get("type",""),
    })
write_csv(os.path.join(csv_dir,"stargazers.csv"), star_rows, ["repo_full_name","starred_at","login","html_url","type"])

if commits:
    com_rows=[]
    for c in commits:
        commit = c.get("commit") or {}
        author = (c.get("author") or {})
        committer = (c.get("committer") or {})
        com_rows.append({
            "repo_full_name": c.get("repo_full_name",""),
            "sha": c.get("sha",""),
            "message": (commit.get("message","") or "").split("\n")[0],
            "author_login": author.get("login",""),
            "author_name": (commit.get("author") or {}).get("name",""),
            "author_email": (commit.get("author") or {}).get("email",""),
            "author_date": (commit.get("author") or {}).get("date",""),
            "committer_login": committer.get("login",""),
            "committer_name": (commit.get("committer") or {}).get("name",""),
            "committer_email": (commit.get("committer") or {}).get("email",""),
            "committer_date": (commit.get("committer") or {}).get("date",""),
            "html_url": c.get("html_url",""),
        })
    write_csv(os.path.join(csv_dir,"commits.csv"), com_rows, ["repo_full_name","sha","message","author_login","author_name","author_email","author_date","committer_login","committer_name","committer_email","committer_date","html_url"])

user_rows=[]
for u in users:
    user_rows.append({
        "login": u.get("login",""),
        "name": u.get("name",""),
        "company": u.get("company",""),
        "email": u.get("email",""),
        "blog": u.get("blog",""),
        "twitter_username": u.get("twitter_username",""),
        "location": u.get("location",""),
        "bio": u.get("bio",""),
        "hireable": u.get("hireable",""),
        "html_url": u.get("html_url",""),
        "followers": u.get("followers",""),
        "following": u.get("following",""),
        "public_repos": u.get("public_repos",""),
        "public_gists": u.get("public_gists",""),
        "created_at": u.get("created_at",""),
        "updated_at": u.get("updated_at",""),
        "type": u.get("type",""),
    })
write_csv(os.path.join(csv_dir,"users.csv"), user_rows, ["login","name","company","email","blog","twitter_username","location","bio","hireable","html_url","followers","following","public_repos","public_gists","created_at","updated_at","type"])

if acct_type == "Organization":
    om_rows=[]
    for m in load_jsonl(os.path.join(raw_dir, "org_members.jsonl")):
        om_rows.append({
            "login": m.get("login",""),
            "html_url": m.get("html_url",""),
            "type": m.get("type",""),
            "site_admin": m.get("site_admin",""),
        })
    write_csv(os.path.join(csv_dir,"org_members.csv"), om_rows, ["login","html_url","type","site_admin"])
    team_rows=[]
    for t in load_jsonl(os.path.join(raw_dir, "org_teams.jsonl")):
        team_rows.append({
            "id": t.get("id",""),
            "slug": t.get("slug",""),
            "name": t.get("name",""),
            "description": t.get("description",""),
            "privacy": t.get("privacy",""),
            "html_url": t.get("html_url",""),
        })
    write_csv(os.path.join(csv_dir,"org_teams.csv"), team_rows, ["id","slug","name","description","privacy","html_url"])

if do_attio:
    comp_rows=[]
    if profile:
        company_name = profile.get("name") or profile.get("login") or account
        comp_rows.append({
            "Company Name": company_name,
            "GitHub Org": profile.get("login",""),
            "GitHub URL": profile.get("html_url",""),
            "Description": profile.get("bio","") or profile.get("description",""),
            "Location": profile.get("location",""),
            "Website": profile.get("blog",""),
            "Domain": urllib.parse.urlparse(profile.get("blog","") if str(profile.get("blog",""))[:4]=='http' else 'http://'+str(profile.get("blog",""))).hostname if profile.get("blog") else "",
            "Email": profile.get("email",""),
            "Twitter": profile.get("twitter_username",""),
            "Created At": profile.get("created_at",""),
            "Updated At": profile.get("updated_at",""),
            "Public Repos": profile.get("public_repos",""),
            "Members Count": len(load_jsonl(os.path.join(raw_dir, "org_members.jsonl"))) if acct_type=="Organization" else "",
        })
    companies_seen=set([r["Company Name"] for r in comp_rows])
    for u in users:
        comp = (u.get("company") or "").strip()
        if comp and comp not in companies_seen:
            companies_seen.add(comp)
            comp_rows.append({
                "Company Name": comp,
                "GitHub Org": "",
                "GitHub URL": "",
                "Description": "",
                "Location": "",
                "Website": "",
                "Domain": "",
                "Email": "",
                "Twitter": "",
                "Created At": "",
                "Updated At": "",
                "Public Repos": "",
                "Members Count": "",
            })
    write_csv(os.path.join(attio_dir,"Companies.csv"), comp_rows,
              ["Company Name","GitHub Org","GitHub URL","Description","Location","Website","Domain","Email","Twitter","Created At","Updated At","Public Repos","Members Count"])

    people_rows=[]
    for u in users:
        people_rows.append({
            "Name": u.get("name") or u.get("login",""),
            "Email": u.get("email",""),
            "GitHub Username": u.get("login",""),
            "GitHub URL": u.get("html_url",""),
            "Company": u.get("company","") or (profile.get("login","") if acct_type=="Organization" else ""),
            "Location": u.get("location",""),
            "Bio": u.get("bio",""),
            "Twitter": u.get("twitter_username",""),
            "Website": u.get("blog",""),
            "Followers": u.get("followers",""),
            "Following": u.get("following",""),
            "Public Repos": u.get("public_repos",""),
            "Public Gists": u.get("public_gists",""),
            "Created At": u.get("created_at",""),
            "Updated At": u.get("updated_at",""),
        })
    write_csv(os.path.join(attio_dir,"People.csv"), people_rows,
              ["Name","Email","GitHub Username","GitHub URL","Company","Location","Bio","Twitter","Website","Followers","Following","Public Repos","Public Gists","Created At","Updated At"])

    readme = f"""# Attio Import Notes

**Files Generated**
- `People.csv` — import to *People* object
- `Companies.csv` — import to *Companies* object

**Recommended Field Mapping**
- People:
  - Name → Name
  - Email → Email
  - GitHub Username → Custom text field (e.g. "GitHub Username")
  - GitHub URL → Website or custom URL field
  - Company → Company (text)
  - Location → Location (text)
  - Twitter → Twitter (text)
  - Website → Website
  - Followers / Following / Public Repos / Public Gists → custom number fields
  - Created At / Updated At → custom date fields

- Companies:
  - Company Name → Name
  - GitHub Org → Custom text field (e.g. "GitHub Org")
  - GitHub URL → Website or custom URL
  - Description → Description
  - Location → Location
  - Website → Website
  - Domain → Domain
  - Members Count / Public Repos / Created At / Updated At → custom fields
"""
    with open(os.path.join(attio_dir,"README_ATTIO.md"),"w",encoding="utf-8") as f:
        f.write(readme)

print("✅ CSV build complete.")
PYCODE

echo ""
echo "📊 Summary:"
echo "- Raw JSONL: $RAW_DIR"
echo "- CSVs:      $CSV_DIR"
if [[ "$DO_ATTIO" == "true" ]]; then
  echo "- Attio:     $ATTIO_DIR (People.csv, Companies.csv)"
fi

mkdir -p "$OUT_BASE"
ln -sfn "$(basename "$OUT_DIR")" "$OUT_BASE/latest"
echo "- Latest symlink: $OUT_BASE/latest"

echo "🎉 Done."


