"""Pipeline worktree placement and stranded-worktree sweep (#2077).

Operator directive 2026-08-01: pipeline worktrees stop appearing as siblings in
`~/Projects`. Two parts, and they are independent.

**Placement.** A roll's worktrees move from `Projects/<repo>-<issue>` to
`<repo>/data/worktrees/<name>`. `data/` is already gitignored in every campaign
repo, so a roll adds nothing to `~/Projects` and nothing to `git status`.

**Sweep.** At launcher start, every pipeline worktree is swept -- not only the
issue about to be rolled. The old behaviour self-healed one issue and left the
rest, which is how ten accumulated in a single day.

| State | Action |
|---|---|
| clean, registered | plain `git worktree remove` |
| dirty, registered | commit to `graveyard/<branch>-<timestamp>`, push, then plain remove |
| on disk, not registered | move under `data/worktrees/orphaned/`, never delete |

**Nothing here deletes content, on any path.** Dirty work is committed to a
branch before its worktree goes; an unregistered directory is relocated, never
removed. That is what lets this ship without waiting on a proven archive.

**Never `--force`, anywhere.** A worktree that resists a plain remove is a fact
to surface, not to overpower -- it is reported by name and the roll continues.
`test_sweep_source_contains_no_force` asserts this against this file's source.

**Every failure reaches the operator (ADR 0236, #3585).** A worktree list that
cannot be read raises before anything moves, because reading it as "nothing
registered" would relocate every pipeline worktree as an orphan. Each entry
the sweep cannot finish alerts the operator with its cause, a graveyard push
that fails keeps the worktree, ReadOnly clearing raises rather than clear part
of a tree, and an unexpected OSError alerts and stops the sweep.
"""

from __future__ import annotations

import logging
import re
import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from assemblyzero.core import alert
from assemblyzero.speedrun.preserved import record_preserved

logger = logging.getLogger(__name__)

_WHERE = "assemblyzero/speedrun/worktrees.py"

WORKTREES_REL = Path("data/worktrees")
ORPHANED_DIRNAME = "orphaned"

# `<issue>` or `<issue>-lld`. Deliberately strict: the sweep walks directories
# that sit beside a real repo, and a loose glob would pull in anything sharing
# the repo's name prefix. Only names this pattern produces are ever touched.
_PIPELINE_NAME = re.compile(r"^\d+(-lld)?$")

_TS_FMT = "%Y%m%d-%H%M%S"


def _now_tag() -> str:
    return datetime.now().strftime(_TS_FMT)


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------


def worktrees_root(repo: Path | str) -> Path:
    return Path(repo) / WORKTREES_REL


def orphaned_root(repo: Path | str) -> Path:
    return worktrees_root(repo) / ORPHANED_DIRNAME


def pipeline_worktree_path(repo: Path | str, issue: int, *, lld: bool = False) -> Path:
    """Where a roll's worktree lives: `<repo>/data/worktrees/<issue>[-lld]`."""
    name = f"{issue}-lld" if lld else f"{issue}"
    return worktrees_root(repo) / name


def legacy_worktree_path(repo: Path | str, issue: int, *, lld: bool = False) -> Path:
    """The pre-#2077 sibling location, still swept so old debris is found."""
    repo = Path(repo)
    suffix = f"{issue}-lld" if lld else f"{issue}"
    return repo.parent / f"{repo.name}-{suffix}"


# ---------------------------------------------------------------------------
# Discovery and classification
# ---------------------------------------------------------------------------


class WorktreeSweepError(RuntimeError):
    """git could not answer a question the sweep needs answered."""


def registered_worktrees(repo: Path) -> set[Path]:
    """Every worktree git has registered for `repo`, resolved.

    A `git worktree list` that fails alerts the operator and raises
    `WorktreeSweepError` with its exit code and stderr. An empty set here
    would make every pipeline worktree look unregistered, and the sweep would
    relocate each one as an orphan.
    """
    result = _run(["git", "-C", str(repo), "worktree", "list", "--porcelain"])
    paths: set[Path] = set()
    if result.returncode != 0:
        cause = (
            f"git -C {repo} worktree list exited {result.returncode}: "
            f"{(result.stderr or '').strip()}"
        )
        alert.alert_operator(
            what="list the registered worktrees", where=f"{_WHERE} registered_worktrees",
            cause=cause,
            consequence="no pipeline worktree is swept or counted; nothing is moved",
            repo=str(repo),
        )
        raise WorktreeSweepError(cause)
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            paths.add(Path(line[len("worktree ") :].strip()).resolve())
    return paths


def discover_pipeline_worktrees(repo: Path | str) -> list[Path]:
    """Every pipeline worktree directory, in both the old and new locations.

    Scans siblings named `<repo>-<issue>[-lld]` and entries under
    `<repo>/data/worktrees/`. The `orphaned/` holding area is never a candidate
    -- relocating an already-relocated directory would loop.
    """
    repo = Path(repo).resolve()
    found: list[Path] = []

    parent = repo.parent
    if parent.is_dir():
        prefix = repo.name + "-"
        for entry in sorted(parent.iterdir()):
            if not entry.is_dir() or not entry.name.startswith(prefix):
                continue
            if _PIPELINE_NAME.match(entry.name[len(prefix) :]):
                found.append(entry)

    managed = worktrees_root(repo)
    if managed.is_dir():
        for entry in sorted(managed.iterdir()):
            if entry.is_dir() and _PIPELINE_NAME.match(entry.name):
                found.append(entry)

    return found


def is_dirty(path: Path) -> bool:
    """True when the worktree holds uncommitted or untracked content."""
    result = _run(["git", "-C", str(path), "status", "--porcelain"])
    if result.returncode != 0:
        # Cannot read its state. Treated as dirty so the preserve path runs
        # rather than the remove path -- unknown is never "safe to discard".
        # The failure itself is the operator's to know (ADR 0236).
        alert.alert_operator(
            what=f"read the state of pipeline worktree {path.name}",
            where=f"{_WHERE} is_dirty",
            cause=(
                f"git -C {path} status exited {result.returncode}: "
                f"{(result.stderr or '').strip()}"
            ),
            consequence="the worktree is treated as dirty and preserved, never discarded",
            repo=str(path),
        )
        return True
    return bool(result.stdout.strip())


def current_branch(path: Path) -> str | None:
    result = _run(["git", "-C", str(path), "branch", "--show-current"])
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------


@dataclass
class SweepEntry:
    path: Path
    state: str  # clean | dirty | orphan
    action: str  # removed | preserved-and-removed | relocated | reported
    ok: bool = True
    branch: str | None = None
    detail: str = ""

    def describe(self) -> str:
        bits = f"{self.path.name}: {self.state} -> {self.action}"
        if self.branch:
            bits += f" ({self.branch})"
        if self.detail:
            bits += f" -- {self.detail}"
        return bits


@dataclass
class SweepResult:
    entries: list[SweepEntry] = field(default_factory=list)

    @property
    def problems(self) -> list[SweepEntry]:
        return [e for e in self.entries if not e.ok]

    def summary(self) -> str:
        if not self.entries:
            return "worktree sweep: nothing to do"
        return f"worktree sweep: {len(self.entries)} handled, {len(self.problems)} reported"


#: Windows refuses to delete a directory carrying FILE_ATTRIBUTE_READONLY, and
#: git reports it as `Permission denied` from `worktree remove`. Measured
#: 2026-08-09 against boostgauge: all 8 registered clean worktrees failed that
#: way, every directory in each tree carrying the attribute -- the worktree
#: root, `src`, `.venv`, and the `logs`/`refs` dirs under
#: `.git/worktrees/<name>`.
#:
#: #2136 asked what in the pipeline sets it. Measured 2026-08-12: nothing does.
#: The attribute is ambient across the whole Projects tree -- 100% of top-level
#: directories in boostgauge, AssemblyZero, Aletheia and Talos carry it,
#: including `.mypy_cache`, `.ruff_cache` and `.github`, which no pipeline code
#: has ever touched -- while a fresh `mkdir` does not. So the pipeline cannot
#: stop producing these trees, which makes clearing-and-retrying the fix rather
#: than a mask.
_READONLY = 0x1


def _is_permission_error(stderr: str) -> bool:
    lowered = (stderr or "").lower()
    return "permission denied" in lowered or "access is denied" in lowered


def _readonly_failed(step: str, target: Path, exc: OSError) -> None:
    logger.error(
        "[SWEEP] clearing ReadOnly: cannot %s %s: %s: %s",
        step, target, type(exc).__name__, exc,
    )


def clear_readonly(root: Path) -> int:
    """Clear the ReadOnly attribute across a tree. Returns dirs+files changed.

    An absent root is 0, and so is a filesystem with no ReadOnly attribute:
    off Windows `os.stat` has no `st_file_attributes`, and there is nothing to
    clear. A tree that cannot be listed, a path that cannot be stat'd, and a
    chmod that fails log at ERROR and re-raise the `OSError` (ADR 0236): a
    partly cleared tree used to return as if the clearing had worked, and the
    sweep then reported the retry's failure without its cause.
    """
    if not root.exists():
        return 0
    if not hasattr(os.stat(root), "st_file_attributes"):
        return 0

    try:
        targets: list[Path] = [root, *root.rglob("*")]
    except OSError as exc:
        _readonly_failed("list the tree under", root, exc)
        raise

    changed = 0
    for target in targets:
        try:
            attrs = os.stat(target).st_file_attributes
        except OSError as exc:
            _readonly_failed("stat", target, exc)
            raise
        if not attrs & _READONLY:
            continue
        try:
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
        except OSError as exc:
            _readonly_failed("chmod", target, exc)
            raise
        changed += 1
    return changed


def _remove_worktree(repo: Path, path: Path, log) -> subprocess.CompletedProcess:
    """Plain `git worktree remove`, retried once after clearing ReadOnly.

    NEVER `--force`, here or anywhere in this module. Clearing the attribute
    makes the PLAIN path work rather than bypassing the check that refuses a
    dirty tree -- the module's no-force invariant is intact, and its source
    test still passes.
    """
    removed = _run(["git", "-C", str(repo), "worktree", "remove", str(path)])
    if removed.returncode == 0 or not _is_permission_error(removed.stderr):
        return removed

    admin = repo / ".git" / "worktrees" / path.name
    cleared = clear_readonly(path) + clear_readonly(admin)
    if not cleared:
        return removed

    log(f"    cleared ReadOnly on {cleared} path(s) under {path.name}; retrying")
    return _run(["git", "-C", str(repo), "worktree", "remove", str(path)])


def _sweep_failed(
    repo: Path,
    path: Path,
    state: str,
    *,
    what: str,
    cause: str,
    consequence: str,
    detail: str,
    where: str,
    action: str = "reported",
    branch: str | None = None,
) -> SweepEntry:
    """Alert the operator about one entry the sweep could not finish.

    The entry is still returned and the sweep goes on to the next worktree:
    each is handled on its own, and nothing here deletes content, so stopping
    would only strand the rest.
    """
    alert.alert_operator(
        what=what, where=f"{_WHERE} {where}", cause=cause,
        consequence=consequence, repo=str(repo),
    )
    return SweepEntry(path, state, action, ok=False, branch=branch, detail=detail)


def _preserve_dirty(repo: Path, path: Path, log) -> SweepEntry:
    """Commit a dirty worktree's content to a graveyard branch, then remove it."""
    branch = current_branch(path) or "detached"
    grave = f"graveyard/{branch}-{_now_tag()}"

    created = _run(["git", "-C", str(path), "checkout", "-b", grave])
    if created.returncode != 0:
        return SweepEntry(
            path, "dirty", "reported", ok=False,
            detail=f"could not create {grave}: {created.stderr.strip()}",
        )

    added = _run(["git", "-C", str(path), "add", "-A"])
    if added.returncode != 0:
        stderr = (added.stderr or "").strip()
        return _sweep_failed(
            repo, path, "dirty", where="_preserve_dirty", branch=grave,
            what=f"stage stranded worktree {path.name} for preservation on {grave}",
            cause=f"git add -A exited {added.returncode}: {stderr}",
            consequence=(
                "nothing is committed and the worktree is kept as it was; "
                "a commit now would preserve less than the tree holds"
            ),
            detail=f"git add -A failed: {stderr}",
        )
    committed = _run([
        "git", "-C", str(path), "commit",
        "-m", f"chore(graveyard): preserve stranded worktree {path.name}",
    ])
    if committed.returncode != 0 and "nothing to commit" not in committed.stdout.lower():
        return SweepEntry(
            path, "dirty", "reported", ok=False, branch=grave,
            detail=f"commit failed: {committed.stderr.strip() or committed.stdout.strip()}",
        )

    pushed = _run(["git", "-C", str(path), "push", "-u", "origin", grave])

    # #2355: write down what was preserved, as it is preserved. The archiver
    # used to infer the set from a `graveyard/<run>*` prefix this line has
    # never produced, so it bundled none of them. Written even when the push
    # failed: the local branch holds the content either way.
    unrecorded = ""
    try:
        record_preserved(
            repo, grave, source="sweep", detail=f"stranded worktree {path.name}"
        )
    except (OSError, ValueError) as exc:
        unrecorded = f"{type(exc).__name__}: {exc}"
        alert.alert_operator(
            what=f"record graveyard branch {grave} in the preserved-branch ledger",
            where=f"{_WHERE} _preserve_dirty",
            cause=unrecorded,
            consequence=(
                "the archive finds the branch only by its graveyard/ prefix, with "
                "no attribution; the content is safe on the branch"
            ),
            repo=str(repo),
        )

    if pushed.returncode != 0:
        # ADR 0236 (#3585): the local branch holds the content, but a branch
        # that exists only here is not preserved against this checkout going,
        # so the worktree stays until the push can be made.
        stderr = (pushed.stderr or "").strip()
        return _sweep_failed(
            repo, path, "dirty", where="_preserve_dirty", branch=grave,
            what=f"push graveyard branch {grave} for stranded worktree {path.name}",
            cause=f"git push exited {pushed.returncode}: {stderr}",
            consequence=(
                f"the worktree is kept; its content is committed to {grave}, "
                "which exists only in this checkout"
            ),
            detail=f"committed to {grave} but the push failed, so not removed: {stderr}",
        )

    removed = _remove_worktree(repo, path, log)
    if removed.returncode != 0:
        stderr = (removed.stderr or "").strip()
        return _sweep_failed(
            repo, path, "dirty", where="_preserve_dirty", branch=grave,
            what=f"remove stranded worktree {path.name} after preserving it on {grave}",
            cause=f"git worktree remove exited {removed.returncode}: {stderr}",
            consequence=f"the worktree stays registered and on disk; its content is on {grave}",
            detail=f"preserved on {grave} but not removed: {stderr}",
        )
    if unrecorded:
        return SweepEntry(
            path, "dirty", "preserved-and-removed", ok=False, branch=grave,
            detail=f"not recorded in the preserved-branch ledger: {unrecorded}",
        )
    return SweepEntry(path, "dirty", "preserved-and-removed", branch=grave)


def _relocate_orphan(repo: Path, path: Path) -> SweepEntry:
    """Move an unregistered directory into the holding area. Never deletes."""
    dest_root = orphaned_root(repo)
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / f"{path.name}-{_now_tag()}"
    try:
        shutil.move(str(path), str(dest))
    except OSError as exc:
        return _sweep_failed(
            repo, path, "orphan", where="_relocate_orphan",
            what=f"relocate unregistered pipeline directory {path.name}",
            cause=f"{type(exc).__name__}: {exc}",
            consequence="the directory stays where it is; nothing in it is deleted",
            detail=f"could not relocate: {exc}",
        )
    return SweepEntry(dest, "orphan", "relocated", detail=f"from {path}")


def _log_to_stderr(msg: str) -> None:
    """The sweep's log when the caller passes none: never a no-op (ADR 0236)."""
    sys.stderr.write(f"{msg}\n")


def sweep_pipeline_worktrees(repo: Path | str, *, log=None) -> SweepResult:
    """Sweep every pipeline worktree, not only the issue being rolled.

    Returns a result describing what happened to each. A worktree the sweep
    cannot finish is reported by name, and the operator is alerted with its
    cause, and the sweep goes on to the next. A worktree list git cannot give,
    or an unexpected OSError, alerts and raises: the first before anything
    moves, the second at the worktree it hit. With no `log`, every line goes
    to stderr.
    """
    repo = Path(repo).resolve()
    log = log or _log_to_stderr
    result = SweepResult()

    registered = registered_worktrees(repo)

    for path in discover_pipeline_worktrees(repo):
        resolved = path.resolve()
        try:
            if resolved not in registered:
                entry = _relocate_orphan(repo, resolved)
            elif is_dirty(resolved):
                entry = _preserve_dirty(repo, resolved, log)
            else:
                removed = _remove_worktree(repo, resolved, log)
                if removed.returncode == 0:
                    entry = SweepEntry(resolved, "clean", "removed")
                else:
                    stderr = (removed.stderr or "").strip()
                    entry = _sweep_failed(
                        repo, resolved, "clean", where="sweep_pipeline_worktrees",
                        what=f"remove clean pipeline worktree {resolved.name}",
                        cause=f"git worktree remove exited {removed.returncode}: {stderr}",
                        consequence="the worktree stays registered and on disk",
                        detail=f"git declined to remove it: {stderr}",
                    )
        except OSError as exc:
            log(f"  ERROR: {path.name}: {type(exc).__name__}: {exc}")
            alert.alert_operator(
                what=f"sweep pipeline worktree {path.name}",
                where=f"{_WHERE} sweep_pipeline_worktrees",
                cause=f"{type(exc).__name__}: {exc}",
                consequence=(
                    f"the sweep stops at {path.name}; it and any worktree after "
                    "it are not handled"
                ),
                repo=str(repo),
            )
            raise

        result.entries.append(entry)
        log(f"  {entry.describe()}")

    # No repo-wide prune: on a Windows + WSL machine it drops the other side's
    # live worktrees, which each side sees as stale (#4232). Each worktree above
    # was removed by name.
    log(f"  {result.summary()}")
    return result
