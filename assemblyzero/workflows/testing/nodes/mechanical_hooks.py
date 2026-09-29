"""N4.5: Mechanical Hooks node for TDD Testing Workflow.

Issue #3678: Execute build hooks defined in .unleashed.json (e.g. post_implement_command)
after implementation and before tests.
"""

import json
import subprocess
from pathlib import Path
from typing import Any

from assemblyzero.workflows.testing.audit import gate_log, get_repo_root
from assemblyzero.workflows.testing.state import TestingWorkflowState


def mechanical_hooks(state: TestingWorkflowState) -> dict[str, Any]:
    """N4.5: Run mechanical hooks from .unleashed.json.

    Args:
        state: Current workflow state.

    Returns:
        State updates (none).
    """
    gate_log("[N4.5] Running mechanical hooks...")

    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()
    unleashed_path = repo_root / ".unleashed.json"

    if not unleashed_path.exists():
        return {}

    try:
        config = json.loads(unleashed_path.read_text(encoding="utf-8"))
    except Exception as e:
        # fail-open: if config is invalid, log and proceed
        gate_log(f"  [WARN] Failed to parse .unleashed.json: {e}")
        return {}

    post_command = config.get("post_implement_command")
    if not post_command:
        return {}

    gate_log(f"  Executing post_implement_command: {post_command}")
    try:
        result = subprocess.run(
            post_command,
            shell=True,
            cwd=repo_root,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            gate_log(f"  [WARN] post_implement_command failed (exit code {result.returncode})")
            gate_log(f"  Stdout: {result.stdout}")
            gate_log(f"  Stderr: {result.stderr}")
        else:
            gate_log("  post_implement_command completed successfully.")
            # Artifact Staging: Any files created or modified by the mechanical hook 
            # must be automatically staged (git add)
            subprocess.run(["git", "add", "."], cwd=repo_root, check=False)
            gate_log("  Staged modified artifacts.")
    except Exception as e:
        # fail-open: hook execution failure shouldn't crash the workflow here
        gate_log(f"  [WARN] Error executing mechanical hook: {e}")

    return {}
