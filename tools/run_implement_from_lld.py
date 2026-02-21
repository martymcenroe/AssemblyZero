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
    # Select from approved LLDs interactively
    python tools/run_implement_from_lld.py --select

    # Full TDD workflow (auto, no human review)
    python tools/run_implement_from_lld.py --issue 42

    # Fast mode (skip E2E)
    python tools/run_implement_from_lld.py --issue 42 --skip-e2e

    # Just scaffold tests
    python tools/run_implement_from_lld.py --issue 42 --scaffold-only

    # With human review at all stages
    python tools/run_implement_from_lld.py --issue 42 --review all

    # With human review at draft stage only
    python tools/run_implement_from_lld.py --issue 42 --review draft

    # With sandbox repo for E2E
    python tools/run_implement_from_lld.py --issue 42 --sandbox-repo mcwiz/assemblyzero-e2e-sandbox

    # Cross-repo (test another project)
    python tools/run_implement_from_lld.py --issue 42 --repo /path/to/other/repo
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Issue #120: Configure LangSmith tracing (enabled when LANGSMITH_API_KEY is set)
from assemblyzero.tracing import configure_langsmith
configure_langsmith()


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


def get_checkpoint_db_path(issue_number: int = 0) -> Path:
    """Get path to SQLite checkpoint database.

    Priority:
    1. ASSEMBLYZERO_WORKFLOW_DB environment variable (explicit override)
    2. Per-issue database: testing_{issue_number}.db
    3. Fallback: testing_workflow.db (when issue_number is 0)

    Issue #379: Partition database by issue to prevent concurrent deadlocks.

    Args:
        issue_number: GitHub issue number for per-issue partitioning.

    Returns:
        Path to checkpoint database.
    """
    if db_path_env := os.environ.get("ASSEMBLYZERO_WORKFLOW_DB"):
        db_path = Path(db_path_env)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    db_dir = Path.home() / ".assemblyzero"
    db_dir.mkdir(parents=True, exist_ok=True)

    if issue_number > 0:
        return db_dir / f"testing_{issue_number}.db"

    return db_dir / "testing_workflow.db"


def select_approved_lld(repo_root: Path) -> int | None:
    """Interactively select from approved LLDs in docs/lld/active/.

    Scans for LLD-NNN.md files, extracts issue number, title, and
    approval status from each file.

    Args:
        repo_root: Path to repository root.

    Returns:
        Selected issue number, or None if cancelled/no LLDs found.
    """
    lld_dir = repo_root / "docs" / "lld" / "active"
    if not lld_dir.exists():
        print(f"No LLD directory found: {lld_dir}")
        return None

    # Scan for LLD files
    lld_files = sorted(lld_dir.glob("LLD-*.md"))
    if not lld_files:
        print("No LLD files found in docs/lld/active/")
        return None

    entries = []
    for lld_path in lld_files:
        # Extract issue number from filename (LLD-NNN.md)
        match = re.match(r"LLD-(\d+)\.md", lld_path.name)
        if not match:
            continue
        issue_num = int(match.group(1))

        # Read first line for title, scan for approval status
        content = lld_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()

        title = ""
        approved = False
        approval_date = ""

        # Title from first heading
        for line in lines[:5]:
            if line.startswith("# "):
                title = line.lstrip("# ").strip()
                # Strip issue number prefix if present (e.g., "305 - Feature: ...")
                title = re.sub(r"^\d+\s*[-–—]\s*", "", title)
                break

        # Check for APPROVED in review log
        for line in lines:
            if "APPROVED" in line and "|" in line:
                approved = True
                # Try to extract date from table row
                cells = [c.strip() for c in line.split("|")]
                for cell in cells:
                    if re.match(r"\d{4}-\d{2}-\d{2}", cell):
                        approval_date = cell
                        break
                break

        entries.append({
            "issue": issue_num,
            "title": title[:60],
            "approved": approved,
            "date": approval_date,
            "path": lld_path,
        })

    if not entries:
        print("No valid LLD files found.")
        return None

    # Display menu
    print()
    print("=" * 70)
    print("Approved LLDs ready for implementation")
    print("=" * 70)

    for i, entry in enumerate(entries, 1):
        status = "APPROVED" if entry["approved"] else "pending"
        date_str = f" ({entry['date']})" if entry["date"] else ""
        print(f"  [{i:2d}] #{entry['issue']:>4d}: {entry['title']}")
        print(f"        Status: {status}{date_str}")

    print()
    print(f"  [ 0] Cancel")
    print()

    # Prompt for selection
    try:
        choice = input(f"Select LLD [0-{len(entries)}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return None

    try:
        idx = int(choice)
    except ValueError:
        print("Invalid selection.")
        return None

    if idx == 0:
        print("Cancelled.")
        return None

    if idx < 1 or idx > len(entries):
        print(f"Invalid selection. Choose 1-{len(entries)} or 0 to cancel.")
        return None

    selected = entries[idx - 1]
    print(f"\nSelected: #{selected['issue']} - {selected['title']}")
    return selected["issue"]


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser for the CLI.

    Separated from main() to enable testing.
    """
    parser = argparse.ArgumentParser(
        description="Run TDD Testing Workflow on an issue with an approved LLD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Issue selection (mutually exclusive)
    issue_group = parser.add_mutually_exclusive_group(required=True)
    issue_group.add_argument(
        "--issue",
        type=int,
        help="GitHub issue number (must have approved LLD)",
    )
    issue_group.add_argument(
        "--select",
        action="store_true",
        help="Interactively select from approved LLDs in docs/lld/active/",
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
        "--review",
        choices=["none", "draft", "verdict", "all"],
        default=None,
        dest="review",
        help="Human review stages: none (default) | draft | verdict | all",
    )
    parser.add_argument(
        "--gates",
        default=None,
        dest="gates_deprecated",
        help=argparse.SUPPRESS,  # Hidden deprecated alias for --review
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help=argparse.SUPPRESS,  # Hidden deprecated alias
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
    parser.add_argument(
        "--db-path",
        type=str,
        help="Path to checkpoint database (overrides default per-issue partitioning)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview execution plan without API calls or file modifications",
    )
    parser.add_argument(
        "--context",
        action="append",
        default=[],
        help="Additional context files to inject into prompts (can be repeated)",
    )
    parser.add_argument(
        "--issue-only",
        action="store_true",
        help="Use issue body as spec (skip LLD/spec file search). For small changes.",
    )

    return parser


def apply_review_config(args: argparse.Namespace) -> None:
    """Apply review configuration to args, handling deprecated flags.

    Args:
        args: Parsed arguments namespace. Modified in place.
    """
    # Handle deprecated --gates flag
    if args.gates_deprecated is not None:
        print(
            "WARNING: --gates is deprecated. Use --review instead.",
            file=sys.stderr,
        )
        gates_val = args.gates_deprecated.lower().strip()
        if gates_val in ("draft,verdict", "verdict,draft", "both"):
            args.review = "all"
        else:
            args.review = gates_val

    # Handle deprecated --auto flag
    if args.auto:
        print(
            "WARNING: --auto is deprecated. Use --review none instead.",
            file=sys.stderr,
        )
        if args.review is None:
            args.review = "none"

    # Apply default if --review not specified
    if args.review is None:
        args.review = "none"

    # Set individual gate flags based on --review value
    if args.review == "none":
        args.gates_draft = False
        args.gates_verdict = False
        args.auto_mode = True
    elif args.review == "draft":
        args.gates_draft = True
        args.gates_verdict = False
        args.auto_mode = False
    elif args.review == "verdict":
        args.gates_draft = False
        args.gates_verdict = True
        args.auto_mode = False
    else:  # "all"
        args.gates_draft = True
        args.gates_verdict = True
        args.auto_mode = False


def _write_status_file(
    repo_root: Path,
    issue_number: int,
    status: str,
    error: str = "",
) -> None:
    """Write a discoverable status file to the repo root.

    Issue #380: When SQLite checkpointing fails, this file is still
    discoverable so agents can detect success/failure independently.

    Args:
        repo_root: Repository root path.
        issue_number: GitHub issue number.
        status: "SUCCESS" or "FAILED".
        error: Error message if failed.
    """
    import json
    from datetime import datetime, timezone

    status_file = Path(repo_root) / f".implement-status-{issue_number}.json"
    try:
        status_data = {
            "issue": issue_number,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "repo": str(repo_root),
        }
        if error:
            status_data["error"] = error
        status_file.write_text(json.dumps(status_data, indent=2), encoding="utf-8")
        print(f"[implement] Status file: {status_file}")
    except OSError:
        pass  # Non-fatal — best-effort status file


def main():
    parser = create_argument_parser()
    args = parser.parse_args()

    # Apply review configuration
    apply_review_config(args)

    # Set environment variables for mode flags
    if args.auto_mode:
        os.environ["ASSEMBLYZERO_AUTO_MODE"] = "1"

    # Import after setting up path
    from langgraph.checkpoint.sqlite import SqliteSaver

    from assemblyzero.workflows.testing import TestingWorkflowState, build_testing_workflow
    from assemblyzero.workflows.testing.audit import get_repo_root

    # Determine repo root (needed before --select)
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

    # Handle --select: interactive LLD selection
    if args.select:
        selected = select_approved_lld(repo_root)
        if selected is None:
            sys.exit(0)
        args.issue = selected

    # Validate issue number
    if args.issue is None or args.issue <= 0:
        print("Error: --issue must be a positive integer")
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

    # Set up checkpoint database (Issue #379: per-issue partitioning)
    if args.db_path:
        db_path = Path(args.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        db_path = get_checkpoint_db_path(args.issue)

    # Startup banner (Issue #380: visible diagnostics for cross-repo debugging)
    print()
    print(f"[implement] AssemblyZero TDD Testing Workflow")
    print(f"[implement] ============================")
    print(f"[implement] Issue: #{args.issue}")
    print(f"[implement] Repository: {repo_root}")
    if worktree_path:
        print(f"[implement] Worktree: {worktree_path}")
    print(f"[implement] Database: {db_path}")
    print(f"[implement] Mode: {'auto' if args.auto_mode else 'interactive'}")
    if args.skip_e2e:
        print(f"[implement] E2E: skipped")
    if args.scaffold_only:
        print(f"[implement] Mode: scaffold-only")
    if args.issue_only:
        print(f"[implement] Mode: issue-only (no LLD)")
    if args.dry_run:
        print(f"[implement] Mode: DRY RUN")
    print()

    # Issue #290: Dry-run — preview execution plan and exit
    if args.dry_run:
        lld_path = repo_root / "docs" / "lld" / "active" / f"LLD-{args.issue:03d}.md"
        lld_exists = lld_path.exists()
        print("[DRY RUN] Would execute:")
        print("  N0_load_lld -> N1_review_test_plan -> N2_scaffold_tests -> N3_verify_red")
        print("  -> N4_implement_code -> N5_verify_green -> N6_e2e_validation -> N7_finalize")
        print()
        print(f"  LLD: {lld_path} ({'found' if lld_exists else 'NOT FOUND'})")
        print(f"  Database: {db_path}")
        print(f"  Mock mode: {args.mock}")
        print(f"  Skip E2E: {args.skip_e2e}")
        print(f"  Max iterations: {args.max_iterations}")
        print()
        print("[DRY RUN] No API calls made, no files modified.")
        return 0

    # Issue #288/#289: Load and validate context files
    context_content = ""
    if args.context:
        from assemblyzero.workflows.testing.path_validator import load_context_files

        print(f"[implement] Loading {len(args.context)} context file(s)...")
        context_content, context_errors = load_context_files(args.context, repo_root)
        for err in context_errors:
            print(f"[implement] {err}")
        if context_errors and not context_content:
            print("[implement] ERROR: All context files failed validation")
            sys.exit(1)
        if context_content:
            print(f"[implement] Context loaded: {len(context_content):,} chars")

    # Build initial state
    initial_state: TestingWorkflowState = {
        "issue_number": args.issue,
        "repo_root": str(repo_root),
        "auto_mode": args.auto_mode,
        "mock_mode": args.mock,
        "skip_e2e": args.skip_e2e,
        "scaffold_only": args.scaffold_only,
        "max_iterations": args.max_iterations,
        "context_files": args.context or [],
        "context_content": context_content,
        "issue_only": args.issue_only,
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
                    _write_status_file(repo_root, args.issue, "FAILED", values.get("error_message", ""))
                    return 1
                else:
                    print("Status: SUCCESS")
                    _write_status_file(repo_root, args.issue, "SUCCESS")

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
