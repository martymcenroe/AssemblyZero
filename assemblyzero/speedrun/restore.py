"""Rebuild pipeline inputs from refs (#2571; machinery moved from speedrun_roll).

The working copy of a pipeline input is a cache, not a source of record.
Issue #331's LLD was deleted from the working tree three times in one day
(see #2551) and survived only on refs — the live `{issue}-lld` branch and
the janitor's preservation refs. This module is the search-and-materialize
half: whatever was preserved can be restored, and the LOADER can now do it
too, not just the speedrun resume planner.

Search order, verified against the measured incidents:

* the live `{issue}-lld` branch and its origin twin — the lld stage pushes
  the approved LLD there (boostgauge PR #366 was exactly that branch, and
  the only ref carrying `LLD-331.md` through the 2026-08-27 deletions);
* `graveyard/{issue}-lld-*` grafts — a HALT's RESTORE renames the branch
  to an archive name and keeps the commits (#2516);
* `graveyard/leavings-*` refs, newest first — where the file janitor
  preserves what it clears (standard 0027; the 2026-08-15 boostgauge #1
  incident in `restore_artifact`'s history was exactly two artifacts
  sitting on these, preserved, pushed, and one `git show` away).
"""

from __future__ import annotations

from pathlib import Path

from assemblyzero.speedrun.leavings import _run


def graveyard_leavings_refs(repo_root: Path) -> list[str]:
    """Every `graveyard/leavings-*` ref, newest first.

    These are where the file janitor PRESERVES what it clears. Nothing is
    deleted -- preserve-then-clear is structural (standard 0027) -- so a
    cleared artifact is always on one of these, and the newest is the one
    the last run wrote.
    """
    result = _run(
        [
            "git", "for-each-ref", "--format=%(refname:short)",
            "refs/heads/graveyard/leavings-*",
            "refs/remotes/origin/graveyard/leavings-*",
        ],
        cwd=repo_root,
    )
    if result.returncode != 0:
        return []
    refs = [
        line.strip()
        for line in (result.stdout or "").splitlines() if line.strip()
    ]

    # Sorted on the timestamp in the NAME, not on committerdate. Two
    # leavings refs cut in the same second tie under `--sort=-committerdate`
    # and git then falls back to refname ASCENDING -- oldest first, the
    # wrong way round, which a fixture caught. The name carries
    # `-YYYYMMDD-HHMMSS` by construction, so it orders these exactly and
    # cannot be perturbed by a rewrite that changes commit times.
    def _stamp(ref: str) -> str:
        _, _, tail = ref.rpartition("leavings-")
        return tail

    return sorted(refs, key=_stamp, reverse=True)


def graveyard_issue_lld_refs(repo_root: Path, issue: int) -> list[str]:
    """Every grafted copy of this issue's lld branch, newest first (#2516).

    A HALT's RESTORE preserves the attempt branch by renaming it to
    `graveyard/{issue}-lld-<UTC stamp>` (ADR 0217 keeps the commits; the
    rename frees the name). The stamp is in the NAME, so name order is
    time order -- same reasoning as `graveyard_leavings_refs`, same
    immunity to history rewrites perturbing committer dates.
    """
    result = _run(
        [
            "git", "for-each-ref", "--format=%(refname:short)",
            f"refs/heads/graveyard/{issue}-lld-*",
            f"refs/remotes/origin/graveyard/{issue}-lld-*",
        ],
        cwd=repo_root,
    )
    if result.returncode != 0:
        return []
    refs = [
        line.strip()
        for line in (result.stdout or "").splitlines() if line.strip()
    ]

    def _stamp(ref: str) -> str:
        _, _, tail = ref.rpartition("-lld-")
        return tail

    return sorted(refs, key=_stamp, reverse=True)


def input_refs(repo_root: Path, issue: int) -> list[str]:
    """The refs a missing input is rebuilt from, in search order."""
    refs = [f"{issue}-lld", f"origin/{issue}-lld"]
    # #2516: the grafted copies of the lld branch rank right behind the
    # live ones -- a HALT's RESTORE renames the branch to
    # graveyard/{issue}-lld-*, and what it holds IS the lld branch's
    # content under an archive name.
    refs += graveyard_issue_lld_refs(repo_root, issue)
    # Newest leavings first: the last run's copy is the current one, and
    # an older ref may hold a stale draft from a superseded attempt.
    refs += graveyard_leavings_refs(repo_root)
    return refs


def restore_artifact(
    repo_root: Path, issue: int, artifact: str, *, log=None
) -> bool:
    """Materialize a file from the refs so a stage can read it.

    The exit janitor clears pipeline-authored untracked files (standard
    0027). Two places hold what it cleared, and BOTH are searched: the
    issue's lld branch (when the draft was committed there) and the
    `graveyard/leavings-*` refs the janitor preserves onto.

    The second was missing once, and it is the difference between a resume
    and a redraw. Measured on boostgauge #1, 2026-08-15: neither
    `LLD-001.md` nor `spec-0001-implementation-readiness.md` was on disk,
    and NEITHER was on `1-lld` -- they were on
    `graveyard/leavings-20260815-161853` and `...-161847`. The restorer
    consulted only the lld branch, so it returned False and the resume was
    abandoned for artifacts that were preserved, pushed, and one
    `git show` away.

    #2571 moves this here so the LOADER can rebuild too: a working copy is
    a cache, and `find_lld_path` now rebuilds it from these refs before
    concluding absence instead of depending on an untracked file surviving.
    """
    path = Path(artifact)
    if path.is_file():
        return True
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        # fail-open: a path outside the repo cannot be on any of the
        # repo's refs; False is the honest "not restorable", exactly what
        # this returned when it lived in speedrun_roll (the move into the
        # audited package is what made the site newly visible).
        return False

    for ref in input_refs(repo_root, issue):
        show = _run(
            ["git", "show", f"{ref}:{rel.as_posix()}"], cwd=repo_root
        )
        if show.returncode == 0 and show.stdout:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(show.stdout, encoding="utf-8")
            if log is not None:
                log(f"[REBUILT] {rel.as_posix()} restored from '{ref}' (#2571)")
            return True
    return False
