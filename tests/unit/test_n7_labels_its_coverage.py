"""N7's reports say which coverage number they show (#4436).

N5 judges changed lines. When a run changed none, the number that reaches N7 is
the whole-file figure, which decided nothing, and it sits beside the target. An
unlabelled "Coverage: 54%" over "Target: 95%" reads as a failure that passed.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

# The nodes package re-exports the node FUNCTION under the module's name.
fin = importlib.import_module("assemblyzero.workflows.testing.nodes.finalize")


def _state(repo: Path, lineage: Path, **overrides) -> dict:
    state = {
        "issue_number": 7,
        "repo_root": str(repo),
        "audit_dir": str(lineage),
        "lld_path": "",
        "test_report_path": "",
        "implementation_report_path": "",
        "test_files": ["tests/test_x.py"],
        "implementation_files": ["x.py"],
        "coverage_achieved": 54.0,
        "coverage_target": 95,
        "iteration_count": 1,
        "green_phase_output": "4 passed in 0.2s",
        "skip_e2e": True,
    }
    state.update(overrides)
    return state


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path / "target"


@pytest.fixture
def lineage(repo: Path) -> Path:
    path = repo / "docs" / "lineage" / "active" / "7-testing" / "run-1"
    path.mkdir(parents=True)
    return path


def _report_text(repo: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in (repo / "docs" / "reports").rglob("*.md")
    )


def _summary_text(repo: Path) -> str:
    done = repo / "docs" / "lineage" / "done" / "7-testing" / "run-1"
    return next(done.glob("*summary.md")).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("judged", "label"),
    [(True, "changed lines"), (False, "whole files, not judged")],
)
def test_every_report_names_the_figure(repo, lineage, capsys, judged, label):
    result = fin.finalize(_state(repo, lineage, coverage_judged=judged))

    assert not result.get("error_message")
    assert f"Coverage ({label}): 54.0%" in capsys.readouterr().out
    assert f"| Coverage ({label}) | 54.0% |" in _report_text(repo)
    assert f"| Coverage ({label}) | 54.0% |" in _summary_text(repo)


def test_a_state_that_predates_the_key_reads_as_changed_lines(repo, lineage, capsys):
    fin.finalize(_state(repo, lineage))
    assert "Coverage (changed lines): 54.0%" in capsys.readouterr().out
