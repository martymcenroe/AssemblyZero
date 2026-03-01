

```python
#!/usr/bin/env python3
"""CLI entry point for the Janitor workflow.

Usage:
    python tools/run_janitor_workflow.py [OPTIONS]

Options:
    --scope {all|links|worktrees|harvest|todo}  Probes to run (default: all)
    --auto-fix {true|false}                     Apply auto-fixes (default: true)
    --dry-run                                   Preview mode, no modifications
    --silent                                    Suppress stdout on success
    --create-pr                                 Create PR instead of direct commit
    --reporter {github|local}                   Report backend (default: github)

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from assemblyzero.workflows.janitor.graph import build_janitor_graph
from assemblyzero.workflows.janitor.state import JanitorState, ProbeScope

ALL_SCOPES: list[ProbeScope] = ["links", "worktrees", "harvest", "todo"]
VALID_SCOPES = ["all"] + ALL_SCOPES


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Janitor: Automated repository hygiene workflow"
    )
    parser.add_argument(
        "--scope",
        choices=VALID_SCOPES,
        default="all",
        help="Which probes to run (default: all)",
    )
    parser.add_argument(
        "--auto-fix",
        type=lambda v: v.lower() in ("true", "1", "yes"),
        default=True,
        help="Apply auto-fixes (default: true)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview mode — no file modifications or issue creation",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        default=False,
        help="Suppress stdout output on success",
    )
    parser.add_argument(
        "--create-pr",
        action="store_true",
        default=False,
        help="Create PR instead of direct commit",
    )
    parser.add_argument(
        "--reporter",
        choices=["github", "local"],
        default="github",
        help="Report backend (default: github)",
    )
    return parser.parse_args(argv)


def build_initial_state(args: argparse.Namespace) -> JanitorState:
    """Convert parsed CLI args into initial JanitorState."""
    # Determine repo root
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    repo_root = result.stdout.strip()

    # Determine scope
    scope: list[ProbeScope] = (
        ALL_SCOPES if args.scope == "all" else [args.scope]
    )

    return JanitorState(
        repo_root=repo_root,
        scope=scope,
        auto_fix=args.auto_fix,
        dry_run=args.dry_run,
        silent=args.silent,
        create_pr=args.create_pr,
        reporter_type=args.reporter,
        probe_results=[],
        all_findings=[],
        fix_actions=[],
        unfixable_findings=[],
        report_url=None,
        exit_code=0,
    )


def _print_summary(state: JanitorState) -> None:
    """Print a human-readable summary to stdout."""
    findings_count = len(state.get("all_findings", []))
    fix_count = len(state.get("fix_actions", []))
    unfixable_count = len(state.get("unfixable_findings", []))
    report_url = state.get("report_url")

    print(f"\n Janitor Summary:")
    print(f"   Findings:  {findings_count}")
    print(f"   Fixed:     {fix_count}")
    print(f"   Unfixable: {unfixable_count}")

    if report_url:
        print(f"   Report:    {report_url}")

    exit_code = state.get("exit_code", 0)
    if exit_code == 0:
        print("   Status:    [PASS] All clean")
    else:
        print("   Status:    [WARN] Unfixable issues remain")


def main(argv: list[str] | None = None) -> int:
    """Entry point. Build graph, execute, return exit code.

    Returns:
        0 if all issues fixed or no issues found
        1 if unfixable issues remain
        2 if a fatal error occurred
    """
    args = parse_args(argv)

    # Validate git repo
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if not args.silent:
            print("Error: not a git repository", file=sys.stderr)
        return 2

    try:
        initial_state = build_initial_state(args)
        graph = build_janitor_graph()
        final_state = graph.invoke(initial_state)

        if not args.silent:
            _print_summary(final_state)

        return final_state.get("exit_code", 0)
    except Exception as e:
        if not args.silent:
            print(f"Fatal error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
```
