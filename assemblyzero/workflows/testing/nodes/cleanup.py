"""N9 Cleanup Node for TDD Testing Workflow.

Issue #180: N9 Cleanup Node - Worktree Removal, Lineage Archival, and Learning Summary

Orchestrates three cleanup tasks:
1. Check PR merge status and remove worktree if merged
2. Generate learning summary in active lineage directory
3. Archive lineage from active/ to done/ ONLY if PR is merged

#3585 (ADR 0236): every failure here writes an ERROR line and raises
``CleanupError``. They used to be WARNINGs on the way to END. N9's edge to
END is unconditional, so a returned error_message would reach no HALT; the
raise is what stops the run, and the entry point's handler alerts.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

from assemblyzero.workflows.testing.nodes.cleanup_helpers import (
    LineageReadError,
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


class CleanupError(RuntimeError):
    """N9 could not do what it was asked (#3585). Raised, never returned."""


def _failed(message: str) -> CleanupError:
    """Say the failure at ERROR on stderr and in the log; return the error."""
    logger.error("[N9] %s", message)
    print(f"ERROR [N9] {message}", file=sys.stderr, flush=True)
    return CleanupError(message)


def _posix_path_str(path: Path) -> str:
    """Convert a Path to a forward-slash string for cross-platform consistency."""
    return path.as_posix()


def route_after_document(state: dict[str, Any]) -> str:
    """Conditional routing from N8 to N9.

    Returns "N9_cleanup" when the state carries its issue_number. Without one
    N9 cannot name the lineage it cleans, so this raises CleanupError (#3585,
    ledger 0908 line 47): it used to route to END with an INFO line, and the
    run ended without its cleanup. N8's edge map has no HALT (graph.py), so
    raising is what stops the run until it gains one.
    """
    issue_number = state.get("issue_number")
    if issue_number:
        logger.info("[N9] Routing to N9_cleanup (issue_number=%s)", issue_number)
        return "N9_cleanup"
    raise _failed(
        f"N8 finished with no issue_number in the state ({issue_number!r}), so "
        f"N9 cannot clean up the run's worktree or lineage"
    )


def _required(state: dict[str, Any], key: str) -> Any:
    """A state key N9 cannot do without, or CleanupError naming it."""
    value = state.get(key)
    if value is None or value == "":
        raise _failed(f"the state has no {key}, which N9 needs for the learning summary")
    return value


def cleanup(state: dict[str, Any]) -> dict[str, Any]:
    """N9: Post-implementation cleanup node.

    Orchestrates three cleanup tasks:
    1. Check PR merge status and remove worktree if merged
    2. Generate learning summary in active lineage directory
    3. Archive lineage from active/ to done/ ONLY if PR is merged

    If PR is not merged, the learning summary is written into active/
    so developers can inspect it during iteration.

    Returns updated state fields: pr_merged, learning_summary_path,
    cleanup_skipped_reason (why the worktree was left: no PR, or a PR not
    yet merged).

    Raises:
        CleanupError: repo_root, issue_number or a key the summary reads
            (coverage_achieved, coverage_target, workflow_status) is absent;
            the PR check, the worktree removal or the branch deletion fails;
            the learning summary cannot be built or written; or the archival
            fails or moves nothing (#3585, ledger 0908 lines 72-139).
    """
    logger.info("[N9] Starting cleanup node")

    # Extract state. #3585 (ledger 0908 lines 72 and 81): it read three keys
    # no node writes (final_coverage, target_coverage, outcome), so every
    # summary said 0.0% of 0.0% and UNKNOWN, and it took the current
    # directory for a missing repo_root. It reads the declared keys and
    # refuses when one is absent.
    pr_url = state.get("pr_url", "")
    worktree_path = state.get("worktree_path", "")
    repo_root = Path(_required(state, "repo_root"))
    issue_number = _required(state, "issue_number")
    final_coverage = _required(state, "coverage_achieved")
    target_coverage = _required(state, "coverage_target")
    workflow_status = _required(state, "workflow_status")
    outcome = "SUCCESS" if workflow_status == "completed" else "FAILURE"

    # Initialize return fields
    pr_merged = False
    learning_summary_path = ""
    cleanup_skipped_reason = ""

    # === 1. WORKTREE CLEANUP ===
    if pr_url:
        try:
            pr_merged = check_pr_merged(pr_url)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as exc:
            raise _failed(
                f"the merge check of {pr_url} failed, so the worktree's fate is "
                f"unknown: {type(exc).__name__}: {exc}"
            ) from exc
        logger.info("[N9] PR merge status: %s", "MERGED" if pr_merged else "NOT MERGED")

        if pr_merged and worktree_path:
            try:
                branch = get_worktree_branch(worktree_path)
                remove_worktree(worktree_path)
                if branch:
                    delete_local_branch(branch)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                stderr = getattr(exc, "stderr", "") or ""
                raise _failed(
                    f"the worktree {worktree_path} or its branch could not be "
                    f"removed after {pr_url} merged: {type(exc).__name__}: {exc} "
                    f"{stderr.strip()}".rstrip()
                ) from exc
            logger.info("[N9] Worktree and branch cleaned up")
        elif not pr_merged:
            cleanup_skipped_reason = "PR not yet merged"
            logger.info("[N9] Skipping worktree removal — PR not merged")
        else:
            logger.info("[N9] PR merged but no worktree_path in state")
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
        except (OSError, LineageReadError) as exc:
            raise _failed(
                f"the learning summary in {active_dir} could not be built or "
                f"written: {type(exc).__name__}: {exc}"
            ) from exc
        logger.info("[N9] Learning summary written to active/")
    else:
        logger.info("[N9] No active lineage directory found — skipping summary generation")

    # === 3. LINEAGE ARCHIVAL (only if PR merged) ===
    if active_dir.exists() and pr_merged:
        try:
            done_dir = archive_lineage(repo_root, issue_number)
        except OSError as exc:
            raise _failed(
                f"the lineage {active_dir} could not be archived to done/: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        if not done_dir:
            raise _failed(
                f"archiving the lineage {active_dir} moved nothing: it was "
                f"there a moment before and is not now"
            )
        learning_summary_path = _posix_path_str(done_dir / "learning-summary.md")
        logger.info("[N9] Lineage archived to done/")
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