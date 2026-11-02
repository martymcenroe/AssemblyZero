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
  manifest row ids, line-range citations (``lines 81-83``, #2555),
  ranges of numbered tests (``test_req_060 through test_req_130``, #4545),
  and Section references (``Section 5.1``, read through the heading
  numbered 5.1, #4552) — attributed to the draft's natural blocks (a test
  function, a markdown section).
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
  when the revision itself removed them, it emits the previous draft entire,
  loudly, never the stitched result. When the MERGE malfunctioned (it lost
  tests both inputs hold, or minted duplicates neither holds), it raises
  ``PinningMergeError`` and the drafter node halts (#3585); it used to emit
  the revision unenforced, the gate passing a round it could not judge.
* **Demanded additions** (#2560): when the round's completeness failures
  demand new tests, a locked region introducing one passes — a demand to
  add has no line to cite, so the named-content exemptions cannot cover it.
* **Answers to a named complaint** (#4551): a revised line that carries what
  the round's completeness failures name (a backticked span, a quoted
  phrase, a test name, a criterion's REQ tag) answers the complaint, and
  counts as named the way a line in a block the verdict names does. Naming
  read only the old lines, so a revision replacing locked lines with the
  test a failing check asked for was refused.

Iteration 1 (the initial draft) is untouched — this governs revisions only.
Every function here is pure (ADR 0224): text in, text and events out.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from assemblyzero.workflows.implementation_spec.criteria_coverage import REQ_TAG


class PinningMergeError(RuntimeError):
    """The pinning merge malfunctioned, so no revision can be held to it (#3585).

    Raised for a walked merge that lost tests both inputs hold (a differ
    misalignment) or that holds more copies of a test than either input.
    Neither is the drafter's doing, and emitting the revision unenforced, the
    old response, let the round pass without pinning.
    """

# ---------------------------------------------------------------------------
# What the verdict names
# ---------------------------------------------------------------------------

_BACKTICK_RE = re.compile(r"`([^`\n]{2,120})`")
_TEST_NAME_RE = re.compile(r"\btest_[A-Za-z0-9_]+\b")
_QUOTED_RE = re.compile(r"\"([^\"\n]{4,120})\"")
#: Manifest row ids (#2533) — a verdict citing N4.2 names that row's test.
_ROW_ID_RE = re.compile(r"\b[A-Z]\d{0,3}[a-z]?\.\d+\b")


def named_tokens(feedback: str, completeness_issues: list[str] | None = None) -> set[str]:
    """The identifiers a verdict actually points at, lowercased.

    A Section reference arrives as its canonical token (``section 5.1``),
    which ``named_line_flags`` resolves through the draft's numbered
    headings rather than as text (#4552).
    """
    text = (feedback or "") + "\n" + "\n".join(completeness_issues or [])
    tokens: set[str] = set()
    for pattern in (_BACKTICK_RE, _QUOTED_RE):
        tokens.update(m.group(1).strip() for m in pattern.finditer(text))
    for pattern in (_TEST_NAME_RE, _ROW_ID_RE):
        tokens.update(m.group(0).strip() for m in pattern.finditer(text))
    tokens.update(section_token(number) for number in section_references(text))
    return {t.lower() for t in tokens if len(t.strip()) >= 3}


# ---------------------------------------------------------------------------
# Section references (#4552)
# ---------------------------------------------------------------------------
#
# A reviewer names a spec section by its number ("update Section 5.1 to match
# the implementation in Section 6.3"), and the spec's heading carries that
# number with no word in front of it (``### 5.1 `validate_pack()` ``). Pinning
# read "Section 5.1" as a token and looked for it as text, so it named no
# block, the subsection the verdict asked to change stayed locked, and the
# drafter's compliant edit was refused while the objection came back. A
# Section reference is therefore resolved through the draft's numbered
# headings, never as text.
#
# The grammar is closed. A reference is exactly ``<marker> <number>``:
#
# | part | accepted forms | example |
# |---|---|---|
# | marker, word | ``section`` in any letter case, not preceded by a letter, digit or ``_``, then one or more whitespace characters | ``Section 5.1``, ``section 5.1``, ``SECTION 6`` |
# | marker, sign | ``§`` not preceded by another ``§``, then optional whitespace | ``§5.1``, ``§ 6`` |
# | number | one ASCII digit run (N), or two joined by one ``.`` (N.M) | ``6``, ``5.1``, ``10.2`` |
# | end | the end of the text, or a character that is neither a letter, digit or ``_`` nor a ``.`` followed by one | ``Section 5.1.``, ``Section 6.7's``, ``(Section 10)`` |
#
# Anything else is not a singular reference: a plural (``Sections 3.6 and
# 5.7``, ``§§5.1 and 5.2``), which the plural grammar below reads (#4554), a
# number of three parts (``Section 5.1.2``), a number running into a letter
# (``Section 5a``, ``Section 5.x``), a longer word ending in the marker word
# (``subsection 5.1``), and any marker word or sign not enumerated above.
#
# A heading's number is read by the same rules from the start of its text,
# with the marker optional and the number of any depth:
#
# | heading | its number |
# |---|---|
# | ``## 6. Change Instructions`` | 6 |
# | ``### 5.1 `validate_pack()` `` | 5.1 |
# | ``#### 5.1.2 Edge cases`` | 5.1.2 |
# | ``## Section 10 Tests``, ``## §10 Tests`` | 10 |
#
# A reference names the blocks from each heading carrying exactly its number
# up to the next heading of the same or a shallower level: Section 6 names
# everything under ``## 6.`` down to the next ``## ``, subsections included,
# and Section 5.1 names the ``### 5.1`` subsection, its fenced functions
# included. Headings inside a fence are code, not headings, as ``_blocks``
# reads them. A reference whose number no heading carries names nothing, and
# because it is never read as text, it cannot reach a block that merely
# mentions the section.
#
# Plural references (#4554)
# -------------------------
#
# Reviewers name several sections at once ("Update Sections 5.1 and 6.2 to
# ..."). The singular grammar reads none of them, so every line under both
# headings stayed locked and the edit the verdict asked for was refused, as
# the singular reference once was. A plural names every section a singular
# reference to each of its items would name, and nothing more: an item no
# heading carries names nothing, and no item names a test (#2559).
#
# The plural grammar is closed. A plural reference is exactly
# ``<plural marker> <list>``:
#
# | part | accepted forms | example |
# |---|---|---|
# | plural marker, word | ``sections`` in any letter case, not preceded by a letter, digit or ``_``, then one or more whitespace characters | ``Sections 5.1 and 6.2``, ``SECTIONS 5 and 6`` |
# | plural marker, sign | ``§§`` not preceded by another ``§``, then optional whitespace | ``§§5.1 and 6.2``, ``§§ 5 and 6`` |
# | item | a number as the singular grammar reads it, N or N.M, with the same end rule | ``5.1``, ``6``, ``10.2`` |
# | separator | ``,`` directly after an item, then one or more whitespace characters | ``5.1, 5.2`` |
# | conjunction | one or more whitespace characters, ``and`` in any letter case, then one or more whitespace characters | ``5.1 and 6.2`` |
# | list | two or more items: the last two joined by the conjunction, every earlier pair by the separator | ``5.1 and 6.2``, ``5.1, 5.2 and 6.2``, ``5.1, 5.2, 5.3 and 6.2`` |
# | end | the last item's end, where no separator or conjunction carries the list on to another item | ``Sections 5.1 and 6.2.``, ``Sections 5.1 and 6.2, which`` |
#
# Every other plural shape names nothing until it is added here on purpose:
#
# | refused shape | example |
# |---|---|
# | one item | ``Sections 5.1 cover it`` |
# | ``or`` | ``Sections 5.1 or 5.2`` |
# | ``&`` or ``/`` | ``Sections 5.1 & 5.2``, ``Sections 5.1/5.2`` |
# | a range, by dash or word | ``Sections 5.1-5.3``, ``Sections 5.1–5.3``, ``Sections 5.1 through 5.3``, ``Sections 5.1 to 5.3``, ``§§5.1–5.3`` |
# | a comma before the ``and`` | ``Sections 5.1, 5.2, and 6.2`` |
# | separators only | ``Sections 5.1, 5.2`` |
# | a conjunction between earlier items | ``Sections 5.1 and 5.2 and 6.2`` |
# | a list carried on past its last pair | ``Sections 5.1 and 5.2, 6.2`` |
# | a comma with no whitespace after it, or whitespace before it | ``Sections 5.1,5.2 and 6.2``, ``Sections 5.1 , 5.2 and 6.2`` |
# | an item of three parts, or running into a letter | ``Sections 5.1.2 and 6.2``, ``Sections 5a and 6`` |
# | a tripled sign | ``§§§5.1 and 6.2`` |
# | a longer word ending in the plural word | ``subsections 5.1 and 5.2`` |
# | no whitespace after the plural word | ``Sections5.1 and 6.2`` |
#
# Two shapes name less than they seem to, by the rules above. An item that
# carries its own marker ends the list, and the marked item is read as a
# singular reference on its own: ``Sections 5.1 and Section 6.2`` names 6.2
# only. The singular word before a list is a singular reference:
# ``Section 5.1 and 6.2`` names 5.1 only.

#: The words a reference may open with, compared in lower case.
SECTION_WORDS: tuple[str, ...] = ("section",)
#: The signs a reference may open with.
SECTION_SIGNS: tuple[str, ...] = ("§",)
#: How many dot-joined parts a reference's number may have: N or N.M.
SECTION_REFERENCE_PARTS: tuple[int, ...] = (1, 2)
#: The words a plural reference may open with, compared in lower case (#4554).
SECTION_PLURAL_WORDS: tuple[str, ...] = ("sections",)
#: The signs a plural reference may open with (#4554).
SECTION_PLURAL_SIGNS: tuple[str, ...] = ("§§",)
#: What joins a plural's items before its last pair: written directly after
#: an item, then whitespace (#4554).
SECTION_LIST_SEPARATORS: tuple[str, ...] = (",",)
#: What joins a plural's last two items, with whitespace on both sides,
#: compared in lower case (#4554).
SECTION_LIST_CONJUNCTIONS: tuple[str, ...] = ("and",)

_ASCII_DIGITS = frozenset("0123456789")


def _is_word_char(char: str) -> bool:
    return char.isalnum() or char == "_"


def _skip_whitespace(text: str, pos: int) -> int:
    """The first position at or after ``pos`` that is not whitespace."""
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


def _read_number(text: str, pos: int) -> tuple[tuple[int, ...], int] | None:
    """The dot-joined ASCII digit runs starting at ``pos``, and where they end.

    None when no digit starts at ``pos``, or when the number runs into a
    letter, digit or ``_``, or into a ``.`` followed by one (``5a``,
    ``5.x``). A ``.`` followed by a digit joins the next part, so
    ``5.1.2`` is three parts, never ``5.1`` and a stray ``.2``.
    """
    length = len(text)
    index = pos
    parts: list[int] = []
    while index < length and text[index] in _ASCII_DIGITS:
        start = index
        while index < length and text[index] in _ASCII_DIGITS:
            index += 1
        parts.append(int(text[start:index]))
        if (
            index + 1 < length
            and text[index] == "."
            and text[index + 1] in _ASCII_DIGITS
        ):
            index += 1
            continue
        break
    if not parts:
        return None
    if index < length:
        following = text[index]
        if _is_word_char(following):
            return None
        if (
            following == "."
            and index + 1 < length
            and _is_word_char(text[index + 1])
        ):
            return None
    return tuple(parts), index


def _read_marker(text: str, pos: int) -> int | None:
    """Where the number after a marker at ``pos`` starts, or None."""
    for word in SECTION_WORDS:
        end = pos + len(word)
        if text[pos:end].lower() != word:
            continue
        if pos > 0 and _is_word_char(text[pos - 1]):
            return None
        after = end
        while after < len(text) and text[after].isspace():
            after += 1
        return after if after > end else None
    for sign in SECTION_SIGNS:
        end = pos + len(sign)
        if text[pos:end] != sign:
            continue
        if text[:pos].endswith(SECTION_SIGNS):
            return None  # a doubled sign opens a plural, read on its own
        while end < len(text) and text[end].isspace():
            end += 1
        return end
    return None


def _read_reference(text: str, pos: int) -> tuple[tuple[int, ...], int] | None:
    """The number of the reference starting at ``pos`` and where it ends."""
    after = _read_marker(text, pos)
    if after is None:
        return None
    return _read_item(text, after)


def _read_item(text: str, pos: int) -> tuple[tuple[int, ...], int] | None:
    """A reference's number starting at ``pos`` (N or N.M) and where it ends."""
    number = _read_number(text, pos)
    if number is None or len(number[0]) not in SECTION_REFERENCE_PARTS:
        return None
    return number


def _read_plural_marker(text: str, pos: int) -> int | None:
    """Where the first item after a plural marker at ``pos`` starts, or None."""
    for word in SECTION_PLURAL_WORDS:
        end = pos + len(word)
        if text[pos:end].lower() != word:
            continue
        if pos > 0 and _is_word_char(text[pos - 1]):
            return None
        after = _skip_whitespace(text, end)
        return after if after > end else None
    for sign in SECTION_PLURAL_SIGNS:
        end = pos + len(sign)
        if text[pos:end] != sign:
            continue
        if text[:pos].endswith(SECTION_SIGNS):
            return None  # a tripled sign is not enumerated
        return _skip_whitespace(text, end)
    return None


def _read_separator(text: str, pos: int) -> int | None:
    """Where the next item starts after a separator at ``pos``, or None.

    The separator sits directly after the item it follows, and whitespace
    follows it.
    """
    for separator in SECTION_LIST_SEPARATORS:
        end = pos + len(separator)
        if text[pos:end] != separator:
            continue
        after = _skip_whitespace(text, end)
        return after if after > end else None
    return None


def _read_conjunction(text: str, pos: int) -> int | None:
    """Where the next item starts after a conjunction at ``pos``, or None.

    Whitespace comes before the conjunction and after it.
    """
    start = _skip_whitespace(text, pos)
    if start == pos:
        return None
    for conjunction in SECTION_LIST_CONJUNCTIONS:
        end = start + len(conjunction)
        if text[start:end].lower() != conjunction:
            continue
        after = _skip_whitespace(text, end)
        return after if after > end else None
    return None


def _read_plural_reference(
    text: str, pos: int
) -> tuple[tuple[tuple[int, ...], ...], int] | None:
    """The item numbers of the plural reference at ``pos`` and where it ends.

    None for every shape the plural grammar does not enumerate: one item,
    a joiner that is neither the separator nor the conjunction, a list that
    never reaches its conjunction, a separator or conjunction with no item
    after it, and a list a joiner carries on past its last pair (#4554).
    """
    start = _read_plural_marker(text, pos)
    if start is None:
        return None
    item = _read_item(text, start)
    if item is None:
        return None
    numbers = [item[0]]
    index = item[1]
    while True:
        after = _read_separator(text, index)
        last = after is None  # no separator: only the conjunction may follow
        if after is None:
            after = _read_conjunction(text, index)
        if after is None:
            return None
        item = _read_item(text, after)
        if item is None:
            return None
        numbers.append(item[0])
        index = item[1]
        if last:
            break
    for joiner in (_read_separator, _read_conjunction):
        after = joiner(text, index)
        if after is not None and _read_item(text, after) is not None:
            return None  # the list carries on past its last pair
    return tuple(numbers), index


def section_references(text: str) -> tuple[tuple[int, ...], ...]:
    """Every section number the text references, in order, each once.

    ``"Update Section 5.1 to match §6.3."`` is ``((5, 1), (6, 3))``, and
    ``"Update Sections 5.1 and 6.2."`` is ``((5, 1), (6, 2))`` (#4554).
    """
    found: list[tuple[int, ...]] = []
    text = text or ""
    for pos in range(len(text)):
        numbers: tuple[tuple[int, ...], ...] = ()
        reference = _read_reference(text, pos)
        if reference is not None:
            numbers = (reference[0],)
        else:
            plural = _read_plural_reference(text, pos)
            if plural is not None:
                numbers = plural[0]
        for number in numbers:
            if number not in found:
                found.append(number)
    return tuple(found)


def section_token(number: tuple[int, ...]) -> str:
    """The canonical token for a section number: ``section 5.1``."""
    return "section " + ".".join(str(part) for part in number)


def section_token_number(token: str) -> tuple[int, ...] | None:
    """The section number a token is, when the whole token is one reference.

    ``section 5.1`` and ``§5.1`` are ``(5, 1)``; a quoted phrase that merely
    holds a reference (``update section 5.1 first``) is None, and stays an
    ordinary token matched as text.
    """
    text = (token or "").strip()
    reference = _read_reference(text, 0)
    if reference is None or reference[1] != len(text):
        return None
    return reference[0]


def section_token_numbers(token: str) -> tuple[tuple[int, ...], ...]:
    """The section numbers a token is, when the whole token is one reference.

    A singular reference is its one number, and a plural (``sections 5.1
    and 6.2``, quoted or backticked whole) is each of its items (#4554).
    Every reader that keeps Section tokens away from text matching asks
    this, so a plural is never matched as text either. A token that merely
    holds a reference, or holds none, is ``()`` and stays an ordinary token.
    """
    text = (token or "").strip()
    single = section_token_number(text)
    if single is not None:
        return (single,)
    plural = _read_plural_reference(text, 0)
    if plural is None or plural[1] != len(text):
        return ()
    return plural[0]


def heading_number(heading: str) -> tuple[int, ...] | None:
    """The number a heading's text opens with, or None.

    ``6. Change Instructions`` is ``(6,)``, ``5.1 `validate_pack()` `` is
    ``(5, 1)`` and ``Section 10 Tests`` is ``(10,)``. The marker is
    optional here and the number may have any depth.
    """
    text = (heading or "").strip()
    start = _read_marker(text, 0)
    number = _read_number(text, 0 if start is None else start)
    return None if number is None else number[0]


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
# Lines that answer a named completeness complaint (#4551)
# ---------------------------------------------------------------------------
#
# Naming reads the PREVIOUS draft: a block is named when a token the round
# names appears in it. A completeness check that asks for something the draft
# lacks names a criterion, an exception or a function the old lines need not
# carry, so the revised lines that answer it could replace locked lines and be
# refused. On a real TypeScript run, `criteria_have_tests` named the same eight
# criteria on every revision while pinning refused revision content beside
# them. A revised line that carries what the complaint names is the answer to
# it, and counts as named: it is not refused and it is not the regression
# class, the same rule as a line range a check cites (#2555).


@dataclass(frozen=True)
class ComplaintAnswers:
    """What this round's completeness failures name, as a revised line can
    carry it (#4551): the tokens `named_tokens` reads from them, and the
    criterion keys (``REQ-6``) they list."""

    tokens: frozenset[str] = frozenset()
    keys: frozenset[str] = frozenset()

    def answered_by(self, lines: list[str]) -> bool:
        """Whether any of ``lines`` carries a token or cites a key. A key is
        matched as a tag, so REQ-6 is not answered by REQ-60."""
        for line in lines:
            lower = line.lower()
            if any(token in lower for token in self.tokens):
                return True
            if any(f"REQ-{n}" in self.keys for n in REQ_TAG.findall(line)):
                return True
        return False


def complaint_answers(completeness_issues: list[str] | None) -> ComplaintAnswers:
    """The answers vocabulary of the round's completeness failures (#4551).

    A Section reference token is left out (#4552), a plural one included
    (#4554): it names the section's blocks through their heading, and a
    revised line elsewhere that merely mentions the section answers nothing.
    """
    issues = [str(issue) for issue in completeness_issues or []]
    return ComplaintAnswers(
        tokens=frozenset(
            token for token in named_tokens("", issues)
            if not section_token_numbers(token)
        ),
        keys=frozenset(
            f"REQ-{n}" for issue in issues for n in REQ_TAG.findall(issue)
        ),
    )


# ---------------------------------------------------------------------------
# Ranges of numbered tests (#4545)
# ---------------------------------------------------------------------------
#
# A reviewer asked a drafter to remove the tests it named as "test_req_060
# through test_req_130". The drafter did; the conservation gate (#2559) read
# only the two endpoint names, counted the six tests between them as removed
# with no verdict naming them, and refused the revision three times until the
# run halted. A range is a way of naming, so it names.
#
# The grammar is closed: a regex here reads syntax from a finite, authored set
# of forms and decides nothing else. A range is exactly
#
#     <endpoint> <joiner> <endpoint>
#
# where both endpoints have the same prefix and the first number is not
# greater than the second, and:
#
# | part | accepted forms | example |
# |---|---|---|
# | endpoint, test name | ``test_``, letters and underscores (the prefix), a digit run (the number), then nothing or ``_`` and more | ``test_req_060``, ``test_req_060_typescript_compilation``, ``test_t060``, ``test_060`` |
# | endpoint, T-style id | ``T`` and a digit run; its prefix is ``test_t``, because the fleet names T060's test ``test_t060_...`` | ``T060`` |
# | endpoint, in backticks (#4549) | either form above inside one pair of single backticks, each endpoint on its own | `` `test_req_060` through `test_req_130` ``, `` `T060`–`T130` `` |
# | joiner, word | ``through``, ``to``, with whitespace on both sides | ``T060 to T130`` |
# | joiner, dash | a hyphen or an en dash, whitespace optional | ``test_req_060-test_req_130``, ``T060 – T130`` |
#
# A whole range inside one code span (`` `T060 to T130` ``) reads as the bare
# form, because a backtick is not an identifier character. #4549 added the
# backticked endpoint: a Markdown verdict names code in backticks, and a
# reviewer wrote "Functions `test_req_060` through `test_req_130`", which the
# grammar refused because a backtick, not the joiner, followed the first
# endpoint.
#
# Anything else is not a range: mixed prefixes (``test_req_060 through
# T130``), a reversed span, other joiners (``and``, ``until``), other
# identifier shapes (``REQ-060``), an endpoint with an unpaired backtick next
# to the joiner, and an endpoint in double backticks; backticks change none
# of these. A T-style range names only tests whose
# names carry the T number; it does not reach a ``test_req_`` test through a
# mapping table, because the table is the draft's prose and not the verdict's
# naming.

#: The joiners a range may use, enumerated (#4545). Words need whitespace on
#: both sides; a dash may stand bare.
RANGE_WORD_JOINERS: tuple[str, ...] = ("through", "to")
RANGE_DASH_JOINERS: tuple[str, ...] = ("-", "–")  # hyphen, en dash

#: The prefix a T-style id stands for: T060 is the test named test_t060_...
T_ID_PREFIX = "test_t"

#: A numbered test name, whole: prefix, number, optional ``_`` tail.
_NUMBERED_TEST_RE = re.compile(r"(test_[A-Za-z_]*)(\d+)(?:_[A-Za-z0-9_]*)?")
#: A T-style id, whole.
_T_ID_RE = re.compile(r"T(\d+)")

_ENDPOINT = r"(?:test_[A-Za-z_]*\d+(?:_[A-Za-z0-9_]*)?|T\d+)"
_JOINER = (
    r"(?:\s+(?:" + "|".join(RANGE_WORD_JOINERS) + r")\s+"
    r"|\s*[" + "".join(re.escape(d) for d in RANGE_DASH_JOINERS) + r"]\s*)"
)
#: An endpoint, bare or in one pair of single backticks (#4549). The
#: conditional group closes a backtick only when one opened, so an unpaired
#: backtick beside the joiner is not a range, as before.
_FIRST = r"(?P<open1>`)?(?P<first>" + _ENDPOINT + r")(?(open1)`)"
_LAST = r"(?P<open2>`)?(?P<last>" + _ENDPOINT + r")(?(open2)`)"
_TEST_RANGE_RE = re.compile(
    r"(?<![A-Za-z0-9_])" + _FIRST + _JOINER + _LAST + r"(?![A-Za-z0-9_])"
)


def numbered_test(identifier: str) -> tuple[str, int] | None:
    """(prefix, number) of a numbered test identifier, or None.

    ``test_req_070_single_turn`` is ``("test_req_", 70)``; ``T070`` is
    ``("test_t", 70)``, the same as ``test_t070_reset``. A name with no
    digit run, or whose digit run is not followed by ``_`` or the end
    (``test_2fa_login``), carries no number.
    """
    t_id = _T_ID_RE.fullmatch(identifier)
    if t_id is not None:
        return T_ID_PREFIX, int(t_id.group(1))
    name = _NUMBERED_TEST_RE.fullmatch(identifier)
    if name is None:
        return None
    return name.group(1).lower(), int(name.group(2))


@dataclass(frozen=True)
class NumberedRange:
    """A span of numbered tests a verdict named by its endpoints (#4545)."""

    prefix: str
    first: int
    last: int

    def names(self, identifier: str) -> bool:
        numbered = numbered_test(identifier)
        return (
            numbered is not None
            and numbered[0] == self.prefix
            and self.first <= numbered[1] <= self.last
        )


def named_test_ranges(
    feedback: str, completeness_issues: list[str] | None = None
) -> tuple[NumberedRange, ...]:
    """Every range of numbered tests the verdict and complaints name."""
    text = (feedback or "") + "\n" + "\n".join(completeness_issues or [])
    ranges: list[NumberedRange] = []
    for match in _TEST_RANGE_RE.finditer(text):
        start = numbered_test(match.group("first"))
        end = numbered_test(match.group("last"))
        if start is None or end is None:
            continue
        if start[0] != end[0] or start[1] > end[1]:
            continue
        span = NumberedRange(start[0], start[1], end[1])
        if span not in ranges:
            ranges.append(span)
    return tuple(ranges)


def range_named_tests(
    draft: str, feedback: str, completeness_issues: list[str] | None = None
) -> set[str]:
    """The draft's test names that a named range covers, lowercased (#4545).

    These join the round's named tokens, so a range names each test inside
    it exactly as listing that test by name would: the conservation gate
    lets it go, and its blocks are named for pinning. A test outside every
    range, or a range the grammar above does not accept, names nothing.
    """
    ranges = named_test_ranges(feedback, completeness_issues)
    if not ranges:
        return set()
    return {
        name.lower()
        for name in _TEST_NAME_RE.findall(draft or "")
        if any(span.names(name) for span in ranges)
    }


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


def section_spans(
    draft: str, numbers: set[tuple[int, ...]] | frozenset[tuple[int, ...]]
) -> tuple[tuple[int, int], ...]:
    """0-based ``[start, end)`` line spans of the sections ``numbers`` name.

    Each span runs from a heading carrying one of ``numbers`` (read by
    ``heading_number``) to the next heading of the same or a shallower
    level, or to the end of the draft (#4552). Headings inside a fence are
    skipped, as ``_blocks`` skips them, so every span is a run of whole
    blocks. A number no heading carries contributes no span.
    """
    if not numbers:
        return ()
    lines = (draft or "").splitlines()
    headings: list[tuple[int, int, tuple[int, ...] | None]] = []
    in_fence = False
    for index, line in enumerate(lines):
        if _FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(line)
        if match:
            level = len(line) - len(line.lstrip("#"))
            headings.append((index, level, heading_number(match.group(1))))
    spans: list[tuple[int, int]] = []
    for position, (index, level, number) in enumerate(headings):
        if number is None or number not in numbers:
            continue
        end = next(
            (
                later
                for later, later_level, _ in headings[position + 1:]
                if later_level <= level
            ),
            len(lines),
        )
        spans.append((index, end))
    return tuple(spans)


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

    A Section reference token (``section 5.1``, or a whole plural such as
    ``sections 5.1 and 6.2``, #4554) is the exception to text matching
    (#4552): it names the blocks of each section whose heading carries one
    of its numbers (``section_spans``), and nothing for a number no heading
    carries. It is never looked for as text, so a block that only mentions
    the section stays locked.
    """
    lines = draft.splitlines()
    flags = [False] * len(lines)
    if not tokens and not ranges:
        return flags
    text_tokens: set[str] = set()
    sections: set[tuple[int, ...]] = set()
    for token in tokens:
        numbers = section_token_numbers(token)
        if numbers:
            sections.update(numbers)
        else:
            text_tokens.add(token)
    spans = section_spans(draft, sections)
    for block in _blocks(draft):
        block_lower = block.text.lower()
        name_lower = block.name.lower()
        named = any(
            token in name_lower or token in block_lower for token in text_tokens
        ) or any(
            # 1-based inclusive (start, end) vs 0-based [block.start, block.end)
            start - 1 < block.end and block.start < end
            for start, end in ranges
        ) or any(
            # 0-based [start, end) vs 0-based [block.start, block.end)
            start < block.end and block.start < end
            for start, end in spans
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
    #: Locked regions passed through because the revised lines answer a named
    #: completeness complaint (#4551).
    answers: tuple[str, ...] = ()
    #: Non-empty when the conservation gate overrode the merge (#2559): the
    #: revision itself removed tests no verdict named, so ``text`` is the
    #: previous draft entire. A merge malfunction raises PinningMergeError
    #: instead (#3585); it used to set this and emit the revision unenforced.
    conservation_event: str = ""
    #: The tests that conservation event names, so the drafter can be told
    #: which ones to keep (#4545). Empty exactly when the event is.
    conservation_lost: tuple[str, ...] = ()
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
    complaint: ComplaintAnswers | None = None,
) -> PinningResult:
    """Carry every unnamed span of ``previous`` forward byte-verbatim.

    Walks the line diff. A changed region whose OLD lines are all outside the
    verdict's named blocks is locked: the old lines are restored and the
    attempt recorded as a refusal. Regions that touch any named line pass
    through — restructuring AROUND a named item is the named item's business.
    Insertions pass through: adding is not un-fixing.

    ``complaint`` (#4551) is what the CURRENT completeness failures name
    (``complaint_answers``). A locked region whose REVISED lines carry it
    answers a named complaint and counts as named: it passes, it is never a
    refusal and never the regression class, as a cited line range is not.

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
    held and no verdict named, emit the previous draft entire when the
    revision lacks those tests too (the revision itself removed them). When
    the revision still holds them, the merge itself malfunctioned (differ
    misalignment) and this raises (#3585). Never the stitched result.

    Raises:
        PinningMergeError: the walked merge lost tests both inputs hold, or
            multiplied a test beyond both inputs (#3585). Both used to emit
            the revision unenforced.
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
    answers: list[str] = []
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
        # #4551: revised lines that answer a named completeness complaint
        # count as named, so they are neither refused nor the regression
        # class -- the rule a cited line range already has (#2555).
        answers_complaint = bool(
            complaint is not None and complaint.answered_by(new_region)
        )
        # The S2-regression class: this change touches lines NO verdict ever
        # named. Recorded before any restoration decision.
        if (
            old_region and not answers_complaint
            and all(not ever_flags[i] for i in range(i1, i2))
        ):
            regressions.append(_preview(old_region, i2 - i1))
        locked = old_region and all(
            not current_flags[i] for i in range(i1, i2)
        )
        if locked and not unlock_reason:
            if answers_complaint:
                out.extend(new_region)
                answers.append(_preview(new_region, j2 - j1))
            elif additions_demanded and _introduces_demanded_artifact(
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
    # logged, never silent. A Section reference opens its section's lines
    # to revision but names none of the tests under it (#4552): a test is
    # let go only by its name, a range, or a block other naming reaches, so
    # "fix Section 10.1" never licenses dropping every test 10.1 holds.
    if not unlock_reason:
        text_tokens = {
            token for token in current_tokens
            if not section_token_numbers(token)
        }
        override = _conservation_override(
            previous, revised, text,
            current_tokens=current_tokens,
            current_flags=(
                current_flags if len(text_tokens) == len(current_tokens)
                else named_line_flags(previous, text_tokens, current_ranges)
            ),
            regressions=tuple(regressions),
        )
        if override is not None:
            return override

    return PinningResult(
        text=text,
        refusals=tuple(refusals),
        regressions=tuple(regressions),
        additions=tuple(additions),
        answers=tuple(answers),
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
    token nor by flagging any of its definition lines. The caller's
    ``current_flags`` leave Section references out (#4552), so a verdict
    naming the section a test sits in does not name the test. A test inside a range
    the verdict names (``test_req_060 through test_req_130``) arrives here
    as a token: the caller adds ``range_named_tests`` to ``current_tokens``
    (#4545). Tier one: the
    revision still holds every lost test (differ misalignment — a moved
    block the walk mispaired): the merge malfunctioned, and this raises
    (#3585). Tier two: the revision lost them too (an eliding rewrite —
    run-issue331-111729's iteration 6 carried [UNCHANGED] placeholders where
    18 definitions had been), emit the previous draft entire; abstaining to
    the revision there would lose exactly what the gate exists to keep.

    The merge can also MANUFACTURE duplicates — run-issue331-111729's
    iteration 2 restored a superseded test listing alongside the
    revision's moved copy, and the duplicate definitions later broke six
    edit-script SEARCH blocks as ambiguous. A name occurring more times in
    the walked output than in EITHER input was minted by the merge, never
    authored: this raises too (#3585). (A count the revision itself
    carries is authored content — the fleet's spec template legitimately
    lists a test in both its change-instruction and test-mapping sections
    — and is not the merge's to judge.)

    Both raises used to return the revision unenforced, which let the round
    through without pinning: a gate that could not run, read as a pass.
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
            raise PinningMergeError(
                f"the walked merge multiplied {len(multiplied)} test "
                f"definition(s) beyond both inputs ({', '.join(multiplied)}), "
                f"so the revision cannot be held to its pinning; it is not "
                f"emitted unenforced (#3585)"
            )
        return None
    if all(name in _test_def_names(revised) for name in lost):
        raise PinningMergeError(
            f"the walked merge lost {len(lost)} test(s) present in both "
            f"inputs ({', '.join(lost)}), a differ misalignment, so the "
            f"revision cannot be held to its pinning; it is not emitted "
            f"unenforced (#3585)"
        )
    return PinningResult(
        text=previous,
        regressions=regressions,
        conservation_lost=tuple(lost),
        conservation_event=(
            f"the revision removed {len(lost)} test(s) no verdict named "
            f"({', '.join(lost)}) -- revision refused entire, previous "
            f"draft kept"
        ),
    )
