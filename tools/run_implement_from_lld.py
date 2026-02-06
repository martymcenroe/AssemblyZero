#!/usr/bin/env python3
"""CLI entry point for LLD Implementation Workflow (TDD).

Takes an approved LLD and implements it using Test-Driven Development:
1. Load LLD
2. Review test plan (Gemini)
3. Scaffold tests (red phase)
4. Implement code (Claude)
5. Verify tests pass (green phase)
6. E2E validation
7. Generate documentation

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization

Usage:
    # Full TDD workflow (all gates enabled)
    python tools/run_implement_from_lld.py --issue 42

    # Fast mode (skip E2E)
    python tools/run_implement_from_lld.py --issue 42 --skip-e2e

    # Just scaffold tests
    python tools/run_implement_from_lld.py --issue 42 --scaffold-only

    # Fully automated (no human gates)
    python tools/run_implement_from_lld.py --issue 42 --gates none

    # Only draft gate (skip verdict)
    python tools/run_implement_from_lld.py --issue 42 --gates draft

    # With sandbox repo for E2E
    python tools/run_implement_from_lld.py --issue 42 --sandbox-repo mcwiz/assemblyzero-e2e-sandbox

    # Cross-repo (test another project)
    python tools/run_implement_from_lld.py --issue 42 --repo /path/to/other/repo
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_current_branch(repo_path: Path) -> str:
    """Get the current git branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def find_existing_worktree(repo_path: Path, issue_number: int) -> Path | None:
    """Find an existing worktree for this issue."""
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    # Parse worktree list for issue-specific worktree
    worktree_path = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            path = Path(line.split(" ", 1)[1])
            # Check if this worktree is for our issue
            if f"-{issue_number}" in path.name:
                worktree_path = path
                break

    return worktree_path


def create_worktree(repo_path: Path, issue_number: int) -> tuple[Path, str]:
    """Create a git worktree for the issue.

    Args:
        repo_path: Path to the main repository.
        issue_number: Issue number.

    Returns:
        Tuple of (worktree_path, error_message).
    """
    # Derive project name from repo path
    project_name = repo_path.name

    # Worktree path: ../ProjectName-IssueNumber
    worktree_path = repo_path.parent / f"{project_name}-{issue_number}"

    # Branch name: issue-number-implementation
    branch_name = f"{issue_number}-implementation"

    # Check if worktree already exists AND is valid
    if worktree_path.exists():
        # Verify it's actually a git worktree (has .git file)
        git_marker = worktree_path / ".git"
        if git_marker.exists():
            return worktree_path, ""
        else:
            # Directory exists but isn't a valid worktree - remove it
            import shutil
            shutil.rmtree(worktree_path)
            # Continue to create proper worktree below

    # Create worktree
    result = subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "-b", branch_name],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # Maybe branch already exists - try without -b
        result = subprocess.run(
            ["git", "worktree", "add", str(worktree_path), branch_name],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return worktree_path, f"Failed to create worktree: {result.stderr.strip()}"

    # Push branch to remote
    result = subprocess.run(
        ["git", "push", "-u", "origin", branch_name],
        cwd=str(worktree_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Non-fatal - might be offline or remote doesn't accept
        print(f"    [WARN] Could not push branch to remote: {result.stderr.strip()}")

    return worktree_path, ""


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser for the CLI.

    Separated from main() to enable testing.
    """
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
        "--gates",
        choices=["none", "draft", "verdict", "all"],
        default=None,
        help="Which gates to enable: none, draft, verdict, all (default: all)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="DEPRECATED: Use --gates none instead",
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
    parser.add_argument(
        "--no-worktree",
        action="store_true",
        help="Skip worktree creation (use current directory)",
    )

    return parser


def apply_gates_config(args: argparse.Namespace) -> None:
    """Apply gates configuration to args, handling deprecation.

    Args:
        args: Parsed arguments namespace. Modified in place.
    """
    # Handle deprecated --auto flag
    if args.auto:
        if args.gates is not None:
            # Both flags specified - warn and prefer --gates
            print(
                "WARNING: --auto is deprecated and conflicts with --gates. "
                "Ignoring --auto, using --gates.",
                file=sys.stderr,
            )
        else:
            # Only --auto specified - map to --gates none
            print(
                "WARNING: --auto is deprecated. Use --gates none instead.",
                file=sys.stderr,
            )
            args.gates = "none"

    # Apply default if --gates not specified
    if args.gates is None:
        args.gates = "all"

    # Set individual gate flags based on --gates value
    if args.gates == "none":
        args.gates_draft = False
        args.gates_verdict = False
        args.auto_mode = True
    elif args.gates == "draft":
        args.gates_draft = True
        args.gates_verdict = False
        args.auto_mode = False
    elif args.gates == "verdict":
        args.gates_draft = False
        args.gates_verdict = True
        args.auto_mode = False
    else:  # "all"
        args.gates_draft = True
        args.gates_verdict = True
        args.auto_mode = False


def main():
    parser = create_argument_parser()
    args = parser.parse_args()

    # Apply gates configuration
    apply_gates_config(args)

    # Validate issue number
    if args.issue <= 0:
        print("Error: --issue must be a positive integer")
        sys.exit(1)

    # Set environment variables for mode flags
    if args.auto_mode:
        os.environ["AGENTOS_AUTO_MODE"] = "1"

    # Import after setting up path
    from langgraph.checkpoint.sqlite import SqliteSaver

    from assemblyzero.workflows.testing import TestingWorkflowState, build_testing_workflow
    from assemblyzero.workflows.testing.audit import get_repo_root

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

    # Track original repo for worktree cleanup later
    original_repo_root = repo_root
    worktree_path = None

    # Handle worktree creation/detection
    if not args.no_worktree:
        current_branch = get_current_branch(repo_root)

        # Check if we're on main/master (need worktree)
        if current_branch in ("main", "master"):
            # Check for existing worktree first
            existing = find_existing_worktree(repo_root, args.issue)

            if existing and existing.exists():
                print(f"Found existing worktree: {existing}")
                repo_root = existing
                worktree_path = existing
            else:
                print(f"Creating worktree for issue #{args.issue}...")
                worktree_path, error = create_worktree(repo_root, args.issue)
                if error:
                    print(f"Error: {error}")
                    sys.exit(1)
                print(f"Created worktree: {worktree_path}")
                repo_root = worktree_path
        elif f"-{args.issue}" in current_branch or f"{args.issue}-" in current_branch:
            # Already on issue branch - likely in a worktree
            print(f"Already on issue branch: {current_branch}")
        else:
            # On some other branch - warn user
            print(f"WARNING: On branch '{current_branch}', not main.")
            print("         Use --no-worktree to skip worktree creation.")
            print("         Or switch to main first: git checkout main")
            sys.exit(1)

    print()
    print(f"AssemblyZero TDD Testing Workflow")
    print(f"============================")
    print(f"Issue: #{args.issue}")
    print(f"Repository: {repo_root}")
    if worktree_path:
        print(f"Worktree: {worktree_path}")
    print(f"Mode: {'auto' if args.auto_mode else 'interactive'}")
    if args.skip_e2e:
        print(f"E2E: skipped")
    if args.scaffold_only:
        print(f"Mode: scaffold-only")
    print()

    # Build initial state
    initial_state: TestingWorkflowState = {
        "issue_number": args.issue,
        "repo_root": str(repo_root),
        "auto_mode": args.auto_mode,
        "mock_mode": args.mock,
        "skip_e2e": args.skip_e2e,
        "scaffold_only": args.scaffold_only,
        "max_iterations": args.max_iterations,
    }

    # Track worktree for later reference (cleanup, PR creation)
    if worktree_path:
        initial_state["worktree_path"] = str(worktree_path)
        initial_state["original_repo_root"] = str(original_repo_root)

    if args.lld:
        initial_state["lld_path"] = args.lld

    if args.coverage_target:
        initial_state["coverage_target"] = args.coverage_target

    if args.sandbox_repo:
        initial_state["sandbox_repo"] = args.sandbox_repo

    # Set up checkpoint database
    db_path = Path.home() / ".assemblyzero" / "testing_workflow.db"
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

                # Debug: Show key final state values
                print(f"DEBUG: Final state error_message: '{values.get('error_message', '')}'")
                print(f"DEBUG: Final state next_node: '{values.get('next_node', '')}'")
                print(f"DEBUG: Final state iteration_count: {values.get('iteration_count', 0)}")
                print(f"DEBUG: Final state coverage_achieved: {values.get('coverage_achieved', 0)}")

                if values.get("test_report_path"):
                    print(f"Test Report: {values['test_report_path']}")

                if values.get("error_message"):
                    print(f"Status: {values['error_message']}")
                    return 1
                else:
                    print("Status: SUCCESS")

                    # Show next steps for worktree workflow
                    if worktree_path:
                        print()
                        print("Next steps:")
                        print(f"  1. cd {worktree_path}")
                        print("  2. Review changes: git diff")
                        print("  3. Commit: git add . && git commit -m 'feat: implement issue #{}'".format(args.issue))
                        print("  4. Create PR: gh pr create")

                    return 0

    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted. Use --resume to continue.")
        return 130

    except Exception as e:
        # Check if this is an ImplementationError (issue #272)
        if type(e).__name__ == "ImplementationError":
            print(f"\n{'='*60}")
            print("IMPLEMENTATION FAILED")
            print(f"{'='*60}")
            print(f"File: {getattr(e, 'filepath', 'unknown')}")
            print(f"Reason: {getattr(e, 'reason', str(e))}")
            preview = getattr(e, 'response_preview', None)
            if preview:
                print(f"\nResponse preview:\n{preview[:500]}")
            print(f"\nThis is a hard failure. The implementation node could not produce valid code.")
            print("Check the LLD specification and try again.")
            return 1

        print(f"\n[FATAL] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
