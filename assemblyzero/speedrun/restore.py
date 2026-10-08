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

from assemblyzero.core.settlement import sha256_text
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


def _main_checkout(repo_root: Path) -> Path:
    """The primary checkout of the repo `repo_root` belongs to (#3764).

    A stage runs in a worktree, but the durable LLD copy and the settlement
    record live in the primary checkout's gitignored lineage and data.
    """
    result = _run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=repo_root,
    )
    common = (result.stdout or "").strip()
    if result.returncode != 0 or not common:
        return repo_root
    return Path(common).parent


def _settled_lld_sha(main: Path, issue: int) -> str | None:
    """The content hash of the issue's settled LLD, or None with no record."""
    from assemblyzero.workflows.requirements.audit import load_settlement

    record = load_settlement(issue, "lld", main)
    if not isinstance(record, dict):
        return None
    return record.get("artifact_sha256") or None


def _sources(
    repo_root: Path, issue: int, rel: Path, base: str
) -> list[tuple[str, str]]:
    """Where a missing input is rebuilt from, in order (#3764).

    Each entry is (kind, where): kind "file" is a path on disk, "ref" a git
    ref. The newest authoritative copy comes first:

    * the durable handoff copy (#3750), for the LLD only;
    * the base the run builds on: ``origin/<base>`` when the caller knows it,
      then this checkout's ``HEAD``, which a worktree cut from the base holds;
    * the live ``<N>-lld`` branch, which is the LLD before it lands;
    * the graveyard refs, last, because their newest match may be months old.
    """
    from assemblyzero.workflows.requirements.nodes.finalize import durable_lld_path

    sources: list[tuple[str, str]] = []
    if rel.name == f"LLD-{issue:03d}.md":
        durable = durable_lld_path(_main_checkout(repo_root), issue)
        sources.append(("file", str(durable)))
    if base:
        sources.append(("ref", f"origin/{base}"))
    sources.append(("ref", "HEAD"))
    sources += [("ref", ref) for ref in input_refs(repo_root, issue)]
    return sources


def restore_artifact(
    repo_root: Path, issue: int, artifact: str, *, log=None, base: str = ""
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

    #3764: since the merge driver deletes `<N>-lld` after landing, the search
    used to fall through to the graveyard, and boostgauge #2
    (run-issue2-052813) was implemented against an August draft. The durable
    copy and the base now come first (`_sources`). A graveyard copy that is
    not the settled LLD, by content hash, is refused and named, never used.
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

    is_lld = rel.name == f"LLD-{issue:03d}.md"
    settled_sha = _settled_lld_sha(_main_checkout(repo_root), issue) if is_lld else None

    for kind, where in _sources(repo_root, issue, rel, base):
        if kind == "file":
            source = Path(where)
            if not source.is_file():
                continue
            content = source.read_text(encoding="utf-8")
        else:
            show = _run(
                ["git", "show", f"{where}:{rel.as_posix()}"], cwd=repo_root
            )
            if show.returncode != 0 or not show.stdout:
                continue
            content = show.stdout
            if (
                "graveyard/" in where
                and settled_sha
                and sha256_text(content) != settled_sha
            ):
                if log is not None:
                    log(
                        f"[REFUSED] {rel.as_posix()} on '{where}' is not the "
                        f"settled LLD (settled {settled_sha[:12]}, this copy "
                        f"{sha256_text(content)[:12]}); not used (#3764)"
                    )
                continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if log is not None:
            log(f"[REBUILT] {rel.as_posix()} restored from '{where}' (#2571, #3764)")
        return True
    return False
