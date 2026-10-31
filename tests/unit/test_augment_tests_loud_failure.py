"""N4c stops on every failure of its own, and says why (#3585, ADR 0236).

Ledger 0908 rows for ``assemblyzero/workflows/testing/nodes/augment_tests.py``.
Each test is named for the ledger line it settles (line numbers from commit
79e18ad1).

N4c used to return to N5 with an empty ``error_message`` whatever went wrong:
no test file, no uncovered line named, an unreadable file, a seat it could not
resolve, a failed or empty model call, no code, attempts spent, a vetting run
that ran nothing, a rejected repair, and no added test passing. N5 then
measured the same shortfall and sent it back, and the operator heard nothing.
Every one of those now halts through ``route_after_augment``, which sends a
recorded reason to HALT, and HALT alerts. The suite on disk is always one that
passes: what was there, plus only the additions that ran and passed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.nodes import augment_tests as mod

RUN_PYTEST = "assemblyzero.workflows.testing.nodes.verify_phases.run_pytest"

GREEN_OUTPUT = """\
Name                                   Stmts   Miss  Cover   Missing
--------------------------------------------------------------------
src/boostgauge/collector.py               82      6    93%   56-58, 63
--------------------------------------------------------------------
TOTAL                                     82      6    93%
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

ONE_FAILS = (
    "FAILED tests/test_x.py::test_covers_the_platform_branch - assert 0.0 == 30.0\n"
    "1 passed, 1 failed\n"
)

REPAIRED = (
    "```python\n"
    "def test_covers_the_platform_branch():\n"
    "    assert DataCollector is not None\n"
    "```\n"
)


def _pytest_says(output: str, passed: int, failed: int = 0, errors: int = 0, rc: int = 1):
    return {
        "returncode": rc, "stdout": output, "stderr": "",
        "parsed": {"passed": passed, "failed": failed, "errors": errors},
    }


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    pkg = tmp_path / "src" / "boostgauge"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "collector.py").write_text(
        "class DataCollector:\n    pass\n" + "x = 1\n" * 70, encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text(
        "def test_existing():\n    assert True\n", encoding="utf-8",
    )
    (tmp_path / "audit").mkdir()
    return tmp_path


def _state(worktree: Path, **overrides) -> dict:
    state = {
        "issue_number": 77,
        "repo_root": str(worktree),
        "audit_dir": str(worktree / "audit"),
        "test_files": [str(worktree / "tests" / "test_x.py")],
        "green_phase_output": GREEN_OUTPUT,
        "uncovered_changed_lines": {"src/boostgauge/collector.py": [56, 57, 58, 63]},
        "coverage_achieved": 93.0,
        "coverage_target": 95,
        "coverage_module": "",
    }
    state.update(overrides)
    return state


def _suite(worktree: Path) -> str:
    return (worktree / "tests" / "test_x.py").read_text(encoding="utf-8")


BEFORE = "def test_existing():\n    assert True\n"


def _halted(result: dict, capsys, *needles: str) -> str:
    """The node halted: a reason in error_message, said at ERROR on stderr."""
    message = result["error_message"]
    assert message, "the node returned no reason, so the run would not halt"
    assert result["next_node"] == "end"
    err = capsys.readouterr().err
    assert "ERROR" in err and message in err
    for needle in needles:
        assert needle in message, (needle, message)
    return message


# ------------------------------------------------------ lines 101, 106


def test_101_a_malformed_range_raises():
    with pytest.raises(mod.CoverageRangeUnreadable, match="'5-x'"):
        mod._line_numbers(["1-3", "5-x"])


def test_106_a_malformed_line_number_raises():
    with pytest.raises(mod.CoverageRangeUnreadable, match="'y'"):
        mod._line_numbers(["4", "y"])


def test_101_the_lines_n5_names_never_pass_through_a_report_parse(worktree):
    """#4436: a Missing column N4c could misread is gone from the node's path;
    it reads the numbers N5 judged. `_line_numbers` still guards the vetting
    run's report, which is the one report text this node reads."""
    state = _state(worktree, green_phase_output="not a coverage table at all")
    with patch.object(mod, "call_claude_for_file", return_value=("", "stop here")) as call:
        mod.augment_tests_for_coverage(state)
    assert ">> 56:" in call.call_args.args[0]


# ------------------------------------------------------ lines 134, 142, 209


def test_134_an_unreadable_source_raises(tmp_path):
    with pytest.raises(OSError):
        mod._read_context(tmp_path / "absent.py", ["1"])


def test_134_the_node_halts_when_the_source_cannot_be_read(worktree, capsys):
    (worktree / "src" / "boostgauge" / "collector.py").unlink()
    with patch.object(mod, "call_claude_for_file") as call:
        result = mod.augment_tests_for_coverage(_state(worktree))
    _halted(result, capsys, "collector.py")
    call.assert_not_called()


def test_142_a_source_that_does_not_parse_falls_back_to_bare_lines(tmp_path):
    """Pinned: compliant, documented fallback."""
    path = tmp_path / "broken.py"
    path.write_text("def broken(:\n    pass\n", encoding="utf-8")
    assert mod._read_context(path, ["2"]) == "2:     pass"


def test_209_read_lines_raises_on_an_unreadable_source(tmp_path):
    with pytest.raises(OSError):
        mod._read_lines(tmp_path / "absent.py", ["1"])


# ------------------------------------------------------ lines 218, 223


def test_218_read_lines_raises_on_a_malformed_range(tmp_path):
    path = tmp_path / "a.py"
    path.write_text("x = 1\n" * 5, encoding="utf-8")
    with pytest.raises(mod.CoverageRangeUnreadable):
        mod._read_lines(path, ["1-x"])


def test_223_read_lines_raises_on_a_malformed_line(tmp_path):
    path = tmp_path / "a.py"
    path.write_text("x = 1\n" * 5, encoding="utf-8")
    with pytest.raises(mod.CoverageRangeUnreadable):
        mod._read_lines(path, ["q"])


# ------------------------------------------------------ lines 317, 318


def test_317_an_addition_that_does_not_parse_is_an_invariant_breach(worktree):
    with pytest.raises(mod.AugmentInvariantBroken, match="does not parse"):
        mod._keep_passing_additions(
            worktree / "tests" / "test_x.py", BEFORE, "def broken(:\n", worktree,
        )


def test_318_the_fail_open_tags_are_gone():
    assert "fail-open:" not in Path(mod.__file__).read_text(encoding="utf-8")


# ---------------------------------------------------------------- line 347


def test_347_a_vetting_run_that_ran_nothing_halts(worktree, capsys):
    broken = "E   ImportError: cannot import name 'gone' from 'boostgauge.collector'\n"
    with patch.object(mod, "call_claude_for_file", return_value=(NEW_TESTS, "")), \
         patch(RUN_PYTEST, return_value=_pytest_says(broken, 0, rc=2)):
        result = mod.augment_tests_for_coverage(_state(worktree))
    _halted(result, capsys, "ImportError: cannot import name 'gone'", "exit 2")
    assert _suite(worktree) == BEFORE


# ------------------------------------------------------ lines 389, 390


def test_389_without_named_tests_raises_on_unparseable_source():
    with pytest.raises(SyntaxError):
        mod._without_named_tests("def broken(:\n", {"test_x"})


def test_389_the_quiet_answers_stay_quiet():
    """Pinned: nothing to remove returns the source unchanged."""
    source = "def test_a():\n    pass\n"
    assert mod._without_named_tests(source, set()) == (source, [])
    assert mod._without_named_tests(source, {"test_b"}) == (source, [])


# ---------------------------------------------------------------- line 537


def test_537_no_test_file_halts(worktree, capsys):
    result = mod.augment_tests_for_coverage(_state(worktree, test_files=[]))
    _halted(result, capsys, "no test file")


# ---------------------------------------------------------------- line 554


def test_554_a_shortfall_with_no_uncovered_line_named_halts(worktree, capsys):
    result = mod.augment_tests_for_coverage(_state(worktree, uncovered_changed_lines={}))
    _halted(result, capsys, "names no uncovered line", "93.0%")


# ---------------------------------------------------------------- line 581


def test_581_an_unreadable_test_file_halts(worktree, capsys):
    target = worktree / "tests" / "test_dir.py"
    target.mkdir()
    with patch.object(mod, "call_claude_for_file") as call:
        result = mod.augment_tests_for_coverage(_state(worktree, test_files=[str(target)]))
    _halted(result, capsys, str(target))
    call.assert_not_called()


# ---------------------------------------------------------------- line 593


@pytest.mark.parametrize("audit_dir", ["", "missing"], ids=["unset", "absent"])
def test_593_no_audit_dir_halts(worktree, capsys, audit_dir):
    value = str(worktree / audit_dir) if audit_dir else ""
    with patch.object(mod, "call_claude_for_file") as call:
        result = mod.augment_tests_for_coverage(_state(worktree, audit_dir=value))
    _halted(result, capsys, "audit")
    call.assert_not_called()


# ---------------------------------------------------------------- line 613


def test_613_an_unresolvable_seat_halts(worktree, capsys):
    def no_seat(state, seat):
        raise ValueError("no seat impl.augment_tests in profile 'x'")

    with patch.object(mod, "resolve", no_seat):
        result = mod.augment_tests_for_coverage(_state(worktree))
    _halted(result, capsys, "no seat impl.augment_tests")


# ---------------------------------------------------------------- line 645


@pytest.mark.parametrize(
    "reply, cause", [(("", "timed out after 900s"), "timed out after 900s"),
                     (("", ""), "empty response")],
    ids=["error", "empty"],
)
def test_645_a_failed_generation_call_halts_with_its_cause(worktree, capsys, reply, cause):
    with patch.object(mod, "call_claude_for_file", return_value=reply):
        result = mod.augment_tests_for_coverage(_state(worktree))
    _halted(result, capsys, cause)
    assert _suite(worktree) == BEFORE


# ---------------------------------------------------------------- line 650


def test_650_a_response_with_no_code_is_revised_then_halts(worktree, capsys):
    with patch.object(mod, "call_claude_for_file",
                      return_value=("I would test it like this, in prose.", "")) as call:
        result = mod.augment_tests_for_coverage(_state(worktree))
    _halted(result, capsys, "Coverage test additions spent", "no ```python code block")
    assert call.call_count == mod.MAX_GENERATION_ATTEMPTS
    assert _suite(worktree) == BEFORE


# ---------------------------------------------------------------- line 671


def test_671_spent_generation_attempts_halt(worktree, capsys):
    bad = NEW_TESTS.replace("DataCollector", "DataCollecter")
    with patch.object(mod, "call_claude_for_file", return_value=(bad, "")):
        result = mod.augment_tests_for_coverage(_state(worktree))
    _halted(result, capsys, "Coverage test additions spent", "DataCollecter")
    assert _suite(worktree) == BEFORE


# ---------------------------------------------------------------- line 701


def test_701_dropped_tests_are_said_at_error(worktree, capsys):
    runs = iter([_pytest_says(ONE_FAILS, 1, 1), _pytest_says("2 passed", 2, rc=0)])
    with patch.object(mod, "call_claude_for_file",
                      side_effect=[(NEW_TESTS, ""), (REPAIRED, "")]), \
         patch(RUN_PYTEST, side_effect=lambda *a, **k: next(runs)):
        result = mod.augment_tests_for_coverage(_state(worktree))
    assert result["error_message"] == ""
    err = capsys.readouterr().err
    assert "ERROR [N4c] dropped test_covers_the_platform_branch: assert 0.0 == 30.0" in err


def test_701_drops_left_after_the_repair_are_counted_as_failures(worktree, capsys):
    still = ONE_FAILS.replace("assert 0.0 == 30.0", "assert False")
    runs = iter([_pytest_says(ONE_FAILS, 1, 1), _pytest_says(still, 1, 1)])
    with patch.object(mod, "call_claude_for_file",
                      side_effect=[(NEW_TESTS, ""), (REPAIRED, "")]), \
         patch(RUN_PYTEST, side_effect=lambda *a, **k: next(runs)):
        result = mod.augment_tests_for_coverage(_state(worktree))
    assert result["next_node"] == "N5_verify_green"
    assert "def test_covers_the_error_path" in _suite(worktree)
    assert "1 added test(s) failed and were dropped" in capsys.readouterr().err


# ------------------------------------------------------ lines 721, 734, 755


def _repair_halts(worktree, capsys, repair_reply, *needles):
    with patch.object(mod, "call_claude_for_file",
                      side_effect=[(NEW_TESTS, ""), repair_reply]), \
         patch(RUN_PYTEST, return_value=_pytest_says(ONE_FAILS, 1, 1)):
        result = mod.augment_tests_for_coverage(_state(worktree))
    _halted(result, capsys, *needles)
    suite = _suite(worktree)
    assert "def test_covers_the_error_path" in suite, "the passing addition is kept"
    assert "def test_covers_the_platform_branch" not in suite, "the failing one is not"
    return result


def test_721_a_repair_call_that_fails_halts(worktree, capsys):
    _repair_halts(worktree, capsys, ("", "HTTP 529 overloaded"), "HTTP 529 overloaded")


def test_721_a_repair_with_no_code_halts(worktree, capsys):
    _repair_halts(worktree, capsys, ("no code here", ""),
                  "Coverage test additions spent", "no ```python code block")


def test_734_a_repair_that_does_not_parse_halts(worktree, capsys):
    _repair_halts(worktree, capsys, ("```python\ndef broken(:\n```\n", ""),
                  "Coverage test additions spent", "does not parse")


def test_755_a_repair_that_fails_import_validation_halts(worktree, capsys):
    bad = REPAIRED.replace(
        "def test_covers", "from boostgauge.collector import Gone\n\n\ndef test_covers"
    )
    _repair_halts(worktree, capsys, (bad, ""), "Coverage test additions spent", "Gone")


# ---------------------------------------------------------------- line 761


def test_761_no_added_test_passing_halts_and_restores(worktree, capsys):
    all_fail = ONE_FAILS + (
        "FAILED tests/test_x.py::test_covers_the_error_path - assert False\n"
    )
    with patch.object(mod, "call_claude_for_file", return_value=(NEW_TESTS, "")), \
         patch(RUN_PYTEST, return_value=_pytest_says(all_fail, 0, 2)):
        result = mod.augment_tests_for_coverage(_state(worktree))
    _halted(result, capsys, "Coverage test additions spent", "none of the")
    assert _suite(worktree) == BEFORE


# ------------------------------------------------------ the success path


def test_a_clean_addition_still_returns_to_verification(worktree):
    with patch.object(mod, "call_claude_for_file", return_value=(NEW_TESTS, "")), \
         patch(RUN_PYTEST, return_value=_pytest_says("3 passed", 3, rc=0)):
        result = mod.augment_tests_for_coverage(_state(worktree))
    assert result["error_message"] == ""
    assert result["next_node"] == "N5_verify_green"
    assert result["coverage_augment_attempts"] == 1
    assert "def test_covers_the_error_path" in _suite(worktree)
