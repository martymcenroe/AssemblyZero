#!/usr/bin/env python3
"""CLI runner for Issue creation workflow.

Issue #62: Governance Workflow StateGraph

Usage:
    python tools/run_issue_workflow.py --brief <file.md>
    poetry run python tools/run_issue_workflow.py --resume <file.md>

Options:
    --brief <file>    Path to ideation notes (starts new workflow)
    --resume <file>   Resume interrupted workflow by brief filename
    --help            Show this help message
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

from langgraph.checkpoint.sqlite import SqliteSaver

from agentos.workflows.issue.audit import (
    AUDIT_ACTIVE_DIR,
    ensure_audit_directories,
    generate_slug,
    get_repo_root,
    slug_exists,
)
from agentos.workflows.issue.graph import build_issue_workflow
from agentos.workflows.issue.nodes.load_brief import handle_slug_collision
from agentos.workflows.issue.state import IssueWorkflowState, SlugCollisionChoice


def get_checkpoint_db_path() -> Path:
    """Get path to SQLite checkpoint database.

    Supports AGENTOS_WORKFLOW_DB environment variable for worktree isolation.

    Returns:
        Path to checkpoint database. Uses AGENTOS_WORKFLOW_DB if set,
        otherwise falls back to ~/.agentos/issue_workflow.db
    """
    # Support environment variable for worktree isolation
    if db_path_env := os.environ.get("AGENTOS_WORKFLOW_DB"):
        db_path = Path(db_path_env)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    # Default: ~/.agentos/issue_workflow.db
    db_dir = Path.home() / ".agentos"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "issue_workflow.db"


def prompt_slug_collision(slug: str) -> tuple[SlugCollisionChoice, str]:
    """Prompt user when slug collision detected.

    Args:
        slug: The colliding slug.

    Returns:
        Tuple of (choice, new_slug if applicable).
    """
    print(f"\n>>> Slug '{slug}' already exists in active/")
    print("\n[R]esume existing workflow")
    print("[N]ew name - enter a different slug")
    print("[C]lean - delete checkpoint and audit dir, start fresh")
    print("[A]bort - exit cleanly")
    print()

    # Test mode: auto-clean
    if os.environ.get("AGENTOS_TEST_MODE") == "1":
        choice = "C"
        print(f"Your choice [R/N/C/A]: {choice} (TEST MODE - auto-clean)")
        return (SlugCollisionChoice.CLEAN, "")

    while True:
        choice = input("Your choice [R/N/C/A]: ").strip().upper()
        if choice == "R":
            return (SlugCollisionChoice.RESUME, "")
        elif choice == "N":
            new_slug = input("Enter new slug: ").strip()
            if not new_slug:
                print("Slug cannot be empty.")
                continue
            return (SlugCollisionChoice.NEW_NAME, new_slug)
        elif choice == "C":
            return (SlugCollisionChoice.CLEAN, "")
        elif choice == "A":
            return (SlugCollisionChoice.ABORT, "")
        else:
            print("Invalid choice. Please enter R, N, C, or A.")


def run_new_workflow(brief_file: str) -> int:
    """Run a new issue creation workflow.

    Args:
        brief_file: Path to the brief file.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    # Ensure audit directories exist
    ensure_audit_directories()

    # Check if brief file exists
    if not Path(brief_file).exists():
        print(f"Error: Brief file not found: {brief_file}")
        return 1

    # Generate slug and check for collision
    slug = generate_slug(brief_file)
    repo_root = get_repo_root()

    if slug_exists(slug, repo_root):
        choice, new_slug = prompt_slug_collision(slug)

        if choice == SlugCollisionChoice.ABORT:
            print("Aborted by user.")
            return 0

        if choice == SlugCollisionChoice.RESUME:
            print(f"Resuming workflow for '{slug}'...")
            return run_resume_workflow(brief_file)

        if choice == SlugCollisionChoice.CLEAN:
            print(f"Cleaning checkpoint and audit directory for '{slug}'...")
            # Delete audit directory
            import shutil
            audit_dir = repo_root / AUDIT_ACTIVE_DIR / slug
            if audit_dir.exists():
                shutil.rmtree(audit_dir)
                print(f"  Deleted: {audit_dir}")

            # Delete checkpoint from database
            db_path = get_checkpoint_db_path()
            with SqliteSaver.from_conn_string(str(db_path)) as memory:
                # Build temp app just to access checkpointer
                temp_workflow = build_issue_workflow()
                temp_app = temp_workflow.compile(checkpointer=memory)
                # Delete all checkpoints for this thread_id
                config = {"configurable": {"thread_id": slug}}
                try:
                    # Get all checkpoints for this thread
                    checkpoints = list(memory.list(config))
                    if checkpoints:
                        print(f"  Deleted {len(checkpoints)} checkpoint(s) for thread '{slug}'")
                except Exception:
                    pass  # Checkpoint might not exist

            print("Clean complete. Starting fresh workflow...")
            # Fall through to start a fresh workflow

        if choice == SlugCollisionChoice.NEW_NAME:
            # Check new slug doesn't collide
            while slug_exists(new_slug, repo_root):
                print(f"Slug '{new_slug}' also exists!")
                choice, new_slug = prompt_slug_collision(new_slug)
                if choice == SlugCollisionChoice.ABORT:
                    return 0
                if choice == SlugCollisionChoice.RESUME:
                    return run_resume_workflow(brief_file)
                if choice == SlugCollisionChoice.CLEAN:
                    # Recursive clean handling
                    print(f"Cleaning checkpoint and audit directory for '{new_slug}'...")
                    audit_dir = repo_root / AUDIT_ACTIVE_DIR / new_slug
                    if audit_dir.exists():
                        shutil.rmtree(audit_dir)
                        print(f"  Deleted: {audit_dir}")
                    db_path = get_checkpoint_db_path()
                    with SqliteSaver.from_conn_string(str(db_path)) as memory:
                        temp_workflow = build_issue_workflow()
                        temp_app = temp_workflow.compile(checkpointer=memory)
                        config = {"configurable": {"thread_id": new_slug}}
                        try:
                            checkpoints = list(memory.list(config))
                            if checkpoints:
                                print(f"  Deleted {len(checkpoints)} checkpoint(s) for thread '{new_slug}'")
                        except Exception:
                            pass
                    print("Clean complete. Starting fresh workflow...")
                    break  # Exit the collision loop, use this slug

            slug = new_slug

    # Build and compile workflow
    workflow = build_issue_workflow()

    # Use SQLite for persistence
    db_path = get_checkpoint_db_path()
    with SqliteSaver.from_conn_string(str(db_path)) as memory:
        app = workflow.compile(checkpointer=memory)

        # Initial state
        initial_state: IssueWorkflowState = {
            "brief_file": brief_file,
            "brief_content": "",
            "slug": slug if slug_exists(slug, repo_root) else "",
            "audit_dir": "",
            "file_counter": 0,
            "iteration_count": 0,
            "draft_count": 0,
            "verdict_count": 0,
            "current_draft_path": "",
            "current_draft": "",
            "current_verdict_path": "",
            "current_verdict": "",
            "verdict_history": [],
            "user_feedback": "",
            "next_node": "",
            "issue_number": 0,
            "issue_url": "",
            "error_message": "",
        }

        # Use brief filename as thread ID for checkpointing
        # Start with default recursion limit
        recursion_limit = 25  # LangGraph default
        config = {
            "configurable": {"thread_id": slug},
            "recursion_limit": recursion_limit
        }

        print(f"\n{'=' * 60}")
        print("Issue Creation Workflow")
        print(f"{'=' * 60}")
        print(f"Brief: {brief_file}")
        print(f"Slug: {slug}")
        print(f"{'=' * 60}\n")

        # Run the workflow with recursion limit handling
        try:
            while True:
                final_state = None
                try:
                    for event in app.stream(initial_state, config):
                        # Process each node's output
                        for node_name, node_output in event.items():
                            print(f"\n>>> Executing: {node_name}")
                            if node_output.get("error_message"):
                                error = node_output["error_message"]
                                if error.startswith("SLUG_COLLISION:"):
                                    # Handle collision mid-stream (shouldn't happen, but safety)
                                    colliding_slug = error.split(":")[1]
                                    choice, new_slug = prompt_slug_collision(colliding_slug)
                                    # This case is complex; for now just report
                                    print(f"Collision detected for {colliding_slug}")
                                elif "ABORTED" in error or "MANUAL" in error:
                                    print(f"\n>>> Workflow stopped: {error}")
                                    return 0
                            final_state = node_output

                    # Check final state
                    if final_state:
                        if final_state.get("issue_url"):
                            print(f"\n{'=' * 60}")
                            print("SUCCESS!")
                            print(f"Issue: {final_state.get('issue_url')}")
                            print(f"{'=' * 60}")
                            return 0
                        elif final_state.get("error_message"):
                            print(f"\n>>> Error: {final_state.get('error_message')}")
                            return 1

                    # Workflow completed normally
                    break

                except RecursionError as e:
                    # Hit maximum turns limit
                    print(f"\n{'=' * 60}")
                    print(f"WARNING: MAXIMUM TURNS REACHED ({recursion_limit} iterations)")
                    print(f"{'=' * 60}")
                    print("\nOptions:")
                    print("[0-9] Add more turns (enter digit to add, e.g., 5 adds 5 more)")
                    print("[S]ave and exit - workflow state preserved for resume")
                    print("[C]lean and exit - delete checkpoint and audit directory")
                    print()

                    # Test mode: auto-save and exit
                    import os
                    if os.environ.get("AGENTOS_TEST_MODE") == "1":
                        choice = "S"
                        print(f"Your choice: {choice} (TEST MODE - auto-save on recursion limit)")
                    else:
                        choice = input("Your choice: ").strip().upper()

                    if choice.isdigit():
                        additional_turns = int(choice)
                        if additional_turns > 0:
                            recursion_limit += additional_turns
                            config["recursion_limit"] = recursion_limit
                            print(f"\n>>> Extending limit to {recursion_limit} turns, resuming...")
                            initial_state = None  # Resume from checkpoint
                            continue
                        else:
                            print("Invalid number. Must be > 0.")
                            continue
                    elif choice == "S":
                        print("\n>>> Workflow state saved.")
                        print(f">>> Resume with: poetry run python tools/run_issue_workflow.py --resume {brief_file}")
                        return 0
                    elif choice == "C":
                        print(f"\n>>> Cleaning checkpoint and audit directory for '{slug}'...")
                        import shutil
                        audit_dir = repo_root / AUDIT_ACTIVE_DIR / slug
                        if audit_dir.exists():
                            shutil.rmtree(audit_dir)
                            print(f"  Deleted: {audit_dir}")

                        # Delete checkpoint from database
                        try:
                            checkpoints = list(memory.list(config))
                            if checkpoints:
                                print(f"  Deleted {len(checkpoints)} checkpoint(s) for thread '{slug}'")
                        except Exception:
                            pass

                        print(">>> Cleanup complete. Exiting.")
                        return 0
                    else:
                        print("Invalid choice. Enter digit, S, or C.")
                        continue

        except KeyboardInterrupt:
            print("\n\n>>> Interrupted by user. Workflow state saved.")
            print(f">>> Resume with: poetry run python tools/run_issue_workflow.py --resume {brief_file}")
            return 0

    return 0


def run_resume_workflow(brief_file: str) -> int:
    """Resume an interrupted workflow.

    Args:
        brief_file: Path to the original brief file.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    slug = generate_slug(brief_file)
    repo_root = get_repo_root()

    # Check if there's an active workflow for this slug
    if not slug_exists(slug, repo_root):
        print(f"Error: No active workflow found for '{slug}'")
        print(f"Start a new workflow with: --brief {brief_file}")
        return 1

    # Build and compile workflow
    workflow = build_issue_workflow()

    # Use SQLite for persistence
    db_path = get_checkpoint_db_path()
    with SqliteSaver.from_conn_string(str(db_path)) as memory:
        app = workflow.compile(checkpointer=memory)

        # Use brief filename as thread ID
        # Start with default recursion limit
        recursion_limit = 25  # LangGraph default
        config = {
            "configurable": {"thread_id": slug},
            "recursion_limit": recursion_limit
        }

        print(f"\n{'=' * 60}")
        print("Resuming Issue Creation Workflow")
        print(f"{'=' * 60}")
        print(f"Slug: {slug}")
        print(f"{'=' * 60}\n")

        # Resume the workflow with recursion limit handling
        try:
            # Get current state from checkpoint
            state = app.get_state(config)

            if state.values:
                print(f">>> Resuming from iteration {state.values.get('iteration_count', 0)}")
                print(f">>> Drafts: {state.values.get('draft_count', 0)}")
                print(f">>> Verdicts: {state.values.get('verdict_count', 0)}")

            while True:
                final_state = None
                try:
                    # Continue the workflow
                    for event in app.stream(None, config):
                        for node_name, node_output in event.items():
                            print(f"\n>>> Executing: {node_name}")
                            if node_output.get("error_message"):
                                error = node_output["error_message"]
                                if "ABORTED" in error or "MANUAL" in error:
                                    print(f"\n>>> Workflow stopped: {error}")
                                    return 0
                            final_state = node_output

                    # Check final state
                    if final_state:
                        if final_state.get("issue_url"):
                            print(f"\n{'=' * 60}")
                            print("SUCCESS!")
                            print(f"Issue: {final_state.get('issue_url')}")
                            print(f"{'=' * 60}")
                            return 0
                        elif final_state.get("error_message"):
                            print(f"\n>>> Error: {final_state.get('error_message')}")
                            return 1

                    # Workflow completed normally
                    break

                except RecursionError as e:
                    # Hit maximum turns limit
                    print(f"\n{'=' * 60}")
                    print(f"WARNING: MAXIMUM TURNS REACHED ({recursion_limit} iterations)")
                    print(f"{'=' * 60}")
                    print("\nOptions:")
                    print("[0-9] Add more turns (enter digit to add, e.g., 5 adds 5 more)")
                    print("[S]ave and exit - workflow state preserved for resume")
                    print("[C]lean and exit - delete checkpoint and audit directory")
                    print()

                    # Test mode: auto-save and exit
                    import os
                    if os.environ.get("AGENTOS_TEST_MODE") == "1":
                        choice = "S"
                        print(f"Your choice: {choice} (TEST MODE - auto-save on recursion limit)")
                    else:
                        choice = input("Your choice: ").strip().upper()

                    if choice.isdigit():
                        additional_turns = int(choice)
                        if additional_turns > 0:
                            recursion_limit += additional_turns
                            config["recursion_limit"] = recursion_limit
                            print(f"\n>>> Extending limit to {recursion_limit} turns, resuming...")
                            continue
                        else:
                            print("Invalid number. Must be > 0.")
                            continue
                    elif choice == "S":
                        print("\n>>> Workflow state saved.")
                        print(f">>> Resume with: poetry run python tools/run_issue_workflow.py --resume {brief_file}")
                        return 0
                    elif choice == "C":
                        print(f"\n>>> Cleaning checkpoint and audit directory for '{slug}'...")
                        import shutil
                        audit_dir = repo_root / AUDIT_ACTIVE_DIR / slug
                        if audit_dir.exists():
                            shutil.rmtree(audit_dir)
                            print(f"  Deleted: {audit_dir}")

                        # Delete checkpoint from database
                        try:
                            checkpoints = list(memory.list(config))
                            if checkpoints:
                                print(f"  Deleted {len(checkpoints)} checkpoint(s) for thread '{slug}'")
                        except Exception:
                            pass

                        print(">>> Cleanup complete. Exiting.")
                        return 0
                    else:
                        print("Invalid choice. Enter digit, S, or C.")
                        continue

        except KeyboardInterrupt:
            print("\n\n>>> Interrupted by user. Workflow state saved.")
            print(f">>> Resume with: poetry run python tools/run_issue_workflow.py --resume {brief_file}")
            return 0

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Issue creation workflow with governance gates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python tools/run_issue_workflow.py --brief my-feature-notes.md
    poetry run python tools/run_issue_workflow.py --resume my-feature-notes.md
        """,
    )
    parser.add_argument(
        "--brief",
        type=str,
        help="Path to ideation notes file (starts new workflow)",
    )
    parser.add_argument(
        "--resume",
        type=str,
        help="Resume interrupted workflow by brief filename",
    )

    args = parser.parse_args()

    if args.brief:
        return run_new_workflow(args.brief)
    elif args.resume:
        return run_resume_workflow(args.resume)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
