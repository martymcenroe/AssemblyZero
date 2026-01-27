#!/usr/bin/env python3
"""CLI runner for Issue creation workflow.

Issue #62: Governance Workflow StateGraph

Usage:
    python tools/run_issue_workflow.py --brief <file.md>
    python tools/run_issue_workflow.py --resume <file.md>

Options:
    --brief <file>    Path to ideation notes (starts new workflow)
    --resume <file>   Resume interrupted workflow by brief filename
    --help            Show this help message
"""

import argparse
import sys
from pathlib import Path

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

    Returns:
        Path to ~/.agentos/issue_workflow.db
    """
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
    print("[A]bort - exit cleanly")
    print()

    while True:
        choice = input("Your choice [R/N/A]: ").strip().upper()
        if choice == "R":
            return (SlugCollisionChoice.RESUME, "")
        elif choice == "N":
            new_slug = input("Enter new slug: ").strip()
            if not new_slug:
                print("Slug cannot be empty.")
                continue
            return (SlugCollisionChoice.NEW_NAME, new_slug)
        elif choice == "A":
            return (SlugCollisionChoice.ABORT, "")
        else:
            print("Invalid choice. Please enter R, N, or A.")


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

        if choice == SlugCollisionChoice.NEW_NAME:
            # Check new slug doesn't collide
            while slug_exists(new_slug, repo_root):
                print(f"Slug '{new_slug}' also exists!")
                choice, new_slug = prompt_slug_collision(new_slug)
                if choice == SlugCollisionChoice.ABORT:
                    return 0
                if choice == SlugCollisionChoice.RESUME:
                    return run_resume_workflow(brief_file)

            slug = new_slug

    # Build and compile workflow
    workflow = build_issue_workflow()

    # Use SQLite for persistence
    db_path = get_checkpoint_db_path()
    with SqliteSaver.from_conn_string(f"sqlite:///{db_path}") as memory:
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
            "user_feedback": "",
            "next_node": "",
            "issue_number": 0,
            "issue_url": "",
            "error_message": "",
        }

        # Use brief filename as thread ID for checkpointing
        config = {"configurable": {"thread_id": slug}}

        print(f"\n{'=' * 60}")
        print("Issue Creation Workflow")
        print(f"{'=' * 60}")
        print(f"Brief: {brief_file}")
        print(f"Slug: {slug}")
        print(f"{'=' * 60}\n")

        # Run the workflow
        try:
            final_state = None
            for event in app.stream(initial_state, config):
                # Process each node's output
                for node_name, node_output in event.items():
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

        except KeyboardInterrupt:
            print("\n\n>>> Interrupted by user. Workflow state saved.")
            print(f">>> Resume with: python tools/run_issue_workflow.py --resume {brief_file}")
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
    with SqliteSaver.from_conn_string(f"sqlite:///{db_path}") as memory:
        app = workflow.compile(checkpointer=memory)

        # Use brief filename as thread ID
        config = {"configurable": {"thread_id": slug}}

        print(f"\n{'=' * 60}")
        print("Resuming Issue Creation Workflow")
        print(f"{'=' * 60}")
        print(f"Slug: {slug}")
        print(f"{'=' * 60}\n")

        try:
            # Get current state from checkpoint
            state = app.get_state(config)

            if state.values:
                print(f">>> Resuming from iteration {state.values.get('iteration_count', 0)}")
                print(f">>> Drafts: {state.values.get('draft_count', 0)}")
                print(f">>> Verdicts: {state.values.get('verdict_count', 0)}")

            # Continue the workflow
            for event in app.stream(None, config):
                for node_name, node_output in event.items():
                    if node_output.get("error_message"):
                        error = node_output["error_message"]
                        if "ABORTED" in error or "MANUAL" in error:
                            print(f"\n>>> Workflow stopped: {error}")
                            return 0

            # Check for success
            final_state = app.get_state(config)
            if final_state.values and final_state.values.get("issue_url"):
                print(f"\n{'=' * 60}")
                print("SUCCESS!")
                print(f"Issue: {final_state.values.get('issue_url')}")
                print(f"{'=' * 60}")
                return 0

        except KeyboardInterrupt:
            print("\n\n>>> Interrupted by user. Workflow state saved.")
            print(f">>> Resume with: python tools/run_issue_workflow.py --resume {brief_file}")
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
    python tools/run_issue_workflow.py --resume my-feature-notes.md
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
