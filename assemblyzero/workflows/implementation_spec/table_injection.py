"""The LLD's decision table reaches the spec by code, not by drafter (#2611).

#2607 landed the lld-side half: the source issue's decision table is carried
into the LLD verbatim, machine-owned, re-asserted every round. This is the
spec-side half, and it is deliberately NOT a second copy of that module -- it
imports its primitives and supplies only what genuinely differs.

## The source of truth is the LLD, not the issue

Operator-ruled: **each stage derives from its immediate upstream settled
artifact, and never reaches around it to the source.** The two candidates the
issue named -- the LLD's injected block, or the issue directly -- agree while
the LLD's block is intact and diverge exactly when it is not. Reaching around
the LLD would make the spec silently correct while the LLD was silently wrong,
which hides the damage instead of surfacing it.

Under #2609 that is enforced rather than merely intended: the spec's settlement
records the LLD's content hash as an input, so damaging the LLD unsettles the
spec derived from it (`settlement.UPSTREAM_OF["spec"] == "lld"`).

## Why the assertion manifest does not already do this

Checked before building, and the answer is no on three counts (evidence on
#2611):

* the manifest reaches the drafter as PROMPT text -- `_manifest_section`'s
  "WRAP rows, invent nothing" -- which is an instruction to a stochastic
  drafter to copy verbatim, the exact path #2607 removed;
* `check_manifest_traceability` judges row-ID citation bookkeeping and never
  reads `row.expected`, so a test citing `# manifest: N4.2` and asserting the
  wrong number passes it;
* `expected` is `"; ".join(extract_literals(...))` -- regex matches, not the
  binding cell -- so a qualifying clause like `250 ms ± 5 ms (within the 0.82R
  band)` contributes its tokens and drops its prose. That is #2563's founding
  case.

The manifest keeps its job: it tells the drafter which assertions to write.
The injected block carries the binding values a reader can check them against.
They are complementary, and neither subsumes the other.

## The same fence, deliberately

The markers are #2607's, imported rather than redefined. The drafter reads the
LLD -- including its machine-owned block -- so a copy of that block can land in
the spec by ordinary imitation. Reusing the fence means such a copy is FOUND
and replaced by the canonical text rather than lingering beside a second block
under a different name. One marker pair, one meaning: this region is not the
drafter's.
"""

from __future__ import annotations

from assemblyzero.workflows.requirements.table_injection import (
    BEGIN_MARKER,
    END_MARKER,
    has_injection,
    injected_line_span,
    source_criteria_tables,
    source_table_text,
    strip_injection,
)

__all__ = [
    "BEGIN_MARKER",
    "END_MARKER",
    "INJECTED_HEADING",
    "apply_injection",
    "authoritative_tables",
    "build_injection",
    "current_block",
    "has_injection",
    "injected_line_span",
    "reassert",
    "strip_injection",
]

#: The heading the block is filed under in a spec. Numbered into the template's
#: own scheme (0701) so it reads as a section rather than as an intrusion, and
#: placed immediately above Test Mapping because that is the section whose
#: assertions must agree with these values.
INJECTED_HEADING = "## 9.5 Binding Decision Table (injected verbatim from the LLD)"

_PREAMBLE = (
    "The rows below are carried **verbatim** from the LLD by the derivation "
    "itself (#2611), which carried them verbatim from the source issue "
    "(#2607). They are machine-owned: the drafter does not write them, and a "
    "revision cannot change them. Every assertion in the test mapping must "
    "agree with these values; cite the IDs, do not restate the values."
)


def authoritative_tables(lld_content: str):
    """The LLD's criteria tables that bind the spec, in document order.

    When the LLD carries a machine-owned block, ONLY the tables inside it are
    authoritative -- that block is the one region no drafter and no revision
    could have touched. A drafter-written restatement elsewhere in the LLD is
    not a second source of truth; #2607's preamble tells the drafter not to
    write one, and #2563 catches it if they do.

    An LLD with no such block -- one drawn before #2607, or a prose-only
    issue's -- falls back to every criteria table it has. That is the correct
    reading of "derive from the upstream artifact" when the upstream artifact
    predates the fence.
    """
    tables = source_criteria_tables(lld_content)
    span = injected_line_span(lld_content or "")
    if span is None:
        return tables
    start, end = span
    inside = [t for t in tables if start <= t.line_no <= end]
    # An injected block that parses to no criteria table means the fence is
    # present but its content is not what this function is looking for. Fall
    # back rather than inject nothing: emitting no block would silently drop
    # the protection, which is the failure mode this module exists to end.
    return inside or tables


def build_injection(lld_content: str) -> str:
    """The machine-owned block for this LLD, or "" when none applies.

    An LLD with no criteria decision table injects nothing and the spec
    derivation proceeds exactly as before -- prose-only LLDs are the ordinary
    case and this issue's control.
    """
    tables = authoritative_tables(lld_content)
    if not tables:
        return ""
    parts = [BEGIN_MARKER, "", INJECTED_HEADING, "", _PREAMBLE, ""]
    for table in tables:
        parts.append(source_table_text(lld_content, table))
        parts.append("")
    parts.append(END_MARKER)
    return "\n".join(parts)


def current_block(text: str) -> str:
    """The machine-owned block ``text`` currently holds, or "" when none.

    Read through the public span helper rather than by re-matching the fence,
    so this module keeps exactly one notion of where the block is and it is
    #2607's.
    """
    span = injected_line_span(text or "")
    if span is None:
        return ""
    start, end = span
    return "\n".join((text or "").splitlines()[start - 1:end])


def _insertion_point(lines: list[str]) -> int:
    """Index to insert at: just BEFORE the Test Mapping section.

    The spec template (standard 0701) runs `## 1. Overview` through `## 11.
    Implementation Notes`; the binding values belong immediately above the
    section whose assertions have to match them. Falls back to the end of the
    document, which is correct rather than degraded -- placement is for the
    human reader, and every consumer of these rows finds a table anywhere.
    """
    import re

    for index, line in enumerate(lines):
        if re.match(r"^##\s+10[.\s]", line.strip()):
            return index
    return len(lines)


def apply_injection(draft: str, injection: str) -> str:
    """Assemble the drafter's output with the machine-owned block.

    Idempotent: an existing block is REPLACED, never duplicated, so calling
    this on every round re-asserts the canonical text over whatever the drafter
    did to it -- including over a block the drafter copied out of the LLD.
    """
    import re

    if not injection:
        return draft
    body = strip_injection(draft or "")
    lines = body.splitlines()
    at = _insertion_point(lines)
    merged = lines[:at] + ["", injection, ""] + lines[at:]
    text = "\n".join(merged)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if (draft or "").endswith("\n") and not text.endswith("\n"):
        text += "\n"
    return text


def reassert(draft: str, lld_content: str) -> tuple[str, bool]:
    """Restore the canonical block over whatever the draft now holds.

    Returns (text, changed). `changed` is True when the draft's block did not
    match the LLD's -- the drafter having edited machine-owned content, which
    the caller logs. Nothing is refused and nothing halts: the correct text is
    simply reinstated, which is why pinning never has to adjudicate this
    region. Re-assertion does not adjudicate a diff, so there is nothing for a
    revision to argue with.
    """
    injection = build_injection(lld_content)
    if not injection:
        return draft, False
    if current_block(draft) == injection:
        return draft, False
    return apply_injection(draft, injection), True
