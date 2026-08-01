"""The iterate loop must never revise from a state worse than its best (#2050).

boostgauge #2, run-issue2-205420, impl stage 1534.7s:

    Iteration 1: 7/15 passing,  36.0%
    Iteration 2: 39/41 passing, 99.0%   (one revision from done)
    Iteration 3: 7/15 passing,  36.0%   (reverted, and the run halted here)

The loop was a random walk over drafter variance with no memory of its best
result, and the halt left the WORST state it had produced on disk.
"""

from pathlib import Path

import pytest

from assemblyzero.workflows.testing.nodes.verify_phases import _hill_climb


@pytest.fixture
def tree(tmp_path):
    repo = tmp_path / "worktree"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    impl = repo / "src" / "renderer.py"
    test = repo / "tests" / "test_renderer.py"
    impl.write_text("GOOD_IMPL = 2\n", encoding="utf-8")
    test.write_text("# 41 tests\n", encoding="utf-8")
    audit = tmp_path / "audit"
    audit.mkdir()
    return repo, impl, test, audit


def _state(repo, impl, test, audit, best=None):
    return {
        "implementation_files": [str(impl)],
        "test_files": [str(test)],
        "audit_dir": str(audit),
        "best_iteration": best,
    }


class TestABetterIterationIsSnapshotted:
    def test_first_measurement_becomes_the_best(self, tree):
        repo, impl, test, audit = tree
        updates = {}
        _hill_climb(_state(repo, impl, test, audit), repo, 39, 99.0, ["t_a"], updates)

        best = updates["best_iteration"]
        assert best["passed"] == 39 and best["coverage"] == 99.0
        assert len(best["files"]) == 2
        for snap in best["files"].values():
            assert Path(snap).is_file()

    def test_an_improvement_replaces_the_best(self, tree):
        repo, impl, test, audit = tree
        updates = {}
        _hill_climb(_state(repo, impl, test, audit), repo, 7, 36.0, [], updates)
        prior = updates["best_iteration"]

        updates2 = {}
        _hill_climb(
            _state(repo, impl, test, audit, best=prior), repo, 39, 99.0, [], updates2
        )
        assert updates2["best_iteration"]["passed"] == 39


class TestAWorseIterationIsRolledBack:
    def test_the_live_oscillation_restores_the_best_files(self, tree):
        """Iteration 3 reverts to 7/15 -- the best files must come back."""
        repo, impl, test, audit = tree
        updates = {}
        _hill_climb(_state(repo, impl, test, audit), repo, 39, 99.0, ["t_a"], updates)
        best = updates["best_iteration"]

        # The bad revision destroys the good implementation.
        impl.write_text("BROKEN = 1\n", encoding="utf-8")

        updates3 = {}
        _hill_climb(
            _state(repo, impl, test, audit, best=best), repo, 7, 36.0, [], updates3
        )

        assert impl.read_text(encoding="utf-8") == "GOOD_IMPL = 2\n"

    def test_the_guards_compare_against_the_best_not_the_dice(self, tree):
        """previous_* must carry the best metrics, or the next stagnation
        decision judges progress against the bad roll."""
        repo, impl, test, audit = tree
        updates = {}
        _hill_climb(_state(repo, impl, test, audit), repo, 39, 99.0, ["t_a"], updates)
        best = updates["best_iteration"]

        updates3 = {"previous_passed": 7, "previous_coverage": 36.0}
        _hill_climb(
            _state(repo, impl, test, audit, best=best), repo, 7, 36.0, [], updates3
        )

        assert updates3["previous_passed"] == 39
        assert updates3["previous_coverage"] == 99.0
        assert updates3["previous_green_failures"] == ["t_a"]

    def test_an_equal_iteration_neither_snapshots_nor_restores(self, tree):
        repo, impl, test, audit = tree
        updates = {}
        _hill_climb(_state(repo, impl, test, audit), repo, 39, 99.0, [], updates)
        best = updates["best_iteration"]
        impl.write_text("DIFFERENT_BUT_EQUAL = 3\n", encoding="utf-8")

        updates2 = {}
        _hill_climb(
            _state(repo, impl, test, audit, best=best), repo, 39, 99.0, [], updates2
        )

        assert "best_iteration" not in updates2
        assert impl.read_text(encoding="utf-8") == "DIFFERENT_BUT_EQUAL = 3\n"


class TestDegradedInputs:
    def test_no_tracked_files_is_a_no_op(self, tree):
        repo, impl, test, audit = tree
        updates = {}
        _hill_climb(
            {"implementation_files": [], "test_files": [], "audit_dir": str(audit)},
            repo, 10, 50.0, [], updates,
        )
        assert updates == {}

    def test_a_missing_snapshot_file_restores_what_it_can(self, tree):
        repo, impl, test, audit = tree
        updates = {}
        _hill_climb(_state(repo, impl, test, audit), repo, 39, 99.0, [], updates)
        best = updates["best_iteration"]
        # One snapshot vanishes (disk cleanup, whatever).
        next(iter(best["files"].values())) and Path(
            next(iter(best["files"].values()))
        ).unlink()
        impl.write_text("BROKEN = 1\n", encoding="utf-8")

        updates3 = {}
        _hill_climb(
            _state(repo, impl, test, audit, best=best), repo, 7, 36.0, [], updates3
        )
        # No crash; metrics still carried.
        assert updates3["previous_passed"] == 39

    def test_the_state_field_is_declared(self):
        """#2018's channel rule: an undeclared key never crosses the node
        boundary and the hill-climb would silently never engage."""
        from assemblyzero.workflows.testing.state import TestingWorkflowState

        assert "best_iteration" in TestingWorkflowState.__annotations__
