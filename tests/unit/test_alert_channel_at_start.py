"""Every workflow entry point checks the alert channel before its first node (#3729).

ADR 0236: every failure alerts the operator, so a run whose alert channel
cannot work refuses to start. `alert.require_alert_channel` prints the reason
at ERROR and exits 1; it does not alert, because the channel is what is
broken. A mock run checks it too: the rule has no carve-out.

Each test breaks the channel, runs one entry point, and asserts the refusal
came before anything ran: the first thing the entry point would have called
is a stand-in that must not be reached.
"""
from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core import alert

REASON = "no alert sender configured: set AZ_OPERATOR_EMAIL_FROM"


@pytest.fixture
def broken_channel(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise alert.AlertDeliveryError(REASON)

    monkeypatch.setattr(alert, "check_alert_channel", refuse)


def _assert_refused(exc_info, capsys, operator_alerts, entry: str) -> None:
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert f"ERROR [preflight] {entry}" in err
    assert REASON in err
    assert operator_alerts == []


class TestTheStandInIsInPlace:
    def test_every_tier_gets_a_working_channel_without_aws(self):
        """tests/conftest.py replaces the check, so no test depends on the
        machine's sender or AWS credentials (#3729 requirement 2)."""
        assert alert.check_alert_channel() == "tests@example.invalid"

    def test_require_returns_the_sender_when_the_channel_works(self):
        assert alert.require_alert_channel("a test") == "tests@example.invalid"


class TestEveryEntryPointRefuses:
    def test_the_lld_workflow(self, broken_channel, capsys, operator_alerts):
        tool = importlib.import_module("tools.run_requirements_workflow")
        argv = ["prog", "--type", "lld", "--issue", "42", "--mock"]
        with patch("sys.argv", argv), \
             patch.object(tool, "run_single_workflow") as run, \
             patch.object(tool, "resolve_roots") as roots, \
             pytest.raises(SystemExit) as exc:
            tool.main()
        run.assert_not_called()
        roots.assert_not_called()
        _assert_refused(exc, capsys, operator_alerts, "tools/run_requirements_workflow.py")

    def test_the_issue_workflow(self, broken_channel, capsys, operator_alerts):
        tool = importlib.import_module("tools.run_requirements_workflow")
        argv = ["prog", "--type", "issue", "--brief", "brief.md", "--mock"]
        with patch("sys.argv", argv), \
             patch.object(tool, "run_single_workflow") as run, \
             pytest.raises(SystemExit) as exc:
            tool.main()
        run.assert_not_called()
        _assert_refused(exc, capsys, operator_alerts, "tools/run_requirements_workflow.py")

    def test_the_implementation_workflow(self, broken_channel, capsys, operator_alerts):
        tool = importlib.import_module("tools.run_implement_from_lld")
        argv = ["prog", "--issue", "42", "--mock", "--auto"]
        with patch("sys.argv", argv), \
             patch("assemblyzero.workflows.testing.build_testing_workflow") as build, \
             patch("assemblyzero.core.resume_contract.check_and_consume") as consume, \
             pytest.raises(SystemExit) as exc:
            tool.main()
        build.assert_not_called()
        consume.assert_not_called()
        _assert_refused(exc, capsys, operator_alerts, "tools/run_implement_from_lld.py")

    def test_the_implementation_spec_workflow(self, broken_channel, capsys, operator_alerts):
        tool = importlib.import_module("tools.run_implementation_spec_workflow")
        argv = ["prog", "--issue", "42", "--mock"]
        with patch("sys.argv", argv), \
             patch.object(tool, "run_workflow") as run, \
             pytest.raises(SystemExit) as exc:
            tool.main()
        run.assert_not_called()
        _assert_refused(exc, capsys, operator_alerts, "tools/run_implementation_spec_workflow.py")

    def test_the_orchestrator(self, broken_channel, capsys, operator_alerts):
        tool = importlib.import_module("tools.orchestrate")
        argv = ["prog", "--issue", "42", "--mock"]
        with patch("sys.argv", argv), \
             patch.object(tool, "orchestrate") as run, \
             pytest.raises(SystemExit) as exc:
            tool.main()
        run.assert_not_called()
        _assert_refused(exc, capsys, operator_alerts, "tools/orchestrate.py")

    def test_the_janitor(self, broken_channel, capsys, operator_alerts):
        tool = importlib.import_module("tools.run_janitor_workflow")
        with patch.object(tool, "build_janitor_graph") as build, \
             pytest.raises(SystemExit) as exc:
            tool.main(["--silent"])
        build.assert_not_called()
        _assert_refused(exc, capsys, operator_alerts, "tools/run_janitor_workflow.py")

    def test_the_scout(self, broken_channel, capsys, operator_alerts):
        tool = importlib.import_module("tools.run_scout_workflow")
        argv = ["prog", "--topic", "anything", "--offline", "--yes"]
        with patch("sys.argv", argv), \
             patch.object(tool, "create_initial_state") as start, \
             pytest.raises(SystemExit) as exc:
            tool.main()
        start.assert_not_called()
        _assert_refused(exc, capsys, operator_alerts, "tools/run_scout_workflow.py")

    def test_the_replay(self, broken_channel, capsys, operator_alerts, tmp_path):
        tool = importlib.import_module("tools.replay_run")
        argv = ["--recording", str(tmp_path), "--clone", str(tmp_path), "--issue", "42"]
        with patch.object(tool, "collect") as collect, \
             pytest.raises(SystemExit) as exc:
            tool.main(argv)
        collect.assert_not_called()
        _assert_refused(exc, capsys, operator_alerts, "tools/replay_run.py")

    def test_a_real_child_process_refuses_with_no_stand_in(self, tmp_path):
        """The whole path, with nothing patched: the orchestrator run as its own
        process, a home with no alert.json and no sender in the environment.
        It exits 1 at the check, before the merge-driver check or any stage."""
        import os
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        env = {k: v for k, v in os.environ.items() if k not in ("AZ_OPERATOR_EMAIL_FROM",)}
        env["HOME"] = str(tmp_path)
        env["USERPROFILE"] = str(tmp_path)
        proc = subprocess.run(
            [sys.executable, str(root / "tools" / "orchestrate.py"),
             "--issue", "2", "--repo", str(tmp_path), "--mock"],
            cwd=str(root), env=env, capture_output=True, text=True, timeout=120, check=False,
        )

        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert "ERROR [preflight] tools/orchestrate.py" in proc.stderr
        assert "no alert sender configured" in proc.stderr
        assert "Starting pipeline" not in proc.stdout
        assert not (tmp_path / ".assemblyzero" / "alerts.jsonl").exists()

    def test_the_child_helper_gives_a_working_channel(self, tmp_path):
        """`child_env_with_alert_channel` is what subprocess tests use; with it
        the same child passes the check and reaches the next refusal."""
        import os
        import subprocess
        import sys
        from pathlib import Path

        from tests.conftest import child_env_with_alert_channel

        root = Path(__file__).resolve().parents[2]
        env = child_env_with_alert_channel(
            {k: v for k, v in os.environ.items() if k != "AZ_MERGE_DRIVER"}
        )
        env["HOME"] = str(tmp_path)
        env["USERPROFILE"] = str(tmp_path)
        proc = subprocess.run(
            [sys.executable, str(root / "tools" / "orchestrate.py"),
             "--issue", "2", "--repo", str(tmp_path)],
            cwd=str(root), env=env, capture_output=True, text=True, timeout=120, check=False,
        )

        assert "ERROR [preflight]" not in proc.stderr, proc.stderr
        assert "merge driver not configured" in proc.stdout, proc.stdout + proc.stderr

    def test_the_hourglass(self, broken_channel, capsys, operator_alerts):
        from assemblyzero.workflows.death import hourglass

        build = MagicMock()
        with patch.object(hourglass, "create_hourglass_graph", build), \
             patch.object(hourglass, "load_age_meter_state") as meter, \
             pytest.raises(SystemExit) as exc:
            hourglass.run_death("report", "summon", ".", "owner/repo")
        build.assert_not_called()
        meter.assert_not_called()
        _assert_refused(
            exc, capsys, operator_alerts,
            "assemblyzero.workflows.death.hourglass.run_death",
        )
