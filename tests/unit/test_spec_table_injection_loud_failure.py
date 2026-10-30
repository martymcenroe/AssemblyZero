"""The spec-side table_injection under standard 0034 (#3585).

Named ``test_spec_...`` because the requirements workflow has a module of the
same name. Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md.

An LLD whose machine-owned block is present but holds no criteria table has a
damaged block. It used to fall back to every criteria table in the LLD, which
is the one place the block exists to keep the spec from reading.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from assemblyzero.workflows.implementation_spec import table_injection as ti
from assemblyzero.workflows.implementation_spec.graph import route_after_generate_spec

gs = importlib.import_module("assemblyzero.workflows.implementation_spec.nodes.generate_spec")

TABLE = (
    "| ID | Criterion | Binding value | Assertion method |\n"
    "|----|-----------|---------------|------------------|\n"
    "| N1 | needle colour | #F73923 | sampled at the tip |\n"
)
DAMAGED = (
    "# LLD\n\n"
    f"{ti.BEGIN_MARKER}\n\nThe table that belonged here was deleted.\n\n{ti.END_MARKER}\n\n"
    "## 10. Test Plan\n\n" + TABLE
)


def test_139_a_damaged_block_raises_rather_than_reading_around_it():
    with pytest.raises(ti.DamagedInjectionError) as caught:
        ti.authoritative_tables(DAMAGED)
    assert "machine-owned" in str(caught.value)
    assert "line" in str(caught.value)


def test_139_building_the_injection_from_a_damaged_block_raises():
    with pytest.raises(ti.DamagedInjectionError):
        ti.build_injection(DAMAGED)


def test_an_lld_with_no_block_still_binds_its_own_tables():
    """Kept: an LLD drawn before the fence existed (#2607) has no block, and
    its own criteria tables are the upstream artifact."""
    assert "#F73923" in ti.build_injection("# LLD\n\n" + TABLE)


def test_a_prose_only_lld_injects_nothing():
    """Kept: no decision table is the ordinary case."""
    assert ti.build_injection("# LLD\n\nJust prose.\n") == ""


def test_the_drafter_node_halts_on_a_damaged_block_before_the_call(tmp_path):
    drafter = Mock()
    drafter.invoke.return_value = Mock(
        success=True, response="# Spec\n\n" + "line\n" * 20, error_message=None,
        input_tokens=0, output_tokens=0,
    )
    lineage = tmp_path / "lineage"
    lineage.mkdir()
    state = {
        "config_mock_mode": True, "lld_content": DAMAGED, "assemblyzero_root": "",
        "repo_root": "", "issue_number": 42, "audit_dir": str(lineage),
        "review_iteration": 0, "current_state_snapshots": {}, "pattern_references": [],
    }
    with patch.object(gs, "get_provider", return_value=drafter), patch.object(
        gs, "load_template", return_value="# Template",
    ):
        result = gs.generate_spec(state)

    assert "machine-owned" in result["error_message"]
    assert "#42" in result["error_message"]
    assert route_after_generate_spec(result) == "HALT"
    drafter.invoke.assert_not_called()
    assert not list(Path(lineage).glob("*-spec-draft.md"))
