"""The Ponder Stibbons auto-fix node under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (lines at 79e18ad1). A fixed
draft that cannot be written back, or a lineage record of the fixes that
cannot be written, halts the run: the disk and the state used to diverge
behind a warning, and the lineage record was dropped without one.
"""
from __future__ import annotations

import importlib
from unittest.mock import patch

import pytest

from assemblyzero.workflows.requirements.graph import route_after_ponder
from assemblyzero.workflows.requirements.nodes.ponder_rules import AutoFix

pn = importlib.import_module("assemblyzero.workflows.requirements.nodes.ponder")

FIX = AutoFix(rule="title", description="normalised the title", section="0")


def _fixing(draft):
    return lambda text, ctx: (text + "\n<!-- fixed -->\n", [FIX])


def test_35_kept_no_draft_skips_to_validation_which_blocks_it():
    """Compliant by the ledger: N1.5 blocks an empty draft."""
    out = pn.ponder_stibbons_node({"current_draft": "", "iteration_count": 0})
    assert not out.get("error_message")
    assert route_after_ponder(out) == "N1_5_validate_mechanical"


def test_73_a_fixed_draft_that_cannot_be_written_halts(tmp_path, capsys):
    draft_path = tmp_path / "missing-dir" / "003-draft.md"
    state = {"current_draft": "# Draft\n", "current_draft_path": str(draft_path), "iteration_count": 0}

    with patch.object(pn, "apply_all_rules", side_effect=_fixing("# Draft\n")):
        out = pn.ponder_stibbons_node(state)

    assert out["error_message"]
    assert route_after_ponder(out) == "HALT"
    assert str(draft_path) in out["error_message"]
    assert "ERROR" in capsys.readouterr().err


def test_73_kept_a_fixed_draft_is_written_back(tmp_path):
    draft_path = tmp_path / "003-draft.md"
    draft_path.write_text("# Draft\n", encoding="utf-8")
    state = {"current_draft": "# Draft\n", "current_draft_path": str(draft_path), "iteration_count": 0}

    with patch.object(pn, "apply_all_rules", side_effect=_fixing("# Draft\n")):
        out = pn.ponder_stibbons_node(state)

    assert not out.get("error_message")
    assert draft_path.read_text(encoding="utf-8") == out["current_draft"]


def test_108_a_lineage_record_that_cannot_be_written_raises(tmp_path, capsys):
    blocker = tmp_path / "a-file"
    blocker.write_text("", encoding="utf-8")

    with pytest.raises(OSError):
        pn._save_fixes_to_lineage([FIX], blocker / "lineage", {"file_counter": 3})
    assert "ERROR" in capsys.readouterr().err


def test_108_and_the_node_halts_on_it(tmp_path):
    blocker = tmp_path / "a-file"
    blocker.write_text("", encoding="utf-8")
    state = {"current_draft": "# Draft\n", "lineage_path": str(blocker / "lineage"), "iteration_count": 0}

    with patch.object(pn, "apply_all_rules", side_effect=_fixing("# Draft\n")):
        out = pn.ponder_stibbons_node(state)

    assert out["error_message"]
    assert route_after_ponder(out) == "HALT"


def test_108_kept_a_lineage_record_is_written(tmp_path):
    lineage = tmp_path / "lineage"

    pn._save_fixes_to_lineage([FIX], lineage, {"file_counter": 3})

    assert (lineage / "004-ponder-fixes.md").is_file()
