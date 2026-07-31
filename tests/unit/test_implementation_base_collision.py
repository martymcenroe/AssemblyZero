"""A mid-arc phase must extend what earlier phases built (#2032).

boostgauge #2, 2026-07-31:

    [1/5] src/boostgauge/telltale.py (Add)... Skipped (already exists)
    [2/5] src/boostgauge/skins/stingray.py (Add)... Skipped (already exists)
    ... all five ...
    Implementation complete: 5 files written        <- wrote zero
    [N5] Results: 0 passed, 0 failed | Exit: 2 (test execution interrupted)

`hardening-run-14` already carried those files from #41 and #1, and the worktree
is cut from that base, so every planned path existed before the node started.
The #547 skip-on-resume guard could not tell "our own half-written output" from
"an earlier phase's finished work" and skipped all of them.

Not skipping alone would be worse: the plan says Add, so the node would have
OVERWRITTEN the telltale module #41 built. Hence both halves -- do not skip a
base file, and treat it as a Modify so it is extended.
"""

import subprocess

import pytest

from assemblyzero.workflows.testing.nodes.implementation.orchestrator import (
    _should_skip_existing_file,
    came_from_base,
    resolve_change_type,
)


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


@pytest.fixture
def worktree(tmp_path):
    """A repo standing in for a pipeline worktree cut from an integration
    branch: one file committed (an earlier phase), one written but uncommitted
    (a previous attempt of this run)."""
    repo = tmp_path / "boostgauge-2"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "src").mkdir()
    (repo / "src" / "telltale.py").write_text("# from phase 41\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "phase 41 landed telltale")

    # Written by a previous attempt of the current stage: never committed.
    (repo / "src" / "windows.py").write_text("# half done\n", encoding="utf-8")
    return repo


class TestTellingBaseWorkFromOurOwn:
    def test_a_committed_file_came_from_the_base(self, worktree):
        assert came_from_base(worktree, "src/telltale.py") is True

    def test_an_uncommitted_file_is_this_run_s_output(self, worktree):
        assert came_from_base(worktree, "src/windows.py") is False

    def test_a_missing_file_is_not_from_the_base(self, worktree):
        assert came_from_base(worktree, "src/nope.py") is False


class TestSkipOnResume:
    def test_a_base_file_is_never_skipped(self, worktree):
        """The live defect: skipping here implements nothing at all."""
        assert _should_skip_existing_file(
            "Add", worktree / "src" / "telltale.py", 0, worktree, "src/telltale.py"
        ) is False

    def test_our_own_output_is_still_skipped(self, worktree):
        """#547's actual purpose survives: don't re-call the model for a file
        this run already wrote."""
        assert _should_skip_existing_file(
            "Add", worktree / "src" / "windows.py", 0, worktree, "src/windows.py"
        ) is True

    def test_retry_iterations_still_rewrite(self, worktree):
        """#1842: iteration > 0 exists to rewrite with failure feedback."""
        assert _should_skip_existing_file(
            "Add", worktree / "src" / "windows.py", 1, worktree, "src/windows.py"
        ) is False


class TestAddOnABaseFileBecomesModify:
    def test_a_base_file_planned_as_add_is_coerced(self, worktree):
        """Following the plan literally would replace #41's module."""
        assert resolve_change_type(
            "Add", worktree, "src/telltale.py", worktree / "src" / "telltale.py"
        ) == "Modify"

    def test_a_genuinely_new_file_stays_an_add(self, worktree):
        assert resolve_change_type(
            "Add", worktree, "src/new.py", worktree / "src" / "new.py"
        ) == "Add"

    def test_our_own_uncommitted_output_stays_an_add(self, worktree):
        """Untracked means this run wrote it; it is not an earlier phase's."""
        assert resolve_change_type(
            "Add", worktree, "src/windows.py", worktree / "src" / "windows.py"
        ) == "Add"

    def test_an_explicit_modify_is_left_alone(self, worktree):
        assert resolve_change_type(
            "Modify", worktree, "src/telltale.py", worktree / "src" / "telltale.py"
        ) == "Modify"

    def test_the_coercion_is_announced(self, worktree, capsys):
        resolve_change_type(
            "Add", worktree, "src/telltale.py", worktree / "src" / "telltale.py"
        )
        out = capsys.readouterr().out
        assert "Modify" in out and "src/telltale.py" in out


class TestEarlierPhaseWorkIsNotDestroyed:
    def test_the_base_file_is_untouched_by_these_decisions(self, worktree):
        """The whole point: #41's content must still be there afterwards, since
        a Modify prompt carries it as context instead of replacing it."""
        before = (worktree / "src" / "telltale.py").read_text(encoding="utf-8")
        _should_skip_existing_file(
            "Add", worktree / "src" / "telltale.py", 0, worktree, "src/telltale.py"
        )
        resolve_change_type(
            "Add", worktree, "src/telltale.py", worktree / "src" / "telltale.py"
        )
        assert (worktree / "src" / "telltale.py").read_text(encoding="utf-8") == before
