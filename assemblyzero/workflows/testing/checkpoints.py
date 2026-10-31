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
1. **A failure is loud and raised (ADR 0236, #3810).** A checkpoint that
   cannot be committed writes an ERROR line to stderr and raises
   ``CheckpointError`` naming the worktree and git's stderr. It used to be
   best-effort: every failure printed "(non-fatal)" to stdout and returned
   False, which read the same as "nothing to commit", and the standalone
   finish then had to guess which it was (#4150). Nothing here alerts: the
   caller that can stop the run does, so one failure is one alert.
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

import logging
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)


class CheckpointError(RuntimeError):
    """A checkpoint commit or a measurement note failed. Raised, never returned."""


def _failed(tag: str, message: str) -> CheckpointError:
    """Say the failure at ERROR, on stderr and in the log; return the error to raise."""
    logger.error("[%s] %s", tag, message)
    print(f"ERROR [{tag}] {message}", file=sys.stderr, flush=True)
    return CheckpointError(message)


def _git_said(result: subprocess.CompletedProcess) -> str:
    """git's own words for a failed command: its stderr, else its stdout."""
    return (result.stderr or result.stdout or "").strip()[:400] or "(git printed nothing)"


# Paths excluded from checkpoint commits (workflow-internal, not user work).
# Named once: the standalone finish (#4150) reads this to tell a deliberate
# exclusion from work the final checkpoint failed to commit.
EXCLUDED_PATHS = (".assemblyzero", "data/lineage", "data/hourglass")

_GIT_TIMEOUT_S = 30


def commit_checkpoint(worktree_path: str | Path | None,
                       issue_number: int | str | None,
                       name: str) -> bool:
    """Stage and commit the current state of `worktree_path`. Local only.

    Args:
        worktree_path: Path to the git worktree to checkpoint. None (or "")
            means the caller named no worktree, so there is nothing to
            commit: a quiet False, which is an answer, not a failure. A path
            that is not a directory is a failure.
        issue_number: Issue number for the commit message reference. Can
            be int, str, or None (omitted from message).
        name: Checkpoint name -- inserted as `[CP:<name>]` in the commit
            message. Conventional values: "post-scaffold", "post-impl",
            "post-green".

    Returns:
        True if a checkpoint commit was created. False when no worktree was
        named or nothing was staged (git diff --cached exits 0).

    Raises:
        CheckpointError: the worktree is not a directory, or git add, git
            diff --cached or git commit failed, timed out or could not run
            (#3810). The message names the worktree and git's stderr, and an
            ERROR line has already gone to stderr.
    """
    if not worktree_path:
        return False
    wt = Path(worktree_path)
    tag = f"CP:{name}"
    if not wt.is_dir():
        raise _failed(
            tag,
            f"checkpoint {name}: the worktree {wt} is not a directory, so "
            "nothing could be committed",
        )

    def git(*args: str) -> subprocess.CompletedProcess:
        try:
            return _run(["git", "-C", str(wt), *args], timeout=_GIT_TIMEOUT_S)
        except (subprocess.TimeoutExpired, OSError) as e:
            raise _failed(
                tag,
                f"checkpoint {name} in {wt}: `git {args[0]}` could not run: "
                f"{type(e).__name__}: {e}",
            ) from e

    # Stage everything except workflow-internal dirs. An excluded path the
    # repository already ignores needs no exclusion: `-A` never stages an
    # ignored file, and naming an ignored path in a pathspec makes `git add`
    # exit 1 ("The following paths are ignored") with nothing wrong, which
    # since the raise above halted every run on a target that ignores data/
    # (#3585, found when the testing batches were joined).
    excludes: list[str] = []
    for path in EXCLUDED_PATHS:
        ignored = git("check-ignore", "-q", "--", path)
        if ignored.returncode == 1:
            excludes.append(f":!{path}")
        elif ignored.returncode != 0:
            raise _failed(
                tag,
                f"checkpoint {name} in {wt}: `git check-ignore {path}` failed "
                f"(exit {ignored.returncode}): {_git_said(ignored)}",
            )
    add = git("add", "-A", "--", ".", *excludes)
    if add.returncode != 0:
        raise _failed(
            tag,
            f"checkpoint {name} in {wt}: `git add` failed (exit "
            f"{add.returncode}): {_git_said(add)}",
        )

    # `--quiet` exits 0 for nothing staged and 1 for staged changes; any
    # other exit is git failing, not a diff.
    diff = git("diff", "--cached", "--quiet")
    if diff.returncode == 0:
        return False  # nothing to commit: an answer, not a failure
    if diff.returncode != 1:
        raise _failed(
            tag,
            f"checkpoint {name} in {wt}: `git diff --cached` failed (exit "
            f"{diff.returncode}): {_git_said(diff)}",
        )

    if issue_number is not None:
        msg = f"[CP:{name}] issue #{issue_number}: workflow checkpoint"
    else:
        msg = f"[CP:{name}] workflow checkpoint"

    commit = git("commit", "-m", msg)
    if commit.returncode != 0:
        raise _failed(
            tag,
            f"checkpoint {name} in {wt}: `git commit` failed (exit "
            f"{commit.returncode}): {_git_said(commit)}",
        )

    # No push. See the module docstring (#2339): the local commit IS the
    # recovery artifact, and the push that used to follow could only ever
    # fail loudly or succeed silently.
    return True


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
# checkpoint is. A note that cannot be written, and a note that cannot be
# read, raise ``CheckpointError`` like a failed checkpoint (#3810). They used
# to be best-effort: a failed write cost the next resume its choice without
# telling anyone, and a failed or corrupt read looked exactly like a commit
# never measured.

#: The notes ref carrying N5's measurement of a checkpoint commit.
MEASURE_NOTES_REF = "az-measure"

#: The note's fields, in the order ``record_measurement`` writes them:
#: ``passed=<int> total=<int> coverage=<float>``.
_MEASUREMENT_FIELDS = ("passed", "total", "coverage")


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
    """Note N5's result on HEAD of `worktree_path`. Local only.

    Returns True when the note was written. False only when no worktree was
    named or the path is not a directory (unchanged; not a ledger site).

    Raises:
        CheckpointError: `git notes add` failed, timed out or could not run
            (#3810). The message names the worktree, the note and git's
            stderr, and an ERROR line has already gone to stderr.
    """
    if not worktree_path:
        return False
    wt = Path(worktree_path)
    if not wt.is_dir():
        return False
    note = f"passed={int(passed)} total={int(total)} coverage={float(coverage):.1f}"
    what = f"measurement note {note!r} on HEAD of {wt}"
    try:
        result = _run(
            ["git", "-C", str(wt), "notes", f"--ref={MEASURE_NOTES_REF}",
             "add", "-f", "-m", note, "HEAD"],
            timeout=_GIT_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        raise _failed(
            "N5", f"{what}: `git notes add` could not run: {type(e).__name__}: {e}",
        ) from e
    if result.returncode != 0:
        raise _failed(
            "N5",
            f"{what}: `git notes add` failed (exit {result.returncode}): "
            f"{_git_said(result)}",
        )
    return True


def read_measurement(repo_path: str | Path, commit: str) -> Measurement | None:
    """The measurement noted on `commit`, or None when there is none.

    None means git said the commit carries no note (`git notes show` exits 1,
    "no note found"): the commit was never measured, and the caller takes the
    newest attempt instead (#2845). None also when no repository or no commit
    was named, since nothing was asked.

    Raises:
        CheckpointError: git could not run or failed any other way (no
            repository, an unknown commit), or the note is not
            ``passed=<int> total=<int> coverage=<float>`` (#3810). An
            unreadable measurement is not an unmeasured commit: reading it as
            one let a resume start from a worse attempt without a word. The
            message names the repository, the commit and the note's text.
    """
    if not repo_path or not commit:
        return None
    where = f"the measurement note on {commit} in {repo_path}"
    try:
        result = _run(
            ["git", "-C", str(repo_path), "notes", f"--ref={MEASURE_NOTES_REF}",
             "show", commit],
            timeout=_GIT_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        raise _failed(
            "resume", f"{where}: `git notes show` could not run: {type(e).__name__}: {e}",
        ) from e
    if result.returncode == 1 and not (result.stdout or "").strip():
        # git's "no note found for object": exit 1 is that and only that;
        # a missing repository or an unknown commit dies with 128.
        return None
    if result.returncode != 0:
        raise _failed(
            "resume",
            f"{where}: `git notes show` failed (exit {result.returncode}): "
            f"{_git_said(result)}",
        )
    return _parse_measurement(result.stdout or "", where)


def _parse_measurement(text: str, where: str) -> Measurement:
    """``passed=<int> total=<int> coverage=<float>``, or CheckpointError naming
    ``where`` and the text."""
    fields: dict[str, str] = {}
    for token in text.split():
        key, sep, value = token.partition("=")
        if not sep or key not in _MEASUREMENT_FIELDS or key in fields:
            raise _failed(
                "resume",
                f"{where} is corrupt: {token!r} is not one of the fields "
                f"{', '.join(_MEASUREMENT_FIELDS)} (note text {text.strip()!r})",
            )
        fields[key] = value
    missing = [key for key in _MEASUREMENT_FIELDS if key not in fields]
    if missing:
        raise _failed(
            "resume",
            f"{where} is corrupt: it has no {', '.join(missing)} "
            f"(note text {text.strip()!r})",
        )
    try:
        return Measurement(
            int(fields["passed"]), int(fields["total"]), float(fields["coverage"]),
        )
    except ValueError as e:
        raise _failed(
            "resume",
            f"{where}: its numbers do not convert ({e}; note text {text.strip()!r})",
        ) from e


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
