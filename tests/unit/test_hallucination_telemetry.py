"""Hallucination-event telemetry (#1812).

Pins the record-only contract: the instrument measures invented-API calls
in both the spec draft and the LLD, writes structured events to both
sinks, and can never — under any failure — alter the completeness gate's
verdict. Clean runs still write events, and "detector could not run" is
recorded as ``skipped``, never as silence.

Issue: #1812
"""

import json
from datetime import datetime

import pytest

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    detect_unknown_method_calls,
    validate_completeness,
)
from assemblyzero.workflows.telemetry.hallucination_log import (
    AUDIT_SUFFIX,
    JSONL_RELATIVE_PATH,
    build_hallucination_event,
    record_hallucination_event,
)

# A method name no allowlist or repo will ever contain.
FAKE_CALL = "frobnicate_the_widget"

KNOWN_SYMBOLS = ["to_dict", "from_dict", "Question"]

# Long enough to clear the node's empty-draft guard (>= 100 chars).
_FILLER = "This spec describes the change in enough detail to validate. " * 3

CLEAN_SPEC = (
    "# Implementation Spec\n\n" + _FILLER + "\n"
    "```python\nresult = question.to_dict()\n```\n"
)
HALLUCINATED_SPEC = (
    "# Implementation Spec\n\n" + _FILLER + "\n"
    f"```python\nresult = question.{FAKE_CALL}()\n```\n"
)
CLEAN_LLD = "# LLD\n\n```python\nobj = Question.from_dict(data)\n```\n"
HALLUCINATED_LLD = f"# LLD\n\n```python\nobj = question.{FAKE_CALL}()\n```\n"


def _read_jsonl(az_root):
    path = az_root / JSONL_RELATIVE_PATH
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.fixture
def state(tmp_path):
    """Minimal node state with live audit + JSONL sinks under tmp_path."""
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    return {
        "issue_number": 42,
        "lld_content": HALLUCINATED_LLD,
        "files_to_modify": [],
        "pattern_references": [],
        "spec_draft": CLEAN_SPEC,
        "gathered_symbols": list(KNOWN_SYMBOLS),
        "review_iteration": 0,
        "repo_root": str(tmp_path),
        "assemblyzero_root": str(tmp_path),
        "audit_dir": str(audit_dir),
        "error_message": "",
    }


# =============================================================================
# The event builder — pure
# =============================================================================


class TestBuildEvent:

    def test_flagged_event_fields(self):
        event = build_hallucination_event(
            repo="/r", issue=7, artifact="lld", iteration=2,
            symbols_checked=447,
            flagged={FAKE_CALL: [f"question.{FAKE_CALL}()"]},
        )
        assert event["stage"] == "spec"
        assert event["artifact"] == "lld"
        assert event["iteration"] == 2
        assert event["symbols_checked"] == 447
        assert event["passed"] is False
        assert event["skipped"] is False
        # Timestamp must parse as ISO-8601
        datetime.fromisoformat(event["ts"])

    def test_clean_event_passes(self):
        event = build_hallucination_event(
            repo="/r", issue=7, artifact="spec_draft", iteration=0,
            symbols_checked=10, flagged={},
        )
        assert event["passed"] is True

    def test_skipped_event_is_not_a_clean_event(self):
        """'Not checked' must be distinguishable from 'checked, clean'."""
        event = build_hallucination_event(
            repo="/r", issue=7, artifact="spec_draft", iteration=0,
            symbols_checked=0, flagged={}, skipped=True,
        )
        assert event["skipped"] is True
        assert event["passed"] is True  # nothing flagged — but skipped says why


# =============================================================================
# The sinks — guarded
# =============================================================================


class TestRecordEvent:

    def _event(self):
        return build_hallucination_event(
            repo="/r", issue=7, artifact="lld", iteration=0,
            symbols_checked=3, flagged={},
        )

    def test_writes_numbered_audit_file(self, tmp_path):
        audit = tmp_path / "audit"
        audit.mkdir()
        record_hallucination_event(self._event(), audit, None)
        files = list(audit.glob(f"*-{AUDIT_SUFFIX}"))
        assert len(files) == 1
        assert files[0].name.startswith("001-")
        assert json.loads(files[0].read_text(encoding="utf-8"))["issue"] == 7

    def test_appends_jsonl_creating_directories(self, tmp_path):
        record_hallucination_event(self._event(), None, tmp_path)
        record_hallucination_event(self._event(), None, tmp_path)
        events = _read_jsonl(tmp_path)
        assert len(events) == 2

    def test_missing_audit_dir_skips_that_sink_without_error(self, tmp_path):
        record_hallucination_event(
            self._event(), tmp_path / "does-not-exist", tmp_path
        )
        assert len(_read_jsonl(tmp_path)) == 1

    def test_sink_failure_is_swallowed(self, tmp_path, capsys):
        """A broken sink degrades to a warning — never an exception."""
        # data/ as a FILE makes the JSONL sink's mkdir raise.
        (tmp_path / "data").write_text("in the way", encoding="utf-8")
        audit = tmp_path / "audit"
        audit.mkdir()
        record_hallucination_event(self._event(), audit, tmp_path)
        assert "WARNING" in capsys.readouterr().out
        # The other sink still wrote.
        assert len(list(audit.glob(f"*-{AUDIT_SUFFIX}"))) == 1


# =============================================================================
# The shared detector
# =============================================================================


class TestDetectUnknownMethodCalls:

    def test_flags_unknown_call_in_code_fence(self):
        flagged = detect_unknown_method_calls(
            HALLUCINATED_SPEC, set(KNOWN_SYMBOLS)
        )
        assert FAKE_CALL in flagged
        assert FAKE_CALL in flagged[FAKE_CALL][0]

    def test_known_symbol_not_flagged(self):
        assert detect_unknown_method_calls(CLEAN_SPEC, set(KNOWN_SYMBOLS)) == {}

    def test_allowlisted_builtin_not_flagged(self):
        text = "```python\nitems.append(1)\nname.strip()\n```\n"
        assert detect_unknown_method_calls(text, {"unrelated"}) == {}

    def test_prose_outside_fences_ignored(self):
        text = f"The design calls question.{FAKE_CALL}() in prose only.\n"
        assert detect_unknown_method_calls(text, set(KNOWN_SYMBOLS)) == {}


# =============================================================================
# Node integration — the record-only contract
# =============================================================================


class TestNodeTelemetry:

    def test_first_pass_records_lld_then_spec(self, state, tmp_path):
        validate_completeness(state)
        events = _read_jsonl(tmp_path)
        assert [e["artifact"] for e in events] == ["lld", "spec_draft"]
        assert all(e["issue"] == 42 and e["iteration"] == 0 for e in events)
        # Both events also archived beside the run.
        audit_files = list((tmp_path / "audit").glob(f"*-{AUDIT_SUFFIX}"))
        assert len(audit_files) == 2

    def test_revision_pass_records_spec_only(self, state, tmp_path):
        state["review_iteration"] = 1
        validate_completeness(state)
        events = _read_jsonl(tmp_path)
        assert [e["artifact"] for e in events] == ["spec_draft"]
        assert events[0]["iteration"] == 1

    def test_clean_run_still_writes_events(self, state, tmp_path):
        """Absence of evidence must not look like absence of instrumentation."""
        state["lld_content"] = CLEAN_LLD
        validate_completeness(state)
        events = _read_jsonl(tmp_path)
        assert len(events) == 2
        assert all(e["passed"] is True and e["skipped"] is False for e in events)

    def test_no_gathered_symbols_records_skipped(self, state, tmp_path):
        state["gathered_symbols"] = []
        validate_completeness(state)
        events = _read_jsonl(tmp_path)
        assert len(events) == 2
        assert all(e["skipped"] is True and e["symbols_checked"] == 0 for e in events)

    def test_lld_hallucinations_never_affect_the_gate(self, state, tmp_path):
        """The money test: LLD detection records, the gate ignores it."""
        dirty = validate_completeness(dict(state))

        clean_state = dict(state)
        clean_state["lld_content"] = CLEAN_LLD
        clean = validate_completeness(clean_state)

        # Identical gating outcome regardless of LLD contents...
        assert dirty["validation_passed"] == clean["validation_passed"]
        assert dirty["completeness_issues"] == clean["completeness_issues"]
        # ...while the telemetry saw the difference.
        lld_events = [e for e in _read_jsonl(tmp_path) if e["artifact"] == "lld"]
        assert [e["passed"] for e in lld_events] == [False, True]

    def test_telemetry_failure_cannot_change_the_verdict(
        self, state, tmp_path, monkeypatch, capsys
    ):
        baseline = validate_completeness(dict(state))

        # The nodes package re-exports the function under the module's own
        # name, so `import ... as vc` would grab the function. sys.modules
        # is unambiguous.
        import sys

        vc = sys.modules[
            "assemblyzero.workflows.implementation_spec.nodes.validate_completeness"
        ]

        def boom(*args, **kwargs):
            raise RuntimeError("telemetry sink exploded")

        monkeypatch.setattr(vc, "record_hallucination_event", boom)
        result = validate_completeness(dict(state))

        assert result["validation_passed"] == baseline["validation_passed"]
        assert result["completeness_issues"] == baseline["completeness_issues"]
        assert "telemetry" in capsys.readouterr().out.lower()
