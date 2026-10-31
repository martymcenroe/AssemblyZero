"""Generic workflow state persistence for save/load/resume.

Issue #486: Halt-and-Plan pattern — self-babysitting workflows.

Provides a simple save/load mechanism for any workflow's state dict.
Used by the HALT node to persist state on errors, enabling later resumption.
"""

import json
from pathlib import Path

from assemblyzero.core.halt_paths import (
    halt_directory,
    run_key,
    state_is_mock,
    state_repo_root,
)

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

    Raises:
        UnkeyableRun: the state names no repository, or neither an issue nor
            a brief (#4292). The file lives in the run's repository's own
            directory, a mock run's in its ``mock`` subdirectory, named by the
            run key; it used to be ``{workflow}-{issue}.json`` in one
            directory for the whole machine.
    """
    directory = halt_directory(
        state_repo_root(state), state_is_mock(state), STATE_DIR
    )
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{workflow}-{run_key(state, issue_number)}.json"
    state_path = directory / filename

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


def load_state_snapshot(
    workflow: str, issue_number: int, *, repo_root: Path | str, mock: bool = False
) -> dict | None:
    """Load the most recent state snapshot for a workflow/issue of a repository.

    Args:
        workflow: Workflow name.
        issue_number: The issue number.
        repo_root: The repository the run was against (#4292): a worktree or
            its primary checkout. Issue numbers are per repository.
        mock: Whether the run was a ``--mock`` run, which halts apart.

    Returns:
        The saved state dict, or None when no snapshot was written.

    Raises:
        RuntimeError: the snapshot exists and cannot be read or parsed
            (#3797). It used to read as "no snapshot".
    """
    filename = f"{workflow}-{issue_number}.json"
    state_path = halt_directory(repo_root, mock, STATE_DIR) / filename

    if not state_path.exists():
        return None

    try:
        with open(state_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(
            f"cannot read the state snapshot {state_path}: {type(exc).__name__}: {exc}"
        ) from exc
