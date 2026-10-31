"""The speedrun reset loses nothing it cannot give back (#4215 to #4219, #4221).

Every test drives real git: the defects live in what git does with a branch,
a ref and a worktree, and a mocked `_run` would report success for the code
that shipped them. Only `gh` is faked, because the target repository in a unit
test has no GitHub remote.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import speedrun_reset as reset
import speedrun_roll as roll


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)


def _must(result: subprocess.CompletedProcess) -> str:
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


class Gh:
    """A stand-in for the `gh` CLI that the reset shells out to.

    `prs` is what `gh pr list` returns; every `gh pr close` and `gh issue
    reopen` is recorded. Anything that is not `gh` runs for real.
    """

    def __init__(self, prs: list[dict] | None = None, *, issue_state: str = "OPEN"):
        self.prs = prs or []
        self.issue_state = issue_state
        self.closed: list[int] = []
        self.commands: list[list[str]] = []

    def __call__(self, cmd, cwd=None, check=False):
        self.commands.append(list(cmd))
        if cmd[0] != "gh":
            return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)
        def done(out=""):
            return subprocess.CompletedProcess(cmd, 0, out, "")

        if cmd[1:3] == ["pr", "list"]:
            return done(json.dumps(self.prs))
        if cmd[1:3] == ["pr", "close"]:
            self.closed.append(int(cmd[3]))
            return done()
        if cmd[1:3] == ["issue", "view"]:
            return done(json.dumps({"state": self.issue_state}))
        return done()


@pytest.fixture
def gh(monkeypatch) -> Gh:
    fake = Gh()
    monkeypatch.setattr(reset, "_run", fake)
    return fake


@pytest.fixture
def origin(tmp_path: Path) -> Path:
    path = tmp_path / "origin.git"
    _must(subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(path)], capture_output=True, text=True, check=False,
    ))
    return path


@pytest.fixture
def repo(tmp_path: Path, origin: Path) -> Path:
    """A target repo on `main`, with `origin` carrying the same first commit."""
    root = tmp_path / "target"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-m", "seed")
    git(root, "remote", "add", "origin", str(origin))
    _must(git(root, "push", "origin", "main"))
    git(root, "fetch", "origin")
    git(root, "remote", "set-head", "origin", "main")
    return root


def commit_on(repo: Path, branch: str, message: str, filename: str | None = None) -> str:
    """Commit on `branch` (created from main if new), then return to main. Full sha."""
    exists = git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0
    _must(git(repo, "switch", branch) if exists else git(repo, "switch", "-c", branch, "main"))
    (repo / (filename or f"{branch.replace('/', '_')}-{message[:6]}.txt")).write_text(
        message + "\n", encoding="utf-8",
    )
    git(repo, "add", "-A")
    _must(git(repo, "commit", "-m", message))
    sha = _must(git(repo, "rev-parse", "HEAD"))
    _must(git(repo, "switch", "main"))
    return sha


def push_branch(repo: Path, branch: str) -> None:
    _must(git(repo, "push", "-u", "origin", branch))


def remote_heads(origin: Path) -> dict[str, str]:
    out = _must(subprocess.run(
        ["git", "-C", str(origin), "for-each-ref", "--format=%(refname:short) %(objectname)",
         "refs/heads"], capture_output=True, text=True, check=False,
    ))
    return {line.split()[0]: line.split()[1] for line in out.splitlines() if line}


def local_branches(repo: Path) -> list[str]:
    out = _must(git(repo, "branch", "--list", "--format=%(refname:short)"))
    return [line for line in out.splitlines() if line]


# ---------------------------------------------------------------------------
# #4216: the checkpoint search and the pin both include issue-{N}
# ---------------------------------------------------------------------------


class TestCheckpointSearch:
    def test_the_pin_finds_a_checkpoint_only_on_the_impl_stage_branch(self, repo: Path):
        """T1 (R1): the impl stage checkpoints on `issue-{N}`, nothing creates
        `{N}-impl`, so before #4216 the newest checkpoint was never pinned."""
        sha = commit_on(repo, "issue-7", "[CP:post-impl] issue #7: workflow checkpoint")

        rescue = reset.pin_checkpoint(repo, 7)

        assert rescue is not None and rescue.startswith("refs/rescue/")
        assert _must(git(repo, "rev-parse", rescue)) == sha

    def test_the_pin_finds_a_checkpoint_that_survives_only_on_origin(
        self, repo: Path
    ):
        sha = commit_on(repo, "issue-7", "[CP:post-impl] issue #7: workflow checkpoint")
        push_branch(repo, "issue-7")
        _must(git(repo, "branch", "-d", "issue-7"))

        rescue = reset.pin_checkpoint(repo, 7)

        assert rescue is not None
        assert _must(git(repo, "rev-parse", rescue)) == sha

    def test_the_roll_finds_the_same_checkpoint(self, repo: Path):
        sha = commit_on(repo, "issue-7", "[CP:post-impl] issue #7: workflow checkpoint")
        assert _must(git(repo, "rev-parse", "--short", sha)) == roll.find_checkpoint(repo, 7)

    def test_the_list_names_the_impl_stage_branch_locally_and_on_origin(self):
        refs = reset.checkpoint_search_refs(7)
        assert refs[:2] == ["issue-7", "origin/issue-7"]
        assert "origin/issue-7" in refs and "7-lld" in refs

    def test_the_pin_and_the_roll_read_one_list(self, repo: Path, monkeypatch):
        """T2 (R2): swap the one shared list for a branch no pipeline names. If
        either function kept a list of its own it would not find the checkpoint
        there, or would still find ones on the real branches."""
        monkeypatch.setattr(reset, "CHECKPOINT_BRANCH_FORMATS", ("only-{issue}",))
        commit_on(repo, "issue-7", "[CP:post-impl] issue #7: workflow checkpoint")
        assert reset.pin_checkpoint(repo, 7) is None
        assert roll.find_checkpoint(repo, 7) is None

        sha = commit_on(repo, "only-7", "[CP:post-impl] issue #7: workflow checkpoint")
        rescue = reset.pin_checkpoint(repo, 7)
        assert rescue is not None and _must(git(repo, "rev-parse", rescue)) == sha
        assert roll.find_checkpoint(repo, 7) == _must(git(repo, "rev-parse", "--short", sha))


# ---------------------------------------------------------------------------
# #4215: no branch is deleted before its tip is recoverable
# ---------------------------------------------------------------------------


@pytest.fixture
def alerts(monkeypatch) -> list[dict]:
    """Record `alert_operator` calls instead of emailing the operator."""
    from assemblyzero.core import alert

    seen: list[dict] = []
    monkeypatch.setattr(alert, "alert_operator", lambda **kw: seen.append(kw) or kw)
    return seen


def graveyard_heads(origin: Path) -> dict[str, str]:
    return {n: s for n, s in remote_heads(origin).items() if n.startswith("graveyard/")}


def reject_graveyard_pushes(origin: Path) -> None:
    """Make origin refuse any push to refs/heads/graveyard/*."""
    hook = origin / "hooks" / "pre-receive"
    hook.write_text(
        "#!/bin/sh\n"
        "while read old new ref; do\n"
        '  case "$ref" in refs/heads/graveyard/*) echo "graveyard refused" >&2; exit 1;; esac\n'
        "done\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)


class TestNoBranchIsDeletedBeforeItsTipIsRecoverable:
    def test_a_pushed_branch_with_unlanded_commits_survives_on_origin_after_the_reset(
        self, repo: Path, origin: Path, gh: Gh
    ):
        """T1 (R1): commits on no other branch, pushed, no PR. Before #4215 the
        reset deleted the local and the remote copy and nothing held the tip."""
        tip = commit_on(repo, "issue-7", "unlanded work")
        push_branch(repo, "issue-7")
        assert tip not in remote_heads(origin).get("main", "")

        reset.reset_one_issue(repo, "owner/repo", 7)

        heads = remote_heads(origin)
        assert "issue-7" not in heads, "the branch name is freed on origin"
        parked = graveyard_heads(origin)
        assert list(parked.values()) == [tip], f"the tip must be on a graveyard ref: {heads}"
        # The proof a reviewer can run: the tip is reachable from a ref on origin.
        contains = subprocess.run(
            ["git", "-C", str(origin), "branch", "--contains", tip, "--list", "graveyard/*"],
            capture_output=True, text=True, check=False,
        ).stdout
        assert "graveyard/issue-7-" in contains
        # And locally the branch was parked, not deleted.
        assert [b for b in local_branches(repo) if b.startswith("graveyard/issue-7-")]

    def test_the_graveyard_ref_is_on_origin_before_the_delete_goes_out(
        self, repo: Path, origin: Path, gh: Gh
    ):
        commit_on(repo, "issue-7", "unlanded work")
        push_branch(repo, "issue-7")

        reset.reset_one_issue(repo, "owner/repo", 7)

        pushes = [c for c in gh.commands if c[:3] == ["git", "push", "origin"]]
        graveyard_at = next(i for i, c in enumerate(pushes) if "graveyard/" in c[3])
        delete_at = next(i for i, c in enumerate(pushes) if c[3] == "--delete")
        assert graveyard_at < delete_at

    def test_a_branch_whose_commits_are_all_on_the_base_is_removed_with_no_graveyard_ref(
        self, repo: Path, origin: Path, gh: Gh
    ):
        """T2 (R2)."""
        commit_on(repo, "issue-7", "landed work")
        push_branch(repo, "issue-7")
        _must(git(repo, "merge", "--ff-only", "issue-7"))
        _must(git(repo, "push", "origin", "main"))

        reset.reset_one_issue(repo, "owner/repo", 7)

        assert "issue-7" not in remote_heads(origin)
        assert graveyard_heads(origin) == {}
        assert not [b for b in local_branches(repo) if "7" in b]

    def test_a_per_stage_branch_is_secured_the_same_way(
        self, repo: Path, origin: Path, gh: Gh
    ):
        tip = commit_on(repo, "7-lld", "design draft")
        push_branch(repo, "7-lld")

        reset.reset_one_issue(repo, "owner/repo", 7)

        assert "7-lld" not in remote_heads(origin)
        assert list(graveyard_heads(origin).values()) == [tip]

    def test_a_local_only_branch_is_parked_locally_and_pushes_nothing(
        self, repo: Path, origin: Path, gh: Gh
    ):
        """Unpushed work is not published by a reset; it keeps a local ref."""
        tip = commit_on(repo, "issue-7", "never pushed")

        reset.reset_one_issue(repo, "owner/repo", 7)

        parked = [b for b in local_branches(repo) if b.startswith("graveyard/issue-7-")]
        assert len(parked) == 1
        assert _must(git(repo, "rev-parse", parked[0])) == tip
        assert graveyard_heads(origin) == {}

    def test_a_tip_that_exists_only_on_origin_is_fetched_and_preserved(
        self, repo: Path, origin: Path, gh: Gh, tmp_path: Path
    ):
        """Pushed from another clone: this repo has no copy of the commit."""
        other = tmp_path / "other"
        _must(subprocess.run(
            ["git", "clone", "-q", str(origin), str(other)], capture_output=True, text=True, check=False,
        ))
        git(other, "config", "user.email", "o@example.com")
        git(other, "config", "user.name", "O")
        _must(git(other, "switch", "-c", "issue-7"))
        (other / "theirs.txt").write_text("theirs\n", encoding="utf-8")
        git(other, "add", "-A")
        _must(git(other, "commit", "-m", "work from another clone"))
        tip = _must(git(other, "rev-parse", "HEAD"))
        _must(git(other, "push", "origin", "issue-7"))
        assert git(repo, "cat-file", "-e", f"{tip}^{{commit}}").returncode != 0

        reset.reset_one_issue(repo, "owner/repo", 7)

        assert "issue-7" not in remote_heads(origin)
        assert list(graveyard_heads(origin).values()) == [tip]

    def test_origin_refusing_the_graveyard_push_keeps_the_branch_and_stops_the_reset(
        self, repo: Path, origin: Path, gh: Gh, alerts: list[dict]
    ):
        tip = commit_on(repo, "issue-7", "unlanded work")
        push_branch(repo, "issue-7")
        reject_graveyard_pushes(origin)

        with pytest.raises(reset.ResetPreservationError):
            reset.reset_one_issue(repo, "owner/repo", 7)

        assert remote_heads(origin).get("issue-7") == tip, "the branch must still be on origin"
        assert graveyard_heads(origin) == {}
        assert not [c for c in gh.commands if c[:4] == ["git", "push", "origin", "--delete"]]
        assert len(alerts) == 1 and "issue-7" in alerts[0]["what"]
        assert alerts[0]["issue"] == 7

    def test_an_unlistable_origin_stops_the_reset_instead_of_skipping_the_sweep(
        self, repo: Path, gh: Gh, alerts: list[dict], tmp_path: Path
    ):
        _must(git(repo, "remote", "set-url", "origin", str(tmp_path / "nowhere.git")))

        with pytest.raises(reset.ResetPreservationError):
            reset.delete_remote_branches(repo, 7)

        assert len(alerts) == 1 and "listing origin" in alerts[0]["what"]

    def test_the_checked_out_branch_and_an_attempt_branch_are_never_touched(
        self, repo: Path, origin: Path, gh: Gh
    ):
        commit_on(repo, "hardening-run-1", "attempt work")
        push_branch(repo, "hardening-run-1")
        commit_on(repo, "issue-7", "standing here")
        push_branch(repo, "issue-7")
        _must(git(repo, "switch", "issue-7"))

        reset.delete_remote_branches(repo, 7)

        heads = remote_heads(origin)
        assert "hardening-run-1" in heads and "issue-7" in heads
        assert graveyard_heads(origin) == {}

    def test_the_reset_never_hands_git_a_force_delete(self, repo: Path, origin: Path, gh: Gh):
        commit_on(repo, "issue-7", "unlanded work")
        push_branch(repo, "issue-7")

        reset.reset_one_issue(repo, "owner/repo", 7)

        branch_cmds = [c for c in gh.commands if c[:2] == ["git", "branch"]]
        assert not [c for c in branch_cmds if "-D" in c or "-M" in c]

    def test_the_checkpoint_is_pinned_before_any_branch_leaves_origin(
        self, repo: Path, origin: Path, gh: Gh
    ):
        """#4216 T1, end to end: the only checkpoint commit is on `issue-7`."""
        sha = commit_on(repo, "issue-7", "[CP:post-impl] issue #7: workflow checkpoint")
        push_branch(repo, "issue-7")

        reset.reset_one_issue(repo, "owner/repo", 7)

        rescue = _must(git(repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/rescue/"))
        assert rescue.endswith(sha) and "refs/rescue/issue-7-" in rescue
        pinned_at = next(i for i, c in enumerate(gh.commands) if c[:2] == ["git", "update-ref"])
        deleted_at = next(
            i for i, c in enumerate(gh.commands) if c[:4] == ["git", "push", "origin", "--delete"]
        )
        assert pinned_at < deleted_at


# ---------------------------------------------------------------------------
# #4219: a clean worktree's ignored files are copied out before it is removed
# ---------------------------------------------------------------------------

LINEAGE_FILE = Path("docs") / "lineage" / "active" / "7-testing" / "calls.jsonl"


@pytest.fixture
def ignoring_repo(repo: Path) -> Path:
    """A target whose .gitignore ignores `docs/lineage/` and `node_modules/`."""
    (repo / ".gitignore").write_text("docs/lineage/\nnode_modules/\ndata/\n", encoding="utf-8")
    git(repo, "add", ".gitignore")
    _must(git(repo, "commit", "-m", "ignore lineage"))
    return repo


def add_worktree(repo: Path, issue: int = 7) -> Path:
    path = repo / "data" / "worktrees" / str(issue)
    path.parent.mkdir(parents=True, exist_ok=True)
    _must(git(repo, "worktree", "add", str(path), "-b", f"issue-{issue}", "main"))
    return path


def holder(repo: Path, issue: int = 7) -> Path:
    return repo / "data" / "speedrun" / "reset-artifacts" / f"issue-{issue}" / "worktree-ignored"


class TestIgnoredFilesAreCopiedOutBeforeTheWorktreeGoes:
    def test_a_clean_worktrees_ignored_lineage_is_in_reset_artifacts_with_the_same_bytes(
        self, ignoring_repo: Path
    ):
        """T1 (R1)."""
        worktree = add_worktree(ignoring_repo)
        calls = worktree / LINEAGE_FILE
        calls.parent.mkdir(parents=True)
        payload = b'{"call": 1}\n{"call": 2, "bytes": "\xff\xfe"}\n'
        calls.write_bytes(payload)
        assert _must(git(worktree, "status", "--porcelain")) == "", "the worktree is clean to git"

        assert reset.remove_worktree(ignoring_repo, 7) is True

        assert not worktree.exists()
        copy = holder(ignoring_repo) / "7" / LINEAGE_FILE
        assert copy.read_bytes() == payload

    def test_a_failed_copy_keeps_the_worktree_and_says_why(
        self, ignoring_repo: Path, monkeypatch, alerts: list[dict]
    ):
        """T2 (R2)."""
        worktree = add_worktree(ignoring_repo)
        (worktree / LINEAGE_FILE).parent.mkdir(parents=True)
        (worktree / LINEAGE_FILE).write_text("evidence\n", encoding="utf-8")

        def full_disk(*_a, **_k):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(reset.shutil, "copy2", full_disk)

        with pytest.raises(reset.ResetPreservationError) as caught:
            reset.remove_worktree(ignoring_repo, 7)

        assert worktree.exists() and (worktree / LINEAGE_FILE).read_text(encoding="utf-8") == "evidence\n"
        assert str(worktree) in _must(git(ignoring_repo, "worktree", "list", "--porcelain"))
        assert "calls.jsonl" in str(caught.value) and "No space left" in str(caught.value)
        assert len(alerts) == 1 and alerts[0]["issue"] == 7

    def test_a_copy_that_differs_from_its_source_keeps_the_worktree(
        self, ignoring_repo: Path, monkeypatch, alerts: list[dict]
    ):
        worktree = add_worktree(ignoring_repo)
        (worktree / LINEAGE_FILE).parent.mkdir(parents=True)
        (worktree / LINEAGE_FILE).write_text("evidence\n", encoding="utf-8")

        def truncating_copy(src, dst, **_k):
            Path(dst).write_text("evid", encoding="utf-8")

        monkeypatch.setattr(reset.shutil, "copy2", truncating_copy)

        with pytest.raises(reset.ResetPreservationError) as caught:
            reset.remove_worktree(ignoring_repo, 7)

        assert worktree.exists()
        assert "differs from its source" in str(caught.value)

    def test_a_dirty_worktree_is_left_alone_and_nothing_is_copied(self, ignoring_repo: Path):
        worktree = add_worktree(ignoring_repo)
        (worktree / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
        (worktree / LINEAGE_FILE).parent.mkdir(parents=True)
        (worktree / LINEAGE_FILE).write_text("evidence\n", encoding="utf-8")

        assert reset.remove_worktree(ignoring_repo, 7) is False

        assert worktree.exists()
        assert not holder(ignoring_repo).exists()

    def test_regenerable_ignored_dirs_are_named_not_copied(
        self, ignoring_repo: Path, capsys
    ):
        worktree = add_worktree(ignoring_repo)
        (worktree / "node_modules" / "left-pad").mkdir(parents=True)
        (worktree / "node_modules" / "left-pad" / "index.js").write_text("x\n", encoding="utf-8")
        (worktree / LINEAGE_FILE).parent.mkdir(parents=True)
        (worktree / LINEAGE_FILE).write_text("evidence\n", encoding="utf-8")

        assert reset.remove_worktree(ignoring_repo, 7) is True

        assert (holder(ignoring_repo) / "7" / LINEAGE_FILE).exists()
        assert not (holder(ignoring_repo) / "7" / "node_modules").exists()
        assert "Not copying 1 regenerable ignored file" in capsys.readouterr().out

    def test_a_worktree_with_no_ignored_files_is_removed_without_a_copy(
        self, ignoring_repo: Path
    ):
        worktree = add_worktree(ignoring_repo)
        assert reset.remove_worktree(ignoring_repo, 7) is True
        assert not worktree.exists() and not holder(ignoring_repo).exists()

    def test_a_second_reset_does_not_overwrite_the_first_ones_copy(self, ignoring_repo: Path):
        for text in ("first\n", "second\n"):
            worktree = add_worktree(ignoring_repo)
            (worktree / LINEAGE_FILE).parent.mkdir(parents=True)
            (worktree / LINEAGE_FILE).write_text(text, encoding="utf-8")
            assert reset.remove_worktree(ignoring_repo, 7) is True
            git(ignoring_repo, "branch", "-d", "issue-7")
        copies = sorted(p.read_text(encoding="utf-8") for p in holder(ignoring_repo).rglob("calls.jsonl"))
        assert copies == ["first\n", "second\n"]

    def test_the_end_of_roll_restore_keeps_a_worktree_it_could_not_preserve(
        self, ignoring_repo: Path, monkeypatch, alerts: list[dict]
    ):
        """The restore calls the same `remove_worktree`, and it runs from a
        `finally`, so a failed copy must come back as a named failure and not
        as an exception that skips the rest of the restore."""
        worktree = add_worktree(ignoring_repo)
        (worktree / LINEAGE_FILE).parent.mkdir(parents=True)
        (worktree / LINEAGE_FILE).write_text("evidence\n", encoding="utf-8")
        monkeypatch.setattr(
            reset.shutil, "copy2", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
        )

        class Log:
            def __init__(self) -> None:
                self.lines: list[str] = []

            def write(self, line: str) -> None:
                self.lines.append(line)

        failures = roll.restore_repo(ignoring_repo, [7], Log())

        assert worktree.exists()
        assert any("worktree for #7 kept" in f and "disk full" in f for f in failures), failures


# ---------------------------------------------------------------------------
# #4221: the standalone reset tool is behind --execute and the typed phrase too
# ---------------------------------------------------------------------------


class TestStandaloneResetNeedsExecute:
    @pytest.fixture
    def tool(self, repo: Path, origin: Path, gh: Gh, monkeypatch, tmp_path: Path):
        import _gate
        import speedrun_clean_check as gate

        commit_on(repo, "issue-7", "unlanded work")
        push_branch(repo, "issue-7")
        monkeypatch.setattr(reset, "_gh_repo", lambda _p: "owner/repo")
        monkeypatch.setattr(_gate, "GATE_REFUSAL_LOG", tmp_path / "gate-refusals.jsonl")
        monkeypatch.setattr(gate, "check_repo", lambda *a, **k: [])
        self.argv_base = ["speedrun_reset.py", "--repo", str(repo), "--issue", "7"]
        return repo

    def run(self, monkeypatch, *extra, answers=()):
        queue = list(answers)

        def fake_input(prompt=""):
            answer = queue.pop(0)
            if isinstance(answer, BaseException):
                raise answer
            return answer

        monkeypatch.setattr("builtins.input", fake_input)
        monkeypatch.setattr(sys, "argv", [*self.argv_base, *extra])
        return reset.main()

    def test_without_execute_it_prints_the_plan_and_changes_nothing(
        self, tool, origin: Path, gh: Gh, monkeypatch, capsys
    ):
        refs_before = _must(git(tool, "for-each-ref"))
        remote_before = remote_heads(origin)

        code = self.run(monkeypatch)

        out = capsys.readouterr().out
        assert code == 0
        assert "RESET PLAN" in out and "issue-7" in out
        assert "approve forbidden reset-issues for owner/repo #7" in out
        assert _must(git(tool, "for-each-ref")) == refs_before
        assert remote_heads(origin) == remote_before
        assert [c for c in gh.commands if c[0] == "gh" and c[1:3] != ["pr", "list"]
                and c[1:3] != ["issue", "view"]] == []

    def test_with_execute_but_the_wrong_phrase_it_changes_nothing(
        self, tool, origin: Path, gh: Gh, monkeypatch
    ):
        remote_before = remote_heads(origin)
        for answer in ("yes", EOFError()):
            assert self.run(monkeypatch, "--execute", answers=[answer]) == 1
            assert remote_heads(origin) == remote_before
            assert local_branches(tool).count("issue-7") == 1
        assert gh.closed == []

    def test_with_execute_and_the_phrase_it_resets(
        self, tool, origin: Path, gh: Gh, monkeypatch
    ):
        phrase = reset.reset_phrase("owner/repo", [7])

        code = self.run(monkeypatch, "--execute", answers=[phrase])

        assert code == 0
        assert "issue-7" not in remote_heads(origin)
        assert len(graveyard_heads(origin)) == 1

    def test_the_plan_names_what_the_reset_would_do_to_each_branch(
        self, tool, origin: Path, gh: Gh
    ):
        gh.prs = [
            {"number": 11, "title": "pipeline", "headRefName": "issue-7"},
            {"number": 12, "title": "hand-made", "headRefName": "mine"},
        ]
        lines = reset.reset_plan(tool, "owner/repo", 7, "main")
        text = "\n".join(lines)
        assert "close PR #11" in text and "leave open PR #12" in text
        assert "rename local branch issue-7: 1 commit(s) beyond main" in text
        assert "delete origin's issue-7: 1 commit(s) beyond main" in text


# ---------------------------------------------------------------------------
# #4217: the live-orchestrator refusal reads the lock where the writer puts it
# ---------------------------------------------------------------------------


class TestLockLayoutIsShared:
    @pytest.fixture
    def az(self, tmp_path: Path, monkeypatch) -> Path:
        """An AssemblyZero root the orchestrator is started in: its cwd."""
        root = tmp_path / "assemblyzero"
        root.mkdir()
        monkeypatch.chdir(root)
        monkeypatch.setattr(reset, "AZ_ROOT", root)
        return root

    def test_a_lock_written_by_the_orchestrators_own_code_stops_the_reset_before_any_write(
        self, repo: Path, az: Path, gh: Gh
    ):
        """T1 (R1, R2): the lock comes from `acquire_orchestration_lock`, run as
        the orchestrator runs it (cwd = the AssemblyZero root), and the target
        repo has no `.assemblyzero` directory at all."""
        from assemblyzero.workflows.orchestrator import resume

        commit_on(repo, "issue-7", "[CP:post-impl] issue #7: workflow checkpoint")
        before_refs = _must(git(repo, "for-each-ref"))
        assert not (repo / ".assemblyzero").exists()
        assert resume.acquire_orchestration_lock(7) is True
        try:
            with pytest.raises(reset.LiveOrchestratorError) as caught:
                reset.reset_one_issue(repo, "owner/repo", 7)
        finally:
            resume.release_orchestration_lock(7)

        assert str(az / ".assemblyzero" / "orchestrator" / "locks" / "7.lock") in str(
            caught.value
        )
        assert _must(git(repo, "for-each-ref")) == before_refs, "no pin, no deletion"
        assert [c for c in gh.commands if c[0] == "gh"] == [], "no PR closed, no issue touched"

    def test_the_reader_and_the_writer_share_one_path(self, az: Path):
        from assemblyzero.workflows.orchestrator import resume

        assert resume.acquire_orchestration_lock(7) is True
        try:
            written = [p.resolve() for p in az.rglob("7.lock")]
            assert written == [resume.orchestration_lock_path(7, az).resolve()]
            assert resume.live_orchestrator_pid(7, az) == os.getpid()
        finally:
            resume.release_orchestration_lock(7)

    def test_a_lock_in_the_target_repo_is_not_where_the_orchestrator_writes(
        self, repo: Path, az: Path, gh: Gh
    ):
        stray = repo / ".assemblyzero" / "orchestrator" / "locks"
        stray.mkdir(parents=True)
        (stray / "7.lock").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
        reset.refuse_if_orchestrator_is_live(repo, 7)


# ---------------------------------------------------------------------------
# #4218: only the pipeline's own PRs are closed
# ---------------------------------------------------------------------------


class TestOnlyPipelinePrsAreClosed:
    def test_a_hand_made_pr_naming_the_issue_is_listed_and_left_open(
        self, gh: Gh, capsys
    ):
        """T1 (R1, R2)."""
        gh.prs = [
            {"number": 11, "title": "the pipeline's PR", "headRefName": "issue-7"},
            {"number": 12, "title": "somebody's hand-made PR", "headRefName": "my-own-work"},
        ]

        closed = reset.close_open_prs("owner/repo", 7)

        assert closed == 1
        assert gh.closed == [11]
        out = capsys.readouterr().out
        assert "Closed PR #11" in out
        assert "Left open PR #12" in out and "my-own-work" in out

    def test_a_per_stage_branch_of_the_issue_is_the_pipelines_own(self, gh: Gh):
        gh.prs = [{"number": 21, "title": "lld", "headRefName": "7-lld"}]
        assert reset.close_open_prs("owner/repo", 7) == 1
        assert gh.closed == [21]

    def test_another_issues_branch_is_not_this_issues(self, gh: Gh):
        """`17-lld` starts with `1` and `7`, but it is issue 17's branch."""
        gh.prs = [
            {"number": 31, "title": "other", "headRefName": "17-lld"},
            {"number": 32, "title": "other impl", "headRefName": "issue-17"},
        ]
        assert reset.close_open_prs("owner/repo", 7) == 0
        assert gh.closed == []

    def test_a_pr_with_no_head_branch_reported_is_left_open(self, gh: Gh, capsys):
        gh.prs = [{"number": 41, "title": "no head"}]
        assert reset.close_open_prs("owner/repo", 7) == 0
        assert gh.closed == []
        assert "Left open PR #41" in capsys.readouterr().out
