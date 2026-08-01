"""Test runs must not poison the next iteration, and stagnant halts name names (#2048).

boostgauge #2, 2026-07-31, run-issue2-201843: the generated visual test wrote
its baseline PNG on first execution ("or not baseline_path.exists()"). The
revise loop then changed the renderer, and every later iteration failed
RMS-diff (0.047 vs 1/255) against the stale baseline -- an unwinnable loop.
"2 regression(s) detected" became "same 4 test(s) failing, stagnant", and the
halt named none of them; diagnosis took a manual worktree from the checkpoint
branch and a hand-run full suite.

Files a test RUN creates are droppings, not implementation: N4 writes its
files before pytest starts, so anything untracked that appears during the run
was made by the run.
"""

import subprocess


import pytest

from assemblyzero.workflows.testing.nodes.verify_phases import (
    _remove_test_run_droppings,
    _snapshot_untracked,
)


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


@pytest.fixture
def worktree(tmp_path):
    r = tmp_path / "boostgauge-2"
    r.mkdir()
    _git(r, "init", "-b", "main")
    (r / "src").mkdir()
    (r / "src" / "gauge.py").write_text("# committed\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "base")
    # N4's output: written BEFORE pytest runs, untracked, must survive.
    (r / "src" / "telltale.py").write_text("# impl\n", encoding="utf-8")
    return r


class TestDroppingsAreRemoved:
    def test_a_file_the_run_created_is_deleted(self, worktree):
        """The live poisoning: a baseline PNG born during the test run."""
        before = _snapshot_untracked(worktree)
        baselines = worktree / "tests" / "visual" / "baselines"
        baselines.mkdir(parents=True)
        (baselines / "test_stingray_telltales.png").write_bytes(b"PNG")

        _remove_test_run_droppings(worktree, before)

        assert not (baselines / "test_stingray_telltales.png").exists()

    def test_implementation_files_survive(self, worktree):
        """N4's output predates the run and is in the before-set."""
        before = _snapshot_untracked(worktree)
        (worktree / "junk.tmp").write_text("x", encoding="utf-8")

        _remove_test_run_droppings(worktree, before)

        assert (worktree / "src" / "telltale.py").exists()
        assert not (worktree / "junk.tmp").exists()

    def test_committed_files_are_never_touched(self, worktree):
        before = _snapshot_untracked(worktree)
        (worktree / "born-in-run.txt").write_text("x", encoding="utf-8")

        _remove_test_run_droppings(worktree, before)

        assert (worktree / "src" / "gauge.py").exists()

    def test_a_failed_snapshot_deletes_nothing(self, worktree):
        """'Could not measure' is not 'nothing was there' (#2028's rule) --
        None must never authorise deleting whatever is untracked now."""
        (worktree / "precious.txt").write_text("x", encoding="utf-8")

        _remove_test_run_droppings(worktree, None)

        assert (worktree / "precious.txt").exists()

    def test_a_quiet_run_removes_nothing(self, worktree):
        before = _snapshot_untracked(worktree)
        _remove_test_run_droppings(worktree, before)
        assert (worktree / "src" / "telltale.py").exists()


class TestSnapshot:
    def test_untracked_files_are_seen(self, worktree):
        snap = _snapshot_untracked(worktree)
        assert any("telltale.py" in p for p in snap)

    def test_a_non_repo_returns_none(self, tmp_path):
        bare = tmp_path / "not-a-repo"
        bare.mkdir()
        assert _snapshot_untracked(bare) is None


class TestTheStagnantHaltNamesTheTests:
    def test_the_message_carries_the_names(self):
        """'same 4 test(s)' sent diagnosis to a manual worktree; the names
        were in regression_names the whole time."""
        import inspect

        from assemblyzero.workflows.testing.nodes import verify_phases

        source = inspect.getsource(verify_phases.verify_green_phase)
        segment = source[source.index("Full suite regression stagnant"):]
        assert "{named}" in segment.split("Halting.")[0], (
            "the stagnant halt must name the failing tests, not just count them"
        )
