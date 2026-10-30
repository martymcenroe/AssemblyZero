"""The JSON runners parse the report on stdout, whatever stderr says (#3065).

`_run_subprocess` appended stderr to stdout and returned one string, and the
Jest/Vitest and Playwright runners took everything from the first `{` to the
end of it to `json.loads`. `npx` writes to stderr as a matter of routine --
`npm WARN` lines, deprecation notices -- so a report delivered correctly on
stdout was followed by a warning, the parse failed, and the runner fell back
to an invented result. A `{` in a log line ahead of the report broke it the
same way.

The streams now come back apart. pytest's runner, which reads human output,
joins them as it did; the JSON runners parse stdout alone, decoding only the
complete object, matched brace to brace, that carries the report's key, so
nothing after the report or before it can break the parse. (The issue
proposed `raw_decode` at each `{`; that needs a handler that steps past every
failed attempt, which is the fall-through shape ADR 0236 retires.)

`base_runner.run_command` is stood in for and `shutil.which` answers for
`npx`: nothing real is run.
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.runner_registry import get_runner
from assemblyzero.workflows.testing.runners import (
    base_runner,
    jest_runner,
    playwright_runner,
)

NPX_WARNING = "npm WARN deprecated inflight@1.0.6: This module is not supported\n"

JEST_REPORT = json.dumps({
    "numPassedTests": 3, "numFailedTests": 1, "numPendingTests": 0, "numTotalTests": 4,
})

PLAYWRIGHT_REPORT = json.dumps({
    "suites": [{"specs": [{"tests": [
        {"results": [{"status": "passed"}]},
        {"results": [{"status": "passed"}]},
        {"results": [{"status": "failed"}]},
    ]}]}],
})


def _completed(stdout: str, stderr: str, code: int = 1) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr=stderr)


def _runner(framework: TestFramework, root):
    which = jest_runner.shutil if framework in (TestFramework.JEST, TestFramework.VITEST) \
        else playwright_runner.shutil
    with patch.object(which, "which", return_value="/usr/bin/npx"):
        return get_runner(framework, str(root))


def test_run_subprocess_returns_the_streams_apart(tmp_path):
    runner = _runner(TestFramework.JEST, tmp_path)
    with patch.object(base_runner, "run_command",
                      return_value=_completed(JEST_REPORT, NPX_WARNING)):
        returned = runner._run_subprocess(["npx", "jest", "--json"])

    assert returned == (JEST_REPORT, NPX_WARNING, 1)


@pytest.mark.parametrize("framework", [TestFramework.JEST, TestFramework.VITEST])
def test_a_jest_or_vitest_report_survives_an_npx_warning_on_stderr(framework, tmp_path):
    runner = _runner(framework, tmp_path)
    with patch.object(base_runner, "run_command",
                      return_value=_completed(JEST_REPORT, NPX_WARNING)):
        result = runner.run_tests(test_paths=["tests/a.test.ts"])

    assert (result["passed"], result["failed"], result["total"]) == (3, 1, 4)
    assert NPX_WARNING.strip() in result["raw_output"], "the reader still sees stderr"


def test_a_playwright_report_survives_an_npx_warning_on_stderr(tmp_path):
    runner = _runner(TestFramework.PLAYWRIGHT, tmp_path)
    with patch.object(base_runner, "run_command",
                      return_value=_completed(PLAYWRIGHT_REPORT, NPX_WARNING)):
        result = runner.run_tests(test_paths=["tests/a.spec.ts"])

    assert (result["passed"], result["failed"]) == (2, 1)
    assert NPX_WARNING.strip() in result["raw_output"]


def test_a_brace_in_a_log_line_before_the_report_is_skipped(tmp_path):
    runner = _runner(TestFramework.JEST, tmp_path)
    stdout = "Using config {rootDir: web}\n" + JEST_REPORT + "\nDone in 2.1s\n"
    with patch.object(base_runner, "run_command", return_value=_completed(stdout, "")):
        result = runner.run_tests(test_paths=["tests/a.test.ts"])

    assert (result["passed"], result["failed"]) == (3, 1)


def test_a_json_log_line_that_is_not_the_report_is_skipped(tmp_path):
    """The first object that parses is not necessarily the report."""
    runner = _runner(TestFramework.PLAYWRIGHT, tmp_path)
    stdout = '{"level": "info", "msg": "starting"}\n' + PLAYWRIGHT_REPORT
    with patch.object(base_runner, "run_command", return_value=_completed(stdout, "")):
        result = runner.run_tests(test_paths=["tests/a.spec.ts"])

    assert (result["passed"], result["failed"]) == (2, 1)


def test_a_report_that_carries_the_key_and_does_not_parse_raises():
    """That is the report, broken: it is never passed over for a later one."""
    with pytest.raises(ValueError, match='"numPassedTests"'):
        base_runner.first_json_object('{"numPassedTests": 3,,}', "numPassedTests")


def test_a_brace_inside_a_json_string_does_not_end_the_object():
    text = '{"numPassedTests": 1, "path": "src/{a}.ts"} trailing'
    assert base_runner.first_json_object(text, "numPassedTests") == {
        "numPassedTests": 1, "path": "src/{a}.ts",
    }


def test_pytest_still_reads_both_streams(tmp_path):
    runner = get_runner(TestFramework.PYTEST, str(tmp_path))
    with patch.object(base_runner, "run_command",
                      return_value=_completed("3 passed in 0.1s\n", "a warning\n", 0)):
        result = runner.run_tests(test_paths=["tests/test_a.py"])

    assert result["passed"] == 3
    assert "a warning" in result["raw_output"]
