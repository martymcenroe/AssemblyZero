"""A verdict's "Sections 5.1 and 6.2" names both sections (#4554).

#4552 made a singular ``Section N.M`` name the block under the heading with
that number, by a closed grammar that read one section per reference. A
plural named nothing, so a verdict saying "Update Sections 5.1 and 6.2 to
..." left every line under both headings locked, and the edit it asked for
was refused the way the singular once was.

* T1 (R1): "Update Sections 5.1 and 6.2" lets edits under ``### 5.1`` and
  ``### 6.2`` through, and refuses an edit under ``### 5.2``.
* T2 (R2): "Sections 5.1, 5.2 and 6.2" names all three subsections.
* T3 (R3): "Sections 5.1 through 5.3" and "Sections 5.1 or 5.2" name
  nothing.

The plural grammar is closed. ``TestThePluralGrammar`` enumerates every
accepted shape and every refused one, and pins the vocabulary the code
lists: the plural word ``sections``, the doubled sign ``§§``, the separator
``,`` and the conjunction ``and``.
"""

from __future__ import annotations

import pytest

from assemblyzero.workflows.implementation_spec import revision_pinning as rp
from assemblyzero.workflows.implementation_spec.message_addressability import (
    ADDRESSED,
    addresses_draft,
)
from tests.unit.test_pinning_section_references import (
    EDGE_LOW,
    EDGE_LOW_FIXED,
    NO_CHANGES,
    PATTERN_LINE,
    PATTERN_LINE_EDITED,
    PREVIOUS,
    WITH_DIFF,
)

#: The one line under ``### 5.2``.
SETTLE_LINE = "Settles each row against its actuals."
SETTLE_LINE_EDITED = "Settles rows."

#: Each subsection's heading and the heading after it, in PREVIOUS.
SPANS = {
    "5.1": ("### 5.1 `validate_rows()`", "### 5.2 `settle_rows()`"),
    "5.2": ("### 5.2 `settle_rows()`", "## 6. Change Instructions"),
    "6.1": ("### 6.1 `src/ledger.py` (Modify)", "### 6.2 `src/handler.py` (Modify)"),
    "6.2": ("### 6.2 `src/handler.py` (Modify)", "### 6.3 `src/bounds.py` (Add)"),
    "6.3": ("### 6.3 `src/bounds.py` (Add)", "## 7. Pattern References"),
    "7.1": ("### 7.1 Row validation pattern", "## 10. Test Mapping"),
}


def _revise(text: str, *pairs: tuple[str, str]) -> str:
    for old, new in pairs:
        assert old in text, old
        text = text.replace(old, new)
    return text


def _span(text: str, key: str) -> range:
    lines = text.splitlines()
    heading, next_heading = SPANS[key]
    return range(lines.index(heading), lines.index(next_heading))


def _named(flags: list[bool], key: str) -> bool:
    """Every line of the subsection is named."""
    return all(flags[index] for index in _span(PREVIOUS, key))


def _untouched(flags: list[bool], key: str) -> bool:
    """No line of the subsection is named."""
    return not any(flags[index] for index in _span(PREVIOUS, key))


# ---------------------------------------------------------------------------
# T1 (R1): Sections A and B names what Section A and Section B would
# ---------------------------------------------------------------------------


class TestATwoItemPluralNamesBothSections:
    """AC1: what a two-item plural names."""

    def test_edits_under_both_pass_and_one_under_a_sibling_is_refused(self):
        """T1. Fails on main: the plural named nothing, so all three edits
        came back refused."""
        revised = _revise(
            PREVIOUS,
            (EDGE_LOW, EDGE_LOW_FIXED),
            (NO_CHANGES, WITH_DIFF),
            (SETTLE_LINE, SETTLE_LINE_EDITED),
        )
        result = rp.enforce_pinning(
            PREVIOUS, revised,
            current_tokens=rp.named_tokens(
                "Update Sections 5.1 and 6.2 to match the implementation."
            ),
        )
        assert EDGE_LOW_FIXED in result.text
        assert WITH_DIFF in result.text
        assert SETTLE_LINE in result.text
        assert SETTLE_LINE_EDITED not in result.text
        assert len(result.refusals) == 1

    def test_it_names_what_the_two_singulars_name(self):
        """R1 read literally: the plural's lines are the union of the two
        singular references' lines, no more and no fewer."""
        plural = rp.named_line_flags(
            PREVIOUS, rp.named_tokens("Update Sections 5.1 and 6.2.")
        )
        first = rp.named_line_flags(PREVIOUS, rp.named_tokens("Update Section 5.1."))
        second = rp.named_line_flags(PREVIOUS, rp.named_tokens("Update Section 6.2."))
        assert plural == [a or b for a, b in zip(first, second)]
        assert any(plural)

    def test_the_real_verdicts_sentence_names_both(self):
        """The sentence the real run's verdict opened with."""
        assert rp.section_references(
            "Sections 3.6 and 5.7 specify that the rows are bounded."
        ) == ((3, 6), (5, 7))

    def test_whole_sections_name_their_subsections(self):
        flags = rp.named_line_flags(
            PREVIOUS, rp.named_tokens("Sections 5 and 7 are thin.")
        )
        for key in ("5.1", "5.2", "7.1"):
            assert _named(flags, key), key
        for key in ("6.1", "6.2", "6.3"):
            assert _untouched(flags, key), key

    def test_an_item_no_heading_carries_names_nothing(self):
        """#4552's R3 holds per item: 9.9 names nothing, and never widens."""
        flags = rp.named_line_flags(
            PREVIOUS, rp.named_tokens("Update Sections 5.1 and 9.9.")
        )
        assert _named(flags, "5.1")
        for key in ("5.2", "6.1", "6.2", "6.3", "7.1"):
            assert _untouched(flags, key), key

    def test_no_item_any_heading_carries_names_nothing(self):
        assert not any(
            rp.named_line_flags(PREVIOUS, rp.named_tokens("Sections 8.1 and 9.9."))
        )

    def test_the_doubled_sign_reads_the_same(self):
        assert rp.named_line_flags(
            PREVIOUS, rp.named_tokens("Update §§5.1 and 6.2.")
        ) == rp.named_line_flags(
            PREVIOUS, rp.named_tokens("Update Sections 5.1 and 6.2.")
        )


# ---------------------------------------------------------------------------
# T2 (R2): a comma list with a final "and" names each section in it
# ---------------------------------------------------------------------------


class TestACommaListNamesEachSection:
    """AC2: what a comma list names."""

    def test_three_items_name_three_subsections(self):
        """T2."""
        flags = rp.named_line_flags(
            PREVIOUS, rp.named_tokens("Sections 5.1, 5.2 and 6.2 omit the bound.")
        )
        for key in ("5.1", "5.2", "6.2"):
            assert _named(flags, key), key
        for key in ("6.1", "6.3", "7.1"):
            assert _untouched(flags, key), key

    def test_edits_under_all_three_pass(self):
        revised = _revise(
            PREVIOUS,
            (EDGE_LOW, EDGE_LOW_FIXED),
            (SETTLE_LINE, SETTLE_LINE_EDITED),
            (NO_CHANGES, WITH_DIFF),
            (PATTERN_LINE, PATTERN_LINE_EDITED),
        )
        result = rp.enforce_pinning(
            PREVIOUS, revised,
            current_tokens=rp.named_tokens("Sections 5.1, 5.2 and 6.2 omit the bound."),
        )
        assert EDGE_LOW_FIXED in result.text
        assert SETTLE_LINE_EDITED in result.text
        assert WITH_DIFF in result.text
        assert PATTERN_LINE in result.text  # 7.1 was never named
        assert len(result.refusals) == 1

    def test_four_items(self):
        assert rp.section_references("Sections 5.1, 5.2, 6.1 and 6.2") == (
            (5, 1), (5, 2), (6, 1), (6, 2),
        )


# ---------------------------------------------------------------------------
# T3 (R3): any other plural shape names nothing
# ---------------------------------------------------------------------------


class TestAnotherPluralShapeNamesNothing:
    """AC3: which plural shapes are references at all."""

    @pytest.mark.parametrize(
        "verdict", ["Sections 5.1 through 5.3", "Sections 5.1 or 5.2"]
    )
    def test_a_range_or_a_choice_names_nothing(self, verdict):
        """T3."""
        assert rp.section_references(verdict) == ()
        assert not any(rp.named_line_flags(PREVIOUS, rp.named_tokens(verdict)))

    @pytest.mark.parametrize(
        "verdict", ["Sections 5.1 through 5.3", "Sections 5.1 or 5.2"]
    )
    def test_an_edit_under_its_first_item_stays_refused(self, verdict):
        revised = _revise(PREVIOUS, (EDGE_LOW, EDGE_LOW_FIXED))
        result = rp.enforce_pinning(
            PREVIOUS, revised, current_tokens=rp.named_tokens(verdict)
        )
        assert EDGE_LOW in result.text
        assert EDGE_LOW_FIXED not in result.text
        assert len(result.refusals) == 1


# ---------------------------------------------------------------------------
# The closed plural grammar, enumerated
# ---------------------------------------------------------------------------


class TestThePluralGrammar:
    """Every accepted plural shape, and every shape still refused."""

    def test_the_vocabulary_is_enumerated(self):
        assert rp.SECTION_PLURAL_WORDS == ("sections",)
        assert rp.SECTION_PLURAL_SIGNS == ("§§",)
        assert rp.SECTION_LIST_SEPARATORS == (",",)
        assert rp.SECTION_LIST_CONJUNCTIONS == ("and",)
        # the singular vocabulary #4552 listed is unchanged
        assert rp.SECTION_WORDS == ("section",)
        assert rp.SECTION_SIGNS == ("§",)
        assert rp.SECTION_REFERENCE_PARTS == (1, 2)

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Sections 5.1 and 6.2", ((5, 1), (6, 2))),
            ("sections 5.1 and 6.2", ((5, 1), (6, 2))),
            ("SECTIONS 5 AND 6", ((5,), (6,))),
            ("Sections\t5.1\nand  6.2", ((5, 1), (6, 2))),
            ("§§5.1 and 6.2", ((5, 1), (6, 2))),
            ("§§ 5 and 6", ((5,), (6,))),
            ("Sections 5.1, 5.2 and 6.2", ((5, 1), (5, 2), (6, 2))),
            ("Sections 5.1, 5.2, 5.3 and 6.2", ((5, 1), (5, 2), (5, 3), (6, 2))),
            ("§§5.1, 5.2 and 6.2", ((5, 1), (5, 2), (6, 2))),
            ("Sections 10 and 10.2", ((10,), (10, 2))),
            ("Sections 5.1 and 6.2.", ((5, 1), (6, 2))),
            ("Sections 5.1 and 6.2's lines", ((5, 1), (6, 2))),
            ("(Sections 5.1 and 6.2)", ((5, 1), (6, 2))),
            ("`Sections 5.1 and 6.2`", ((5, 1), (6, 2))),
            ("Sections 5.1 and 6.2, which disagree", ((5, 1), (6, 2))),
            ("Sections 5.1 and 5.1", ((5, 1),)),
            ("Sections 6.2 and 5.1, then Section 7.1", ((6, 2), (5, 1), (7, 1))),
        ],
    )
    def test_accepted_shapes(self, text, expected):
        assert rp.section_references(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            "Sections 5.1 cover it",              # one item
            "Sections 5.1 or 5.2",                # `or` is not enumerated
            "Sections 5.1 & 5.2",                 # `&` is not enumerated
            "Sections 5.1/5.2",                   # `/` is not enumerated
            "Sections 5.1-5.3",                   # a range, by hyphen
            "Sections 5.1–5.3",                   # a range, by en dash
            "Sections 5.1 through 5.3",           # a range, by word
            "Sections 5.1 to 5.3",                # a range, by word
            "§§5.1–5.3",                          # a range under the sign
            "Sections 5.1, 5.2, and 6.2",         # a comma before the `and`
            "Sections 5.1, and 6.2",              # a comma before the `and`
            "Sections 5.1, 5.2",                  # separators only
            "Sections 5.1 and 5.2 and 6.2",       # a conjunction between earlier items
            "Sections 5.1 and 5.2, 6.2",          # carried on past the last pair
            "Sections 5.1,5.2 and 6.2",           # no whitespace after the comma
            "Sections 5.1 , 5.2 and 6.2",         # whitespace before the comma
            "Sections 5.1 and6.2",                # no whitespace after `and`
            "Sections 5.1and 6.2",                # no whitespace before `and`
            "Sections 5.1.2 and 6.2",             # an item of three parts
            "Sections 5.1 and 6.2.3",             # an item of three parts
            "Sections 5a and 6",                  # an item running into a letter
            "Sections five and six",              # no digits
            "§§§5.1 and 6.2",                     # a tripled sign
            "the subsections 5.1 and 5.2",        # a longer word ending in the plural word
            "Sections5.1 and 6.2",                # no whitespace after the plural word
            "Chapters 5.1 and 5.2",               # a word not enumerated
        ],
    )
    def test_refused_shapes(self, text):
        assert rp.section_references(text) == ()

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            # an item carrying its own marker ends the list; the marked item
            # is a singular reference on its own
            ("Sections 5.1 and Section 6.2", ((6, 2),)),
            ("§§5.1 and §6.2", ((6, 2),)),
            # the singular word before a list is a singular reference
            ("Section 5.1 and 6.2", ((5, 1),)),
        ],
    )
    def test_shapes_that_name_less_than_they_seem(self, text, expected):
        assert rp.section_references(text) == expected

    def test_each_item_arrives_as_its_canonical_token(self):
        tokens = rp.named_tokens("Update Sections 5.1, 5.2 and 6.2.")
        assert {"section 5.1", "section 5.2", "section 6.2"} <= tokens

    @pytest.mark.parametrize(
        ("token", "expected"),
        [
            ("section 5.1", ((5, 1),)),
            ("§5.1", ((5, 1),)),
            ("sections 5.1 and 6.2", ((5, 1), (6, 2))),
            ("§§5.1, 5.2 and 6.2", ((5, 1), (5, 2), (6, 2))),
            ("update sections 5.1 and 6.2 first", ()),
            ("sections 5.1 or 5.2", ()),
            ("settle_rows", ()),
        ],
    )
    def test_only_a_whole_token_is_a_reference(self, token, expected):
        assert rp.section_token_numbers(token) == expected

    def test_a_plural_token_is_not_a_singular_token(self):
        assert rp.section_token_number("sections 5.1 and 6.2") is None


# ---------------------------------------------------------------------------
# #4552's rules still hold for a plural
# ---------------------------------------------------------------------------


class TestAPluralNamesNoTest:
    """Conservation (#2559): a plural opens its sections' lines and never
    lets a test under them go."""

    def test_dropping_a_test_under_a_named_section_is_refused_entire(self):
        revised = PREVIOUS.replace(
            "def test_req_010_rejects_turn_zero():\n    assert True\n", ""
        )
        assert revised != PREVIOUS
        result = rp.enforce_pinning(
            PREVIOUS, revised,
            current_tokens=rp.named_tokens("Sections 5.1 and 10.1 are thin; rework them."),
        )
        assert result.conservation_lost == ("test_req_010_rejects_turn_zero",)
        assert result.text == PREVIOUS

    def test_a_quoted_plural_names_no_test_either(self):
        """A plural quoted whole is a Section token, never a text token, so
        it cannot reach a test whose block happens to mention it."""
        test_def = "def test_req_010_rejects_turn_zero():\n    assert True\n"
        previous = PREVIOUS.replace(
            test_def,
            "def test_req_010_rejects_turn_zero():\n"
            "    # Sections 5.1 and 10.1 set the bound.\n"
            "    assert True\n",
        )
        assert previous != PREVIOUS
        revised = previous.replace(
            "def test_req_010_rejects_turn_zero():\n"
            "    # Sections 5.1 and 10.1 set the bound.\n"
            "    assert True\n",
            "",
        )
        result = rp.enforce_pinning(
            previous, revised,
            current_tokens=rp.named_tokens("Rework `Sections 5.1 and 10.1`."),
        )
        assert result.conservation_lost == ("test_req_010_rejects_turn_zero",)
        assert result.text == previous


class TestTheOtherReadersAgree:
    def test_a_plural_is_not_an_answer_line(self):
        """#4551's answers leave Section tokens out, a plural's included."""
        answers = rp.complaint_answers(["Sections 5.1 and 10 carry no tests."])
        assert not any(rp.section_token_numbers(t) for t in answers.tokens)
        assert not answers.answered_by(["See Sections 5.1 and 10 for the tests."])

    def test_a_backticked_plural_is_not_an_answer_line(self):
        answers = rp.complaint_answers(["`Sections 5.1 and 6.2` carry no tests."])
        assert not any(rp.section_token_numbers(t) for t in answers.tokens)
        assert not answers.answered_by(["`Sections 5.1 and 6.2` now carry tests."])

    def test_a_block_that_only_mentions_the_plural_stays_locked(self):
        """A plural is never read as text, quoted whole or not."""
        mention = PATTERN_LINE + " Sections 5.1 and 6.2 list the cases."
        previous = _revise(PREVIOUS, (PATTERN_LINE, mention))
        for verdict in ("Update Sections 5.1 and 6.2.", 'Update "Sections 5.1 and 6.2".'):
            flags = rp.named_line_flags(previous, rp.named_tokens(verdict))
            assert not flags[previous.splitlines().index(mention)], verdict
            assert flags[previous.splitlines().index(EDGE_LOW)], verdict

    def test_the_classifier_reads_both_headings(self):
        verdict = addresses_draft("Sections 5.1 and 6.2 omit the error path", PREVIOUS)
        assert verdict.verdict == ADDRESSED
        assert "section_headings" in verdict.via
        lines = PREVIOUS.splitlines()
        assert lines.index(EDGE_LOW) + 1 in verdict.matched_lines
        assert lines.index(NO_CHANGES) + 1 in verdict.matched_lines
        assert lines.index(SETTLE_LINE) + 1 not in verdict.matched_lines
