"""Rehearse a target with pytest at its root and Vitest in web/ (#4438, #3585 step 6).

Two named steps, each on a throwaway target it builds under a new directory:

    poetry run python tools/rehearse_two_frameworks.py mock --work-dir <new dir>
    poetry run python tools/rehearse_two_frameworks.py provision --work-dir <new dir>

`mock` runs the LLD and implementation workflows under --mock, through every
phase, offline. It exits 0 only when both exit 0, every framework got its
scaffold, and the three snapshots taken before and after are byte-identical:
the target's git state, its origin's refs, and AssemblyZero's state directories.

`provision` is the part --mock only plans. It cuts a worktree of the target,
really runs `poetry install` and `npm ci` in it through the run's own
`provision_worktree`, then runs both whole suites there, each in the environment
that was just installed. pytest runs through `run_pytest`, the gate's own call,
under this process's virtualenv, which is the condition a real run is in (#4490).
It lists no plugin, because the fixture installs none; coverage is refused by
name; and once the fixture's optional `coverage` group is installed, coverage is
measured and the one plugin listed is pytest-cov. The step needs the network,
and exits 0 only when all of that held and both suites ran tests and passed.

Neither step touches anything outside the new directory, except that `mock`
reads the state directories it snapshots.

The fixture's `web/package-lock.json` is real, kept as data in
`tests/fixtures/two_framework/web-package-lock.json.txt`. The `.txt` keeps
dependency scanners off a project that does not exist. To refresh it, run
`npm install --package-lock-only` beside a copy of `PACKAGE_JSON` in a worktree.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ISSUE = "42"
ROOT = Path(__file__).resolve().parent.parent
Run = Callable[[list[str], Path], int]

PYPROJECT = """\
[tool.poetry]
name = "two-framework-fixture"
version = "0.1.0"
description = "pytest at the root and Vitest in web/ (#4438)"
authors = ["rehearsal <rehearsal@example.com>"]
package-mode = false

[tool.poetry.dependencies]
python = ">=3.10,<4.0"

[tool.poetry.group.dev.dependencies]
pytest = ">=8,<10"

[tool.poetry.group.coverage]
optional = true

[tool.poetry.group.coverage.dependencies]
pytest-cov = ">=6"

[tool.pytest.ini_options]
pythonpath = ["."]
"""
PACKAGE_JSON = {
    "name": "two-framework-fixture-web",
    "private": True,
    "version": "0.1.0",
    "type": "module",
    "scripts": {"test": "vitest run"},
    "devDependencies": {"@vitest/coverage-v8": "^3.2.4", "vitest": "^3.2.4"},
}
LOCK = ROOT / "tests" / "fixtures" / "two_framework" / "web-package-lock.json.txt"
FILES = {
    ".gitignore": (
        "data/\ndocs/lineage/\nnode_modules/\ncoverage/\n__pycache__/\n.pytest_cache/\n"
        "poetry.lock\n.coverage\ncoverage.json\n"
    ),
    "README.md": "A throwaway target with two test frameworks.\n",
    "pyproject.toml": PYPROJECT,
    "app.py": "def add(a, b):\n    return a + b\n",
    "tests/test_app.py": (
        "from app import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    ),
    "web/package.json": json.dumps(PACKAGE_JSON, indent=2) + "\n",
    "web/vitest.config.ts": (
        'import { defineConfig } from "vitest/config";\n\n'
        "export default defineConfig({});\n"
    ),
    "web/src/add.ts": "export const add = (a: number, b: number): number => a + b;\n",
    "web/tests/add.test.ts": (
        'import { expect, test } from "vitest";\n'
        'import { add } from "../src/add";\n\n'
        'test("adds", () => {\n  expect(add(2, 3)).toBe(5);\n});\n'
    ),
}


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def build_target(work: Path) -> tuple[Path, Path]:
    """The two-framework target and its bare origin, under `work`."""
    origin = work / "origin.git"
    root = work / "target"
    subprocess.run(
        ["git", "init", "-q", "--bare", "--initial-branch=main", str(origin)],
        capture_output=True, text=True, check=True,
    )
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "Test")
    for relative, text in FILES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (root / "web" / "package-lock.json").write_text(
        LOCK.read_text(encoding="utf-8"), encoding="utf-8"
    )
    git(root, "add", ".")
    git(root, "commit", "-qm", "base")
    git(root, "remote", "add", "origin", str(origin))
    git(root, "push", "-qu", "origin", "main")
    git(root, "remote", "set-head", "origin", "--auto")
    return root, origin


def _listing(path: Path) -> str:
    if not path.is_dir():
        return f"{path}: absent\n"
    return f"{path}:\n" + "".join(f"  {p.name}\n" for p in sorted(path.iterdir()))


def snapshot(root: Path, origin: Path, home: Path | None = None) -> str:
    """The three snapshots #3585's rehearsal compares, as one text."""
    home = home or Path.home()
    return "".join([
        "== status\n", git(root, "status", "--porcelain", "--untracked-files=all"),
        "== worktrees\n", git(root, "worktree", "list", "--porcelain"),
        "== branches\n", git(root, "branch", "-a"),
        "== origin refs\n", git(origin, "for-each-ref"),
        "== state\n",
        _listing(home / ".assemblyzero"),
        _listing(home / ".assemblyzero" / "workflow_state"),
        _listing(home / ".claude" / "assemblyzero"),
    ])


def _run_tool(argv: list[str], log: Path) -> int:
    with log.open("w", encoding="utf-8") as handle:
        return subprocess.run(
            [sys.executable, *argv], cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONUNBUFFERED": "1"},
            check=False,
        ).returncode


def mock_argv(root: Path) -> dict[str, list[str]]:
    """The two commands of the mock step, by name."""
    return {
        "lld": [
            "tools/run_requirements_workflow.py", "--type", "lld", "--issue", ISSUE,
            "--mock", "--yes", "--review", "none", "--repo", str(root),
            "--base-branch", "main",
        ],
        "impl": [
            "tools/run_implement_from_lld.py", "--issue", ISSUE, "--repo", str(root),
            "--mock", "--auto",
        ],
    }


def step_mock(work: Path, run: Run = _run_tool, home: Path | None = None) -> int:
    """Both workflows under --mock on the fixture. See the module docstring."""
    root, origin = build_target(work)
    before = snapshot(root, origin, home)
    (work / "snapshot-before.txt").write_text(before, encoding="utf-8")

    exits = {name: run(argv, work / f"{name}.log") for name, argv in mock_argv(root).items()}

    after = snapshot(root, origin, home)
    (work / "snapshot-after.txt").write_text(after, encoding="utf-8")
    impl_log = (work / "impl.log").read_text(encoding="utf-8", errors="replace")
    scaffolds = {
        "pytest": f"tests/test_issue_{ISSUE}.py" in impl_log,
        "vitest": f"web/tests/issue_{ISSUE}.test.ts" in impl_log,
    }
    same = before == after
    print(f"lld exit {exits['lld']}; impl exit {exits['impl']}")
    print(f"scaffolds written: {scaffolds}")
    print(f"snapshots identical: {same}")
    print(f"logs and snapshots: {work}")
    return 0 if (not any(exits.values()) and all(scaffolds.values()) and same) else 1


def step_provision(work: Path) -> int:
    """The installs and both suites, for real. See the module docstring."""
    from assemblyzero.workflows.provisioning import provision_worktree
    from assemblyzero.workflows.testing.framework_detector import TestFramework
    from assemblyzero.workflows.testing.nodes.verify_phases import get_runner

    root, _ = build_target(work)
    worktree = work / "run-worktree"
    git(root, "worktree", "add", "-q", "--detach", str(worktree), "main")
    for line in provision_worktree(worktree, mock=False):
        print(line)

    python = pytest_proof(worktree)
    vitest = get_runner(
        TestFramework.VITEST, str(worktree), working_directory="web"
    ).run_tests(test_paths=None)
    print(vitest["raw_output"][-600:])

    results = {
        "pytest": (python["passed"], python["exit"]),
        "vitest": (vitest.get("passed", 0), vitest.get("exit_code")),
    }
    print(f"both suites, passed and exit: {results}")
    for failure in python["failures"]:
        print(f"pytest: {failure}", file=sys.stderr)
    suites_ran = all(passed > 0 and code == 0 for passed, code in results.values())
    if python["failures"] or not suites_ran:
        print(f"the worktree stays, for diagnosis: {worktree}", file=sys.stderr)
        return 1
    _remove_worktree(root, worktree)
    return 0


def listed_plugins(output: str) -> list[str]:
    """The plugins pytest's header names. A pytest with none prints no such line."""
    for line in output.splitlines():
        if line.startswith("plugins: "):
            return [name.strip() for name in line.removeprefix("plugins: ").split(",")]
    return []


def pytest_proof(worktree: Path) -> dict:
    """What `run_pytest`, the gate's call, does in the worktree (#4490).

    Returns the whole suite's passed count and exit code, and `failures`, in
    words, for each thing that did not hold; none means all of it did.
    """
    from assemblyzero.workflows.target_env import hook_environment
    from assemblyzero.workflows.testing.nodes.verify_phases import (
        PhaseStepError,
        run_pytest,
    )

    failures: list[str] = []
    suite = run_pytest([], repo_root=worktree)
    print(suite["stdout"][-600:])
    if plugins := listed_plugins(suite["stdout"]):
        failures.append(f"listed plugins the fixture does not install: {plugins}")

    measured_args = {"coverage_module": "app", "repo_root": worktree}
    try:
        run_pytest(["tests/test_app.py"], **measured_args)
        failures.append("coverage ran in a target with no pytest-cov")
    except PhaseStepError as exc:
        if "pytest-cov" not in str(exc):
            failures.append(f"coverage was refused without naming pytest-cov: {exc}")

    subprocess.run(
        ["poetry", "install", "--with", "coverage"], cwd=worktree,
        env=hook_environment(), capture_output=True, text=True, check=True,
    )
    report = worktree / "coverage.json"
    measured = run_pytest(["tests/test_app.py"], coverage_report=report, **measured_args)
    print(measured["stdout"][-600:])
    plugins = listed_plugins(measured["stdout"])
    if len(plugins) != 1 or not plugins[0].startswith("cov-"):
        failures.append(f"with pytest-cov installed, the plugins listed were {plugins}")
    if measured["returncode"] != 0 or not report.is_file():
        failures.append(
            f"coverage was not measured: exit {measured['returncode']}, "
            f"report written: {report.is_file()}"
        )
    return {
        "passed": suite["parsed"].get("passed", 0),
        "exit": suite["returncode"],
        "failures": failures,
    }


def _remove_worktree(root: Path, worktree: Path) -> None:
    """A rehearsal that passed leaves no worktree and no Poetry environment."""
    env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    subprocess.run(["poetry", "env", "remove", "--all"], cwd=worktree, env=env, check=True)
    git(root, "worktree", "remove", str(worktree))
    print(f"removed the worktree and its environment: {worktree}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=["mock", "provision"])
    parser.add_argument("--work-dir", required=True, type=Path, help="A directory that does not exist yet")
    args = parser.parse_args(argv)

    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=False)
    code = step_mock(work) if args.step == "mock" else step_provision(work)
    print(f"{args.step}: {'PASS' if code == 0 else 'FAIL'}", file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
