"""N4c keeps the suite it was given, records what it did, and is bounded (#2899, #2900).

boostgauge #4, `run-issue4-021938` (2026-09-06 02:19), the first run to
measure the whole suite on a resume (#2897) and to have N4c's output accepted
(#2895):

    [N5] Results: 38 passed, 0 failed | Coverage: 91.0%
    [LLM] provider=claude model=opus output=187699 cost=$4.7112 duration=3335.1s
    [N4c] added 9 test(s) targeting 9 uncovered range(s)
    [N5] Results: 20 passed, 2 failed | Coverage: 92.0%
    [N5] iteration regressed (20 passing at 92.0% vs best 38 at 91.0%) -- restored 6 file(s)

Twenty-two is the scaffold's thirteen plus the nine appended to it: N4c
returned `test_files` as `[test_path]`, the plan's three test files (25
tests) fell out of the measurement, the regression guard restored the
pre-N4c scaffold, and fifty-five minutes of generation were gone. Nothing of
that generation was saved -- N4c wrote no prompt and no response to the
audit dir -- and nothing bounded it: 3,335 s and 187,699 output tokens for
nine tests, against 194 s for twelve on the first live run.

Three things are held here: the returned list is the given list, the audit
dir carries the prompt and every response, and the call carries a ceiling.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.nodes import augment_tests
from assemblyzero.workflows.testing.nodes.augment_tests import (
    AUGMENT_TIMEOUT_SECONDS,
    augment_tests_for_coverage,
)
from assemblyzero.workflows.testing.nodes.implementation import claude_client

GREEN_OUTPUT = """\
---------- coverage: platform win32, python 3.14.7-final-0 ----------
Name                                   Stmts   Miss  Cover   Missing
--------------------------------------------------------------------
src\\boostgauge\\collector.py               82      6    93%   56-58, 63
src\\boostgauge\\collectors\\windows.py     119     11    91%   86, 153-158
--------------------------------------------------------------------
TOTAL                                    201     17    91%
==================== 38 passed in 1.04s ====================
"""

NEW_TESTS = (
    "```python\n"
    "from boostgauge.collector import DataCollector\n"
    "\n\n"
    "def test_covers_the_error_path():\n"
    "    assert DataCollector\n"
    "\n\n"
    "def test_covers_the_platform_branch():\n"
    "    assert DataCollector\n"
    "```\n"
)


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    pkg = tmp_path / "src" / "boostgauge"
    (pkg / "collectors").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "collector.py").write_text(
        "class DataCollector:\n    pass\n" + "\n" * 70, encoding="utf-8",
    )
    (pkg / "collectors" / "windows.py").write_text("x = 1\n" * 160, encoding="utf-8")
    for rel in (
        "tests/test_issue_4.py", "tests/unit/test_collector.py",
        "tests/integration/test_windows_sweep_crosscheck.py",
        "tests/benchmark/test_sweep_cost.py",
    ):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def test_existing():\n    assert True\n", encoding="utf-8")
    (tmp_path / "audit").mkdir()
    return tmp_path


def _state(worktree: Path, **overrides) -> dict:
    files = [
        str(worktree / "tests" / "test_issue_4.py"),
        str(worktree / "tests" / "unit" / "test_collector.py"),
        str(worktree / "tests" / "integration" / "test_windows_sweep_crosscheck.py"),
        str(worktree / "tests" / "benchmark" / "test_sweep_cost.py"),
    ]
    state = {
        "repo_root": str(worktree),
        "audit_dir": str(worktree / "audit"),
        "test_files": files,
        "green_phase_output": GREEN_OUTPUT,
        "coverage_achieved": 91.0,
        "coverage_target": 95,
        "coverage_module": "",
    }
    state.update(overrides)
    return state


class TestTheSuiteIsKept:
    def test_run_34s_four_files_come_back_with_the_scaffold_extended(self, worktree):
        with patch.object(augment_tests, "call_claude_for_file", return_value=(NEW_TESTS, "")):
            result = augment_tests_for_coverage(_state(worktree))

        assert result["next_node"] == "N5_verify_green"
        assert [Path(p).name for p in result["test_files"]] == [
            "test_issue_4.py", "test_collector.py",
            "test_windows_sweep_crosscheck.py", "test_sweep_cost.py",
        ]
        scaffold = (worktree / "tests" / "test_issue_4.py").read_text(encoding="utf-8")
        assert "def test_existing" in scaffold
        assert "def test_covers_the_error_path" in scaffold

    def test_only_the_first_file_is_extended(self, worktree):
        with patch.object(augment_tests, "call_claude_for_file", return_value=(NEW_TESTS, "")):
            augment_tests_for_coverage(_state(worktree))

        for rel in ("tests/unit/test_collector.py", "tests/benchmark/test_sweep_cost.py"):
            assert "test_covers" not in (worktree / rel).read_text(encoding="utf-8")


class TestTheRecord:
    def test_the_prompt_and_the_response_are_in_the_audit_dir(self, worktree):
        with patch.object(augment_tests, "call_claude_for_file", return_value=(NEW_TESTS, "")):
            augment_tests_for_coverage(_state(worktree))

        names = sorted(p.name for p in (worktree / "audit").iterdir())
        assert any(n.endswith("augment-prompt.md") for n in names), names
        assert any(n.endswith("augment-response.md") for n in names), names
        prompt = next(p for p in (worktree / "audit").iterdir() if p.name.endswith("augment-prompt.md"))
        assert "Uncovered lines, by file" in prompt.read_text(encoding="utf-8")

    def test_a_rejected_attempt_leaves_both_responses(self, worktree):
        bad = NEW_TESTS.replace("DataCollector", "DataCollecter")
        with patch.object(
            augment_tests, "call_claude_for_file", side_effect=[(bad, ""), (NEW_TESTS, "")],
        ):
            augment_tests_for_coverage(_state(worktree))

        names = sorted(p.name for p in (worktree / "audit").iterdir())
        assert any(n.endswith("augment-response.md") for n in names), names
        assert any(n.endswith("augment-response-retry2.md") for n in names), names

    def test_no_audit_dir_means_no_files_and_no_failure(self, worktree):
        with patch.object(augment_tests, "call_claude_for_file", return_value=(NEW_TESTS, "")):
            result = augment_tests_for_coverage(_state(worktree, audit_dir=""))

        assert result["next_node"] == "N5_verify_green"


class TestTheCeiling:
    def test_the_call_carries_the_ceiling_and_says_so(self, worktree, capsys):
        with patch.object(
            augment_tests, "call_claude_for_file", return_value=(NEW_TESTS, ""),
        ) as call:
            augment_tests_for_coverage(_state(worktree))

        assert call.call_args.kwargs["timeout_seconds"] == AUGMENT_TIMEOUT_SECONDS
        assert AUGMENT_TIMEOUT_SECONDS == 900
        assert "[N4c] generation ceiling 900 s per attempt, model " in capsys.readouterr().out

    def test_the_model_is_routed_as_n4_routes_it_not_bare_opus(self, worktree):
        """The cause of the 3,335-second call: bare `opus` runs with extended
        thinking and no ceiling on it. N4 routes through select_model_for_file
        and returns in twenty seconds; N4c now does the same."""
        from assemblyzero.workflows.testing.nodes.implementation.routing import (
            select_model_for_file,
        )
        with patch.object(
            augment_tests, "call_claude_for_file", return_value=(NEW_TESTS, ""),
        ) as call:
            augment_tests_for_coverage(_state(worktree))

        routed = select_model_for_file(str(worktree / "tests" / "test_issue_4.py"))
        assert call.call_args.kwargs["model"] == routed
        assert call.call_args.kwargs["model"] != "opus"

    def test_call_claude_for_file_honours_an_explicit_ceiling(self):
        seen: dict = {}

        class _Result:
            success = True
            response = "ok"

        class _Provider:
            def invoke(self, **kwargs):
                seen.update(kwargs)
                return _Result()

        with patch.object(claude_client, "get_provider", return_value=_Provider()):
            claude_client.call_claude_for_file("p", file_path="t.py", timeout_seconds=900)
            assert seen["timeout_seconds"] == 900.0
            claude_client.call_claude_for_file("p", file_path="t.py")
            assert seen["timeout_seconds"] == claude_client.compute_dynamic_timeout("p")

    def test_a_timed_out_generation_leaves_the_suite_unchanged(self, worktree, capsys):
        before = (worktree / "tests" / "test_issue_4.py").read_text(encoding="utf-8")
        with patch.object(
            augment_tests, "call_claude_for_file",
            return_value=("", "timed out after 900s"),
        ):
            result = augment_tests_for_coverage(_state(worktree))

        assert result["next_node"] == "N5_verify_green"
        assert (worktree / "tests" / "test_issue_4.py").read_text(encoding="utf-8") == before
        assert "no new tests generated: timed out after 900s" in capsys.readouterr().out
