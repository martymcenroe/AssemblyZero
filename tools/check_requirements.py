#!/usr/bin/env python3
"""Run the N0c requirements-consistency gate against an issue, without a roll.

Issue #2221. The gate is node 3 of the LLD workflow, so every ruling on an
issue's text used to be verified by paying for the next launch. This calls the
same gate directly -- imported from the workflow, never reimplemented -- so a
defect in an edit is found while the editor still holds the context.

    poetry run python tools/check_requirements.py \\
        --repo /c/Users/mcwiz/Projects/boostgauge --issue 7

The call costs one drafter-class model request (roughly 200 seconds). What it
saves is the launch around it: the codebase-analysis node, the blocked
launcher, the filed issues, and the operator round-trip.

Exit codes:
    0  clean    -- the gate ran and found no contradictions
    1  conflict -- the gate ran and found at least one; they print verbatim
    2  error    -- the check could not run, so nothing was verified

There is no fail-open here. In a roll the gate proceeds on a dead provider by
design; standalone, an analysis that cannot run exits 2 rather than passing.

On conflict the gate files must-resolve issues on the target repo, exactly as
it does in a roll. That is the imported behavior, not an addition.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assemblyzero.workflows.requirements.precheck import (  # noqa: E402
    DEFAULT_DRAFTER,
    EXIT_ERROR,
    PrecheckError,
    fetch_issue,
    render_report,
    run_gate,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the LLD workflow's requirements-consistency gate against a "
            "GitHub issue without launching a roll."
        )
    )
    parser.add_argument("--repo", required=True, help="target repository checkout")
    parser.add_argument("--issue", required=True, type=int, help="issue number")
    parser.add_argument(
        "--drafter",
        default=DEFAULT_DRAFTER,
        help=f"provider spec for the analysis call (default: {DEFAULT_DRAFTER})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="mirror the gate's own output while it runs",
    )
    args = parser.parse_args(argv)

    # Issue #773: subscription only. Never the paid Anthropic API.
    from assemblyzero.core.llm_provider import set_api_policy

    set_api_policy(False)

    repo = Path(args.repo).resolve()

    try:
        title, body = fetch_issue(repo, args.issue)
        print(
            f"Reading #{args.issue} through the N0c gate with {args.drafter} "
            f"-- one model call, expect a few minutes.",
            flush=True,
        )
        result = run_gate(
            repo,
            args.issue,
            title,
            body,
            drafter=args.drafter,
            echo_stream=sys.stdout if args.verbose else None,
        )
    except PrecheckError as exc:
        print(f"\nERROR -- the pre-check could not run: {exc}", file=sys.stderr)
        print(
            "Nothing about this issue's requirements has been verified.",
            file=sys.stderr,
        )
        return EXIT_ERROR

    print()
    print(render_report(result, repo, args.issue, args.drafter), end="", flush=True)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
