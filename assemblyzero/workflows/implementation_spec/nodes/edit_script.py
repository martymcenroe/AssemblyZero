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
# #2918: the three marker lines, matched whole. `parse_edit_blocks` reads
# the response line by line against these rather than with the regex above,
# which is kept only as documentation of the format.
_SEARCH_MARKER_RE = re.compile(r"<{7} SEARCH[ \t]*\r?")
_SEPARATOR_RE = re.compile(r"={7}[ \t]*\r?")
_REPLACE_MARKER_RE = re.compile(r">{7} REPLACE[ \t]*\r?")


def _has_marker_line(section: str) -> bool:
    """Does an edit section carry one of the three markers as a line (#2918)?"""
    return any(
        _SEARCH_MARKER_RE.fullmatch(line)
        or _SEPARATOR_RE.fullmatch(line)
        or _REPLACE_MARKER_RE.fullmatch(line)
        for line in section.splitlines()
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
    apply_failure: str = "",
) -> str:
    """Build the revision prompt that requests edit blocks, not a rewrite.

    ``apply_failure`` (#2569): the exact failure of the previous attempt's
    edit blocks, when there was one. There is no full-regeneration fallback
    any more — a failed script re-prompts with its failure, because the
    drafter can disambiguate a SEARCH far more reliably than enforcement
    can un-mangle a rewrite.
    """
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
        "blocks — edit blocks only.\n"
        "5. PINNING (#2532): content a completed review round passed "
        "without objection is LOCKED — an edit touching text the feedback "
        "below does not name will be refused mechanically and the old text "
        "kept. If a fix genuinely requires restructuring beyond the named "
        "items, put a single line `UNLOCK: <one-line reason>` before your "
        "first edit block; the unlock is logged, never silent."
    )

    if apply_failure:
        sections.append(
            "## YOUR PREVIOUS ATTEMPT FAILED TO APPLY (#2569)\n\n"
            f"{apply_failure}\n\n"
            "This is a correction round, not a restart: emit a fresh, "
            "complete set of edit blocks for ALL listed deficiencies, "
            "with the failure above repaired."
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

    # #2918: line by line, so an EMPTY section is a section. The regex this
    # replaces required a newline on both sides of each section's text, so a
    # block whose REPLACE was empty -- a deletion -- did not match at its own
    # `>>>>>>> REPLACE` and the lazy `(.*?)` ran on to the NEXT block's
    # closing marker, capturing that marker and the next block's SEARCH as
    # the replacement text. run-issue4-141929 wrote `>>>>>>> REPLACE` into
    # line 13 of windows.py, reported `Applied 2 edit(s); 100% preserved`,
    # and every test in the suite died on the SyntaxError.
    blocks: list[tuple[str, str]] = []
    section: str | None = None
    search: list[str] = []
    replace: list[str] = []
    for line in text.splitlines():
        if _SEARCH_MARKER_RE.fullmatch(line):
            if section is not None:
                return []  # a block opened inside a block: malformed
            section, search, replace = "search", [], []
        elif section == "search" and _SEPARATOR_RE.fullmatch(line):
            section = "replace"
        elif section == "replace" and _REPLACE_MARKER_RE.fullmatch(line):
            blocks.append(("\n".join(search), "\n".join(replace)))
            section = None
        elif section == "search":
            search.append(line)
        elif section == "replace":
            replace.append(line)
    return blocks


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
        if _has_marker_line(search) or _has_marker_line(replace):
            # #2918: a marker inside a section can only come from a
            # malformed response, and written into a file it is a
            # SyntaxError on every test. Never applied, whatever the parser
            # in front of this did.
            failures.append(
                f"block {i}: an edit marker inside a section; the response "
                f"is malformed"
            )
            continue
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
