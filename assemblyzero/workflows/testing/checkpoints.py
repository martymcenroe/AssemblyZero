"""TDD workflow git checkpoints (Issue #689).

Each TDD node generates code (scaffolded tests in N2, implementation in N4,
verified-green state in N5) but does not commit. A crash, timeout, or
premature cleanup at any point loses everything since the last human commit.

The 2026-01-31 incident lost 6,114 lines of working code via worktree
deletion before commit. This module provides `commit_checkpoint()`, called
at the end of N2, N4, and N5 to stage and commit the current state.

Checkpoints are LOCAL (#2339)
-----------------------------

They do not push, and the worktree is no longer given an upstream at
creation for their benefit. Both halves of that were removed together.

run-issue7-192332 settled it. `origin/issue-7` was a stale remote branch
from an earlier run, so the upstream push at worktree creation was rejected
as non-fast-forward, so every checkpoint push failed with "no upstream
branch" and printed git's four-line advice into the run log. Four
checkpoints, four identical failures, and one operator reading a log that
looked like a broken run.

The same incident is the evidence for going local rather than repairing the
remote. Every checkpoint commit survived without ever reaching origin. The
chain was preserved on ``graveyard/issue-7-20260814T002812Z`` by the #2310
disposal discipline, and it is the only reason the post-mortem behind
#2337, #2338, #2339 and #2340 had anything to measure. A remote copy would
have added nothing that mattered on the one day it was tested.

Pushing the branch is the pr stage's job. That push is the run's product,
it is untouched here, and its own stale-remote reconcile landed in #2349.

Design rules:
1. **Best-effort.** Checkpoint failures must NOT fail the node they were
   protecting. The original work survives in the working tree either way;
   committing is a recovery convenience, not a correctness guarantee.
2. **Worktree-scoped.** Stages only files inside the worktree. Excludes
   workflow-internal dirs (.assemblyzero/, data/lineage/) so the checkpoint
   commits represent ONLY the work the human cares about.
3. **Squashable.** Commit message prefix `[CP:NAME]` is recognizable so
   the post-merge squash collapses them cleanly.
4. **Local only.** No network call, so no network failure to tolerate and
   no advice text to print. A run with no remote at all behaves the same as
   one with a healthy remote, which is what makes the checkpoint's outcome
   readable.
5. **Idempotent on empty.** If `git diff --cached` is empty after staging,
   skips the commit (no empty-commit pollution).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import NamedTuple

# Paths excluded from checkpoint commits (workflow-internal, not user work).
_EXCLUDE_PATHSPECS = (
    ":!.assemblyzero",
    ":!data/lineage",
    ":!data/hourglass",
)

_GIT_TIMEOUT_S = 30


def commit_checkpoint(worktree_path: str | Path | None,
                       issue_number: int | str | None,
                       name: str) -> bool:
    """Stage and commit the current state of `worktree_path`. Local only.

    Args:
        worktree_path: Path to the git worktree to checkpoint. If None or
            not a directory, no-op (returns False).
        issue_number: Issue number for the commit message reference. Can
            be int, str, or None (omitted from message).
        name: Checkpoint name -- inserted as `[CP:<name>]` in the commit
            message. Conventional values: "post-scaffold", "post-impl",
            "post-green".

    Returns:
        True if a checkpoint commit was created. False if no-op (no
        worktree, nothing to commit, or any failure -- failures are
        warned to stdout but never raised).
    """
    if not worktree_path:
        return False
    wt = Path(worktree_path)
    if not wt.is_dir():
        return False

    try:
        # Stage everything except workflow-internal dirs
        add_args = ["git", "-C", str(wt), "add", "-A", "--", "."]
        add_args.extend(_EXCLUDE_PATHSPECS)
        _run(add_args, timeout=_GIT_TIMEOUT_S)

        # Skip if nothing staged
        diff = _run(
            ["git", "-C", str(wt), "diff", "--cached", "--quiet"],
            timeout=_GIT_TIMEOUT_S,
        )
        if diff.returncode == 0:
            return False  # nothing to commit; benign

        if issue_number is not None:
            msg = f"[CP:{name}] issue #{issue_number}: workflow checkpoint"
        else:
            msg = f"[CP:{name}] workflow checkpoint"

        commit = _run(
            ["git", "-C", str(wt), "commit", "-m", msg],
            timeout=_GIT_TIMEOUT_S,
        )
        if commit.returncode != 0:
            print(f"  [CP:{name}] commit failed (non-fatal): "
                  f"{(commit.stderr or commit.stdout).strip()[:200]}")
            return False

        # No push. See the module docstring (#2339): the local commit IS the
        # recovery artifact, and the push that used to follow could only ever
        # fail loudly or succeed silently.
        return True

    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"  [CP:{name}] checkpoint failed (non-fatal): {e}")
        return False


# =============================================================================
# Measurements (#2867)
# =============================================================================
#
# A checkpoint commit says what the tree was; nothing said how good it was.
# `_restore_best` compares iterations within one run and dies with the
# worktree (#2005). Across runs the only survivors are the graveyard branches,
# and #2845's resume takes the newest of them -- which after a degrading run
# is the worst: boostgauge #4 preserved 44/47, then 41/44, then 37/41, and the
# next resume would have started from the last. The halt writes the failing
# count into error_message and the graves carry nothing a resume can read.
#
# N5 now notes its result on the commit it measured -- the post-impl
# checkpoint N4 just cut -- under `refs/notes/az-measure`. A note is keyed by
# the commit, so it survives the #2310 rename to `graveyard/` and any later
# branch that carries the commit, and it is local for the same reasons the
# checkpoint is. Best-effort like the checkpoint: a failed note is printed and
# the run goes on, because a measurement that cannot be recorded is not a
# reason to stop measuring.

#: The notes ref carrying N5's measurement of a checkpoint commit.
MEASURE_NOTES_REF = "az-measure"

_MEASUREMENT_RE = re.compile(
    r"passed=(\d+)\s+total=(\d+)\s+coverage=([0-9]+(?:\.[0-9]+)?)"
)


class Measurement(NamedTuple):
    """What N5 measured on one checkpoint: tests passing of total, coverage."""

    passed: int
    total: int
    coverage: float

    @property
    def score(self) -> tuple[int, float]:
        """Most passing first, then coverage -- the order `_restore_best` uses."""
        return (self.passed, self.coverage)

    def describe(self) -> str:
        return f"{self.passed} passing of {self.total} at {self.coverage:.0f}%"


def record_measurement(worktree_path: str | Path | None,
                       passed: int, total: int, coverage: float) -> bool:
    """Note N5's result on HEAD of `worktree_path`. Local only, best-effort.

    Returns True when the note was written. False on a missing worktree or
    any git failure -- warned to stdout, never raised.
    """
    if not worktree_path:
        return False
    wt = Path(worktree_path)
    if not wt.is_dir():
        return False
    note = f"passed={int(passed)} total={int(total)} coverage={float(coverage):.1f}"
    try:
        result = _run(
            ["git", "-C", str(wt), "notes", f"--ref={MEASURE_NOTES_REF}",
             "add", "-f", "-m", note, "HEAD"],
            timeout=_GIT_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        # fail-open: the note is a hint for a LATER resume, not this run's
        # verdict -- N5 has already measured and printed. A note that cannot
        # be written costs the next resume its preference (it takes the
        # newest attempt, #2845's behaviour), and the miss is printed here.
        print(f"    [N5] measurement note failed (non-fatal): {e}")
        return False
    if result.returncode != 0:
        print(f"    [N5] measurement note failed (non-fatal): "
              f"{(result.stderr or result.stdout).strip()[:200]}")
        return False
    return True


def read_measurement(repo_path: str | Path, commit: str) -> Measurement | None:
    """The measurement noted on `commit`, or None when there is none.

    None also for a repo git cannot read and for a note that does not parse:
    an unreadable measurement is no measurement, and the caller's fallback
    (newest attempt, #2845) is the behaviour that existed before notes did.
    """
    if not repo_path or not commit:
        return None
    try:
        result = _run(
            ["git", "-C", str(repo_path), "notes", f"--ref={MEASURE_NOTES_REF}",
             "show", commit],
            timeout=_GIT_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError):
        # fail-open: None is "no measurement", and no measurement is what
        # every checkpoint had before #2867. The caller then takes the newest
        # attempt, which is the pre-existing behaviour, not an invented one;
        # halting a resume because a note could not be read would cost the
        # whole preserved attempt to protect a preference.
        return None
    if result.returncode != 0:
        return None
    match = _MEASUREMENT_RE.search(result.stdout or "")
    if not match:
        return None
    try:
        return Measurement(
            int(match.group(1)), int(match.group(2)), float(match.group(3)),
        )
    except ValueError:
        # fail-open: same direction as the handler above -- a note that does
        # not parse is no measurement, and an unmeasured checkpoint is simply
        # not preferred. The regex admits only digits, so this is belt and
        # braces rather than a live path.
        return None


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    """subprocess.run with the encoding defaults from #837."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
