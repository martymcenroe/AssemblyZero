#!/usr/bin/env python3
"""Consolidate session shards into review history.

This script is invoked by the post-commit git hook to merge all active
session shards into the permanent review_history.jsonl file.

Uses atomic write pattern: temp file + os.replace() for crash safety.

Issue #57: Distributed Session-Sharded Logging Architecture
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from assemblyzero.core.config import DEFAULT_AUDIT_LOG_PATH


def read_jsonl(path: Path) -> list[dict]:
    """Read all entries from a JSONL file.

    Args:
        path: Path to JSONL file.

    Returns:
        List of parsed JSON objects.
    """
    entries: list[dict] = []

    if not path.exists():
        return entries

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue

    return entries


def detect_repo_root() -> Path:
    """Detect repository root via git rev-parse.

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
        raise RuntimeError("git not found")
    except subprocess.TimeoutExpired:
        raise RuntimeError("git rev-parse timed out")

    if result.returncode != 0:
        raise RuntimeError(f"Not in a git repository: {result.stderr.strip()}")

    return Path(result.stdout.strip())


def consolidate(repo_root: Path) -> int:
    """Merge all shards into history using atomic write pattern.

    Pattern: Read history + shards -> Write to temp -> os.replace()

    Args:
        repo_root: Repository root path.

    Returns:
        Number of shards processed.

    Raises:
        OSError: If atomic write fails.
    """
    active_dir = repo_root / "logs" / "active"
    history_file = repo_root / DEFAULT_AUDIT_LOG_PATH

    # Find all shards (exclude .gitkeep)
    if not active_dir.exists():
        return 0

    shards = sorted(active_dir.glob("*.jsonl"))
    if len(shards) == 0:
        return 0

    # Read existing history
    existing_entries = read_jsonl(history_file)

    # Read all shards
    new_entries: list[dict] = []
    for shard in shards:
        new_entries.extend(read_jsonl(shard))

    if len(new_entries) == 0:
        # Shards exist but are empty - clean them up
        for shard in shards:
            shard.unlink()
        return len(shards)

    # Merge and sort by timestamp
    all_entries = existing_entries + new_entries
    all_entries.sort(key=lambda e: e.get("timestamp", ""))

    # Ensure logs directory exists
    history_file.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write: temp file + os.replace()
    # TODO: For history files >50MB, consider log rotation (Gemini review G1.1)
    fd = None
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(
            dir=history_file.parent,
            prefix=".history_",
            suffix=".tmp",
        )

        # Write all entries to temp file
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = None  # Prevent double close
            for entry in all_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Atomic rename (cross-platform via os.replace)
        os.replace(temp_path, history_file)
        temp_path = None  # Prevent cleanup

    finally:
        # Cleanup on failure
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    # Delete processed shards only after successful atomic write
    for shard in shards:
        try:
            shard.unlink()
        except OSError:
            # Shard may be locked by another process; skip
            pass

    return len(shards)


def main() -> None:
    """Entry point for hook invocation."""
    try:
        repo_root = detect_repo_root()
        count = consolidate(repo_root)
        if count > 0:
            print(f"Consolidated {count} audit shard(s)")
    except Exception as e:
        # Fail silently in hook context (don't block commits)
        print(f"Warning: Log consolidation failed: {e}", file=sys.stderr)
        # Exit 0 to not block the commit
        sys.exit(0)


if __name__ == "__main__":
    main()
