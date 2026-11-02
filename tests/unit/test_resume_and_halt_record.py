"""A resume reaches the node that crashed, and a halt keeps its record (#4508, #4526).

#4508: `--resume` re-enters the graph at the top with the checkpoint's state.
N2 finds the test files on disk and skips, and N2.5 then hashed those same
files against the hash it had stored from them: always equal, so a resume after
a crash at the red phase always halted, reporting a scaffolder that repeats
itself when no model had been called.

#4526: N7 moved the lineage to done/ without telling the state, N8 recreated
the old path, and the landing then moved both aside, so a refused landing's
HALT could write neither its evidence nor its contract.
"""

from __future__ import annotations

import hashlib
import importlib
from pathlib import Path
from unittest.mock import patch

import pytest
from langgraph.checkpoint.memory import MemorySaver

from assemblyzero.workflows.testing import graph as testing_graph
from assemblyzero.workflows.testing.nodes.scaffold_tests import scaffold_tests
from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    MAX_SCAFFOLD_ATTEMPTS,
    validate_tests_mechanical_node,
)

# The nodes package re-exports the function under the module's name.
cleanup_module = importlib.import_module("assemblyzero.workflows.testing.nodes.cleanup")

VALID_SUITE = '''\
import pytest

from widget.core import combine


def test_combine_adds():
    assert combine(1, 2) == 3


def test_combine_rejects_none():
    with pytest.raises(TypeError):
        combine(None, 1)
'''


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path, monkeypatch):
    """Halt snapshots, resume contracts and the audit log stay in tmp."""
    from assemblyzero.core import resume_contract, state_persistence
    from assemblyzero.workflows.testing import audit as testing_audit

    state = tmp_path / "workflow_state"
    monkeypatch.setattr(state_persistence, "STATE_DIR", state)
    monkeypatch.setattr(resume_contract, "STATE_DIR", state)
    monkeypatch.setattr(
        testing_audit, "WORKFLOW_AUDIT_FILE", tmp_path / "workflow-audit.jsonl"
    )


def _after_a_validated_scaffold(root: Path, *, attempts: int = 1, **overrides) -> dict:
    """The checkpoint a run leaves when it crashes at the red phase."""
    suite = root / "tests" / "test_issue_4242.py"
    suite.parent.mkdir(parents=True, exist_ok=True)
    suite.write_text(VALID_SUITE, encoding="utf-8")
    state = {
        "issue_number": 4242,
        "repo_root": str(root),
        "generated_tests": VALID_SUITE,
        "test_files": [str(suite)],
        "parsed_scenarios": {"scenarios": [
            {"id": "S1", "description": "combine adds"},
            {"id": "S2", "description": "combine rejects None"},
        ]},
        "scaffold_attempts": attempts,
        "previous_scaffold_hash": hashlib.sha256(VALID_SUITE.encode()).hexdigest(),
        "scaffold_validation_errors": [],
    }
    state.update(overrides)
    return state


def _through_n2_and_n2_5(state: dict) -> dict:
    """N2 then N2.5, as the graph runs them: N2.5 sees what N2 returned."""
    return validate_tests_mechanical_node({**state, **scaffold_tests(state)})


class TestAResumeIsNotAReproducedScaffold:
    def test_t1_a_skipped_scaffold_routes_continue(self, tmp_path):
        """T1 (#4508 R1): the suite hashes the same because it is the same file."""
        result = _through_n2_and_n2_5(
            _after_a_validated_scaffold(tmp_path, resume_pass=True)
        )

        assert result["scaffold_route"] == "continue"
        assert "error_message" not in result

    def test_a_resume_is_not_charged_to_the_scaffold_budget(self, tmp_path):
        """The third suite validated and the run crashed. Nothing was generated
        since, so counting a fourth halts on the budget, on a false count."""
        result = _through_n2_and_n2_5(_after_a_validated_scaffold(
            tmp_path, attempts=MAX_SCAFFOLD_ATTEMPTS, resume_pass=True,
        ))

        assert result["scaffold_route"] == "continue"
        assert result["scaffold_attempts"] == MAX_SCAFFOLD_ATTEMPTS

    def test_the_resume_marks_only_one_pass(self, tmp_path):
        """Whatever sends the run back to N2 later is measured as usual."""
        result = _through_n2_and_n2_5(
            _after_a_validated_scaffold(tmp_path, resume_pass=True)
        )

        assert result["resume_pass"] is False
        assert result["scaffold_reused"] is False


class TestARealRepetitionStillHalts:
    def test_t3_a_regeneration_with_identical_output_halts(self, tmp_path):
        """T3 (#4508 R3): N2 reused nothing, so the hash means what it says."""
        state = _after_a_validated_scaffold(tmp_path)

        result = validate_tests_mechanical_node(state)

        assert result["scaffold_route"] == "escalate"
        assert "byte for byte" in result["error_message"]

    def test_a_regeneration_during_a_resume_is_still_compared(self, tmp_path):
        """A resume that does regenerate has no claim to the exemption."""
        state = _after_a_validated_scaffold(tmp_path, resume_pass=True)

        result = validate_tests_mechanical_node(state)

        assert result["scaffold_route"] == "escalate"

    def test_the_red_phase_sending_a_suite_back_is_not_a_resume(self, tmp_path):
        """#2767's loop: N3 finds nothing collected and N2 skips. Exempting
        this pass would leave that loop bounded by nothing but the recursion
        limit."""
        state = _after_a_validated_scaffold(tmp_path, next_node="N2_scaffold_tests")

        result = _through_n2_and_n2_5(state)

        assert result["scaffold_route"] == "escalate"


class _ReachedN3AgainError(Exception):
    """The resumed run got back to the node that crashed."""


class TestAResumeReachesTheNodeThatCrashed:
    def test_t2_a_run_crashed_at_n3_and_resumed_reaches_n3(
        self, tmp_path, operator_alerts,
    ):
        """T2 (#4508 R2), on the real graph with the real N2 and N2.5."""
        checkpoint = _after_a_validated_scaffold(tmp_path)
        checkpoint["previous_scaffold_hash"] = ""
        checkpoint["scaffold_attempts"] = 0
        red_phases: list[int] = []

        def red_phase(state):
            red_phases.append(state["scaffold_attempts"])
            if len(red_phases) == 1:
                raise RuntimeError("the process died at the red phase")
            raise _ReachedN3AgainError

        with (
            patch.object(testing_graph, "load_lld", lambda state: {}),
            patch.object(testing_graph, "review_test_plan", lambda state: {}),
            patch.object(testing_graph, "verify_red_phase", red_phase),
            patch.object(testing_graph, "commit_checkpoint", lambda *a, **k: None),
        ):
            app = testing_graph.build_testing_workflow().compile(
                checkpointer=MemorySaver()
            )
            config = {"configurable": {"thread_id": "4242-testing"}}

            with pytest.raises(RuntimeError, match="died at the red phase"):
                app.invoke(checkpoint, config)
            with pytest.raises(_ReachedN3AgainError):
                # What `--resume` does: input over the checkpoint, from the top.
                app.invoke({"issue_number": 4242, "resume_pass": True}, config)

        assert red_phases == [1, 1]


def _n7(root: Path) -> tuple[dict, Path]:
    """The testing workflow's N7 on a run whose lineage is in active/."""
    finalize_module = importlib.import_module(
        "assemblyzero.workflows.testing.nodes.finalize"
    )
    active = root / "docs" / "lineage" / "active" / "42-testing"
    active.mkdir(parents=True)
    (active / "005-red-phase.txt").write_text("3 failed\n", encoding="utf-8")
    state = {
        "issue_number": 42,
        "repo_root": str(root),
        "audit_dir": str(active),
        "lld_path": "",
        "test_report_path": "",
        "implementation_report_path": "",
        "skip_e2e": True,
        "test_files": ["tests/test_foo.py"],
        "implementation_files": ["assemblyzero/foo.py"],
        "coverage_achieved": 92.0,
        "coverage_target": 90,
        "iteration_count": 1,
        "green_phase_output": "3 passed in 0.5s",
    }
    with patch.object(
        finalize_module, "generate_test_report",
        return_value=root / "docs" / "reports" / "active" / "42-test-report.md",
    ):
        return finalize_module.finalize(state), active


class TestTheStateFollowsTheLineage:
    def test_t1_after_n7_moves_the_folder_audit_dir_names_where_it_went(self, tmp_path):
        """T1 (#4526 R1): N8, N9 and any HALT after N7 read audit_dir."""
        result, active = _n7(tmp_path)

        audit_dir = Path(result["audit_dir"])
        assert not active.exists()
        assert audit_dir == tmp_path / "docs" / "lineage" / "done" / "42-testing"
        assert (audit_dir / "005-red-phase.txt").is_file()

    def test_a_move_n7_did_not_make_leaves_the_state_alone(self, tmp_path):
        """A done/ folder that is already there (an earlier run of the issue)
        keeps the move from happening, and the lineage is still where the
        state says."""
        (tmp_path / "docs" / "lineage" / "done" / "42-testing").mkdir(parents=True)

        result, active = _n7(tmp_path)

        assert active.is_dir()
        assert "audit_dir" not in result

    def test_n9_writes_the_learning_summary_where_n7_put_the_lineage(self, tmp_path):
        """N9 looked only in active/, which N8 had recreated."""
        done = tmp_path / "docs" / "lineage" / "done" / "42-testing"
        done.mkdir(parents=True)
        (done / "005-red-phase.txt").write_text("3 failed\n", encoding="utf-8")
        state = {
            "repo_root": str(tmp_path),
            "issue_number": 42,
            "coverage_achieved": 95.0,
            "coverage_target": 90,
            "workflow_status": "completed",
            "audit_dir": str(done),
        }

        result = cleanup_module.cleanup(state)

        assert Path(result["learning_summary_path"]) == done / "learning-summary.md"
        assert (done / "learning-summary.md").is_file()
        assert not (tmp_path / "docs" / "lineage" / "active" / "42-testing").exists()

    def test_n9_says_where_it_archived_the_lineage(self, tmp_path):
        """N9's own move, the one that runs when a PR merged."""
        active = tmp_path / "docs" / "lineage" / "active" / "42-testing"
        active.mkdir(parents=True)
        (active / "001-lld.md").write_text("lineage\n", encoding="utf-8")
        state = {
            "repo_root": str(tmp_path),
            "issue_number": 42,
            "coverage_achieved": 95.0,
            "coverage_target": 90,
            "workflow_status": "completed",
            "pr_url": "https://github.com/o/r/pull/1",
            "audit_dir": str(active),
        }

        with patch.object(cleanup_module, "check_pr_merged", return_value=True):
            result = cleanup_module.cleanup(state)

        assert Path(result["audit_dir"]).is_dir()
        assert (Path(result["audit_dir"]) / "001-lld.md").is_file()
