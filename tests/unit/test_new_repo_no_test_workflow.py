"""A new repository gets no workflow that runs tests or a linter on GitHub (#4712).

The operator, 2026-11-11: "shut it off fleet-wide. i simply do NOT understand why i ever
did it. and even AZ. why take the extra time and tokens." A repository's tests run on his
machine before a branch lands; a GitHub job that repeats them takes runner time and holds
the merge. The scaffolder has never written one. These tests hold that, so a later change
that adds one fails here instead of spreading to every repository created after it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

_TOOLS = Path(__file__).resolve().parent.parent.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from new_repo import create_github_workflows

# The closed set of test and lint commands a workflow step might run. Every member is
# written here; a command not on the list is not looked for. Each is matched as a whole
# word or phrase in a step's `run:` text.
TEST_AND_LINT_COMMANDS = (
    "pytest",
    "unittest",
    "tox",
    "nox",
    "vitest",
    "jest",
    "mocha",
    "playwright",
    "npm test",
    "npm run test",
    "yarn test",
    "pnpm test",
    "go test",
    "cargo test",
    "ruff",
    "flake8",
    "pylint",
    "mypy",
    "eslint",
    "shellcheck",
    "npm run lint",
)


def running_test_jobs(workflow_text: str) -> list[str]:
    """Job ids whose steps run a listed command, unless the job's `if:` is literally false."""
    doc = yaml.safe_load(workflow_text) or {}
    found = []
    for job_id, job in (doc.get("jobs") or {}).items():
        if job.get("if") is False:
            continue
        runs = " \n".join(str(step.get("run", "")) for step in job.get("steps") or []
                          if step.get("if") is not False)
        if any(re.search(rf"(?<![\w-]){re.escape(c)}(?![\w-])", runs) for c in TEST_AND_LINT_COMMANDS):
            found.append(job_id)
    return found


@pytest.mark.parametrize("enable_pypi, expected", [
    (True, ["auto-reviewer.yml", "release.yml"]),
    (False, ["auto-reviewer.yml"]),
])
def test_the_scaffolder_writes_only_the_known_workflows(tmp_path: Path, enable_pypi, expected):
    create_github_workflows(tmp_path, enable_pypi=enable_pypi)
    written = sorted(p.name for p in (tmp_path / ".github" / "workflows").iterdir())
    assert written == expected


@pytest.mark.parametrize("enable_pypi", [True, False])
def test_no_workflow_the_scaffolder_writes_runs_a_test_or_lint_job(tmp_path: Path, enable_pypi):
    create_github_workflows(tmp_path, enable_pypi=enable_pypi)
    for wf in (tmp_path / ".github" / "workflows").iterdir():
        assert running_test_jobs(wf.read_text(encoding="utf-8")) == [], wf.name


def _workflow(run: str, job_if: str = "") -> str:
    cond = f"    if: {job_if}\n" if job_if else ""
    return ("name: t\non:\n  pull_request:\njobs:\n  check:\n" + cond
            + "    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v7\n"
            + f"      - run: {run} --flag\n")


@pytest.mark.parametrize("command", TEST_AND_LINT_COMMANDS)
def test_the_check_catches_each_listed_command(command):
    assert running_test_jobs(_workflow(command)) == ["check"]


@pytest.mark.parametrize("command", TEST_AND_LINT_COMMANDS)
def test_a_job_set_if_false_is_not_running(command):
    assert running_test_jobs(_workflow(command, job_if="false")) == []


def test_a_command_inside_a_longer_word_is_not_a_match():
    assert running_test_jobs(_workflow("echo pytestish-banner")) == []
