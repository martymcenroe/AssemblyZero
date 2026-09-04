"""The guard that stops a unit test spending money, and its own self-check (#2703).

On 2026-09-02 a unit test called Claude twice, for 96 seconds, at real cost,
because its author stubbed the edit-script path and not the full-rewrite
fallback. Nothing in the suite intercepted a model transport of any kind, so
the only signal was that the test felt slow.

The last class here is the important one: it asserts the guard is actually
INSTALLED for this file, by trying to spawn a model CLI and requiring the
refusal. Without it every other test in this file could pass against a guard
that was never wired in -- the vacuous-pass shape #2677's scanner self-check
exists to prevent.
"""
from __future__ import annotations

import subprocess

import pytest

from tests.model_call_guard import (
    MODEL_CLI_NAMES,
    LiveModelCallInUnitTest,
    model_cli_name,
    refuse,
)


class TestWhichCommandsAreModelCalls:
    @pytest.mark.parametrize(
        "cmd,expected",
        [
            (["claude", "-p", "hello"], "claude"),
            (["agy", "--model", "gemini-3.1-pro-high"], "agy"),
            (["gemini", "-p", "x"], "gemini"),
            # The transports invoke a resolved path, not a bare name. Both
            # separators, on both platforms: the fleet runs Windows and CI runs
            # Linux, where the native path rules do not treat a backslash as a
            # separator at all. CI caught this on its first push.
            ([r"C:\Users\x\AppData\Roaming\npm\claude.cmd", "-p"], "claude"),
            (["/usr/local/bin/claude", "-p"], "claude"),
            (["CLAUDE.EXE", "-p"], "claude"),
        ],
    )
    def test_a_model_cli_is_recognised_however_it_is_spelled(self, cmd, expected):
        assert model_cli_name(cmd) == expected

    def test_a_windows_path_is_read_the_same_way_on_every_platform(self):
        """Pinned separately from the table because the failure it prevents is
        platform-shaped: on Linux this string has no path separators, so the
        stem is the whole thing and the guard would let a Windows transport
        through on the runner."""
        assert model_cli_name([r"C:\npm\claude.cmd"]) == "claude"
        assert model_cli_name([r"C:\Program Files\Git\bin\git.exe"]) == ""

    @pytest.mark.parametrize(
        "cmd",
        [
            ["git", "status"],
            ["git", "-C", "/repo", "log", "--oneline"],
            ["poetry", "run", "pytest"],
            ["gh", "pr", "view", "2703"],
            ["npm", "run", "lint"],
            [r"C:\Program Files\Git\bin\git.exe", "status"],
        ],
    )
    def test_ordinary_tooling_passes_through(self, cmd):
        """Hundreds of tests run git. A guard that stopped them would be
        removed within the day, which is the failure mode this avoids by
        reading the command rather than patching the call site."""
        assert model_cli_name(cmd) == ""
        refuse(cmd, "some::test")

    @pytest.mark.parametrize("cmd", [[], "", None, ["", "-p"]])
    def test_an_empty_command_is_not_a_model_call(self, cmd):
        assert model_cli_name(cmd) == ""

    def test_a_string_command_is_read_up_to_its_first_space(self):
        assert model_cli_name("claude -p hello") == "claude"
        assert model_cli_name("git status") == ""

    def test_the_set_is_closed_and_named(self):
        """Three transports today: ClaudeCLIProvider's two Popen sites and
        gemini_client's `agy`. A new one is added here deliberately."""
        assert MODEL_CLI_NAMES == frozenset({"claude", "agy", "gemini"})


class TestTheRefusal:
    def test_it_raises_on_a_model_cli(self):
        with pytest.raises(LiveModelCallInUnitTest) as caught:
            refuse(["claude", "-p", "hi"], "tests/unit/test_x.py::test_y")
        message = str(caught.value)
        assert "test_x.py::test_y" in message
        assert "'claude'" in message

    def test_the_message_points_at_the_fallback_path(self):
        """The incident was not a missing stub; it was a stub that covered one
        of two paths. A message that just says "stub the transport" would have
        been read as already done."""
        with pytest.raises(LiveModelCallInUnitTest) as caught:
            refuse(["agy"], "t")
        assert "FALLBACK" in str(caught.value)

    def test_the_message_names_where_such_a_test_belongs(self):
        with pytest.raises(LiveModelCallInUnitTest) as caught:
            refuse(["claude"], "t")
        assert "tests/integration/" in str(caught.value)

    def test_it_is_an_assertion_error_so_pytest_reports_it_as_a_failure(self):
        assert issubclass(LiveModelCallInUnitTest, AssertionError)


class TestTheGuardIsActuallyInstalledHere:
    """The self-check. Everything above tests a function; this tests that the
    function is wired into the fixture that runs for every unit test."""

    def test_spawning_a_model_cli_from_a_unit_test_is_refused(self):
        with pytest.raises(LiveModelCallInUnitTest):
            subprocess.Popen(["claude", "-p", "this must never run"])

    def test_subprocess_run_is_guarded_too(self):
        with pytest.raises(LiveModelCallInUnitTest):
            subprocess.run(["agy", "--model", "x"], capture_output=True)

    def test_git_still_runs_under_the_guard(self):
        """The other half: the guard is installed AND harmless. A test that
        only proved the refusal could pass with subprocess broken outright."""
        result = subprocess.run(
            ["git", "--version"], capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "git version" in result.stdout
