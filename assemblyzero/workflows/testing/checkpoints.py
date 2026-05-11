"""TDD workflow git checkpoints (Issue #689).

Each TDD node generates code (scaffolded tests in N2, implementation in N4,
verified-green state in N5) but does not commit. A crash, timeout, or
premature cleanup at any point loses everything since the last human commit.

The 2026-01-31 incident lost 6,114 lines of working code via worktree
deletion before commit. This module provides `commit_checkpoint()`, called
at the end of N2, N4, and N5 to stage + commit + push the current state.

Design rules:
1. **Best-effort.** Checkpoint failures must NOT fail the node they were
   protecting. The original work survives in the working tree either way;
   committing is a recovery convenience, not a correctness guarantee.
2. **Worktree-scoped.** Stages only files inside the worktree. Excludes
   workflow-internal dirs (.assemblyzero/, data/lineage/) so the checkpoint
   commits represent ONLY the work the human cares about.
3. **Squashable.** Commit message prefix `[CP:NAME]` is recognizable so
   the post-merge squash collapses them cleanly.
4. **Network-tolerant.** `git push` failures are warned but ignored --
   the local commit is the primary recovery artifact; remote backup is
   nice-to-have.
5. **Idempotent on empty.** If `git diff --cached` is empty after staging,
   skips the commit (no empty-commit pollution).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

# Paths excluded from checkpoint commits (workflow-internal, not user work).
_EXCLUDE_PATHSPECS = (
    ":!.assemblyzero",
    ":!data/lineage",
    ":!data/hourglass",
)

_GIT_TIMEOUT_S = 30
_PUSH_TIMEOUT_S = 60


def commit_checkpoint(worktree_path: str | Path | None,
                       issue_number: int | str | None,
                       name: str) -> bool:
    """Stage + commit + push the current state of `worktree_path`.

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

        # Push -- non-fatal if offline / no upstream / rejected
        push = _run(
            ["git", "-C", str(wt), "push"],
            timeout=_PUSH_TIMEOUT_S,
        )
        if push.returncode != 0:
            print(f"  [CP:{name}] commit OK, push failed (non-fatal): "
                  f"{(push.stderr or '').strip()[:200]}")

        return True

    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"  [CP:{name}] checkpoint failed (non-fatal): {e}")
        return False


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
