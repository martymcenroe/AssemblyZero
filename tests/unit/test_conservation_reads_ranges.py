"""A verdict that names tests by a range names every test in it (#4545).

The shape is a real implementation-spec run, made generic. The reviewer
asked for the tests "test_req_060 through test_req_130" to be removed as
tautologies that exercise nothing. The drafter's edit removed them. The
conservation gate (#2559) read only the two endpoint names, counted the six
tests between them as removed with no verdict naming them, and refused the
revision entire, three times, until the run halted. Each re-prompt and the
halt said "every edit touched locked content and was refused by pinning
(0 refusal(s))": the wrong gate, a count that contradicts "every edit", and
no word on which tests to keep.

* T1 (R1): a named range counts as naming every test inside it.
* T2 (R2): a conservation refusal names conservation and the removed tests,
  in the re-prompt and in the halt, and never says "locked content".
* T3 (R3): the count in that message is the number of edits refused.

The range grammar is closed, and ``TestTheRangeGrammar`` enumerates it: each
accepted form, and the forms that are not ranges.
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, Mock, patch

import pytest

from assemblyzero.workflows.implementation_spec import revision_pinning as rp
from assemblyzero.workflows.implementation_spec.nodes.edit_script import (
    parse_edit_blocks,
)

# `nodes/__init__` re-exports the FUNCTION generate_spec, which shadows the
# module of the same name, so the module is imported by its dotted path.
gs = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.nodes.generate_spec"
)

# ---------------------------------------------------------------------------
# The observed shape, generic
# ---------------------------------------------------------------------------

#: (number, slug, body). 010-050 exercise the code; 060-130 are the
#: tautologies the reviewer asked to have removed.
_TESTS: list[tuple[str, str, str]] = [
    ("010", "ledger_accepts_a_valid_row", "assert Ledger().add({'id': 1}) is True"),
    ("020", "ledger_rejects_a_missing_id", "assert Ledger().add({}) is False"),
    ("030", "ledger_counts_rows", "assert Ledger().count() == 0"),
    ("040", "ledger_orders_rows_by_id", "assert Ledger().ordered() == []"),
    ("050", "ledger_rejects_a_duplicate_id", "assert Ledger().dedupe([1, 1]) == [1]"),
    ("060", "typed_build_passes", "type_errors = 0\n    assert type_errors == 0"),
    ("070", "frozen_value_is_kept", "kept = 5\n    assert kept == 5"),
    ("080", "repeat_freeze_keeps_first_value", "first = 1\n    assert first == 1"),
    ("090", "absent_flag_is_omitted", "flags = {}\n    assert 'stale' not in flags"),
    ("100", "state_tracks_the_flag", "tracked = True\n    assert tracked"),
    ("110", "cost_uses_actuals", "cost = 5000.0\n    assert cost == 5000.0"),
    ("120", "replay_is_identical", "score = 1\n    assert score == 1"),
    ("130", "flagged_score_matches", "base = 2\n    assert base == 2"),
]


def _name(number: str) -> str:
    return next(f"test_req_{n}_{slug}" for n, slug, _ in _TESTS if n == number)


def _test_text(number: str, slug: str, body: str) -> str:
    return f"def test_req_{number}_{slug}():\n    {body}\n"


def _draft(drop: set[str] = frozenset(), extra_after: dict[str, str] | None = None) -> str:
    """The spec with the tests numbered in ``drop`` removed.

    ``extra_after`` places an extra test definition after a numbered one.
    """
    parts = []
    for number, slug, body in _TESTS:
        if number not in drop:
            parts.append(_test_text(number, slug, body))
        if extra_after and number in extra_after:
            parts.append(extra_after[number])
    return (
        "# Implementation Spec: Widget Ledger\n"
        "\n"
        "## 6. Change Instructions\n"
        "\n"
        "### 6.4 `tests/unit/test_widget_ledger.py` (Add)\n"
        "\n"
        "Complete file contents are in Section 10.1.\n"
        "\n"
        "## 10. Test Mapping\n"
        "\n"
        "### 10.1 Test Implementation\n"
        "\n"
        "```python\n"
        "from widget.ledger import Ledger\n"
        "\n"
        "\n"
        + "\n\n".join(parts)
        + "```\n"
    )


PREVIOUS = _draft()

#: The verdict item, generic, in the words the reviewer used for the range.
VERDICT = (
    "Verdict: REVISE\n"
    "\n"
    "## Feedback Items\n"
    "- Remove tautological tests in Section 10.1: test_req_060 through "
    "test_req_130 under tests/unit/test_widget_ledger.py are hardcoded "
    "tautologies (such as 'type_errors = 0; assert type_errors == 0') that do "
    "not exercise the code under test. Remove these functions.\n"
)

RANGE = [n for n, _, _ in _TESTS if "060" <= n <= "130"]
INNER = [n for n, _, _ in _TESTS if "070" <= n <= "120"]
OUTSIDE = [n for n, _, _ in _TESTS if n <= "050"]


def _pin(revised: str, feedback: str = VERDICT, previous: str = PREVIOUS):
    return gs._apply_pinning(
        {}, previous, revised, response="",
        review_feedback=feedback, completeness_issues=[],
    )


def _conservation(events: list[str]) -> list[str]:
    return [e for e in events if "[PINNING] CONSERVATION:" in e]


# ---------------------------------------------------------------------------
# T1 (R1): a range names every test inside it
# ---------------------------------------------------------------------------


class TestARangeNamesEveryTestInIt:
    def test_t1_removing_the_whole_requested_range_passes_conservation(self):
        """The observed revision: every test from 060 through 130 removed."""
        revised = _draft(drop=set(RANGE))
        text, events = _pin(revised)
        assert _conservation(events) == []
        assert text == revised
        for number in RANGE:
            assert f"def {_name(number)}(" not in text
        for number in OUTSIDE:
            assert f"def {_name(number)}(" in text

    def test_t1_removing_the_six_inside_the_endpoints_passes_conservation(self):
        """The six tests conservation reported: 070 through 120."""
        revised = _draft(drop=set(INNER))
        text, events = _pin(revised)
        assert _conservation(events) == []
        assert text == revised

    def test_naming_only_the_endpoints_still_refuses_the_six_between(self):
        """Control: the range is what names the six. Two endpoint names
        alone name two tests, and conservation keeps the rest."""
        revised = _draft(drop=set(RANGE))
        text, events = _pin(
            revised,
            feedback="Remove test_req_060 and test_req_130 from Section 10.1.",
        )
        assert text == PREVIOUS
        (event,) = _conservation(events)
        for number in INNER:
            assert _name(number) in event
        assert _name("060") not in event and _name("130") not in event

    def test_a_test_outside_the_range_is_still_refused(self):
        revised = _draft(drop={"050", *RANGE})
        text, events = _pin(revised)
        assert text == PREVIOUS, "conservation keeps the previous draft entire"
        (event,) = _conservation(events)
        assert _name("050") in event
        for number in RANGE:
            assert _name(number) not in event

    def test_a_test_the_verdict_never_mentions_is_still_refused(self):
        """An unnumbered test inside the removed span is in no range."""
        stray = "def test_ledger_round_trip():\n    assert Ledger().load(Ledger().dump())\n"
        previous = _draft(extra_after={"090": stray})
        revised = _draft(drop=set(RANGE))
        text, events = _pin(revised, previous=previous)
        assert text == previous
        (event,) = _conservation(events)
        assert "test_ledger_round_trip" in event
        for number in RANGE:
            assert _name(number) not in event

    def test_a_t_style_range_does_not_reach_another_prefix(self):
        """T070 to T120 names tests named test_t070_..., never test_req_070_."""
        revised = _draft(drop=set(RANGE))
        text, events = _pin(
            revised,
            feedback="Remove test_req_060, and the tests T070 to T120, and test_req_130.",
        )
        assert text == PREVIOUS
        (event,) = _conservation(events)
        for number in INNER:
            assert _name(number) in event

    def test_a_t_style_range_names_its_own_tests(self):
        previous = PREVIOUS.replace("def test_req_", "def test_t")
        revised = _draft(drop=set(INNER)).replace("def test_req_", "def test_t")
        text, events = _pin(
            revised, previous=previous,
            feedback="Remove the tautologies T060 to T130 in Section 10.1.",
        )
        assert _conservation(events) == []
        assert text == revised

    def test_the_drafter_node_lands_the_requested_removal_first_time(self, tmp_path):
        """T1 through the node: the observed edit applies on attempt one."""
        removal = _block(
            "\n\n".join(_test_text(*t) for t in _TESTS if t[0] in RANGE),
            "",
        )
        out, drafter = _run_node(tmp_path, removal)
        assert out["error_message"] == ""
        assert drafter.invoke.call_count == 1
        for number in RANGE:
            assert f"def {_name(number)}(" not in out["spec_draft"]
        assert not any("CONSERVATION" in e for e in out["pinning_events"])


# ---------------------------------------------------------------------------
# T2 (R2) and T3 (R3): the re-prompt and the halt name the gate and count
# ---------------------------------------------------------------------------


def _block(search: str, replace: str) -> str:
    return f"<<<<<<< SEARCH\n{search}\n=======\n{replace}\n>>>>>>> REPLACE\n"


def _run_node(tmp_path, response: str):
    lineage = tmp_path / "lineage"
    lineage.mkdir(exist_ok=True)
    drafter = MagicMock()
    drafter.invoke.return_value = Mock(
        success=True, response=response, error_message=None,
        input_tokens=0, output_tokens=0,
    )
    state = {
        "config_mock_mode": False,
        "config_drafter": "claude:whatever",
        "lld_content": "# LLD\n",
        "current_state_snapshots": {},
        "pattern_references": [],
        "assemblyzero_root": "",
        "repo_root": "",
        "issue_number": 7,
        "audit_dir": str(lineage),
        "spec_draft": PREVIOUS,
        "review_feedback": VERDICT,
        "review_iteration": 1,
    }
    with patch.object(gs, "get_provider", return_value=drafter), patch.object(
        gs, "load_template", return_value="# Template"
    ):
        return gs.generate_spec(state), drafter


def _failure_section(prompt: str) -> str:
    """The re-prompt's report of the last attempt, and nothing else of it."""
    head = "## YOUR PREVIOUS ATTEMPT FAILED TO APPLY"
    assert head in prompt, "the re-prompt must report the failed attempt"
    section = prompt.split(head, 1)[1]
    return section.split("\n## ", 1)[0]


#: Two edit blocks: one removes 050 through 130, and 050 is outside the
#: named range; the other rewords a line the verdict names (Section 10.1).
WIDE_REMOVAL = _block(
    "\n\n".join(_test_text(*t) for t in _TESTS if t[0] == "050" or t[0] in RANGE),
    "",
) + "\n" + _block(
    "Complete file contents are in Section 10.1.",
    "Complete file contents are in Section 10.1, tautologies removed.",
)


class TestTheRepromptNamesConservation:
    def test_t2_the_reprompt_names_conservation_and_the_removed_test(self, tmp_path):
        _, drafter = _run_node(tmp_path, WIDE_REMOVAL)
        assert drafter.invoke.call_count == gs.EDIT_SCRIPT_MAX_ATTEMPTS
        for call in drafter.invoke.call_args_list[1:]:
            failure = _failure_section(call.kwargs["content"])
            assert "conservation" in failure
            assert _name("050") in failure
            assert "locked content" not in failure.lower()

    def test_t2_the_halt_names_conservation_and_the_removed_test(self, tmp_path):
        out, _ = _run_node(tmp_path, WIDE_REMOVAL)
        message = out["error_message"]
        assert "spec revision rejected" in message
        assert "conservation refused the revision entire" in message
        assert _name("050") in message
        assert "locked content" not in message.lower()
        assert "spec_draft" not in out, "a halt never overwrites the draft"

    def test_t3_the_count_is_the_number_of_refused_edits(self, tmp_path):
        """Conservation refuses the revision entire, so every edit block of
        it is refused; the message counts them."""
        blocks = parse_edit_blocks(WIDE_REMOVAL)
        assert len(blocks) == 2
        out, _ = _run_node(tmp_path, WIDE_REMOVAL)
        assert f"all {len(blocks)} edit block(s)" in out["error_message"]
        assert "0 refusal(s)" not in out["error_message"]


class TestTheReasonForEachGate:
    """The helper behind the re-prompt, one case per gate."""

    def test_conservation_names_the_gate_the_tests_and_every_block(self):
        result = rp.PinningResult(
            text=PREVIOUS,
            conservation_event="the revision removed 2 test(s) no verdict named",
            conservation_lost=("test_a_1", "test_a_2"),
        )
        reason, context = gs._pinning_refusal(result, 3)
        assert reason.startswith("conservation refused the revision entire, all 3 edit block(s)")
        assert "test_a_1, test_a_2" in reason and "test_a_1, test_a_2" in context
        assert "Keep every one of those tests" in context
        assert "locked content" not in (reason + context).lower()

    def test_locked_content_counts_the_regions_it_refused(self):
        result = rp.PinningResult(
            text=PREVIOUS, refusals=("1 line(s) starting 'a'", "2 line(s) starting 'b'"),
        )
        reason, context = gs._pinning_refusal(result, 5)
        assert reason == (
            "every edit touched locked content and was refused by pinning "
            "(2 refusal(s))"
        )
        assert "1 line(s) starting 'a'; 2 line(s) starting 'b'" in context

    def test_neither_gate_is_said_plainly_never_as_zero_refusals(self):
        reason, _ = gs._pinning_refusal(rp.PinningResult(text=PREVIOUS), 2)
        assert "no refusal and no conservation event" in reason
        assert "locked content" not in reason

    def test_the_conservation_result_carries_the_tests_it_names(self):
        result = rp.enforce_pinning(
            PREVIOUS, _draft(drop={"050", *RANGE}),
            current_tokens=rp.named_tokens(VERDICT)
            | rp.range_named_tests(PREVIOUS, VERDICT),
        )
        assert result.conservation_lost == (_name("050"),)
        assert _name("050") in result.conservation_event


# ---------------------------------------------------------------------------
# #4549: the range written as Markdown code
# ---------------------------------------------------------------------------

#: The resumed run's verdict item, generic: the reviewer names the range's
#: endpoints in backticks, the way a Markdown verdict names code.
BACKTICK_VERDICT = (
    "Verdict: REVISE\n"
    "\n"
    "## Feedback Items\n"
    "- Section 10.1 (`tests/unit/test_widget_ledger.py`): Non-discriminating "
    "test assertions. Functions `test_req_060` through `test_req_130` in the "
    "Python test block in Section 10.1 do not test the code under test; they "
    "assert hardcoded constants against each other (e.g., `type_errors = 0; "
    "assert type_errors == 0`). Remove these tautological Python test stubs.\n"
)


class TestARangeInBackticksNamesEveryTestInIt:
    def test_t1_a_backticked_range_lets_the_requested_removal_through(self):
        """#4549 T1: fails on main, where conservation names 070 to 120."""
        revised = _draft(drop=set(RANGE))
        text, events = _pin(revised, feedback=BACKTICK_VERDICT)
        assert _conservation(events) == []
        assert text == revised

    def test_t1_a_backticked_en_dash_range_lets_it_through(self):
        revised = _draft(drop=set(RANGE))
        feedback = BACKTICK_VERDICT.replace(
            "`test_req_060` through `test_req_130`",
            "`test_req_060`–`test_req_130`",
        )
        assert "`test_req_060`–`test_req_130`" in feedback
        text, events = _pin(revised, feedback=feedback)
        assert _conservation(events) == []
        assert text == revised

    def test_t4_a_test_outside_a_backticked_range_is_still_refused(self):
        revised = _draft(drop={"050", *RANGE})
        text, events = _pin(revised, feedback=BACKTICK_VERDICT)
        assert text == PREVIOUS
        (event,) = _conservation(events)
        assert _name("050") in event
        for number in RANGE:
            assert _name(number) not in event


# ---------------------------------------------------------------------------
# The closed range grammar
# ---------------------------------------------------------------------------


#: How a range's endpoints may sit in Markdown code. "each in backticks",
#: "first in backticks" and "last in backticks" are #4549's form; a whole
#: range inside one code span was already read as the bare form.
WRAPPINGS: dict[str, str] = {
    "bare": "{first}{joiner}{last}",
    "each in backticks": "`{first}`{joiner}`{last}`",
    "first in backticks": "`{first}`{joiner}{last}",
    "last in backticks": "{first}{joiner}`{last}`",
    "whole range in one span": "`{first}{joiner}{last}`",
}

#: The forms refused before #4549, as (first, joiner, last), so each can be
#: tried bare and with its endpoints in backticks.
REFUSED: list[tuple[str, str, str]] = [
    ("test_req_060", " and ", "test_req_130"),        # not a joiner
    ("test_req_060", " until ", "test_req_130"),      # not a joiner
    ("test_req_060", " , ", "test_req_130"),          # not a joiner
    ("test_req_060", " through ", "T130"),            # mixed prefixes
    ("test_req_060", " through ", "test_t130"),       # mixed prefixes
    ("test_req_130", " through ", "test_req_060"),    # reversed
    ("REQ-060", " through ", "REQ-130"),              # not a test identifier
    ("t060", " through ", "t130"),                    # a T-style id is upper case
    ("test_req_060", " through", "test_req_130"),     # a word joiner needs spaces
    ("mytest_req_060", " through ", "test_req_130"),  # endpoint inside a word
    ("test_2fa", " through ", "test_9fa"),            # no delimited number
    ("Section 10.1", " through ", "Section 10.3"),    # not a test identifier
]


class TestTheRangeGrammar:
    @pytest.mark.parametrize("wrapping", sorted(WRAPPINGS))
    @pytest.mark.parametrize("joiner", [
        f" {word} " for word in rp.RANGE_WORD_JOINERS
    ] + [
        dash for dash in rp.RANGE_DASH_JOINERS
    ] + [
        f" {dash} " for dash in rp.RANGE_DASH_JOINERS
    ])
    @pytest.mark.parametrize("first, last, prefix", [
        ("test_req_060", "test_req_130", "test_req_"),
        ("test_req_060_typed_build_passes", "test_req_130_flagged_score_matches", "test_req_"),
        ("test_t060", "test_t130", "test_t"),
        ("test_060", "test_130", "test_"),
        ("T060", "T130", "test_t"),
    ])
    def test_each_accepted_form_is_a_range(self, wrapping, joiner, first, last, prefix):
        text = WRAPPINGS[wrapping].format(first=first, joiner=joiner, last=last)
        assert rp.named_test_ranges(f"Remove {text} now.") == (
            rp.NumberedRange(prefix, 60, 130),
        )

    def test_the_backticked_en_dash_range_written_out(self):
        """`test_req_060`–`test_req_130`, written out rather than built."""
        assert rp.named_test_ranges("Drop `test_req_060`–`test_req_130`.") == (
            rp.NumberedRange("test_req_", 60, 130),
        )

    def test_the_joiners_are_exactly_the_four_enumerated(self):
        assert rp.RANGE_WORD_JOINERS == ("through", "to")
        assert rp.RANGE_DASH_JOINERS == ("-", "–")

    @pytest.mark.parametrize("wrapping", ["bare", "each in backticks"])
    @pytest.mark.parametrize("first, joiner, last", REFUSED)
    def test_forms_outside_the_grammar_are_not_ranges(self, wrapping, first, joiner, last):
        """T3 of #4549: backticks change none of these."""
        text = WRAPPINGS[wrapping].format(first=first, joiner=joiner, last=last)
        assert rp.named_test_ranges(text) == ()

    @pytest.mark.parametrize("text", [
        "test_req_060` through test_req_130",      # unpaired, closing
        "test_req_060 through `test_req_130",      # unpaired, opening
        "``test_req_060`` through ``test_req_130``",  # double backticks
        "`test_req_060`through `test_req_130`",    # a word joiner needs spaces
    ])
    def test_backticks_that_do_not_wrap_an_endpoint_are_not_ranges(self, text):
        assert rp.named_test_ranges(text) == ()

    def test_complaints_are_read_as_well_as_the_verdict(self):
        assert rp.named_test_ranges("", ["drop T010 to T030"]) == (
            rp.NumberedRange("test_t", 10, 30),
        )

    def test_a_range_names_by_number_not_by_spelling(self):
        span = rp.NumberedRange("test_req_", 60, 130)
        assert span.names("test_req_070_frozen_value_is_kept")
        assert span.names("test_req_70")
        assert span.names("test_req_130")
        assert not span.names("test_req_050_ledger_rejects_a_duplicate_id")
        assert not span.names("test_req_0600_far_away")
        assert not span.names("test_other_070_x")
        assert not span.names("test_ledger_round_trip")

    def test_range_named_tests_reads_the_draft(self):
        named = rp.range_named_tests(PREVIOUS, VERDICT)
        assert named == {_name(n).lower() for n in RANGE}

    def test_no_range_names_nothing(self):
        assert rp.range_named_tests(PREVIOUS, "Remove test_req_060.") == set()
