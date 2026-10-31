"""Prompt-failure telemetry fails loudly (ADR 0236, #3585).

This store is where the rate of every drafter validation failure is computed.
A failure with an empty detail used to be dropped, a write that failed was
printed to stdout and dropped, a store that could not be read read as "no
failures", and a corrupt line was skipped uncounted: each one made the rate
lower than it was. Now an empty detail is recorded under an explicit
fingerprint, and the write and read failures alert the operator and raise.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import json

import pytest

from assemblyzero.speedrun.prompt_telemetry import (
    read_failures,
    record_failure,
    telemetry_path,
)


def test_130_a_failure_with_an_empty_detail_is_still_counted(tmp_path, operator_alerts):
    record = record_failure(tmp_path, stage="lld", check="mechanical", detail="   ")

    assert record is not None
    assert record.fingerprint == "lld:mechanical:empty-detail"
    rows = read_failures(tmp_path)
    assert [r["fingerprint"] for r in rows] == ["lld:mechanical:empty-detail"]
    assert rows[0]["detail_raw"] == "   "


def test_152_a_write_that_fails_alerts_and_raises(tmp_path, operator_alerts):
    blocker = tmp_path / "data" / "speedrun"
    blocker.parent.mkdir(parents=True)
    blocker.write_text("not a directory\n", encoding="utf-8")

    with pytest.raises(OSError):
        record_failure(tmp_path, stage="lld", check="mechanical", detail="table malformed", issue=4)

    assert len(operator_alerts) == 1
    alert = operator_alerts[0]
    assert "prompt-failure" in alert["what"]
    assert "record_failure" in alert["where"]
    assert "lld:mechanical:table-malformed" in alert["cause"]
    assert alert["issue"] == 4


def test_180_a_store_that_exists_but_cannot_be_read_alerts_and_raises(tmp_path, operator_alerts):
    path = telemetry_path(tmp_path)
    path.mkdir(parents=True)  # a directory where the file must be

    with pytest.raises(OSError):
        read_failures(tmp_path)

    assert len(operator_alerts) == 1
    assert str(path) in operator_alerts[0]["cause"]


def test_188_a_corrupt_line_alerts_and_raises_naming_it(tmp_path, operator_alerts):
    path = telemetry_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"ts_local": "2026-08-01 10:00:00", "fingerprint": "ok"}) + "\n"
        "{ this is not json\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as excinfo:
        read_failures(tmp_path)

    assert f"{path}:2" in str(excinfo.value)
    assert len(operator_alerts) == 1


def test_188_a_line_that_is_not_an_object_alerts_and_raises(tmp_path, operator_alerts):
    path = telemetry_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("[1, 2]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not a JSON object"):
        read_failures(tmp_path)


def test_an_absent_store_is_a_quiet_empty_answer(tmp_path, operator_alerts):
    assert read_failures(tmp_path) == []
    assert operator_alerts == []


def test_a_written_failure_reads_back(tmp_path, operator_alerts):
    record_failure(tmp_path, stage="lld", check="mechanical", detail="table malformed")

    assert [r["fingerprint"] for r in read_failures(tmp_path)] == ["lld:mechanical:table-malformed"]
    assert operator_alerts == []
