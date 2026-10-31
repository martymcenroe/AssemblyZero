"""The telemetry emitter fails loudly (ADR 0236, #3585).

The emitter was fire-and-forget: every failure was a bare ``pass`` or a silent
``None``. An event that could not be built, or that reached neither DynamoDB
nor the local buffer, was dropped; a credentials file that could not be loaded
read as "no telemetry configured"; a buffered event that failed to upload was
kept with nothing said; and a buffer file that could not be read or rewritten
was skipped. Now each alerts the operator. A lost event, and a flush that
cannot read or rewrite its buffer, also raise.

Two answers stay quiet, by contract, and are pinned here (won't do for 54 and
171): a machine with no credentials file runs in local-only mode, keeping every
event in the buffer, so nothing is lost; and ``flush`` with no client has
uploaded nothing, so 0 is the true count. The opt-out is
``ASSEMBLYZERO_TELEMETRY=0``.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.telemetry import emitter
from assemblyzero.telemetry.emitter import emit, flush


@pytest.fixture
def fresh_client(monkeypatch):
    """Reset the cached client so _get_dynamo_client runs again."""
    monkeypatch.setattr(emitter, "_dynamo_client", None)
    monkeypatch.setattr(emitter, "_dynamo_init_attempted", False)
    monkeypatch.setattr(emitter, "_alerted", set(), raising=False)


def _no_client(monkeypatch, buffer_dir):
    monkeypatch.setattr(emitter, "_dynamo_client", None)
    monkeypatch.setattr(emitter, "_dynamo_init_attempted", True)
    monkeypatch.setattr(emitter, "_BUFFER_DIR", buffer_dir)
    monkeypatch.setattr(emitter, "_alerted", set(), raising=False)


def _client(monkeypatch, buffer_dir, table):
    monkeypatch.setattr(emitter, "_dynamo_client", table)
    monkeypatch.setattr(emitter, "_dynamo_init_attempted", True)
    monkeypatch.setattr(emitter, "_BUFFER_DIR", buffer_dir)
    monkeypatch.setattr(emitter, "_alerted", set(), raising=False)


def test_54_no_credentials_file_is_local_only_mode_and_quiet(tmp_path, monkeypatch, fresh_client, operator_alerts):
    monkeypatch.setattr(emitter.Path, "home", classmethod(lambda cls: tmp_path))

    assert emitter._get_dynamo_client() is None
    assert operator_alerts == []


def test_68_a_credentials_file_that_cannot_be_loaded_alerts_once_and_raises_every_time(
    tmp_path, monkeypatch, fresh_client, operator_alerts
):
    creds = tmp_path / ".assemblyzero" / "aws-telemetry-credentials.json"
    creds.parent.mkdir(parents=True)
    creds.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(emitter.Path, "home", classmethod(lambda cls: tmp_path))

    for _ in range(2):
        with pytest.raises(RuntimeError) as excinfo:
            emitter._get_dynamo_client()
        assert type(excinfo.value).__name__ == "TelemetryConfigError"

    assert len(operator_alerts) == 1
    assert "DynamoDB" in operator_alerts[0]["what"]
    assert "not json" not in operator_alerts[0]["cause"], "no credential content in the alert"


def test_84_an_event_the_buffer_cannot_take_alerts_and_raises(tmp_path, monkeypatch, operator_alerts):
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    _no_client(monkeypatch, blocker / "buffer")

    with pytest.raises(OSError):
        emit("workflow.start", repo="AssemblyZero")

    assert len(operator_alerts) == 1
    assert "workflow.start" in operator_alerts[0]["cause"]


def test_151_a_failed_put_alerts_once_and_the_event_is_buffered(tmp_path, monkeypatch, operator_alerts, capsys):
    table = MagicMock()
    table.put_item.side_effect = RuntimeError("throttled")
    _client(monkeypatch, tmp_path / "buffer", table)

    emit("tool.start")
    emit("tool.complete")

    assert len(list((tmp_path / "buffer").glob("*.jsonl"))) == 1
    lines = next((tmp_path / "buffer").glob("*.jsonl")).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2, "both events are kept for the sync"
    assert len(operator_alerts) == 1, "one alert per process, not one per event"
    assert capsys.readouterr().err.count("ERROR [TELEMETRY]") == 2


def test_156_an_event_that_cannot_be_built_alerts_and_raises(tmp_path, monkeypatch, operator_alerts):
    _no_client(monkeypatch, tmp_path / "buffer")
    monkeypatch.setattr(emitter, "_build_event", MagicMock(side_effect=RuntimeError("boom")))

    with pytest.raises(RuntimeError):
        emit("test.event")

    assert len(operator_alerts) == 1
    assert "boom" in operator_alerts[0]["cause"]


def test_171_flush_with_no_client_uploads_nothing_and_says_zero(tmp_path, monkeypatch, operator_alerts):
    _no_client(monkeypatch, tmp_path / "buffer")
    assert flush() == 0
    assert operator_alerts == []


def test_192_a_buffered_event_that_fails_to_upload_is_kept_and_alerts_once(tmp_path, monkeypatch, operator_alerts, capsys):
    buffer_dir = tmp_path / "buffer"
    buffer_dir.mkdir()
    buffer_file = buffer_dir / "2026-10-30.jsonl"
    buffer_file.write_text('{"n": 1}\n{"n": 2}\n{not json\n', encoding="utf-8")
    table = MagicMock()
    table.put_item.side_effect = [None, RuntimeError("throttled")]
    _client(monkeypatch, buffer_dir, table)

    assert flush() == 1

    remaining = buffer_file.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["n"] for line in remaining[:1]] == [2]
    assert remaining[1] == "{not json"
    assert len(operator_alerts) == 1
    assert capsys.readouterr().err.count("ERROR [TELEMETRY]") == 2


def test_200_a_buffer_file_that_cannot_be_read_alerts_and_raises(tmp_path, monkeypatch, operator_alerts):
    buffer_dir = tmp_path / "buffer"
    buffer_dir.mkdir()
    (buffer_dir / "2026-10-30.jsonl").mkdir()  # a directory where a file must be
    _client(monkeypatch, buffer_dir, MagicMock())

    with pytest.raises(OSError):
        flush()

    assert len(operator_alerts) == 1
    assert "2026-10-30.jsonl" in operator_alerts[0]["cause"]


def test_203_the_flush_does_not_swallow_its_own_failure(tmp_path, monkeypatch, operator_alerts):
    _client(monkeypatch, tmp_path / "buffer", MagicMock())
    (tmp_path / "buffer").mkdir()

    with (
        patch.object(emitter.Path, "glob", side_effect=PermissionError(13, "denied")),
        pytest.raises(PermissionError),
    ):
        flush()


def test_a_healthy_emit_and_flush_are_quiet(tmp_path, monkeypatch, operator_alerts, capsys):
    table = MagicMock()
    _no_client(monkeypatch, tmp_path / "buffer")
    emit("workflow.start")
    _client(monkeypatch, tmp_path / "buffer", table)

    assert flush() == 1
    assert operator_alerts == []
    assert "ERROR" not in capsys.readouterr().err
