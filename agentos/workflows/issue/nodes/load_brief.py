"""N0: Load Brief node for Issue creation workflow.

Issue #62: Governance Workflow StateGraph

Loads user's ideation notes from --brief argument, creates audit directory,
and handles slug collision with R/N/A prompt.
"""

from pathlib import Path
from typing import Any

from agentos.workflows.issue.audit import (
    create_audit_dir,
    generate_slug,
    get_repo_root,
    next_file_number,
    save_audit_file,
    slug_exists,
)
from agentos.workflows.issue.state import IssueWorkflowState, SlugCollisionChoice


def load_brief(state: IssueWorkflowState) -> dict[str, Any]:
    """N0: Load user's brief file and create audit directory.

    Steps:
    1. Read brief file from state["brief_file"]
    2. Generate slug from filename
    3. Check for slug collision - prompt R/N/A if exists
    4. Create docs/audit/active/{slug}/ directory
    5. Copy brief to 001-brief.md
    6. Initialize counters

    Args:
        state: Current workflow state with brief_file set.

    Returns:
        dict with: brief_content, slug, audit_dir, file_counter,
                   iteration_count, draft_count, verdict_count

    Raises:
        FileNotFoundError: If brief file doesn't exist.
        SlugCollisionError: If user aborts on collision (handled by caller).
    """
    brief_file = state.get("brief_file", "")

    if not brief_file:
        return {
            "error_message": "No brief file specified. Use --brief <filename>",
        }

    brief_path = Path(brief_file)
    if not brief_path.exists():
        return {
            "error_message": f"Brief file not found: {brief_file}",
        }

    # Load brief content
    brief_content = brief_path.read_text(encoding="utf-8")

    # Generate slug from filename
    slug = generate_slug(brief_file)

    if not slug:
        return {
            "error_message": f"Could not generate valid slug from: {brief_file}",
        }

    # Check for slug collision
    repo_root = get_repo_root()
    if slug_exists(slug, repo_root):
        # Collision detected - this will be handled by the graph's
        # interrupt mechanism. Return state indicating collision.
        return {
            "brief_content": brief_content,
            "slug": slug,
            "error_message": f"SLUG_COLLISION:{slug}",
        }

    # Create audit directory
    audit_dir = create_audit_dir(slug, repo_root)

    # Save brief as 001-brief.md
    file_counter = 1
    save_audit_file(audit_dir, file_counter, "brief.md", brief_content)

    return {
        "brief_content": brief_content,
        "slug": slug,
        "audit_dir": str(audit_dir),
        "file_counter": file_counter,
        "iteration_count": 0,
        "draft_count": 0,
        "verdict_count": 0,
        "error_message": "",
    }


def handle_slug_collision(
    state: IssueWorkflowState,
    choice: SlugCollisionChoice,
    new_slug: str | None = None,
) -> dict[str, Any]:
    """Handle slug collision based on user choice.

    Called by the CLI when slug collision is detected.

    Args:
        state: Current workflow state.
        choice: User's choice (R/N/A).
        new_slug: New slug if choice is NEW_NAME.

    Returns:
        Updated state dict.
    """
    brief_content = state.get("brief_content", "")
    original_slug = state.get("slug", "")

    if choice == SlugCollisionChoice.ABORT:
        return {
            "error_message": "ABORTED:User chose to abort on slug collision",
        }

    if choice == SlugCollisionChoice.RESUME:
        # Return state indicating resume is needed
        return {
            "error_message": f"RESUME:{original_slug}",
        }

    if choice == SlugCollisionChoice.NEW_NAME:
        if not new_slug:
            return {
                "error_message": "No new slug provided",
            }

        # Validate new slug doesn't collide
        repo_root = get_repo_root()
        if slug_exists(new_slug, repo_root):
            return {
                "error_message": f"SLUG_COLLISION:{new_slug}",
            }

        # Create audit directory with new slug
        audit_dir = create_audit_dir(new_slug, repo_root)

        # Save brief as 001-brief.md
        file_counter = 1
        save_audit_file(audit_dir, file_counter, "brief.md", brief_content)

        return {
            "slug": new_slug,
            "audit_dir": str(audit_dir),
            "file_counter": file_counter,
            "iteration_count": 0,
            "draft_count": 0,
            "verdict_count": 0,
            "error_message": "",
        }

    return {"error_message": f"Unknown choice: {choice}"}
