"""The convergence record fails loudly (ADR 0236, #3585).

A run record that cannot be appended used to return False, and every caller
ignored it, so the factory report quietly fell back to the banner for that run.
It now alerts the operator with the store path and the cause, and raises.

A line of the store that is not a record used to be counted, and the one
consumer (``factory_report.apply_records``) threw the count away, so the report
stated numbers from a store it had not fully read. ``read_records`` now alerts
and raises naming the store and the line, and returns only the records: the
count is gone with the partial read.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
The ``802`` test is factory_report's site that consumed the count; it is fixed
by the same change and pinned here.
"""

from __future__ import annotations

import json

import pytest

from assemblyzero.speedrun import convergence
from assemblyzero.speedrun.convergence import (
    read_records,
    record_node_enter,
    record_stage_enter,
    record_terminal,
    records_path,
)


def _blocked_root(tmp_path):
    (tmp_path / "data").write_text("not a directory", encoding="utf-8")
    return tmp_path


def _store(tmp_path, *lines: str):
    path = records_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for line in lines:
            fh.write(line + "\n")
    return path


def test_90_a_record_that_cannot_be_written_alerts_and_raises(tmp_path, operator_alerts):
    root = _blocked_root(tmp_path)

    with pytest.raises(OSError):
        record_node_enter(root, "lld", "N1_draft", 2, 9)

    assert len(operator_alerts) == 1
    alert = operator_alerts[0]
    assert "convergence record" in alert["what"]
    assert "_append" in alert["where"]
    assert str(records_path(root)) in alert["cause"]
    assert "node.enter" in alert["cause"]


@pytest.mark.parametrize(
    "write",
    [
        lambda root: record_stage_enter(root, "lld", 2, 7),
        lambda root: record_terminal(root, outcome="passed", furthest_stage="lld"),
    ],
    ids=["stage.enter", "run.terminal"],
)
def test_90_every_event_kind_alerts_and_raises(tmp_path, operator_alerts, write):
    with pytest.raises(OSError):
        write(_blocked_root(tmp_path))
    assert len(operator_alerts) == 1


def test_91_the_withdrawn_tag_is_gone():
    source = convergence.__loader__.get_source(convergence.__name__)
    assert "fail-open" not in source


def test_185_a_line_that_is_not_json_alerts_and_raises_naming_it(tmp_path, monkeypatch, operator_alerts):
    monkeypatch.setenv("SPEEDRUN_RUN_TAG", "run-1")
    record_stage_enter(tmp_path, "lld", 2, 7)
    path = _store(tmp_path, "{truncated")

    with pytest.raises(ValueError) as excinfo:
        read_records(tmp_path)

    assert f"{path}:2" in str(excinfo.value)
    assert len(operator_alerts) == 1
    assert f"{path}:2" in operator_alerts[0]["cause"]
    assert "read_records" in operator_alerts[0]["where"]


def test_186_the_withdrawn_tag_is_gone():
    source = convergence.__loader__.get_source(convergence.__name__)
    assert "# fail-open" not in source


@pytest.mark.parametrize(
    "line", [json.dumps({"event": "something.else"}), json.dumps([1])],
    ids=["unknown-event", "not-an-object"],
)
def test_195_a_line_that_is_not_a_record_alerts_and_raises(tmp_path, operator_alerts, line):
    path = _store(tmp_path, line)

    with pytest.raises(ValueError) as excinfo:
        read_records(tmp_path)

    assert f"{path}:1" in str(excinfo.value)
    assert len(operator_alerts) == 1


def test_802_the_report_does_not_build_from_a_partial_store(tmp_path, operator_alerts):
    from assemblyzero.speedrun.factory_report import apply_records

    _store(tmp_path, "{truncated")

    with pytest.raises(ValueError):
        apply_records([], tmp_path)


def test_a_clean_store_reads_with_no_alert(tmp_path, monkeypatch, operator_alerts):
    monkeypatch.setenv("SPEEDRUN_RUN_TAG", "run-1")
    record_stage_enter(tmp_path, "lld", 2, 7)

    records = read_records(tmp_path)

    assert [r["event"] for r in records] == ["stage.enter"]
    assert operator_alerts == []


def test_a_missing_store_is_a_quiet_empty_answer(tmp_path, operator_alerts):
    assert read_records(tmp_path) == []
    assert operator_alerts == []


def test_a_written_record_returns_true(tmp_path, operator_alerts):
    assert record_node_enter(tmp_path, "lld", "N1_draft", 2, 9) is True
    assert operator_alerts == []
