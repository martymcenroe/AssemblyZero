"""N9 Cleanup Node for TDD Testing Workflow.

Issue #180: N9 Cleanup Node - Worktree Removal, Lineage Archival, and Learning Summary

Orchestrates three cleanup tasks:
1. Check PR merge status and remove worktree if merged
2. Generate learning summary in active lineage directory
3. Archive lineage from active/ to done/ ONLY if PR is merged
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from assemblyzero.workflows.testing.nodes.cleanup_helpers import (
    archive_lineage,
    build_learning_summary,
    check_pr_merged,
    delete_local_branch,
    get_worktree_branch,
    remove_worktree,
    render_learning_summary,
    write_learning_summary,
)

logger = logging.getLogger(__name__)


def _posix_path_str(path: Path) -> str:
    """Convert a Path to a forward-slash string for cross-platform consistency."""
    return path.as_posix()


def route_after_document(state: dict[str, Any]) -> str:
    """Conditional routing from N8 to N9 or END.

    Returns "N9_cleanup" if state has valid issue_number,
    otherwise returns "end".
    """
    issue_number = state.get("issue_number")
    if issue_number:
        logger.info("[N9] Routing to N9_cleanup (issue_number=%s)", issue_number)
        return "N9_cleanup"
    logger.info("[N9] No issue_number — routing to end")
    return "end"


def cleanup(state: dict[str, Any]) -> dict[str, Any]:
    """N9: Post-implementation cleanup node.

    Orchestrates three cleanup tasks:
    1. Check PR merge status and remove worktree if merged
    2. Generate learning summary in active lineage directory
    3. Archive lineage from active/ to done/ ONLY if PR is merged

    If PR is not merged, the learning summary is written into active/
    so developers can inspect it during iteration.

    Returns updated state fields: pr_merged, learning_summary_path,
    cleanup_skipped_reason.
    """
    logger.info("[N9] Starting cleanup node")

    # Extract state
    pr_url = state.get("pr_url", "")
    worktree_path = state.get("worktree_path", "")
    issue_number = state.get("issue_number", 0)
    repo_root_str = state.get("repo_root", "")
    final_coverage = state.get("final_coverage", 0.0)
    target_coverage = state.get("target_coverage", 0.0)
    outcome = state.get("outcome", "UNKNOWN")

    # Initialize return fields
    pr_merged = False
    learning_summary_path = ""
    cleanup_skipped_reason = ""

    repo_root = Path(repo_root_str) if repo_root_str else Path.cwd()

    # === 1. WORKTREE CLEANUP ===
    if pr_url:
        try:
            pr_merged = check_pr_merged(pr_url)
            logger.info("[N9] PR merge status: %s", "MERGED" if pr_merged else "NOT MERGED")

            if pr_merged and worktree_path:
                try:
                    branch = get_worktree_branch(worktree_path)
                    remove_worktree(worktree_path)
                    if branch:
                        delete_local_branch(branch)
                    logger.info("[N9] Worktree and branch cleaned up")
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                    logger.warning("[N9] Worktree cleanup failed: %s", exc)
            elif not pr_merged:
                cleanup_skipped_reason = "PR not yet merged"
                logger.info("[N9] Skipping worktree removal — PR not merged")
            else:
                logger.info("[N9] PR merged but no worktree_path in state")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as exc:
            logger.warning("[N9] PR merge check failed: %s", exc)
            cleanup_skipped_reason = f"PR merge check failed: {exc}"
    else:
        cleanup_skipped_reason = "No PR URL in state"
        logger.info("[N9] No PR URL — skipping worktree cleanup")

    # === 2. LEARNING SUMMARY (generated in active/ first) ===
    active_dir = (
        repo_root / "docs" / "lineage" / "active" / f"{issue_number}-testing"
    )

    if active_dir.exists():
        try:
            summary_data = build_learning_summary(
                active_dir, issue_number, outcome, final_coverage, target_coverage
            )
            markdown = render_learning_summary(summary_data)
            write_learning_summary(active_dir, markdown)
            logger.info("[N9] Learning summary written to active/")
        except Exception as exc:
            logger.warning("[N9] Learning summary generation failed: %s", exc)
    else:
        logger.info("[N9] No active lineage directory found — skipping summary generation")

    # === 3. LINEAGE ARCHIVAL (only if PR merged) ===
    if active_dir.exists() and pr_merged:
        try:
            done_dir = archive_lineage(repo_root, issue_number)
            if done_dir:
                learning_summary_path = _posix_path_str(
                    done_dir / "learning-summary.md"
                )
                logger.info("[N9] Lineage archived to done/")
            else:
                logger.warning("[N9] archive_lineage returned None unexpectedly")
        except Exception as exc:
            logger.warning("[N9] Lineage archival failed: %s", exc)
    elif active_dir.exists() and not pr_merged:
        learning_summary_path = _posix_path_str(
            active_dir / "learning-summary.md"
        )
        logger.info(
            "[N9] Lineage kept in active/ (PR not merged) — summary available for inspection"
        )
    else:
        logger.info("[N9] No lineage directory available — skipping archival")

    logger.info("[N9] Cleanup complete")

    return {
        "pr_merged": pr_merged,
        "learning_summary_path": learning_summary_path,
        "cleanup_skipped_reason": cleanup_skipped_reason,
    }