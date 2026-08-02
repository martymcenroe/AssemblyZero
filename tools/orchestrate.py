#!/usr/bin/env python3
"""CLI entry point for orchestration workflow.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)

Usage:
    poetry run python tools/orchestrate.py --issue 305
    poetry run python tools/orchestrate.py --issue 305 --dry-run
    poetry run python tools/orchestrate.py --issue 305 --resume-from spec
    poetry run python tools/orchestrate.py --issue 305 --skip-lld --no-gate-pr
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# #2040: installed before anything can spawn. A detached roll has no console to
# inherit, so every child -- git, gh, poetry, pytest, claude -- would otherwise
# open its own window on the operator's desktop.
from assemblyzero.core.no_console import install as _install_no_console  # noqa: E402

_install_no_console()

from assemblyzero.workflows.orchestrator.graph import (  # noqa: E402
    ConcurrentOrchestrationError,
    OrchestrationResult,
    orchestrate,
)
from assemblyzero.workflows.orchestrator.state import (  # noqa: E402
    STAGE_ORDER,
    OrchestrationState,
    StageResult,
)


def report_progress(state: OrchestrationState) -> None:
    """Report current stage, duration, and artifacts to stdout."""
    from datetime import datetime

    issue_number = state.get("issue_number", "?")
    current_stage = state.get("current_stage", "unknown")
    started_at = state.get("started_at", "")

    elapsed = ""
    if started_at:
        try:
            start_dt = datetime.fromisoformat(started_at)
            elapsed_s = (datetime.now(start_dt.tzinfo) - start_dt).total_seconds()
            minutes = int(elapsed_s // 60)
            seconds = int(elapsed_s % 60)
            elapsed = f"{minutes}m {seconds}s"
        except (ValueError, TypeError):
            elapsed = "?"

    print(f"\n[ORCHESTRATOR] Issue #{issue_number} | Stage: {current_stage} | Elapsed: {elapsed}")

    stage_results = state.get("stage_results", {})
    for stage in STAGE_ORDER:
        result = stage_results.get(stage, {})
        status = result.get("status", "")
        artifact = result.get("artifact_path", "")

        if status == "passed":
            print(f"  [PASS] {stage} -> {artifact}")
        elif status == "skipped":
            print(f"  [SKIP] {stage} -> {artifact} (skipped)")
        elif status == "failed":
            print(f"  [FAIL] {stage} -- {result.get('error_message', 'unknown error')}")
        elif status == "blocked":
            print(f"  [BLOCK] {stage} -- BLOCKED: {result.get('error_message', '')}")
        elif stage == current_stage:
            print(f"  [....] {stage} (in progress)")
        else:
            print(f"  [    ] {stage}")

    print()


def format_error_message(stage: str, stage_result: StageResult) -> str:
    """Format actionable error message with context."""
    error = stage_result.get("error_message", "Unknown error")
    attempts = stage_result.get("attempts", 0)
    duration = stage_result.get("duration_seconds", 0)

    minutes = int(duration // 60)
    seconds = int(duration % 60)

    # #1941: a replayed attempt must be legible as such without reading
    # transcripts. Diagnosing run11b -- where attempt 2 resumed attempt 1's
    # artifacts verbatim and reproduced its outcome exactly -- required exactly
    # that archaeology.
    retry_mode = stage_result.get("retry_mode", "")
    attempts_line = f"  Attempts: {attempts} | Duration: {minutes}m {seconds}s"
    if attempts > 1 and retry_mode:
        attempts_line += f" | Retries: {retry_mode}"

    lines = [
        "",
        "=" * 58,
        f"  ORCHESTRATION FAILED at stage: {stage}",
        "=" * 58,
        f"  Error: {error}",
        attempts_line,
        "",
        f"  Resume: orchestrate --issue N --resume-from {stage}",
        "=" * 58,
        "",
    ]

    return "\n".join(lines)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Orchestrate end-to-end pipeline from GitHub issue to PR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --issue 305              Run full pipeline
  %(prog)s --issue 305 --dry-run    Show plan without executing
  %(prog)s --issue 305 --resume-from spec  Resume from spec stage
  %(prog)s --issue 305 --no-gate-pr Skip human gate before PR
        """,
    )
    parser.add_argument("--issue", type=int, required=True, help="GitHub issue number")
    parser.add_argument("--repo", type=str, default=None, help="Target repository path to build (default: AssemblyZero)")
    parser.add_argument("--dry-run", action="store_true", help="Show planned stages without execution")
    parser.add_argument("--resume-from", type=str, default=None, choices=STAGE_ORDER, help="Stage to resume from")
    parser.add_argument("--skip-lld", action="store_true", help="Skip LLD stage if artifact exists")
    parser.add_argument("--no-skip-lld", action="store_true", help="Force LLD regeneration")
    parser.add_argument("--skip-spec", action="store_true", help="Skip spec stage if artifact exists")
    parser.add_argument("--no-skip-spec", action="store_true", help="Force spec regeneration")
    parser.add_argument("--gate-pr", action="store_true", default=None, help="Enable human gate before PR")
    parser.add_argument("--no-gate-pr", action="store_true", help="Disable human gate before PR")
    parser.add_argument(
        "--ignore-capacity",
        action="store_true",
        help=(
            "Start even when a provider is recorded as exhausted (#1883). "
            "The record may be stale if the quota window ended early."
        ),
    )
    parser.add_argument(
        "--base-branch",
        type=str,
        default=None,
        dest="base_branch",
        help=(
            "Integration branch every pipeline PR targets (#1755 "
            "attempt-branch model). Default: the branch the target repo "
            "is checked out on."
        ),
    )

    args = parser.parse_args()

    # Build config overrides from CLI args
    overrides: dict = {}
    if args.skip_lld:
        overrides["skip_existing_lld"] = True
    if args.no_skip_lld:
        overrides["skip_existing_lld"] = False
    if args.skip_spec:
        overrides["skip_existing_spec"] = True
    if args.no_skip_spec:
        overrides["skip_existing_spec"] = False
    if args.no_gate_pr:
        overrides.setdefault("gates", {})["pr"] = False
    elif args.gate_pr:
        overrides.setdefault("gates", {})["pr"] = True

    config = overrides if overrides else None

    # Resolve repo targeting (Issue #1374). This file lives at
    # AssemblyZero/tools/orchestrate.py, so parent.parent is the AssemblyZero
    # root. target_repo defaults to it, so omitting --repo builds AssemblyZero.
    assemblyzero_root = str(Path(__file__).resolve().parent.parent)
    target_repo = str(Path(args.repo).resolve()) if args.repo else assemblyzero_root

    print(f"[ORCHESTRATOR] Starting pipeline for issue #{args.issue}")
    print(f"[ORCHESTRATOR] Target repo: {target_repo}")

    # #1883: a run needs BOTH providers — Gemini designs and reviews, Claude
    # implements. Starting one while either is exhausted spends the healthy
    # provider's quota just to discover the dry one, and on a recorded take
    # that is a dead run. Read-only, zero API calls.
    if not args.dry_run and not args.ignore_capacity:
        from assemblyzero.core.capacity import blocked_providers

        blocked = blocked_providers()
        if blocked:
            print("\n" + "=" * 58)
            # ASCII only: the Windows console renders an em-dash as a
            # replacement char, and this banner is read under pressure.
            print("  RUN NOT STARTED - provider capacity exhausted")
            print("=" * 58)
            for status in blocked:
                print(f"  {status.wait_summary()}")
                if status.detail:
                    print(f"    detail: {status.detail[:160]}")
            print(
                "\n  Nothing was spent. Re-run after the reset above, or pass\n"
                "  --ignore-capacity to start anyway."
            )
            print("=" * 58 + "\n")
            sys.exit(2)
    if args.dry_run:
        print("[ORCHESTRATOR] DRY RUN -- no stages will execute")
    if args.resume_from:
        print(f"[ORCHESTRATOR] Resuming from stage: {args.resume_from}")

    try:
        result: OrchestrationResult = orchestrate(
            issue_number=args.issue,
            config=config,
            resume_from=args.resume_from,
            dry_run=args.dry_run,
            target_repo=target_repo,
            assemblyzero_root=assemblyzero_root,
            base_branch=args.base_branch,
        )

        # #1785: the summary IS the per-stage evidence — printed on every
        # exit, success or failure. No more blanket success banner (#1779).
        from assemblyzero.workflows.orchestrator.graph import format_stage_table
        print()
        print(format_stage_table(result["stage_results"]))

        if result["success"]:
            print(f"\n[ORCHESTRATOR] All stages passed.")
            if result["pr_url"]:
                print(f"[ORCHESTRATOR] PR: {result['pr_url']}")
            print(f"[ORCHESTRATOR] Duration: {result['total_duration_seconds']:.1f}s")
        else:
            # Find the failed stage
            for stage_name, stage_result in result["stage_results"].items():
                if stage_result.get("status") in ("failed", "blocked"):
                    print(format_error_message(stage_name, stage_result))
                    break

            if result["error_summary"]:
                print(f"[ORCHESTRATOR] {result['error_summary']}")

            sys.exit(1)

    except ConcurrentOrchestrationError as exc:
        print(f"\n[ORCHESTRATOR] ERROR: {exc}")
        sys.exit(2)
    except ValueError as exc:
        print(f"\n[ORCHESTRATOR] ERROR: {exc}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[ORCHESTRATOR] Interrupted by user. State has been saved.")
        print(f"[ORCHESTRATOR] Resume with: orchestrate --issue {args.issue} --resume-from <stage>")
        sys.exit(130)


if __name__ == "__main__":
    main()
