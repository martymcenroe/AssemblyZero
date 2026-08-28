"""The source decision table reaches the LLD by code, not by drafter (#2607).

Literals travelled through a stochastic rewriter and the whole guard stack
existed to catch what fell out. Three demonstrations in one week:

* the #361 sampling window shed silently, re-opening a settled conflict as
  boostgauge #369 and killing a roll (#2563's founding case);
* four genuine losses in the #2563 gate's own calibration (PR #2564);
* five criticals on the first post-gate redraw (run-issue331-093613) — and
  that same run, diagnosed under #2608, turned out to have emitted **no
  table at all** in draft 1, then repaired to a seven-item bullet list that
  dropped S7 and S9 and every assertion method.

The last one is why detection alone is not enough. The gate makes loss
loud; injection makes loss impossible. Where the transform is "copy these
values verbatim", no LLM belongs in the path.

## Byte-verbatim, and how

`RawTable.line_no` is the 1-based index of the header line, so the source's
own lines can be SLICED out of the issue body and re-emitted unchanged.
Nothing is re-rendered from parsed cells: a round-trip through cells would
normalise padding, drop trailing whitespace, and quietly become "modulo
reformatting" — a phrase that hides exactly the kind of drift this module
exists to end. The block that lands in the LLD is the block that was in the
issue, byte for byte.

## The shared substrate question, answered by evidence

#2607 asks whether the #2533 manifest compiler's row parser is the right
shared substrate. It already IS shared: `assertion_manifest` imports
`parse_tables` and `RawTable` from `requirements.form_check`, and layers
`is_criteria_table` on top. #2608 established the parser handles real state
correctly — 15 of 15 tables in the run-19 LLD, and the source's nine-row
table — so the failure was never parsing. This module reuses that pair and
adds no third notion of "what a decision table is".

## Machine-owned regions

The injected block is fenced by HTML comment markers. Two properties follow
and both are mechanical rather than adjudicated:

* the drafter is told to write AROUND it and never to restate the table;
* on every revision the block is RE-ASSERTED from source — whatever the
  drafter did inside the markers is discarded and the canonical text
  restored.

Re-assertion is deliberately stronger than asking pinning to protect the
region. Pinning adjudicates a diff and can be argued with; re-assertion
does not adjudicate. It also means pinning never has to reason about the
injected rows at all, which is what #2607 asks for — the region is content
no verdict need ever name.
"""

from __future__ import annotations

import re

from assemblyzero.workflows.implementation_spec.assertion_manifest import (
    is_criteria_table,
)
from assemblyzero.workflows.requirements.form_check import RawTable, parse_tables

#: The fence. HTML comments so the block renders as an ordinary table in
#: every markdown viewer while staying machine-findable.
BEGIN_MARKER = "<!-- BEGIN MACHINE-OWNED: source decision table (#2607) -->"
END_MARKER = "<!-- END MACHINE-OWNED -->"

#: A machine-owned block: BEGIN, then anything that is NOT another BEGIN,
#: then END.
#:
#: The "not another BEGIN" clause is load-bearing (#2628). A plain `.*?` lets a
#: STRAY begin marker swallow the document down to the real block's end, and
#: drafters emit stray markers: boostgauge's halted draw `run-issue331-152355`
#: carries an empty pair at line 3 whose END reads
#: `<!-- END MACHINE-OWNED: source decision table (#2607) -->` -- byte-exact
#: BEGIN, near-miss END. With `.*?` the span ran from line 3 to line 126 and
#: `strip_injection` deleted 125 lines including Sections 1, 2 and 3.
#:
#: That was one revision round from firing for real: `reassert` runs on every
#: lld draft and `apply_injection` strips first, so the next round would have
#: deleted Section 3, then failed to find `## 3.` to insert at, and appended
#: the block to a gutted document. The format-war halt this issue reports is
#: what stopped it.
#:
#: With the guard, the match starting at the stray BEGIN is rejected because a
#: real BEGIN intervenes before any END, and the match starting at the real
#: BEGIN is accepted. The stray pair is left alone: it is the drafter's own
#: text, and removing it is not this rule's job.
_BLOCK_RE = re.compile(
    re.escape(BEGIN_MARKER)
    + r"(?:(?!" + re.escape(BEGIN_MARKER) + r").)*?"
    + re.escape(END_MARKER),
    re.DOTALL,
)

#: The heading the block is filed under. A real heading, so the table sits
#: somewhere a reader expects to find it rather than in an unexplained fence.
INJECTED_HEADING = "### 3.1 Source Decision Table (injected verbatim)"

_PREAMBLE = (
    "The rows below are carried **verbatim** from the source issue by the "
    "derivation itself (#2607). They are machine-owned: the drafter does "
    "not write them, and a revision cannot change them. Cite these IDs from "
    "the requirements and test-plan sections; do not restate their values."
)


def source_table_text(issue_body: str, table: RawTable) -> str:
    """The table's own lines, sliced out of the source. Byte-verbatim.

    `line_no` is 1-based and points at the header; the separator follows it
    and then one line per row, which is exactly how `parse_tables` walked
    them. Slicing rather than re-rendering is the whole point -- a
    round-trip through parsed cells would normalise the very characters the
    derivation is supposed to preserve.
    """
    lines = (issue_body or "").splitlines()
    start = max(0, table.line_no - 1)
    end = min(len(lines), start + 2 + len(table.rows))
    return "\n".join(lines[start:end])


def source_criteria_tables(issue_body: str) -> list[RawTable]:
    """Every criteria decision table in the source, in document order."""
    return [t for t in parse_tables(issue_body or "") if is_criteria_table(t)]


def build_injection(issue_body: str) -> str:
    """The machine-owned block for this issue, or "" when none applies.

    An issue with no criteria decision table injects nothing and the
    derivation proceeds exactly as before -- prose-only requirements are the
    ordinary case and #2607's control.
    """
    tables = source_criteria_tables(issue_body)
    if not tables:
        return ""
    parts = [BEGIN_MARKER, "", INJECTED_HEADING, "", _PREAMBLE, ""]
    for table in tables:
        parts.append(source_table_text(issue_body, table))
        parts.append("")
    parts.append(END_MARKER)
    return "\n".join(parts)


def has_injection(text: str) -> bool:
    return bool(_BLOCK_RE.search(text or ""))


def strip_injection(text: str) -> str:
    """Remove every machine-owned block, leaving the drafter's own prose."""
    stripped = _BLOCK_RE.sub("", text or "")
    # Collapse the blank-line run the removal leaves behind, so repeated
    # strip/inject cycles do not accumulate whitespace in the document.
    return re.sub(r"\n{3,}", "\n\n", stripped)


def injected_line_span(text: str) -> tuple[int, int] | None:
    """1-based inclusive (start, end) of the machine-owned block.

    For callers that need to know which lines are not the drafter's -- the
    pinning path asserts it never adjudicates them.
    """
    match = _BLOCK_RE.search(text or "")
    if not match:
        return None
    before = (text or "")[: match.start()]
    start = before.count("\n") + 1
    end = start + match.group(0).count("\n")
    return (start, end)


def _insertion_point(lines: list[str]) -> int:
    """Index to insert at: just after the Requirements section's heading.

    Falls back to the end of the document. Placement is for the human
    reader; the manifest compiler finds a criteria table anywhere, so a
    fallback that appends is correct rather than degraded.
    """
    for index, line in enumerate(lines):
        if re.match(r"^##\s+3[.\s]", line.strip()):
            return index + 1
    return len(lines)


def apply_injection(draft: str, injection: str) -> str:
    """Assemble the drafter's output with the machine-owned block.

    Idempotent: an existing block is REPLACED, never duplicated, so calling
    this on every round re-asserts the canonical text over whatever the
    drafter did to it.
    """
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


def reassert(draft: str, issue_body: str) -> tuple[str, bool]:
    """Restore the canonical block over whatever the draft now holds.

    Returns (text, changed). `changed` is True when the draft's block did
    not match the source -- which is the drafter having edited machine-owned
    content, and the caller logs it. Nothing is refused and nothing halts:
    the correct text is simply reinstated, which is why pinning never has to
    adjudicate this region.
    """
    injection = build_injection(issue_body)
    if not injection:
        return draft, False
    current = _BLOCK_RE.search(draft or "")
    if current and current.group(0) == injection:
        return draft, False
    return apply_injection(draft, injection), True
