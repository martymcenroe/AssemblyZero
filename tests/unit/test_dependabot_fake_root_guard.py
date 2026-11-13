"""#4736: the dependabot gate never runs a suite that lacks the fake-root guard.

``fake_root_guard_gap`` is tested against real git in ``tmp_path``: a bare
origin whose ``main`` carries the guard, and clones whose HEAD does or does
not. ``_process_pr_inside_worktree`` is tested with git and gh stubbed at
``run``, so the guard comparison itself still runs, and with every step that
installs, tests, comments or merges replaced by a recorder.
"""
import importlib.util
import subprocess
from pathlib import Path

import pytest

# Load the tools/ script as a module without polluting sys.path.
TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "dependabot_review", TOOLS_DIR / "dependabot_review.py"
)
dependabot_review = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dependabot_review)

GUARD = "tests/fake_root_guard.py"
BASE_REF = f"origin/{dependabot_review.BASE_BRANCH}"


def _completed(returncode: int = 0, stdout: str = "",
               stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# ---- fake_root_guard_gap against real git ----


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false",
         *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


@pytest.fixture
def git_env(tmp_path, monkeypatch):
    """git with the machine's config shut out, and no repository above tmp_path."""
    empty = tmp_path / "empty.gitconfig"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "t")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "t")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@example.com")


@pytest.fixture
def origin_with_guard(tmp_path, git_env) -> Path:
    """A bare origin whose main is: a commit without the guard, then one adding it."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", str(origin))
    seed = tmp_path / "seed"
    _git(tmp_path, "init", "-q", str(seed))
    (seed / "README.md").write_text("seed\n", encoding="utf-8")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-q", "-m", "before the guard")
    guard = seed / GUARD
    guard.parent.mkdir(parents=True)
    guard.write_text("# the fake-root guard\n", encoding="utf-8")
    _git(seed, "add", GUARD)
    _git(seed, "commit", "-q", "-m", "add the guard")
    _git(seed, "remote", "add", "origin", str(origin))
    _git(seed, "push", "-q", "origin", "main")
    return origin


def _clone(tmp_path: Path, origin: Path) -> Path:
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    return clone


def test_gap_names_the_guard_when_head_predates_it(tmp_path, origin_with_guard):
    clone = _clone(tmp_path, origin_with_guard)
    _git(clone, "switch", "-q", "--detach", "HEAD~1")
    assert _git(clone, "ls-tree", "HEAD", "--", GUARD).stdout == "", (
        "precondition: this HEAD must lack the guard")

    missing, error = dependabot_review.fake_root_guard_gap(clone)

    assert error == ""
    assert missing == [GUARD]


def test_gap_is_empty_when_head_carries_the_guard(tmp_path, origin_with_guard):
    clone = _clone(tmp_path, origin_with_guard)

    missing, error = dependabot_review.fake_root_guard_gap(clone)

    assert error == ""
    assert missing == []


def test_gap_reports_an_error_outside_a_repository(tmp_path, git_env):
    plain = tmp_path / "plain"
    plain.mkdir()

    missing, error = dependabot_review.fake_root_guard_gap(plain)

    assert error != ""
    assert missing == []


# ---- _process_pr_inside_worktree with git and gh stubbed ----


def _pr() -> "dependabot_review.PRInfo":
    return dependabot_review.PRInfo(
        number=4736, title="bump foo", author_login="app/dependabot",
        body="", head_ref="dependabot/pip/foo",
    )


def _wire(monkeypatch, *, head_has_guard: bool, stale: bool = False,
          package_count: int = 1) -> dict[str, list]:
    """Stub git and gh at `run`, and record every step that would act."""
    calls: dict[str, list] = {
        "run": [], "evict": [], "install": [], "tests": [], "baseline": [],
        "reviews": [], "rebase": [], "recreate": [], "approvals": [],
    }
    listing = f"100644 blob {'a' * 40}\t{GUARD}\n"

    def fake_run(cmd, cwd=None, **kwargs):
        calls["run"].append(list(cmd))
        if cmd[:3] == ["git", "fetch", "origin"]:
            return _completed(0)
        if cmd[:2] == ["git", "ls-tree"]:
            on_base = cmd[2] == BASE_REF
            return _completed(0, listing if on_base or head_has_guard else "")
        if cmd[:3] == ["gh", "pr", "checkout"]:
            return _completed(0)
        if cmd[:3] == ["gh", "pr", "diff"]:
            return _completed(0, "poetry.lock\n")
        raise AssertionError(f"unexpected command reached run: {cmd}")

    def fake_rebase(pr_number, repo, explanation=None):
        calls["rebase"].append(explanation)

    monkeypatch.setattr(dependabot_review, "run", fake_run)
    monkeypatch.setattr(dependabot_review, "evict_poetry_venv",
                        lambda wt: calls["evict"].append(wt))
    monkeypatch.setattr(dependabot_review, "install_deps",
                        lambda wt: calls["install"].append(wt) or True)
    monkeypatch.setattr(dependabot_review, "run_tests_detailed",
                        lambda wt: calls["tests"].append(wt) or (0, ""))
    monkeypatch.setattr(dependabot_review, "run_baseline_gate",
                        lambda *a: calls["baseline"].append(a) or (0, ""))
    monkeypatch.setattr(dependabot_review, "review_comment_on_pr",
                        lambda n, r, body: calls["reviews"].append(body) or True)
    monkeypatch.setattr(dependabot_review, "is_pr_branch_stale",
                        lambda n, r: stale)
    monkeypatch.setattr(dependabot_review, "count_packages",
                        lambda body: package_count)
    monkeypatch.setattr(dependabot_review, "request_dependabot_rebase",
                        fake_rebase)
    monkeypatch.setattr(dependabot_review, "request_dependabot_recreate",
                        lambda n, r: calls["recreate"].append(n))
    monkeypatch.setattr(dependabot_review, "inject_no_issue",
                        lambda pr, repo: True)
    monkeypatch.setattr(
        dependabot_review, "approve_pr",
        lambda n, r, desc: calls["approvals"].append(desc) or True)
    monkeypatch.setattr(dependabot_review, "wait_for_mergeable",
                        lambda n, r: True)
    monkeypatch.setattr(dependabot_review, "squash_merge", lambda n, r: True)
    monkeypatch.setattr(dependabot_review.time, "sleep", lambda s: None)
    return calls


def _suite_commands(calls: dict[str, list]) -> list[list[str]]:
    return [c for c in calls["run"] if c[0] == "poetry" or "pytest" in c]


def test_head_without_guard_is_deferred_untested_and_rebased(
        tmp_path, monkeypatch, capsys):
    """#4736 test 1: main has the guard, the head lacks it, the PR is stale."""
    calls = _wire(monkeypatch, head_has_guard=False, stale=True)

    result = dependabot_review._process_pr_inside_worktree(
        _pr(), "owner/repo", tmp_path)

    assert result == "deferred"
    assert calls["install"] == [], "poetry install must not run unguarded"
    assert calls["tests"] == [], "pytest must not run unguarded"
    assert calls["evict"] == []
    assert calls["baseline"] == [], "the baseline must not run either"
    assert _suite_commands(calls) == []
    assert calls["approvals"] == []

    out = capsys.readouterr().out
    assert "SKIP GATE" in out
    assert GUARD in out
    assert "#4736" in out
    assert GUARD in result.reason
    assert "not run" in result.reason

    assert len(calls["reviews"]) == 1
    assert "fake-root guard" in calls["reviews"][0]
    assert len(calls["rebase"]) == 1
    explanation = calls["rebase"][0]
    assert explanation is not None and GUARD in explanation
    assert "Test suite failed" not in explanation, (
        "the rebase comment must not claim a suite failed that never ran")
    assert calls["recreate"] == []


def test_head_without_guard_on_current_branch_is_not_recreated(
        tmp_path, monkeypatch, capsys):
    """A current multi-package head that lacks the guard is not split:
    nothing failed, so there is nothing to isolate."""
    calls = _wire(monkeypatch, head_has_guard=False, stale=False,
                  package_count=3)

    result = dependabot_review._process_pr_inside_worktree(
        _pr(), "owner/repo", tmp_path)

    assert result == "deferred"
    assert calls["install"] == [] and calls["tests"] == []
    assert calls["rebase"] == []
    assert calls["recreate"] == []
    assert "SKIP GATE" in capsys.readouterr().out


def test_head_with_guard_runs_install_and_pytest(tmp_path, monkeypatch, capsys):
    """#4736 test 2: when the head carries the guard, the gate runs as before."""
    calls = _wire(monkeypatch, head_has_guard=True)

    result = dependabot_review._process_pr_inside_worktree(
        _pr(), "owner/repo", tmp_path)

    assert calls["install"] == [tmp_path]
    assert calls["tests"] == [tmp_path]
    assert result == "merged"
    assert calls["approvals"] and "pytest passed" in calls["approvals"][0]
    assert "SKIP GATE" not in capsys.readouterr().out


def test_guard_check_error_is_errored_and_runs_nothing(
        tmp_path, monkeypatch, capsys):
    calls = _wire(monkeypatch, head_has_guard=True)
    monkeypatch.setattr(dependabot_review, "fake_root_guard_gap",
                        lambda worktree, rev="HEAD", fetch=True: ([], "boom"))

    result = dependabot_review._process_pr_inside_worktree(
        _pr(), "owner/repo", tmp_path)

    assert result == "errored"
    assert "boom" in result.reason
    assert calls["tests"] == [], "no pytest call after a failed guard check"
    assert calls["install"] == []
    assert _suite_commands(calls) == []
    assert calls["approvals"] == []
    assert "boom" in capsys.readouterr().out
