"""Every agy process and every Claude provider call writes one model-call ledger line.

No model runs here. A Popen double answers as ``agy --output-format json``
would, and every ledger is a file in the test's tmp_path, named by
MODEL_CALL_LEDGER.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core import model_call_ledger as mcl
from assemblyzero.core.gemini_client import GeminiClient
from assemblyzero.core.llm_provider import LLMCallResult, log_llm_call

MODEL = "gemini-3.8-flash-high"


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    path = tmp_path / "ledger.jsonl"
    monkeypatch.setenv(mcl.LEDGER_ENV, str(path))
    return path


def rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


def proc(stdout="", stderr="", returncode=0):
    p = MagicMock()
    p.pid = 4242
    p.communicate.return_value = (stdout, stderr)
    p.returncode = returncode
    return p


def client():
    c = GeminiClient(model=MODEL)
    c._agy_cli = "/fake/agy"
    return c


def agy_json(response="A fine review.", status="SUCCESS", usage=None):
    return json.dumps({"status": status, "response": response,
                       "usage": usage if usage is not None else {"input_tokens": 2766, "output_tokens": 41}})


# --- the agy transport ------------------------------------------------------------------


@patch("assemblyzero.core.gemini_client.subprocess.Popen")
def test_a_successful_agy_call_writes_one_full_line(mock_popen, ledger):
    mock_popen.return_value = proc(stdout=agy_json())
    ok, text, err = client()._invoke_via_stdin("prompt")
    assert ok is True and text == "A fine review." and err == ""
    [row] = rows(ledger)
    assert set(row) == set(mcl.FIELDS)
    assert (row["library"], row["transport"], row["model"]) == ("assemblyzero.gemini_client", "agy", MODEL)
    assert (row["tokens_in"], row["tokens_out"], row["outcome"]) == (2766, 41, "ok")
    assert row["error"] is None and row["repo"] and row["program"]


@patch("assemblyzero.core.gemini_client.subprocess.Popen")
def test_agy_is_asked_for_json(mock_popen, ledger):
    mock_popen.return_value = proc(stdout=agy_json())
    client()._invoke_via_stdin("prompt")
    argv = mock_popen.call_args[0][0]
    assert argv[argv.index("--output-format") + 1] == "json"


@patch("assemblyzero.core.gemini_client.subprocess.Popen")
def test_plain_text_output_still_succeeds_with_no_tokens(mock_popen, ledger):
    mock_popen.return_value = proc(stdout="A plain answer.\n")
    ok, text, _ = client()._invoke_via_stdin("prompt")
    assert ok is True and text == "A plain answer."
    [row] = rows(ledger)
    assert row["outcome"] == "ok" and row["tokens_in"] is None


@patch("assemblyzero.core.gemini_client.subprocess.Popen")
def test_a_status_other_than_success_is_a_failure_that_keeps_its_tokens(mock_popen, ledger):
    mock_popen.return_value = proc(stdout=agy_json(response="", status="ERROR",
                                                   usage={"input_tokens": 9, "output_tokens": 0}))
    ok, _, err = client()._invoke_via_stdin("prompt")
    assert ok is False and "ERROR" in err
    [row] = rows(ledger)
    assert row["outcome"] == "failed" and row["tokens_in"] == 9 and row["error"]


@patch("assemblyzero.core.gemini_client.subprocess.Popen")
def test_a_non_zero_exit_writes_a_failed_line(mock_popen, ledger):
    mock_popen.return_value = proc(stderr="Error: invalid --model", returncode=1)
    ok, _, _ = client()._invoke_via_stdin("prompt")
    assert ok is False
    assert [r["outcome"] for r in rows(ledger)] == ["failed"]


@patch("assemblyzero.core.gemini_client.kill_process_tree")
@patch("assemblyzero.core.gemini_client.subprocess.Popen")
def test_a_timeout_writes_a_timeout_line(mock_popen, _kill, ledger):
    p = proc()
    p.communicate.side_effect = [subprocess.TimeoutExpired(cmd="agy", timeout=1), ("", "")]
    mock_popen.return_value = p
    ok, _, err = client()._invoke_via_stdin("prompt", timeout_seconds=1)
    assert ok is False and "timeout" in err.lower()
    assert [r["outcome"] for r in rows(ledger)] == ["timeout"]


@patch("assemblyzero.core.gemini_client.subprocess.Popen", side_effect=OSError("no agy"))
def test_agy_that_never_started_writes_nothing(_popen, ledger):
    ok, _, _ = client()._invoke_via_stdin("prompt")
    assert ok is False
    assert rows(ledger) == []


@patch("assemblyzero.core.gemini_client.subprocess.Popen")
def test_each_retry_is_its_own_line(mock_popen, ledger, monkeypatch):
    """invoke() retries: every agy process it starts is a model call."""
    monkeypatch.setattr(GeminiClient, "_backoff_delay", lambda self, attempt: 0)
    mock_popen.side_effect = [proc(stderr="503 overloaded", returncode=1), proc(stdout=agy_json())]
    result = client().invoke("sys", "content")
    assert result.success is True
    assert [r["outcome"] for r in rows(ledger)] == ["failed", "ok"]


@patch("assemblyzero.core.gemini_client.subprocess.Popen")
def test_a_reply_that_opens_like_json_and_does_not_parse_raises_and_is_recorded(mock_popen, ledger):
    mock_popen.return_value = proc(stdout='{"status": "SUCCESS", "response": ')
    with pytest.raises(RuntimeError, match="does not parse"):
        client()._invoke_via_stdin("prompt")
    [row] = rows(ledger)
    assert row["outcome"] == "failed" and "does not parse" in row["error"]


@patch("assemblyzero.core.gemini_client.subprocess.Popen")
def test_a_json_model_answer_outside_the_envelope_is_plain_text(mock_popen, ledger):
    mock_popen.return_value = proc(stdout='{"verdict": "APPROVE"}')
    ok, text, _ = client()._invoke_via_stdin("prompt")
    assert ok is True and text == '{"verdict": "APPROVE"}'


def test_a_line_that_cannot_be_written_alerts_the_operator(tmp_path, monkeypatch):
    """ADR 0236: the failed write is loud and reaches the operator; it is not swallowed."""
    monkeypatch.setenv(mcl.LEDGER_ENV, str(tmp_path))  # a directory: open() fails
    alerts = []
    monkeypatch.setattr("assemblyzero.core.alert.alert_operator", lambda **kw: alerts.append(kw))
    mcl.record("assemblyzero.gemini_client", "agy", MODEL, None, 1.0, "ok")
    assert len(alerts) == 1
    assert alerts[0]["issue"] == 4199 and "missing" in alerts[0]["consequence"]


# --- the providers ----------------------------------------------------------------------


def call(provider: str, success: bool = True, **kw) -> LLMCallResult:
    return LLMCallResult(success=success, response="x" if success else None, raw_response=None,
                         error_message=None if success else "claude -p failed: boom",
                         provider=provider, model_used="opus", duration_ms=1500, attempts=1, **kw)


def test_a_claude_provider_call_writes_one_line(ledger, capsys):
    log_llm_call(call("claude", input_tokens=10, output_tokens=5, cache_read_tokens=100,
                      cache_creation_tokens=1))
    [row] = rows(ledger)
    assert (row["library"], row["transport"], row["model"]) == ("assemblyzero.llm_provider", "claude", "opus")
    assert (row["tokens_in"], row["tokens_out"], row["outcome"], row["wall_s"]) == (111, 5, "ok", 1.5)


def test_a_failed_provider_call_writes_a_failed_line(ledger, capsys):
    log_llm_call(call("claude", success=False))
    [row] = rows(ledger)
    assert (row["transport"], row["outcome"]) == ("claude", "failed")
    assert row["error"]


def test_a_timed_out_provider_call_is_a_timeout(ledger, capsys):
    log_llm_call(call("claude", success=False, failure_class="timeout"))
    assert rows(ledger)[0]["outcome"] == "timeout"


@pytest.mark.parametrize("provider", ["gemini", "mock"])
def test_gemini_and_mock_providers_write_nothing_here(ledger, capsys, provider):
    """The Gemini seat's line is written per agy process by GeminiClient; a mock is no model."""
    log_llm_call(call(provider))
    assert rows(ledger) == []


# --- the writer -------------------------------------------------------------------------


def test_under_pytest_without_the_variable_nothing_is_written(tmp_path, monkeypatch):
    monkeypatch.delenv(mcl.LEDGER_ENV, raising=False)
    monkeypatch.setattr(mcl.Path, "home", lambda: tmp_path / "home")
    assert mcl.ledger_path() is None
    mcl.record("x", "agy", "m", None, 1.0, "ok")
    assert not (tmp_path / "home").exists()


def test_outside_pytest_the_ledger_is_under_claude_logs(monkeypatch):
    monkeypatch.delenv(mcl.LEDGER_ENV, raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(mcl.Path, "home", lambda: Path("/h"))
    assert mcl.ledger_path() == Path("/h/.claude/logs/model-calls.jsonl")


@pytest.mark.parametrize("gitdir", [
    "/mnt/c/Users/me/Projects/Repo/.git/worktrees/Repo-12",
    "C:/Users/me/Projects/Repo/.git/worktrees/Repo-12",
])
def test_a_worktree_is_its_repository(tmp_path, gitdir):
    wt = tmp_path / "Repo-12"
    (wt / "sub").mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    assert mcl.repo_of(wt / "sub") == "Repo"
