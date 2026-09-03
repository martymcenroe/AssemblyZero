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
* **The conservation gate** (#2559): the merge never emits a document that
  lost a test definition the previous draft held and no verdict named —
  on violation it emits the revision unenforced or the previous draft
  entire, loudly, never the stitched result.
* **Demanded additions** (#2560): when the round's completeness failures
  demand new tests, a locked region introducing one passes — a demand to
  add has no line to cite, so the named-content exemptions cannot cover it.

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

    An OPENING fence delimiter belongs to the region it opens, not to the
    heading above it (#2681). It was attributed backward, so on a spec whose
    §10.1 fence holds the named tests, the tests unlocked while the ```python
    line stayed locked inside an unnamed heading block — and an insertion
    inside the fence, which shifts that line, read as modifying locked
    content. `manifest_traceability` demands a `# manifest:` comment that can
    only live inside the fence, so the two were jointly unsatisfiable and
    boostgauge #384 burned two caps with the drafter's fix written and
    refused. A fence that holds no top-level def keeps its old attribution:
    there is no region for it to open.
    """
    lines = draft.splitlines()
    blocks: list[_Block] = []
    current = _Block(name="(preamble)", start=0, end=0)
    in_fence = False
    fence_open_at: int | None = None

    def close(at: int) -> None:
        nonlocal current
        current.end = at
        if current.end > current.start:
            current.text = "\n".join(lines[current.start:current.end])
            blocks.append(current)

    for index, line in enumerate(lines):
        if _FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            # Remember an opening delimiter so the first def inside can claim
            # it; forget it on the close, and on an open whose fence turned
            # out to hold no def (the delimiter then stays where it was).
            fence_open_at = index if in_fence else None
            continue
        if in_fence:
            match = _DEF_RE.match(line)
            if match and not line[:1].isspace():
                start = fence_open_at if fence_open_at is not None else index
                close(start)
                current = _Block(name=match.group(1), start=start, end=start)
                fence_open_at = None
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
    #: Regions passed through as demanded additions (#2560) — a completeness
    #: failure demanded new tests, and the region introduces one.
    additions: tuple[str, ...] = ()
    #: Non-empty when the conservation gate overrode the merge (#2559):
    #: the walked output lost tests no verdict named, so ``text`` is the
    #: revision unenforced (differ misalignment) or the previous draft
    #: entire (the revision itself removed them).
    conservation_event: str = ""
    unlock_reason: str = ""


_UNLOCK_RE = re.compile(r"^\s*UNLOCK:\s*(.+?)\s*$", re.MULTILINE)

#: A test definition line — the conserved quantity of the merge (#2559) and
#: the artifact class completeness checks demand added (#2560).
_TEST_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)\s*\(")

#: A fence delimiter. The second artifact class a completeness check demands
#: added (#2591) — an excerpt, a data-structure example and an I/O example are
#: all fenced code blocks, and none of them is a test definition.
_FENCE_OPEN_RE = re.compile(r"^\s*```")

#: EVERY addition-demanding phrase our completeness checks emit, enumerated
#: from their own `details=` strings rather than guessed at (#2591). The set is
#: closed and authored: five phrasings, four checks, all in
#: `validate_completeness.py`, and a new one has to be added here deliberately.
#:
#: | phrase | check | artifact demanded |
#: |---|---|---|
#: | `have no test` / `add a test` / `owes each a test` | criteria, error paths, manifest | a test definition |
#: | `no test varies the platform` | error paths, platform branch | a test definition |
#: | `MUST include a code block` | `modify_files_have_excerpts` | a fenced excerpt |
#: | `MUST have at least one JSON/YAML/Python example` | `data_structures_have_examples` | a fenced example |
#: | `MUST have at least one example` | `functions_have_io_examples` | a fenced example |
#: | `Add the block inside that subsection` | `function_spec_sections_have_examples` | a fenced example |
#:
#: #2560 built this for tests because tests were the only demanded artifact
#: then. They are not now, and the regex encoded "an addition means a test" as
#: if it were a law. `check_modify_files_have_excerpts` fires on any spec
#: missing an excerpt -- a routine condition, not an exotic one -- and its
#: demand was covered by neither the named-content vocabulary (the path it
#: cites is absent from the draft BY DEFINITION, which is what it is
#: complaining about) nor this exemption.
#:
#: #2740 added the platform row. `check_error_path_coverage` has two branches
#: worded differently -- the exception branch says "owes each a test" and was
#: covered, the platform branch says "no test varies the platform" and was not,
#: and no other phrase here matches it incidentally. So the drafter could be
#: told to add a platform test, add one, and have the addition refused because
#: nothing in the round was recognised as demanding it: a complaint that could
#: be made and never satisfied.
#:
#: Enumerating phrasings by hand is what made that hole, and adding one more
#: phrase by hand would only postpone the next one.
#: `tests/unit/test_addition_demands_are_recognised.py` renders each check's
#: REAL complaint from the check's own code and asserts this pattern matches
#: it, so the list is now derived from the checks rather than trusted to agree
#: with them.
_ADDITION_DEMAND_RE = re.compile(
    r"\bhave no test\b"
    r"|\badd a test\b"
    r"|\bowes each a test\b"
    r"|\bno test varies the platform\b"
    r"|\bMUST include a code block\b"
    r"|\bMUST have at least one\b"
    r"|\bAdd the block inside that subsection\b",
    re.IGNORECASE,
)


def demands_additions(completeness_issues: list[str] | None) -> bool:
    """True when any current completeness failure demands new content (#2560).

    Widened past tests by #2591's operator ruling. Note this is only HALF the
    gate: `enforce_pinning` also requires the revised region to introduce the
    demanded artifact, and until #2591 that predicate was a test definition
    alone -- so widening this regex on its own changed nothing, measured. Both
    halves moved together.
    """
    return any(
        _ADDITION_DEMAND_RE.search(str(issue))
        for issue in completeness_issues or []
    )


def _introduces_demanded_artifact(
    new_region: list[str], prev_test_names: set[str]
) -> bool:
    """Does this region carry content a completeness check asked to be added?

    Two artifact classes, because our checks demand two (#2591):

    * a test definition the previous draft lacked -- #2560's original case;
    * an opening fence -- an excerpt, a data-structure example and an I/O
      example are all fenced code blocks.

    A fence is not name-checked against the previous draft the way a test is,
    because a fence has no name. That is a deliberately weaker test and it is
    bounded by the caller: this is consulted ONLY when the round's own
    completeness failures demanded an addition, and only for a region that
    would otherwise be refused outright. The alternative -- refusing the
    demanded excerpt -- is the deadlock this repairs.
    """
    for line in new_region:
        match = _TEST_DEF_RE.match(line)
        if match and match.group(1) not in prev_test_names:
            return True
        if _FENCE_OPEN_RE.match(line):
            return True
    return False


def _test_def_names(text: str) -> set[str]:
    names: set[str] = set()
    for line in text.splitlines():
        match = _TEST_DEF_RE.match(line)
        if match:
            names.add(match.group(1))
    return names


def _is_expansion(old_region: list[str], new_region: list[str]) -> bool:
    """Every old line survives, in order, inside the new region.

    Such a replace is an insertion wearing a replace costume — the differ
    bundled new content with untouched neighbours (a blank line, an anchor
    comment). No previous byte is lost, so pinning has nothing to protect:
    insertions pass, and this IS one (#2560 — run-issue331-111729's
    demanded error-path test landed only because its region happened to
    diff as a pure insert, while the REQ-8/9/10 additions died bundled).
    """
    iterator = iter(new_region)
    return all(line in iterator for line in old_region)


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
    additions_demanded: bool = False,
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

    ``additions_demanded`` (#2560): the round's completeness failures demand
    NEW tests ("have no test in the spec ... Add a test for each"). A demand
    to add has no line to cite and no existing content to name, so the
    named-content exemptions cannot cover it; instead, a locked region whose
    revised side introduces a test definition the previous draft lacks is
    the demanded compliance and passes. Off by default — an unprompted
    addition bundled into a locked modification stays refusable.

    The conservation gate (#2559): the walk's region rule is all-or-nothing
    — a region touching ANY named line passes wholesale — which is sound for
    targeted diffs and lossy for restructures. run-issue331-111729's
    iteration 6 diffed an eliding rewrite into giant regions; each touched
    some named line, so the elisions passed through and 18 test definitions
    vanished with no refusal and no regression event. So the way out is
    gated: if the walked output lost any test definition the previous draft
    held and no verdict named, the merge has malfunctioned — emit the
    revision unenforced when it still holds those tests (differ
    misalignment), or the previous draft entire when it does not (the
    revision itself removed them). Never the stitched result.
    """
    prev_lines = previous.splitlines()
    rev_lines = revised.splitlines()
    current_flags = named_line_flags(previous, current_tokens, current_ranges)
    ever_flags = (
        named_line_flags(previous, ever_tokens, current_ranges)
        if ever_tokens is not None else current_flags
    )
    prev_test_names = _test_def_names(previous)

    refusals: list[str] = []
    regressions: list[str] = []
    additions: list[str] = []
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
        new_region = rev_lines[j1:j2]
        # An expansion is an insertion wearing a replace costume: every old
        # line survives in order, so nothing pinning protects is touched.
        # No refusal, no regression — same law as the insert branch (#2560).
        if old_region and new_region and _is_expansion(old_region, new_region):
            out.extend(new_region)
            continue
        # The S2-regression class: this change touches lines NO verdict ever
        # named. Recorded before any restoration decision.
        if old_region and all(not ever_flags[i] for i in range(i1, i2)):
            regressions.append(_preview(old_region, i2 - i1))
        locked = old_region and all(
            not current_flags[i] for i in range(i1, i2)
        )
        if locked and not unlock_reason:
            if additions_demanded and _introduces_demanded_artifact(
                new_region, prev_test_names
            ):
                # The demanded compliance: this round's completeness
                # failures asked for an addition and this region carries one
                # the previous draft lacks (#2560, widened past tests by
                # #2591). The regression event above still fires —
                # visibility without destruction.
                out.extend(new_region)
                additions.append(_preview(new_region, j2 - j1))
            else:
                out.extend(old_region)  # byte-verbatim carry-forward
                refusals.append(_preview(old_region, i2 - i1))
        else:
            out.extend(rev_lines[j1:j2])

    text = "\n".join(out)
    if revised.endswith("\n") or previous.endswith("\n"):
        text += "\n"

    # Conservation gate (#2559). Skipped under an explicit unlock — the
    # drafter asked to restructure and owns the outcome; the grant is
    # logged, never silent.
    if not unlock_reason:
        override = _conservation_override(
            previous, revised, text,
            current_tokens=current_tokens,
            current_flags=current_flags,
            regressions=tuple(regressions),
        )
        if override is not None:
            return override

    return PinningResult(
        text=text,
        refusals=tuple(refusals),
        regressions=tuple(regressions),
        additions=tuple(additions),
        unlock_reason=unlock_reason,
    )


def _conservation_override(
    previous: str,
    revised: str,
    walked: str,
    *,
    current_tokens: set[str],
    current_flags: list[bool],
    regressions: tuple[str, ...] = (),
) -> PinningResult | None:
    """The way out of the merge is gated (#2559): None when conservation
    holds; otherwise the result to emit INSTEAD of the stitched text.

    A test definition the previous draft held is lost when it is absent
    from the walked output and no current verdict named it — neither as a
    token nor by flagging any of its definition lines. Tier one: the
    revision still holds every lost test (differ misalignment — a moved
    block the walk mispaired), emit the revision unenforced. Tier two: the
    revision lost them too (an eliding rewrite — run-issue331-111729's
    iteration 6 carried [UNCHANGED] placeholders where 18 definitions had
    been), emit the previous draft entire; abstaining to the revision
    there would lose exactly what the gate exists to keep.

    The merge can also MANUFACTURE duplicates — run-issue331-111729's
    iteration 2 restored a superseded test listing alongside the
    revision's moved copy, and the duplicate definitions later broke six
    edit-script SEARCH blocks as ambiguous. A name occurring more times in
    the walked output than in EITHER input was minted by the merge, never
    authored: emit the revision unenforced. (A count the revision itself
    carries is authored content — the fleet's spec template legitimately
    lists a test in both its change-instruction and test-mapping sections
    — and is not the merge's to judge.)
    """
    prev_lines = previous.splitlines()
    walked_names = _test_def_names(walked)
    lost = sorted(
        name for name in _test_def_names(previous)
        if name not in walked_names
        and name.lower() not in current_tokens
        and not any(
            current_flags[i]
            for i, line in enumerate(prev_lines)
            if (match := _TEST_DEF_RE.match(line))
            and match.group(1) == name
        )
    )
    if not lost:
        def _counts(text: str) -> dict[str, int]:
            counts: dict[str, int] = {}
            for line in text.splitlines():
                match = _TEST_DEF_RE.match(line)
                if match:
                    counts[match.group(1)] = counts.get(match.group(1), 0) + 1
            return counts

        prev_counts = _counts(previous)
        rev_counts = _counts(revised)
        multiplied = sorted(
            name for name, count in _counts(walked).items()
            if count > max(prev_counts.get(name, 0), rev_counts.get(name, 0))
        )
        if multiplied:
            return PinningResult(
                text=revised,
                regressions=regressions,
                conservation_event=(
                    f"the walked merge multiplied {len(multiplied)} test "
                    f"definition(s) beyond both inputs "
                    f"({', '.join(multiplied)}) -- emitting the revision "
                    f"unenforced instead of the stitched result"
                ),
            )
        return None
    if all(name in _test_def_names(revised) for name in lost):
        return PinningResult(
            text=revised,
            regressions=regressions,
            conservation_event=(
                f"the walked merge lost {len(lost)} test(s) present in "
                f"both inputs ({', '.join(lost)}) -- emitting the revision "
                f"unenforced instead of the stitched result"
            ),
        )
    return PinningResult(
        text=previous,
        regressions=regressions,
        conservation_event=(
            f"the revision removed {len(lost)} test(s) no verdict named "
            f"({', '.join(lost)}) -- revision refused entire, previous "
            f"draft kept"
        ),
    )
