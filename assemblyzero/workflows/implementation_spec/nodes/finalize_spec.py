"""N6: Finalize Spec node for Implementation Spec Workflow.

Issue #304: Implementation Readiness Review Workflow (LLD -> Implementation Spec)

Writes the approved Implementation Spec to docs/lld/drafts/ with embedded
review metadata. This is the terminal node in the happy path:

    N0 -> N1 -> N2 -> N3 -> N4 -> N5 -> N6 -> END

This node:
- Adds a review log section to the spec with verdict, iteration count, and date
- Writes the final spec to docs/lld/drafts/spec-{issue_number}.md (atomic:
  write to temp file first, then rename on success)
- Saves the final spec to the audit trail
- Returns the spec_path for downstream consumers

This node populates:
- spec_path: Final output path for the approved spec
- error_message: "" on success, error text on failure
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from assemblyzero.workflows.requirements.audit import (
    move_lineage_to_done,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState


# =============================================================================
# Constants
# =============================================================================

# Output directory relative to repo root (LLD Section 2.5 step 9)
SPEC_OUTPUT_DIR = Path("docs/lld/drafts")

# Minimum spec size to be considered valid for finalization
MIN_SPEC_SIZE = 100


# =============================================================================
# Main Node
# =============================================================================


def finalize_spec(state: ImplementationSpecState) -> dict[str, Any]:
    """N6: Write final spec to docs/lld/drafts/ directory.

    Issue #304: Implementation Readiness Review Workflow

    Steps:
    1. Guard against empty/invalid spec drafts
    2. Guard against non-APPROVED verdicts (safety check)
    3. Add review log metadata to spec
    4. Generate output filename
    5. Write spec atomically (temp file -> rename)
    6. Save to audit trail
    7. Return state updates with spec_path

    Args:
        state: Current workflow state. Requires:
            - spec_draft: Approved Implementation Spec markdown (from N2)
            - review_verdict: Must be "APPROVED" (from N5)
            - issue_number: GitHub issue number
            - review_iteration: Number of review rounds completed
            - repo_root: Target repository root path

    Returns:
        Dict with state field updates:
        - spec_path: Path to the finalized spec file
        - error_message: "" on success, error text on failure
    """
    # Extract state
    spec_draft = state.get("spec_draft", "")
    review_verdict = state.get("review_verdict", "BLOCKED")
    review_feedback = state.get("review_feedback", "")
    issue_number = state.get("issue_number", 0)
    review_iteration = state.get("review_iteration", 0)
    repo_root_str = state.get("repo_root", "")

    print(f"\n[N6] Finalizing Implementation Spec for issue #{issue_number}...")

    # -------------------------------------------------------------------------
    # GUARD: Spec draft must be non-empty
    # -------------------------------------------------------------------------
    if not spec_draft or not spec_draft.strip():
        print("    [GUARD] BLOCKED: Spec draft is empty")
        return {
            "spec_path": "",
            "error_message": "GUARD: Cannot finalize empty spec draft",
        }

    if len(spec_draft) < MIN_SPEC_SIZE:
        print(
            f"    [GUARD] BLOCKED: Spec draft too short "
            f"({len(spec_draft)} chars < {MIN_SPEC_SIZE} minimum)"
        )
        return {
            "spec_path": "",
            "error_message": (
                f"GUARD: Spec draft too short ({len(spec_draft)} chars). "
                f"Minimum is {MIN_SPEC_SIZE} chars."
            ),
        }

    # -------------------------------------------------------------------------
    # GUARD: Verdict must be APPROVED
    # -------------------------------------------------------------------------
    if review_verdict != "APPROVED":
        print(f"    [GUARD] BLOCKED: Verdict is {review_verdict}, not APPROVED")
        return {
            "spec_path": "",
            "error_message": (
                f"GUARD: Cannot finalize spec with verdict '{review_verdict}'. "
                "Only APPROVED specs can be finalized."
            ),
        }

    # -------------------------------------------------------------------------
    # GUARD: Issue number must be valid
    # -------------------------------------------------------------------------
    if not issue_number or issue_number < 1:
        print(f"    [GUARD] BLOCKED: Invalid issue number: {issue_number}")
        return {
            "spec_path": "",
            "error_message": f"GUARD: Invalid issue number: {issue_number}",
        }

    # -------------------------------------------------------------------------
    # Resolve repo root
    # -------------------------------------------------------------------------
    if repo_root_str:
        repo_root = Path(repo_root_str)
    else:
        repo_root = Path(".")

    # -------------------------------------------------------------------------
    # Add review log to spec
    # -------------------------------------------------------------------------
    finalized_content = _add_review_log(
        spec_draft=spec_draft,
        review_verdict=review_verdict,
        review_feedback=review_feedback,
        review_iteration=review_iteration,
        issue_number=issue_number,
    )

    # -------------------------------------------------------------------------
    # Generate output path
    # -------------------------------------------------------------------------
    spec_filename = generate_spec_filename(issue_number)
    output_dir = repo_root / SPEC_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    spec_path = output_dir / spec_filename

    # -------------------------------------------------------------------------
    # Atomic write: temp file then rename
    # -------------------------------------------------------------------------
    try:
        # Write to temp file in the same directory (same filesystem for rename)
        fd, tmp_path_str = tempfile.mkstemp(
            suffix=".md",
            prefix=f".spec-{issue_number:04d}-",
            dir=str(output_dir),
        )
        tmp_path = Path(tmp_path_str)
        # Close the fd from mkstemp BEFORE writing — Windows locks
        # the file while the original fd is open (WinError 32).
        import os
        os.close(fd)
        try:
            tmp_path.write_text(finalized_content, encoding="utf-8")
            # Atomic rename (replace if exists)
            tmp_path.replace(spec_path)
        except Exception:
            # Clean up temp file on failure
            if tmp_path.exists():
                tmp_path.unlink()
            raise
    except OSError as e:
        print(f"    ERROR: Failed to write spec file: {e}")
        return {
            "spec_path": "",
            "error_message": f"Failed to write spec file: {e}",
        }

    # -------------------------------------------------------------------------
    # Output verification guard
    # -------------------------------------------------------------------------
    if not spec_path.exists():
        print(f"    ERROR: Spec file not created at {spec_path}")
        return {
            "spec_path": "",
            "error_message": f"Spec file not created at {spec_path}",
        }

    print(f"    Saved spec to: {spec_path}")
    print(f"    Spec size: {len(finalized_content)} chars")
    print(f"    Review iterations: {review_iteration}")

    # -------------------------------------------------------------------------
    # Save to audit trail
    # -------------------------------------------------------------------------
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None

    if audit_dir and audit_dir.exists():
        file_num = next_file_number(audit_dir)
        audit_path = save_audit_file(
            audit_dir, file_num, "final-spec.md", finalized_content
        )
        print(f"    Audit trail: {audit_path.name}")

    # Issue #100: Move lineage from active/ to done/
    if audit_dir and audit_dir.exists():
        move_lineage_to_done(audit_dir, repo_root)

    # -------------------------------------------------------------------------
    # Return state updates
    # -------------------------------------------------------------------------
    return {
        "spec_path": str(spec_path),
        "error_message": "",
    }


# =============================================================================
# Helpers
# =============================================================================


def generate_spec_filename(issue_number: int) -> str:
    """Generate filename for the Implementation Spec.

    Follows the convention: spec-{issue_number:04d}-implementation-readiness.md
    Uses 4-digit zero-padded issue numbers for consistent sorting.

    Args:
        issue_number: GitHub issue number.

    Returns:
        Filename string (e.g., "spec-0304-implementation-readiness.md").
    """
    return f"spec-{issue_number:04d}-implementation-readiness.md"


def _add_review_log(
    spec_draft: str,
    review_verdict: str,
    review_feedback: str,
    review_iteration: int,
    issue_number: int,
) -> str:
    """Add review log section to the spec.

    Appends a review log at the end of the spec documenting the
    review process: verdict, date, iteration count, and summary
    of any feedback received.

    Args:
        spec_draft: The spec markdown content.
        review_verdict: Final verdict (should be "APPROVED").
        review_feedback: Review feedback text.
        review_iteration: Number of review rounds completed.
        issue_number: GitHub issue number.

    Returns:
        Spec content with appended review log section.
    """
    review_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    review_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build review log section
    log_lines: list[str] = [
        "",
        "---",
        "",
        "## Review Log",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Issue | #{issue_number} |",
        f"| Verdict | {review_verdict} |",
        f"| Date | {review_date} |",
        f"| Iterations | {review_iteration} |",
        f"| Finalized | {review_time} |",
        "",
    ]

    # Add feedback summary if present (truncated for readability)
    if review_feedback and review_feedback.strip():
        feedback_preview = review_feedback.strip()
        # Truncate very long feedback for the review log
        if len(feedback_preview) > 500:
            feedback_preview = feedback_preview[:500] + "..."
        log_lines.extend([
            "### Review Feedback Summary",
            "",
            feedback_preview,
            "",
        ])

    # Ensure spec ends with a newline before appending
    content = spec_draft.rstrip() + "\n"
    content += "\n".join(log_lines)

    # Ensure trailing newline
    if not content.endswith("\n"):
        content += "\n"

    return content