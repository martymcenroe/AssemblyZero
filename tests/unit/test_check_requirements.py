"""Unit tests for the standalone N0c requirements pre-check (#2221).

The load-bearing property is that standalone the gate never fails open. In a
roll an analysis that cannot run is a warning and the workflow proceeds; here
it must be an error, because a human asked for the check and a clean exit
would assert something nobody verified. Most of this file drives the live node
through each of its fail-open branches and asserts a nonzero result.

No test may reach the network. The conflict path files must-resolve issues via
gh in production, so every conflict test patches that out and asserts on the
recorded call instead.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from assemblyzero.core.llm_provider import LLMCallResult  # noqa: E402
from assemblyzero.workflows.requirements import precheck  # noqa: E402

ISSUE_BODY = "The app shall persist window position on exit."
ISSUE_TITLE = "feat: config persistence"


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeProvider:
    """Stands in for whatever get_provider() returns inside the node."""

    def __init__(self, result: LLMCallResult) -> None:
        self._result = result
        self.calls: list[dict] = []

    def invoke(self, **kwargs) -> LLMCallResult:
        self.calls.append(kwargs)
        return self._result


def _result(success: bool, response: str | None, error: str | None = None) -> LLMCallResult:
    return LLMCallResult(
        success=success,
        response=response,
        raw_response=response,
        error_message=error,
        provider="fake",
        model_used="fake-model",
        duration_ms=1,
        attempts=1,
    )


@pytest.fixture
def no_filing(monkeypatch):
    """Capture must-resolve filings and telemetry instead of performing them."""
    filings: list[tuple] = []

    def _fake_file_all_conflicts(repo_root, source_issue, conflicts, **kwargs):
        filings.append((repo_root, source_issue, conflicts))
        return []

    monkeypatch.setattr(
        "assemblyzero.speedrun.must_resolve.file_all_conflicts",
        _fake_file_all_conflicts,
    )
    monkeypatch.setattr(
        "assemblyzero.speedrun.prompt_telemetry.record_failures",
        lambda *a, **k: None,
    )
    return filings


def _install_provider(monkeypatch, provider) -> None:
    """The node imports get_provider at call time, so patch the module."""
    monkeypatch.setattr(
        "assemblyzero.core.llm_provider.get_provider",
        lambda spec, *a, **k: provider,
    )


def _run(tmp_path, *, body: str = ISSUE_BODY, drafter: str = "fake:model"):
    return precheck.run_gate(tmp_path, 7, ISSUE_TITLE, body, drafter=drafter)


CONSISTENT = '{"is_consistent": true, "conflicts": []}'

CONFLICT_A = "the exit write touches only hand-changed keys"
CONFLICT_B = "--reset-config rewrites the file regardless"
CONFLICTED = (
    '{"is_consistent": false, "conflicts": [{"criterion_a": "%s", '
    '"criterion_b": "%s", "diverging_situation": "a reset session that was '
    'never touched"}]}' % (CONFLICT_A, CONFLICT_B)
)


# ---------------------------------------------------------------------------
# The gate is imported, never reimplemented (acceptance criterion 1)
# ---------------------------------------------------------------------------


class TestSameGate:
    def test_precheck_calls_the_function_the_graph_registers_as_n0c(self):
        """Identity, not equivalence: one function object, two callers.

        A copied or re-derived checker could drift from the gate, and a clean
        result from a drifted checker is false confidence.
        """
        from assemblyzero.workflows.requirements import graph

        assert precheck.analyze_requirements is graph.analyze_requirements

    def test_gate_module_is_the_workflow_node_module(self):
        assert (
            precheck.analyze_requirements.__module__
            == "assemblyzero.workflows.requirements.nodes.analyze_requirements"
        )


# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------


class TestClean:
    def test_consistent_requirements_exit_zero(self, tmp_path, monkeypatch):
        _install_provider(monkeypatch, _FakeProvider(_result(True, CONSISTENT)))

        result = _run(tmp_path)

        assert result.status == "clean"
        assert result.exit_code == 0

    def test_clean_marker_still_matches_the_live_node(self, tmp_path, monkeypatch):
        """Drift guard for the one string this tool reads as a pass.

        The node signals a clean verdict only by printing it -- the state
        update is empty for a clean result and for every fail-open skip
        alike. If the node's wording changes, this fails here rather than
        turning every clean pre-check into a spurious error in the field.
        """
        _install_provider(monkeypatch, _FakeProvider(_result(True, CONSISTENT)))

        result = _run(tmp_path)

        assert precheck.CLEAN_MARKER in result.node_output

    def test_report_names_what_it_did_not_verify(self, tmp_path, monkeypatch):
        _install_provider(monkeypatch, _FakeProvider(_result(True, CONSISTENT)))
        result = _run(tmp_path)

        report = precheck.render_report(result, tmp_path, 7, "fake:model")

        assert "CLEAN" in report
        assert "Not verified" in report

    def test_fenced_json_is_still_a_clean_verdict(self, tmp_path, monkeypatch):
        fenced = f"```json\n{CONSISTENT}\n```"
        _install_provider(monkeypatch, _FakeProvider(_result(True, fenced)))

        assert _run(tmp_path).status == "clean"


# ---------------------------------------------------------------------------
# Conflict (acceptance criterion 2)
# ---------------------------------------------------------------------------


class TestConflict:
    def test_conflict_exits_nonzero(self, tmp_path, monkeypatch, no_filing):
        _install_provider(monkeypatch, _FakeProvider(_result(True, CONFLICTED)))

        result = _run(tmp_path)

        assert result.status == "conflict"
        assert result.exit_code != 0

    def test_both_sentences_print_verbatim(self, tmp_path, monkeypatch, no_filing):
        _install_provider(monkeypatch, _FakeProvider(_result(True, CONFLICTED)))

        result = _run(tmp_path)
        report = precheck.render_report(result, tmp_path, 7, "fake:model")

        assert CONFLICT_A in report
        assert CONFLICT_B in report
        assert "a reset session that was never touched" in report

    def test_conflict_files_must_resolve_issues_against_the_target_repo(
        self, tmp_path, monkeypatch, no_filing
    ):
        """The gate's own side effect, aimed at the repo under analysis.

        Passing no target_repo would make the node fall back to ".", filing
        the target repo's conflicts against whatever repo the tool ran from.
        """
        _install_provider(monkeypatch, _FakeProvider(_result(True, CONFLICTED)))

        _run(tmp_path)

        assert len(no_filing) == 1
        repo_root, source_issue, conflicts = no_filing[0]
        assert Path(repo_root) == tmp_path
        assert source_issue == 7
        assert len(conflicts) == 1

    def test_report_says_filing_failed_when_it_did(self, tmp_path, monkeypatch):
        def _boom(*a, **k):
            raise RuntimeError("gh exploded")

        monkeypatch.setattr(
            "assemblyzero.speedrun.must_resolve.file_all_conflicts", _boom
        )
        monkeypatch.setattr(
            "assemblyzero.speedrun.prompt_telemetry.record_failures",
            lambda *a, **k: None,
        )
        _install_provider(monkeypatch, _FakeProvider(_result(True, CONFLICTED)))

        result = _run(tmp_path)
        report = precheck.render_report(result, tmp_path, 7, "fake:model")

        assert result.status == "conflict"
        assert result.filing_failed
        assert "could not file" in report


# ---------------------------------------------------------------------------
# Fail-open does not carry over (acceptance criterion 4)
# ---------------------------------------------------------------------------


class TestNeverASilentPass:
    def test_provider_failure_is_an_error_not_a_pass(self, tmp_path, monkeypatch):
        """The roll proceeds here. Standalone this must not read as clean."""
        _install_provider(
            monkeypatch, _FakeProvider(_result(False, None, "503 from provider"))
        )

        result = _run(tmp_path)

        assert result.status == "error"
        assert result.exit_code == precheck.EXIT_ERROR
        assert "503 from provider" in result.detail

    def test_empty_response_is_an_error(self, tmp_path, monkeypatch):
        _install_provider(monkeypatch, _FakeProvider(_result(True, "")))

        assert _run(tmp_path).status == "error"

    def test_unparseable_response_is_an_error(self, tmp_path, monkeypatch):
        _install_provider(monkeypatch, _FakeProvider(_result(True, "not json at all")))

        result = _run(tmp_path)

        assert result.status == "error"
        assert "unparseable" in result.detail

    def test_schema_violating_json_is_an_error(self, tmp_path, monkeypatch):
        """Valid JSON missing the contract's required key is still no verdict."""
        _install_provider(
            monkeypatch, _FakeProvider(_result(True, '{"something_else": true}'))
        )

        assert _run(tmp_path).status == "error"

    def test_invalid_provider_spec_is_an_error(self, tmp_path):
        """get_provider raises, the node warns and returns {}. Not a pass."""
        result = _run(tmp_path, drafter="nosuchprovider:model")

        assert result.status == "error"
        assert result.exit_code == precheck.EXIT_ERROR

    def test_mock_mode_is_never_requested(self, tmp_path, monkeypatch):
        """config_mock_mode short-circuits the node before any analysis."""
        seen: list[dict] = []

        def _spy(state):
            seen.append(dict(state))
            return {}

        monkeypatch.setattr(precheck, "analyze_requirements", _spy)

        precheck.run_gate(tmp_path, 7, ISSUE_TITLE, ISSUE_BODY)

        assert "config_mock_mode" not in seen[0]

    def test_silent_empty_update_is_an_error(self, tmp_path, monkeypatch):
        """A node that returns {} while printing nothing verified nothing."""
        monkeypatch.setattr(precheck, "analyze_requirements", lambda state: {})

        result = precheck.run_gate(tmp_path, 7, ISSUE_TITLE, ISSUE_BODY)

        assert result.status == "error"
        assert "no verdict" in result.detail

    def test_empty_issue_body_raises(self, tmp_path):
        with pytest.raises(precheck.PrecheckError, match="empty body"):
            precheck.run_gate(tmp_path, 7, ISSUE_TITLE, "   \n  ")

    def test_gate_exception_raises_rather_than_returning_clean(
        self, tmp_path, monkeypatch
    ):
        def _boom(state):
            raise RuntimeError("node exploded")

        monkeypatch.setattr(precheck, "analyze_requirements", _boom)

        with pytest.raises(precheck.PrecheckError, match="node exploded"):
            precheck.run_gate(tmp_path, 7, ISSUE_TITLE, ISSUE_BODY)


# ---------------------------------------------------------------------------
# Issue fetch
# ---------------------------------------------------------------------------


class TestFetchIssue:
    def _fake_run(self, monkeypatch, *, returncode=0, stdout="", stderr=""):
        import subprocess

        class _Proc:
            pass

        proc = _Proc()
        proc.returncode = returncode
        proc.stdout = stdout
        proc.stderr = stderr
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: proc)

    def test_returns_title_and_body(self, tmp_path, monkeypatch):
        self._fake_run(
            monkeypatch, stdout='{"title": "feat: x", "body": "the body"}'
        )

        assert precheck.fetch_issue(tmp_path, 7) == ("feat: x", "the body")

    def test_gh_failure_raises(self, tmp_path, monkeypatch):
        self._fake_run(monkeypatch, returncode=1, stderr="could not resolve to an Issue")

        with pytest.raises(precheck.PrecheckError, match="could not resolve"):
            precheck.fetch_issue(tmp_path, 7)

    def test_non_json_output_raises(self, tmp_path, monkeypatch):
        self._fake_run(monkeypatch, stdout="<html>login</html>")

        with pytest.raises(precheck.PrecheckError, match="not JSON"):
            precheck.fetch_issue(tmp_path, 7)

    def test_payload_without_body_raises(self, tmp_path, monkeypatch):
        self._fake_run(monkeypatch, stdout='{"title": "feat: x"}')

        with pytest.raises(precheck.PrecheckError, match="no issue body"):
            precheck.fetch_issue(tmp_path, 7)

    def test_missing_repo_raises(self, tmp_path):
        with pytest.raises(precheck.PrecheckError, match="not a directory"):
            precheck.fetch_issue(tmp_path / "nope", 7)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    def _cli(self):
        import check_requirements

        return check_requirements

    def test_clean_run_exits_zero(self, tmp_path, monkeypatch, capsys):
        cli = self._cli()
        monkeypatch.setattr(
            cli, "fetch_issue", lambda repo, issue, **k: (ISSUE_TITLE, ISSUE_BODY)
        )
        _install_provider(monkeypatch, _FakeProvider(_result(True, CONSISTENT)))

        code = cli.main(["--repo", str(tmp_path), "--issue", "7", "--drafter", "fake:m"])

        assert code == 0
        assert "CLEAN" in capsys.readouterr().out

    def test_conflict_exits_one(self, tmp_path, monkeypatch, capsys, no_filing):
        cli = self._cli()
        monkeypatch.setattr(
            cli, "fetch_issue", lambda repo, issue, **k: (ISSUE_TITLE, ISSUE_BODY)
        )
        _install_provider(monkeypatch, _FakeProvider(_result(True, CONFLICTED)))

        code = cli.main(["--repo", str(tmp_path), "--issue", "7", "--drafter", "fake:m"])

        out = capsys.readouterr().out
        assert code == 1
        assert CONFLICT_A in out and CONFLICT_B in out

    def test_analysis_failure_exits_two(self, tmp_path, monkeypatch, capsys):
        cli = self._cli()
        monkeypatch.setattr(
            cli, "fetch_issue", lambda repo, issue, **k: (ISSUE_TITLE, ISSUE_BODY)
        )
        _install_provider(monkeypatch, _FakeProvider(_result(False, None, "529")))

        code = cli.main(["--repo", str(tmp_path), "--issue", "7", "--drafter", "fake:m"])

        assert code == 2
        assert "ERROR" in capsys.readouterr().out

    def test_fetch_failure_exits_two(self, tmp_path, monkeypatch, capsys):
        cli = self._cli()

        def _boom(repo, issue, **k):
            raise precheck.PrecheckError("gh issue view #7 failed")

        monkeypatch.setattr(cli, "fetch_issue", _boom)

        code = cli.main(["--repo", str(tmp_path), "--issue", "7"])

        assert code == 2
        assert "has been verified" in capsys.readouterr().err
