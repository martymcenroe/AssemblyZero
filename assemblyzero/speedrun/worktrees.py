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
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

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


def registered_worktrees(repo: Path) -> set[Path]:
    result = _run(["git", "-C", str(repo), "worktree", "list", "--porcelain"])
    paths: set[Path] = set()
    if result.returncode != 0:
        return paths
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

    _run(["git", "-C", str(path), "add", "-A"])
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
    if pushed.returncode != 0:
        # The local branch already holds the content, so the work is safe. A
        # push failure is reported and the sweep proceeds; refusing here would
        # strand the worktree again for a reason unrelated to its content.
        log(f"    push of {grave} failed (content is safe on the local branch)")

    removed = _run(["git", "-C", str(repo), "worktree", "remove", str(path)])
    if removed.returncode != 0:
        return SweepEntry(
            path, "dirty", "reported", ok=False, branch=grave,
            detail=f"preserved on {grave} but not removed: {removed.stderr.strip()}",
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
        return SweepEntry(
            path, "orphan", "reported", ok=False, detail=f"could not relocate: {exc}"
        )
    return SweepEntry(dest, "orphan", "relocated", detail=f"from {path}")


def sweep_pipeline_worktrees(repo: Path | str, *, log=None) -> SweepResult:
    """Sweep every pipeline worktree, not only the issue being rolled.

    Returns a result describing what happened to each. Never raises for a
    single bad worktree: one that cannot be handled is reported by name and the
    caller continues, because a stuck directory must not cost a roll.
    """
    repo = Path(repo).resolve()
    log = log or (lambda _msg: None)
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
                removed = _run(["git", "-C", str(repo), "worktree", "remove", str(resolved)])
                if removed.returncode == 0:
                    entry = SweepEntry(resolved, "clean", "removed")
                else:
                    entry = SweepEntry(
                        resolved, "clean", "reported", ok=False,
                        detail=f"git declined to remove it: {removed.stderr.strip()}",
                    )
        except OSError as exc:  # pragma: no cover - defensive
            entry = SweepEntry(path, "unknown", "reported", ok=False, detail=str(exc))

        result.entries.append(entry)
        log(f"  {entry.describe()}")

    _run(["git", "-C", str(repo), "worktree", "prune"])
    log(f"  {result.summary()}")
    return result
