"""Generic workflow state persistence for save/load/resume.

Issue #486: Halt-and-Plan pattern — self-babysitting workflows.

Provides a simple save/load mechanism for any workflow's state dict.
Used by the HALT node to persist state on errors, enabling later resumption.
"""

import json
from pathlib import Path

STATE_DIR = Path.home() / ".assemblyzero" / "workflow_state"


def save_state_snapshot(
    workflow: str,
    issue_number: int,
    state: dict,
    trigger: str = "error",
) -> Path:
    """Save workflow state to a JSON file.

    A value JSON cannot hold is written as its ``str()``. #3797 judged this
    and kept it: the snapshot is HALT's record and is written before HALT
    alerts, so raising here would cost the halt its recovery plan and its
    alert; and nothing reads the snapshot back as state (the resume contract
    only hashes the file). A snapshot that cannot be written still raises.

    Args:
        workflow: Workflow name (requirements, implementation_spec, testing, orchestrator).
        issue_number: The issue number being processed.
        state: The full workflow state dict to persist.
        trigger: Why the snapshot was taken (error, halt, checkpoint).

    Returns:
        Path to the saved state file.
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{workflow}-{issue_number}.json"
    state_path = STATE_DIR / filename

    # Filter out non-serializable values
    serializable_state = {}
    for key, value in state.items():
        try:
            json.dumps(value)
            serializable_state[key] = value
        except (TypeError, ValueError):
            serializable_state[key] = str(value)

    payload = {
        "workflow": workflow,
        "issue_number": issue_number,
        "trigger": trigger,
        **serializable_state,
    }

    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return state_path


def load_state_snapshot(workflow: str, issue_number: int) -> dict | None:
    """Load the most recent state snapshot for a workflow/issue.

    Args:
        workflow: Workflow name.
        issue_number: The issue number.

    Returns:
        The saved state dict, or None when no snapshot was written.

    Raises:
        RuntimeError: the snapshot exists and cannot be read or parsed
            (#3797). It used to read as "no snapshot".
    """
    filename = f"{workflow}-{issue_number}.json"
    state_path = STATE_DIR / filename

    if not state_path.exists():
        return None

    try:
        with open(state_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(
            f"cannot read the state snapshot {state_path}: {type(exc).__name__}: {exc}"
        ) from exc
