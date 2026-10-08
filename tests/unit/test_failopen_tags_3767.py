"""The five `# fail-open:` tags that landed after ADR 0236 (#3767).

Each site either fails loud (raise, or route to HALT, which alerts) or is
shown not to be a failure path, and its comment no longer carries the tag.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.implementation_spec.graph import route_after_validation
from assemblyzero.workflows.orchestrator.graph import _route_after_stage

# The nodes packages re-export each node function under its module's name.
vc = importlib.import_module("assemblyzero.workflows.implementation_spec.nodes.validate_completeness")
finalize_mod = importlib.import_module("assemblyzero.workflows.requirements.nodes.finalize")

AZ_ROOT = Path(__file__).resolve().parents[2]


def _spec(code: str) -> str:
    return f"# Spec\n\n```python\n{code}\n```\n"


def _repo_with_broken_module(tmp_path: Path) -> Path:
    pkg = tmp_path / "src" / "boostgauge"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "telltale.py").write_text("class Telltale(:\n    pass\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "boostgauge"\npackages = [{ include = "boostgauge", from = "src" }]\n',
        encoding="utf-8",
    )
    return tmp_path


PLAN = [{"path": "src/boostgauge/telltale_group.py", "change_type": "Add"}]


# ---- validate_completeness.py:1725, shown not a failure path ----


def test_an_unparseable_python_fence_fails_the_draft_by_name():
    """The reason the call check may skip such a fence: python_fences_parse
    fails the same draft, naming the fence."""
    spec = _spec("def broken(:\n    pass")
    result = vc.check_api_symbols_exist(spec, ["boostgauge.telltale.Telltale"], "")
    assert result["check_name"] == "python_fences_parse"
    assert result["passed"] is False


# ---- validate_completeness.py:1746, now fails loud ----


def test_a_callee_that_does_not_parse_raises_cannot_check(tmp_path):
    spec = _spec("from boostgauge.telltale import Telltale\nTelltale(window=1)")
    with pytest.raises(vc.CompletenessCannotCheck, match="boostgauge.telltale"):
        vc.check_call_signatures_match(spec, PLAN, str(_repo_with_broken_module(tmp_path)))


def test_the_node_turns_cannot_check_into_a_halt(tmp_path, capsys):
    spec = _spec("from boostgauge.telltale import Telltale\nTelltale(window=1)") + "x" * 120
    state = {
        "spec_draft": spec,
        "files_to_modify": PLAN,
        "pattern_references": [],
        "repo_root": str(_repo_with_broken_module(tmp_path)),
    }
    out = vc.validate_completeness(state)

    assert out["validation_passed"] is False
    assert "cannot check calls into `boostgauge.telltale`" in out["completeness_cannot_check"]
    assert out["error_message"] == out["completeness_cannot_check"]
    assert "ERROR [N3]" in capsys.readouterr().err
    assert route_after_validation({**out, "review_iteration": 0, "max_iterations": 3}) == "HALT"


def test_a_grace_revision_still_reaches_n2():
    """The new route keys on its own field: the cap message rides
    error_message on a grace revision, which must not halt (#2304)."""
    state = {
        "validation_passed": False, "review_iteration": 1, "max_iterations": 3,
        "error_message": "", "completeness_issues": ["x"],
    }
    assert route_after_validation(state) == "N2_generate_spec"


# ---- orchestrator/stages.py:2233, shown to fail loud ----


def test_a_failed_pr_stage_routes_to_the_halt_node():
    state = {
        "current_stage": "pr",
        "stage_results": {"pr": {"status": "failed", "error_message": "PR landing error: x", "transient": False}},
    }
    assert _route_after_stage(state) == "terminal"


# ---- finalize.py:643, now fails loud ----


def test_an_unwritable_durable_copy_stops_finalize(tmp_path, capsys):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("", encoding="utf-8")
    write_root = tmp_path / "wt"
    state = {
        "workflow_type": "lld", "issue_number": 7, "target_repo": str(tmp_path),
        "current_draft": "# LLD\n", "lld_status": "APPROVED", "verdict_count": 1,
    }
    with patch.object(finalize_mod, "validate_lld_final", return_value=[]), \
         patch.object(finalize_mod, "embed_review_evidence", return_value="# LLD\n"), \
         patch("assemblyzero.core.seats.resolve", return_value=MagicMock()), \
         patch.object(finalize_mod, "lld_write_root", return_value=write_root), \
         patch.object(finalize_mod, "update_lld_status"), \
         patch.object(finalize_mod, "durable_lld_path", return_value=blocker / "LLD-007.md"):
        out = finalize_mod._save_lld_file(state)

    assert "could not write the durable LLD copy" in out["error_message"]
    assert "#7" in out["error_message"]
    assert "ERROR [finalize]" in capsys.readouterr().err


# ---- all five: no tag left at these sites ----


@pytest.mark.parametrize("key", [
    "validate_completeness.py::check_call_signatures_match::fail_open_tag::1",
    "validate_completeness.py::check_call_signatures_match::fail_open_tag::2",
    "stages.py::run_pr_stage::fail_open_tag::1",
    "analyze_requirements.py::analyze_requirements::fail_open_tag::3",
    "finalize.py::_save_lld_file::fail_open_tag::2",
])
def test_the_five_keys_are_out_of_the_baseline(key):
    """AC1: these five keys are absent from the loud-failure baseline."""
    baseline = (AZ_ROOT / "tests" / "fixtures" / "loud_failure_baseline.json").read_text(encoding="utf-8")
    assert key not in baseline
