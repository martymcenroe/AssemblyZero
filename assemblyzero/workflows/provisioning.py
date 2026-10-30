"""Install the environment a run's worktree needs, before any node runs (#4238).

A worktree is a fresh checkout. Poetry keys its environments to the checkout
path, so a new worktree has no environment of its own, and ``node_modules`` is
never committed. A run that tested in one without installing ran against
whatever environment happened to resolve: AssemblyZero's own, a parent
directory's ``node_modules``, or none.

What is installed, in this order:

- ``poetry install`` in the worktree's root and in every directory a test
  framework was detected in (``detect_framework_dirs``), where a
  ``pyproject.toml`` declares a project (a ``[project]`` or ``[tool.poetry]``
  table). Retried once with ``--no-root`` when the only failure is the
  project's own package, which does not exist yet on a base that predates the
  work (#1994). A ``pyproject.toml`` that only configures tools declares
  nothing to install.
- ``npm ci`` in every directory that holds a ``package-lock.json`` or
  ``npm-shrinkwrap.json`` and is, or is under, the directory of a detected
  JavaScript test suite, read from the files on disk (``npm_install_dirs``).

Every install runs in the target's environment, never the workflow's
(``hook_environment``, #3705): the workflow runs under ``poetry run``, and an
inherited ``VIRTUAL_ENV`` makes ``poetry install`` install the target's
dependencies into AssemblyZero's own virtualenv.

ADR 0236. An install that fails, or cannot start, or does not finish, raises
``ProvisioningError`` naming the command, the directory and its output, and
nothing after it runs. So does a JavaScript suite's directory with no lock
file, and any directory in or under one that has a ``package.json`` and no
lock file, because ``npm ci`` needs the lock and the suite's tests would
otherwise run against whatever ``node_modules`` resolves. The caller stops the run
before its graph is built and alerts. Nothing to install is an answer, and is
said in one line.

A mock run makes the same plan and runs none of it: it stays offline and
fast, names each install it did not run, and a plan that cannot be made stops
it as it would stop a real run.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from assemblyzero.utils.shell import run_command
from assemblyzero.workflows.testing.framework_detector import (
    MAX_DETECT_DEPTH,
    SKIPPED_DIRS,
    TestFramework,
    detect_framework_dirs,
)
from assemblyzero.workflows.testing.nodes.mechanical_hooks import hook_environment

POETRY_INSTALL = ("poetry", "install")
POETRY_INSTALL_NO_ROOT = ("poetry", "install", "--no-root")
NPM_CI = ("npm", "ci")

#: The lock files `npm ci` installs from. Closed: npm reads exactly these.
NPM_LOCK_FILES = ("package-lock.json", "npm-shrinkwrap.json")

#: A first install in a new worktree builds its environment from nothing.
INSTALL_TIMEOUT_SECONDS = 1800

#: How much of a failed install's output the error carries: the end, where
#: poetry and npm both put the reason.
OUTPUT_TAIL_CHARS = 4000

#: Poetry's words when the project's own package is absent (#1994).
_MISSING_ROOT_PACKAGE = "the current project could not be installed"


class ProvisioningError(RuntimeError):
    """The worktree's environment could not be installed. The message names
    the directory and, for an install, the command and its output."""

    def __init__(self, message: str, *, directory: Path, command: str = "",
                 output: str = ""):
        super().__init__(message)
        self.directory = directory
        self.command = command
        self.output = output


@dataclass(frozen=True)
class InstallStep:
    """One install: the command and the directory it runs in."""

    directory: Path
    argv: tuple[str, ...]

    @property
    def command(self) -> str:
        return " ".join(self.argv)


@dataclass(frozen=True)
class ProvisioningPlan:
    """What a worktree needs installed, in the order it is installed."""

    worktree: Path
    directories: tuple[str, ...]
    steps: tuple[InstallStep, ...]


def _text(value: object) -> str:
    """A captured stream as text; TimeoutExpired carries bytes even when the
    call asked for text."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _output(stdout: object, stderr: object) -> str:
    """Both streams, the end of them when they are long."""
    text = "\n".join(
        part for part in (_text(stdout).strip(), _text(stderr).strip()) if part
    )
    if not text:
        return "(no output)"
    if len(text) > OUTPUT_TAIL_CHARS:
        return "..." + text[-OUTPUT_TAIL_CHARS:]
    return text


def _declares_project(pyproject: Path) -> bool:
    """Whether ``pyproject`` declares a project poetry can install.

    A file that cannot be read as TOML is a broken project, not a missing one,
    so it raises."""
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProvisioningError(
            f"worktree provisioning failed: {pyproject} could not be read as "
            f"TOML: {type(exc).__name__}: {exc}",
            directory=pyproject.parent,
        ) from exc
    return "project" in data or "poetry" in (data.get("tool") or {})


def _inside(worktree: Path, relative: str) -> Path:
    """``worktree / relative``, refused when a declared test directory points
    outside the worktree: nothing is installed into another tree."""
    directory = worktree / relative
    if not directory.resolve().is_relative_to(worktree.resolve()):
        raise ProvisioningError(
            f"worktree provisioning failed: a test suite is placed at "
            f"{relative}, which is outside the worktree {worktree}",
            directory=directory,
        )
    return directory


def _has_lock(directory: Path) -> bool:
    return any((directory / name).is_file() for name in NPM_LOCK_FILES)


def _no_lock(directory: Path, why: str) -> ProvisioningError:
    return ProvisioningError(
        f"worktree provisioning failed: {directory} {why} and no "
        f"{' or '.join(NPM_LOCK_FILES)}, so `npm ci` cannot install its "
        f"node_modules and the suite's tests would run against whatever "
        f"resolves. Commit the lock file to the target",
        directory=directory, command=" ".join(NPM_CI),
    )


def _directories_in(root: Path, directory: Path) -> list[Path]:
    """``directory`` and the directories below it, to MAX_DETECT_DEPTH levels
    under ``root``, skipping SKIPPED_DIRS and hidden directories: the bounds
    the framework detector searches within, in path order."""
    top = os.path.abspath(root)
    found: list[Path] = []
    for current, dirnames, _files in os.walk(directory):
        relative = os.path.relpath(current, top)
        depth = 0 if relative == "." else relative.count(os.sep) + 1
        dirnames[:] = sorted(
            d for d in dirnames if d not in SKIPPED_DIRS and not d.startswith(".")
        )
        if depth >= MAX_DETECT_DEPTH:
            dirnames[:] = []
        found.append(Path(current))
    return found


def npm_install_dirs(worktree: Path | str, suite_dirs: Iterable[str]) -> list[Path]:
    """Every directory ``npm ci`` must run in for the JavaScript test suites
    at ``suite_dirs``, read from the files on disk (#4238).

    ``suite_dirs`` are the suites' directories relative to ``worktree`` ("."
    for the root), from whatever detected them. For each one, it and every
    directory below it (to MAX_DETECT_DEPTH levels under the worktree's root,
    skipping SKIPPED_DIRS and hidden directories) that holds a
    ``package-lock.json`` or ``npm-shrinkwrap.json`` is returned, once, in
    the order found.

    Raises ProvisioningError for a suite directory with no lock file, and for
    any directory among them that has a ``package.json`` and no lock file:
    ``npm ci`` needs the lock. Also for a suite directory outside the worktree.
    """
    root = Path(worktree)
    found: list[Path] = []
    for relative in dict.fromkeys(suite_dirs):
        suite = _inside(root, relative)
        if not _has_lock(suite):
            raise _no_lock(suite, "holds a JavaScript test suite")
        for directory in _directories_in(root, suite):
            if _has_lock(directory):
                if directory not in found:
                    found.append(directory)
            elif (directory / "package.json").is_file():
                raise _no_lock(
                    directory, f"has a package.json, in the JavaScript suite at {suite},",
                )
    return found


def plan_provisioning(worktree: Path | str) -> ProvisioningPlan:
    """The installs ``worktree`` needs, without running any of them: the
    Python installs, then ``npm_install_dirs`` for every JavaScript suite
    ``detect_framework_dirs`` finds.

    Raises ProvisioningError when the plan cannot be made: the project files
    cannot be read, a ``pyproject.toml`` is not TOML, a test directory is
    outside the worktree, or a JavaScript suite is missing a lock file.
    """
    root = Path(worktree)
    try:
        detected = detect_framework_dirs(str(root))
    except (OSError, ValueError) as exc:
        raise ProvisioningError(
            f"worktree provisioning failed: could not tell which directories "
            f"of {root} hold a test suite: {type(exc).__name__}: {exc}",
            directory=root,
        ) from exc

    directories = list(dict.fromkeys([".", *detected.values()]))
    steps: list[InstallStep] = []
    for relative in directories:
        pyproject = _inside(root, relative) / "pyproject.toml"
        if pyproject.is_file() and _declares_project(pyproject):
            steps.append(InstallStep(pyproject.parent, POETRY_INSTALL))
    javascript = [
        relative for framework, relative in detected.items()
        if framework is not TestFramework.PYTEST
    ]
    steps += [InstallStep(d, NPM_CI) for d in npm_install_dirs(root, javascript)]
    return ProvisioningPlan(root, tuple(directories), tuple(steps))


def _argv(argv: tuple[str, ...]) -> list[str]:
    """npm on Windows is npm.cmd, which CreateProcess cannot find from a bare
    name because it does not apply PATHEXT; shutil.which does. Elsewhere the
    argv is passed as it is."""
    if sys.platform != "win32":
        return list(argv)
    return [shutil.which(argv[0]) or argv[0], *argv[1:]]


def _run(step: InstallStep, run: Callable[..., subprocess.CompletedProcess]):
    try:
        return run(
            _argv(step.argv), cwd=str(step.directory),
            timeout=INSTALL_TIMEOUT_SECONDS, env=hook_environment(),
            check=False, capture_output=True, text=True,
        )
    except subprocess.TimeoutExpired as exc:
        output = _output(exc.stdout, exc.stderr)
        raise ProvisioningError(
            f"worktree provisioning failed: `{step.command}` in {step.directory} "
            f"did not finish in {INSTALL_TIMEOUT_SECONDS} s; its output so far:\n"
            f"{output}",
            directory=step.directory, command=step.command, output=output,
        ) from exc
    except OSError as exc:
        raise ProvisioningError(
            f"worktree provisioning failed: `{step.command}` in {step.directory} "
            f"could not start: {type(exc).__name__}: {exc}",
            directory=step.directory, command=step.command,
        ) from exc


def _install(step: InstallStep, run: Callable[..., subprocess.CompletedProcess]) -> list[str]:
    """Run one install; one line per command run. Raises ProvisioningError
    when it fails."""
    lines: list[str] = []
    result = _run(step, run)
    if result.returncode != 0 and step.argv == POETRY_INSTALL:
        both = f"{_text(result.stdout)}\n{_text(result.stderr)}".lower()
        if _MISSING_ROOT_PACKAGE in both:
            lines.append(
                f"[ENV] {step.directory}: the project's own package is not there "
                "yet (the base predates the code); retrying with --no-root"
            )
            step = InstallStep(step.directory, POETRY_INSTALL_NO_ROOT)
            result = _run(step, run)
    if result.returncode != 0:
        output = _output(result.stdout, result.stderr)
        raise ProvisioningError(
            f"worktree provisioning failed: `{step.command}` in {step.directory} "
            f"exited {result.returncode}:\n{output}",
            directory=step.directory, command=step.command, output=output,
        )
    lines.append(f"[ENV] {step.directory}: `{step.command}` done")
    return lines


def provision_worktree(
    worktree: Path | str, *, mock: bool = False,
    run: Callable[..., subprocess.CompletedProcess] | None = None,
) -> list[str]:
    """Install what ``worktree`` needs, in plan order. Returns the lines to
    print: one per command run, or, when nothing needs installing, one line
    that says so.

    ``run`` is the subprocess layer (``run_command`` when not given). A mock
    run runs nothing and returns one line per planned install. Raises
    ProvisioningError on the first failure; no install after it runs.
    """
    plan = plan_provisioning(worktree)
    if not plan.steps:
        return [(
            f"[ENV] nothing to install in {plan.worktree}: no pyproject.toml in "
            f"{', '.join(plan.directories)} declares a project, and no "
            "JavaScript test suite was found"
        )]
    if mock:
        return [
            (
                f"[ENV] mock run: `{step.command}` in {step.directory} is planned "
                "and not run (a mock run installs nothing and stays offline)"
            )
            for step in plan.steps
        ]
    runner = run if run is not None else run_command
    lines: list[str] = []
    for step in plan.steps:
        lines += _install(step, runner)
    return lines
