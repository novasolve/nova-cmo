#!/usr/bin/env python3
import json, statistics, datetime as dt
from pathlib import Path

LEDGER = Path("artifacts/rescue_ledger.jsonl")
OUTDIR = Path("docs")
OUTDIR.mkdir(parents=True, exist_ok=True)

rows = []
if LEDGER.exists():
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
            ts = r.get("ts")
            if isinstance(ts, str) and len(ts) >= 10:
                rows.append(r)
        except Exception:
            pass

by_key = {}
iso = lambda ts: ts or ""
for r in rows:
    key = (r.get("repo"), r.get("pr"))
    if not key[0] or not key[1]:
        continue
    prev = by_key.get(key)
    if not prev or iso(r.get("ts")) > iso(prev.get("ts")):
        by_key[key] = r

items = []
for r in sorted(by_key.values(), key=lambda x: iso(x.get("ts")), reverse=True):
    repo_full = r.get("repo", "owner/repo")
    owner, repo = (repo_full.split("/", 1) + [""])[:2]
    status = r.get("status")
    status_norm = "GREEN" if status == "accepted" else ("FAILED" if status == "reverted" else "PENDING")
    items.append({
        "owner": owner,
        "repo": repo,
        "pr_number": r.get("pr"),
        "fix_pr_number": r.get("fix_pr"),
        "status": status_norm,
        "merged": bool(r.get("merged")),
        "loc": int(r.get("loc", 0) or 0),
        "files": int(r.get("files", 0) or 0),
        "ttg_hours": round(float(r.get("ttg_min") or 0) / 60, 2),
        "fixed_at": r.get("ts"),
    })

accepted = [r for r in rows if r.get("status") == "accepted"]
attempted = [r for r in rows if r.get("status") in ("opened_pr", "accepted")]

def median(nums):
    return round(statistics.median(nums), 2) if nums else 0

today = dt.date.today().isoformat()
rescued_today = sum(1 for r in accepted if (r.get("ts", "")[:10] == today))
rescues_7d = sum(
    1
    for r in rows
    if r.get("status") in ("opened_pr", "accepted")
    and (dt.date.today() - dt.date.fromisoformat((r.get("ts", "")[:10] or today))).days <= 7
)
acceptance_pct = round(100 * len(accepted) / max(1, len(attempted)), 2)
median_loc = median([int(r.get("loc", 0) or 0) for r in accepted])
median_ttg = median([(float(r.get("ttg_min") or 0) / 60) for r in accepted])
merged_count = sum(1 for r in accepted if r.get("merged"))

(OUTDIR / "prs.json").write_text(json.dumps(items, indent=2), encoding="utf-8")
(OUTDIR / "stats.json").write_text(
    json.dumps(
        {
            "goal": 100,
            "rescued_total": len(accepted),
            "merged_count": merged_count,
            "success_rate": acceptance_pct,
            "rescued_today": rescued_today,
            "rescues_7d": rescues_7d,
            "median_loc": median_loc,
            "median_ttg": median_ttg,
            "mrr": 0,
        },
        indent=2,
    ),
    encoding="utf-8",
)

print("Wrote docs/prs.json and docs/stats.json")
