"""#4504: the runner reads Vitest's report from the file it named.

Vitest 5's JSON reporter writes `.vitest/json/output.json` in the project and
prints one line, so a runner reading stdout found nothing and the first real run
to reach the red phase crashed, on a correct result of twelve failing tests. The
stand-in here does what Vitest 5 does: it honours `--outputFile` and prints one
line.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.runners.base_runner import RunnerError
from assemblyzero.workflows.testing.runners.jest_runner import JestRunner

REPORT = json.dumps({
    "success": False, "numPassedTests": 3, "numFailedTests": 12,
    "numPendingTests": 1, "numTotalTests": 16,
})


def _report_path(command: list[str]) -> Path | None:
    for argument in command:
        if argument.startswith("--outputFile="):
            return Path(argument.split("=", 1)[1])
    return None


@pytest.fixture
def runner(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    def make(framework=TestFramework.VITEST):
        return JestRunner({"framework": framework}, project_root=str(tmp_path))

    return make


def _vitest_5(monkeypatch, instance, seen: list):
    def run(command, *args, **kwargs):
        seen.append(command)
        path = _report_path(command)
        assert path is not None, "Vitest 5 prints no report on stdout"
        path.write_text(REPORT, encoding="utf-8")
        return "JSON report written to the file named\n", "", 1

    monkeypatch.setattr(instance, "_run_subprocess", run)


def test_t1_the_report_is_read_from_the_file(runner, monkeypatch):
    instance = runner()
    _vitest_5(monkeypatch, instance, [])

    result = instance.run_tests()

    assert (result["passed"], result["failed"], result["skipped"]) == (3, 12, 1)


def test_t2_the_file_is_named_ahead_of_the_test_paths(runner, monkeypatch):
    instance = runner()
    seen: list = []
    _vitest_5(monkeypatch, instance, seen)

    instance.run_tests(test_paths=["tests/stocks.test.ts"])

    command = seen[0]
    assert command[:4] == ["npx", "vitest", "run", "--reporter=json"]
    assert command[4].startswith("--outputFile=")
    assert command[-1].endswith("stocks.test.ts")


def test_t3_nothing_is_left_behind(runner, monkeypatch, tmp_path):
    instance = runner()
    seen: list = []
    _vitest_5(monkeypatch, instance, seen)

    instance.run_tests()

    report = _report_path(seen[0])
    assert not report.is_relative_to(tmp_path), "the report stays out of the target's tree"
    assert not report.parent.exists()
    assert list(tmp_path.iterdir()) == []


def test_t4_a_run_that_writes_no_report_still_raises_with_what_it_said(runner, monkeypatch):
    instance = runner()
    monkeypatch.setattr(
        instance, "_run_subprocess", lambda *a, **k: ("Startup Error: no config", "", 1),
    )

    with pytest.raises(RunnerError, match="Startup Error"):
        instance.run_tests()


def test_an_older_vitest_printing_to_stdout_is_still_read(runner, monkeypatch):
    instance = runner()
    monkeypatch.setattr(instance, "_run_subprocess", lambda *a, **k: (REPORT, "", 1))

    assert instance.run_tests()["failed"] == 12


def test_t5_jest_is_unchanged(runner, monkeypatch):
    instance = runner(TestFramework.JEST)
    seen: list = []

    def run(command, *args, **kwargs):
        seen.append(command)
        return REPORT, "", 1

    monkeypatch.setattr(instance, "_run_subprocess", run)

    instance.run_tests()

    assert seen == [["npx", "jest", "--json"]]
