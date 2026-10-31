#!/usr/bin/env python3
"""Reset spawn state for a speed-run attempt (#1076).

Performs the cleanup needed between attempts:

  1. Closes any open PR for the issue (without merging).
  2. Removes the worktrees at `{repo}-{issue}` and `{repo}-{issue}-lld`
     if they exist (#1848).
  3. Deletes the local feature branch (safe-delete) and the same branches
     on origin (#1885) — the attempt branch is never a candidate.
  4. Deletes `docs/lineage/active/{issue}-*/` directories.
  5. Relocates untracked LLD/spec artifacts out of the target repo's
     docs/lld tree into `data/speedrun/reset-artifacts/` (#1849) — left
     in place they make the next run resolve existing artifacts and
     silently skip design generation.
  6. Reopens the issue if it was closed.
  7. Prints "spawn state restored" on success.

Idempotent: safe to run multiple times. Each step is independently
guarded — a missing PR / worktree / branch is not an error.

Usage:

    poetry run python tools/speedrun_reset.py \\
        --repo ../boostgauge \\
        --issue 35

    # Reset all known speed-run issues at once:
    poetry run python tools/speedrun_reset.py \\
        --repo ../boostgauge \\
        --all-issues

The `--all-issues` mode reads `data/speedrun/run-log.jsonl` and resets
every issue that's appeared in any attempt (covers the full speed-run
arc across multiple takes).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

# Branch namespace for preserved work. Matches speedrun_new_attempt and the
# `speedrun_clean_check` exemption, so a parked branch is not later reported
# as debris.
GRAVEYARD_PREFIX = "graveyard/"

# The AssemblyZero checkout this tool sits in. The orchestrator runs with it as
# its working directory (`speedrun_roll.py` Popen cwd), so it holds the locks (#4217).
AZ_ROOT = Path(__file__).resolve().parents[1]


def _rmtree_clearing_readonly(path: Path) -> None:
    """rmtree that survives the ReadOnly attribute (#2162).

    The pipeline's own lineage directories carry the Windows ReadOnly
    attribute (root cause hunted in #2136), and a plain rmtree dies on them
    with WinError 5 -- measured live 2026-08-09, mid-roll. The handler
    clears the attribute on the failing entry AND its parent (POSIX refusals
    come from a write-protected parent), then retries that one deletion.
    Plain deletion first; the chmod fires only on failure. Same pattern as
    dependabot_review's worktree cleanup.
    """

    def _clear_and_retry(func, failing, _exc):
        for target in (failing, os.path.dirname(failing)):
            try:
                os.chmod(target, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
            except OSError:
                pass
        func(failing)

    shutil.rmtree(path, onexc=_clear_and_retry)


def _run(cmd: list[str], cwd: Path | None = None, check: bool = False):
    """Subprocess wrapper that returns the result and captures both streams."""
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=check,
    )


def _gh_repo(repo_root: Path) -> str:
    """Read GitHub remote and extract owner/repo."""
    result = _run(["git", "remote", "get-url", "origin"], cwd=repo_root)
    if result.returncode != 0:
        raise RuntimeError(f"Could not read git remote: {result.stderr}")
    url = result.stdout.strip()
    # https://github.com/owner/repo.git → owner/repo
    if url.startswith("https://github.com/"):
        path = url[len("https://github.com/"):]
    elif url.startswith("git@github.com:"):
        path = url[len("git@github.com:"):]
    else:
        raise RuntimeError(f"Unrecognized remote URL: {url}")
    if path.endswith(".git"):
        path = path[:-4]
    return path


def is_pipeline_branch(branch: str, issue: int) -> bool:
    """True when `branch` is one the pipeline creates for this issue (#4218).

    The impl stage's `issue-{N}` and the per-stage `{N}-*` branches (`{N}-lld`).
    The same two shapes the branch sweeps list.
    """
    return branch == f"issue-{issue}" or branch.startswith(f"{issue}-")


def close_open_prs(repo: str, issue: int) -> int:
    """Close the pipeline's own open PRs that name this issue. Returns count closed.

    #4218: a search for the closing text also returns a PR somebody made by
    hand that happens to name the issue. Only a PR whose head branch is one of
    the issue's pipeline branches is closed; any other is named in the output
    and left open. (A closed PR can be reopened, so nothing was lost before,
    but the reset has no business touching work that is not the pipeline's.)
    """
    # Find PRs that reference the issue in body.
    result = _run([
        "gh", "pr", "list",
        "--repo", repo,
        "--state", "open",
        "--search", f"Closes #{issue}",
        "--json", "number,title,headRefName",
    ])
    if result.returncode != 0:
        print(f"  WARNING: gh pr list failed: {result.stderr.strip()}")
        return 0
    try:
        prs = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return 0
    closed = 0
    for pr in prs:
        n = pr["number"]
        head = pr.get("headRefName") or ""
        if not is_pipeline_branch(head, issue):
            print(
                f"  Left open PR #{n}: {pr['title']} "
                f"(head branch '{head or 'unknown'}' is not a pipeline branch "
                f"of #{issue})"
            )
            continue
        r = _run(["gh", "pr", "close", str(n), "--repo", repo])
        if r.returncode == 0:
            print(f"  Closed PR #{n}: {pr['title']}")
            closed += 1
        else:
            print(f"  WARNING: could not close PR #{n}: {r.stderr.strip()}")
    return closed


def worktree_is_dirty(worktree_path: Path) -> bool:
    """
    True if the worktree holds uncommitted work (tracked or untracked).

    Returns True when the state cannot be read, so an unreadable worktree
    is treated as "might hold work" rather than "safe to delete".
    """
    result = _run(["git", "status", "--porcelain"], cwd=worktree_path)
    if result.returncode != 0:
        return True
    return bool(result.stdout.strip())


def remove_worktree(repo_root: Path, issue: int) -> bool:
    """
    Remove the worktrees at `{repo}-{issue}` and `{repo}-{issue}-lld`.

    The requirements workflow creates an `-lld` worktree alongside the
    implementation worktree; both are pipeline debris after a cut take
    (#1848). Returns True if at least one was removed.
    """
    parent = repo_root.parent
    removed_any = False
    for suffix in (f"{issue}", f"{issue}-lld"):
        candidates = [
            # Current home (#2077): inside the repo's gitignored data/.
            repo_root / "data" / "worktrees" / suffix,
            # Pre-#2077 sibling. Still checked so a reset run against debris
            # left by an older pipeline still finds and clears it.
            parent / f"{repo_root.name}-{suffix}",
        ]
        for worktree_path in candidates:
            if _remove_worktree_at(repo_root, worktree_path):
                removed_any = True
    return removed_any


def _remove_worktree_at(repo_root: Path, worktree_path: Path) -> bool:
    """
    Remove one worktree directory if it exists.

    A CUT take leaves a half-finished worktree behind, and that worktree
    may hold uncommitted work. `git worktree remove` refuses in that case,
    and that refusal is a signal to respect, not to route around: this
    function never force-removes and never deletes a dirty directory. A
    worktree holding work is reported and left for the operator (#1762).
    """
    if not worktree_path.exists():
        return False

    result = _run(
        ["git", "worktree", "remove", str(worktree_path)],
        cwd=repo_root,
    )
    if result.returncode == 0:
        print(f"  Removed worktree: {worktree_path}")
        return True

    if worktree_is_dirty(worktree_path):
        print(f"  SKIPPED worktree {worktree_path} — it holds uncommitted work.")
        print("    Left in place. Inspect it, then remove it yourself once")
        print("    you have salvaged anything worth keeping.")
        return False

    # Clean, but git would not remove it — typically a directory that is no
    # longer registered as a worktree. #3518: "clean" is not "nothing at
    # stake". `git status` is clean in a separate clone holding unpushed
    # commits, and it never reports ignored files, so this directory is moved
    # aside, stamped, never deleted.
    try:
        aside = worktree_path.with_name(
            f"{worktree_path.name}.bak-{_disposal_stamp()}"
        )
        worktree_path.rename(aside)
        print(f"  Moved unregistered worktree directory aside: {worktree_path} -> {aside}")
        _forget_worktree(repo_root, worktree_path)
        return True
    except OSError as e:
        print(f"  WARNING: could not remove worktree {worktree_path}: {e}")
        return False


def _forget_worktree(repo_root: Path, worktree_path: Path) -> None:
    """
    Drop the registration of this one worktree, whose directory is gone.

    Without this, git keeps the path registered and the next `git worktree
    add` there fails as already-registered. `git worktree remove` on a
    registered path whose directory is missing clears exactly that
    registration (git 2.53, measured 2026-09-26), and fails harmlessly on a
    path that was never registered. It replaced a repo-wide prune, which
    drops EVERY registration git thinks is stale: on a machine running agents
    on both Windows and WSL, each side sees the other side's live worktrees
    that way (#4232).
    """
    _run(["git", "worktree", "remove", str(worktree_path)], cwd=repo_root)


def current_branch(repo_root: Path) -> str:
    """Name of the branch the repo is checked out on, or '' if undetermined."""
    result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def dispose_pipeline_branches(
    repo_root: Path, issue: int, base: str | None = None,
) -> list[str]:
    """
    Free the pipeline branch names for one issue. Returns failure descriptions.

    #2310: removing a worktree does not remove the branch it carried, so a
    failed roll left `issue-{N}` standing on the exact SHA the relaunch
    wanted to branch from, and `git worktree add -b issue-{N}` died with a
    bare `fatal: a branch named 'issue-7' already exists`. A name squatting
    on the base killed a roll whose spec stage had just passed for the first
    time in campaign history.

    Two dispositions, decided by MEASURING what the branch holds:

    - Zero commits beyond `base`: safe-delete, and the name is freed. This
      is the measured case from #2310 -- the stranded branch was
      pointer-identical to `origin/hardening-run-17`'s tip.
    - Anything else, INCLUDING a count that cannot be established: the
      branch is RENAMED under `graveyard/`, which keeps every commit and
      still frees the name. Never `-D`, never a force delete, per the
      banned-commands rule and ADR-0217.

    #2325: the decision must NOT be delegated to `git branch -d`. That
    command accepts any branch merged into its UPSTREAM, and every pipeline
    branch gets an upstream at creation (`push -u` in stages.py, #1780), so
    `-d` accepts branches carrying arbitrary unique work. Asking it for the
    verdict inverted this function: run against the boostgauge #7 branches
    it deleted both while reporting "no unique commits", when they held 3
    and 2 commits respectively. Nothing was lost only because the remote
    refs still existed -- the brittle upstream-tracking path ADR-0217
    rejects. Measure against `base` first; `-d` then merely executes a
    decision already made.

    Defaulting to preservation when the count is unknown costs a less tidy
    graveyard and nothing else, which is the right side to err on: a rename
    is non-destructive and still frees the name.

    `base` should be the branch the pipeline cut from. It falls back to
    `origin/HEAD`, which is right for a repo rolling on its default branch
    and wrong for one rolling on an integration branch -- so callers that
    know their base should pass it.
    """
    result = _run(
        [
            "git", "branch", "--list", "--format=%(refname:short)",
            f"{issue}-*", f"issue-{issue}",
        ],
        cwd=repo_root,
    )
    if result.returncode != 0:
        return [f"could not list branches for #{issue}"]

    base_ref = base or _default_base_ref(repo_root)
    active = current_branch(repo_root)
    failures: list[str] = []
    for branch in (line.strip() for line in result.stdout.splitlines()):
        if not branch or branch.startswith(GRAVEYARD_PREFIX):
            continue
        if branch == active:
            # Never dispose of the branch the checkout is standing on (#1762).
            print(f"  Skipped branch {branch} (currently checked out).")
            continue

        unique = _unique_commit_count(repo_root, branch, base_ref)
        if unique == 0:
            # Proven to add nothing beyond the base. `-d` cannot refuse this,
            # and if it somehow does, the refusal is reported rather than
            # escalated.
            deleted = _run(["git", "branch", "-d", branch], cwd=repo_root)
            if deleted.returncode == 0:
                print(
                    f"  Freed branch name: {branch} "
                    f"(no commits beyond {base_ref})"
                )
                continue
            failures.append(
                f"branch '{branch}' measured empty against '{base_ref}' but "
                f"the safe delete refused: "
                f"{(deleted.stderr or '').strip()[:200]}"
            )
            continue

        # Unique work, or a count that could not be established. Preserve it
        # under a name no relaunch will collide with. `-m` (not `-M`) so an
        # existing graveyard name is never clobbered; the collision is
        # reported instead.
        parked = f"{GRAVEYARD_PREFIX}{branch}-{_disposal_stamp()}"
        renamed = _run(["git", "branch", "-m", branch, parked], cwd=repo_root)
        if renamed.returncode == 0:
            detail = (
                f"{unique} commit(s)" if unique is not None
                else f"commits (count against '{base_ref}' unavailable)"
            )
            print(f"  Preserved branch {branch} -> {parked} ({detail} kept)")
        else:
            failures.append(
                f"branch '{branch}' holds work and could not be renamed to "
                f"'{parked}': {(renamed.stderr or '').strip()[:200]}"
            )
    return failures


def _disposal_stamp() -> str:
    """UTC stamp for a graveyard branch name. Sorts, and never collides."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _default_base_ref(repo_root: Path) -> str:
    """`origin/HEAD` as a name, or 'HEAD' when it cannot be resolved."""
    result = _run(
        ["git", "rev-parse", "--abbrev-ref", "origin/HEAD"], cwd=repo_root
    )
    if result.returncode != 0 or not result.stdout.strip():
        return "HEAD"
    return result.stdout.strip()


def _unique_commit_count(
    repo_root: Path, branch: str, base_ref: str,
) -> int | None:
    """
    Commits on `branch` not reachable from `base_ref`, or None if unknown.

    None means "could not measure" and is deliberately distinct from 0 --
    the caller preserves on None and only deletes on a proven 0 (#2325).
    """
    counted = _run(
        ["git", "rev-list", "--count", f"{base_ref}..{branch}"],
        cwd=repo_root,
    )
    if counted.returncode != 0:
        return None
    try:
        return int(counted.stdout.strip())
    except ValueError:
        return None


class ResetPreservationError(RuntimeError):
    """A branch's tip could not be preserved, so the reset stopped before
    removing it (#4215). Nothing was removed that was not first recoverable."""


def _refuse(repo_root: Path, issue: int, where: str, what: str, cause: str,
            consequence: str) -> None:
    """Alert the operator and raise (ADR 0236, standard 0034).

    `alert_operator` writes the ERROR to standard error, emails, and records
    the failure; the raise stops every step that depends on this one.
    """
    from assemblyzero.core import alert

    alert.alert_operator(
        what=what, where=f"tools/speedrun_reset.py {where}", cause=cause,
        consequence=consequence, repo=str(repo_root), issue=issue,
    )
    raise ResetPreservationError(f"{what}: {cause}")


def _secure_remote_tip(
    repo_root: Path, issue: int, branch: str, tip: str, base_ref: str,
) -> str | None:
    """Make `tip` recoverable before origin's `branch` is deleted (#4215).

    Returns the graveyard ref now holding it on origin, or None when the tip
    is proven to be on `base_ref` (the same proof `dispose_pipeline_branches`
    uses: no commits beyond the base, and a count that cannot be established
    is not a proof). Raises `ResetPreservationError` when it can do neither.
    The graveyard ref is verified on origin before this returns, so the caller
    deletes the branch only once the tip has another home.
    """
    where = "delete_remote_branches"
    have = _run(["git", "cat-file", "-e", f"{tip}^{{commit}}"], cwd=repo_root)
    if have.returncode != 0:
        # Pushed from another clone, or this one's remote-tracking ref is
        # stale: the object is not here yet. A graveyard push needs it here.
        _run(["git", "fetch", "origin", branch], cwd=repo_root)
        have = _run(["git", "cat-file", "-e", f"{tip}^{{commit}}"], cwd=repo_root)
        if have.returncode != 0:
            _refuse(
                repo_root, issue, where,
                f"reading the tip of origin's '{branch}' for #{issue}",
                f"commit {tip[:12]} is not in this repository and could not be "
                f"fetched: {(have.stderr or '').strip()[:200]}",
                f"origin's '{branch}' was not deleted and the reset stopped",
            )

    unique = _unique_commit_count(repo_root, tip, base_ref)
    if unique == 0:
        print(
            f"  Remote branch {branch} is on {base_ref}; "
            f"no graveyard ref needed"
        )
        return None

    graveyard = f"{GRAVEYARD_PREFIX}{branch}-{_disposal_stamp()}"
    pushed = _run(
        ["git", "push", "origin", f"{tip}:refs/heads/{graveyard}"], cwd=repo_root,
    )
    if pushed.returncode != 0:
        _refuse(
            repo_root, issue, where,
            f"pushing a graveyard ref for origin's '{branch}' (#{issue})",
            f"git push exited {pushed.returncode}: "
            f"{(pushed.stderr or '').strip()[:200]}",
            f"origin's '{branch}' was not deleted and the reset stopped",
        )
    # Read it back from origin: a push that reported success is not the
    # evidence, the ref being there with this tip is.
    verify = _run(
        ["git", "ls-remote", "--heads", "origin", graveyard], cwd=repo_root,
    )
    on_origin = verify.stdout.split()[:1] if verify.returncode == 0 else []
    if on_origin != [tip]:
        _refuse(
            repo_root, issue, where,
            f"verifying the graveyard ref for origin's '{branch}' (#{issue})",
            f"origin does not hold {graveyard} at {tip[:12]} after the push "
            f"(ls-remote exited {verify.returncode}, said "
            f"{verify.stdout.strip()[:120]!r})",
            f"origin's '{branch}' was not deleted and the reset stopped",
        )
    detail = (
        f"{unique} commit(s)" if unique is not None
        else f"commits (count against '{base_ref}' unavailable)"
    )
    print(f"  Preserved remote branch {branch} -> {graveyard} ({detail} kept)")
    return graveyard


def delete_remote_branches(
    repo_root: Path, issue: int, base: str | None = None,
) -> int:
    """Delete the pipeline's pushed branches on origin. Returns count deleted.

    The local sweep alone left `issue-{N}` and `{N}-lld` on origin after every
    roll of the 2026-07-28 campaign, so the wipe was one forgotten command away
    from leaving debris that collides with the next roll's push (#1885).

    #4215: a branch is deleted on origin only after its tip is recoverable.
    The merge driver pushes every pipeline branch with `-u`, and a branch that
    was pushed and never landed holds commits that no other branch, rescue ref
    or (when its PR was never opened) PR holds. Deleting it dropped them to
    unreferenced objects, which breaks standard 0027. Each tip is pushed to
    `graveyard/<branch>-<stamp>` and read back from origin first, unless it is
    proven to be on `base` (see `_secure_remote_tip`). If it cannot be, the
    branch stays, the operator is alerted, and the reset stops.

    Which branches: whatever origin has that is `issue-{N}` or `{N}-*`, the
    shape the PR filter and the clean-check use, asked of origin itself rather
    than of local state. The attempt branch is never a candidate: it is named
    for the attempt, and the checked-out branch is excluded by name (#1762).
    Each ref is handled independently: a single `git push --delete a b` aborts
    the whole push when either is already gone, the common case on a
    partially-cleaned repo.

    `base` is the branch the pipeline cut from; it falls back to `origin/HEAD`
    as `dispose_pipeline_branches` does.
    """
    ls_remote = _run(["git", "ls-remote", "--heads", "origin"], cwd=repo_root)
    if ls_remote.returncode != 0:
        _refuse(
            repo_root, issue, "delete_remote_branches",
            f"listing origin's branches for #{issue}",
            f"git ls-remote exited {ls_remote.returncode}: "
            f"{(ls_remote.stderr or '').strip()[:200]}",
            "no branch was deleted on origin and the reset stopped",
        )
    remote_tips = {}
    for line in ls_remote.stdout.splitlines():
        if "refs/heads/" not in line:
            continue
        tip, ref = line.split(None, 1)
        remote_tips[ref.strip().split("refs/heads/", 1)[1]] = tip

    base_ref = base or _default_base_ref(repo_root)
    active = current_branch(repo_root)
    deleted = 0
    for branch, tip in remote_tips.items():
        if branch.startswith(GRAVEYARD_PREFIX) or not is_pipeline_branch(branch, issue):
            continue
        if branch == active:
            continue
        _secure_remote_tip(repo_root, issue, branch, tip, base_ref)
        r = _run(
            ["git", "push", "origin", "--delete", branch], cwd=repo_root
        )
        if r.returncode != 0:
            _refuse(
                repo_root, issue, "delete_remote_branches",
                f"deleting origin's '{branch}' (#{issue})",
                f"git push --delete exited {r.returncode}: "
                f"{(r.stderr or '').strip()[:200]}",
                "the reset stopped; the branch is still on origin and its tip "
                "is preserved",
            )
        print(f"  Deleted remote branch: {branch}")
        deleted += 1
    return deleted


def archive_lineage_dirs(repo_root: Path, issue: int) -> int:
    """Move docs/lineage/active/{issue}-* into reset-artifacts. Returns count.

    #2409: this deleted outright, in the same reset that RELOCATED the LLD two
    steps later. The remedy was internally inconsistent -- preservation was the
    principle for one artifact and destruction for another -- and what it
    destroyed was the most expensive thing the campaign produces: on
    2026-08-15 a passed spec stage carrying five review iterations of verdict
    history, which the fresh redraw then had to pay for again without it.

    If preservation is the principle for one artifact it is the principle for
    all of them. Same destination as `relocate_lld_artifacts`, so everything a
    reset displaces lands in one place the operator can find.
    """
    lineage_active = repo_root / "docs" / "lineage" / "active"
    if not lineage_active.exists():
        return 0

    destination = (
        repo_root / "data" / "speedrun" / "reset-artifacts"
        / f"issue-{issue}" / "lineage"
    )
    archived = 0
    for d in sorted(lineage_active.glob(f"{issue}-*")):
        if not d.is_dir():
            continue
        try:
            destination.mkdir(parents=True, exist_ok=True)
            target = destination / d.name
            if target.exists():
                # A second reset must not clobber the first one's evidence.
                target = destination / f"{d.name}-{_disposal_stamp()}"
            try:
                shutil.move(str(d), str(target))
            except OSError:
                # #2162: lineage dirs can carry the ReadOnly attribute, and
                # shutil.move falls back to copy-then-rmtree across
                # filesystems, where a plain rmtree dies on them. Copy, then
                # remove with the attribute-clearing variant.
                shutil.copytree(str(d), str(target), dirs_exist_ok=True)
                # #3518 gate: the source goes only once its copy is there.
                assert target.is_dir()
                _rmtree_clearing_readonly(d)
            print(f"  Archived lineage dir: {d.relative_to(repo_root)} -> "
                  f"{target.relative_to(repo_root)}")
            archived += 1
        except OSError as e:
            print(f"  WARNING: could not archive {d}: {e}")
    return archived


#: The branches, as formats over the issue number, a checkpoint commit can sit
#: on (#4216). `issue-{issue}` is the branch the impl stage commits its
#: checkpoints on (`stages.py`; `testing/checkpoints.py`) and comes first.
#: Nothing in the pipeline creates `{issue}-impl`; it stays for a branch an
#: older roll left. The pin below and `speedrun_roll.find_checkpoint` both
#: read this one list, so they cannot disagree about where a checkpoint lives.
CHECKPOINT_BRANCH_FORMATS = (
    "issue-{issue}",
    "{issue}-impl",
    "{issue}-lld",
    "{issue}-spec",
    "{issue}-fix",
)


def checkpoint_search_refs(issue: int) -> list[str]:
    """Every ref a checkpoint for this issue could be on, in search order.

    Each branch is searched locally and then as `origin/<branch>`, so a
    checkpoint that was pushed, and whose local branch is gone, is still found.
    """
    refs: list[str] = []
    for branch_format in CHECKPOINT_BRANCH_FORMATS:
        branch = branch_format.format(issue=issue)
        refs.extend((branch, f"origin/{branch}"))
    return refs


def pin_checkpoint(repo_root: Path, issue: int) -> str | None:
    """Stamp a rescue ref over this issue's newest checkpoint, before branches go.

    #2409: `d1e9269 [CP:post-impl]` survived the 2026-08-15 reset only as an
    unreferenced object, recoverable because nothing had garbage-collected it
    yet. That is luck, not design. A checkpoint is reachable from the issue's
    pipeline branches and from nothing else, so deleting those branches orphans
    it; pinning first makes the survival deliberate.

    Returns the rescue ref name, or None when there was no checkpoint to pin.
    """
    for ref in checkpoint_search_refs(issue):
        found = _run(
            ["git", "log", "-1", "--format=%H", "--grep=^\\[CP:", ref],
            cwd=repo_root,
        )
        sha = found.stdout.strip() if found.returncode == 0 else ""
        if not sha:
            continue
        rescue = f"refs/rescue/issue-{issue}-{_disposal_stamp()}"
        made = _run(["git", "update-ref", rescue, sha], cwd=repo_root)
        if made.returncode == 0:
            print(f"  Pinned checkpoint {sha[:7]} at {rescue}")
            return rescue
        print(f"  WARNING: could not pin checkpoint {sha[:7]}: {made.stderr.strip()}")
        return None
    return None


def _is_git_tracked(repo_root: Path, file_path: Path) -> bool:
    """True when git tracks the file (deliberate repo content)."""
    try:
        rel = file_path.relative_to(repo_root)
    except ValueError:
        return False
    result = _run(
        ["git", "ls-files", "--error-unmatch", str(rel)], cwd=repo_root
    )
    return result.returncode == 0


def relocate_lld_artifacts(
    repo_root: Path, issue: int, preserve: set[str] | None = None
) -> int:
    """
    Move untracked LLD/spec artifacts out of the target repo's docs tree.

    The requirements/spec stages save `LLD-{NNN}.md` and `spec-{NNNN}-*.md`
    into the target repo's primary checkout. Left in place, the next run
    resolves them as existing artifacts and can silently skip design
    generation — a wiped repo must not behave differently from a cold
    start (#1849). The bytes are already preserved in the design PR's
    commits, so working copies are relocated (never deleted) to
    `data/speedrun/reset-artifacts/issue-{N}/` for inspection. Tracked
    files are deliberate repo content and are left alone.

    #2609: ``preserve`` names files (by basename) that are SETTLED and must
    survive the reset. A settled artifact embodies a ruling that was not made
    by the run being reset, so resetting the run must not discard it. The
    settledness decision is made by the caller, which is where the inputs can
    be hashed; this function only honours it, and says so per file.

    ``preserve`` deliberately does not weaken #1849: an artifact left in place
    is only skipped by the next run if it is still settled THEN, which the
    stage-entry check re-verifies against the inputs at that moment.
    """
    preserve = preserve or set()
    active = repo_root / "docs" / "lld" / "active"
    drafts = repo_root / "docs" / "lld" / "drafts"
    candidates: list[Path] = []
    candidates.extend(active.glob(f"LLD-{issue:03d}.md"))
    candidates.extend(active.glob(f"LLD-{issue}.md"))
    candidates.extend(drafts.glob(f"spec-{issue:04d}-*.md"))
    candidates.extend(drafts.glob(f"spec-{issue}-*.md"))

    dest_dir = repo_root / "data" / "speedrun" / "reset-artifacts" / f"issue-{issue}"
    seen: set[Path] = set()
    moved = 0
    for artifact in candidates:
        if artifact in seen or not artifact.is_file():
            continue
        seen.add(artifact)
        if artifact.name in preserve:
            print(
                f"  Preserved (settled): {artifact.relative_to(repo_root)}"
            )
            continue
        if _is_git_tracked(repo_root, artifact):
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / artifact.name
        counter = 1
        while dest.exists():
            dest = dest_dir / f"{artifact.stem}.{counter}{artifact.suffix}"
            counter += 1
        try:
            shutil.move(str(artifact), str(dest))
            print(
                f"  Relocated artifact: {artifact.relative_to(repo_root)}"
                f" -> {dest.relative_to(repo_root)}"
            )
            moved += 1
        except OSError as e:
            print(f"  WARNING: could not relocate {artifact}: {e}")

    # An emptied drafts/ dir is itself pipeline debris; active/ keeps .gitkeep
    try:
        if drafts.exists() and not any(drafts.iterdir()):
            drafts.rmdir()
    except OSError:
        pass
    return moved


def reopen_issue(repo: str, issue: int) -> bool:
    """Reopen the GitHub issue if it's currently closed."""
    result = _run([
        "gh", "issue", "view", str(issue),
        "--repo", repo,
        "--json", "state",
    ])
    if result.returncode != 0:
        return False
    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    if info.get("state") == "OPEN":
        return False
    r = _run([
        "gh", "issue", "reopen", str(issue),
        "--repo", repo,
    ])
    if r.returncode == 0:
        print(f"  Reopened issue #{issue}")
        return True
    print(f"  WARNING: could not reopen issue #{issue}: {r.stderr.strip()}")
    return False


class LiveOrchestratorError(RuntimeError):
    """Raised when a reset is asked to run under a live orchestrator (#2510)."""


def refuse_if_orchestrator_is_live(
    repo_root: Path, issue: int, az_root: Path | None = None,
) -> None:
    """Refuse -- not warn -- while this issue's lock names a live process.

    On 2026-09-02 at 19:20 the follower announced `The roll is done: FAILED`
    because the WRAPPER had been killed, and the orchestrator was still working.
    A reset run on that verdict closed the run's LLD PR (#431), removed its
    worktree, deleted branch `4-lld` locally and on origin, and archived the
    lineage out from under a process that was still writing into it. The run had
    no path to approval, so nothing that could have shipped was lost; that is
    luck and not a defence.

    A reset that can run under a live orchestrator is the same class as a
    `git clean` in someone else's checkout, so this raises rather than printing.
    The lock has carried the pid the whole time -- nothing needed to be recorded
    that was not already there, only read.

    #4217: the lock is read where the orchestrator WRITES it. Its lock
    directory is relative to its working directory, and `speedrun_roll.py`
    starts it with the AssemblyZero root as that directory, so the lock lives
    under the AssemblyZero root and not in the target repository, which may
    have no `.assemblyzero` directory at all. This used to read the target
    repo's copy, which nothing writes, so the refusal could not see a roll
    started by `speedrun_roll.py`. The path comes from the orchestrator's own
    `orchestration_lock_path`, the function its writer calls.
    """
    from assemblyzero.workflows.orchestrator.resume import (
        live_orchestrator_pid,
        orchestration_lock_path,
    )

    az_root = AZ_ROOT if az_root is None else Path(az_root)
    pid = live_orchestrator_pid(issue, az_root)
    if pid is None:
        return
    raise LiveOrchestratorError(
        f"issue #{issue} has a live orchestrator: the lock at "
        f"{orchestration_lock_path(issue, az_root)} "
        f"names pid {pid}, and that process is running. Refusing to reset "
        f"{repo_root}.\n"
        f"A reset here closes the run's PRs, deletes its branches locally and "
        f"on origin, and archives the lineage the run is still writing (#2510).\n"
        f"The wrapper's own pid file can name a DEAD process while the "
        f"orchestrator lives, so a follower saying the roll is done is not "
        f"evidence. Stop the run first, or wait for the lock to clear."
    )


def reset_one_issue(
    repo_root: Path, repo: str, issue: int, preserve: set[str] | None = None,
    base: str | None = None,
) -> None:
    """Run all reset steps for one issue.

    #2409: the checkpoint is pinned FIRST, before anything that could orphan
    it. Branch deletion is what unreferences a checkpoint commit, so the pin
    has to precede it or the ordering is the bug.

    #2609: ``preserve`` names settled artifacts the reset must leave in place.

    #2510: the live-orchestrator refusal comes before the pin, because the pin
    is already a write and everything after it is destructive.

    #4215: branches go by the proof `dispose_pipeline_branches` uses, never by
    `git branch -d` alone. Locally a branch with work of its own is renamed
    under `graveyard/`; on origin its tip is pushed to a `graveyard/` ref and
    read back first. Either way a branch is removed only when its tip is
    recoverable or proven to be on ``base``, the branch the pipeline cut from
    (`origin/HEAD` when not given). A branch that cannot be secured stops the
    reset with `ResetPreservationError`, after alerting the operator.
    """
    refuse_if_orchestrator_is_live(repo_root, issue)
    print(f"\nResetting issue #{issue}:")
    pin_checkpoint(repo_root, issue)
    close_open_prs(repo, issue)
    remove_worktree(repo_root, issue)
    failures = dispose_pipeline_branches(repo_root, issue, base)
    if failures:
        _refuse(
            repo_root, issue, "reset_one_issue",
            f"disposing of #{issue}'s local pipeline branches",
            "; ".join(failures),
            "the reset stopped before it touched origin's branches",
        )
    delete_remote_branches(repo_root, issue, base)
    archive_lineage_dirs(repo_root, issue)
    relocate_lld_artifacts(repo_root, issue, preserve)
    reopen_issue(repo, issue)


def all_logged_issues(repo_root: Path) -> list[int]:
    """Read run-log.jsonl and return unique issue numbers."""
    log_path = repo_root / "data" / "speedrun" / "run-log.jsonl"
    if not log_path.exists():
        return []
    issues: set[int] = set()
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if "issue" in entry:
                    issues.add(int(entry["issue"]))
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
    return sorted(issues)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset speed-run state for one or more issues",
    )
    parser.add_argument(
        "--repo", required=True, type=Path,
        help="Path to the target repo (e.g., ../boostgauge)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--issue", type=int, help="Reset a single issue")
    group.add_argument(
        "--all-issues", action="store_true",
        help="Reset every issue that has appeared in run-log.jsonl",
    )
    args = parser.parse_args()

    repo_root = args.repo.resolve()
    if not repo_root.exists():
        print(f"ERROR: repo path does not exist: {repo_root}")
        return 1

    try:
        repo = _gh_repo(repo_root)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return 1

    # #4215: the branch the attempt stands on is the base a pipeline branch is
    # proven against; '' (detached, unreadable) falls back to origin/HEAD.
    base = current_branch(repo_root) or None

    # #2510: a live orchestrator stops the whole reset, not just its own issue.
    # A sweep that reset four issues and then refused the fifth would have done
    # four issues' worth of irreversible work before saying so.
    try:
        if args.issue:
            reset_issues = [args.issue]
            reset_one_issue(repo_root, repo, args.issue, base=base)
        else:
            issues = all_logged_issues(repo_root)
            if not issues:
                print("No issues in run-log.jsonl — nothing to reset.")
                return 0
            for issue in issues:
                refuse_if_orchestrator_is_live(repo_root, issue)
            print(f"Resetting {len(issues)} issue(s) from run-log: {issues}")
            for issue in issues:
                reset_one_issue(repo_root, repo, issue, base=base)
            reset_issues = issues
    except (LiveOrchestratorError, ResetPreservationError) as exc:
        print(f"\nREFUSED: {exc}")
        return 1

    # #1918: a reset that cannot prove it finished did not finish. The
    # clean-check enumerates every debris class this tool is supposed to
    # clear; a nonzero remainder (e.g. a dirty worktree deliberately left
    # for the operator per #1762) is reported honestly instead of the
    # unconditional success banner this tool used to print.
    from speedrun_clean_check import check_repo
    from speedrun_clean_check import current_branch as gate_current_branch

    # #2000: check_repo grew a required base_ref in #1959 and this production
    # caller was not updated -- the whole test suite stayed green because
    # nothing exercised speedrun_reset.main() past the reset itself, so the
    # TypeError only appeared when a real reset ran. A reset verifies the tree
    # it is standing on, which is the branch the debris was cleared from.
    base_ref = gate_current_branch(repo_root) or "HEAD"
    findings = check_repo(repo_root, reset_issues, base_ref)
    errors = [f for f in findings if f.startswith("ERROR:")]
    debris = [f for f in findings if not f.startswith("ERROR:")]
    if errors:
        print("\nVERIFY: clean-check could not fully answer:")
        for e in errors:
            print(f"  {e}")
        return 2
    if debris:
        print(f"\nVERIFY: reset INCOMPLETE — {len(debris)} finding(s) remain:")
        for d in debris:
            print(f"  {d}")
        return 1

    print("\nspawn state restored — verified clean (speedrun_clean_check)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
