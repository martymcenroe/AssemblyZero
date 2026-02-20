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

from assemblyzero.workflows.orchestrator.graph import (
    ConcurrentOrchestrationError,
    OrchestrationResult,
    orchestrate,
)
from assemblyzero.workflows.orchestrator.state import (
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

    lines = [
        "",
        "=" * 58,
        f"  ORCHESTRATION FAILED at stage: {stage}",
        "=" * 58,
        f"  Error: {error}",
        f"  Attempts: {attempts} | Duration: {minutes}m {seconds}s",
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
    parser.add_argument("--dry-run", action="store_true", help="Show planned stages without execution")
    parser.add_argument("--resume-from", type=str, default=None, choices=STAGE_ORDER, help="Stage to resume from")
    parser.add_argument("--skip-lld", action="store_true", help="Skip LLD stage if artifact exists")
    parser.add_argument("--no-skip-lld", action="store_true", help="Force LLD regeneration")
    parser.add_argument("--skip-spec", action="store_true", help="Skip spec stage if artifact exists")
    parser.add_argument("--no-skip-spec", action="store_true", help="Force spec regeneration")
    parser.add_argument("--gate-pr", action="store_true", default=None, help="Enable human gate before PR")
    parser.add_argument("--no-gate-pr", action="store_true", help="Disable human gate before PR")

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

    print(f"[ORCHESTRATOR] Starting pipeline for issue #{args.issue}")
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
        )

        if result["success"]:
            print(f"\n[ORCHESTRATOR] Pipeline completed successfully!")
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
