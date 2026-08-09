"""The verdict, the conflict classification, and the prerequisite gate
(#2165, #2166, #2167).

A roll ended 2026-08-09 with `exit 1` as its last word: the operator had to
interpret the code, nothing said "resolve #228 and #229", nothing said
"do not re-roll", and the redraw loop had already burned two draws against
an issue whose verdict said no draw could help. These pin the repairs: the
conflict exit code and its never-redraw/continue-the-batch classification,
the verdict block as the narration's last words, and the prerequisite file
that makes the next launch refuse while the questions stay open.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def _healthy_box(*_args, **_kwargs):
    from assemblyzero.speedrun.box_health import BoxHealth

    return BoxHealth(True, [], "")

import speedrun_roll as sr  # noqa: E402

from assemblyzero.core.exit_codes import (  # noqa: E402
    CONFLICT_EXIT_CODE,
    CONFLICT_MARKER,
    is_requirements_conflict,
)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "boostgauge"
    (r / ".git").mkdir(parents=True)
    return r


QUESTIONS = [
    {"number": 228, "title": "must-resolve: #1 needle visibility at 75"},
    {"number": 229, "title": "must-resolve: #1 arc 60-100 vs mid-arc 50"},
]


def _main(repo, issues, rolls, *, questions=None, gh_error=None, extra_argv=()):
    """Run main() with scripted per-issue roll results.

    `rolls` maps issue number to a list of exit codes, one per attempt.
    """
    counts = {i: 0 for i in rolls}

    def _roll(repo_root, issue, log_dir, az_root, _extra):
        result = rolls[issue][min(counts[issue], len(rolls[issue]) - 1)]
        counts[issue] += 1
        return result

    argv = ["--repo", str(repo), "--attempts", "3", *extra_argv]
    for i in issues:
        argv += ["--issue", str(i)]

    # Stateful: the PREFLIGHT query (call 1) sees a repo with no open
    # questions, as in real life -- the run FILES them, so only the
    # verdict-time query (call 2+) returns them.
    calls = {"n": 0}

    def _must_resolve(_repo):
        calls["n"] += 1
        if calls["n"] == 1:
            return [], None
        return (questions or [], gh_error)

    with patch.object(sr, "check_assemblyzero_tree", lambda p: []), \
            patch.object(sr, "check_box_health", _healthy_box), \
            patch.object(sr, "open_must_resolve_issues", _must_resolve), \
            patch.object(sr, "roll_issue", _roll), \
            patch.object(sr, "restore_repo", lambda *a: []), \
            patch.object(sr.time, "sleep", lambda s: None):
        code = sr.main(argv)
    return code, counts


class TestConflictClassification:
    def test_the_marker_is_pinned_to_its_source(self):
        """The exit-code module's copy must never drift from the analysis
        gate's canonical marker."""
        from assemblyzero.workflows.requirements.nodes.analyze_requirements import (
            REQUIREMENTS_CONFLICT_MARKER,
        )
        assert CONFLICT_MARKER == REQUIREMENTS_CONFLICT_MARKER

    def test_detection_reads_the_protocol_prefix(self):
        assert is_requirements_conflict(
            "REQUIREMENTS CONFLICT: no spec can satisfy both readings"
        )
        assert not is_requirements_conflict("MECHANICAL VALIDATION FAILED")
        assert not is_requirements_conflict(None)

    def test_a_conflict_is_never_redrawn(self, repo):
        _code, counts = _main(repo, [1], {1: [CONFLICT_EXIT_CODE]},
                              questions=QUESTIONS)
        assert counts[1] == 1, "no redraw can help an ambiguous issue"

    def test_the_batch_continues_past_a_blocked_issue(self, repo):
        """Today's shape: with this classification, #4 and #7 would have
        rolled while #1 waited for its ruling."""
        code, counts = _main(
            repo, [1, 4, 7],
            {1: [CONFLICT_EXIT_CODE], 4: [0], 7: [0]},
            questions=QUESTIONS,
        )
        assert counts[4] == 1 and counts[7] == 1
        assert code == CONFLICT_EXIT_CODE, "the batch result names the block"

    def test_a_generic_failure_still_redraws_and_stops(self, repo):
        code, counts = _main(repo, [1, 4], {1: [1, 1, 1], 4: [0]})
        assert counts[1] == 3, "generic failures keep the redraw budget"
        assert counts.get(4, 0) == 0, "exhaustion still stops the batch"
        assert code == 1


class TestVerdictBlock:
    def test_blocked_verdict_names_questions_and_forbids_rerolling(
        self, repo, capsys
    ):
        _main(repo, [1], {1: [CONFLICT_EXIT_CODE]}, questions=QUESTIONS)
        out = capsys.readouterr().out
        assert "ROLL BLOCKED" in out
        assert "#228" in out and "#229" in out
        assert "resolve #228 and #229" in out
        assert "Do not re-roll without resolution" in out
        assert "--override-prereqs" in out

    def test_success_verdict_states_it_in_words(self, repo, capsys):
        code, _ = _main(repo, [4, 7], {4: [0], 7: [0]})
        out = capsys.readouterr().out
        assert code == 0
        assert "ROLL SUCCEEDED: all 2 issue(s) rolled (#4, #7)." in out

    def test_failed_verdict_names_the_stop_and_the_next_step(self, repo, capsys):
        _main(repo, [1, 4], {1: [1, 1, 1], 4: [0]})
        out = capsys.readouterr().out
        assert "ROLL FAILED at #1" in out
        assert "Not rolled: #4." in out
        assert "Inspect" in out

    def test_gh_unreachable_still_renders_a_verdict(self, repo, capsys):
        _main(repo, [1], {1: [CONFLICT_EXIT_CODE]}, gh_error="boom")
        out = capsys.readouterr().out
        assert "ROLL BLOCKED" in out
        assert "gh was unreachable" in out


class TestPrereqFile:
    def test_a_blocked_run_writes_the_prereq_file(self, repo):
        _main(repo, [1], {1: [CONFLICT_EXIT_CODE]}, questions=QUESTIONS)
        data = json.loads(sr.prereqs_path(repo).read_text(encoding="utf-8"))
        assert [b["number"] for b in data["blocking"]] == [228, 229]

    def test_a_clean_run_writes_no_prereq_file(self, repo):
        _main(repo, [4], {4: [0]})
        assert not sr.prereqs_path(repo).exists()


def _gh_state(state):
    def _run(cmd, cwd=None, env=None):
        if cmd[:3] == ["gh", "issue", "view"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=state, stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return _run


class TestPrereqGate:
    def _seed(self, repo, blocking=None):
        sr.write_prereqs(
            repo,
            QUESTIONS if blocking is None else blocking,
            "blocked issue(s) #1",
        )

    def test_no_file_means_no_gate(self, repo):
        assert sr.check_prereqs(repo, override=False) is None

    def test_open_questions_refuse_and_name_the_override(self, repo, capsys):
        self._seed(repo)
        with patch.object(sr, "_run", _gh_state("OPEN")):
            assert sr.check_prereqs(repo, override=False) == 91
        out = capsys.readouterr().out
        assert "#228" in out and "#229" in out
        assert "Do not re-roll without resolution" in out
        assert "--override-prereqs" in out

    def test_resolved_questions_clear_the_gate_and_the_file(self, repo, capsys):
        self._seed(repo)
        with patch.object(sr, "_run", _gh_state("CLOSED")):
            assert sr.check_prereqs(repo, override=False) is None
        assert not sr.prereqs_path(repo).exists()
        assert "resolved" in capsys.readouterr().out

    def test_offline_refuses_conservatively(self, repo, capsys):
        """Unlike the live must-resolve gate, this file is certain local
        knowledge of a block; unverifiable closure must not proceed."""
        self._seed(repo)

        def _down(cmd, cwd=None, env=None):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="no net")

        with patch.object(sr, "_run", _down):
            assert sr.check_prereqs(repo, override=False) == 91
        assert "cannot verify" in capsys.readouterr().out

    def test_override_proceeds_once_and_keeps_the_file(self, repo, capsys):
        self._seed(repo)
        assert sr.check_prereqs(repo, override=True) is None
        assert sr.prereqs_path(repo).exists(), "override is not forgetting"
        assert "OVERRIDE" in capsys.readouterr().out

    def test_an_unreadable_file_refuses_rather_than_guessing(self, repo, capsys):
        path = sr.prereqs_path(repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json", encoding="utf-8")
        assert sr.check_prereqs(repo, override=False) == 91
        assert "could not be read" in capsys.readouterr().out

    def test_the_gate_runs_before_anything_is_spent(self, repo, capsys):
        self._seed(repo)
        rolled = []
        with patch.object(sr, "check_assemblyzero_tree", lambda p: []), \
                patch.object(sr, "check_box_health", _healthy_box), \
                patch.object(sr, "roll_issue",
                             lambda *a: rolled.append(a) or 0), \
                patch.object(sr, "_run", _gh_state("OPEN")):
            code = sr.main(["--repo", str(repo), "--issue", "7"])
        assert code == 91
        assert rolled == []

    def test_the_override_rides_the_detached_relaunch(self, tmp_path):
        import argparse

        args = argparse.Namespace(
            issue=[7], log_dir=None, assemblyzero_root=None,
            detach=True, detached_stdout=None, override_prereqs=True,
        )
        argv = sr.detached_argv(args, [], tmp_path / "r", tmp_path / "a",
                                tmp_path / "l")
        assert "--override-prereqs" in argv
