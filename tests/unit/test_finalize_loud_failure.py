"""finalize.py (N7) under standard 0034, one test per sweep site.

N7 writes the test report and archives the spec and reports from active/ to
done/. A file to archive that was missing was a WARNING and None, a move
that failed was an ERROR naming nothing but the file, and both landed in a
"skipped" list nothing read, so the run reported COMPLETE. A green-phase
output with no test counts in it was reported as 0 of 0 tests passed, and
the run was COMPLETE. Each now raises after an ERROR line on stderr; the raise
reaches the run's entry point, which alerts. Line numbers in the names are
ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import patch

import pytest

# The nodes package re-exports the node FUNCTION under the module's name.
fin = importlib.import_module("assemblyzero.workflows.testing.nodes.finalize")
_archive_workflow_artifacts = fin._archive_workflow_artifacts
archive_file_to_done = fin.archive_file_to_done
finalize = fin.finalize


def _finalize_error():
    """The node's error class, looked up when a test runs."""
    return fin.FinalizeError


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for sub in ("docs/lld/active", "docs/lld/done", "docs/reports/active"):
        (tmp_path / sub).mkdir(parents=True)
    return tmp_path


def _node_state(repo: Path, **overrides) -> dict:
    audit = repo / "docs" / "lineage" / "active" / "7-testing"
    audit.mkdir(parents=True, exist_ok=True)
    state = {
        "issue_number": 7,
        "repo_root": str(repo),
        "audit_dir": str(audit),
        "lld_path": "",
        "test_report_path": "",
        "implementation_report_path": "",
        "test_files": ["tests/test_x.py"],
        "implementation_files": ["x.py"],
        "coverage_achieved": 95.0,
        "coverage_target": 90,
        "iteration_count": 1,
        "green_phase_output": "4 passed in 0.2s",
        "skip_e2e": True,
    }
    state.update(overrides)
    return state


# --- line 46: the file to archive is missing ----------------------------------


def test_46_a_missing_file_raises_naming_it(repo, capsys):
    missing = repo / "docs" / "lld" / "active" / "7-missing.md"
    with pytest.raises(FileNotFoundError) as raised:
        archive_file_to_done(missing)
    assert str(missing) in str(raised.value)
    assert "ERROR [N7]" in capsys.readouterr().err


def test_a_file_an_earlier_pass_archived_is_found_in_done(repo):
    """Kept on resume: N7 run again after archiving finds the file in done/
    and does not call that a failure."""
    done = repo / "docs" / "lld" / "done" / "7-spec.md"
    done.write_text("# spec", encoding="utf-8")
    assert archive_file_to_done(repo / "docs" / "lld" / "active" / "7-spec.md") == done


def test_a_file_elsewhere_is_not_archived(repo):
    """Kept: a file not under an active/ directory has nothing to archive.
    (The test's name avoids that word: pytest names tmp_path after it, and
    the node's check reads the whole path.)"""
    elsewhere = repo / "docs" / "elsewhere" / "7-spec.md"
    elsewhere.parent.mkdir(parents=True)
    elsewhere.write_text("# spec", encoding="utf-8")
    assert archive_file_to_done(elsewhere) is None
    assert elsewhere.exists()


# --- line 74: the move to done/ fails -----------------------------------------


def test_74_a_move_that_fails_raises_naming_both_paths(repo, capsys):
    active = repo / "docs" / "lld" / "active" / "7-spec.md"
    active.write_text("# spec", encoding="utf-8")

    refused = PermissionError(13, "Permission denied")
    with (
        patch.object(Path, "rename", side_effect=refused),
        pytest.raises(_finalize_error()) as raised,
    ):
        archive_file_to_done(active)

    message = str(raised.value)
    assert str(active) in message
    assert str(repo / "docs" / "lld" / "done" / "7-spec.md") in message
    assert "PermissionError" in message
    assert active.exists()
    assert "ERROR [N7]" in capsys.readouterr().err


# --- line 152: the green-phase output carries no test counts ------------------


@pytest.mark.parametrize("output", ["", "collected 4 items\n<no summary line>\n"])
def test_152_no_test_counts_stops_before_the_report(repo, capsys, output):
    state = _node_state(repo, green_phase_output=output)
    with (
        patch("assemblyzero.workflows.testing.nodes.finalize.generate_test_report") as report,
        pytest.raises(_finalize_error()) as raised,
    ):
        finalize(state)
    report.assert_not_called()
    assert "test counts" in str(raised.value)
    assert "ERROR [N7]" in capsys.readouterr().err


def test_a_green_output_with_counts_completes(repo):
    """Kept: counts read from the output, and the run completes."""
    state = _node_state(repo)
    with patch("assemblyzero.workflows.testing.nodes.finalize.generate_test_report") as report:
        report.return_value = repo / "docs" / "reports" / "active" / "7-test-report.md"
        result = finalize(state)
    assert result["workflow_status"] == "completed"
    assert result["error_message"] == ""


# --- line 216: some artifacts failed to archive -------------------------------


def test_216_an_artifact_that_fails_to_archive_is_not_a_skip(repo):
    """One report archives and the other is missing: that used to be one
    archived and one "skipped", and the run reported COMPLETE."""
    present = repo / "docs" / "reports" / "active" / "7-impl.md"
    present.write_text("# impl", encoding="utf-8")
    missing = repo / "docs" / "reports" / "active" / "7-missing.md"
    state = {
        "issue_number": 7,
        "lld_path": "",
        "test_report_path": str(missing),
        "implementation_report_path": str(present),
    }
    with pytest.raises(FileNotFoundError):
        _archive_workflow_artifacts(state)


def test_216_the_node_stops_when_an_artifact_fails_to_archive(repo):
    missing = repo / "docs" / "lld" / "active" / "7-spec.md"
    state = _node_state(repo, lld_path=str(missing))
    with patch("assemblyzero.workflows.testing.nodes.finalize.generate_test_report") as report:
        report.return_value = repo / "docs" / "reports" / "active" / "7-test-report.md"
        with pytest.raises(FileNotFoundError):
            finalize(state)


def test_a_file_elsewhere_is_listed_as_not_archived(repo, capsys):
    """Kept: the skip list now holds only files with nothing to archive, and
    N7 says which."""
    elsewhere = repo / "docs" / "elsewhere" / "7-spec.md"
    elsewhere.parent.mkdir(parents=True)
    elsewhere.write_text("# spec", encoding="utf-8")
    state = _node_state(repo, lld_path=str(elsewhere))
    with patch("assemblyzero.workflows.testing.nodes.finalize.generate_test_report") as report:
        report.return_value = repo / "docs" / "reports" / "active" / "7-test-report.md"
        result = finalize(state)
    assert result["workflow_status"] == "completed"
    assert "Not archived" in capsys.readouterr().out
