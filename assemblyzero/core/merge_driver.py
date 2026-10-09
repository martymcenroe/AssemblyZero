"""Land a pull request through the fleet merge driver (#3704).

On the operator's machines `gh pr create`, `gh pr new` and `gh pr merge` are
refused to every process that is not the merge driver (`tracked_pr_land.py`):
the driver pushes the branch, opens the PR, waits for the checks, merges,
verifies the squash on the base branch, fast-forwards the primary checkout,
removes the worktree and deletes the branch. The LLD workflow used to push
and then call `gh pr create` itself, so every real run ended with a pushed
branch and no PR.

The driver's path is the machine's, not this repository's: it is read from
``AZ_MERGE_DRIVER``. A run that will need the driver checks for it at start
(`check_configured`) and refuses before any model call, so a missing setting
costs nothing.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

#: The environment variable naming the driver's path.
DRIVER_ENV = "AZ_MERGE_DRIVER"

#: What the driver prints, line by line, that a caller reads back. These are
#: the driver's own fixed lines, a closed set; no pattern matching is needed.
_CREATED = "created PR #"
_SQUASH = "squash SHA "
_LANDED = "[OK] stage=landed"


class MergeDriverError(Exception):
    """The driver is not configured, could not start, or did not land."""


@dataclass
class Landing:
    """What the driver reported."""

    pr_number: int | None
    squash_sha: str
    output: str
    argv: list[str] = field(default_factory=list)

    @property
    def pr_url(self) -> str:
        return f"#{self.pr_number}" if self.pr_number else ""


def check_configured(environ: dict[str, str] | None = None) -> str | None:
    """Why the driver cannot be used, or None when it can.

    The answer a preflight prints before a run spends anything.
    """
    env = os.environ if environ is None else environ
    value = (env.get(DRIVER_ENV) or "").strip()
    if not value:
        return (
            f"{DRIVER_ENV} is not set. A real LLD, implementation or orchestrated "
            "run lands its PR through the fleet merge driver (tracked_pr_land.py), "
            "because this machine's gh "
            "wrapper refuses `gh pr create` from anything else. Set it to the "
            "driver's absolute path and run again."
        )
    if not Path(value).is_file():
        return f"{DRIVER_ENV}={value!r} names no file."
    return None


def driver_path(environ: dict[str, str] | None = None) -> Path:
    """The driver's path, or MergeDriverError with the reason."""
    reason = check_configured(environ)
    if reason:
        raise MergeDriverError(reason)
    env = os.environ if environ is None else environ
    return Path(env[DRIVER_ENV].strip())


def build_argv(
    driver: Path,
    *,
    worktree: Path | str,
    branch: str,
    title: str,
    body_file: Path | str,
    issue: int | None = None,
    no_issue: bool = False,
    base: str | None = None,
    python: str | None = None,
) -> list[str]:
    """The driver's command line. One of `issue` and `no_issue` is required:
    the driver checks the title and body for the closing directive, or for the
    `No-Issue:` exemption line."""
    if (issue is None) == (not no_issue):
        raise ValueError("give exactly one of issue=N and no_issue=True")
    argv = [
        python or sys.executable, str(driver),
        "--repo", str(Path(worktree).resolve()),
        "--branch", branch,
        "--title", title,
        "--body-file", str(Path(body_file).resolve()),
    ]
    if no_issue:
        argv.append("--no-issue")
    else:
        argv += ["--issue", str(issue)]
    if base:
        argv += ["--base", base]
    return argv


def parse_output(output: str) -> tuple[int | None, str, bool]:
    """(PR number, squash SHA, landed) from the driver's stdout."""
    pr_number: int | None = None
    squash = ""
    landed = False
    for raw in output.splitlines():
        line = raw.strip()
        if line.startswith(_CREATED):
            rest = line[len(_CREATED):].split()
            if rest and rest[0].isdigit():
                pr_number = int(rest[0])
        elif line.startswith(_SQUASH):
            rest = line[len(_SQUASH):].split()
            if rest:
                squash = rest[0]
        elif line.startswith(_LANDED):
            landed = True
    return pr_number, squash, landed


def land(
    *,
    worktree: Path | str,
    branch: str,
    title: str,
    body_file: Path | str,
    issue: int | None = None,
    no_issue: bool = False,
    base: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    environ: dict[str, str] | None = None,
) -> Landing:
    """Run the driver and return what it reported.

    The driver pushes, opens, waits, merges and cleans up; nothing here
    touches git or gh. Any failure is MergeDriverError carrying the driver's
    own output, and nothing is retried: the driver's refusals are decisions.
    """
    driver = driver_path(environ)
    argv = build_argv(
        driver, worktree=worktree, branch=branch, title=title, body_file=body_file,
        issue=issue, no_issue=no_issue, base=base,
    )
    try:
        proc = runner(argv, capture_output=True, text=True, check=False)
    except OSError as e:
        raise MergeDriverError(f"the merge driver could not start: {e}") from e
    output = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    pr_number, squash, landed = parse_output(proc.stdout or "")
    if proc.returncode != 0 or not landed:
        raise MergeDriverError(
            f"the merge driver did not land {branch} (exit {proc.returncode}):\n{output.strip()}"
        )
    return Landing(pr_number=pr_number, squash_sha=squash, output=output, argv=argv)
