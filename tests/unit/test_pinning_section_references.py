"""A verdict's "Section 5.1" names the block under the heading numbered 5.1 (#4552).

The shape is a real implementation-spec run, made generic. The reviewer told
the drafter to update Section 5.1 to match the implementation in Section 6.3,
and to change what Section 6.7 said. The drafter made both edits and pinning
(#2532) refused both: it read "Section 5.1" as a token and looked for it as
text, and a spec heading reads ``### 5.1 `name()` ``, never "Section 5.1", so
the reference named no block and every line under the heading stayed locked.
The same objection came back, and the run spent its cap on it.

* T1 (R1): "Section 5.1" names the ``### 5.1`` subsection, whatever its
  heading says after the number, so the revision it asked for passes with no
  refusal and no regression event.
* T2 (R2): "Section 6" names every block from ``## 6.`` to the next ``## ``,
  subsections included, and leaves ``### 7.1`` locked.
* T3 (R3): a reference whose number no heading carries names nothing, so an
  unrelated edit is still refused.

The reference grammar is closed, and ``TestTheReferenceGrammar`` enumerates
it: each accepted form, and the forms that are not references. Plurals
("Sections 3.6 and 5.7") are read by the plural grammar #4554 added, and
``test_pinning_plural_section_references.py`` enumerates that one.
"""

from __future__ import annotations

import importlib

import pytest

from assemblyzero.workflows.implementation_spec import revision_pinning as rp
from assemblyzero.workflows.implementation_spec.message_addressability import (
    ADDRESSED,
    UNADDRESSABLE,
    addresses_draft,
)

# `nodes/__init__` re-exports the FUNCTION generate_spec, which shadows the
# module of the same name, so the module is imported by its dotted path.
gs = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.nodes.generate_spec"
)

# ---------------------------------------------------------------------------
# The observed shape, generic
# ---------------------------------------------------------------------------

#: The two edge-case lines the verdict asked to bring in line with 6.3.
EDGE_LOW = "- A row at turn 0 raises AssertionError('row turn 0 is before the first turn')"
EDGE_HIGH = "- A row past the last turn raises AssertionError('row turn 9 is past the last turn')"
EDGE_LOW_FIXED = "- A row at turn 0 raises AssertionError(f'row[{idx}]: turn {t} out of bounds')"
EDGE_HIGH_FIXED = "- A row past the last turn raises AssertionError(f'row[{idx}]: turn {t} out of bounds')"

#: The 6.2 line a reviewer asked to replace with an explicit diff.
NO_CHANGES = "No changes required to the request handler."
WITH_DIFF = "Export `settle_rows` so the replay test can import it."

#: An unrelated line no verdict here names.
PATTERN_LINE = "Validate every row before the ledger folds it."
PATTERN_LINE_EDITED = "Validate each row once, before the ledger folds it."

PREVIOUS = f"""# Implementation Spec: 42 - Ledger row bounds

## 1. Overview

Bound every ledger row's turn.

## 5. Function Specifications

### 5.1 `validate_rows()`

**Edge cases:**

{EDGE_LOW}
{EDGE_HIGH}

### 5.2 `settle_rows()`

Settles each row against its actuals.

## 6. Change Instructions

### 6.1 `src/ledger.py` (Modify)

Add the bounds check.

### 6.2 `src/handler.py` (Modify)

{NO_CHANGES}

### 6.3 `src/bounds.py` (Add)

```python
def validate_rows(rows, turns):
    for idx, row in enumerate(rows):
        t = row["turn"]
        assert 1 <= t < turns, f"row[{{idx}}]: turn {{t}} out of bounds"
```

## 7. Pattern References

### 7.1 Row validation pattern

{PATTERN_LINE}

## 10. Test Mapping

### 10.1 Per-criterion test functions

```python
def test_req_010_rejects_turn_zero():
    assert True
```
"""

VERDICT_51 = (
    "- The edge cases in Section 5.1 raise messages that differ from the "
    "implementation in Section 6.3. Update Section 5.1 to match Section 6.3."
)


def _revise(text: str, *pairs: tuple[str, str]) -> str:
    for old, new in pairs:
        assert old in text, old
        text = text.replace(old, new)
    return text


def _line_index(text: str, line: str) -> int:
    return text.splitlines().index(line)


def _heading_span(text: str, heading: str, next_heading: str) -> range:
    lines = text.splitlines()
    return range(lines.index(heading), lines.index(next_heading))


# ---------------------------------------------------------------------------
# T1 (R1): Section N.M names the block opened by the heading numbered N.M
# ---------------------------------------------------------------------------


class TestASubsectionReferenceNamesItsHeading:
    """AC1: which blocks a numbered subsection reference names."""

    def test_the_revision_the_verdict_asked_for_passes(self):
        """T1. Fails on main: the 5.1 lines came back refused."""
        revised = _revise(
            PREVIOUS, (EDGE_LOW, EDGE_LOW_FIXED), (EDGE_HIGH, EDGE_HIGH_FIXED)
        )
        result = rp.enforce_pinning(
            PREVIOUS, revised, current_tokens=rp.named_tokens(VERDICT_51)
        )
        assert result.refusals == ()
        assert result.regressions == ()
        assert EDGE_LOW_FIXED in result.text
        assert EDGE_HIGH_FIXED in result.text
        assert result.text == revised

    def test_it_passes_through_the_real_call_site(self, capsys):
        """T1 again, through the drafter node's own pinning call."""
        revised = _revise(
            PREVIOUS, (EDGE_LOW, EDGE_LOW_FIXED), (EDGE_HIGH, EDGE_HIGH_FIXED)
        )
        text, events = gs._apply_pinning(
            {}, PREVIOUS, revised,
            response="", review_feedback=VERDICT_51, completeness_issues=[],
        )
        capsys.readouterr()
        assert text == revised
        assert not any("refused" in event for event in events), events
        assert not any("REGRESSION CLASS" in event for event in events), events

    def test_the_other_change_instruction_the_run_refused_passes(self):
        """The run's second refusal: a "No changes required" line under a
        numbered change instruction the verdict named by number."""
        verdict = "Provide an explicit diff in Section 6.2 exporting `settle_rows`."
        revised = _revise(PREVIOUS, (NO_CHANGES, WITH_DIFF))
        result = rp.enforce_pinning(
            PREVIOUS, revised, current_tokens=rp.named_tokens(verdict)
        )
        assert result.refusals == ()
        assert WITH_DIFF in result.text

    def test_the_heading_text_after_the_number_does_not_matter(self):
        flags = rp.named_line_flags(PREVIOUS, rp.named_tokens(VERDICT_51))
        for index in _heading_span(
            PREVIOUS, "### 5.1 `validate_rows()`", "### 5.2 `settle_rows()`"
        ):
            assert flags[index], PREVIOUS.splitlines()[index]

    def test_the_subsection_holds_its_fenced_functions(self):
        """``_blocks`` splits a fence per def; Section 6.3 names them too."""
        flags = rp.named_line_flags(PREVIOUS, rp.named_tokens("See Section 6.3."))
        for index in _heading_span(
            PREVIOUS, "### 6.3 `src/bounds.py` (Add)", "## 7. Pattern References"
        ):
            assert flags[index], PREVIOUS.splitlines()[index]

    def test_a_sibling_the_verdict_never_names_stays_locked(self):
        flags = rp.named_line_flags(PREVIOUS, rp.named_tokens(VERDICT_51))
        for index in _heading_span(
            PREVIOUS, "### 5.2 `settle_rows()`", "## 6. Change Instructions"
        ):
            assert not flags[index], PREVIOUS.splitlines()[index]
        assert not flags[_line_index(PREVIOUS, NO_CHANGES)]
        assert not flags[_line_index(PREVIOUS, PATTERN_LINE)]

    def test_a_sibling_edit_is_still_refused(self):
        revised = _revise(
            PREVIOUS,
            (EDGE_LOW, EDGE_LOW_FIXED),
            ("Settles each row against its actuals.", "Settles rows."),
        )
        result = rp.enforce_pinning(
            PREVIOUS, revised, current_tokens=rp.named_tokens(VERDICT_51)
        )
        assert EDGE_LOW_FIXED in result.text
        assert "Settles each row against its actuals." in result.text
        assert len(result.refusals) == 1

    def test_a_block_that_only_mentions_the_section_stays_locked(self):
        """The reference is never read as text, so a block elsewhere that
        cites "Section 5.1" is not named by it."""
        previous = _revise(
            PREVIOUS, (PATTERN_LINE, PATTERN_LINE + " Section 5.1 lists the cases.")
        )
        flags = rp.named_line_flags(previous, rp.named_tokens("Update Section 5.1."))
        assert not flags[_line_index(previous, PATTERN_LINE + " Section 5.1 lists the cases.")]
        assert flags[_line_index(previous, EDGE_LOW)]

    def test_section_one_does_not_reach_section_ten(self):
        """A number names its own heading, never one it is a prefix of."""
        flags = rp.named_line_flags(PREVIOUS, rp.named_tokens("Section 1 is vague."))
        lines = PREVIOUS.splitlines()
        assert flags[lines.index("Bound every ledger row's turn.")]
        assert not flags[lines.index("### 10.1 Per-criterion test functions")]
        assert not any(flags[lines.index("## 5. Function Specifications"):])

    def test_a_completeness_failure_names_its_subsection_too(self):
        """R1 covers a completeness failure, read the same way."""
        revised = _revise(PREVIOUS, (EDGE_LOW, EDGE_LOW_FIXED))
        result = rp.enforce_pinning(
            PREVIOUS, revised,
            current_tokens=rp.named_tokens("", ["Section 5.1 has no example."]),
        )
        assert result.refusals == ()


# ---------------------------------------------------------------------------
# T2 (R2): Section N names every block under ## N., subsections included
# ---------------------------------------------------------------------------


class TestASectionReferenceNamesItsSubsections:
    """AC2: which blocks a whole-section reference names."""

    def test_section_six_names_its_subsections_and_not_seven(self):
        """T2."""
        flags = rp.named_line_flags(
            PREVIOUS, rp.named_tokens("Section 6 omits the handler export.")
        )
        for index in _heading_span(
            PREVIOUS, "## 6. Change Instructions", "## 7. Pattern References"
        ):
            assert flags[index], PREVIOUS.splitlines()[index]
        for index in _heading_span(
            PREVIOUS, "### 7.1 Row validation pattern", "## 10. Test Mapping"
        ):
            assert not flags[index], PREVIOUS.splitlines()[index]
        assert not flags[_line_index(PREVIOUS, EDGE_LOW)]

    def test_an_edit_under_six_passes_and_one_under_seven_is_refused(self):
        revised = _revise(
            PREVIOUS, (NO_CHANGES, WITH_DIFF), (PATTERN_LINE, PATTERN_LINE_EDITED)
        )
        result = rp.enforce_pinning(
            PREVIOUS, revised,
            current_tokens=rp.named_tokens("Section 6 omits the handler export."),
        )
        assert WITH_DIFF in result.text
        assert PATTERN_LINE in result.text
        assert PATTERN_LINE_EDITED not in result.text
        assert len(result.refusals) == 1

    def test_the_section_ends_at_a_heading_without_a_number(self):
        draft = PREVIOUS + "\n## Completeness Checklist\n\n- [x] Every row bounded.\n"
        flags = rp.named_line_flags(draft, rp.named_tokens("Section 10 is thin."))
        lines = draft.splitlines()
        assert flags[lines.index("def test_req_010_rejects_turn_zero():")]
        assert not flags[lines.index("- [x] Every row bounded.")]


# ---------------------------------------------------------------------------
# T3 (R3): a reference no heading carries names nothing
# ---------------------------------------------------------------------------


class TestAnUnmatchedReferenceNamesNothing:
    """AC3: what an unmatched reference names."""

    def test_an_unrelated_edit_stays_refused(self):
        """T3."""
        revised = _revise(PREVIOUS, (PATTERN_LINE, PATTERN_LINE_EDITED))
        result = rp.enforce_pinning(
            PREVIOUS, revised,
            current_tokens=rp.named_tokens("Section 9.9 is missing its diff."),
        )
        assert PATTERN_LINE in result.text
        assert PATTERN_LINE_EDITED not in result.text
        assert len(result.refusals) == 1

    def test_it_never_widens_to_the_whole_draft(self):
        flags = rp.named_line_flags(
            PREVIOUS, rp.named_tokens("Section 9.9 is missing its diff.")
        )
        assert not any(flags)

    def test_a_mention_in_the_text_does_not_stand_in_for_a_heading(self):
        previous = _revise(PREVIOUS, (PATTERN_LINE, PATTERN_LINE + " See Section 9.9."))
        flags = rp.named_line_flags(previous, rp.named_tokens("Fix Section 9.9."))
        assert not any(flags)


# ---------------------------------------------------------------------------
# The closed grammar, enumerated
# ---------------------------------------------------------------------------


class TestTheReferenceGrammar:
    """Every accepted form, and the forms that are not references."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Update Section 5.1 now", ((5, 1),)),
            ("update section 5.1 now", ((5, 1),)),
            ("SECTION 6 is thin", ((6,),)),
            ("Section\t5.1", ((5, 1),)),
            ("see §5.1", ((5, 1),)),
            ("see § 6", ((6,),)),
            ("as Section 10.2.", ((10, 2),)),
            ("Section 6.7's line", ((6, 7),)),
            ("(Section 10)", ((10,),)),
            ("`Section 5.1`", ((5, 1),)),
            ("Section 05.1", ((5, 1),)),
            ("Section 5.1 to match Section 6.3, then §5.1", ((5, 1), (6, 3))),
        ],
    )
    def test_accepted_forms(self, text, expected):
        assert rp.section_references(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            "Sections 3.6 cover it",        # the plural word, one item (#4554)
            "see §§5.1",                    # doubled sign, one item (#4554)
            "Section 5.1.2 is wrong",       # three parts
            "Section 5a is wrong",          # runs into a letter
            "Section 5.x is wrong",         # runs into a letter past a dot
            "Section 5_1 is wrong",         # runs into an underscore
            "the subsection 5.1 is wrong",  # longer word ending in the marker
            "Section5.1 is wrong",          # no whitespace after the word
            "Section five is wrong",        # no digits
            "Chapter 5.1 is wrong",         # a word not enumerated
            "Part 5.1 is wrong",            # a word not enumerated
            "Section ٥ is wrong",           # a digit that is not ASCII
        ],
    )
    def test_rejected_forms(self, text):
        assert rp.section_references(text) == ()

    def test_the_vocabulary_is_enumerated(self):
        assert rp.SECTION_WORDS == ("section",)
        assert rp.SECTION_SIGNS == ("§",)
        assert rp.SECTION_REFERENCE_PARTS == (1, 2)

    def test_a_reference_arrives_as_its_canonical_token(self):
        tokens = rp.named_tokens("Update §5.1 to match Section 6.3.")
        assert {"section 5.1", "section 6.3"} <= tokens
        assert "section 6.3." not in tokens

    @pytest.mark.parametrize(
        ("token", "expected"),
        [
            ("section 5.1", (5, 1)),
            ("§5.1", (5, 1)),
            ("section 10", (10,)),
            ("update section 5.1 first", None),
            ("section 5.1.2", None),
            ("settle_rows", None),
        ],
    )
    def test_only_a_whole_token_is_a_reference(self, token, expected):
        assert rp.section_token_number(token) == expected

    @pytest.mark.parametrize(
        ("heading", "expected"),
        [
            ("6. Change Instructions", (6,)),
            ("5.1 `validate_rows()`", (5, 1)),
            ("5.1. `validate_rows()`", (5, 1)),
            ("5.1.2 Edge cases", (5, 1, 2)),
            ("10.1 Per-criterion test functions", (10, 1)),
            ("Section 10 Tests", (10,)),
            ("§10 Tests", (10,)),
            ("Completeness Checklist", None),
            ("Section Overview", None),
            ("`validate_rows()` 5.1", None),
        ],
    )
    def test_a_heading_number(self, heading, expected):
        assert rp.heading_number(heading) == expected

    def test_a_heading_inside_a_fence_is_code(self):
        draft = (
            "## 5. Functions\n\nText.\n\n```python\n# 6. not a heading\n"
            "x = 1\n```\n\n## 6. Changes\n\nMore.\n"
        )
        spans = rp.section_spans(draft, {(6,)})
        lines = draft.splitlines()
        assert spans == ((lines.index("## 6. Changes"), len(lines)),)


# ---------------------------------------------------------------------------
# What pinning reads, everywhere it is read
# ---------------------------------------------------------------------------


class TestASectionReferenceNamesNoTest:
    """Conservation (#2559) is not loosened: naming the section a test sits
    in opens its lines to revision, and never lets the test go."""

    def test_dropping_a_test_under_a_named_section_is_refused_entire(self):
        revised = PREVIOUS.replace(
            "def test_req_010_rejects_turn_zero():\n    assert True\n", ""
        )
        assert revised != PREVIOUS
        result = rp.enforce_pinning(
            PREVIOUS, revised,
            current_tokens=rp.named_tokens("Section 10.1 is thin; rework it."),
        )
        assert result.conservation_lost == ("test_req_010_rejects_turn_zero",)
        assert result.text == PREVIOUS

    def test_naming_the_test_still_lets_it_go(self):
        revised = PREVIOUS.replace(
            "def test_req_010_rejects_turn_zero():\n    assert True\n", ""
        )
        result = rp.enforce_pinning(
            PREVIOUS, revised,
            current_tokens=rp.named_tokens(
                "Remove test_req_010_rejects_turn_zero from Section 10.1."
            ),
        )
        assert result.conservation_event == ""
        assert "test_req_010_rejects_turn_zero" not in result.text


class TestTheOtherReadersAgree:
    def test_a_section_reference_is_not_an_answer_line(self):
        """#4551's answers read tokens as text in revised lines; a line that
        merely mentions the section a complaint names answers nothing."""
        answers = rp.complaint_answers(["Section 10 carries no test functions."])
        assert not any(rp.section_token_number(t) for t in answers.tokens)
        assert not answers.answered_by(["See Section 10 for the tests."])

    def test_the_classifier_reads_the_heading(self):
        verdict = addresses_draft("Section 5.1 omits the error path", PREVIOUS)
        assert verdict.verdict == ADDRESSED
        assert "section_headings" in verdict.via
        assert _line_index(PREVIOUS, EDGE_LOW) + 1 in verdict.matched_lines

    def test_the_classifier_finds_nothing_without_the_heading(self):
        verdict = addresses_draft("Section 9.9 omits the error path", PREVIOUS)
        assert verdict.verdict == UNADDRESSABLE
