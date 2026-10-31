"""assertion_manifest under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md. The compiler is pure: a
criterion it cannot compile is a CompileFailure, which the compile node turns
into a halt. No part of a row is dropped without one.
"""
from __future__ import annotations

from assemblyzero.workflows.implementation_spec import assertion_manifest as am

HEADER = (
    "| ID | Criterion | Binding value (quoted) | Assertion method |\n"
    "|----|-----------|------------------------|------------------|\n"
)


def test_325_a_fragment_with_no_literal_is_a_failure_not_a_dropped_fragment():
    lld = HEADER + "| N1 | needle colour | the needle | R ≥ 180; looks right to a person |\n"
    result = am.compile_manifest(lld)

    reasons = [f.reason for f in result.failures if f.criterion_id == "N1"]
    assert reasons, "a literal-less fragment used to vanish from the manifest"
    assert any("looks right to a person" in r for r in reasons)
    assert not [r for r in result.rows if r.criterion_id == "N1"], (
        "a row with an uncompilable fragment contributes no partial rows"
    )


def test_325_every_literal_less_fragment_is_named():
    lld = HEADER + "| N1 | needle | the needle | R ≥ 180; looks right; feels balanced |\n"
    reasons = [f.reason for f in am.compile_manifest(lld).failures]
    assert any("looks right" in r for r in reasons)
    assert any("feels balanced" in r for r in reasons)


def test_a_fragment_backed_by_the_binding_cell_still_compiles():
    """Kept: the binding cell's literals back a fragment with none of its own."""
    lld = HEADER + "| N1 | needle | #F73923 | sampled at the tip; sampled at the base |\n"
    result = am.compile_manifest(lld)
    assert result.failures == ()
    assert [r.row_id for r in result.rows] == ["N1.1", "N1.2"]


def test_a_row_with_no_literal_anywhere_keeps_its_one_failure():
    """Kept: the whole-row message (#265) when no fragment compiles."""
    lld = HEADER + "| N1 | needle | the needle | looks right |\n"
    [failure] = am.compile_manifest(lld).failures
    assert "no literal value anywhere in the row" in failure.reason


def test_284_a_row_without_an_id_is_a_failure():
    """Compliant, pinned."""
    lld = HEADER + "|  | needle | #F73923 | at the tip |\n"
    [failure] = am.compile_manifest(lld).failures
    assert failure.criterion_id == "(missing)"


def test_259_an_lld_whose_tables_are_not_criteria_tables_abstains():
    """WON'T DO, pinned: abstention is kept as an answer. Every LLD carries at
    least the Section 2.1 table, so tables_seen > 0 for every non-visual LLD;
    halting on ``abstained`` would halt all of them."""
    lld = (
        "### 2.1 Files Changed\n\n| File | Change Type | Description |\n|---|---|---|\n"
        "| `a.py` | Add | x |\n\n"
        "### 10.1 Test Scenarios\n\n| ID | Scenario | Type | Pass Criteria |\n|---|---|---|---|\n"
        "| 010 | REQ-1 x | Auto | ok |\n"
    )
    result = am.compile_manifest(lld)
    assert result.applicable is False
    assert result.abstained is True
    assert result.tables_seen == 2
