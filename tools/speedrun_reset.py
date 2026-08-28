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
        --repo /c/Users/mcwiz/Projects/boostgauge \\
        --issue 35

    # Reset all known speed-run issues at once:
    poetry run python tools/speedrun_reset.py \\
        --repo /c/Users/mcwiz/Projects/boostgauge \\
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


def close_open_prs(repo: str, issue: int) -> int:
    """Close any open PR that closes this issue. Returns count closed."""
    # Find PRs that reference the issue in body.
    result = _run([
        "gh", "pr", "list",
        "--repo", repo,
        "--state", "open",
        "--search", f"Closes #{issue}",
        "--json", "number,title",
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
        _prune_worktrees(repo_root)
        return True

    if worktree_is_dirty(worktree_path):
        print(f"  SKIPPED worktree {worktree_path} — it holds uncommitted work.")
        print("    Left in place. Inspect it, then remove it yourself once")
        print("    you have salvaged anything worth keeping.")
        return False

    # Clean, but git would not remove it — typically a directory that is no
    # longer registered as a worktree. Nothing uncommitted is at stake.
    try:
        _rmtree_clearing_readonly(worktree_path)
        print(f"  Removed unregistered worktree directory: {worktree_path}")
        _prune_worktrees(repo_root)
        return True
    except OSError as e:
        print(f"  WARNING: could not remove worktree {worktree_path}: {e}")
        return False


def _prune_worktrees(repo_root: Path) -> None:
    """
    Drop stale worktree registrations.

    Without this, git keeps the removed path registered and the next
    `git worktree add` at that path fails as already-registered — the
    exact state a reset is supposed to clear.
    """
    _run(["git", "worktree", "prune"], cwd=repo_root)


def current_branch(repo_root: Path) -> str:
    """Name of the branch the repo is checked out on, or '' if undetermined."""
    result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def delete_local_branches(repo_root: Path, issue: int) -> int:
    """
    Safe-delete the pipeline branches for one issue. Returns count deleted.

    Candidates are the per-stage work branches the pipeline creates:
    `{issue}-*` (e.g. `7-lld`) and the implementation branch `issue-{N}`
    (e.g. `issue-7`, missed by the glob alone — #1862). The attempt branch
    itself (the integration branch every pipeline PR targets under the
    #1755 model) is named for the attempt, not the issue, so it never
    matches. The checked-out branch is additionally excluded by name, so a
    reset can never delete the very branch the attempt is standing on
    (#1762).
    """
    # `--format` emits the bare refname — see #1937. Plain output decorates a
    # worktree-checked-out branch with `+ `, which the old `lstrip('* ')` left
    # intact, so the name compared against `active` below (and printed in the
    # skip message) was `+ issue-4` rather than `issue-4`.
    result = _run(
        [
            "git", "branch", "--list", "--format=%(refname:short)",
            f"{issue}-*", f"issue-{issue}",
        ],
        cwd=repo_root,
    )
    if result.returncode != 0:
        return 0
    branches = [
        name
        for name in (line.strip() for line in result.stdout.splitlines())
        if name
    ]
    active = current_branch(repo_root)
    deleted = 0
    for branch in branches:
        if not branch:
            continue
        if branch == active:
            print(f"  Skipped branch {branch} (currently checked out).")
            continue
        r = _run(["git", "branch", "-d", branch], cwd=repo_root)
        if r.returncode == 0:
            print(f"  Deleted local branch: {branch}")
            deleted += 1
        else:
            # Safe-delete refused: the branch holds commits not reachable
            # from HEAD. That refusal is the safety net working. Report it
            # and move on -- never escalate to a force-delete, and never
            # suggest one, per the banned-commands rule and ADR-0217.
            print(
                f"  Skipped branch {branch} (holds unmerged commits; "
                f"left in place for review)."
            )
    return deleted


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


def delete_remote_branches(repo_root: Path, issue: int) -> int:
    """Delete the pipeline's pushed branches on origin. Returns count deleted.

    The local sweep alone left `issue-{N}` and `{N}-lld` on origin after every
    roll of the 2026-07-28 campaign, so the wipe was one forgotten command away
    from leaving debris that collides with the next roll's push (#1885).

    Deletes each ref independently: a single `git push --delete a b` aborts the
    whole push when either ref is already gone, which is the common case on a
    partially-cleaned repo. The attempt branch is never a candidate — the same
    exclusion the local sweep honours (#1762).
    """
    candidates = [f"issue-{issue}"]
    result = _run(
        ["git", "branch", "--list", "--format=%(refname:short)", f"{issue}-*"],
        cwd=repo_root,
    )
    if result.returncode == 0:
        # Bare refnames only (#1937): a `+ `-decorated name here would be
        # pushed to origin as a nonexistent ref and silently skipped.
        candidates.extend(
            name
            for name in (line.strip() for line in result.stdout.splitlines())
            if name
        )
    # Whatever the local sweep already deleted still needs removing on origin,
    # so ask origin what it actually has rather than trusting local state.
    ls_remote = _run(["git", "ls-remote", "--heads", "origin"], cwd=repo_root)
    if ls_remote.returncode != 0:
        print("  WARNING: could not list remote branches; skipping remote sweep")
        return 0
    remote_names = {
        line.split("refs/heads/", 1)[1].strip()
        for line in ls_remote.stdout.splitlines()
        if "refs/heads/" in line
    }
    for suffix in (f"{issue}-lld",):
        candidates.append(suffix)

    active = current_branch(repo_root)
    deleted = 0
    for branch in dict.fromkeys(candidates):  # de-dupe, keep order
        if not branch or branch == active or branch not in remote_names:
            continue
        r = _run(
            ["git", "push", "origin", "--delete", branch], cwd=repo_root
        )
        if r.returncode == 0:
            print(f"  Deleted remote branch: {branch}")
            deleted += 1
        else:
            print(
                f"  WARNING: could not delete remote branch {branch}: "
                f"{(r.stderr or '').strip()[:120]}"
            )
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
                _rmtree_clearing_readonly(d)
            print(f"  Archived lineage dir: {d.relative_to(repo_root)} -> "
                  f"{target.relative_to(repo_root)}")
            archived += 1
        except OSError as e:
            print(f"  WARNING: could not archive {d}: {e}")
    return archived


def pin_checkpoint(repo_root: Path, issue: int) -> str | None:
    """Stamp a rescue ref over this issue's newest checkpoint, before branches go.

    #2409: `d1e9269 [CP:post-impl]` survived the 2026-08-15 reset only as an
    unreferenced object, recoverable because nothing had garbage-collected it
    yet. That is luck, not design. A checkpoint is reachable from the issue's
    pipeline branches and from nothing else, so deleting those branches orphans
    it; pinning first makes the survival deliberate.

    Returns the rescue ref name, or None when there was no checkpoint to pin.
    """
    for ref in (
        f"{issue}-impl", f"origin/{issue}-impl",
        f"{issue}-lld", f"origin/{issue}-lld",
        f"{issue}-spec", f"origin/{issue}-spec",
        f"{issue}-fix", f"origin/{issue}-fix",
    ):
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


def reset_one_issue(
    repo_root: Path, repo: str, issue: int, preserve: set[str] | None = None
) -> None:
    """Run all reset steps for one issue.

    #2409: the checkpoint is pinned FIRST, before anything that could orphan
    it. Branch deletion is what unreferences a checkpoint commit, so the pin
    has to precede it or the ordering is the bug.

    #2609: ``preserve`` names settled artifacts the reset must leave in place.
    """
    print(f"\nResetting issue #{issue}:")
    pin_checkpoint(repo_root, issue)
    close_open_prs(repo, issue)
    remove_worktree(repo_root, issue)
    delete_local_branches(repo_root, issue)
    delete_remote_branches(repo_root, issue)
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
        help="Path to the target repo (e.g., /c/Users/mcwiz/Projects/boostgauge)",
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

    if args.issue:
        reset_issues = [args.issue]
        reset_one_issue(repo_root, repo, args.issue)
    else:
        issues = all_logged_issues(repo_root)
        if not issues:
            print("No issues in run-log.jsonl — nothing to reset.")
            return 0
        print(f"Resetting {len(issues)} issue(s) from run-log: {issues}")
        for issue in issues:
            reset_one_issue(repo_root, repo, issue)
        reset_issues = issues

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
