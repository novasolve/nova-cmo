#!/usr/bin/env python3
"""
Smoke test for CMO Agent toolbelt.

Runs minimal, safe checks for each tool to validate imports, initialization,
and a tiny execute path. External-API tools are tested only if their env vars
are present; otherwise they are skipped with a notice.
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# Ensure project root on sys.path for absolute imports
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from cmo_agent.tools.github import (
    SearchGitHubRepos,
    ExtractPeople,
    EnrichGitHubUsers,
    FindCommitEmailsBatch,
)
from cmo_agent.tools.hygiene import MXCheck, ICPScores
from cmo_agent.tools.personalization import RenderCopy, SendInstantly
from cmo_agent.tools.crm import SyncAttio, SyncLinear
from cmo_agent.tools.export import ExportCSV, Done
from cmo_agent.core.state import DEFAULT_CONFIG

# Load environment variables from .env if present
load_dotenv()


def print_header(title: str):
    print(f"\n=== {title} ===")


async def test_github_tools(config: Dict[str, Any]) -> Dict[str, Any]:
    results: Dict[str, Any] = {"skipped": True}
    token = (
        os.getenv("GITHUB_TOKEN")
        or config.get("GITHUB_TOKEN")
        or os.getenv("GITHUB_API_KEY")  # alias
        or config.get("GITHUB_API_KEY")
    )
    if not token:
        print("GitHub: SKIP (missing GITHUB_TOKEN)")
        return results

    results["skipped"] = False
    results["tests"] = {}

    try:
        # Search minimal repos
        search_tool = SearchGitHubRepos(token)
        search_res = await search_tool.execute(q="pytest", max_repos=1)
        ok = bool(search_res.success and search_res.data.get("repos"))
        results["tests"]["search_github_repos"] = ok
        print(f"search_github_repos: {'OK' if ok else 'FAIL'}")

        # Extract people (best-effort; may return empty depending on repo)
        repos = search_res.data.get("repos", [])
        extract_tool = ExtractPeople(token)
        extract_res = await extract_tool.execute(repos=repos, top_authors_per_repo=1)
        ok = bool(extract_res.success)
        results["tests"]["extract_people"] = ok
        print(f"extract_people: {'OK' if ok else 'FAIL'}")

        # Enrich user (batch) with a known login
        enrich_batch = EnrichGitHubUsers(token)
        eb_res = await enrich_batch.execute(logins=["octocat"], batch_size=1)
        ok = bool(eb_res.success and eb_res.data.get("profiles"))
        results["tests"]["enrich_github_users"] = ok
        print(f"enrich_github_users: {'OK' if ok else 'FAIL'}")

        # Find commit emails batch (best-effort, may be empty but should succeed)
        fceb = FindCommitEmailsBatch(token)
        pairs = [{"login": "octocat", "repo_full_name": "octocat/Hello-World"}]
        fe_res = await fceb.execute(user_repo_pairs=pairs, days=7, batch_size=1)
        ok = bool(fe_res.success and isinstance(fe_res.data.get("user_emails", {}), dict))
        results["tests"]["find_commit_emails_batch"] = ok
        print(f"find_commit_emails_batch: {'OK' if ok else 'FAIL'}")

    except Exception as e:
        print(f"GitHub smoke test error: {e}")
        results["error"] = str(e)

    return results


async def test_hygiene_tools() -> Dict[str, Any]:
    results: Dict[str, Any] = {"tests": {}}

    try:
        mx = MXCheck()
        mx_res = await mx.execute(["info@gmail.com", "nobody@invalid.invalid"])  # one valid, one invalid
        ok = bool(mx_res.success and isinstance(mx_res.data.get("valid_emails", []), list))
        results["tests"]["mx_check"] = ok
        print(f"mx_check: {'OK' if ok else 'FAIL'}")

        icp = ICPScores()
        dummy_profile = {
            "login": "octocat",
            "followers": 10,
            "contributions": [
                {"repo_stars": 50, "repo_language": "Python", "repo_topics": ["testing", "ci"]}
            ],
        }
        icp_res = await icp.execute(dummy_profile)
        ok = bool(icp_res.success and isinstance(icp_res.data.get("final_score"), float))
        results["tests"]["score_icp"] = ok
        print(f"score_icp: {'OK' if ok else 'FAIL'}")

    except Exception as e:
        print(f"Hygiene smoke test error: {e}")
        results["error"] = str(e)

    return results


async def test_personalization_tools(config: Dict[str, Any]) -> Dict[str, Any]:
    results: Dict[str, Any] = {"tests": {}, "skipped_send": False}

    try:
        render = RenderCopy()
        lead = {"login": "octocat", "name": "The Octocat", "email": "octo@example.com"}
        r_res = await render.execute(lead)
        ok = bool(r_res.success and r_res.data.get("subject") and r_res.data.get("body"))
        results["tests"]["render_copy"] = ok
        print(f"render_copy: {'OK' if ok else 'FAIL'}")

        api_key = (
            os.getenv("INSTANTLY_API_KEY")
            or config.get("INSTANTLY_API_KEY")
            or os.getenv("INSTANTLY_API_TOKEN")  # alias
            or config.get("INSTANTLY_API_TOKEN")
        )
        if not api_key:
            results["skipped_send"] = True
            print("send_instantly: SKIP (missing INSTANTLY_API_KEY/INSTANTLY_API_TOKEN)")
        else:
            send = SendInstantly(api_key)
            contact = {"email": "octo@example.com", "subject": "Hi", "body": "Test"}
            seq_name = (
                os.getenv("INSTANTLY_CAMPAIGN_NAME")
                or config.get("INSTANTLY_CAMPAIGN_NAME")
                or "My Campaign"
            )
            s_res = await send.execute([contact], seq_id=seq_name, per_inbox_cap=1)
            ok = bool(s_res.success and s_res.data.get("contacts_sent") == 1)
            results["tests"]["send_instantly"] = ok
            print(f"send_instantly: {'OK' if ok else 'FAIL'}")

    except Exception as e:
        print(f"Personalization smoke test error: {e}")
        results["error"] = str(e)

    return results


async def test_crm_tools(config: Dict[str, Any]) -> Dict[str, Any]:
    results: Dict[str, Any] = {"tests": {}, "skipped_attio": False, "skipped_linear": False}

    try:
        # Support multiple env var aliases for Attio API token
        attio_key = (
            os.getenv("ATTIO_ACCESS_TOKEN")
            or config.get("ATTIO_ACCESS_TOKEN")
            or os.getenv("ATTIO_API_KEY")
            or config.get("ATTIO_API_KEY")
            or os.getenv("ATTIO_API_TOKEN")  # alias used by setup_attio.sh
            or config.get("ATTIO_API_TOKEN")
        )
        attio_ws = os.getenv("ATTIO_WORKSPACE_ID") or config.get("ATTIO_WORKSPACE_ID")
        if not (attio_key and attio_ws):
            results["skipped_attio"] = True
            missing = []
            if not attio_key:
                missing.append("ATTIO_ACCESS_TOKEN/ATTIO_API_KEY/ATTIO_API_TOKEN")
            if not attio_ws:
                missing.append("ATTIO_WORKSPACE_ID")
            print(f"sync_attio: SKIP (missing {', '.join(missing)})")
        else:
            attio = SyncAttio(attio_key, attio_ws)
            person = {"email": "octo@example.com", "name": "The Octocat"}
            a_res = await attio.execute([person], list_id="smoke_list")
            ok = bool(a_res.success)
            results["tests"]["sync_attio"] = ok
            print(f"sync_attio: {'OK' if ok else 'FAIL'}")

        linear_key = os.getenv("LINEAR_API_KEY") or config.get("LINEAR_API_KEY")
        if not linear_key:
            results["skipped_linear"] = True
            print("sync_linear: SKIP (missing LINEAR_API_KEY)")
        else:
            linear = SyncLinear(linear_key)
            events = [{"type": "error", "error_type": "TestError", "error_message": "Test", "timestamp": "now"}]
            l_res = await linear.execute(parent_title="Smoke Test", events=events)
            ok = bool(l_res.success)
            results["tests"]["sync_linear"] = ok
            print(f"sync_linear: {'OK' if ok else 'FAIL'}")

    except Exception as e:
        print(f"CRM smoke test error: {e}")
        results["error"] = str(e)

    return results


async def test_export_and_done() -> Dict[str, Any]:
    results: Dict[str, Any] = {"tests": {}}

    try:
        # Export CSV
        export = ExportCSV("./exports")
        rows = [{"id": 1, "name": "octo"}, {"id": 2, "name": "cat"}]
        e_res = await export.execute(rows=rows, path="smoke_test.csv")
        ok = bool(e_res.success and Path(e_res.data.get("path", "")).exists())
        results["tests"]["export_csv"] = ok
        print(f"export_csv: {'OK' if ok else 'FAIL'}")

        # Done tool
        done = Done()
        d_res = await done.execute(summary="Smoke test complete")
        ok = bool(d_res.success and d_res.data.get("status") == "completed")
        results["tests"]["done"] = ok
        print(f"done: {'OK' if ok else 'FAIL'}")

        # Cleanup export file
        try:
            p = Path(e_res.data.get("path", ""))
            if p.exists():
                p.unlink()
        except Exception:
            pass

    except Exception as e:
        print(f"Export/Done smoke test error: {e}")
        results["error"] = str(e)

    return results


async def main() -> int:
    print_header("CMO Agent Toolbelt Smoke Test")
    config = DEFAULT_CONFIG.copy()

    github = await test_github_tools(config)
    hygiene = await test_hygiene_tools()
    personalization = await test_personalization_tools(config)
    crm = await test_crm_tools(config)
    export_done = await test_export_and_done()

    print_header("Summary")
    def count_ok(section: Dict[str, Any]) -> int:
        return sum(1 for v in section.get("tests", {}).values() if v)

    def count_total(section: Dict[str, Any]) -> int:
        return len(section.get("tests", {}))

    print(f"GitHub: {count_ok(github)}/{count_total(github)} (skipped={github.get('skipped', False)})")
    print(f"Hygiene: {count_ok(hygiene)}/{count_total(hygiene)}")
    print(f"Personalization: {count_ok(personalization)}/{count_total(personalization)} (send_skipped={personalization.get('skipped_send', False)})")
    print(f"CRM: {count_ok(crm)}/{count_total(crm)} (attio_skipped={crm.get('skipped_attio', False)}, linear_skipped={crm.get('skipped_linear', False)})")
    print(f"Export/Done: {count_ok(export_done)}/{count_total(export_done)}")

    # Consider hygiene + export/done + render_copy as must-pass
    must_pass = [
        hygiene.get("tests", {}).get("mx_check", False),
        hygiene.get("tests", {}).get("score_icp", False),
        personalization.get("tests", {}).get("render_copy", False),
        export_done.get("tests", {}).get("export_csv", False),
        export_done.get("tests", {}).get("done", False),
    ]

    exit_code = 0 if all(must_pass) else 1
    if exit_code == 0:
        print("\n✅ Smoke test passed")
    else:
        print("\n❌ Smoke test failed (see above for details)")
    return exit_code


if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code)


