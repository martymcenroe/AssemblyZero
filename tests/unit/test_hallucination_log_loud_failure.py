"""The hallucination-event log fails loudly (ADR 0236, #3585).

The log is the baseline every invented-API detection is measured against. An
audit directory that was given but does not exist was skipped silently, and a
sink that could not be written printed a WARNING to stdout and went on, so the
baseline lost events with nothing said. Now each sink failure alerts the
operator, both sinks are still attempted, and the first failure is raised.

``None`` for a sink still means "no such sink for this run" and stays quiet.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import json

import pytest

# Imported first, as a run does: a cold import of the telemetry package goes
# hallucination_log -> requirements.audit -> ... -> validate_completeness ->
# the half-initialised telemetry package (a circular import; reported, not
# fixed here).
import assemblyzero.workflows.implementation_spec.nodes.validate_completeness  # noqa: F401
from assemblyzero.workflows.telemetry.hallucination_log import (
    AUDIT_SUFFIX,
    JSONL_RELATIVE_PATH,
    build_hallucination_event,
    record_hallucination_event,
)


def _event():
    return build_hallucination_event(
        repo="/r", issue=7, artifact="lld", iteration=0,
        symbols_checked=3, flagged={},
    )


def _jsonl(root):
    path = root / JSONL_RELATIVE_PATH
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_105_an_audit_dir_that_was_given_but_is_missing_alerts_and_raises(tmp_path, operator_alerts):
    missing = tmp_path / "does-not-exist"

    with pytest.raises(FileNotFoundError) as excinfo:
        record_hallucination_event(_event(), missing, tmp_path)

    assert str(missing) in str(excinfo.value)
    assert len(operator_alerts) == 1
    assert "audit" in operator_alerts[0]["what"]
    assert operator_alerts[0]["issue"] == 7
    assert len(_jsonl(tmp_path)) == 1, "the other sink is still written"


def test_114_an_audit_sink_that_cannot_be_written_alerts_and_raises(tmp_path, monkeypatch, operator_alerts):
    from assemblyzero.workflows.telemetry import hallucination_log

    def _refuse(*_args, **_kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(hallucination_log, "save_audit_file", _refuse)
    audit = tmp_path / "audit"
    audit.mkdir()

    with pytest.raises(PermissionError):
        record_hallucination_event(_event(), audit, tmp_path)

    assert len(operator_alerts) == 1
    assert "PermissionError" in operator_alerts[0]["cause"]
    assert len(_jsonl(tmp_path)) == 1, "the other sink is still written"


def test_123_a_jsonl_sink_that_cannot_be_written_alerts_and_raises(tmp_path, operator_alerts):
    (tmp_path / "data").write_text("in the way", encoding="utf-8")
    audit = tmp_path / "audit"
    audit.mkdir()

    with pytest.raises(OSError):
        record_hallucination_event(_event(), audit, tmp_path)

    assert len(operator_alerts) == 1
    assert "JSONL" in operator_alerts[0]["what"]
    assert len(list(audit.glob(f"*-{AUDIT_SUFFIX}"))) == 1, "the other sink is still written"


def test_both_sinks_failing_alerts_twice_and_raises_the_first(tmp_path, operator_alerts):
    (tmp_path / "data").write_text("in the way", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        record_hallucination_event(_event(), tmp_path / "missing", tmp_path)

    assert len(operator_alerts) == 2


def test_a_sink_given_as_none_is_quiet(tmp_path, operator_alerts):
    record_hallucination_event(_event(), None, None)
    record_hallucination_event(_event(), None, tmp_path)

    assert len(_jsonl(tmp_path)) == 1
    assert operator_alerts == []


def test_both_sinks_written_is_quiet(tmp_path, operator_alerts):
    audit = tmp_path / "audit"
    audit.mkdir()

    record_hallucination_event(_event(), audit, tmp_path)

    assert len(list(audit.glob(f"*-{AUDIT_SUFFIX}"))) == 1
    assert len(_jsonl(tmp_path)) == 1
    assert operator_alerts == []
