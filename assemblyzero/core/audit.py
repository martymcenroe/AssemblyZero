"""Audit logging infrastructure for AssemblyZero reviews.

This module provides persistent audit logging for LLD review decisions,
using session-sharded JSONL format to eliminate write collisions.

Issue #57: Distributed Session-Sharded Logging Architecture
- Each session writes to a unique shard: logs/active/{timestamp}_{session_id}.jsonl
- Shards are consolidated into logs/review_history.jsonl via post-commit hook
- tail() merges history + active shards for unified view
"""

import json
import subprocess
import uuid as uuid_module
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional, TypedDict

from assemblyzero.core.config import DEFAULT_AUDIT_LOG_PATH, LOGS_ACTIVE_DIR


class ReviewLogEntry(TypedDict):
    """Single entry in the review audit log."""

    id: str  # UUID as string
    sequence_id: int  # From state.iteration_count
    timestamp: str  # ISO8601 format
    node: str  # Node name (e.g., "review_lld")
    model: str  # Model requested (e.g., "gemini-3-pro-preview")
    model_verified: str  # Actual model from API response
    issue_id: int  # GitHub issue being reviewed
    verdict: str  # "APPROVED" or "BLOCK"
    critique: str  # Gemini's feedback
    tier_1_issues: list[str]  # Blocking issues found
    raw_response: str  # Full Gemini response
    duration_ms: int  # Call duration including retries
    # Credential observability (per Gemini review feedback)
    credential_used: str  # Name of credential that succeeded
    rotation_occurred: bool  # True if rotation happened during call
    attempts: int  # Total API call attempts


class GeminiReviewResponse(TypedDict):
    """Structured output schema for Gemini LLD reviews."""

    verdict: str  # "APPROVED" or "BLOCK"
    critique: str  # Summary feedback
    tier_1_issues: list[str]  # Blocking issues (empty if approved)


class ReviewAuditLog:
    """Persistent audit log for review decisions.

    Uses session-sharded JSONL format:
    - Each session writes to a unique shard in logs/active/
    - Shards are consolidated via post-commit hook
    - tail() merges history + active shards for unified view

    Issue #57: Distributed Session-Sharded Logging Architecture
    """

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        session_id: Optional[str] = None,
        log_path: Optional[Path] = None,
    ):
        """Initialize with auto-detected repo root and unique session ID.

        Args:
            repo_root: Repository root path. Auto-detected if None.
            session_id: Session identifier (8 chars). Generated if None.
            log_path: Legacy parameter for backwards compatibility.
                      If provided, uses old single-file mode.

        Raises:
            RuntimeError: If not in a git repository and repo_root not provided.
        """
        # Legacy mode: if log_path provided, use old single-file behavior
        if log_path is not None:
            self._legacy_mode = True
            self.log_path = log_path
            self.repo_root = log_path.parent.parent
            self.session_id = ""
            self.active_dir = self.repo_root / "logs" / "active"
            self.history_file = log_path
            self.shard_file = log_path  # Write to history directly
            return

        self._legacy_mode = False
        self.repo_root = repo_root or self._detect_repo_root()
        self.session_id = session_id or uuid_module.uuid4().hex[:8]

        # Set paths relative to repo root
        self.active_dir = self.repo_root / LOGS_ACTIVE_DIR
        self.history_file = self.repo_root / DEFAULT_AUDIT_LOG_PATH
        self.shard_file = self.active_dir / self._generate_shard_filename()

        # Ensure active directory exists (fail-closed if not writable)
        self.active_dir.mkdir(parents=True, exist_ok=True)

        # Also ensure logs directory exists for history file
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        # For backwards compatibility
        self.log_path = self.history_file

    def _detect_repo_root(self) -> Path:
        """Detect repository root via git rev-parse --show-toplevel.

        Returns:
            Path to repository root.

        Raises:
            RuntimeError: If not in a git repository.
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "git not found. Install git or provide repo_root explicitly."
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("git rev-parse timed out")

        if result.returncode != 0:
            raise RuntimeError(
                f"Not in a git repository: {result.stderr.strip()}"
            )

        return Path(result.stdout.strip())

    def _generate_shard_filename(self) -> str:
        """Generate unique shard filename: {YYYYMMDDTHHMMSS}_{session_id}.jsonl

        Returns:
            Shard filename string.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        return f"{timestamp}_{self.session_id}.jsonl"

    def log(self, entry: ReviewLogEntry) -> None:
        """Append entry to session shard.

        Args:
            entry: The review log entry to write.

        Raises:
            OSError: If shard directory is not writable (fail-closed).
        """
        # Ensure parent directory exists
        self.shard_file.parent.mkdir(parents=True, exist_ok=True)

        # Serialize to JSON string
        json_line = json.dumps(entry, ensure_ascii=False)

        # Append with newline (fail-closed: let OSError propagate)
        with open(self.shard_file, "a", encoding="utf-8") as f:
            f.write(json_line + "\n")
            f.flush()

    def tail(self, n: int = 10) -> list[ReviewLogEntry]:
        """Return last N entries from history + active shards.

        Merges entries from review_history.jsonl and all active shards,
        sorted by timestamp. Gracefully skips locked or inaccessible shards.

        Optimization: History file is assumed sorted (guaranteed by consolidator),
        so we read only the last K lines instead of the entire file.

        Args:
            n: Number of entries to return. If 0, returns all entries.

        Returns:
            List of the last N entries, oldest first.
        """
        entries: list[ReviewLogEntry] = []

        # Count active shards to estimate buffer size
        shard_count = 0
        if self.active_dir.exists():
            shard_count = len(list(self.active_dir.glob("*.jsonl")))

        # Read from history file (optimized: only last K lines if n > 0)
        if n > 0:
            # Read extra lines to account for active shards that may interleave
            # Assume max 100 entries per shard as buffer
            buffer_size = n + (shard_count * 100)
            entries.extend(self._read_jsonl_tail(self.history_file, buffer_size))
        else:
            # n=0 means read all
            entries.extend(self._read_jsonl_safe(self.history_file))

        # Read from all active shards (always read fully - they're small)
        if self.active_dir.exists():
            for shard in self.active_dir.glob("*.jsonl"):
                entries.extend(self._read_jsonl_safe(shard))

        # Sort by timestamp (shards may interleave with history tail)
        entries.sort(key=lambda e: e.get("timestamp", ""))

        # Return last N
        return entries[-n:] if n > 0 else entries

    def _read_jsonl_tail(self, path: Path, n: int) -> list[ReviewLogEntry]:
        """Read last N lines from JSONL file, gracefully handling errors.

        Optimized for large files - only reads the tail portion.

        Args:
            path: Path to JSONL file.
            n: Maximum number of lines to read from end.

        Returns:
            List of entries, or empty list if file inaccessible.
        """
        if not path.exists():
            return []

        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()

            entries: list[ReviewLogEntry] = []
            # Get last N lines
            for line in lines[-n:]:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue
            return entries
        except (OSError, IOError):
            # Skip locked or inaccessible files (graceful degradation)
            return []

    def _read_jsonl_safe(self, path: Path) -> list[ReviewLogEntry]:
        """Read JSONL file, gracefully handling errors.

        Args:
            path: Path to JSONL file.

        Returns:
            List of entries, or empty list if file inaccessible.
        """
        entries: list[ReviewLogEntry] = []

        if not path.exists():
            return entries

        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            # Skip malformed lines
                            continue
        except (OSError, IOError):
            # Skip locked or inaccessible files (graceful degradation)
            pass

        return entries

    def __iter__(self) -> Iterator[ReviewLogEntry]:
        """Iterate over all entries from history + active shards.

        Yields:
            Each review log entry in chronological order.
        """
        # Get all entries and sort
        all_entries = self.tail(n=0)  # n=0 returns all
        yield from all_entries

    def count(self) -> int:
        """Return total number of entries across history + shards.

        Returns:
            Count of log entries.
        """
        return len(self.tail(n=0))


def create_log_entry(
    node: str,
    model: str,
    model_verified: str,
    issue_id: int,
    verdict: str,
    critique: str,
    tier_1_issues: list[str],
    raw_response: str,
    duration_ms: int,
    credential_used: str,
    rotation_occurred: bool,
    attempts: int,
    sequence_id: int = 0,
) -> ReviewLogEntry:
    """Factory function to create a review log entry.

    Args:
        node: Node name (e.g., "review_lld").
        model: Model requested.
        model_verified: Actual model used.
        issue_id: GitHub issue number.
        verdict: "APPROVED" or "BLOCK".
        critique: Gemini's feedback.
        tier_1_issues: List of blocking issues.
        raw_response: Full Gemini response.
        duration_ms: Call duration in milliseconds.
        credential_used: Name of credential that succeeded.
        rotation_occurred: Whether rotation happened.
        attempts: Total API call attempts.
        sequence_id: Sequence number from state.

    Returns:
        A complete ReviewLogEntry for the review decision.
    """
    return ReviewLogEntry(
        id=str(uuid_module.uuid4()),
        sequence_id=sequence_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        node=node,
        model=model,
        model_verified=model_verified,
        issue_id=issue_id,
        verdict=verdict,
        critique=critique,
        tier_1_issues=tier_1_issues,
        raw_response=raw_response,
        duration_ms=duration_ms,
        credential_used=credential_used,
        rotation_occurred=rotation_occurred,
        attempts=attempts,
    )
