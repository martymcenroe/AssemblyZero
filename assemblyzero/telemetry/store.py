"""Append-only JSONL store for LLM call records.

Issue #774: Thread-safe JSONL writer with query helpers.

A record that cannot be written, a line that cannot be read, and a store file
whose name holds no date each alert the operator and raise (ADR 0236, #3585).
They used to be logged at WARNING or skipped, so the store held, or a reader
returned, fewer records than the calls made.
"""

import datetime
import logging
import threading
from pathlib import Path
from typing import Optional

import orjson

from assemblyzero.core import alert
from assemblyzero.telemetry.llm_call_record import LLMCallRecord

logger = logging.getLogger(__name__)

_FILE_SIZE_WARNING_BYTES = 100 * 1024 * 1024  # 100MB


def _unreadable(path: Path, cause: str, where: str) -> ValueError:
    """Alert on a store file or line that cannot be read; return the error."""
    alert.alert_operator(
        what="read the LLM call-record store",
        where=f"assemblyzero/telemetry/store.py {where}",
        cause=cause,
        consequence=(
            f"the store at {path.parent} cannot be read in full, so no partial "
            f"list of call records is returned"
        ),
    )
    return ValueError(cause)


class CallStore:
    """Append-only JSONL store for LLMCallRecord instances."""

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        *,
        enabled: bool = True,
    ) -> None:
        """Initialize the store.

        Args:
            base_dir: Directory for JSONL files. Defaults to ~/.assemblyzero/telemetry/
            enabled: If False, write() is a no-op (for tests / --no-telemetry flag).
        """
        self.enabled = enabled
        self.base_dir = base_dir or Path.home() / ".assemblyzero" / "telemetry"
        self._locks: dict[str, threading.Lock] = {}
        self._locks_lock = threading.Lock()

        if self.enabled:
            self.base_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    def write(self, record: LLMCallRecord) -> None:
        """Append record to today's JSONL file. Thread-safe via file lock.

        A disabled store writes nothing. A record that cannot be written
        alerts the operator with the path and the cause, and raises (#3585);
        it used to be a WARNING and the record was lost.
        """
        if not self.enabled:
            return

        path: Path | None = None
        try:
            today = datetime.date.today()
            path = self._day_path(today)
            lock = self._get_lock(str(path))

            # Check file size
            if path.exists() and path.stat().st_size > _FILE_SIZE_WARNING_BYTES:
                logger.warning(
                    "Telemetry file %s exceeds 100MB (%d bytes)",
                    path,
                    path.stat().st_size,
                )

            data = orjson.dumps(record) + b"\n"

            with lock:
                with open(path, "ab") as f:
                    f.write(data)

        except Exception as exc:
            alert.alert_operator(
                what="write an LLM call record",
                where="assemblyzero/telemetry/store.py CallStore.write",
                cause=f"{type(exc).__name__}: {exc} ({path or self.base_dir})",
                consequence=(
                    f"call record {record.get('record_id', '')} is not in the "
                    f"store; the write is raised"
                ),
            )
            raise

    def read_day(self, date: datetime.date) -> list[LLMCallRecord]:
        """Read all records for a given date.

        Returns [] when the day has no file. A corrupt line alerts the
        operator and raises ``ValueError`` naming the file and the line.
        """
        path = self._day_path(date)
        if not path.exists():
            return []

        records: list[LLMCallRecord] = []
        with open(path, "rb") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(orjson.loads(line))
                except orjson.JSONDecodeError as exc:
                    raise _unreadable(
                        path, f"{path}:{line_num}: not JSON ({exc})", "CallStore.read_day"
                    ) from exc
        return records

    def query(
        self,
        *,
        workflow: Optional[str] = None,
        model: Optional[str] = None,
        since: Optional[datetime.datetime] = None,
        limit: Optional[int] = None,
    ) -> list[LLMCallRecord]:
        """Filter across stored JSONL files. Reads lazily.

        A ``calls-*.jsonl`` file whose name holds no ISO date, and a corrupt
        line, alert the operator and raise ``ValueError`` naming the file (and
        the line); skipping either returned fewer records than the store holds.
        """
        if limit is not None and limit <= 0:
            return []

        results: list[LLMCallRecord] = []
        jsonl_files = sorted(self.base_dir.glob("calls-*.jsonl"))

        for jsonl_path in jsonl_files:
            # Extract date from filename for quick filtering
            date_str = jsonl_path.stem.replace("calls-", "")
            try:
                file_date = datetime.date.fromisoformat(date_str)
            except ValueError as exc:
                raise _unreadable(
                    jsonl_path,
                    f"{jsonl_path}: the file name holds no ISO date ({exc})",
                    "CallStore.query",
                ) from exc

            if since is not None and file_date < since.date():
                continue

            with open(jsonl_path, "rb") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record: LLMCallRecord = orjson.loads(line)
                    except orjson.JSONDecodeError as exc:
                        raise _unreadable(
                            jsonl_path,
                            f"{jsonl_path}:{line_num}: not JSON ({exc})",
                            "CallStore.query",
                        ) from exc

                    # Apply filters
                    if workflow is not None:
                        if record.get("inputs", {}).get("workflow") != workflow:
                            continue
                    if model is not None:
                        if record.get("outputs", {}).get("model_used") != model:
                            continue
                    if since is not None:
                        record_ts = record.get("timestamp_utc", "")
                        if record_ts < since.isoformat():
                            continue

                    results.append(record)

                    if limit is not None and len(results) >= limit:
                        return results

        return results

    def _day_path(self, date: datetime.date) -> Path:
        """Return path to JSONL file for given date."""
        return self.base_dir / f"calls-{date.isoformat()}.jsonl"

    def _get_lock(self, key: str) -> threading.Lock:
        """Get or create a lock for the given key."""
        with self._locks_lock:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            return self._locks[key]