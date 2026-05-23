"""Tests for tools/_gate.py (AZ #1231 typed-confirmation gate).

Covers:
- Correct phrase → returns normally
- Wrong phrase → sys.exit(2) + refusal log entry
- EOF on stdin → sys.exit(2) + refusal log entry
- Refusal log entry contains expected fields with got truncated
- Multi-call (per-target loop simulation) preserves per-call state
- gate_phrase() returns the canonical format
- print_gate_phrase() prints the phrase and returns (no exit)
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import _gate  # noqa: E402


@pytest.fixture
def tmp_log(tmp_path, monkeypatch):
    """Redirect GATE_REFUSAL_LOG to a tmp path so tests don't pollute ~/.cache."""
    log_path = tmp_path / "gate-refusals.jsonl"
    monkeypatch.setattr(_gate, "GATE_REFUSAL_LOG", log_path)
    return log_path


def _read_log_records(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_gate_phrase_format():
    assert _gate.gate_phrase("rewrite-history", "martymcenroe/foo") == \
        "approve forbidden rewrite-history for martymcenroe/foo"


def test_correct_phrase_returns_normally(tmp_log, capsys):
    phrase = _gate.gate_phrase("delete-protection", "martymcenroe/foo")
    stream = io.StringIO(phrase + "\n")
    _gate.require_confirmation("delete-protection", "martymcenroe/foo", stream=stream)
    out = capsys.readouterr().out
    assert "Confirmed. Proceeding." in out
    assert _read_log_records(tmp_log) == []


def test_wrong_phrase_exits_2(tmp_log, capsys):
    stream = io.StringIO("wrong thing\n")
    with pytest.raises(SystemExit) as exc:
        _gate.require_confirmation("delete-protection", "martymcenroe/foo", stream=stream)
    assert exc.value.code == _gate.EXIT_REFUSED == 2
    out = capsys.readouterr().out
    assert "Confirmation failed" in out
    assert "Aborting. No changes made." in out


def test_wrong_phrase_logs_refusal(tmp_log):
    stream = io.StringIO("close enough\n")
    with pytest.raises(SystemExit):
        _gate.require_confirmation("force-push", "martymcenroe/foo", stream=stream)
    records = _read_log_records(tmp_log)
    assert len(records) == 1
    record = records[0]
    assert record["operation"] == "force-push"
    assert record["target"] == "martymcenroe/foo"
    assert record["expected"] == "approve forbidden force-push for martymcenroe/foo"
    assert record["got"] == "close enough"
    assert "ts" in record and isinstance(record["ts"], (int, float))


def test_eof_exits_2_and_logs(tmp_log, capsys):
    stream = io.StringIO("")
    with pytest.raises(SystemExit) as exc:
        _gate.require_confirmation("rewrite-history", "martymcenroe/foo", stream=stream)
    assert exc.value.code == 2
    records = _read_log_records(tmp_log)
    assert len(records) == 1
    assert records[0]["got"] == ""


def test_got_truncated_to_80_chars_in_log(tmp_log):
    long_garbage = "x" * 200
    stream = io.StringIO(long_garbage + "\n")
    with pytest.raises(SystemExit):
        _gate.require_confirmation("delete-protection", "martymcenroe/foo", stream=stream)
    records = _read_log_records(tmp_log)
    assert len(records) == 1
    got = records[0]["got"]
    assert got.endswith("...")
    assert len(got) == _gate.GOT_LOG_TRUNCATE + 3
    assert got == "x" * _gate.GOT_LOG_TRUNCATE + "..."


def test_trailing_whitespace_stripped(tmp_log, capsys):
    phrase = _gate.gate_phrase("delete-protection", "martymcenroe/foo")
    stream = io.StringIO(phrase + "\r\n")
    _gate.require_confirmation("delete-protection", "martymcenroe/foo", stream=stream)
    assert "Confirmed. Proceeding." in capsys.readouterr().out


def test_multi_target_loop_each_prompt_independent(tmp_log, capsys):
    """Simulate a per-target loop: 3 targets, all confirmed."""
    targets = ["martymcenroe/a", "martymcenroe/b", "martymcenroe/c"]
    for target in targets:
        phrase = _gate.gate_phrase("set-protection", target)
        stream = io.StringIO(phrase + "\n")
        _gate.require_confirmation("set-protection", target, stream=stream)
    out = capsys.readouterr().out
    assert out.count("Confirmed. Proceeding.") == 3
    assert _read_log_records(tmp_log) == []


def test_multi_target_loop_one_refusal_logs_only_that_one(tmp_log):
    """Simulate per-target loop where the middle target is refused."""
    targets = ["martymcenroe/a", "martymcenroe/b", "martymcenroe/c"]
    for i, target in enumerate(targets):
        phrase = _gate.gate_phrase("set-protection", target)
        text = phrase + "\n" if i != 1 else "no\n"
        stream = io.StringIO(text)
        if i == 1:
            with pytest.raises(SystemExit):
                _gate.require_confirmation("set-protection", target, stream=stream)
            break
        else:
            _gate.require_confirmation("set-protection", target, stream=stream)
    records = _read_log_records(tmp_log)
    assert len(records) == 1
    assert records[0]["target"] == "martymcenroe/b"
    assert records[0]["got"] == "no"


def test_print_gate_phrase_prints_and_returns(tmp_log, capsys):
    """`--gate-print-only` support: prints the phrase, returns, does not exit."""
    _gate.print_gate_phrase("rewrite-history", "martymcenroe/foo")
    out = capsys.readouterr().out
    assert out.strip() == "approve forbidden rewrite-history for martymcenroe/foo"


def test_log_dir_created_if_missing(tmp_path, monkeypatch):
    """Refusal log path should be created on first refusal even if parent dirs don't exist."""
    deep_path = tmp_path / "deep" / "nested" / "missing" / "gate-refusals.jsonl"
    monkeypatch.setattr(_gate, "GATE_REFUSAL_LOG", deep_path)
    stream = io.StringIO("wrong\n")
    with pytest.raises(SystemExit):
        _gate.require_confirmation("delete-protection", "martymcenroe/foo", stream=stream)
    assert deep_path.exists()
    assert len(_read_log_records(deep_path)) == 1


def test_stdin_fallback_when_no_stream(tmp_log, capsys, monkeypatch):
    """If stream=None, falls back to input(). Verify input() is called and returns its value."""
    phrase = _gate.gate_phrase("delete-protection", "martymcenroe/foo")
    with patch("builtins.input", return_value=phrase) as mock_input:
        _gate.require_confirmation("delete-protection", "martymcenroe/foo")
    mock_input.assert_called_once()
    assert "Confirmed. Proceeding." in capsys.readouterr().out
