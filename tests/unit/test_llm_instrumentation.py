"""Unit tests for LLM call instrumentation.

Issue #774: Tests for record construction, store writes, instrumentation context manager.
"""

import datetime
import json
import logging
import threading
from pathlib import Path
from unittest.mock import patch

import orjson
import pytest

from assemblyzero.telemetry.llm_call_record import (
    LLMCallRecord,
    LLMInputParams,
    LLMOutputMetadata,
    make_record_id,
    now_utc_iso,
)
from assemblyzero.telemetry.instrumentation import InstrumentedCall
from assemblyzero.telemetry.store import CallStore
from assemblyzero.telemetry.cost import estimate_cost


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def tmp_store(tmp_path: Path) -> CallStore:
    """Create a CallStore backed by tmp_path."""
    return CallStore(base_dir=tmp_path, enabled=True)


@pytest.fixture
def disabled_store(tmp_path: Path) -> CallStore:
    """Create a disabled CallStore."""
    return CallStore(base_dir=tmp_path, enabled=False)


@pytest.fixture
def sample_inputs() -> LLMInputParams:
    return LLMInputParams(
        provider="claude_cli",
        model_requested="claude:opus",
        effort_level="high",
        max_budget_usd=5.0,
        workflow="implementation",
        node="coder_node",
        issue_number=774,
        system_prompt_len=2340,
        user_prompt_len=18450,
        temperature=None,
        max_tokens=16384,
    )


@pytest.fixture
def sample_outputs() -> LLMOutputMetadata:
    return LLMOutputMetadata(
        model_used="claude-opus-4-5-20250514",
        input_tokens=12450,
        output_tokens=3200,
        thinking_tokens=8500,
        cache_read_tokens=4000,
        cache_write_tokens=1200,
        stop_reason="end_turn",
    )


@pytest.fixture
def claude_cli_fixture() -> dict:
    fixture_path = Path(__file__).parent.parent / "fixtures" / "llm_instrumentation" / "claude_cli_response.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def anthropic_api_fixture() -> dict:
    fixture_path = Path(__file__).parent.parent / "fixtures" / "llm_instrumentation" / "anthropic_api_response.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def gemini_fixture() -> dict:
    fixture_path = Path(__file__).parent.parent / "fixtures" / "llm_instrumentation" / "gemini_response.json"
    with open(fixture_path) as f:
        return json.load(f)


# ── T010: Full record construction ───────────────────────────────────


class TestRecordConstruction:
    """T010: Build LLMCallRecord with all input and output fields."""

    def test_full_record_serializes_roundtrip(
        self, sample_inputs: LLMInputParams, sample_outputs: LLMOutputMetadata
    ):
        record = LLMCallRecord(
            record_id=make_record_id(),
            timestamp_utc=now_utc_iso(),
            inputs=sample_inputs,
            outputs=sample_outputs,
            success=True,
            error=None,
        )
        raw = orjson.dumps(record)
        restored = orjson.loads(raw)

        assert restored["record_id"] == record["record_id"]
        assert restored["timestamp_utc"] == record["timestamp_utc"]
        assert restored["inputs"]["provider"] == "claude_cli"
        assert restored["inputs"]["model_requested"] == "claude:opus"
        assert restored["inputs"]["effort_level"] == "high"
        assert restored["inputs"]["workflow"] == "implementation"
        assert restored["inputs"]["node"] == "coder_node"
        assert restored["inputs"]["issue_number"] == 774
        assert restored["inputs"]["system_prompt_len"] == 2340
        assert restored["inputs"]["user_prompt_len"] == 18450
        assert restored["outputs"]["model_used"] == "claude-opus-4-5-20250514"
        assert restored["outputs"]["input_tokens"] == 12450
        assert restored["outputs"]["output_tokens"] == 3200
        assert restored["outputs"]["thinking_tokens"] == 8500
        assert restored["outputs"]["cache_read_tokens"] == 4000
        assert restored["outputs"]["cache_write_tokens"] == 1200
        assert restored["outputs"]["stop_reason"] == "end_turn"
        assert restored["success"] is True
        assert restored["error"] is None

    def test_record_id_is_uuid4(self):
        rid = make_record_id()
        assert len(rid) == 36
        assert rid.count("-") == 4

    def test_timestamp_is_iso8601(self):
        ts = now_utc_iso()
        assert ts.endswith("Z")
        datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))


# ── T020: Input parameters captured ──────────────────────────────────


class TestInputCapture:
    """T020: InstrumentedCall captures all input parameters."""

    def test_all_input_fields_recorded(
        self,
        tmp_store: CallStore,
        sample_inputs: LLMInputParams,
        sample_outputs: LLMOutputMetadata,
    ):
        with InstrumentedCall(tmp_store, sample_inputs) as ic:
            ic.record_outputs(sample_outputs)

        records = tmp_store.read_day(datetime.date.today())
        assert len(records) == 1
        r = records[0]

        assert r["inputs"]["provider"] == "claude_cli"
        assert r["inputs"]["model_requested"] == "claude:opus"
        assert r["inputs"]["effort_level"] == "high"
        assert r["inputs"]["max_budget_usd"] == 5.0
        assert r["inputs"]["workflow"] == "implementation"
        assert r["inputs"]["node"] == "coder_node"
        assert r["inputs"]["issue_number"] == 774
        assert r["inputs"]["system_prompt_len"] == 2340
        assert r["inputs"]["user_prompt_len"] == 18450
        assert r["inputs"]["max_tokens"] == 16384


# ── T030: Output metadata captured ───────────────────────────────────


class TestOutputCapture:
    """T030: InstrumentedCall captures all output metadata."""

    def test_all_output_fields_recorded(
        self,
        tmp_store: CallStore,
        sample_inputs: LLMInputParams,
        sample_outputs: LLMOutputMetadata,
    ):
        with InstrumentedCall(tmp_store, sample_inputs) as ic:
            ic.record_outputs(sample_outputs)

        records = tmp_store.read_day(datetime.date.today())
        assert len(records) == 1
        r = records[0]

        assert r["outputs"]["model_used"] == "claude-opus-4-5-20250514"
        assert r["outputs"]["input_tokens"] == 12450
        assert r["outputs"]["output_tokens"] == 3200
        assert r["outputs"]["thinking_tokens"] == 8500
        assert r["outputs"]["cache_read_tokens"] == 4000
        assert r["outputs"]["cache_write_tokens"] == 1200
        assert r["outputs"]["stop_reason"] == "end_turn"
        assert r["outputs"]["latency_ms"] >= 0
        assert r["outputs"]["cost_usd_estimate"] >= 0
        assert r["success"] is True


# ── T040: Exception handling ─────────────────────────────────────────


class TestExceptionHandling:
    """T040: Failed call record written with success=False."""

    def test_exception_records_failure(
        self, tmp_store: CallStore, sample_inputs: LLMInputParams
    ):
        with pytest.raises(RuntimeError, match="upstream timeout"):
            with InstrumentedCall(tmp_store, sample_inputs) as ic:
                raise RuntimeError("upstream timeout")

        records = tmp_store.read_day(datetime.date.today())
        assert len(records) == 1
        r = records[0]
        assert r["success"] is False
        assert "RuntimeError" in r["error"]
        assert "upstream timeout" in r["error"]
        assert r["outputs"]["latency_ms"] >= 0


# ── T050: Store creates file ─────────────────────────────────────────


class TestStoreCreation:
    """T050: store.write() creates file if absent."""

    def test_creates_file_on_first_write(self, tmp_path: Path, sample_inputs: LLMInputParams):
        new_dir = tmp_path / "new_telemetry_dir"
        store = CallStore(base_dir=new_dir, enabled=True)

        record = LLMCallRecord(
            record_id=make_record_id(),
            timestamp_utc=now_utc_iso(),
            inputs=sample_inputs,
            outputs={},
            success=True,
            error=None,
        )
        store.write(record)

        today = datetime.date.today()
        path = new_dir / f"calls-{today.isoformat()}.jsonl"
        assert path.exists()

        lines = path.read_bytes().strip().split(b"\n")
        assert len(lines) == 1

    def test_directory_permissions(self, tmp_path: Path):
        import os
        import sys

        new_dir = tmp_path / "restricted_dir"
        store = CallStore(base_dir=new_dir, enabled=True)

        if sys.platform != "win32":
            stat = os.stat(new_dir)
            assert stat.st_mode & 0o777 == 0o700


# ── T060: Store append semantics ─────────────────────────────────────


class TestStoreAppend:
    """T060: store.write() appends to existing file."""

    def test_two_writes_two_lines(self, tmp_store: CallStore, sample_inputs: LLMInputParams):
        for i in range(2):
            record = LLMCallRecord(
                record_id=make_record_id(),
                timestamp_utc=now_utc_iso(),
                inputs=sample_inputs,
                outputs={},
                success=True,
                error=None,
            )
            tmp_store.write(record)

        records = tmp_store.read_day(datetime.date.today())
        assert len(records) == 2
        assert records[0]["record_id"] != records[1]["record_id"]


# ── T070: Disabled store ─────────────────────────────────────────────


class TestDisabledStore:
    """T070: store.enabled=False -> no file I/O."""

    def test_no_files_created(self, disabled_store: CallStore, tmp_path: Path, sample_inputs: LLMInputParams):
        record = LLMCallRecord(
            record_id=make_record_id(),
            timestamp_utc=now_utc_iso(),
            inputs=sample_inputs,
            outputs={},
            success=True,
            error=None,
        )
        disabled_store.write(record)

        jsonl_files = list(tmp_path.rglob("*.jsonl"))
        assert len(jsonl_files) == 0


# ── T110: Claude CLI parser ──────────────────────────────────────────


class TestClaudeCLIParser:
    """T110: _parse_usage_from_cli_output fixture."""

    def test_extracts_all_fields(self, claude_cli_fixture: dict):
        from assemblyzero.core.claude_client import _parse_usage_from_cli_output

        result = _parse_usage_from_cli_output(claude_cli_fixture)

        assert result["model_used"] == "claude-opus-4-5-20250514"
        assert result["input_tokens"] == 12450
        assert result["output_tokens"] == 3200
        assert result["thinking_tokens"] == 8500
        assert result["cache_read_tokens"] == 4000
        assert result["cache_write_tokens"] == 1200
        assert result["stop_reason"] == "end_turn"

    def test_missing_usage_returns_none_fields(self):
        from assemblyzero.core.claude_client import _parse_usage_from_cli_output

        result = _parse_usage_from_cli_output({"model": "test-model"})
        assert result["model_used"] == "test-model"
        assert result.get("input_tokens") is None
        assert result.get("output_tokens") is None


# ── T120: Anthropic API parser ───────────────────────────────────────


class TestAnthropicAPIParser:
    """T120: _parse_usage_from_message fixture."""

    def test_extracts_usage_block(self, anthropic_api_fixture: dict):
        from assemblyzero.nodes.anthropic_provider import _parse_usage_from_message

        result = _parse_usage_from_message(anthropic_api_fixture)

        assert result["model_used"] == "claude-sonnet-4-6-20250514"
        assert result["input_tokens"] == 2095
        assert result["output_tokens"] == 503
        assert result["cache_read_tokens"] == 1800
        assert result["cache_write_tokens"] == 0
        assert result["stop_reason"] == "end_turn"


# ── T130: Gemini parser ──────────────────────────────────────────────


class TestGeminiParser:
    """T130: _parse_usage_from_gemini_response fixture."""

    def test_extracts_usage_metadata(self, gemini_fixture: dict):
        from assemblyzero.core.gemini_client import _parse_usage_from_gemini_response

        result = _parse_usage_from_gemini_response(gemini_fixture)

        assert result["model_used"] == "gemini-2.5-pro-preview-05-06"
        assert result["input_tokens"] == 1250
        assert result["output_tokens"] == 680

    def test_missing_usage_metadata(self):
        from assemblyzero.core.gemini_client import _parse_usage_from_gemini_response

        result = _parse_usage_from_gemini_response({})
        assert result["model_used"] == "gemini-unknown"
        assert result.get("input_tokens") is None


# ── T140: read_day round-trip ─────────────────────────────────────────


class TestReadDayRoundTrip:
    """T140: read_day round-trip preserves all record fields."""

    def test_write_read_preserves_fields(self, tmp_store: CallStore, sample_inputs: LLMInputParams, sample_outputs: LLMOutputMetadata):
        written_ids = []
        for _ in range(5):
            record = LLMCallRecord(
                record_id=make_record_id(),
                timestamp_utc=now_utc_iso(),
                inputs=sample_inputs,
                outputs=sample_outputs,
                success=True,
                error=None,
            )
            written_ids.append(record["record_id"])
            tmp_store.write(record)

        read_back = tmp_store.read_day(datetime.date.today())
        assert len(read_back) == 5
        read_ids = [r["record_id"] for r in read_back]
        assert read_ids == written_ids

        for r in read_back:
            assert r["inputs"]["provider"] == "claude_cli"
            assert r["outputs"]["model_used"] == "claude-opus-4-5-20250514"


# ── T150: query by workflow ──────────────────────────────────────────


class TestQueryFilter:
    """T150: query() filter by workflow returns only matching records."""

    def test_filter_by_workflow(self, tmp_store: CallStore):
        for wf, count in [("tdd", 3), ("requirements", 2)]:
            for _ in range(count):
                record = LLMCallRecord(
                    record_id=make_record_id(),
                    timestamp_utc=now_utc_iso(),
                    inputs=LLMInputParams(provider="claude_cli", workflow=wf),
                    outputs={},
                    success=True,
                    error=None,
                )
                tmp_store.write(record)

        results = tmp_store.query(workflow="tdd")
        assert len(results) == 3
        assert all(r["inputs"]["workflow"] == "tdd" for r in results)


# ── T160: Concurrent writes ──────────────────────────────────────────


class TestConcurrentWrites:
    """T160: Concurrent writes produce correct line count without corruption."""

    def test_thread_safety(self, tmp_store: CallStore):
        errors: list[Exception] = []

        def write_records(n: int):
            try:
                for _ in range(n):
                    record = LLMCallRecord(
                        record_id=make_record_id(),
                        timestamp_utc=now_utc_iso(),
                        inputs=LLMInputParams(provider="claude_cli"),
                        outputs={},
                        success=True,
                        error=None,
                    )
                    tmp_store.write(record)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_records, args=(10,)) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"

        records = tmp_store.read_day(datetime.date.today())
        assert len(records) == 100

        path = tmp_store._day_path(datetime.date.today())
        with open(path, "rb") as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 100
        for line in lines:
            orjson.loads(line)


# ── T170: Write failure is non-fatal ─────────────────────────────────


class TestWriteFailure:
    """T170: Write failure is non-fatal; warning logged."""

    def test_oserror_does_not_propagate(self, tmp_store: CallStore, caplog):
        record = LLMCallRecord(
            record_id=make_record_id(),
            timestamp_utc=now_utc_iso(),
            inputs=LLMInputParams(provider="claude_cli"),
            outputs={},
            success=True,
            error=None,
        )

        with patch("builtins.open", side_effect=OSError("disk full")):
            with caplog.at_level(logging.WARNING):
                tmp_store.write(record)

        assert "Failed to write telemetry record" in caplog.text