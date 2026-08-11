"""Acceptance tests for the must-resolve launch gate (#2073).

The seven tests named in the issue body are the acceptance criteria.

The gate is exercised through `speedrun_roll.main`, so "nothing is spent" is a
real assertion about what the launcher did, not a claim about a helper.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import speedrun_roll  # noqa: E402

from assemblyzero.speedrun.must_resolve import (  # noqa: E402
    open_must_resolve_issues,
    refusal_message,
)

BLOCKING = [
    {"number": 224, "title": "must-resolve: #4 requirements conflict — handle-count cadence"},
    {"number": 231, "title": "must-resolve: #9 requirements conflict — retry budget"},
]


class FakeGh:
    def __init__(self, issues=None, *, list_fails=False, remote="https://github.com/martymcenroe/boostgauge.git"):
        self.issues = issues if issues is not None else []
        self.list_fails = list_fails
        self.remote = remote
        self.list_calls = 0
        self.calls: list[list[str]] = []

    def __call__(self, args):
        self.calls.append(list(args))
        if args[0] == "git":
            if self.remote is None:
                return subprocess.CompletedProcess(args, 1, "", "no remote")
            return subprocess.CompletedProcess(args, 0, self.remote, "")
        if "issue" in args and "list" in args:
            self.list_calls += 1
            if self.list_fails:
                return subprocess.CompletedProcess(args, 1, "", "could not connect to github.com")
            return subprocess.CompletedProcess(args, 0, json.dumps(self.issues), "")
        return subprocess.CompletedProcess(args, 0, "", "")


@pytest.fixture
def target_repo(tmp_path) -> Path:
    """The launcher validates --repo is a git repository root before the gate."""
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "Test"],
    ):
        subprocess.run(["git", "-C", str(tmp_path), *args], capture_output=True, text=True)
    (tmp_path / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-qm", "base"], capture_output=True
    )
    return tmp_path


@pytest.fixture
def launcher(monkeypatch, target_repo):
    """speedrun_roll.main with everything past the gate stubbed out."""
    state = {"rolls": [], "detached": 0, "base_calls": 0}

    monkeypatch.setattr(speedrun_roll, "check_assemblyzero_tree", lambda _root: [])
    monkeypatch.setattr(
        speedrun_roll, "sweep_pipeline_worktrees",
        lambda *_a, **_k: type("Sweep", (), {"problems": []})(),
    )
    monkeypatch.setattr(speedrun_roll, "install_signal_handlers", lambda _s: None)

    def fake_roll(repo_root, issue, log_dir, az_root, extra):
        state["rolls"].append(issue)
        return 0

    def fake_ensure_base(*_a, **_kw):
        state["base_calls"] += 1
        return "hardening-run-1"

    def fake_detach(*_a, **_kw):
        state["detached"] += 1
        return 0

    monkeypatch.setattr(speedrun_roll, "roll_issue", fake_roll)
    monkeypatch.setattr(speedrun_roll, "ensure_base", fake_ensure_base)
    monkeypatch.setattr(speedrun_roll, "launch_detached", fake_detach)
    return state


def _argv(target_repo, *issues, detach=False):
    args = ["--repo", str(target_repo), "--log-dir", str(target_repo / "logs")]
    for issue in issues:
        args += ["--issue", str(issue)]
    if detach:
        args.append("--detach")
    return args


# --- "exits 91 and the message names the issue number and title" ----------


def test_open_must_resolve_refuses_with_91_naming_number_and_title(
    launcher, monkeypatch, target_repo, capsys
):
    monkeypatch.setattr(
        speedrun_roll, "open_must_resolve_issues", lambda _r: (BLOCKING, None)
    )

    code = speedrun_roll.main(_argv(target_repo, 4))

    assert code == 91
    out = capsys.readouterr().out
    assert "224" in out and "handle-count cadence" in out
    assert "231" in out and "retry budget" in out


# --- "with none open, the roll proceeds" ---------------------------------


def test_no_open_must_resolve_lets_the_roll_proceed(launcher, monkeypatch, target_repo):
    monkeypatch.setattr(speedrun_roll, "open_must_resolve_issues", lambda _r: ([], None))

    code = speedrun_roll.main(_argv(target_repo, 4))

    assert code == 0
    assert launcher["rolls"] == [4]


# --- "with gh erroring, the launcher warns and proceeds" -----------------


def test_gh_failure_warns_and_proceeds(launcher, monkeypatch, target_repo, capsys):
    monkeypatch.setattr(
        speedrun_roll, "open_must_resolve_issues",
        lambda _r: ([], "could not connect to github.com"),
    )

    code = speedrun_roll.main(_argv(target_repo, 4))

    assert code == 0, "GitHub being unreachable must not brick a local roll"
    assert launcher["rolls"] == [4]
    assert "WARNING" in capsys.readouterr().out


def test_offline_gh_is_reported_as_an_error_not_an_empty_list(tmp_path):
    gh = FakeGh(list_fails=True)
    issues, error = open_must_resolve_issues(tmp_path, runner=gh)
    assert issues == []
    assert error and "github.com" in error


def test_no_remote_is_an_error_not_a_clean_pass(tmp_path):
    gh = FakeGh(remote=None)
    issues, error = open_must_resolve_issues(tmp_path, runner=gh)
    assert issues == [] and error


# --- "checked once per invocation, not once per redraw" ------------------


def test_gate_runs_once_per_invocation_not_per_redraw(
    launcher, monkeypatch, target_repo
):
    calls = {"n": 0}

    def counting(_repo):
        calls["n"] += 1
        return [], None

    monkeypatch.setattr(speedrun_roll, "open_must_resolve_issues", counting)

    # Three issues, each allowed three attempts: nine roll opportunities.
    def failing_roll(repo_root, issue, log_dir, az_root, extra):
        launcher["rolls"].append(issue)
        return 1

    monkeypatch.setattr(speedrun_roll, "roll_issue", failing_roll)

    speedrun_roll.main(_argv(target_repo, 4, 9, 12) + ["--attempts", "1"])

    # #2206 retired redraws, so the batch halts at the first failure: #4
    # rolls once and #9/#12 never start. The invariant this test protects --
    # the wall is queried once per invocation, never once per roll -- holds
    # more simply than it did when redraws could multiply the queries.
    assert launcher["rolls"] == [4], "one roll per issue, then the batch halts"
    assert calls["n"] == 1, "the wall is checked once per invocation"


# --- "a batch is refused as a whole, not partially rolled" ---------------


def test_batch_is_refused_as_a_whole(launcher, monkeypatch, target_repo):
    monkeypatch.setattr(
        speedrun_roll, "open_must_resolve_issues", lambda _r: (BLOCKING, None)
    )

    code = speedrun_roll.main(_argv(target_repo, 4, 9, 12))

    assert code == 91
    assert launcher["rolls"] == [], "no issue in the batch may roll"


# --- "the refusal happens before ensure_base does any work" --------------


def test_refusal_spends_nothing_and_creates_no_branch(launcher, monkeypatch, target_repo):
    monkeypatch.setattr(
        speedrun_roll, "open_must_resolve_issues", lambda _r: (BLOCKING, None)
    )

    code = speedrun_roll.main(_argv(target_repo, 4))

    assert code == 91
    assert launcher["base_calls"] == 0, "ensure_base must not have been reached"
    assert launcher["rolls"] == []


def test_refusal_happens_before_the_detach_handoff(launcher, monkeypatch, target_repo):
    # Otherwise the refusal would land inside a scheduled task nobody is watching.
    monkeypatch.setattr(
        speedrun_roll, "open_must_resolve_issues", lambda _r: (BLOCKING, None)
    )

    code = speedrun_roll.main(_argv(target_repo, 4, detach=True))

    assert code == 91
    assert launcher["detached"] == 0


# --- "the refusal message is plain English, no internal identifiers" -----


def test_refusal_message_is_plain_english():
    message = refusal_message(BLOCKING)

    # Names the issues so the operator can act without looking anything up.
    assert "#224" in message and "#231" in message
    assert "handle-count cadence" in message

    # Judge the message's OWN prose. The quoted issue titles are data the
    # message is required to reproduce verbatim, and they carry the label name
    # because that is what the filer titles them -- scanning them would force
    # the message to stop naming the issues, which is the opposite of the goal.
    titles = {i["title"] for i in BLOCKING}
    prose = "\n".join(
        line for line in message.splitlines()
        if not any(t in line for t in titles)
    ).lower()

    for jargon in ("n0c", "must-resolve", "preflight", "ensure_base", "gate",
                   "#1899", "#2072", "#2073", "exit 91", "label", "stage"):
        assert jargon not in prose, f"{jargon!r} is internal jargon in the message's prose"

    # Says what to do, not merely that something is wrong.
    assert "close" in prose and "edit" in prose


def test_refusal_message_singular_and_plural_read_correctly():
    one = refusal_message(BLOCKING[:1])
    many = refusal_message(BLOCKING)
    assert "1 unanswered question " in one
    assert "2 unanswered questions " in many


def test_open_must_resolve_reads_number_and_title(tmp_path):
    gh = FakeGh(issues=[{"number": 224, "title": "a title"}])
    issues, error = open_must_resolve_issues(tmp_path, runner=gh)
    assert error is None
    assert issues == [{"number": 224, "title": "a title"}]

    listing = [c for c in gh.calls if "issue" in c and "list" in c][0]
    assert listing[listing.index("--label") + 1] == "must-resolve"
    assert listing[listing.index("--state") + 1] == "open"
