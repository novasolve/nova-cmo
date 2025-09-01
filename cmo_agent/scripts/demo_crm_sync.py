#!/usr/bin/env python3
"""
Demo script: run Attio and Linear sync tools with dummy data

- Uses env vars: ATTIO_ACCESS_TOKEN/ATTIO_API_KEY/ATTIO_API_TOKEN, ATTIO_WORKSPACE_ID, LINEAR_API_KEY
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv

# Ensure project root on sys.path for absolute imports
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from cmo_agent.tools.crm import SyncAttio, SyncLinear  # noqa: E402


def get_attio_credentials() -> Dict[str, Any]:
    """Return Attio credentials from any supported env var alias."""
    token = (
        os.getenv("ATTIO_ACCESS_TOKEN")
        or os.getenv("ATTIO_API_KEY")
        or os.getenv("ATTIO_API_TOKEN")
    )
    workspace_id = os.getenv("ATTIO_WORKSPACE_ID")
    return {"token": token, "workspace_id": workspace_id}


async def main() -> int:
    load_dotenv()

    # Prepare dummy payloads
    people = [
        {
            "email": "demo.person@example.com",
            "first_name": "Demo",
            "last_name": "Person",
            "name": "Demo Person",
            "login": "demouser",
            "company": "Acme Corp",
            "location": "San Francisco, CA",
            "primary_repo": "owner/repo",
            "activity_90d": 42,
        }
    ]
    list_id = os.getenv("ATTIO_DEMO_LIST_ID", "demo_list")

    # Run Attio sync if creds present
    attio_creds = get_attio_credentials()
    if attio_creds["token"] and attio_creds["workspace_id"]:
        attio = SyncAttio(attio_creds["token"], attio_creds["workspace_id"])
        a_res = await attio.execute(people=people, list_id=list_id)
        print("\n[Attio] Result:")
        print({
            "success": a_res.success,
            "data": a_res.data,
            "error": a_res.error,
        })
    else:
        print("\n[Attio] Skipped (missing ATTIO token and/or ATTIO_WORKSPACE_ID)")

    # Run Linear sync if key present
    linear_key = os.getenv("LINEAR_API_KEY")
    if linear_key:
        linear = SyncLinear(linear_key)
        events = [
            {
                "type": "error",
                "error_type": "DemoError",
                "error_message": "This is a demo error event",
                "timestamp": "now",
            }
        ]
        l_res = await linear.execute(parent_title="Demo CRM Sync", events=events)
        print("\n[Linear] Result:")
        print({
            "success": l_res.success,
            "data": l_res.data,
            "error": l_res.error,
        })
    else:
        print("\n[Linear] Skipped (missing LINEAR_API_KEY)")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
