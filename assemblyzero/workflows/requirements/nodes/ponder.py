"""Ponder Stibbons: The Compositor — mechanical auto-fix node.

Issue #307: Auto-fix layer that corrects mechanical issues in LLD drafts
before they reach the reviewer. Sits between N1b (test plan validation)
and routing to N2/N3.

Ponder only fixes mechanical/formatting issues. Content errors, logic
errors, or anything requiring judgment goes through to the reviewer
unchanged.

#3585 (ADR 0236): a fixed draft that cannot be written back, or a lineage
record of the fixes that cannot be written, sets ``error_message``, which
``route_after_ponder`` sends to HALT. The disk and the state used to diverge
behind a warning, and the lineage record was dropped without one.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from assemblyzero.workflows.requirements.nodes.ponder_rules import (
    apply_all_rules,
)

logger = logging.getLogger(__name__)


def _loud(message: str) -> str:
    """One ERROR line on stderr and in the log (ADR 0236 property 1)."""
    logger.error("[N_PONDER] %s", message)
    print(f"ERROR [N_PONDER] {message}", file=sys.stderr, flush=True)
    return message


def ponder_stibbons_node(state: dict[str, Any]) -> dict[str, Any]:
    """N_PONDER: Apply mechanical auto-fixes to the current draft.

    Reads the current draft, applies deterministic fix rules, and
    updates the draft in-place. No LLM calls.

    Args:
        state: Current workflow state.

    Returns:
        State updates with (possibly) fixed draft and audit trail.
    """
    draft = state.get("current_draft", "")
    if not draft:
        print("\n[N_PONDER] No draft to fix — skipping")
        return {
            "iteration_count": state.get("iteration_count", 0) + 1,
        }

    # Build context for rules
    ctx = {
        "issue_number": state.get("issue_number"),
        "workflow_type": state.get("workflow_type"),
    }

    print("\n[N_PONDER] Ponder Stibbons — applying mechanical fixes...")

    fixed_draft, fixes = apply_all_rules(draft, ctx)

    if not fixes:
        print("    [RESULT] No fixes needed — draft is clean")
        return {
            "iteration_count": state.get("iteration_count", 0) + 1,
        }

    # Report fixes
    print(f"    [RESULT] Applied {len(fixes)} fix(es):")
    for fix in fixes:
        print(f"      - [{fix.rule}] {fix.description}")

    # Save audit trail to lineage
    lineage_path = state.get("lineage_path")
    if lineage_path:
        try:
            _save_fixes_to_lineage(fixes, Path(lineage_path), state)
        except OSError as e:
            return {"error_message": (
                f"[N_PONDER] the record of {len(fixes)} auto-fix(es) could not "
                f"be written to {lineage_path}: {type(e).__name__}: {e}"
            )}

    # Persist fixed draft to disk if draft path exists
    draft_path = state.get("current_draft_path")
    if draft_path:
        try:
            Path(draft_path).write_text(fixed_draft, encoding="utf-8")
        except OSError as e:
            return {"error_message": _loud(
                f"the fixed draft could not be written to {draft_path} "
                f"({type(e).__name__}: {e}), so the draft on disk and the one "
                f"in state would differ"
            )}
        print(f"    [SAVED] Updated draft at {draft_path}")

    return {
        "current_draft": fixed_draft,
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def _save_fixes_to_lineage(
    fixes: list,
    lineage_path: Path,
    state: dict[str, Any],
) -> None:
    """Save applied fixes to lineage directory for audit trail.

    Raises:
        OSError: the record cannot be written (#3585), after an ERROR line
            naming the folder; it used to be swallowed as non-critical.
    """
    file_counter = state.get("file_counter", 0) + 1
    fix_path = lineage_path / f"{file_counter:03d}-ponder-fixes.md"
    lines = [
        "# Ponder Stibbons — Auto-Fixes Applied",
        "",
        f"Draft number: {state.get('draft_number', '?')}",
        f"Fixes applied: {len(fixes)}",
        "",
        "| Rule | Section | Description |",
        "|------|---------|-------------|",
    ]
    for fix in fixes:
        lines.append(f"| {fix.rule} | {fix.section} | {fix.description} |")
    try:
        lineage_path.mkdir(parents=True, exist_ok=True)
        fix_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as exc:
        _loud(
            f"cannot write the auto-fix record {fix_path}: "
            f"{type(exc).__name__}: {exc}"
        )
        raise
