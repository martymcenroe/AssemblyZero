"""Resume-from-stage logic and state persistence.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

from __future__ import annotations

import json
import os
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path

from assemblyzero.workflows.orchestrator.state import (
    STAGE_ORDER,
    OrchestrationState,
)


STATE_DIR = Path(".assemblyzero/orchestrator/state")
LOCK_DIR = Path(".assemblyzero/orchestrator/locks")


def save_orchestration_state(state: OrchestrationState) -> Path:
    """Persist state to disk as JSON for resume capability.

    Creates backup of existing state file before overwriting.
    Returns path to saved state file.
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    issue_number = state["issue_number"]
    state_path = STATE_DIR / f"{issue_number}.json"

    # Backup existing state file
    if state_path.exists():
        backup_path = STATE_DIR / f"{issue_number}.json.bak"
        shutil.copy2(state_path, backup_path)

    state_path.write_text(
        json.dumps(dict(state), indent=2, default=str),
        encoding="utf-8",
    )
    return state_path


def load_orchestration_state(issue_number: int) -> OrchestrationState | None:
    """Load persisted state for an issue, if exists.

    Returns None if no state file found or file is invalid.
    """
    state_path = STATE_DIR / f"{issue_number}.json"
    if not state_path.is_file():
        return None

    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[ORCHESTRATOR] Warning: Could not load state file {state_path}: {exc}")
        return None

    # Basic validation
    required_keys = {"issue_number", "current_stage"}
    if not required_keys.issubset(data.keys()):
        print(
            f"[ORCHESTRATOR] Warning: State file {state_path} missing required keys: "
            f"{required_keys - data.keys()}"
        )
        return None

    if data.get("issue_number") != issue_number:
        print(
            f"[ORCHESTRATOR] Warning: State file issue_number mismatch: "
            f"expected {issue_number}, got {data.get('issue_number')}"
        )
        return None

    return OrchestrationState(**data)


def determine_resume_stage(
    state: OrchestrationState,
    resume_from: str | None,
) -> str:
    """Determine which stage to resume from.

    If resume_from is specified, validates it's a valid stage.
    If not specified, returns current_stage from state.
    """
    if resume_from is None:
        return state.get("current_stage", "triage")

    if resume_from not in STAGE_ORDER:
        msg = (
            f"Invalid stage: '{resume_from}'. "
            f"Valid stages: {', '.join(STAGE_ORDER)}"
        )
        raise ValueError(msg)

    return resume_from


def _is_pid_alive(pid: int) -> bool:
    """Check if a process with given PID is alive."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def acquire_orchestration_lock(issue_number: int) -> bool:
    """Acquire lock file to prevent concurrent runs.

    Creates .assemblyzero/orchestrator/locks/{issue_number}.lock
    Lock file contains PID and timestamp.

    Returns True if lock acquired, False if already locked by live process.
    """
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = LOCK_DIR / f"{issue_number}.lock"

    if lock_path.exists():
        # Check if lock is stale
        try:
            lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
            pid = lock_data.get("pid", -1)
            if _is_pid_alive(pid):
                return False
            # Stale lock — remove it
            print(f"[ORCHESTRATOR] Removing stale lock for issue {issue_number} (PID {pid} is dead)")
            lock_path.unlink()
        except (json.JSONDecodeError, OSError):
            # Corrupted lock file — remove it
            lock_path.unlink(missing_ok=True)

    # Write new lock
    lock_data = {
        "pid": os.getpid(),
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
        "hostname": platform.node(),
    }
    lock_path.write_text(
        json.dumps(lock_data, indent=2),
        encoding="utf-8",
    )
    return True


def release_orchestration_lock(issue_number: int) -> None:
    """Release lock file for an issue. No-op if lock doesn't exist."""
    lock_path = LOCK_DIR / f"{issue_number}.lock"
    lock_path.unlink(missing_ok=True)
