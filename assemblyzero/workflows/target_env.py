"""The Python environment a target's tests run in (#4490).

A workflow runs under `poetry run` from the AssemblyZero checkout, which leaves
AssemblyZero's virtualenv in VIRTUAL_ENV and at the front of PATH. Whatever it
starts for a target sheds that first (`hook_environment`, #3705): poetry takes
an inherited VIRTUAL_ENV as already active and answers from it (#1415).

Shedding it is not enough for pytest. `poetry run pytest` looks the command up
on PATH with the target's environment in front, so an environment with no
pytest runs the next one along. Measured on 2026-11-01: a target that declares
no pytest ran the pytest in another project's virtualenv and exited 0.
`require_pytest` therefore asks the target's own interpreter before a run
starts, and refuses, naming what is missing:

- a target with no project of its own, either no `pyproject.toml` or one that
  only configures tools. Nothing declares or installs what its tests need, and
  poetry would walk up to a parent directory's project, so there is no
  environment to name and the run halts;
- a project poetry names no environment for, which was never installed;
- an environment with no pytest;
- an environment with no pytest-cov, when the run measures coverage. pytest
  without the plugin reads `--cov` as a usage error and exits 4.

Every answer comes from the target's interpreter, which poetry names, and never
from this process (ADR 0236): a wrong-environment answer is worse than none.
"""

from __future__ import annotations

import json
import os
import subprocess
import tomllib
from pathlib import Path

from assemblyzero.utils.shell import run_command

#: Both questions answer in moments; a slow one means poetry is stuck.
PROBE_TIMEOUT_SECONDS = 60

_PROBE = (
    "import importlib.util, json, sys; "
    "print(json.dumps({n: importlib.util.find_spec(n) is not None "
    "for n in sys.argv[1:]}))"
)


class TargetEnvironmentError(OSError):
    """The target has no environment its pytest can run in. The message names
    the target and what is missing. An OSError, as `require_dependencies`
    promises (#4236)."""


def hook_environment(environ: dict[str, str] | None = None) -> dict[str, str]:
    """The target's environment: the workflow's, minus its own poetry activation.

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


def declares_project(pyproject: Path) -> bool:
    """Whether ``pyproject`` declares a project poetry can install: a
    ``[project]`` or ``[tool.poetry]`` table. Raises OSError or ValueError when
    it cannot be read as TOML."""
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return "project" in data or "poetry" in (data.get("tool") or {})


def _require_project(root: Path) -> None:
    pyproject = root / "pyproject.toml"
    try:
        declared = pyproject.is_file() and declares_project(pyproject)
    except (OSError, ValueError) as exc:
        raise TargetEnvironmentError(
            f"{pyproject} could not be read as TOML, so {root}'s environment is "
            f"unknown: {type(exc).__name__}: {exc}"
        ) from exc
    if declared:
        return
    found = "only configures tools" if pyproject.is_file() else "does not exist"
    raise TargetEnvironmentError(
        f"{root} has no Python project of its own: {pyproject} {found}, so "
        f"nothing declares or installs what its tests need and poetry would "
        f"reach a parent directory's project or none. Its pytest suite has no "
        f"environment to run in. Declare a [project] or [tool.poetry] table there"
    )


def _ask(what: str, command: list[str], root: Path) -> subprocess.CompletedProcess:
    try:
        return run_command(
            command, cwd=str(root), timeout=PROBE_TIMEOUT_SECONDS,
            env=hook_environment(), capture_output=True, text=True,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TargetEnvironmentError(
            f"{what} in {root} could not answer, so its environment is "
            f"unknown: {type(exc).__name__}: {exc}"
        ) from exc


def _target_python(root: Path) -> tuple[Path, Path]:
    """The environment poetry names for ``root``, and the interpreter in it."""
    named = _ask("`poetry env info --path`", ["poetry", "env", "info", "--path"], root)
    reported = named.stdout.strip()
    if named.returncode != 0 or not reported:
        # Poetry prints nothing at all for a project that was never installed.
        raise TargetEnvironmentError(
            f"poetry names no environment for {root} (`poetry env info --path` "
            f"exited {named.returncode}: {named.stderr.strip() or 'no output'}), "
            f"so its tests have nowhere to run. `poetry install` there builds one"
        )
    env_path = Path(reported)
    for python in (env_path / "Scripts" / "python.exe", env_path / "bin" / "python"):
        if python.is_file():
            return env_path, python
    raise TargetEnvironmentError(
        f"poetry names {env_path} as {root}'s environment, which holds no python "
        f"(looked for Scripts/python.exe and bin/python)"
    )


def _importable(python: Path, root: Path, modules: list[str]) -> dict[str, bool]:
    """{module: found} from ``python`` itself, never from this process."""
    done = _ask("the import probe", [str(python), "-c", _PROBE, *modules], root)
    where = f"the import probe in {root}'s environment ({python})"
    if done.returncode != 0:
        raise TargetEnvironmentError(
            f"{where} exited {done.returncode}: {done.stderr.strip() or 'no output'}"
        )
    try:
        return dict(json.loads(done.stdout))
    except (TypeError, ValueError) as exc:
        raise TargetEnvironmentError(
            f"{where} printed {done.stdout.strip()[:200]!r}, which is not its "
            f"answer: {type(exc).__name__}: {exc}"
        ) from exc


def require_pytest(repo_root: Path | str, *, coverage: bool = False) -> None:
    """Raise TargetEnvironmentError unless pytest can run in ``repo_root``'s own
    environment, and measure coverage there when ``coverage`` is set.

    Called before a run starts, so what cannot run is named instead of being
    tested in whatever resolves. See the module docstring for each refusal.
    """
    root = Path(repo_root)
    _require_project(root)
    env_path, python = _target_python(root)
    found = _importable(python, root, ["pytest", "pytest_cov"] if coverage else ["pytest"])
    if not found.get("pytest"):
        raise TargetEnvironmentError(
            f"pytest is not installed in {root}'s environment ({env_path}), and "
            f"`poetry run pytest` would run whichever pytest comes next on PATH, "
            f"in another project's environment. Declare it: `poetry add --group "
            f"dev pytest` in {root}"
        )
    if coverage and not found.get("pytest_cov"):
        raise TargetEnvironmentError(
            f"pytest-cov is not installed in {root}'s environment ({env_path}), "
            f"so coverage cannot be measured and the coverage gate cannot run. "
            f"Declare it: `poetry add --group dev pytest-cov` in {root}"
        )
