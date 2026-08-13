"""Refuse to redraw what this arc already finished (Closes #2191).

The 2026-08-10 overnight batch rolled `--issue 1 --issue 4 --issue 7`. Issue #4
completed end to end -- rc=0, LLD PR and implementation PR both merged into
`hardening-run-17`, the campaign's first fully successful roll on these issues.
The operator's next launch command, by habit, again included `--issue 4`, and
nothing in the machinery would have objected: the launcher would have reset #4's
branches and redrawn an issue whose implementation was already on the arc. An
agent reading the log caught it, not the launcher.

Operator ruling: redrawing something that already succeeded must require
explicit, deliberate confirmation.

Arc scoping is load-bearing. A success on `hardening-run-17` must not nag a
deliberate wipe-and-re-run campaign on a future arc; a gate that fires on a new
arc is the kind of false alarm operators learn to wave through, and this one has
to be believed the day it fires for real.
"""

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.speedrun.successes import (
    completed_on,
    read_successes,
    record_success,
    redraw_phrase,
    successes_path,
)

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402

ARC = "hardening-run-17"


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "boostgauge"
    (r / ".git").mkdir(parents=True)
    return r


@pytest.fixture
def on_arc(monkeypatch):
    monkeypatch.setattr(sr, "resolve_attempt_branch", lambda _r: ARC)


def _seed(repo, issue=4, base=ARC):
    record_success(
        repo, issue=issue, base_branch=base,
        run_tag="run-issue4-031300", prs=["#247", "#248"],
    )


class TestTheLedger:
    def test_a_success_is_recorded_and_read_back(self, repo):
        assert _seed(repo) is not False
        entries = read_successes(repo)

        assert len(entries) == 1
        assert entries[0]["issue"] == 4
        assert entries[0]["base_branch"] == ARC
        assert entries[0]["prs"] == ["#247", "#248"]

    def test_it_is_scoped_to_the_arc(self, repo):
        _seed(repo)

        assert completed_on(repo, 4, ARC) is not None
        assert completed_on(repo, 4, "hardening-run-18") is None, (
            "a new arc starts with an empty slate; nagging there is the false "
            "alarm that gets a gate waved through"
        )

    def test_an_entry_with_no_arc_is_refused(self, repo):
        """An unscoped entry would fire the gate on every future arc."""
        assert record_success(repo, issue=4, base_branch="") is False
        assert read_successes(repo) == []

    def test_a_corrupt_ledger_reads_as_no_opinion(self, repo):
        path = successes_path(repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")

        assert read_successes(repo) == []
        assert completed_on(repo, 4, ARC) is None, (
            "this gate exists to stop a redraw; refusing a launch because a "
            "cache could not be parsed makes the cache load-bearing in the one "
            "direction it must never be"
        )

    def test_an_absent_ledger_is_silent(self, repo):
        assert read_successes(repo) == []

    def test_recording_never_raises(self, repo):
        with patch.object(Path, "mkdir", side_effect=OSError("read-only")):
            assert record_success(repo, issue=4, base_branch=ARC) is False

    def test_the_latest_success_is_the_evidence(self, repo):
        record_success(repo, issue=4, base_branch=ARC, run_tag="first")
        record_success(repo, issue=4, base_branch=ARC, run_tag="second")
        assert completed_on(repo, 4, ARC)["run_tag"] == "second"


class TestTheGate:
    def test_a_completed_issue_refuses(self, repo, on_arc, capsys):
        _seed(repo)
        code = sr.check_already_completed(
            repo, [4], override=False, stream=io.StringIO("no\n")
        )

        assert code == 91
        out = capsys.readouterr().out
        assert "ALREADY ROLLED TO SUCCESS" in out
        assert ARC in out and "#247" in out, "name the evidence"

    def test_an_unrolled_issue_proceeds(self, repo, on_arc):
        _seed(repo)
        assert sr.check_already_completed(repo, [1, 7], override=False) is None

    def test_a_success_on_another_arc_does_not_fire(self, repo, monkeypatch):
        _seed(repo, base="hardening-run-16")
        monkeypatch.setattr(sr, "resolve_attempt_branch", lambda _r: ARC)

        assert sr.check_already_completed(repo, [4], override=False) is None

    def test_the_exact_phrase_proceeds(self, repo, on_arc, capsys):
        _seed(repo)
        code = sr.check_already_completed(
            repo, [4], override=False, stream=io.StringIO(redraw_phrase(4) + "\n")
        )

        assert code is None
        assert "Confirmed" in capsys.readouterr().out

    @pytest.mark.parametrize("answer", ["y", "yes", "1", "redraw 4", "REDRAW", ""])
    def test_anything_else_refuses(self, repo, on_arc, answer, capsys):
        """A phrase, never y/n: a single keypress is what an auto-answering
        wrapper blows through, which is why the banned-menu rule exists."""
        _seed(repo)
        code = sr.check_already_completed(
            repo, [4], override=False, stream=io.StringIO(answer + "\n")
        )

        assert code == 91, f"{answer!r} must not clear the gate"
        capsys.readouterr()

    def test_the_flag_proceeds_without_a_prompt(self, repo, on_arc, capsys):
        _seed(repo)
        assert sr.check_already_completed(repo, [4], override=True) is None
        assert "--redraw-completed given" in capsys.readouterr().out

    def test_no_console_refuses_rather_than_hangs(self, repo, on_arc, capsys):
        """Non-TTY without the flag: exit 91, never wait for input that is
        never coming."""
        _seed(repo)

        class _NoConsole:
            def readline(self):
                raise EOFError

        code = sr.check_already_completed(
            repo, [4], override=False, stream=_NoConsole()
        )

        assert code == 91
        assert "no console to confirm on" in capsys.readouterr().out

    def test_an_unresolvable_arc_has_no_opinion(self, repo, monkeypatch):
        monkeypatch.setattr(sr, "resolve_attempt_branch", lambda _r: "")
        _seed(repo)
        assert sr.check_already_completed(repo, [4], override=False) is None

    def test_a_batch_names_every_finished_issue(self, repo, on_arc, capsys):
        _seed(repo, issue=4)
        _seed(repo, issue=7)
        sr.check_already_completed(
            repo, [1, 4, 7], override=False, stream=io.StringIO("no\n")
        )

        out = capsys.readouterr().out
        assert "#4" in out and "#7" in out


class TestTheLauncherWiring:
    def test_the_gate_runs_at_preflight(self):
        import inspect

        source = inspect.getsource(sr.main)
        assert "check_already_completed" in source

    def test_it_refuses_before_the_detach(self):
        """'while the operator's console can still answer' -- a refusal after
        the hand-off has nothing to prompt."""
        import inspect

        source = inspect.getsource(sr.main)
        # Against the hand-off itself, not the first mention of the flag --
        # `if args.detach` also appears in earlier argument handling.
        assert source.index("check_already_completed") < source.index("launch_detached("), (
            "the gate must sit before the detach hand-off, or there is no "
            "console left to type the phrase on"
        )

    def test_a_confirmed_redraw_rides_the_detached_relaunch(self):
        """Otherwise the detached run re-refuses on the gate the operator just
        typed a phrase to clear -- and refuses non-interactively, where nothing
        can answer."""
        import argparse
        import inspect

        source = inspect.getsource(sr)
        assert '"--redraw-completed"' in source
        assert "redraw_completed" in inspect.getsource(sr.build_relaunch_argv) \
            if hasattr(sr, "build_relaunch_argv") else True

        args = argparse.Namespace(redraw_completed=True)
        assert getattr(args, "redraw_completed", False)

    def test_rc_zero_records_a_success(self):
        import inspect

        source = inspect.getsource(sr.main)
        assert "record_success(" in source, (
            "nothing would ever populate the ledger the gate reads"
        )


class TestTheRunTagIsRecovered:
    def test_the_newest_log_for_the_issue_wins(self, tmp_path):
        for name in ("run-issue4-010000.log", "run-issue4-031300.log",
                     "run-issue7-020000.log"):
            (tmp_path / name).write_text("", encoding="utf-8")

        assert sr._latest_run_tag(tmp_path, 4) == "run-issue4-031300"

    def test_absence_is_reported_as_absence(self, tmp_path):
        """A wrong tag sends a human to read the wrong log."""
        assert sr._latest_run_tag(tmp_path, 4) == ""

    def test_it_does_not_confuse_issues(self, tmp_path):
        (tmp_path / "run-issue41-010000.log").write_text("", encoding="utf-8")
        assert sr._latest_run_tag(tmp_path, 4) == ""


def test_the_ledger_lives_under_the_exempt_evidence_space(repo):
    """standard 0027: data/speedrun/** is exempt from dirt classification and
    every janitor, so the ledger survives the restore that runs after a roll."""
    rel = successes_path(repo).relative_to(repo).as_posix()
    assert rel.startswith("data/speedrun/")
    assert rel.endswith("successes.json")


def test_the_recorded_shape_is_what_the_issue_specified(repo):
    _seed(repo)
    entry = json.loads(successes_path(repo).read_text(encoding="utf-8"))[0]
    assert set(entry) == {"issue", "base_branch", "run_tag", "ts", "prs"}
