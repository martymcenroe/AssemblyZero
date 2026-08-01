"""A failed draw redraws inside the detached task (#2068).

Generation quality varies wildly between draws -- the same issue produced
39/41-passing and 4/75-passing initial iterations on consecutive rolls. A bad
draw is self-healing (ensure_base clears its debris), so the retry belongs
inside the detached task, not with a human relaunching every twenty minutes.
"""

import argparse
import sys
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402


def _main(repo, attempts, codes):
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


class TestRedraw:
    def test_a_failed_draw_is_redrawn(self, tmp_path):
        repo = tmp_path / "r"
        (repo / ".git").mkdir(parents=True)
        code, calls = _main(repo, 3, [1, 1, 0, 0])

        assert code == 0
        assert calls == [2, 2, 2, 5], "three draws of #2, then #5 once"

    def test_success_does_not_burn_the_budget(self, tmp_path):
        repo = tmp_path / "r"
        (repo / ".git").mkdir(parents=True)
        code, calls = _main(repo, 5, [0, 0])
        assert code == 0
        assert calls == [2, 5]

    def test_exhausted_attempts_stop_the_arc(self, tmp_path):
        repo = tmp_path / "r"
        (repo / ".git").mkdir(parents=True)
        code, calls = _main(repo, 2, [1, 1])
        assert code == 1
        assert calls == [2, 2], "later issues must not roll after exhaustion"

    def test_a_base_problem_is_never_redrawn(self, tmp_path):
        """91 is a gate/base fault, not a draw; retrying it re-spends against
        the same wall."""
        repo = tmp_path / "r"
        (repo / ".git").mkdir(parents=True)
        code, calls = _main(repo, 5, [91])
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


class TestTheBudgetRidesTheRelaunch:
    def test_detached_argv_carries_attempts(self, tmp_path):
        args = argparse.Namespace(
            issue=[2, 5], log_dir=None, assemblyzero_root=None,
            detach=True, detached_stdout=None, attempts=6,
        )
        argv = sr.detached_argv(args, [], tmp_path / "r", tmp_path / "a",
                                tmp_path / "l")
        assert "--attempts" in argv
        assert argv[argv.index("--attempts") + 1] == "6"
