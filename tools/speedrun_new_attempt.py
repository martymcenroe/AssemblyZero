#!/usr/bin/env python3
"""Re-establish a speedrun attempt branch so the next roll starts from zero (#1986).

`speedrun_reset.py` cleans per-ISSUE debris and deliberately never touches the
attempt branch (#1762 -- a reset must not cut the branch out from under the run
standing on it). Nothing else did either, so after an arc completed the
integration branch permanently carried every merged phase and the repo stayed
parked on it. A roll was idempotent only if a human remembered to graveyard the
branch and cut a fresh one.

That ritual was performed by hand on 2026-07-30 and got wrong:
`git checkout -b hardening-run-12 origin/main` sets the upstream to
`origin/main` and never creates `origin/hardening-run-12`. Every earlier attempt
branch existed on origin; that one did not, so `gh pr create --base
hardening-run-12` would have failed on the run's FIRST PR -- after the LLD and
spec stages had already burned. Nothing local showed a symptom.

Every failure mode here is silent until mid-run, so this tool asserts its own
postconditions (step 6) instead of assuming them.

Dry-run by default; `--apply` mutates. No banned commands appear here -- the old
branch is renamed, never deleted, and the new branch is pushed as a fresh ref,
never force-pushed -- so `--apply` is the correct flag per standard 0017.

Usage:
    poetry run python tools/speedrun_new_attempt.py --repo /c/.../boostgauge \
        --name hardening-run-13 [--issue 4 --issue 2] [--apply]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

GRAVEYARD_PREFIX = "graveyard/"


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def current_branch(repo_root: Path) -> str:
    """Checked-out branch, or "" on detached HEAD / git failure."""
    result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    if result.returncode != 0:
        return ""
    name = result.stdout.strip()
    return "" if name == "HEAD" else name


def default_branch(repo_root: Path) -> str:
    """origin's default branch (e.g. "main"), or "" if it cannot be resolved.

    Read from `origin/HEAD` rather than assumed: hardcoding main is the
    behaviour the attempt-branch model exists to remove.
    """
    result = _run(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        cwd=repo_root,
    )
    if result.returncode != 0:
        return ""
    ref = result.stdout.strip()
    return ref.split("/", 1)[1] if "/" in ref else ""


def remote_branch_exists(repo_root: Path, name: str) -> bool:
    result = _run(
        ["git", "ls-remote", "--heads", "origin", f"refs/heads/{name}"],
        cwd=repo_root,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def local_branch_exists(repo_root: Path, name: str) -> bool:
    result = _run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"],
        cwd=repo_root,
    )
    return result.returncode == 0


def upstream_of(repo_root: Path, name: str) -> str:
    result = _run(
        ["git", "rev-parse", "--abbrev-ref", f"{name}@{{upstream}}"],
        cwd=repo_root,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def commits_ahead(repo_root: Path, ref: str, base: str) -> int | None:
    result = _run(
        ["git", "rev-list", "--count", f"{base}..{ref}"], cwd=repo_root
    )
    if result.returncode != 0 or not result.stdout.strip().isdigit():
        return None
    return int(result.stdout.strip())


# =============================================================================
# Preconditions
# =============================================================================


def check_preconditions(repo_root: Path, new_name: str) -> list[str]:
    """Reasons this repo is not ready for a new attempt. Empty == ready.

    A new attempt starts from a settled repo. Renaming the branch out from
    under uncommitted work, or leaving a worktree pinned to the old attempt,
    reproduces exactly the debris the clean gate exists to refuse.
    """
    problems: list[str] = []

    if not (repo_root / ".git").exists():
        return [f"{repo_root} is not a git repository root"]

    status = _run(["git", "status", "--porcelain"], cwd=repo_root)
    if status.returncode != 0:
        problems.append(f"git status failed: {status.stderr.strip()}")
    elif status.stdout.strip():
        dirty = len(status.stdout.strip().splitlines())
        problems.append(
            f"working tree has {dirty} uncommitted change(s) -- commit, stash, "
            f"or resolve them first (a rename must not strand work)"
        )

    worktrees = _run(["git", "worktree", "list", "--porcelain"], cwd=repo_root)
    extra = [
        line.split(" ", 1)[1]
        for line in worktrees.stdout.splitlines()
        if line.startswith("worktree ")
    ][1:]
    if extra:
        problems.append(
            f"{len(extra)} extra worktree(s) still registered: "
            f"{', '.join(Path(p).name for p in extra)}"
        )

    # A detached HEAD is NOT a blocker. There is simply no branch to graveyard,
    # so the rename step is skipped and the fresh attempt is cut from the
    # default branch as usual. Refusing here (as this tool first did) told a
    # human to "check out the attempt branch first" -- an instruction the tool
    # can carry out itself, which makes it a ritual rather than a safeguard.

    if not default_branch(repo_root):
        problems.append(
            "cannot resolve origin/HEAD -- run "
            "`git remote set-head origin --auto` so the default branch is known"
        )

    if local_branch_exists(repo_root, new_name):
        problems.append(f"local branch '{new_name}' already exists")
    if remote_branch_exists(repo_root, new_name):
        problems.append(f"origin already has a branch named '{new_name}'")

    return problems


# =============================================================================
# Postconditions -- the point of the tool
# =============================================================================


def verify_postconditions(
    repo_root: Path, new_name: str, base: str
) -> list[str]:
    """Assert the new attempt is actually usable. Empty == verified.

    Each check corresponds to a failure that is invisible locally and only
    surfaces mid-run:

    - branch missing on origin -> `gh pr create --base <name>` fails on the
      first PR (the 2026-07-30 hand-run defect);
    - upstream pointing at the DEFAULT branch rather than its own counterpart
      -> exactly the shape that hid that defect, since `git status` reports a
      perfectly healthy tracking branch;
    - not level with the default branch -> the base carries work and the roll
      would rebuild what already exists.
    """
    problems: list[str] = []

    # #2012: the attempt is a REF, so the assertion is the inverse of what it
    # used to be -- the checkout must be on the DEFAULT branch, not on the
    # attempt. Being handed back on a branch is the defect this closes.
    if base and current_branch(repo_root) != base:
        problems.append(
            f"checkout ended on '{current_branch(repo_root) or 'detached'}', "
            f"expected the default branch '{base}'"
        )
    if not remote_branch_exists(repo_root, new_name):
        problems.append(
            f"origin has no branch '{new_name}' -- PRs targeting it would fail"
        )

    upstream = upstream_of(repo_root, new_name)
    if upstream != f"origin/{new_name}":
        problems.append(
            f"upstream of '{new_name}' is '{upstream or 'unset'}', expected "
            f"'origin/{new_name}' (tracking the default branch is what made "
            f"the 2026-07-30 breakage invisible)"
        )

    ahead = commits_ahead(repo_root, new_name, f"origin/{base}")
    if ahead is None:
        problems.append(f"cannot compare '{new_name}' against origin/{base}")
    elif ahead != 0:
        problems.append(
            f"'{new_name}' is {ahead} commit(s) ahead of origin/{base} -- a "
            f"fresh attempt must start level with the default branch"
        )

    return problems


# =============================================================================
# The operation
# =============================================================================


def plan_steps(old_name: str, new_name: str, base: str) -> list[list[str]]:
    """The exact git commands, in order. Printed on dry runs, executed on --apply.

    ``old_name`` is empty on a detached HEAD: there is no branch to graveyard,
    so that step is simply absent rather than being a reason to stop.
    """
    steps: list[list[str]] = [["git", "fetch", "origin"]]
    # #2012: step off the branch BEFORE renaming it. `git branch -m` moves the
    # checkout along with the branch, so graveyarding the branch you are
    # standing on lands you on `graveyard/<name>` -- worse than where you
    # started. Ending on the default branch is the guarantee, so take it first.
    if old_name != base:
        steps.append(["git", "checkout", base])
    if old_name and old_name != base:
        steps.append(
            ["git", "branch", "-m", old_name, f"{GRAVEYARD_PREFIX}{old_name}"]
        )
    # #2012: create the ref WITHOUT checking it out. Nothing needs the main
    # checkout to stand on the attempt branch -- the worktree is cut from an
    # explicit base and PRs target it by name. Parking the operator on it was a
    # leftover from the manual ritual this tool replaced.
    steps.append(["git", "branch", new_name, f"origin/{base}"])
    steps.append(["git", "push", "-u", "origin", new_name])
    return steps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Graveyard the current speedrun attempt branch and establish a "
            "fresh one from origin's default (#1986)."
        )
    )
    parser.add_argument("--repo", required=True, help="Target repo root path")
    parser.add_argument(
        "--name", required=True,
        help="Name for the new attempt branch (e.g. hardening-run-13)",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually perform the change. Without it, print the plan and exit.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo).resolve()
    new_name = args.name

    problems = check_preconditions(repo_root, new_name)
    if problems:
        print(f"BLOCKED: {repo_root.name} is not ready for a new attempt:")
        for p in problems:
            print(f"  - {p}")
        return 1

    old_name = current_branch(repo_root)
    base = default_branch(repo_root)

    print(f"Repo:            {repo_root}")
    print(f"Current attempt: {old_name or '(detached HEAD -- nothing to graveyard)'}")
    if old_name:
        print(f"Graveyard as:    {GRAVEYARD_PREFIX}{old_name}")
    print(f"New attempt:     {new_name} (from origin/{base})")
    print()

    steps = plan_steps(old_name, new_name, base)
    if not args.apply:
        print("DRY RUN -- would execute:")
        for cmd in steps:
            print(f"  {' '.join(cmd)}")
        print("\nRe-run with --apply to perform it.")
        return 0

    for cmd in steps:
        print(f"  $ {' '.join(cmd)}")
        result = _run(cmd, cwd=repo_root)
        if result.returncode != 0:
            print(f"FAILED: {' '.join(cmd)}")
            print((result.stderr or result.stdout).strip())
            print(
                "\nThe repo may be part-way through the change. "
                f"Current branch: {current_branch(repo_root) or 'unknown'}"
            )
            return 2

    failures = verify_postconditions(repo_root, new_name, base)
    if failures:
        print(f"\nUNVERIFIED: '{new_name}' was created but is not usable:")
        for f in failures:
            print(f"  - {f}")
        return 2

    print(f"\nVERIFIED: {repo_root.name} is on '{new_name}'.")
    print(f"  exists on origin, tracks origin/{new_name}, level with origin/{base}.")
    print(f"  checkout on '{current_branch(repo_root)}' -- an attempt is a ref, not a place to stand.")
    print(f"  previous attempt preserved as '{GRAVEYARD_PREFIX}{old_name}'.")
    print(
        f"\nPass --base-branch {new_name} to BOTH speedrun_clean_check.py and "
        f"orchestrate.py\n  so the gate and the roll judge the same tree "
        f"(#1963/#1968)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
