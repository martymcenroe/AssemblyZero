"""The derivation carries its source row's literals, or says it shed them (#2563).

The observed case: boostgauge #331's S6 row states the mirror-band check
with a ruled sampling window ("sampled ONLY at horizontal offsets
0.12 R-0.25 R either side of the vertical axis" -- the #361 ruling); the
generated LLD (preserved at graveyard/331-lld-20260827T170422Z) restated
the check twice with no window, 0.12 appeared nowhere in the document, and
the spec-stage reviewer re-proved from the geometry a contradiction ruled
six days earlier. Calibrated against the real pair before landing: four
firings, all genuine losses (S3, S5, S6, S7), zero false alarms on the five
conserved rows.
"""

from __future__ import annotations

from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
    validate_assertion_literal_conservation,
)

#: The observed S6 row, verbatim shape: ID column, binding value, assertion
#: method carrying the ruled window inline.
ISSUE_BODY = """## Decision table — static elements and their binding values

| ID | Element | Binding value (quoted from the render contract) | Assertion method |
|----|---------|------------------------------------------------|------------------|
| S6 | Wordmark | `BOOSTGAUGE`, `#FFFFFF`, cap height 0.09 R, band centred 0.67 R below the pivot | presence: ≥1 white-classified pixel in the wordmark band; absence of white in the mirror band above the pivot, sampled ONLY at horizontal offsets 0.12 R–0.25 R either side of the vertical axis |
"""

#: The observed derived shape: the check restated with no window — the bare
#: "0 white pixels in mirrored band" the preserved LLD carried.
LLD_WITHOUT_WINDOW = """# LLD-331

## 3. Requirements

1. Wordmark presence and phantom check.

## 10. Test Plan

| ID | Scenario | Pass criterion |
|----|----------|----------------|
| 070 | Wordmark existential and phantom check | >= 1 white pixel in wordmark band (`#FFFFFF`), cap height 0.09 R, centred 0.67 R below pivot; 0 white pixels in mirrored band |
"""

LLD_WITH_WINDOW = LLD_WITHOUT_WINDOW.replace(
    "0 white pixels in mirrored band",
    "0 white pixels in mirrored band sampled at offsets 0.12 R–0.25 R "
    "either side of the vertical axis",
)


class TestTheObservedCase:
    def test_the_shed_window_is_flagged_by_row(self):
        errors = validate_assertion_literal_conservation(
            ISSUE_BODY, LLD_WITHOUT_WINDOW
        )
        assert len(errors) == 1
        message = errors[0].message
        assert "S6" in message
        assert "0.12" in message
        assert "#2563" in message

    def test_the_carried_window_is_quiet(self):
        assert validate_assertion_literal_conservation(
            ISSUE_BODY, LLD_WITH_WINDOW
        ) == []

    def test_a_control_row_with_no_numeric_qualifiers_derives_unchanged(self):
        issue = """| ID | Element | Binding value | Assertion method |
|----|---------|---------------|------------------|
| T1 | Peak marker | a `None` peak renders nothing | the rendered face is identical to the bare face |
"""
        assert validate_assertion_literal_conservation(
            issue, "# LLD\n\nAny content at all."
        ) == []


class TestConservationMechanics:
    def _issue(self, binding: str, assertion: str) -> str:
        return (
            "| ID | Element | Binding value | Assertion method |\n"
            "|----|---------|---------------|------------------|\n"
            f"| S1 | Element | {binding} | {assertion} |\n"
        )

    def test_a_hex_colour_is_conserved_case_insensitively(self):
        issue = self._issue("`#AA0F19` crimson", "classification at 3 points")
        assert validate_assertion_literal_conservation(
            issue, "# LLD\n\nband is #aa0f19, sampled at 3 points"
        ) == []
        errors = validate_assertion_literal_conservation(
            issue, "# LLD\n\nband is crimson, sampled at 3 points"
        )
        assert len(errors) == 1
        assert "#AA0F19" in errors[0].message

    def test_a_number_does_not_survive_as_a_substring(self):
        """0.12 inside 0.125 is not conservation, and 12 inside 0.12 is not
        either -- a coincidental substring must never satisfy the check."""
        issue = self._issue("window at 0.12 R", "sampled in the window")
        errors = validate_assertion_literal_conservation(
            issue, "# LLD\n\nthreshold 0.125 R applies"
        )
        assert len(errors) == 1
        issue_12 = self._issue("offset 12 px", "sampled at the offset")
        errors_12 = validate_assertion_literal_conservation(
            issue_12, "# LLD\n\nwindow at 0.12 R"
        )
        assert len(errors_12) == 1

    def test_an_issue_with_no_decision_table_is_not_applicable(self):
        assert validate_assertion_literal_conservation(
            "## Requirements\n\nJust prose with 0.12 R in it.",
            "# LLD\n\nNothing conserved.",
        ) == []

    def test_empty_inputs_are_quiet(self):
        assert validate_assertion_literal_conservation("", "x") == []
        assert validate_assertion_literal_conservation("x", "") == []
