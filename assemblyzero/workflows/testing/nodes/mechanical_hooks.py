"""N4.5: Mechanical Hooks node for TDD Testing Workflow.

Issue #3678: Execute build hooks defined in .unleashed.json (e.g. post_implement_command)
after implementation and before tests.

#3705: the hook runs in the target's environment, not the workflow's. The
workflow runs under `poetry run` from the AssemblyZero checkout, which leaves
AssemblyZero's virtualenv in VIRTUAL_ENV and at the front of PATH; a hook of
the form `poetry run python -m <package>` then ran AssemblyZero's interpreter
and could not import the target's package. The same leak was fixed for
`tools/dependabot_review.py` in #1415.

#3706: a hook that fails halts the run. Nothing is tested against a build
that did not build, and every failure is loud and stops what depends on it
(#3579). The route is `route_after_mechanical_hooks` in graph.py.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from assemblyzero.workflows.testing.audit import gate_log, get_repo_root
from assemblyzero.workflows.testing.state import TestingWorkflowState


def hook_environment(environ: dict[str, str] | None = None) -> dict[str, str]:
    """The hook's environment: the workflow's, minus its own poetry activation.

    VIRTUAL_ENV and POETRY_ACTIVE make poetry treat the workflow's virtualenv
    as already active and skip per-directory resolution (#1415); that
    virtualenv's bin directory at the front of PATH makes a bare `python`
    resolve to the workflow's interpreter. All three go (#3705).
    """
    env = dict(os.environ if environ is None else environ)
    venv = env.pop("VIRTUAL_ENV", None)
    env.pop("POETRY_ACTIVE", None)
    if venv:
        venv_bin = {str(Path(venv) / "bin"), str(Path(venv) / "Scripts")}
        env["PATH"] = os.pathsep.join(
            p for p in env.get("PATH", "").split(os.pathsep) if p and p not in venv_bin
        )
    return env


def _halt(reason: str) -> dict[str, Any]:
    gate_log(f"  [HALT] {reason}")
    return {"error_message": reason}


def mechanical_hooks(state: TestingWorkflowState) -> dict[str, Any]:
    """N4.5: Run mechanical hooks from .unleashed.json.

    Args:
        state: Current workflow state.

    Returns:
        No update when there is no hook or it succeeded; `error_message` set,
        which `route_after_mechanical_hooks` sends to HALT, when the config
        cannot be read or the hook fails (#3706).
    """
    gate_log("[N4.5] Running mechanical hooks...")

    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()
    unleashed_path = repo_root / ".unleashed.json"

    if not unleashed_path.exists():
        return {}

    try:
        config = json.loads(unleashed_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return _halt(f"N4.5: {unleashed_path} could not be read as JSON: {e}")

    post_command = config.get("post_implement_command")
    if not post_command:
        return {}

    gate_log(f"  Executing post_implement_command: {post_command}")
    try:
        result = subprocess.run(
            post_command,
            shell=True,
            cwd=repo_root,
            env=hook_environment(),
            capture_output=True,
            text=True,
        )
    except OSError as e:
        return _halt(f"N4.5: post_implement_command could not start: {e}")

    if result.stdout:
        gate_log(f"  Stdout: {result.stdout}")
    if result.stderr:
        gate_log(f"  Stderr: {result.stderr}")
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        return _halt(
            f"N4.5: post_implement_command failed (exit code {result.returncode}): "
            f"{post_command}\n{detail}"
        )

    gate_log("  post_implement_command completed successfully.")
    # Artifact Staging: Any files created or modified by the mechanical hook
    # must be automatically staged (git add)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=False)
    gate_log("  Staged modified artifacts.")
    return {}
