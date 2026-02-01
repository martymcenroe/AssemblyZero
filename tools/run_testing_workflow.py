#!/usr/bin/env python3
"""CLI entry point for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization

Usage:
    # Full TDD workflow
    python tools/run_testing_workflow.py --issue 42

    # Fast mode (skip E2E)
    python tools/run_testing_workflow.py --issue 42 --skip-e2e

    # Just scaffold tests
    python tools/run_testing_workflow.py --issue 42 --scaffold-only

    # Auto mode (no human gates)
    python tools/run_testing_workflow.py --issue 42 --auto

    # With sandbox repo for E2E
    python tools/run_testing_workflow.py --issue 42 --sandbox-repo mcwiz/agentos-e2e-sandbox

    # Cross-repo (test another project)
    python tools/run_testing_workflow.py --issue 42 --repo /path/to/other/repo
"""

import argparse
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    parser = argparse.ArgumentParser(
        description="Run TDD Testing Workflow on an issue with an approved LLD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Required arguments
    parser.add_argument(
        "--issue",
        type=int,
        required=True,
        help="GitHub issue number (must have approved LLD)",
    )

    # Optional arguments
    parser.add_argument(
        "--repo",
        type=str,
        help="Target repository path (default: current repo)",
    )
    parser.add_argument(
        "--lld",
        type=str,
        help="Path to LLD file (default: auto-detect from issue number)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto mode - skip human gates",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Mock mode - use fixtures instead of real APIs",
    )
    parser.add_argument(
        "--skip-e2e",
        action="store_true",
        help="Skip E2E validation (fast mode)",
    )
    parser.add_argument(
        "--scaffold-only",
        action="store_true",
        help="Stop after scaffolding tests",
    )
    parser.add_argument(
        "--green-only",
        action="store_true",
        help="Only run green phase verification",
    )
    parser.add_argument(
        "--sandbox-repo",
        type=str,
        help="Sandbox repository for E2E tests",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum implementation iterations (default: 10)",
    )
    parser.add_argument(
        "--coverage-target",
        type=int,
        help="Coverage target percentage (default: from LLD or 90)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint",
    )

    args = parser.parse_args()

    # Validate issue number
    if args.issue <= 0:
        print("Error: --issue must be a positive integer")
        sys.exit(1)

    # Set environment variables for mode flags
    if args.auto:
        os.environ["AGENTOS_AUTO_MODE"] = "1"

    # Import after setting up path
    from langgraph.checkpoint.sqlite import SqliteSaver

    from agentos.workflows.testing import TestingWorkflowState, build_testing_workflow
    from agentos.workflows.testing.audit import get_repo_root

    # Determine repo root
    if args.repo:
        repo_root = Path(args.repo).resolve()
        if not repo_root.exists():
            print(f"Error: Repository path does not exist: {repo_root}")
            sys.exit(1)
    else:
        try:
            repo_root = get_repo_root()
        except RuntimeError as e:
            print(f"Error: {e}")
            sys.exit(1)

    print(f"AgentOS TDD Testing Workflow")
    print(f"============================")
    print(f"Issue: #{args.issue}")
    print(f"Repository: {repo_root}")
    print(f"Mode: {'auto' if args.auto else 'interactive'}")
    if args.skip_e2e:
        print(f"E2E: skipped")
    if args.scaffold_only:
        print(f"Mode: scaffold-only")
    print()

    # Build initial state
    initial_state: TestingWorkflowState = {
        "issue_number": args.issue,
        "repo_root": str(repo_root),
        "auto_mode": args.auto,
        "mock_mode": args.mock,
        "skip_e2e": args.skip_e2e,
        "scaffold_only": args.scaffold_only,
        "max_iterations": args.max_iterations,
    }

    if args.lld:
        initial_state["lld_path"] = args.lld

    if args.coverage_target:
        initial_state["coverage_target"] = args.coverage_target

    if args.sandbox_repo:
        initial_state["sandbox_repo"] = args.sandbox_repo

    # Set up checkpoint database
    db_path = Path.home() / ".agentos" / "testing_workflow.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Build workflow
    workflow = build_testing_workflow()

    # Run with checkpointing
    thread_id = f"{args.issue}-testing"

    try:
        with SqliteSaver.from_conn_string(str(db_path)) as memory:
            app = workflow.compile(checkpointer=memory)

            config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": 50,
            }

            # Check for resume
            if args.resume:
                checkpoint = memory.get(config)
                if checkpoint:
                    print(f"Resuming from checkpoint for issue #{args.issue}...")
                else:
                    print(f"No checkpoint found for issue #{args.issue}, starting fresh...")

            # Stream events
            for event in app.stream(initial_state, config):
                # Each event is keyed by node name
                for node_name, node_output in event.items():
                    if node_name == "__end__":
                        continue

                    # Check for errors
                    error = node_output.get("error_message", "")
                    if error:
                        print(f"\n[ERROR] {error}")
                        if "GUARD" in error or "BLOCKED" in error:
                            # These are expected workflow stops, not crashes
                            pass

            # Get final state
            final_state = app.get_state(config)
            if final_state and final_state.values:
                values = final_state.values

                # Print summary
                print("\n" + "=" * 60)
                print("WORKFLOW COMPLETE")
                print("=" * 60)

                if values.get("test_report_path"):
                    print(f"Test Report: {values['test_report_path']}")

                if values.get("error_message"):
                    print(f"Status: {values['error_message']}")
                    return 1
                else:
                    print("Status: SUCCESS")
                    return 0

    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted. Use --resume to continue.")
        return 130

    except Exception as e:
        print(f"\n[FATAL] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
