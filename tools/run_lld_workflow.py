#!/usr/bin/env python3
"""CLI runner for LLD Governance workflow.

Issue #86: LLD Creation & Governance Review Workflow
Issue #95: --select and LLD Status Tracking
LLD: docs/lld/active/LLD-086-lld-governance-workflow.md

Usage:
    python tools/run_lld_workflow.py --issue 42
    python tools/run_lld_workflow.py --select
    python tools/run_lld_workflow.py --audit
    python tools/run_lld_workflow.py --issue 42 --auto
    python tools/run_lld_workflow.py --issue 42 --mock
    python tools/run_lld_workflow.py --issue 42 --context file.py --context another.md
    python tools/run_lld_workflow.py --issue 42 --resume
    python tools/run_lld_workflow.py --repo /path/to/repo --select

Options:
    --issue <number>      GitHub issue number
    --select              Interactive picker for open GitHub issues
    --audit               Rebuild lld-status.json from all LLD files
    --context <path>      Additional context files (can specify multiple)
    --auto                Auto mode: skip VS Code, auto-send to Gemini
    --mock                Mock mode: use fixtures instead of real APIs
    --resume              Resume interrupted workflow from checkpoint
    --max-iterations <n>  Maximum review iterations (default: 20)
    --repo <path>         Target repository root (default: auto-detect via git)
    --help                Show this help message
"""

import argparse
import os
import sys
import warnings
from pathlib import Path

# Disable LangSmith telemetry to avoid authentication errors
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGCHAIN_API_KEY"] = ""

# Suppress deprecation warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import json
import subprocess

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.errors import GraphRecursionError

from agentos.workflows.lld.audit import (
    AUDIT_ACTIVE_DIR,
    check_lld_status,
    get_repo_root,
    load_lld_tracking,
    rebuild_lld_cache,
)
from agentos.workflows.lld.graph import build_lld_workflow
from agentos.workflows.lld.state import LLDWorkflowState


def get_audit_dir(repo_root: Path, issue_number: int) -> Path:
    """Get the audit directory path for an issue.

    Args:
        repo_root: Repository root path.
        issue_number: GitHub issue number.

    Returns:
        Path to audit directory.
    """
    return repo_root / AUDIT_ACTIVE_DIR / f"{issue_number}-lld"


def count_audit_files(audit_dir: Path) -> tuple[int, int]:
    """Count draft and verdict files in audit directory.

    Part 5.1 fix: Read counters from audit directory (ground truth).

    Args:
        audit_dir: Path to the audit directory.

    Returns:
        Tuple of (draft_count, verdict_count).
    """
    if not audit_dir.exists():
        return 0, 0

    draft_count = len(list(audit_dir.glob("*-draft.md")))
    verdict_count = len(list(audit_dir.glob("*-verdict.md")))
    return draft_count, verdict_count


def select_issue_interactive(repo_root: Path | None = None) -> tuple[int, str] | None:
    """Interactive picker for open GitHub issues.

    Flow:
    1. Fetch open issues via gh CLI
    2. Load lld-status.json for cached statuses
    3. Filter out issues with status="approved"
    4. Display with status indicators
    5. Return (issue_number, title) or None

    Args:
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        Tuple of (issue_number, title) if selected, None if quit.
    """
    print("\nFetching open GitHub issues...")

    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--json", "number,title", "--limit", "50"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(repo_root) if repo_root else None,  # Use target repo for gh commands
        )

        if result.returncode != 0:
            print(f"Error fetching issues: {result.stderr.strip()}")
            return None

        issues = json.loads(result.stdout)

    except subprocess.TimeoutExpired:
        print("Timeout fetching issues from GitHub")
        return None
    except json.JSONDecodeError as e:
        print(f"Failed to parse issues: {e}")
        return None

    if not issues:
        print("No open issues found.")
        return None

    # Load LLD tracking cache
    tracking = load_lld_tracking(repo_root)
    lld_statuses = tracking.get("issues", {})

    # Prepare display list - filter out approved issues entirely
    display_items = []
    skipped_count = 0
    for issue in issues:
        issue_num = issue["number"]
        title = issue["title"]

        # Check LLD status
        status = lld_statuses.get(str(issue_num), {})
        lld_status = status.get("status", "new")

        # Skip approved issues - they don't need LLDs created
        if lld_status == "approved":
            skipped_count += 1
            continue

        if lld_status == "draft":
            indicator = "[DRAFT - has unreviewed LLD]"
        elif lld_status == "blocked":
            indicator = "[BLOCKED - needs revision]"
        else:
            indicator = "[NEW]"

        display_items.append({
            "number": issue_num,
            "title": title,
            "lld_status": lld_status,
            "indicator": indicator,
        })

    if not display_items:
        print("No issues need LLDs. All open issues already have approved LLDs.")
        return None

    # Display
    print(f"\n{'=' * 60}")
    print("Select Issue for LLD Creation")
    if skipped_count > 0:
        print(f"({skipped_count} issues with approved LLDs hidden)")
    print(f"{'=' * 60}\n")

    for i, item in enumerate(display_items, 1):
        print(f"  [{i}] #{item['number']} {item['title'][:40]}")
        print(f"       {item['indicator']}")

    print(f"\n  [q] Quit")
    print()

    # Test mode: select first issue
    if os.environ.get("AGENTOS_TEST_MODE") == "1":
        if display_items:
            choice = "1"
            item = display_items[0]
            print(f"Select issue [1-{len(display_items)}, q]: {choice} (TEST MODE - auto-select)")
            return (item["number"], item["title"])
        print("No issues available in test mode.")
        return None

    while True:
        choice = input(f"Select issue [1-{len(display_items)}, q]: ").strip().lower()

        if choice == "q":
            return None

        try:
            idx = int(choice)
            if 1 <= idx <= len(display_items):
                item = display_items[idx - 1]
                return (item["number"], item["title"])
            else:
                print(f"Invalid number. Enter 1-{len(display_items)} or q.")
        except ValueError:
            print("Invalid input. Enter a number or q.")


def run_audit(repo_root: Path | None = None) -> int:
    """Rebuild lld-status.json from all LLD files.

    Args:
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        Exit code (0 for success).
    """
    print(f"\n{'=' * 60}")
    print("LLD Status Audit")
    print(f"{'=' * 60}\n")

    count = rebuild_lld_cache(repo_root)

    return 0


def get_checkpoint_db_path() -> Path:
    """Get path to checkpoint database.

    Uses AGENTOS_WORKFLOW_DB environment variable if set,
    otherwise defaults to ~/.agentos/lld_workflow.db.

    Returns:
        Path to SQLite database file.
    """
    env_path = os.environ.get("AGENTOS_WORKFLOW_DB")
    if env_path:
        return Path(env_path)

    # Default location
    agentos_dir = Path.home() / ".agentos"
    agentos_dir.mkdir(parents=True, exist_ok=True)
    return agentos_dir / "lld_workflow.db"


def run_workflow(
    issue_number: int,
    context_files: list[str] | None = None,
    auto_mode: bool = False,
    mock_mode: bool = False,
    resume: bool = False,
    max_iterations: int = 20,
    repo_root: Path | None = None,
) -> int:
    """Run the LLD governance workflow.

    Args:
        issue_number: GitHub issue number.
        context_files: Optional list of context file paths.
        auto_mode: If True, skip VS Code and auto-send to review.
        mock_mode: If True, use fixtures instead of real APIs.
        resume: If True, resume from checkpoint.
        max_iterations: Maximum review iterations.
        repo_root: Target repository root path (for cross-repo workflows).

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    # Build workflow
    workflow = build_lld_workflow()

    # Thread ID for checkpointing
    thread_id = f"lld-{issue_number}"

    # Get checkpoint database path
    db_path = get_checkpoint_db_path()

    print(f"\n{'=' * 60}")
    print(f"LLD Governance Workflow - Issue #{issue_number}")
    print(f"{'=' * 60}")

    if mock_mode:
        print("Mode: MOCK (using fixtures)")
    elif auto_mode:
        print("Mode: AUTO (unattended)")
        # Set environment variable for nodes to detect auto mode
        os.environ["AGENTOS_AUTO_MODE"] = "1"
    else:
        print("Mode: INTERACTIVE")

    if context_files:
        print(f"Context files: {len(context_files)}")

    print(f"Checkpoint DB: {db_path}")
    print(f"Max iterations: {max_iterations} (recursion_limit: {max_iterations * 10})")
    print(f"{'=' * 60}\n")

    # Part 6.2 fix: Initialize all TypedDict fields from LLDWorkflowState
    initial_state: LLDWorkflowState = {
        # Input parameters
        "issue_number": issue_number,
        "context_files": context_files or [],
        "repo_root": str(repo_root) if repo_root else "",
        "auto_mode": auto_mode,
        "mock_mode": mock_mode,
        # Iteration limits
        "iteration_count": 0,
        "max_iterations": max_iterations,
        # Counters
        "draft_count": 0,
        "verdict_count": 0,
        "file_counter": 0,
        # Issue content (populated by N0)
        "issue_id": 0,
        "issue_title": "",
        "issue_body": "",
        "context_content": "",
        # Audit trail (populated by N0)
        "audit_dir": "",
        # Design output (populated by N1)
        "lld_draft_path": "",
        "lld_content": "",
        "design_status": "",
        # Review output (populated by N3)
        "lld_status": "",
        "gemini_critique": "",
        # Human input (populated by N2)
        "user_feedback": "",
        # Routing
        "next_node": "",
        # Final output (populated by N4)
        "final_lld_path": "",
        # Error handling
        "error_message": "",
    }

    # Run with checkpointer
    with SqliteSaver.from_conn_string(str(db_path)) as memory:
        app = workflow.compile(checkpointer=memory)
        # Set recursion_limit high enough for max_iterations (each iteration = multiple nodes)
        recursion_limit = max_iterations * 10
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": recursion_limit,
        }

        if resume:
            # Check if checkpoint exists
            state = app.get_state(config)
            if state.values:
                print(f"Resuming from checkpoint...")

                # Part 1.3 fix: Recalculate counters from audit directory (ground truth)
                checkpoint_repo_root = state.values.get("repo_root", "")
                actual_repo_root = Path(checkpoint_repo_root) if checkpoint_repo_root else (repo_root or get_repo_root())
                audit_dir = get_audit_dir(actual_repo_root, issue_number)
                actual_draft_count, actual_verdict_count = count_audit_files(audit_dir)

                checkpoint_draft_count = state.values.get('draft_count', 0)
                checkpoint_verdict_count = state.values.get('verdict_count', 0)

                # Warn if counters don't match
                if actual_draft_count != checkpoint_draft_count:
                    print(f"  [WARN] Draft count mismatch: checkpoint={checkpoint_draft_count}, audit={actual_draft_count}")
                if actual_verdict_count != checkpoint_verdict_count:
                    print(f"  [WARN] Verdict count mismatch: checkpoint={checkpoint_verdict_count}, audit={actual_verdict_count}")

                print(f"  Iteration: {state.values.get('iteration_count', 0)}")
                print(f"  Drafts: {actual_draft_count} (from audit dir)")
                print(f"  Verdicts: {actual_verdict_count} (from audit dir)")
                print()

                # Update state with accurate counters before resuming
                if actual_draft_count != checkpoint_draft_count or actual_verdict_count != checkpoint_verdict_count:
                    app.update_state(
                        config,
                        {
                            "draft_count": actual_draft_count,
                            "verdict_count": actual_verdict_count,
                        },
                    )

                # Resume with None to continue from checkpoint
                input_state = None
            else:
                print("No checkpoint found. Starting fresh.")
                input_state = initial_state
        else:
            # Not resuming - check if old checkpoint exists and warn/clear
            state = app.get_state(config)
            if state.values:
                old_iteration = state.values.get('iteration_count', 0)
                print(f">>> Found existing checkpoint at iteration {old_iteration}")
                print(f">>> Starting fresh (use --resume to continue from checkpoint)")
            input_state = initial_state

        # Stream workflow events with iteration extension support
        final_state = None
        current_max = max_iterations

        while True:
            restart_stream = False
            try:
                for event in app.stream(input_state, config):
                    # Event is dict of {node_name: state_updates}
                    for node_name, state_update in event.items():
                        final_state = state_update

                        # Check for errors
                        error = state_update.get("error_message", "")
                        if error:
                            if "MANUAL" in error:
                                print(f"\n[EXIT] {error}")
                                return 0  # Manual exit is not an error
                            elif error.startswith("MAX_ITERATIONS_REACHED:"):
                                # Parse current max from error
                                current_max = int(error.split(":")[1])
                                print(f"\n{'=' * 60}")
                                print(f"WARNING: MAXIMUM ITERATIONS REACHED ({current_max})")
                                print(f"{'=' * 60}")
                                print("\nOptions:")
                                print("[N] Add more iterations (enter any number, e.g., 10 or 50)")
                                print("[S]ave and exit - workflow state preserved for resume")
                                print("[M]anual - exit for manual handling")
                                print()

                                # Test mode: auto-save
                                if os.environ.get("AGENTOS_TEST_MODE") == "1":
                                    choice = "S"
                                    print(f"Your choice: {choice} (TEST MODE - auto-save)")
                                else:
                                    choice = input("Your choice: ").strip().upper()

                                if choice.isdigit():
                                    additional = int(choice)
                                    if additional > 0:
                                        new_max = current_max + additional
                                        print(f"\n>>> Extending limit to {new_max} iterations, resuming...")
                                        # Update state with new max and reset to continue
                                        saved_state = app.get_state(config)
                                        if saved_state.values:
                                            # Reset error and next_node to continue from human edit
                                            app.update_state(
                                                config,
                                                {
                                                    "max_iterations": new_max,
                                                    "error_message": "",
                                                    "next_node": "N2_human_edit",
                                                },
                                            )
                                        current_max = new_max
                                        # Also update recursion_limit
                                        recursion_limit = new_max * 10
                                        config["recursion_limit"] = recursion_limit
                                        # Resume from updated checkpoint
                                        input_state = None
                                        restart_stream = True
                                        break  # Break inner loop
                                    else:
                                        print("Invalid number. Must be > 0.")
                                        return 1
                                elif choice == "S":
                                    print("\n>>> Workflow state saved.")
                                    print(f">>> Resume with: --issue {issue_number} --resume")
                                    return 0
                                elif choice == "M":
                                    return 0
                                else:
                                    print("Invalid choice.")
                                    return 1
                            else:
                                print(f"\n[ERROR] {error}")
                                return 1

                    # Check if we need to restart the stream
                    if restart_stream:
                        break  # Break outer for loop to restart stream

                # If we didn't restart, stream completed normally
                if not restart_stream:
                    break  # Exit while loop

            except KeyboardInterrupt:
                print("\n\n[INTERRUPTED] Workflow interrupted. Use --resume to continue.")
                return 130  # Standard exit code for SIGINT

            except GraphRecursionError:
                # LangGraph recursion limit hit - this shouldn't happen with our settings
                # but handle it gracefully
                print(f"\n{'=' * 60}")
                print(f"WARNING: Graph recursion limit reached ({recursion_limit})")
                print(f"{'=' * 60}")
                print("\nThis usually means an infinite loop in the workflow graph.")
                print("Use --resume to continue after investigating.")
                return 1

    # Check final outcome
    if final_state:
        final_lld_path = final_state.get("final_lld_path", "")
        if final_lld_path:
            # Part 5.1 fix: Read counters from audit directory (ground truth)
            actual_repo_root = repo_root or get_repo_root()
            audit_dir = get_audit_dir(actual_repo_root, issue_number)
            actual_draft_count, actual_verdict_count = count_audit_files(audit_dir)

            print(f"\n{'=' * 60}")
            print(f"SUCCESS: LLD approved and saved!")
            print(f"  Path: {final_lld_path}")
            print(f"  Iterations: {final_state.get('iteration_count', 0)}")
            print(f"  Drafts: {actual_draft_count}")
            print(f"  Verdicts: {actual_verdict_count}")
            print(f"{'=' * 60}\n")
            return 0

        error = final_state.get("error_message", "")
        if error and not error.startswith("MAX_ITERATIONS_REACHED:"):
            print(f"\n[ERROR] {error}")
            return 1

    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="LLD Governance Workflow - Generate and review LLDs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Interactive issue picker
    python tools/run_lld_workflow.py --select

    # Basic usage - generate LLD for issue
    python tools/run_lld_workflow.py --issue 42

    # Rebuild LLD status cache
    python tools/run_lld_workflow.py --audit

    # Auto mode - unattended execution
    python tools/run_lld_workflow.py --issue 42 --auto

    # Mock mode - test without API calls
    python tools/run_lld_workflow.py --issue 42 --mock

    # With context files
    python tools/run_lld_workflow.py --issue 42 --context src/main.py --context docs/spec.md

    # Resume interrupted workflow
    python tools/run_lld_workflow.py --issue 42 --resume

    # Cross-repo usage
    python tools/run_lld_workflow.py --repo /path/to/repo --select
""",
    )

    parser.add_argument(
        "--issue",
        type=int,
        help="GitHub issue number",
    )
    parser.add_argument(
        "--select",
        action="store_true",
        help="Interactive picker for open GitHub issues",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Rebuild lld-status.json from all LLD files",
    )
    parser.add_argument(
        "--context",
        action="append",
        default=[],
        help="Additional context files (can specify multiple)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto mode: skip VS Code, auto-send to Gemini",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Mock mode: use fixtures instead of real APIs",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume interrupted workflow from checkpoint",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=20,
        help="Maximum review iterations (default: 20)",
    )
    parser.add_argument(
        "--repo",
        type=str,
        help="Target repository root (default: auto-detect via git)",
    )

    args = parser.parse_args()

    # Resolve and validate repo root if provided
    repo_root = None
    if args.repo:
        repo_root = Path(args.repo).resolve()
        if not (repo_root / ".git").exists():
            print(f"Error: {repo_root} is not a git repository")
            return 1

    # Handle --audit first
    if args.audit:
        return run_audit(repo_root)

    # Handle --select
    if args.select:
        result = select_issue_interactive(repo_root)
        if result is None:
            print("No issue selected. Exiting.")
            return 0

        issue_number, title = result

        # Post-selection check: verify LLD status
        lld_status = check_lld_status(issue_number, repo_root)
        if lld_status and lld_status.get("status") == "approved":
            print(f"\n>>> Issue #{issue_number} already has an approved LLD at:")
            print(f"    {lld_status.get('lld_path')}")
            confirm = input("\nCreate new LLD anyway? [y/N]: ").strip().lower()
            if confirm != "y":
                return 0

        # Inject existing draft as context if present
        context_files = args.context or []
        if lld_status and lld_status.get("status") == "draft":
            draft_path = lld_status.get("lld_path")
            if draft_path:
                print(f"\n>>> Found existing draft LLD, injecting as context:")
                print(f"    {draft_path}")
                context_files.insert(0, draft_path)

        return run_workflow(
            issue_number=issue_number,
            context_files=context_files,
            auto_mode=args.auto,
            mock_mode=args.mock,
            resume=args.resume,
            max_iterations=args.max_iterations,
            repo_root=repo_root,
        )

    # Require --issue if not --select or --audit
    if not args.issue:
        parser.error("one of the arguments --issue --select --audit is required")

    return run_workflow(
        issue_number=args.issue,
        context_files=args.context,
        auto_mode=args.auto,
        mock_mode=args.mock,
        resume=args.resume,
        max_iterations=args.max_iterations,
        repo_root=repo_root,
    )


if __name__ == "__main__":
    sys.exit(main())
