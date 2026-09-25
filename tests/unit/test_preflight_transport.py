"""The Gemini preflight runs only for a run that uses Gemini, and checks agy (#3506).

N1 called `check_gemini_available()` unconditionally. That reads
`~/.assemblyzero/gemini-credentials.json`, so a run launched with the
standalone defaults (`--drafter claude:sonnet --reviewer claude:opus`) could
not draft on a machine without the file, and on a machine with it the check
said nothing about whether `agy` -- the transport since ADR 0220 -- was
installed, logged in, or answering.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from assemblyzero.core import preflight


@pytest.fixture(autouse=True)
def _bypass_gemini_preflight():
    """Overrides the conftest fixture of the same name: here the transport
    check is the thing under test, and the credential-file check must never
    be called at all."""
    preflight._TRANSPORT_RESULT = None
    with patch(
        "assemblyzero.core.preflight.check_gemini_available",
        side_effect=AssertionError("the credential-file check must not run"),
    ):
        yield
    preflight._TRANSPORT_RESULT = None


class _FakeClient:
    def __init__(self, agy="agy.exe", success=True, response="pong", raises=None):
        self.agy, self.success, self.response, self.raises = agy, success, response, raises
        self.calls = 0

    def _find_agy_cli(self):
        return self.agy

    def invoke(self, system_instruction, content, response_schema=None):
        self.calls += 1
        if self.raises:
            raise self.raises
        return SimpleNamespace(
            success=self.success, response=self.response,
            error_message=None if self.success else "429 quota",
        )


class TestOnlyWhenGeminiIsConfigured:
    def test_a_claude_only_run_needs_no_preflight(self):
        assert preflight.preflight_for_specs("claude:sonnet", "claude:opus") is None

    def test_a_gemini_reviewer_gets_the_transport_check(self):
        client = _FakeClient()
        result = preflight.preflight_for_specs("claude:sonnet", "gemini:3.1-pro", client=client)
        assert result is not None and result.passed
        assert client.calls == 1

    def test_the_probe_runs_once_per_process(self):
        client = _FakeClient()
        preflight.preflight_for_specs("gemini:3.1-pro", client=client)
        again = preflight.preflight_for_specs("gemini:3.1-pro")
        assert again.passed and client.calls == 1


class TestItChecksTheTransport:
    def test_no_agy_is_a_transport_failure(self):
        r = preflight.check_gemini_transport(_FakeClient(agy=None))
        assert not r.passed
        assert r.warnings[0].startswith("transport: the agy CLI was not found")

    def test_a_failed_probe_is_a_transport_failure(self):
        r = preflight.check_gemini_transport(_FakeClient(success=False, response=None))
        assert not r.passed
        assert "transport: the probe call through agy failed: 429 quota" in r.warnings[0]

    def test_an_empty_answer_is_a_failure(self):
        r = preflight.check_gemini_transport(_FakeClient(response="   "))
        assert not r.passed and "empty response" in r.warnings[0]

    def test_a_raising_probe_is_a_transport_failure(self):
        r = preflight.check_gemini_transport(
            _FakeClient(raises=FileNotFoundError("Credentials file not found"))
        )
        assert not r.passed
        assert "transport: the probe call raised FileNotFoundError" in r.warnings[0]


class TestTheProbeUsesAGeminiModel:
    """#3541: `GeminiClient()` with no model takes `REVIEWER_MODEL`, now a
    Claude id, and raises -- so every Gemini-configured run halted at the
    preflight. The fake-client tests above never built the real client."""

    def test_the_real_client_is_built_without_raising(self):
        from assemblyzero.core.gemini_client import GeminiClient

        ok = SimpleNamespace(success=True, response="pong", error_message=None)
        with patch.object(GeminiClient, "_find_agy_cli", return_value="agy.exe"), \
                patch.object(GeminiClient, "invoke", return_value=ok):
            result = preflight.check_gemini_transport()

        assert result.passed, result.warnings

    def test_the_runs_gemini_spec_picks_the_probe_model(self):
        built: list[str] = []

        class _Recording(_FakeClient):
            def __init__(self, model):
                super().__init__()
                built.append(model)

        with patch("assemblyzero.core.gemini_client.GeminiClient", _Recording):
            result = preflight.preflight_for_specs("claude:sonnet", "gemini:3.1-pro")

        assert result.passed
        assert built == ["gemini-3.1-pro-high"]

    def test_a_spec_without_a_known_name_still_gets_a_gemini_model(self):
        assert preflight.gemini_model_for("gemini:something-new").startswith("gemini-")
        assert preflight.gemini_model_for("claude:opus") == preflight.DEFAULT_PROBE_MODEL


class TestN1ProceedsOnAClaudeOnlyRun:
    def test_n1_with_claude_specs_and_no_credential_file_drafts(self, tmp_path, monkeypatch):
        """The acceptance test: no credential file, Claude for every node,
        and N1 reaches the drafter instead of halting at [PREFLIGHT]."""
        gd = importlib.import_module(
            "assemblyzero.workflows.requirements.nodes.generate_draft"
        )
        from assemblyzero.core import config
        from assemblyzero.workflows.requirements.state import create_initial_state

        monkeypatch.setattr(config, "CREDENTIALS_FILE", tmp_path / "absent.json")
        template_dir = tmp_path / "docs" / "templates"
        template_dir.mkdir(parents=True)
        (template_dir / "0102-feature-lld-template.md").write_text("# T", encoding="utf-8")
        state = create_initial_state(
            workflow_type="lld", assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path), issue_number=42,
            drafter="claude:sonnet", reviewer="claude:opus",
        )
        state["issue_text"] = "# Issue"
        state["audit_dir"] = str(tmp_path / "audit")
        (tmp_path / "audit").mkdir()

        drafted = []

        class _Drafter:
            def invoke(self, *a, **kw):
                drafted.append(1)
                return SimpleNamespace(
                    success=True, response="# Draft\n", error_message=None,
                    input_tokens=0, output_tokens=0, cost_usd=0.0,
                    raw_response="# Draft\n", provider="claude", model_used="sonnet",
                    duration_ms=1, attempts=1,
                )

        with patch.object(gd, "get_provider", return_value=_Drafter()):
            out = gd.generate_draft(state)

        assert "[PREFLIGHT]" not in str(out.get("error_message", "")), out.get("error_message")
        assert drafted, "the drafter was never reached"
        assert not Path(tmp_path / "absent.json").exists()
