"""The redraw budget is retired (#2206, superseding #2068).

#2068 added an in-task redraw loop on the premise that generation quality
varies wildly between draws, so a bad draw was worth re-rolling without a
human in the loop. The campaign disproved the premise: on 2026-08-10/11 every
failure was systematic — a parse misroute, stale binding docs, an unwritable
photo comparison, an under-specified palette — and each redraw re-paid for
passed stages to reproduce a known result. The operator retired it.

What replaces it: one roll per issue, then a halt with the reason, and a
relaunch that resumes from the failed stage (#2193) once the cause is fixed.
"""

import argparse
import sys
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402


def _main(repo, codes, attempts=1):
    """Run main() with roll_issue scripted to return `codes` in order."""
    calls = []

    def _roll(repo_root, issue, log_dir, az_root, extra):
        calls.append(issue)
        return codes[len(calls) - 1]

    with patch.object(sr, "check_assemblyzero_tree", lambda p: []), \
            patch.object(sr, "roll_issue", _roll), \
            patch.object(sr, "restore_repo", lambda *a: []), \
            patch.object(sr.time, "sleep", lambda s: None):
        code = sr.main(
            ["--repo", str(repo), "--issue", "2", "--issue", "5",
             "--attempts", str(attempts)]
        )
    return code, calls


class TestTheBudgetIsRetired:
    def test_a_failed_draw_is_not_redrawn(self, tmp_path):
        """The inversion of the #2068 test this file used to carry."""
        repo = tmp_path / "r"
        (repo / ".git").mkdir(parents=True)
        code, calls = _main(repo, [1, 0, 0])

        assert code == 1
        assert calls == [2], "one roll of #2, then the batch halts"

    def test_success_rolls_every_issue_once(self, tmp_path):
        repo = tmp_path / "r"
        (repo / ".git").mkdir(parents=True)
        code, calls = _main(repo, [0, 0])
        assert code == 0
        assert calls == [2, 5]

    def test_a_failure_stops_the_arc(self, tmp_path):
        repo = tmp_path / "r"
        (repo / ".git").mkdir(parents=True)
        code, calls = _main(repo, [1, 1])
        assert code == 1
        assert calls == [2], "later issues must not roll after a failure"

    def test_a_base_problem_still_stops_at_one(self, tmp_path):
        """91 is a gate/base fault, not a draw — it was never redrawn."""
        repo = tmp_path / "r"
        (repo / ".git").mkdir(parents=True)
        code, calls = _main(repo, [91])
        assert code == 91
        assert calls == [2]

    def test_default_is_a_single_attempt(self, tmp_path):
        repo = tmp_path / "r"
        (repo / ".git").mkdir(parents=True)

        calls = []
        with patch.object(sr, "check_assemblyzero_tree", lambda p: []), \
                patch.object(sr, "roll_issue",
                             lambda *a: calls.append(1) or 1), \
                patch.object(sr, "restore_repo", lambda *a: []), \
                patch.object(sr.time, "sleep", lambda s: None):
            code = sr.main(["--repo", str(repo), "--issue", "2"])
        assert code == 1
        assert calls == [1]

    def test_a_budget_above_one_refuses(self, tmp_path):
        """Asking for the retired behaviour is refused, not silently clamped:
        an operator who typed --attempts 3 believes three draws will happen,
        and a clamp would leave that belief intact."""
        repo = tmp_path / "r"
        (repo / ".git").mkdir(parents=True)
        code, calls = _main(repo, [0, 0], attempts=3)
        assert code == 91
        assert calls == [], "a refused launch spends nothing"


class TestTheFlagRidesTheRelaunch:
    def test_detached_argv_carries_attempts(self, tmp_path):
        """The detached child re-parses argv, so the flag must still ride —
        at the only value that now passes preflight."""
        args = argparse.Namespace(
            issue=[2, 5], log_dir=None, assemblyzero_root=None,
            detach=True, detached_stdout=None, attempts=1,
        )
        argv = sr.detached_argv(args, [], tmp_path / "r", tmp_path / "a",
                                tmp_path / "l")
        assert "--attempts" in argv
        assert argv[argv.index("--attempts") + 1] == "1"
