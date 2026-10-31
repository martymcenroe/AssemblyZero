"""The launcher's refusals that sit between preflight and roll.

#4257: the contract-fidelity preflight's refuse flag stops a launch with exit
91, as the form preflight's does.

The gate is driven through `speedrun_roll.main`, so "starts nothing" is an
assertion about what the launcher did (no roll, no detach), not about a helper.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import _gate
import speedrun_reset
import speedrun_roll


@pytest.fixture
def target_repo(tmp_path) -> Path:
    """The launcher validates --repo is a git repository root first."""
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "Test"],
    ):
        subprocess.run(["git", "-C", str(tmp_path), *args], capture_output=True, text=True, check=False)
    (tmp_path / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True, check=False)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "base"], capture_output=True, check=False)
    return tmp_path


@pytest.fixture
def launcher(monkeypatch, target_repo):
    """speedrun_roll.main with everything past the preflights stubbed out."""
    state = {"rolls": [], "roll_kwargs": [], "detached": 0, "base_calls": 0}

    monkeypatch.setattr(speedrun_roll, "check_assemblyzero_tree", lambda _root: [])
    monkeypatch.setattr(speedrun_roll, "open_must_resolve_issues", lambda _r: ([], None))
    monkeypatch.setattr(
        speedrun_roll, "sweep_pipeline_worktrees",
        lambda *_a, **_k: type("Sweep", (), {"problems": []})(),
    )
    monkeypatch.setattr(speedrun_roll, "install_signal_handlers", lambda _s: None)

    def fake_roll(repo_root, issue, log_dir, az_root, extra, *a, **k):
        state["rolls"].append(issue)
        state["roll_kwargs"].append(k)
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


def _argv(target_repo, *issues, extra=()):
    args = ["--repo", str(target_repo), "--log-dir", str(target_repo / "logs")]
    for issue in issues:
        args += ["--issue", str(issue)]
    return args + list(extra)


class TestFidelityRefusalStopsTheLaunch:
    """#4257 T1 and T2."""

    def test_a_refusing_fidelity_preflight_returns_91_and_starts_nothing(
        self, launcher, monkeypatch, target_repo, capsys
    ):
        monkeypatch.setattr(
            speedrun_roll, "check_contract_fidelity_at_preflight",
            lambda *_a, **_k: ("CONTRACT FIDELITY\n  #4: the audit was NOT REACHED.", True),
        )

        code = speedrun_roll.main(_argv(target_repo, 4))

        assert code == 91
        assert launcher["rolls"] == [], "a refused launch must not roll"
        assert launcher["detached"] == 0
        assert launcher["base_calls"] == 0, "nothing may be set up after the refusal"
        out = capsys.readouterr().out
        assert "NOT REACHED" in out, "the preflight's own reason is printed"
        assert "BLOCKED" in out and "fidelity" in out

    def test_a_refusing_fidelity_preflight_stops_a_detached_launch_too(
        self, launcher, monkeypatch, target_repo
    ):
        monkeypatch.setattr(
            speedrun_roll, "check_contract_fidelity_at_preflight",
            lambda *_a, **_k: ("refused", True),
        )

        code = speedrun_roll.main(_argv(target_repo, 4, extra=["--detach"]))

        assert code == 91
        assert launcher["detached"] == 0

    def test_a_passing_fidelity_preflight_launches_as_before(
        self, launcher, monkeypatch, target_repo
    ):
        monkeypatch.setattr(
            speedrun_roll, "check_contract_fidelity_at_preflight",
            lambda *_a, **_k: ("CONTRACT FIDELITY\n  #4: no defect found.", False),
        )

        code = speedrun_roll.main(_argv(target_repo, 4))

        assert code == 0
        assert launcher["rolls"] == [4]


# ---------------------------------------------------------------------------
# #4221: --fresh is the dry run; --fresh --execute asks for the typed phrase
# ---------------------------------------------------------------------------

PHRASE = _gate.gate_phrase("reset-issues", "owner/repo #4")


class Fresh:
    """What a `--fresh` launch touches, recorded: gh calls, and `reset_one_issue`."""

    def __init__(self):
        self.gh_calls: list[list[str]] = []
        self.resets: list[int] = []
        self.prompts = 0


@pytest.fixture
def fresh(monkeypatch, launcher, target_repo, tmp_path) -> Fresh:
    seen = Fresh()
    subprocess.run(["git", "-C", str(target_repo), "branch", "issue-4"], check=False,
                   capture_output=True)
    monkeypatch.setattr(speedrun_roll.reset, "_gh_repo", lambda _r: "owner/repo")
    monkeypatch.setattr(_gate, "GATE_REFUSAL_LOG", tmp_path / "gate-refusals.jsonl")

    real_run = speedrun_reset._run

    def run(cmd, cwd=None, check=False):
        if cmd[0] == "gh":
            seen.gh_calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        return real_run(cmd, cwd=cwd, check=check)

    monkeypatch.setattr(speedrun_reset, "_run", run)
    monkeypatch.setattr(
        speedrun_roll.reset, "reset_one_issue",
        lambda _root, _repo, issue, *a, **k: seen.resets.append(issue),
    )
    return seen


def _answer(monkeypatch, fresh: Fresh, *answers):
    queue = list(answers)

    def fake_input(prompt=""):
        fresh.prompts += 1
        answer = queue.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    monkeypatch.setattr("builtins.input", fake_input)


def _branches(repo) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "for-each-ref"], capture_output=True, text=True, check=False,
    ).stdout


class TestFreshNeedsExecuteAndTheTypedPhrase:
    def test_fresh_alone_prints_the_plan_and_writes_nothing(
        self, fresh, launcher, monkeypatch, target_repo, capsys
    ):
        """T2 (R2)."""
        _answer(monkeypatch, fresh)
        before = _branches(target_repo)

        code = speedrun_roll.main(_argv(target_repo, 4, extra=["--fresh"]))

        out = capsys.readouterr().out
        assert code == 0
        assert "RESET PLAN" in out and "issue-4" in out
        assert "NOTHING WAS RESET AND NO ROLL WAS STARTED" in out
        assert PHRASE in out, "the dry run names the phrase --execute will ask for"
        assert fresh.prompts == 0
        assert fresh.resets == [] and launcher["rolls"] == [] and launcher["base_calls"] == 0
        assert [c for c in fresh.gh_calls if c[1:3] in (["pr", "close"], ["issue", "reopen"])] == []
        assert _branches(target_repo) == before
        assert not (target_repo / "logs").exists(), "no log directory, no write at all"

    def test_fresh_execute_without_the_phrase_changes_nothing(
        self, fresh, launcher, monkeypatch, target_repo, capsys
    ):
        """T1 (R1): a wrong phrase, and no console at all."""
        for answer in ("yes", "", EOFError()):
            _answer(monkeypatch, fresh, answer)
            before = _branches(target_repo)

            code = speedrun_roll.main(_argv(target_repo, 4, extra=["--fresh", "--execute"]))

            assert code == 91, answer
            assert "BLOCKED" in capsys.readouterr().out
            assert fresh.resets == [] and launcher["rolls"] == [] and launcher["base_calls"] == 0
            assert _branches(target_repo) == before
        assert [c for c in fresh.gh_calls if c[1:3] == ["pr", "close"]] == []

    def test_fresh_execute_with_the_phrase_goes_on_to_roll_fresh(
        self, fresh, launcher, monkeypatch, target_repo
    ):
        _answer(monkeypatch, fresh, PHRASE)

        code = speedrun_roll.main(_argv(target_repo, 4, extra=["--fresh", "--execute"]))

        assert code == 0 and fresh.prompts == 1
        assert launcher["rolls"] == [4]
        assert launcher["roll_kwargs"] == [{"fresh": True}], "the roll is told --fresh"

    def test_the_phrase_names_the_repository_and_every_issue(
        self, fresh, launcher, monkeypatch, target_repo
    ):
        _answer(monkeypatch, fresh, PHRASE)  # names only #4, but two issues are rolled
        code = speedrun_roll.main(
            _argv(target_repo, 4, 9, extra=["--fresh", "--execute"])
        )
        assert code == 91 and launcher["rolls"] == []
        assert speedrun_reset.reset_phrase("owner/repo", [4, 9]) == (
            "approve forbidden reset-issues for owner/repo #4 #9"
        )

    def test_without_fresh_execute_does_nothing_and_asks_nothing(
        self, fresh, launcher, monkeypatch, target_repo
    ):
        _answer(monkeypatch, fresh)
        code = speedrun_roll.main(_argv(target_repo, 4, extra=["--execute"]))
        assert code == 0 and fresh.prompts == 0 and launcher["rolls"] == [4]

    def test_the_phrase_is_asked_on_the_console_before_the_detach(
        self, fresh, launcher, monkeypatch, target_repo
    ):
        order: list[str] = []
        monkeypatch.setattr(
            "builtins.input", lambda p="": order.append("phrase") or PHRASE,
        )
        handed_off: list = []

        def detach(args, extra, repo_root, az_root, log_dir):
            order.append("detach")
            handed_off.append((args, extra, repo_root, az_root, log_dir))
            return 0

        monkeypatch.setattr(speedrun_roll, "launch_detached", detach)

        code = speedrun_roll.main(
            _argv(target_repo, 4, extra=["--fresh", "--execute", "--detach", "--no-follow"])
        )

        assert code == 0 and order == ["phrase", "detach"]
        child = speedrun_roll.detached_argv(*handed_off[0])
        assert "--fresh" in child and "--execute" in child and "--fresh-confirmed" in child

    def test_a_refused_phrase_never_reaches_the_detach(
        self, fresh, launcher, monkeypatch, target_repo
    ):
        _answer(monkeypatch, fresh, "no")
        code = speedrun_roll.main(
            _argv(target_repo, 4, extra=["--fresh", "--execute", "--detach", "--no-follow"])
        )
        assert code == 91 and launcher["detached"] == 0

    def test_the_detached_child_proceeds_without_a_prompt_when_confirmed(
        self, fresh, launcher, monkeypatch, target_repo, tmp_path
    ):
        _answer(monkeypatch, fresh, AssertionError("a detached child must never prompt"))
        monkeypatch.setattr(speedrun_roll, "_redirect_stdio", lambda _p: None)

        code = speedrun_roll.main(_argv(target_repo, 4, extra=[
            "--fresh", "--execute", "--fresh-confirmed",
            "--detached-stdout", str(tmp_path / "launcher.log"),
        ]))

        assert code == 0 and fresh.prompts == 0 and launcher["rolls"] == [4]

    def test_the_detached_child_refuses_rather_than_prompts_when_not_confirmed(
        self, fresh, launcher, monkeypatch, target_repo, tmp_path
    ):
        _answer(monkeypatch, fresh, AssertionError("a detached child must never prompt"))
        monkeypatch.setattr(speedrun_roll, "_redirect_stdio", lambda _p: None)

        code = speedrun_roll.main(_argv(target_repo, 4, extra=[
            "--fresh", "--execute", "--detached-stdout", str(tmp_path / "launcher.log"),
        ]))

        assert code == 91 and fresh.prompts == 0
        assert launcher["rolls"] == [] and fresh.resets == []

    def test_typing_fresh_confirmed_by_hand_skips_nothing(
        self, fresh, launcher, monkeypatch, target_repo
    ):
        _answer(monkeypatch, fresh, "no")
        code = speedrun_roll.main(
            _argv(target_repo, 4, extra=["--fresh", "--execute", "--fresh-confirmed"])
        )
        assert code == 91 and fresh.prompts == 1 and launcher["rolls"] == []

    def test_an_unconfirmed_fresh_is_not_carried_to_a_detached_relaunch(self):
        import argparse

        args = argparse.Namespace(
            issue=[4], attempts=1, fresh=True, execute=True, fresh_confirmed=False,
        )
        argv = speedrun_roll.detached_argv(args, [], Path("/r"), Path("/a"), Path("/l"))
        assert "--fresh" in argv and "--fresh-confirmed" not in argv

    def test_the_runbooks_teach_the_two_step_reset(self):
        docs = Path(__file__).resolve().parents[2] / "docs" / "runbooks"
        compare = (docs / "0956-compare-model-profiles-on-boostgauge.md").read_text(encoding="utf-8")
        solo = (docs / "0952-speedrun-operator-solo.md").read_text(encoding="utf-8")
        rolls = [
            line for line in compare.splitlines()
            if line.startswith("poetry run python tools/speedrun_roll.py") and "--fresh" in line
        ]
        assert len(rolls) == 4
        assert [("--execute" in line) for line in rolls] == [False, True, True, True], (
            "the first is the dry run the runbook says to read; every other --fresh command executes"
        )
        assert "only prints what it would close, delete and remove" in compare
        assert "can lose its commits" not in compare and "cannot see a roll that is already" not in compare
        assert "`--execute`" in solo and "approve forbidden reset-issues" in solo

    def test_every_help_text_that_names_the_destructive_flag_names_execute(self):
        source = (Path(__file__).resolve().parents[2] / "tools" / "speedrun_roll.py").read_text(
            encoding="utf-8"
        )
        assert "Relaunch with --fresh --execute to roll" in source
        assert "relaunch with --fresh --execute to reset" in source
        assert "Relaunch with --fresh to roll" not in source
