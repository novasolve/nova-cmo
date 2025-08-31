#!/usr/bin/env python3
"""
Check which tools are available in the CMO Agent
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
sys.path.insert(0, parent_dir)

from agents.cmo_agent import CMOAgent
from core.state import DEFAULT_CONFIG


def check_available_tools():
    """Check which tools are available based on current configuration"""
    print("🔧 CMO Agent Tool Availability Check")
    print("=" * 50)

    # Load defaults and consider environment overrides for presence checks
    config = DEFAULT_CONFIG.copy()

    # Simulate tool initialization (same logic as CMOAgent._initialize_tools)
    available_tools = []

    # GitHub tools
    if os.getenv("GITHUB_TOKEN") or config.get("GITHUB_TOKEN"):
        available_tools.extend(["search_github_repos", "extract_people", "enrich_github_user", "find_commit_emails"])

    # Hygiene tools (always available)
    available_tools.extend(["mx_check", "score_icp"])

    # Personalization tools
    if os.getenv("INSTANTLY_API_KEY") or config.get("INSTANTLY_API_KEY"):
        available_tools.extend(["render_copy", "send_instantly"])

    # CRM tools (Attio)
    has_attio_token = os.getenv("ATTIO_ACCESS_TOKEN") or config.get("ATTIO_ACCESS_TOKEN") or os.getenv("ATTIO_API_KEY") or config.get("ATTIO_API_KEY")
    if has_attio_token and (os.getenv("ATTIO_WORKSPACE_ID") or config.get("ATTIO_WORKSPACE_ID")):
        available_tools.append("sync_attio")

    if os.getenv("LINEAR_API_KEY") or config.get("LINEAR_API_KEY"):
        available_tools.append("sync_linear")

    # Export tools (always available)
    available_tools.extend(["export_csv", "done"])

    print(f"📋 Available Tools: {len(available_tools)}")
    print()

    # Group tools by category
    tool_categories = {
        "GitHub Tools": [],
        "Hygiene Tools": [],
        "Personalization Tools": [],
        "CRM Tools": [],
        "Export Tools": []
    }

    for tool_name in available_tools:
        if tool_name.startswith("search_") or tool_name.startswith("extract_") or tool_name.startswith("enrich_") or tool_name.startswith("find_"):
            tool_categories["GitHub Tools"].append(tool_name)
        elif tool_name in ["mx_check", "score_icp"]:
            tool_categories["Hygiene Tools"].append(tool_name)
        elif tool_name in ["render_copy", "send_instantly"]:
            tool_categories["Personalization Tools"].append(tool_name)
        elif tool_name.startswith("sync_"):
            tool_categories["CRM Tools"].append(tool_name)
        else:
            tool_categories["Export Tools"].append(tool_name)

    # Display tools by category
    for category, tools in tool_categories.items():
        if tools:
            print(f"📂 {category}:")
            for tool in tools:
                status = "✅ Available"
                if tool in ["render_copy", "send_instantly"] and not (os.getenv("INSTANTLY_API_KEY") or config.get("INSTANTLY_API_KEY")):
                    status = "❌ Missing INSTANTLY_API_KEY"
                elif tool in ["sync_attio"] and not (has_attio_token and (os.getenv("ATTIO_WORKSPACE_ID") or config.get("ATTIO_WORKSPACE_ID"))):
                    status = "❌ Missing ATTIO_ACCESS_TOKEN (or ATTIO_API_KEY) / ATTIO_WORKSPACE_ID"
                elif tool in ["sync_linear"] and not (os.getenv("LINEAR_API_KEY") or config.get("LINEAR_API_KEY")):
                    status = "❌ Missing LINEAR_API_KEY"
                elif tool in ["search_github_repos", "extract_people", "enrich_github_user", "find_commit_emails"] and not (os.getenv("GITHUB_TOKEN") or config.get("GITHUB_TOKEN")):
                    status = "❌ Missing GITHUB_TOKEN"

                print(f"   • {tool}: {status}")
            print()

    print("🔑 To enable all tools, set these environment variables:")
    print("   export GITHUB_TOKEN=your_github_token")
    print("   export OPENAI_API_KEY=your_openai_key")
    print("   export INSTANTLY_API_KEY=your_instantly_key")
    print("   export ATTIO_ACCESS_TOKEN=your_attio_access_token")
    print("   export ATTIO_WORKSPACE_ID=your_workspace_id")
    print("   export LINEAR_API_KEY=your_linear_key")

    print()
    print("🚀 Ready to run: python scripts/run_agent.py 'Find 2k Py maintainers'")


if __name__ == "__main__":
    check_available_tools()
