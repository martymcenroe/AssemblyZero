"""Ponder Stibbons: The Compositor — mechanical auto-fix node.

Issue #307: Auto-fix layer that corrects mechanical issues in LLD drafts
before they reach the reviewer. Sits between N1b (test plan validation)
and routing to N2/N3.

Ponder only fixes mechanical/formatting issues. Content errors, logic
errors, or anything requiring judgment goes through to the reviewer
unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from assemblyzero.workflows.requirements.nodes.ponder_rules import (
    apply_all_rules,
)


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
        _save_fixes_to_lineage(fixes, Path(lineage_path), state)

    # Persist fixed draft to disk if draft path exists
    draft_path = state.get("current_draft_path")
    if draft_path:
        try:
            Path(draft_path).write_text(fixed_draft, encoding="utf-8")
            print(f"    [SAVED] Updated draft at {draft_path}")
        except OSError as e:
            print(f"    [WARN] Could not save fixed draft: {e}")

    return {
        "current_draft": fixed_draft,
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def _save_fixes_to_lineage(
    fixes: list,
    lineage_path: Path,
    state: dict[str, Any],
) -> None:
    """Save applied fixes to lineage directory for audit trail."""
    try:
        lineage_path.mkdir(parents=True, exist_ok=True)
        file_counter = state.get("file_counter", 0) + 1
        filename = f"{file_counter:03d}-ponder-fixes.md"
        fix_path = lineage_path / filename

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

        fix_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass  # Non-critical — don't crash on audit failure
