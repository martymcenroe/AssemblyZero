"""The LLM call-record store fails loudly (ADR 0236, #3585).

``CallStore.write`` swallowed every exception at WARNING, so a call record that
could not be written was lost. ``read_day`` and ``query`` skipped a corrupt
line, and ``query`` skipped a ``calls-*.jsonl`` file whose name held no date,
so either reader returned fewer records than the store holds. Each now alerts
the operator and raises, naming the file (and the line).

A disabled store, and a day with no file, stay quiet by contract.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import datetime

import orjson
import pytest

from assemblyzero.telemetry.llm_call_record import (
    LLMCallRecord,
    LLMInputParams,
    make_record_id,
    now_utc_iso,
)
from assemblyzero.telemetry.store import CallStore


def _record(workflow: str = "lld") -> LLMCallRecord:
    return LLMCallRecord(
        record_id=make_record_id(),
        timestamp_utc=now_utc_iso(),
        inputs=LLMInputParams(provider="claude_cli", workflow=workflow),
        outputs={},
        success=True,
        error=None,
    )


def test_71_a_record_that_cannot_be_written_alerts_and_raises(tmp_path, operator_alerts):
    store = CallStore(tmp_path)
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x", encoding="utf-8")
    store.base_dir = blocker  # every day file now sits under a regular file

    with pytest.raises(OSError):
        store.write(_record())

    assert len(operator_alerts) == 1
    assert "call record" in operator_alerts[0]["what"]
    assert "CallStore.write" in operator_alerts[0]["where"]


def test_88_a_corrupt_line_in_a_day_alerts_and_raises_naming_it(tmp_path, operator_alerts):
    store = CallStore(tmp_path)
    day = datetime.date(2026, 10, 30)
    path = store._day_path(day)
    path.write_bytes(orjson.dumps(_record()) + b"\n{not json\n")

    with pytest.raises(ValueError) as excinfo:
        store.read_day(day)

    assert f"{path}:2" in str(excinfo.value)
    assert len(operator_alerts) == 1


def test_114_a_store_file_with_no_date_in_its_name_alerts_and_raises(tmp_path, operator_alerts):
    store = CallStore(tmp_path)
    stray = tmp_path / "calls-backup.jsonl"
    stray.write_bytes(orjson.dumps(_record()) + b"\n")

    with pytest.raises(ValueError) as excinfo:
        store.query()

    assert str(stray) in str(excinfo.value)
    assert len(operator_alerts) == 1


def test_127_a_corrupt_line_in_a_query_alerts_and_raises_naming_it(tmp_path, operator_alerts):
    store = CallStore(tmp_path)
    path = store._day_path(datetime.date(2026, 10, 30))
    path.write_bytes(b"{not json\n" + orjson.dumps(_record()) + b"\n")

    with pytest.raises(ValueError) as excinfo:
        store.query(workflow="lld")

    assert f"{path}:1" in str(excinfo.value)
    assert len(operator_alerts) == 1


def test_a_disabled_store_writes_nothing_quietly(tmp_path, operator_alerts):
    store = CallStore(tmp_path / "off", enabled=False)
    store.write(_record())
    assert not (tmp_path / "off").exists()
    assert operator_alerts == []


def test_a_day_with_no_file_is_a_quiet_empty_answer(tmp_path, operator_alerts):
    assert CallStore(tmp_path).read_day(datetime.date(2026, 1, 1)) == []
    assert operator_alerts == []


def test_written_records_read_back_and_query(tmp_path, operator_alerts):
    store = CallStore(tmp_path)
    store.write(_record("lld"))
    store.write(_record("impl"))

    assert len(store.query()) == 2
    assert len(store.query(workflow="lld")) == 1
    assert operator_alerts == []
