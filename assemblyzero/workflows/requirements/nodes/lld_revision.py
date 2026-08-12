"""Edit-script revision for LLD drafts, ported from the spec stage (#2200).

The measured failure, twice, in boostgauge:

- ``run-issue1-122404``: draft 2 passed mechanical and test-plan validation
  and the reviewer APPROVED it at 321 lines. The forced revision came back at
  163 lines with sections 2.1, 11 and 12 gone.
- ``run-issue7-182028``: draft 003 carried all twelve numbered sections
  through both validators at 422 lines. Draft 005, responding to a REVISE
  verdict, came back at 268 lines with sections 3, 10, 11 and 12 replaced by
  the literal heading ``## [UNCHANGED] 3. Requirements``. The model emitted
  the revision prompt's own preservation marker in place of the content it
  was being told to preserve.

Draft 003 happened to keep its structure and 005 did not, which is the point:
under the old path preservation was luck. The prompt already said "PRESERVE
sections that weren't flagged" and "Keep ALL template sections intact". Asking
the generator to police its own drift is the defect, not the fix.

The mechanism here is the one the implementation-spec stage adopted in #1528
and has run cleanly since: **the revision model is never asked to redraw the
document.** It names its edits, the harness applies them, and everything
outside the named spans survives byte-identical because no generation ever
touches it. The primitives are imported from the spec stage rather than
copied, so there is one parser and one applier in the fleet; a copy would
drift, and a drifted patcher is worse than none.

There is deliberately no fall back to full regeneration. The spec stage keeps
one because in #1528 the alternative was the pre-existing behavior; here
wholesale regeneration IS the defect being removed, so a revision that cannot
be expressed as edits halts loudly and names the contract it violated, per
standard 0028. The prior draft is retained untouched, on disk and in state,
and a relaunch resumes from this stage (#2193).
"""

from __future__ import annotations

import re

# Imported, never copied: one parser and one applier for the whole fleet.
# These three are document-agnostic -- they operate on text and edit blocks
# and know nothing about specs -- so the spec stage's module is their home
# and this stage is a second caller (the same discipline as #2221).
from assemblyzero.workflows.implementation_spec.nodes.edit_script import (  # noqa: F401
    EDIT_SCRIPT_SYSTEM_PROMPT,
    apply_edit_blocks,
    parse_edit_blocks,
    unchanged_ratio,
)

#: A numbered section heading: ``## 3. Requirements``, ``### 2.1 Files
#: Changed``, ``### 2.1.1 Path Validation``. The number must follow the hashes
#: immediately, which is what makes ``## [UNCHANGED] 3. Requirements`` read as
#: the absence of section 3 rather than its presence. That is the exact shape
#: draft 005 shipped, and mechanical validation agreed: it flagged 11 and 12 as
#: Critical because ``"## 11"`` no longer appeared in the document.
_SECTION_HEADING = re.compile(r"^#{2,4}[ \t]+(\d+(?:\.\d+)*)\.?[ \t]", re.MULTILINE)


def section_numbers(text: str) -> set[str]:
    """The numbered sections a document actually has as headings."""
    return {match.group(1) for match in _SECTION_HEADING.finditer(text or "")}


def _numeric_key(section: str) -> list[int]:
    return [int(part) for part in section.split(".")]


def removed_required_sections(
    prior_draft: str, revised_draft: str, template: str
) -> list[str]:
    """Template-required sections this revision would drop, in order.

    A section counts as removed when the template requires it, the prior
    draft had it, and the revision does not. A section the prior draft never
    carried cannot be removed by this revision, and one the template does not
    require is the author's to delete on a reviewer's instruction, so neither
    is reported here. Only numbered sections are protected; the template's
    unnumbered appendix is a log rather than a requirement-bearing section.
    """
    required = section_numbers(template)
    before = section_numbers(prior_draft)
    after = section_numbers(revised_draft)
    return sorted((required & before) - after, key=_numeric_key)


def build_lld_edit_prompt(existing_draft: str, revision_context: str) -> str:
    """Build the revision prompt that asks for edit blocks, not a document.

    Deliberately carries no "preserve what you did not change" instruction.
    Under this contract untouched content is never emitted at all, so there is
    nothing for such an instruction to protect, and adding one would restore
    the very please-behave posture that produced the two measured losses.
    """
    sections: list[str] = [
        "You are revising a Low-Level Design document. Do NOT rewrite it. "
        "Output ONLY edit blocks in EXACTLY this format:\n\n"
        "<<<<<<< SEARCH\n"
        "(exact lines copied verbatim from the CURRENT LLD below)\n"
        "=======\n"
        "(replacement lines)\n"
        ">>>>>>> REPLACE\n\n"
        "Rules:\n"
        "1. Each SEARCH text must be copied EXACTLY from the current LLD "
        "(character-for-character, including whitespace) and must occur "
        "exactly ONCE in the document. Keep SEARCH as small as practical "
        "(typically 1-15 lines).\n"
        "2. To INSERT new content, SEARCH for the nearest existing anchor "
        "line(s) and REPLACE with those same anchor lines plus the new "
        "content.\n"
        "3. Emit one edit block per fix, and fix EVERY item listed below.\n"
        "4. No preamble, no explanation, no markdown fences around the "
        "blocks -- edit blocks only."
    ]

    if revision_context.strip():
        sections.append(revision_context.strip())

    sections.append(
        "## CURRENT LLD (the document you are patching)\n\n" + existing_draft
    )

    return "\n\n".join(sections)
