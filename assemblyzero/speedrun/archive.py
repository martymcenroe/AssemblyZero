"""Archive a completed speedrun as one compact, restorable record (#2076).

An arc is never merged to main, so the product of a run exists only on
integration branches, in `graveyard/*` attempt branches, in the events /
heartbeat / stdout triplets under the log dir, and in lineage and reset
artifacts. Nothing is lost, but nothing is compact either -- the record of a
run is smeared across branches, logs, lineage dirs and PR history.

This module gathers all of it into `data/speedrun/archives/<run>/`.

## Design decisions

**Run membership is read, not guessed.** The launcher writes
`BASE '<branch>' verified clean for #<issue>` and `LAUNCH base=<branch>` into
every roll's events log. That is a recorded fact tying a roll to a run, so
rolls are selected by parsing it rather than by pattern-matching tag names.
Tag naming across the existing arcs is inconsistent enough (`run-issue4-111608`,
`run11b-issue4-234552`, `run11-roll10-issue-4`) that any name-based rule would
silently mis-bin rolls.

**Unknown is not zero.** Every component that cannot be read is named in
`index.json`, flips `complete` to false, and makes the command exit nonzero. A
partial archive must never be reportable as a complete one, because a false
"archived" is what would later authorize a deletion.

**Orphans are a first-class component, not a defensive branch.** Verified
2026-08-02: `boostgauge-2` and `boostgauge-2-lld` exist as directories on disk,
are absent from `git worktree list`, and their branches were deleted by a
reset. An archiver that enumerates a run by walking worktrees or branches sees
neither and reports success over content it never read.

**This module never deletes anything.** It writes archives. Deletion is gated
on a verified restore and is out of scope by issue.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from assemblyzero.speedrun.preserved import (
    claimed_by_other_run,
    recorded_for,
)

ARCHIVES_REL = Path("data/speedrun/archives")
DEFAULT_LOG_REL = Path("data/speedrun/runs")
RESET_ARTIFACTS_REL = Path("data/speedrun/reset-artifacts")
LINEAGE_REL = Path("docs/lineage")
WORKTREES_REL = Path("data/worktrees")

EVENTS_SUFFIX = "-events.log"
INDEX_NAME = "index.json"
INDEX_VERSION = 1

# `git bundle` packs objects, and pack thread count changes delta selection and
# therefore the output bytes. Pinned to one thread so archiving the same run
# twice produces the same bundle, which is what makes manifests comparable.
# Do not remove: the "identical manifest" test is the regression alarm for it.
_DETERMINISTIC_PACK = ["-c", "pack.threads=1"]

_RE_START = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) START issue=#(?P<issue>\d+)"
)
_RE_BASE = re.compile(r"BASE '(?P<base>[^']+)'")
_RE_LAUNCH = re.compile(r"LAUNCH base=(?P<base>\S+)")
_RE_EXIT = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) EXIT rc=(?P<rc>-?\d+)"
)
_TS_FMT = "%Y-%m-%d %H:%M:%S"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class Component:
    """One archived component and whether it could be read in full."""

    name: str
    ok: bool
    detail: str = ""

    def as_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


@dataclass
class Roll:
    """One roll of one issue, reconstructed from its events log."""

    tag: str
    issue: int | None = None
    base: str | None = None
    start: str | None = None
    end: str | None = None
    outcome: str = "unknown"
    duration_s: float | None = None
    files: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "tag": self.tag,
            "issue": self.issue,
            "base": self.base,
            "start": self.start,
            "end": self.end,
            "outcome": self.outcome,
            "duration_s": self.duration_s,
            "files": sorted(self.files),
        }


@dataclass
class ArchiveResult:
    path: Path
    complete: bool
    components: list[Component]
    index: dict

    @property
    def missing(self) -> list[str]:
        return [c.name for c in self.components if not c.ok]


# ---------------------------------------------------------------------------
# git helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, args: list[str], *, config: list[str] | None = None):
    return subprocess.run(
        ["git", *(config or []), "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _ref_exists(repo: Path, ref: str) -> bool:
    return _git(repo, ["rev-parse", "--verify", "--quiet", ref]).returncode == 0


def _rev(repo: Path, ref: str) -> str | None:
    result = _git(repo, ["rev-parse", ref])
    return result.stdout.strip() if result.returncode == 0 else None


def local_branches(repo: Path) -> list[str]:
    result = _git(repo, ["for-each-ref", "--format=%(refname:short)", "refs/heads/"])
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def graveyard_branches_for(repo: Path, run: str) -> list[str]:
    """Graveyard branches to bundle with `run`. Recorded fact, then measurement.

    This matched ``graveyard/<run>*`` until #2355. The pipeline never writes
    that name. It writes ``graveyard/issue-7-<stamp>`` from the worktree
    preserve step, ``graveyard/7-lld-<stamp>``, and
    ``graveyard/leavings-<stamp>`` from the leavings sweep, none of which
    carry the run prefix. Archiving hardening-run-17 on 2026-08-14 reported
    ``graveyard 0`` against a campaign holding sixty-four of them, and still
    called the archive complete.

    Two sources now, in this order:

    1. **The ledger** (`preserved.py`), written by the preserve steps as they
       preserve. A recorded fact about what this pipeline actually did, which
       a naming convention never was.
    2. **Measured discovery** of every ``graveyard/*`` branch the ledger does
       not attribute to a DIFFERENT run. The sixty-four branches that already
       exist predate the ledger, and losing them is the failure being
       repaired. Only a positive attribution elsewhere excludes a branch:
       over-inclusion costs disk in a tool that only ever writes, while
       under-inclusion costs the evidence record.

    `index.json` records which source produced each branch, so an audit can
    tell a recorded preservation from a discovered one.
    """
    recorded = recorded_for(repo, run)
    claimed = claimed_by_other_run(repo, run)

    matched = {
        branch
        for branch in local_branches(repo)
        if branch.startswith("graveyard/") and branch not in claimed
    }
    matched |= {b for b in recorded if b in set(local_branches(repo))}
    return sorted(matched)


def graveyard_sources(repo: Path, run: str, branches: list[str]) -> dict[str, str]:
    """Where each bundled branch came from, for the index's audit trail."""
    recorded = recorded_for(repo, run)
    return {b: ("ledger" if b in recorded else "discovered") for b in branches}


# ---------------------------------------------------------------------------
# Roll discovery
# ---------------------------------------------------------------------------


def parse_events_log(path: Path) -> Roll:
    """Reconstruct one roll from its events log.

    Raises OSError if the log cannot be read -- callers turn that into an
    incomplete component rather than swallowing it.
    """
    tag = path.name[: -len(EVENTS_SUFFIX)]
    roll = Roll(tag=tag)
    text = path.read_text(encoding="utf-8", errors="replace")

    for line in text.splitlines():
        start = _RE_START.match(line)
        if start and roll.start is None:
            roll.start = start.group("ts")
            roll.issue = int(start.group("issue"))
            continue
        base = _RE_BASE.search(line) or _RE_LAUNCH.search(line)
        if base and roll.base is None:
            roll.base = base.group("base")
            continue
        exited = _RE_EXIT.match(line)
        if exited:
            roll.end = exited.group("ts")
            rc = int(exited.group("rc"))
            roll.outcome = "success" if rc == 0 else f"failed rc={rc}"

    if roll.end is None:
        # No EXIT line: the roll was killed, or is still running. Either way the
        # outcome is genuinely unknown and must not be rendered as a failure.
        roll.outcome = "incomplete"

    if roll.start and roll.end:
        started = datetime.strptime(roll.start, _TS_FMT)
        ended = datetime.strptime(roll.end, _TS_FMT)
        roll.duration_s = (ended - started).total_seconds()

    return roll


def discover_rolls(log_dir: Path, run: str) -> tuple[list[Roll], list[Component]]:
    """Every roll whose events log names `run` as its base branch."""
    rolls: list[Roll] = []
    problems: list[Component] = []

    if not log_dir.is_dir():
        return rolls, [Component(f"logs ({log_dir})", False, "log directory not found")]

    for events in sorted(log_dir.glob(f"*{EVENTS_SUFFIX}")):
        try:
            roll = parse_events_log(events)
        except OSError as exc:
            problems.append(
                Component(f"logs/{events.name}", False, f"unreadable: {exc}")
            )
            continue
        if roll.base != run:
            continue
        for sibling in (
            events,
            log_dir / f"{roll.tag}.log",
            log_dir / f"{roll.tag}-heartbeat.log",
        ):
            if sibling.exists():
                roll.files.append(sibling.name)
        rolls.append(roll)

    return rolls, problems


# ---------------------------------------------------------------------------
# Orphan worktrees
# ---------------------------------------------------------------------------


def registered_worktrees(repo: Path) -> set[Path]:
    result = _git(repo, ["worktree", "list", "--porcelain"])
    paths: set[Path] = set()
    if result.returncode != 0:
        return paths
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            paths.add(Path(line[len("worktree ") :].strip()).resolve())
    return paths


def find_orphan_worktrees(repo: Path) -> list[Path]:
    """Directories that look like pipeline worktrees but git does not register.

    Both layouts are scanned: the pre-#2077 siblings at `<parent>/<repo>-<n>`
    and the post-#2077 home at `<repo>/data/worktrees/<name>`. An orphan is a
    directory containing a `.git` entry that is absent from `git worktree list`.
    """
    repo = repo.resolve()
    registered = registered_worktrees(repo)
    candidates: list[Path] = []

    sibling_prefix = repo.name + "-"
    parent = repo.parent
    if parent.is_dir():
        for entry in sorted(parent.iterdir()):
            if entry.is_dir() and entry.name.startswith(sibling_prefix):
                candidates.append(entry)

    managed = repo / WORKTREES_REL
    if managed.is_dir():
        for entry in sorted(managed.iterdir()):
            if entry.is_dir() and entry.name != "orphaned":
                candidates.append(entry)

    orphans = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in registered:
            continue
        if not (resolved / ".git").exists():
            continue
        orphans.append(resolved)
    return orphans


# ---------------------------------------------------------------------------
# Archiving
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


#: Set when the archiver has had to clear a ReadOnly attribute, so recurrence
#: stays visible rather than silent. Read by `archive_run` for the result note.
_readonly_cleared: list[str] = []


def readonly_clearings() -> list[str]:
    """Paths whose ReadOnly attribute this process had to clear (#2404)."""
    return list(_readonly_cleared)


def _reset_readonly_clearings() -> None:
    _readonly_cleared.clear()


def _clear_readonly(path: Path) -> bool:
    """Drop FILE_ATTRIBUTE_READONLY from `path`. True when it was cleared.

    #2404: a successful roll's auto-archive died with `[WinError 5] Access is
    denied` on an EMPTY directory carrying the Windows ReadOnly attribute --
    the signature #2277 forensically attributed to Google Drive for Desktop's
    attribute-setting. A sweep found 62 such directories under
    `data/speedrun/archives/`.

    The setter has a standing presence, so a one-time manual `attrib -r` sweep
    is not a durable repair: the tool has to tolerate the attribute rather than
    assume its absence.
    """
    try:
        os.chmod(path, stat.S_IWRITE)
    except OSError:
        return False
    _readonly_cleared.append(str(path))
    return True


def _on_permission_error(func, path, _exc_info) -> None:
    """`shutil` error hook: clear ReadOnly, retry once, then let it raise."""
    if _clear_readonly(Path(path)):
        func(path)


def _copy_tree(src: Path, dest: Path) -> None:
    """Copy, tolerating ReadOnly on the source or an existing destination.

    `copytree` copies metadata with `copy2`, so a ReadOnly source file yields a
    ReadOnly destination -- and a re-archive over it then fails on the write.
    Both directions are handled: the destination is made writable before the
    retry, and the source's attribute is cleared only if it is what blocked.
    """
    try:
        shutil.copytree(src, dest, dirs_exist_ok=True)
        return
    except (PermissionError, shutil.Error):
        # `copytree` collects per-file failures and raises `shutil.Error`
        # wrapping them, so catching PermissionError alone never fires -- the
        # first cut of this repair did exactly that and the fixture still saw
        # WinError 5. A non-permission failure is retried once here too and
        # then raises on its own terms, which is the same outcome it had before.
        pass

    # Retry with the destination tree made writable. The source is left alone
    # unless it is itself unreadable -- clearing attributes on the operator's
    # own files is not the archiver's business.
    if dest.exists():
        for path in [dest, *dest.rglob("*")]:
            _clear_readonly(path)
    shutil.copytree(src, dest, dirs_exist_ok=True, copy_function=_copy_writable)


def _copy_writable(src: str, dst: str) -> None:
    """`copy2`, then make the copy writable.

    A ReadOnly source produces a ReadOnly archive, which makes the NEXT
    re-archive fail in exactly the way this repair exists to prevent. The
    archive is our own artifact, so it is ours to keep writable.
    """
    shutil.copy2(src, dst)
    try:
        os.chmod(dst, stat.S_IWRITE)
    except OSError:
        pass


def _rmtree(path: Path) -> None:
    """Remove a tree, clearing ReadOnly on whatever blocks it."""
    shutil.rmtree(path, onexc=_on_permission_error)


def _build_manifest(root: Path) -> dict[str, str]:
    """sha256 for every archived file, keyed by POSIX path relative to root.

    `index.json` itself is excluded -- it carries the manifest, so it cannot
    also be inside it.
    """
    manifest: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == INDEX_NAME:
            continue
        manifest[rel] = _sha256(path)
    return dict(sorted(manifest.items()))


def archive_run(
    repo: Path,
    run: str,
    *,
    out_dir: Path | None = None,
    log_dir: Path | None = None,
    extra_branches: list[str] | None = None,
) -> ArchiveResult:
    """Capture `run` as a restorable record. Writes only; never deletes."""
    repo = Path(repo).resolve()
    log_dir = Path(log_dir) if log_dir else repo / DEFAULT_LOG_REL
    dest = Path(out_dir) if out_dir else repo / ARCHIVES_REL / run

    _reset_readonly_clearings()

    if dest.exists():
        # Re-archiving must be idempotent, and a stale file left from an earlier
        # partial run would otherwise be hashed into the new manifest.
        # #2404: ReadOnly-attributed directories under the archives tree make
        # this raise WinError 5, which is how a successful roll's archive died.
        _rmtree(dest)
    (dest / "logs").mkdir(parents=True, exist_ok=True)
    (dest / "artifacts").mkdir(parents=True, exist_ok=True)
    (dest / "orphans").mkdir(parents=True, exist_ok=True)

    components: list[Component] = []

    # --- branches + bundle ------------------------------------------------
    integration_sha = _rev(repo, run) if _ref_exists(repo, run) else None
    graveyard = graveyard_branches_for(repo, run)
    graveyard_source = graveyard_sources(repo, run, graveyard)
    for extra in extra_branches or []:
        if extra not in graveyard and extra != run:
            graveyard.append(extra)
            graveyard_source[extra] = "explicit"
    graveyard = sorted(set(graveyard))

    refs = ([run] if integration_sha else []) + graveyard
    bundle_rel = f"{run}.bundle"
    bundle_path = dest / bundle_rel

    if integration_sha is None:
        components.append(
            Component(
                f"branch {run}", False, "integration branch not found in this repo"
            )
        )

    if not refs:
        components.append(
            Component(bundle_rel, False, "no refs to bundle: nothing to capture")
        )
    else:
        result = _git(
            repo,
            ["bundle", "create", str(bundle_path), *refs],
            config=_DETERMINISTIC_PACK,
        )
        if result.returncode != 0 or not bundle_path.exists():
            components.append(
                Component(bundle_rel, False, f"git bundle failed: {result.stderr.strip()}")
            )
        else:
            verify = _git(repo, ["bundle", "verify", str(bundle_path)])
            if verify.returncode != 0:
                components.append(
                    Component(
                        bundle_rel, False, f"bundle verify failed: {verify.stderr.strip()}"
                    )
                )
            else:
                components.append(Component(bundle_rel, True))

    # --- logs -------------------------------------------------------------
    rolls, log_problems = discover_rolls(log_dir, run)
    components.extend(log_problems)
    for roll in rolls:
        for name in roll.files:
            src = log_dir / name
            try:
                shutil.copy2(src, dest / "logs" / name)
            except OSError as exc:
                components.append(
                    Component(f"logs/{name}", False, f"unreadable: {exc}")
                )
    if rolls:
        components.append(Component("logs", True, f"{len(rolls)} roll(s)"))

    # --- artifacts --------------------------------------------------------
    lineage = repo / LINEAGE_REL
    issues = {str(r.issue) for r in rolls if r.issue is not None}
    if lineage.is_dir():
        for entry in sorted(lineage.rglob("*")):
            if not entry.is_dir():
                continue
            head = entry.name.split("-")[0]
            if head not in issues:
                continue
            try:
                _copy_tree(entry, dest / "artifacts" / "lineage" / entry.name)
            except OSError as exc:
                components.append(
                    Component(
                        f"artifacts/lineage/{entry.name}", False, f"unreadable: {exc}"
                    )
                )

    reset_artifacts = repo / RESET_ARTIFACTS_REL
    if reset_artifacts.is_dir():
        try:
            _copy_tree(reset_artifacts, dest / "artifacts" / "reset-artifacts")
        except OSError as exc:
            components.append(
                Component("artifacts/reset-artifacts", False, f"unreadable: {exc}")
            )

    # --- orphans ----------------------------------------------------------
    orphan_records = []
    for orphan in find_orphan_worktrees(repo):
        tar_name = f"{orphan.name}.tar.gz"
        try:
            with tarfile.open(dest / "orphans" / tar_name, "w:gz") as tar:
                tar.add(orphan, arcname=orphan.name)
        except OSError as exc:
            components.append(
                Component(f"orphans/{tar_name}", False, f"unreadable: {exc}")
            )
            continue
        orphan_records.append(
            {"name": orphan.name, "source": str(orphan), "archive": f"orphans/{tar_name}"}
        )
        components.append(Component(f"orphans/{tar_name}", True))

    # --- index ------------------------------------------------------------
    manifest = _build_manifest(dest)
    complete = all(c.ok for c in components)

    index = {
        "index_version": INDEX_VERSION,
        "run": run,
        "repo": str(repo),
        "created_ts_local": datetime.now().strftime(_TS_FMT),
        "complete": complete,
        "incomplete_components": [c.as_dict() for c in components if not c.ok],
        "components": [c.as_dict() for c in components],
        "branches": {
            "integration": {"name": run, "sha": integration_sha},
            "graveyard": [
                {
                    "name": b,
                    "sha": _rev(repo, b),
                    "source": graveyard_source.get(b, "explicit"),
                }
                for b in graveyard
            ],
            # #2355: the rule used to be a prefix the pipeline never writes.
            # It is now what was recorded plus what was measured, and each
            # branch above says which of the two produced it.
            "graveyard_match_rule": (
                "the preserved-branch ledger for this run, plus every "
                "refs/heads/graveyard/* not attributed to another run"
            ),
        },
        "bundle": bundle_rel if bundle_path.exists() else None,
        "rolls": [r.as_dict() for r in rolls],
        "orphans": orphan_records,
        "manifest": manifest,
    }

    (dest / INDEX_NAME).write_text(
        json.dumps(index, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )

    return ArchiveResult(path=dest, complete=complete, components=components, index=index)


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


class RestoreRefused(RuntimeError):
    """Raised when an incomplete archive is restored without an explicit force."""


def _materialize_branches(repo_dest: Path, index: dict) -> None:
    """Recreate the run's branches by name in a restored clone.

    Cloning a bundle lands its refs as remote-tracking `origin/*` only, so
    without this the restored repo has the objects but no branch called
    `hardening-run-15` -- which is the name a human restoring an arc is looking
    for. Branches are created from the SHAs recorded in `index.json`, so a
    restore that cannot reproduce a recorded tip fails loudly instead of
    quietly producing a repo missing an arc.
    """
    branches = index.get("branches", {})
    wanted: list[tuple[str, str]] = []
    integration = branches.get("integration") or {}
    if integration.get("name") and integration.get("sha"):
        wanted.append((integration["name"], integration["sha"]))
    for entry in branches.get("graveyard", []):
        if entry.get("name") and entry.get("sha"):
            wanted.append((entry["name"], entry["sha"]))

    for name, sha in wanted:
        existing = subprocess.run(
            ["git", "-C", str(repo_dest), "rev-parse", "--verify", "--quiet", name],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if existing.returncode == 0:
            if existing.stdout.strip() != sha:
                raise RuntimeError(
                    f"restored branch {name} is at {existing.stdout.strip()}, "
                    f"archive recorded {sha}"
                )
            continue
        created = subprocess.run(
            ["git", "-C", str(repo_dest), "branch", name, sha],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if created.returncode != 0:
            raise RuntimeError(
                f"could not restore branch {name} at {sha}: {created.stderr.strip()}"
            )


def restore_archive(archive_dir: Path, dest: Path, *, force: bool = False) -> dict:
    """Unbundle into a fresh clone and lay logs and artifacts beside it."""
    archive_dir = Path(archive_dir).resolve()
    dest = Path(dest)

    index_path = archive_dir / INDEX_NAME
    index = json.loads(index_path.read_text(encoding="utf-8"))

    if not index.get("complete", False) and not force:
        missing = ", ".join(
            c["name"] for c in index.get("incomplete_components", [])
        ) or "unspecified components"
        raise RestoreRefused(
            f"archive is marked incomplete (missing: {missing}); "
            f"pass force to restore it anyway"
        )

    dest.mkdir(parents=True, exist_ok=True)
    repo_dest = dest / "repo"

    bundle = index.get("bundle")
    if bundle:
        bundle_path = archive_dir / bundle
        result = subprocess.run(
            ["git", "clone", str(bundle_path), str(repo_dest)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone from bundle failed: {result.stderr.strip()}")
        _materialize_branches(repo_dest, index)

    for name in ("logs", "artifacts", "orphans"):
        src = archive_dir / name
        if src.is_dir():
            _copy_tree(src, dest / name)

    shutil.copy2(index_path, dest / INDEX_NAME)
    return index


def verify_manifest(archive_dir: Path) -> list[str]:
    """Files whose on-disk sha256 no longer matches the recorded manifest."""
    archive_dir = Path(archive_dir)
    index = json.loads((archive_dir / INDEX_NAME).read_text(encoding="utf-8"))
    mismatched = []
    for rel, expected in index.get("manifest", {}).items():
        path = archive_dir / rel
        if not path.is_file() or _sha256(path) != expected:
            mismatched.append(rel)
    return mismatched


@dataclass
class VerifyResult:
    """Both dimensions of "is this archive trustworthy", in one answer."""

    complete: bool
    missing: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)
    file_count: int = 0
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.complete and not self.mismatched and not self.error


def verify_archive(archive_dir: Path) -> VerifyResult:
    """Whether an archive is complete AND intact (#2354).

    `verify_manifest` answers only "the files I did capture have not rotted".
    An archive marked incomplete at archive time -- a named component that
    could not be read -- passed with "manifest OK" if its captured files
    hashed correctly. That is the vacuous-pass class: the one command whose
    name promises the archive is trustworthy answered a narrower question
    than the one being asked.

    Completeness used to live only in the archive-time exit code, which is
    gone by the time anyone re-verifies. It is recorded in index.json, so it
    is read here.

    Both dimensions are reported. They fail independently and the caller gets
    one exit code, because an operator asking "can I trust this box" wants an
    answer, not two.
    """
    archive_dir = Path(archive_dir)
    index_path = archive_dir / INDEX_NAME

    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # No index is not an intact archive with a missing extra. It is an
        # archive that cannot state anything about itself, and reporting that
        # as a pass would be the same vacuous answer one level up.
        return VerifyResult(
            complete=False,
            error=f"{INDEX_NAME} could not be read: {exc}",
        )

    complete = index.get("complete") is True
    missing = [
        entry.get("name", "(unnamed)")
        for entry in index.get("incomplete_components", [])
    ]
    if not complete and not missing:
        missing = ["(the index records no component detail)"]

    mismatched = []
    manifest = index.get("manifest", {})
    for rel, expected in manifest.items():
        path = archive_dir / rel
        if not path.is_file() or _sha256(path) != expected:
            mismatched.append(rel)

    return VerifyResult(
        complete=complete,
        missing=missing,
        mismatched=mismatched,
        file_count=len(manifest),
    )
