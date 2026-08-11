"""A pass criterion carries its value or the LLD is rejected (#2208).

The spec stage is drafted from the LLD, not from the design docs. A criterion
that defers -- "correct width/color", "per the aesthetic doc" -- leaves the
spec writer nothing to assert, so it writes a test that verifies nothing and
the spec reviewer rejects it for assertion traceability, every round, to the
cap. Seven spec halts on martymcenroe/boostgauge#1 across 2026-08-10/11 came
from exactly that, while the values sat in a design doc the test writer never
read.

The rows quoted below are verbatim from the LLD that produced the last of
those halts (`graveyard/leavings-20260811-020312`), so this suite fails if
the gate would ever let that LLD through again.
"""
from __future__ import annotations

from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
    ValidationSeverity,
    validate_test_plan_pass_criteria,
)

HEADER = (
    "## 10. Verification & Testing\n\n"
    "### 10.0 Test Plan (TDD - Complete Before Implementation)\n\n"
    "| ID | Scenario | Type | Input | Expected Output | Pass Criteria |\n"
    "|---|---|---|---|---|---|\n"
)


def lld(*rows: str) -> str:
    return HEADER + "".join(rows) + "\n## 11. Rollback\nRevert.\n"


# ---------------------------------------------------------------------------
# The real rows from the deadlock
# ---------------------------------------------------------------------------


def test_the_row_that_caused_the_deadlock_is_rejected():
    """Verbatim from the LLD of run-issue1-014959."""
    content = lld(
        "| 050 | Multiple non-coincident telltales (REQ-5) | Auto | `value=50`, "
        "peaks `[20, 30]` | `PIL.Image` | Needles visible at respective angles "
        "with correct width/color. |\n"
    )
    errors = validate_test_plan_pass_criteria(content)
    assert len(errors) == 1
    assert errors[0].severity is ValidationSeverity.ERROR
    assert "050" in errors[0].message
    assert "correct" in errors[0].message


def test_a_deferring_criterion_is_rejected():
    content = lld(
        "| 060 | Telltale colours (REQ-6) | Auto | `value=40` | `PIL.Image` | "
        "Colours per the aesthetic doc. |\n"
    )
    errors = validate_test_plan_pass_criteria(content)
    assert len(errors) == 1
    assert "060" in errors[0].message


# ---------------------------------------------------------------------------
# Rows that must NOT fire -- a noisy gate is worse than the defect
# ---------------------------------------------------------------------------


def test_a_criterion_carrying_a_hex_value_passes():
    content = lld(
        "| 070 | Redline distinctness (REQ-7) | Auto | `value=75` | `PIL.Image` | "
        "Needle tip pixels classify as candy-apple `#F73923`, band pixels as "
        "brick `#9B3020` (aesthetic doc §palette). |\n"
    )
    assert validate_test_plan_pass_criteria(content) == []


def test_the_word_correct_with_a_value_passes():
    """The gate catches missing values, not the word itself."""
    content = lld(
        "| 080 | Angle mapping (REQ-8) | Auto | `value=50` | float | "
        "`calculate_angle(50)` returns the correct value, `90.0`. |\n"
    )
    assert validate_test_plan_pass_criteria(content) == []


def test_criteria_that_already_carry_values_pass():
    content = lld(
        "| 010 | Purity (REQ-1) | Auto | import | none | `sys.modules` contains "
        "no `tkinter` references. |\n"
        "| 030 | Determinism (REQ-3) | Auto | `value=50` x2 | `PIL.Image` | "
        "Image 1 bytes strictly equal Image 2 bytes. |\n"
    )
    assert validate_test_plan_pass_criteria(content) == []


def test_the_header_and_separator_are_not_criteria():
    assert validate_test_plan_pass_criteria(lld()) == []


def test_an_lld_without_a_test_plan_is_not_flagged():
    """Missing sections are a different check's job (#579)."""
    assert validate_test_plan_pass_criteria("## 1. Context\nText.\n") == []


def test_prose_outside_the_test_plan_is_ignored():
    """"Correct" in ordinary narrative is not a pass criterion."""
    content = (
        "## 2. Proposed Changes\n\nThe renderer must produce the correct "
        "output for every value.\n\n" + lld(
            "| 010 | Purity | Auto | import | none | `sys.modules` clean. |\n"
        )
    )
    assert validate_test_plan_pass_criteria(content) == []


def test_a_table_outside_the_test_plan_is_ignored():
    content = (
        "## 2.1 Files Changed\n\n"
        "| File | Change | Why |\n|---|---|---|\n"
        "| `src/x.py` | Add | correct behaviour |\n\n"
        "## 10. Test Plan\n\n"
        "| ID | Scenario | Type | Input | Expected | Pass Criteria |\n"
        "|---|---|---|---|---|---|\n"
        "| 010 | Purity | Auto | import | none | `sys.modules` clean. |\n"
    )
    assert validate_test_plan_pass_criteria(content) == []


def test_subsections_of_the_test_plan_stay_inside_it():
    content = (
        "## 10. Verification & Testing\n\n"
        "### 10.0 Test Plan\n\n"
        "| ID | Scenario | Type | Input | Expected | Pass Criteria |\n"
        "|---|---|---|---|---|---|\n"
        "| 010 | Purity | Auto | import | none | `sys.modules` clean. |\n\n"
        "### 10.1 Render tier\n\n"
        "| ID | Scenario | Type | Input | Expected | Pass Criteria |\n"
        "|---|---|---|---|---|---|\n"
        "| 020 | Colours | Auto | `value=0` | image | Colours as specified. |\n"
    )
    errors = validate_test_plan_pass_criteria(content)
    assert len(errors) == 1, "a deeper subsection is still the test plan"
    assert "020" in errors[0].message


def test_every_bad_row_is_named_individually():
    content = lld(
        "| 010 | A | Auto | x | y | Renders correct output. |\n"
        "| 020 | B | Auto | x | y | Colours per the design doc. |\n"
        "| 030 | C | Auto | x | y | Byte-identical to `baseline.png`. |\n"
    )
    errors = validate_test_plan_pass_criteria(content)
    assert len(errors) == 2
    assert {"010", "020"} == {e.message.split("test ")[1].split("'")[0].strip()
                              for e in errors}


def test_the_message_quotes_the_offending_text():
    """The operator must be able to fix the row without opening the file."""
    content = lld("| 010 | A | Auto | x | y | Renders correct output. |\n")
    (error,) = validate_test_plan_pass_criteria(content)
    assert "Renders correct output" in error.message
    assert "quote the" in error.message
