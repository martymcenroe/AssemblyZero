"""The requirements-unverified ledger fails loudly (ADR 0236, #3585).

The ledger exists so a roll whose requirements gate proceeded without a verdict
cannot read as a verified roll. A record that cannot be written, or a ledger line
that cannot be read, is exactly that misreading: the UNVERIFIED banner never
prints. So each one alerts the operator and raises; nothing returns False or
skips the line.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import json

import pytest

from assemblyzero.speedrun.requirements_status import (
    read_unverified,
    record_unverified,
    unverified_path,
)


def _ledger(tmp_path, text: str):
    path = unverified_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_65_a_record_that_cannot_be_written_alerts_and_raises(tmp_path, operator_alerts):
    (tmp_path / "data").write_text("not a directory", encoding="utf-8")

    with pytest.raises(OSError):
        record_unverified(tmp_path, issue=7, reason="analysis unavailable: timed out")

    assert len(operator_alerts) == 1
    alert = operator_alerts[0]
    assert "requirements-unverified" in alert["what"]
    assert "record_unverified" in alert["where"]
    assert "OSError" in alert["cause"] or "Error" in alert["cause"]
    assert "UNVERIFIED" in alert["consequence"]
    assert alert["issue"] == 7


def test_65_an_issue_that_is_not_a_number_alerts_and_raises(tmp_path, operator_alerts):
    with pytest.raises(ValueError):
        record_unverified(tmp_path, issue="seven", reason="x")  # type: ignore[arg-type]

    assert len(operator_alerts) == 1
    assert "ValueError" in operator_alerts[0]["cause"]
    assert not unverified_path(tmp_path).exists()


def test_65_a_written_record_still_reads_back(tmp_path, operator_alerts):
    record_unverified(tmp_path, issue=7, reason="analysis unavailable: timed out")

    records = read_unverified(tmp_path)

    assert [r["issue"] for r in records] == [7]
    assert operator_alerts == []


def test_88_a_corrupt_line_alerts_and_raises_naming_the_line(tmp_path, operator_alerts):
    good = json.dumps({"ts": "2026-08-13 00:00:00", "issue": 7, "reason": "r"})
    path = _ledger(tmp_path, good + "\n{truncated\n")

    with pytest.raises(ValueError) as excinfo:
        read_unverified(tmp_path)

    assert f"{path}:2" in str(excinfo.value)
    assert len(operator_alerts) == 1
    assert f"{path}:2" in operator_alerts[0]["cause"]
    assert "read_unverified" in operator_alerts[0]["where"]


def test_90_a_line_that_is_not_an_object_alerts_and_raises(tmp_path, operator_alerts):
    path = _ledger(tmp_path, "[1, 2]\n")

    with pytest.raises(ValueError) as excinfo:
        read_unverified(tmp_path)

    assert f"{path}:1" in str(excinfo.value)
    assert "not a JSON object" in str(excinfo.value)
    assert len(operator_alerts) == 1


def test_an_absent_ledger_is_a_legitimate_empty_answer(tmp_path, operator_alerts):
    """No ledger means no run proceeded without a verdict: quiet, by contract."""
    assert read_unverified(tmp_path) == []
    assert operator_alerts == []


def test_blank_lines_are_not_corruption(tmp_path, operator_alerts):
    good = json.dumps({"ts": "2026-08-13 00:00:00", "issue": 7, "reason": "r"})
    _ledger(tmp_path, "\n" + good + "\n\n")

    assert [r["issue"] for r in read_unverified(tmp_path)] == [7]
    assert operator_alerts == []
