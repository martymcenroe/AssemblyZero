"""SEARCH/REPLACE edit-script revision for Implementation Specs (Closes #1528).

The measured failure (boostgauge#96 hardening runs 4-5, posted to #1529):
spec "revisions" are full regenerations — sizes oscillated 1,149 → 341 →
1,407 lines across iterations, fixing one mechanical deficiency while
losing another. The #1521/#1522 prompt fix asks the model to copy
unflagged content "byte-identical"; the data proves models don't.

This module makes drift impossible BY CONSTRUCTION: the revision model
outputs only SEARCH/REPLACE edit blocks; AZ applies them mechanically to
the existing draft. Content the model doesn't name cannot change.

Per ADR 0224, parsing and application are small pure functions with unit
tests. Any failure at any step (no blocks, unmatched SEARCH, ambiguous
SEARCH) is reported to the caller, which falls back to the classic
full-revision prompt — never worse than the pre-#1528 behavior.
"""

from __future__ import annotations

import re

# The aider-style conflict-marker format: robust for LLMs (no line numbers,
# exact-text anchoring). Tolerates trailing whitespace after markers.
_EDIT_BLOCK_RE = re.compile(
    r"^<{7} SEARCH[ \t]*\r?\n(.*?)\r?\n={7}[ \t]*\r?\n(.*?)\r?\n>{7} REPLACE[ \t]*$",
    re.DOTALL | re.MULTILINE,
)

EDIT_SCRIPT_SYSTEM_PROMPT = (
    "You are a precision patch engine. You NEVER rewrite documents — you "
    "emit minimal, exact edit blocks that a machine applies. Your entire "
    "response is edit blocks in the specified format; any prose outside "
    "edit blocks is discarded."
)


def build_edit_script_prompt(
    existing_draft: str,
    review_feedback: str,
    completeness_issues: list[str],
    prior_completeness_breakdown: list[dict] | None = None,
) -> str:
    """Build the revision prompt that requests edit blocks, not a rewrite."""
    sections: list[str] = []

    sections.append(
        "You are revising an Implementation Spec. Do NOT rewrite it. "
        "Output ONLY edit blocks in EXACTLY this format:\n\n"
        "<<<<<<< SEARCH\n"
        "(exact lines copied verbatim from the CURRENT SPEC below)\n"
        "=======\n"
        "(replacement lines)\n"
        ">>>>>>> REPLACE\n\n"
        "Rules:\n"
        "1. Each SEARCH text must be copied EXACTLY from the current spec "
        "(character-for-character, including whitespace) and must occur "
        "exactly ONCE in the spec. Keep SEARCH as small as practical "
        "(typically 1-15 lines).\n"
        "2. To INSERT new content, SEARCH for the nearest existing anchor "
        "line(s) and REPLACE with those same anchor lines plus the new "
        "content.\n"
        "3. Emit one edit block per fix. Fix ALL listed deficiencies. "
        "Touch NOTHING else — content you do not name in a SEARCH block "
        "cannot and must not change.\n"
        "4. No preamble, no explanation, no markdown fences around the "
        "blocks — edit blocks only."
    )

    if completeness_issues:
        issues_text = "## DEFICIENCIES TO FIX (mechanical validation)\n\n"
        for issue in completeness_issues:
            issues_text += f"- {issue}\n"
        sections.append(issues_text)

    if review_feedback:
        sections.append(f"## REVIEWER FEEDBACK TO ADDRESS\n\n{review_feedback}")

    if prior_completeness_breakdown:
        history = "## PRIOR ITERATION FAILURES (do not repeat)\n\n"
        for entry in prior_completeness_breakdown:
            iteration = entry.get("iteration", "?")
            failures = entry.get("failures", [])
            history += f"- Iteration {iteration}: " + "; ".join(
                str(f) for f in failures
            ) + "\n"
        sections.append(history)

    sections.append(
        "## CURRENT SPEC (the document you are patching)\n\n"
        + existing_draft
    )

    return "\n\n".join(sections)


def parse_edit_blocks(response: str) -> list[tuple[str, str]]:
    """Extract (search, replace) pairs from a model response.

    Tolerates the whole response being wrapped in a single markdown fence
    (a common model tic). Returns [] when no well-formed blocks exist —
    the caller falls back to classic regeneration.
    """
    if not response:
        return []
    text = response.strip()

    # Unwrap a single whole-response code fence if present.
    if text.startswith("```") and text.endswith("```"):
        first_newline = text.find("\n")
        if first_newline > 0:
            inner = text[first_newline + 1 : -3].strip()
            if "<<<<<<< SEARCH" in inner:
                text = inner

    return [(m.group(1), m.group(2)) for m in _EDIT_BLOCK_RE.finditer(text)]


def apply_edit_blocks(
    draft: str, blocks: list[tuple[str, str]]
) -> tuple[str, list[str]]:
    """Apply edit blocks sequentially to ``draft``.

    Each SEARCH must match exactly once in the CURRENT text (edits apply
    in order, so later blocks see earlier results). Returns
    (patched_text, failures); failures is non-empty when any block could
    not be applied — the caller must then discard the result and fall
    back (partial application is never returned as success).
    """
    failures: list[str] = []
    text = draft
    for i, (search, replace) in enumerate(blocks, start=1):
        count = text.count(search)
        if count == 0:
            failures.append(
                f"block {i}: SEARCH text not found (model did not copy "
                f"verbatim): {search[:80]!r}"
            )
        elif count > 1:
            failures.append(
                f"block {i}: SEARCH text ambiguous ({count} occurrences): "
                f"{search[:80]!r}"
            )
        else:
            text = text.replace(search, replace, 1)
    return text, failures


def unchanged_ratio(original: str, patched: str) -> float:
    """Fraction of the original's lines that survive byte-identical.

    Cheap stability telemetry for #1529: line-level containment, not a
    true diff — good enough to show 'revision, not regeneration'.
    """
    original_lines = original.splitlines()
    if not original_lines:
        return 1.0
    patched_set = set(patched.splitlines())
    kept = sum(1 for line in original_lines if line in patched_set)
    return kept / len(original_lines)
