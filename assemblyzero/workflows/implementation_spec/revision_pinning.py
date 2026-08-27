"""Pin what passed: revisions edit the named items and nothing else (#2532).

The spec review loop's unit of revision was the whole document while its unit
of error is the individual assertion. Every REVISE re-rolled the dice on every
assertion that was already right — measured on run-issue331-233939: nine
rounds to the hard ceiling, and S2's band-background trap FIXED by round 9,
then REINTRODUCED by the resumed grant's regeneration. The loop un-fixes its
own progress.

This module makes that impossible mechanically:

* **Named** content is what the current verdict (and the current completeness
  failures) actually point at — test names, backticked spans, quoted phrases,
  manifest row ids, and line-range citations (``lines 81-83``, #2555) —
  attributed to the draft's natural blocks (a test function, a markdown
  section).
* **Locked** content is everything else in the reviewed draft: a completed
  round passed it without objection. A revision that touches locked text is
  refused mechanically — the locked span carries forward byte-verbatim from
  the previous draft — unless the drafter requested an unlock explicitly
  (an ``UNLOCK: <reason>`` line in its response), which is logged, never
  silent.
* **The regression event**: a revision that modified content NO verdict in
  the whole history ever objected to is the S2-regression class, flagged at
  the moment it happens instead of one round later.

Iteration 1 (the initial draft) is untouched — this governs revisions only.
Every function here is pure (ADR 0224): text in, text and events out.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# What the verdict names
# ---------------------------------------------------------------------------

_BACKTICK_RE = re.compile(r"`([^`\n]{2,120})`")
_TEST_NAME_RE = re.compile(r"\btest_[A-Za-z0-9_]+\b")
_QUOTED_RE = re.compile(r"\"([^\"\n]{4,120})\"")
#: Manifest row ids (#2533) — a verdict citing N4.2 names that row's test.
_ROW_ID_RE = re.compile(r"\b[A-Z]\d{0,3}[a-z]?\.\d+\b")
#: Section references like "Section 10.2" / "section 5".
_SECTION_RE = re.compile(r"\bSection\s+[\w.]+", re.IGNORECASE)


def named_tokens(feedback: str, completeness_issues: list[str] | None = None) -> set[str]:
    """The identifiers a verdict actually points at, lowercased."""
    text = (feedback or "") + "\n" + "\n".join(completeness_issues or [])
    tokens: set[str] = set()
    for pattern in (_BACKTICK_RE, _QUOTED_RE):
        tokens.update(m.group(1).strip() for m in pattern.finditer(text))
    for pattern in (_TEST_NAME_RE, _ROW_ID_RE, _SECTION_RE):
        tokens.update(m.group(0).strip() for m in pattern.finditer(text))
    return {t.lower() for t in tokens if len(t.strip()) >= 3}


#: Line-range citations like "lines 81-83" (#2555). The DASH IS REQUIRED:
#: a completeness check cites a span deliberately, while bare "line 1"
#: occurs inside quoted error text constantly — the observed fence complaint
#: itself carries "SyntaxError: invalid decimal literal (<unknown>, line 1)",
#: where the 1 is a position inside the snippet, not a draft address.
#: Parsing that would unlock the block holding draft line 1 on every fence
#: complaint. A dashed range in a mechanical check's message is a draft
#: address by construction; a bare line number is anybody's.
_LINE_RANGE_RE = re.compile(r"\blines?\s+(\d+)\s*[-–]\s*(\d+)\b", re.IGNORECASE)


def named_line_ranges(completeness_issues: list[str] | None) -> tuple[tuple[int, int], ...]:
    """1-based inclusive (start, end) ranges the completeness failures cite.

    Completeness checks measure the draft the revision is diffed against, so
    their line numbers address that exact document (#2555 — the fence-parse
    complaint "lines 81-83 (```python)" named the one span the drafter had
    to change, in an addressing scheme no token pattern could read, and
    pinning reverted the mandated retag three rounds running).

    Deliberately NOT parsed from free-form reviewer feedback: a reviewer
    citing "lines 40-60" may mean a repo file or the LLD, and a wrong match
    would silently unlock an unrelated draft block. Mechanical checks own
    their citation convention; prose does not.
    """
    ranges: list[tuple[int, int]] = []
    for issue in completeness_issues or []:
        for match in _LINE_RANGE_RE.finditer(str(issue)):
            start, end = int(match.group(1)), int(match.group(2))
            if 1 <= start <= end:
                ranges.append((start, end))
    return tuple(ranges)


# ---------------------------------------------------------------------------
# The draft's natural blocks
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^```")
_DEF_RE = re.compile(r"^(?:async\s+)?(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)")


@dataclass
class _Block:
    name: str
    start: int  # inclusive line index
    end: int    # exclusive
    text: str = ""


def _blocks(draft: str) -> list[_Block]:
    """Split a draft into attribution blocks.

    Outside fences: one block per markdown section (heading to heading).
    Inside fences: one block per top-level ``def``/``class`` — the verdict's
    unit of naming is the test, and a fence routinely holds many.
    """
    lines = draft.splitlines()
    blocks: list[_Block] = []
    current = _Block(name="(preamble)", start=0, end=0)
    in_fence = False

    def close(at: int) -> None:
        nonlocal current
        current.end = at
        if current.end > current.start:
            current.text = "\n".join(lines[current.start:current.end])
            blocks.append(current)

    for index, line in enumerate(lines):
        if _FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            match = _DEF_RE.match(line)
            if match and not line[:1].isspace():
                close(index)
                current = _Block(name=match.group(1), start=index, end=index)
            continue
        match = _HEADING_RE.match(line)
        if match:
            close(index)
            current = _Block(name=match.group(1), start=index, end=index)
    close(len(lines))
    return blocks


def named_line_flags(
    draft: str,
    tokens: set[str],
    ranges: tuple[tuple[int, int], ...] = (),
) -> list[bool]:
    """Per-line: is this line inside a block the tokens or ranges name?

    A block is named when its own name matches a token, when any token
    appears anywhere in its text, or when any cited 1-based line range
    overlaps it (#2555) — the generous direction, because a wrongly-locked
    legitimate fix costs a round while a wrongly-freed line costs only what
    the old behaviour always risked. A range names its whole enclosing
    block for the same reason a token does: restructuring AROUND a named
    item is the named item's business.
    """
    lines = draft.splitlines()
    flags = [False] * len(lines)
    if not tokens and not ranges:
        return flags
    for block in _blocks(draft):
        block_lower = block.text.lower()
        name_lower = block.name.lower()
        named = any(
            token in name_lower or token in block_lower for token in tokens
        ) or any(
            # 1-based inclusive (start, end) vs 0-based [block.start, block.end)
            start - 1 < block.end and block.start < end
            for start, end in ranges
        )
        if named:
            for index in range(block.start, block.end):
                flags[index] = True
    return flags


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PinningResult:
    text: str
    #: Locked regions the revision tried to change, restored byte-verbatim.
    refusals: tuple[str, ...] = ()
    #: Changed regions no verdict EVER named — the S2-regression class,
    #: flagged at the moment it happens (computed before restoration).
    regressions: tuple[str, ...] = ()
    unlock_reason: str = ""


_UNLOCK_RE = re.compile(r"^\s*UNLOCK:\s*(.+?)\s*$", re.MULTILINE)


def unlock_requested(response: str) -> str:
    """The drafter's explicit unlock request, or "". Logged, never silent."""
    match = _UNLOCK_RE.search(response or "")
    return match.group(1) if match else ""


def _preview(lines: list[str], count: int) -> str:
    first = next((line.strip() for line in lines if line.strip()), "")
    return f"{count} line(s) starting {first[:70]!r}"


def enforce_pinning(
    previous: str,
    revised: str,
    *,
    current_tokens: set[str],
    ever_tokens: set[str] | None = None,
    current_ranges: tuple[tuple[int, int], ...] = (),
    unlock_reason: str = "",
) -> PinningResult:
    """Carry every unnamed span of ``previous`` forward byte-verbatim.

    Walks the line diff. A changed region whose OLD lines are all outside the
    verdict's named blocks is locked: the old lines are restored and the
    attempt recorded as a refusal. Regions that touch any named line pass
    through — restructuring AROUND a named item is the named item's business.
    Insertions pass through: adding is not un-fixing.

    ``current_ranges`` (#2555) are the 1-based line spans the CURRENT
    completeness failures cite against ``previous``; they name lines exactly
    as tokens do, and they feed BOTH flag sets — a change a completeness
    failure explicitly demands is never a lock refusal and never the
    regression class. That is the invariant this parameter exists for: the
    fence-parse gate demanded a one-line retag by line number, no token
    pattern could read the address, and pinning reverted the mandated fix
    into byte-identical drafts three rounds running (run-issue331-092913).

    ``ever_tokens`` (the union across the whole verdict history) drives the
    regression events; they are computed from the REVISION AS SUBMITTED, so
    the flag fires even when enforcement then restores the text. Prior
    rounds' line ranges are deliberately NOT carried into it: line numbers
    address the one document the check measured, and drafts shift under
    revision.

    With ``unlock_reason`` the restoration is skipped entirely — the drafter
    asked to restructure and the caller logs it — but the regression events
    still fire, because an unlock explains a change, it does not un-happen it.
    """
    prev_lines = previous.splitlines()
    rev_lines = revised.splitlines()
    current_flags = named_line_flags(previous, current_tokens, current_ranges)
    ever_flags = (
        named_line_flags(previous, ever_tokens, current_ranges)
        if ever_tokens is not None else current_flags
    )

    refusals: list[str] = []
    regressions: list[str] = []
    out: list[str] = []

    matcher = difflib.SequenceMatcher(None, prev_lines, rev_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            out.extend(prev_lines[i1:i2])
            continue
        if tag == "insert":
            out.extend(rev_lines[j1:j2])
            continue
        old_region = prev_lines[i1:i2]
        # The S2-regression class: this change touches lines NO verdict ever
        # named. Recorded before any restoration decision.
        if old_region and all(not ever_flags[i] for i in range(i1, i2)):
            regressions.append(_preview(old_region, i2 - i1))
        locked = old_region and all(
            not current_flags[i] for i in range(i1, i2)
        )
        if locked and not unlock_reason:
            out.extend(old_region)  # byte-verbatim carry-forward
            refusals.append(_preview(old_region, i2 - i1))
        else:
            out.extend(rev_lines[j1:j2])

    text = "\n".join(out)
    if revised.endswith("\n") or previous.endswith("\n"):
        text += "\n"
    return PinningResult(
        text=text,
        refusals=tuple(refusals),
        regressions=tuple(regressions),
        unlock_reason=unlock_reason,
    )
