"""Pipeline file leavings: classify, preserve, clear (#2144, #2145, #2146).

Standard 0027: the machinery cleans up after itself; it never hands its mess
to the operator. The worktree sweep (#2077) is the reference janitor for
worktrees; this module is its sibling for FILES the pipeline emits into the
target repo's main checkout -- the run-16 LLD droppings that sat untracked
for eight days and then blocked two launches (2026-08-09).

## The authorship line

The janitor only ever touches untracked files under `EMISSION_ALLOWLIST`,
the pipeline's known write sites in a target repo. Everything else is
presumed to be the operator's work: reported by name, never preserved on the
operator's behalf, never deleted. Refusal is reserved for content the
machinery cannot prove it authored.

## Preserve, then clear -- structurally

A leaving is removed from the working tree only after it is reachable from a
pushed graveyard ref. Commit or push failure leaves the file exactly where it
was, reported. The preserving commit is built through a TEMPORARY index
(`GIT_INDEX_FILE`), so the checkout's HEAD, real index, and working tree are
never touched by the preservation itself.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from assemblyzero.speedrun.preserved import record_preserved

#: Where the pipeline writes files into a target repo's main checkout.
#: Grounded in the actual write sites: `workflows/requirements/audit.py`
#: saves approved LLDs to docs/lld/active/; draft specs land in
#: docs/lld/drafts/. Extend deliberately, never wildcard -- the allowlist IS
#: the proof of authorship.
EMISSION_ALLOWLIST = (
    "docs/lld/active/",
    "docs/lld/drafts/",
)

#: #2551: the CURRENT roll's canonical inputs are not leavings. The LLD
#: working copy at docs/lld/active/LLD-{issue}.md is untracked on the main
#:  checkout (main does not carry it; the arc branch does), so the sweep
#: classified it as leavings and preserved-and-cleared it three times on
#: 2026-08-27 -- including once at LAUNCH, before the run had done
#: anything -- and every later stage (and every resume) then read its own
#: input's canonical path and found it gone. The patterns mirror the
#: loader's exactly (`find_lld_path` / `find_spec_path` in
#: workflows/testing/nodes/load_lld.py): what the loader would resolve for
#: the rolling issue is an input; every OTHER issue's file at these paths
#: stays genuine leavings -- the run-16 droppings that this janitor was
#: built to clear (#2144) are still cleared.
_INPUT_GLOB_TEMPLATES = (
    "docs/lld/active/LLD-{padded3}.md",
    "docs/lld/active/LLD-{padded3}-*.md",
    "docs/lld/active/LLD-{issue}.md",
    "docs/lld/active/LLD-{issue}-*.md",
    "docs/lld/drafts/spec-{padded4}.md",
    "docs/lld/drafts/spec-{padded4}-*.md",
    "docs/lld/drafts/spec-{padded3}.md",
    "docs/lld/drafts/spec-{padded3}-*.md",
    "docs/lld/drafts/spec-{issue}.md",
    "docs/lld/drafts/spec-{issue}-*.md",
)


def pipeline_input_globs(issue: int) -> tuple[str, ...]:
    """The canonical input paths the loader resolves for ``issue``."""
    return tuple(
        template.format(
            issue=issue, padded3=f"{issue:03d}", padded4=f"{issue:04d}"
        )
        for template in _INPUT_GLOB_TEMPLATES
    )


def is_pipeline_input(rel_path: str, issues) -> bool:
    """True when ``rel_path`` is a canonical input for any rolling issue."""
    from fnmatch import fnmatch

    normalized = rel_path.replace("\\", "/")
    return any(
        fnmatch(normalized, glob)
        for issue in (issues or ())
        for glob in pipeline_input_globs(int(issue))
    )


GRAVEYARD_LEAVINGS_PREFIX = "graveyard/leavings"

_TS_FMT = "%Y%m%d-%H%M%S"


def _run(
    cmd: list[str], cwd: Path | None = None, env: dict | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _now_tag() -> str:
    return datetime.now().strftime(_TS_FMT)


@dataclass
class LeavingsEntry:
    path: str          # repo-relative, forward slashes
    action: str        # preserved-and-cleared | reported
    ok: bool = True
    detail: str = ""

    def describe(self) -> str:
        bits = f"{self.path}: {self.action}"
        if self.detail:
            bits += f" -- {self.detail}"
        return bits


@dataclass
class LeavingsResult:
    entries: list[LeavingsEntry] = field(default_factory=list)
    branch: str | None = None

    @property
    def problems(self) -> list[LeavingsEntry]:
        return [e for e in self.entries if not e.ok]

    def summary(self) -> str:
        if not self.entries:
            return "file janitor: nothing to do"
        kept = f" (preserved on {self.branch})" if self.branch else ""
        return (
            f"file janitor: {len(self.entries)} handled, "
            f"{len(self.problems)} reported{kept}"
        )


#: The machinery's own record (heals, telemetry, run logs). Standard 0027
#: exempts evidence from every janitor; #2164 taught us it must ALSO be
#: exempt from dirt classification structurally, not just by gitignore
#: convention -- in a repo that does not ignore data/, the healing ledger
#: itself blocked the branch-cutter's preconditions.
#:
#: #2311 adds docs/lineage/ for the same reason, and the reason is worth
#: stating because the issue argued the opposite. It observed that boostgauge
#: gitignores docs/lineage/ (`.gitignore:145`) while docs/lld/drafts/ is not
#: ignored, and concluded the lineage location is therefore "janitor-immune by
#: the janitor's own selection rule". That is true only in boostgauge. The
#: selection rule is `?? ` lines from `git status`, so the immunity comes
#: entirely from that repo's .gitignore -- a convention the next target repo
#: may not have, and precisely the dependency #2164 already removed for
#: data/speedrun/ after it bit. Lineage is evidence (#2250 exists to make
#: failures diagnosable after the fact) and now carries the resume handoff, so
#: it is exempt here, structurally, in every repo.
_EVIDENCE_PREFIXES = ("data/speedrun/", "docs/lineage/")


def _is_evidence(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/")
    return any(normalized.startswith(p) for p in _EVIDENCE_PREFIXES)


def untracked_files(repo: Path | str) -> list[str]:
    """Repo-relative untracked files, individually (-uall expands dirs).

    Evidence under data/speedrun/ never appears: usually because data/ is
    gitignored, and structurally even when it is not (the exemption must
    not depend on a convention a target repo might miss).
    """
    result = _run(
        ["git", "-C", str(repo), "status", "--porcelain", "-uall"]
    )
    if result.returncode != 0:
        return []
    return [
        path
        for line in result.stdout.splitlines()
        if line.startswith("?? ")
        and not _is_evidence(path := line[3:].strip().strip('"'))
    ]


def is_machinery_owned(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in EMISSION_ALLOWLIST)


def classify_dirt(
    repo: Path | str, *, protect_issues=()
) -> tuple[list[str], list[str]]:
    """(machinery-owned untracked, operator-owned dirt) as porcelain lines.

    Machinery-owned: untracked AND under the emission allowlist -- ours to
    preserve and clear. Operator-owned: every other dirty entry (tracked
    modifications of any kind, untracked outside the allowlist) -- named,
    never touched.

    ``protect_issues`` (#2551): the issues currently rolling. Their
    canonical input files (the LLD the loader resolves, the spec-draft
    fallback) are neither machinery leavings nor operator dirt -- they are
    the pipeline's own input at the path every stage and every resume
    reads, and appear in neither list. Every other issue's file at those
    paths is still leavings.
    """
    result = _run(["git", "-C", str(repo), "status", "--porcelain", "-uall"])
    if result.returncode != 0:
        return [], [f"git status failed: {result.stderr.strip()}"]

    machinery: list[str] = []
    operator: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip().strip('"')
        if _is_evidence(path):
            # The machinery's own record is never dirt (#2164).
            continue
        if line.startswith("?? ") and is_machinery_owned(path):
            if is_pipeline_input(path, protect_issues):
                # The current roll's input is not litter (#2551).
                continue
            machinery.append(path)
        else:
            operator.append(line.strip())
    return machinery, operator


def preserve_and_clear(
    repo: Path | str, files: list[str], *, log=None
) -> LeavingsResult:
    """Commit `files` to a pushed graveyard branch, then remove them.

    All-or-nothing on the preservation: if the commit or the push fails, every
    file stays in place and the failure is reported -- nothing is ever removed
    unpreserved. Removal never uses git (the files are untracked); it is a
    plain unlink plus pruning of directories the removals emptied, bounded to
    the allowlist so an operator's directory is never rmdir'd.
    """
    repo = Path(repo).resolve()
    log = log or (lambda _msg: None)
    result = LeavingsResult()
    if not files:
        return result

    branch = f"{GRAVEYARD_LEAVINGS_PREFIX}-{_now_tag()}"
    index = repo / ".git" / f"leavings-index-{os.getpid()}"
    env = dict(os.environ)
    env["GIT_INDEX_FILE"] = str(index)

    def _fail_all(stage: str, detail: str) -> LeavingsResult:
        for f in files:
            result.entries.append(
                LeavingsEntry(f, "reported", ok=False,
                              detail=f"{stage} failed: {detail}")
            )
        log(f"  file janitor: {stage} failed -- nothing cleared ({detail})")
        index.unlink(missing_ok=True)
        return result

    try:
        read = _run(["git", "-C", str(repo), "read-tree", "HEAD"], env=env)
        if read.returncode != 0:
            return _fail_all("read-tree", read.stderr.strip())

        added = _run(
            ["git", "-C", str(repo), "add", "--", *files], env=env
        )
        if added.returncode != 0:
            return _fail_all("add", added.stderr.strip())

        tree = _run(["git", "-C", str(repo), "write-tree"], env=env)
        if tree.returncode != 0:
            return _fail_all("write-tree", tree.stderr.strip())

        commit = _run(
            [
                "git", "-C", str(repo), "commit-tree", tree.stdout.strip(),
                "-p", "HEAD",
                "-m", "chore(graveyard): preserve pipeline file leavings "
                      "before clearing (standard 0027)",
            ],
            env=env,
        )
        if commit.returncode != 0:
            return _fail_all("commit-tree", commit.stderr.strip())

        branched = _run(
            ["git", "-C", str(repo), "branch", branch, commit.stdout.strip()]
        )
        if branched.returncode != 0:
            return _fail_all("branch", branched.stderr.strip())

        pushed = _run(
            ["git", "-C", str(repo), "push", "-u", "origin", branch]
        )
        if pushed.returncode != 0:
            # Spec (#2144): unpushed is unpreserved. The local branch is left
            # for a human to inspect, the files are left in place.
            return _fail_all("push", pushed.stderr.strip())
    finally:
        index.unlink(missing_ok=True)

    # #2355: the archiver reads this record. `graveyard/leavings-<stamp>`
    # carries no run prefix, so the old bundle rule could never find it.
    record_preserved(
        repo, branch, source="leavings", detail=f"{len(files)} file(s)"
    )

    result.branch = branch
    for f in files:
        target = repo / f
        try:
            target.unlink()
        except OSError as exc:
            result.entries.append(
                LeavingsEntry(f, "reported", ok=False,
                              detail=f"preserved on {branch} but not removed: {exc}")
            )
            continue
        _prune_empty_dirs(repo, target.parent)
        result.entries.append(LeavingsEntry(f, "preserved-and-cleared"))

    for entry in result.entries:
        log(f"  {entry.describe()}")
    log(f"  {result.summary()}")
    return result


def _prune_empty_dirs(repo: Path, start: Path) -> None:
    """Remove now-empty directories, but only inside the allowlist."""
    current = start
    while current != repo:
        rel = str(current.relative_to(repo)).replace("\\", "/") + "/"
        inside = any(
            rel.startswith(prefix) or prefix.startswith(rel)
            for prefix in EMISSION_ALLOWLIST
        )
        if not inside:
            return
        try:
            current.rmdir()  # fails on non-empty, which is the stop condition
        except OSError:
            return
        current = current.parent
