#!/usr/bin/env python3
# scripts/compile_greenweek_stats.py
import json, statistics as stats
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

LEDGER = Path("artifacts/rescue_ledger.jsonl")
OUTDIR = Path("docs/green-week")  # Pages root in this repo
GOAL = 100


def iso(ts: str):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def median_safe(values, default=0):
    vals = [v for v in values if v is not None]
    return round(stats.median(vals), 2) if vals else default


def load_ledger():
    if not LEDGER.exists():
        return []
    rows = []
    with LEDGER.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                # skip malformed lines
                pass
    return rows


def compile_state(rows):
    state = defaultdict(
        lambda: {
            "owner": None,
            "repo": None,
            "pr": None,
            "first_seen": None,
            "fixed_at": None,
            "merged_at": None,
            "fix_pr": None,
            "loc": None,
            "files": None,
            "klass": None,
            "status": "PENDING",
        }
    )

    for r in rows:
        key = (r.get("owner"), r.get("repo"), int(r.get("pr")))
        s = state[key]
        s["owner"], s["repo"], s["pr"] = key
        ts = iso(r.get("ts"))
        evt = r.get("event")
        if evt == "candidate":
            s["first_seen"] = s["first_seen"] or ts
        elif evt == "patch_opened":
            s["first_seen"] = s["first_seen"] or ts
            s["fix_pr"] = r.get("fix_pr")
            s["loc"] = r.get("loc")
            s["files"] = r.get("files")
            s["klass"] = r.get("class") or r.get("klass")
        elif evt == "ci_green":
            s["fixed_at"] = ts
            s["status"] = "GREEN"
        elif evt == "merged":
            s["merged_at"] = ts
            s["status"] = "GREEN"
        elif evt == "failed":
            if s["status"] != "GREEN":
                s["status"] = "FAILED"

    prs = []
    for (owner, repo, pr), s in state.items():
        ttg_hours = None
        if s["first_seen"] and s["fixed_at"]:
            ttg_hours = round((s["fixed_at"] - s["first_seen"]).total_seconds() / 3600, 2)
        prs.append(
            {
                "owner": owner,
                "repo": repo,
                "pr_number": pr,
                "fix_pr_number": s["fix_pr"],
                "status": s["status"],
                "merged": bool(s["merged_at"]),
                "loc": s["loc"],
                "files": s["files"],
                "ttg_hours": ttg_hours,
                "first_seen": s["first_seen"].isoformat() if s["first_seen"] else None,
                "fixed_at": s["fixed_at"].isoformat() if s["fixed_at"] else None,
                "merged_at": s["merged_at"].isoformat() if s["merged_at"] else None,
                "class": s["klass"],
            }
        )
    return prs


def compile_stats(prs):
    now = datetime.now(timezone.utc)
    greens = [p for p in prs if p["status"] == "GREEN"]
    fails = [p for p in prs if p["status"] == "FAILED"]
    merged = [p for p in prs if p["merged"]]
    with_fixed_at = [p for p in greens if p["fixed_at"]]

    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days = now - timedelta(days=7)
    rescued_today = sum(1 for p in with_fixed_at if iso(p["fixed_at"]) >= start_today)
    rescues_7d = sum(1 for p in with_fixed_at if iso(p["fixed_at"]) >= seven_days)

    median_loc = median_safe([p["loc"] for p in greens if isinstance(p["loc"], (int, float))])
    median_ttg = median_safe([p["ttg_hours"] for p in greens])
    attempted = len(greens) + len(fails)
    success_rate = round(100 * (len(greens) / attempted), 1) if attempted else 0.0
    acceptance_pct = round(100 * (len(merged) / len(greens)), 1) if greens else 0.0

    return {
        "goal": GOAL,
        "rescued_total": len(greens),
        "merged_count": len(merged),
        "success_rate": success_rate,
        "acceptance_pct": acceptance_pct,
        "median_loc": median_loc,
        "median_ttg": median_ttg,
        "rescued_today": rescued_today,
        "rescues_7d": rescues_7d,
        "mrr": 0,
    }


def main():
    rows = load_ledger()
    prs = compile_state(rows)
    prs_sorted = sorted(prs, key=lambda p: (p["fixed_at"] or p["first_seen"] or ""), reverse=True)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "prs.json").write_text(json.dumps(prs_sorted, ensure_ascii=False, indent=2), encoding="utf-8")
    stats_data = compile_stats(prs)
    (OUTDIR / "stats.json").write_text(json.dumps(stats_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTDIR/'stats.json'} and {OUTDIR/'prs.json'}")


if __name__ == "__main__":
    main()
