"""The requirements pre-check under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (base ``79e18ad1``), for
``assemblyzero/workflows/requirements/precheck.py``. The module already raised
``PrecheckError`` or returned an ``error`` status for every failure; what was
missing is the alert. Its one standalone caller, ``tools/check_requirements.py``,
now writes an ERROR line and alerts the operator on a ``PrecheckError`` and on
an ``error`` status, then exits 2. A conflict is a verdict, not a failure: it
prints verbatim, exits 1 and alerts nobody.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from assemblyzero.workflows.requirements import precheck

TITLE = "feat: config persistence"
BODY = "The app shall persist window position on exit."


@pytest.fixture
def cli():
    import check_requirements

    return check_requirements


def _gh(monkeypatch, *, returncode=0, stdout="", stderr="", raises=None):
    def run(*_a, **_kw):
        if raises is not None:
            raise raises
        return subprocess.CompletedProcess(
            args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr
        )

    monkeypatch.setattr(precheck.subprocess, "run", run)


def _main(cli, repo: Path) -> int:
    return cli.main(["--repo", str(repo), "--issue", "7", "--drafter", "fake:m"])


def _assert_alerted(code, operator_alerts, capsys, *needles):
    err = capsys.readouterr().err
    assert code == precheck.EXIT_ERROR
    assert "ERROR" in err
    assert len(operator_alerts) == 1
    alert = operator_alerts[0]
    assert alert["issue"] == 7
    assert alert["spec"] == "fake:m"
    for needle in needles:
        assert needle in alert["cause"], (needle, alert["cause"])


class TestTheIssueRead:
    def test_181_a_repo_that_is_not_a_directory_alerts(
        self, tmp_path, cli, capsys, operator_alerts
    ):
        code = _main(cli, tmp_path / "nope")
        _assert_alerted(code, operator_alerts, capsys, "not a directory")

    def test_192_a_missing_gh_alerts(self, tmp_path, cli, monkeypatch, capsys, operator_alerts):
        _gh(monkeypatch, raises=FileNotFoundError(2, "No such file", "gh"))
        code = _main(cli, tmp_path)
        _assert_alerted(code, operator_alerts, capsys, "gh CLI not found")

    def test_196_a_gh_timeout_alerts(self, tmp_path, cli, monkeypatch, capsys, operator_alerts):
        _gh(monkeypatch, raises=subprocess.TimeoutExpired(cmd="gh", timeout=60))
        code = _main(cli, tmp_path)
        _assert_alerted(code, operator_alerts, capsys, "timed out")

    def test_201_a_gh_failure_alerts_with_its_stderr(
        self, tmp_path, cli, monkeypatch, capsys, operator_alerts
    ):
        _gh(monkeypatch, returncode=1, stderr="HTTP 404: Not Found")
        code = _main(cli, tmp_path)
        _assert_alerted(code, operator_alerts, capsys, "HTTP 404")

    def test_207_output_that_is_not_json_alerts(
        self, tmp_path, cli, monkeypatch, capsys, operator_alerts
    ):
        _gh(monkeypatch, stdout="<html>rate limited</html>")
        code = _main(cli, tmp_path)
        _assert_alerted(code, operator_alerts, capsys, "not JSON")

    def test_215_a_payload_with_no_body_alerts(
        self, tmp_path, cli, monkeypatch, capsys, operator_alerts
    ):
        _gh(monkeypatch, stdout='{"title": "x"}')
        code = _main(cli, tmp_path)
        _assert_alerted(code, operator_alerts, capsys, "no issue body")


class TestTheGate:
    def _issue(self, cli, monkeypatch, body=BODY):
        monkeypatch.setattr(cli, "fetch_issue", lambda repo, issue, **k: (TITLE, body))

    def test_260_an_empty_body_alerts(self, tmp_path, cli, monkeypatch, capsys, operator_alerts):
        self._issue(cli, monkeypatch, body="   ")
        code = _main(cli, tmp_path)
        _assert_alerted(code, operator_alerts, capsys, "empty body")

    def test_283_a_gate_that_raises_alerts(
        self, tmp_path, cli, monkeypatch, capsys, operator_alerts
    ):
        self._issue(cli, monkeypatch)

        def boom(_state):
            raise RuntimeError("node crashed")

        monkeypatch.setattr(precheck, "analyze_requirements", boom)
        code = _main(cli, tmp_path)
        _assert_alerted(code, operator_alerts, capsys, "RuntimeError: node crashed")

    def test_298_a_gate_with_no_verdict_alerts(
        self, tmp_path, cli, monkeypatch, capsys, operator_alerts
    ):
        self._issue(cli, monkeypatch)
        monkeypatch.setattr(
            precheck, "analyze_requirements",
            lambda _state: {"requirements_unverified": "the provider timed out twice"},
        )
        code = _main(cli, tmp_path)
        _assert_alerted(code, operator_alerts, capsys, "the provider timed out twice")

    def test_310_no_conflict_and_no_clean_marker_alerts(
        self, tmp_path, cli, monkeypatch, capsys, operator_alerts
    ):
        self._issue(cli, monkeypatch)
        monkeypatch.setattr(precheck, "analyze_requirements", lambda _state: {})
        code = _main(cli, tmp_path)
        _assert_alerted(code, operator_alerts, capsys, "no verdict was reached")

    def test_a_conflict_is_a_verdict_and_alerts_nobody(
        self, tmp_path, cli, monkeypatch, capsys, operator_alerts
    ):
        """Kept: the gate ran and found contradictions; that is its job."""
        self._issue(cli, monkeypatch)
        monkeypatch.setattr(
            precheck, "analyze_requirements",
            lambda _state: {"error_message": "A contradicts B"},
        )
        code = _main(cli, tmp_path)
        assert code == precheck.EXIT_CONFLICT
        assert "A contradicts B" in capsys.readouterr().out
        assert operator_alerts == []

    def test_a_clean_verdict_alerts_nobody(
        self, tmp_path, cli, monkeypatch, capsys, operator_alerts
    ):
        self._issue(cli, monkeypatch)

        def clean(_state):
            print(precheck.CLEAN_MARKER)
            return {}

        monkeypatch.setattr(precheck, "analyze_requirements", clean)
        code = _main(cli, tmp_path)
        assert code == precheck.EXIT_CLEAN
        assert operator_alerts == []
