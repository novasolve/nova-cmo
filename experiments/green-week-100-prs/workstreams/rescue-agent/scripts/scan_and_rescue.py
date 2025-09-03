#!/usr/bin/env python3
import os
import argparse
from typing import List
from rich import print

DEFAULT_QUERY = "is:pr is:open status:failure"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan failing PRs and attempt ≤40‑LOC rescues")
    parser.add_argument("--query", default=os.getenv("SEARCH_QUERY", DEFAULT_QUERY))
    parser.add_argument("--max-prs", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def enforce_loc_limit(diff_lines: List[str], max_lines: int) -> bool:
    return len([ln for ln in diff_lines if ln.startswith("+") or ln.startswith("-")]) <= max_lines


def main() -> None:
    args = parse_args()
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("[yellow]GITHUB_TOKEN not set; running in dry-run discovery mode.[/yellow]")
        args.dry_run = True

    print(f"[bold]Query:[/bold] {args.query}")
    print(f"[bold]Max PRs:[/bold] {args.max_prs}")

    # Placeholder: in a real run, search GitHub PRs with failing CI via GraphQL/REST.
    sample_prs = [
        {"repo": "owner/repo1", "number": 123, "title": "Fix flaky test"},
        {"repo": "owner/repo2", "number": 45, "title": "Refactor utils"},
    ][: args.max_prs]

    for pr in sample_prs:
        print(f"\n[cyan]Analyzing PR:[/cyan] {pr['repo']}#{pr['number']} — {pr['title']}")
        # Placeholder failure summary
        failure_summary = "pytest failure in tests/test_example.py::test_addition"
        print(f"  Failure: {failure_summary}")

        # Placeholder patch proposal (≤40 lines enforced)
        proposed_diff = [
            "+# Fix flaky assertion tolerance",
            "+assert add(2, 2) == 4",
        ]
        max_lines = int(os.getenv("MAX_LINES_PER_PATCH", "40"))
        ok = enforce_loc_limit(proposed_diff, max_lines)
        print(f"  Proposed diff lines: {len(proposed_diff)} (limit {max_lines}) -> {'OK' if ok else 'TOO LARGE'}")

        if args.dry_run or not ok:
            print("  [yellow]Dry run or limit exceeded; not posting patch.[/yellow]")
            continue

        # TODO: Post comment or open PR with patch; trigger CI re-run.
        print("  [green]Would post patch and trigger CI re-run here.[/green]")


if __name__ == "__main__":
    main()
