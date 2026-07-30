"""Branch listings are read as bare refnames, not parsed decoration (#1937).

`git branch --list` decorates the current branch with `* ` and a branch
checked out in a WORKTREE with `+ `. Three tools stripped only `'* '`, so a
worktree-held branch parsed as `+ issue-4`. In the speedrun tools that
mangled the report text and any exact-name comparison; in the janitor's
`is_branch_merged` — whose whole body is `branch in merged_branches` — it
produced a silent wrong ANSWER, reporting a merged branch as unmerged.

Every case here builds a real throwaway repo and a real worktree, so the
`+` prefix is genuinely present in git's default output rather than
simulated (standard 0024). Each test asserts the fixed behaviour AND, where
it is observable, that the pre-fix `lstrip('* ')` would have failed it.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from assemblyzero.utils.git import parse_branch_names
from assemblyzero.workflows.janitor.probes.worktrees import is_branch_merged

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_clean_check as scc  # noqa: E402
import speedrun_reset as srr  # noqa: E402


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


def _make_repo(tmp_path, name="boostrepo"):
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "README.md").write_text("x", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    return repo


def _raw_branch_lines(repo, *patterns):
    """git's DEFAULT (decorated) output — proves the `+` is really there."""
    out = subprocess.run(
        ["git", "branch", "--list", *patterns],
        cwd=str(repo), check=True, capture_output=True, text=True,
    ).stdout
    return [line for line in out.splitlines() if line.strip()]


class TestTheDecorationIsReallyPresent:
    """Guards the guard: if git stopped emitting `+`, these tests would pass
    vacuously and the regression they pin would be unprotected."""

    def test_worktree_checked_out_branch_gets_a_plus_prefix(self, tmp_path):
        repo = _make_repo(tmp_path)
        _git(repo, "branch", "issue-7")
        _git(repo, "worktree", "add", str(tmp_path / "wt"), "issue-7")

        lines = _raw_branch_lines(repo, "issue-7")
        assert lines == ["+ issue-7"], lines
        # And the old idiom demonstrably fails to clean it.
        assert lines[0].strip().lstrip("* ").strip() == "+ issue-7"


class TestCleanCheckLocalBranchDebris:
    def test_worktree_held_branch_reported_by_bare_name(self, tmp_path):
        repo = _make_repo(tmp_path)
        _git(repo, "branch", "issue-7")
        _git(repo, "worktree", "add", str(tmp_path / "wt"), "issue-7")

        findings = scc.find_local_branch_debris(repo, 7)
        assert findings == ["local branch: issue-7"], findings

    def test_current_branch_star_prefix_also_clean(self, tmp_path):
        repo = _make_repo(tmp_path)
        _git(repo, "checkout", "-b", "issue-9")

        findings = scc.find_local_branch_debris(repo, 9)
        assert findings == ["local branch: issue-9"], findings

    def test_undecorated_branch_unaffected(self, tmp_path):
        repo = _make_repo(tmp_path)
        _git(repo, "branch", "9-lld")

        assert scc.find_local_branch_debris(repo, 9) == ["local branch: 9-lld"]


class TestResetLocalBranchSweep:
    def test_worktree_held_branch_named_correctly_in_output(
        self, tmp_path, capsys
    ):
        """The branch cannot be deleted while a worktree holds it — but the
        name in the report has to be the real one, and the comparison against
        the active branch has to be able to match."""
        repo = _make_repo(tmp_path)
        _git(repo, "branch", "issue-7")
        _git(repo, "worktree", "add", str(tmp_path / "wt"), "issue-7")

        srr.delete_local_branches(repo, 7)
        out = capsys.readouterr().out
        assert "issue-7" in out
        assert "+ issue-7" not in out

    def test_deletable_branch_still_deleted(self, tmp_path):
        """The sweep's actual job keeps working."""
        repo = _make_repo(tmp_path)
        _git(repo, "branch", "7-lld")

        assert srr.delete_local_branches(repo, 7) == 1
        assert scc.find_local_branch_debris(repo, 7) == []

    def test_checked_out_branch_is_skipped_by_matching_name(
        self, tmp_path, capsys
    ):
        """#1762's guard depends on `branch == active` matching. With a `* `
        prefix left on the parsed name it never could."""
        repo = _make_repo(tmp_path)
        _git(repo, "checkout", "-b", "issue-8")

        assert srr.delete_local_branches(repo, 8) == 0
        assert "currently checked out" in capsys.readouterr().out


class TestFormatFlagIsPinned:
    """The speedrun tools are deliberately stdlib-only standalone scripts, so
    they cannot import the shared parser (running one from a worktree resolves
    `assemblyzero` to the MAIN checkout — a #1904 wrong-environment trap). Their
    protection is `--format`, so a future edit must not be able to drop it
    silently and reintroduce decoration parsing."""

    def _branch_list_calls(self, monkeypatch, module, fn, *args):
        seen = []

        def fake_run(cmd, cwd=None, check=False):
            seen.append(cmd)
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        monkeypatch.setattr(module, "_run", fake_run)
        fn(*args)
        return [c for c in seen if c[:3] == ["git", "branch", "--list"]]

    def test_clean_check_passes_format(self, monkeypatch, tmp_path):
        calls = self._branch_list_calls(
            monkeypatch, scc, scc.find_local_branch_debris, tmp_path, 7
        )
        assert calls, "no branch listing was issued"
        for cmd in calls:
            assert "--format=%(refname:short)" in cmd, cmd

    def test_reset_local_sweep_passes_format(self, monkeypatch, tmp_path):
        calls = self._branch_list_calls(
            monkeypatch, srr, srr.delete_local_branches, tmp_path, 7
        )
        assert calls, "no branch listing was issued"
        for cmd in calls:
            assert "--format=%(refname:short)" in cmd, cmd

    def test_reset_remote_sweep_passes_format(self, monkeypatch, tmp_path):
        calls = self._branch_list_calls(
            monkeypatch, srr, srr.delete_remote_branches, tmp_path, 7
        )
        assert calls, "no branch listing was issued"
        for cmd in calls:
            assert "--format=%(refname:short)" in cmd, cmd


class TestSharedParser:
    """`parse_branch_names` is the backstop for package consumers."""

    def test_strips_current_marker(self):
        assert parse_branch_names("* main\n  other\n") == ["main", "other"]

    def test_strips_worktree_marker(self):
        assert parse_branch_names("+ issue-4\n  main\n") == ["issue-4", "main"]

    def test_undecorated_passthrough(self):
        assert parse_branch_names("main\nissue-4\n") == ["main", "issue-4"]

    def test_a_branch_literally_named_plus_foo_survives(self):
        """`lstrip('*+ ')` — the obvious fix — would have eaten this."""
        assert parse_branch_names("  +foo\n") == ["+foo"]

    def test_detached_head_pseudo_entry_omitted(self):
        out = "* (HEAD detached at abc1234)\n  main\n"
        assert parse_branch_names(out) == ["main"]

    def test_blank_lines_ignored(self):
        assert parse_branch_names("\n  main\n\n") == ["main"]


class TestJanitorMergedCheck:
    """The silent wrong answer — an exact-name comparison against the list."""

    def _repo_with_merged_branch(self, tmp_path):
        repo = _make_repo(tmp_path)
        _git(repo, "checkout", "-b", "feature")
        (repo / "f.txt").write_text("f", encoding="utf-8")
        _git(repo, "add", "f.txt")
        _git(repo, "commit", "-m", "feature work")
        _git(repo, "checkout", "main")
        _git(repo, "merge", "feature", "--no-edit")
        return repo

    def test_merged_branch_held_by_a_worktree_reads_as_merged(self, tmp_path):
        repo = self._repo_with_merged_branch(tmp_path)
        _git(repo, "worktree", "add", str(tmp_path / "wt"), "feature")

        assert is_branch_merged(str(repo), "feature", "main") is True

    def test_merged_branch_without_a_worktree_reads_as_merged(self, tmp_path):
        repo = self._repo_with_merged_branch(tmp_path)

        assert is_branch_merged(str(repo), "feature", "main") is True

    def test_unmerged_branch_still_reads_as_unmerged(self, tmp_path):
        """The fix must not turn the check into a rubber stamp."""
        repo = _make_repo(tmp_path)
        _git(repo, "checkout", "-b", "solo")
        (repo / "s.txt").write_text("s", encoding="utf-8")
        _git(repo, "add", "s.txt")
        _git(repo, "commit", "-m", "unmerged work")
        _git(repo, "checkout", "main")

        assert is_branch_merged(str(repo), "solo", "main") is False
