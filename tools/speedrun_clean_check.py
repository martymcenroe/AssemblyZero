#!/usr/bin/env python3
"""Deterministic clean-state gate for speedrun rolls (#1918).

Debris is the antithesis of idempotent. A killed roll leaves worktrees,
branches, remote refs, open PRs, and stray pipeline artifacts;
`speedrun_reset.py` removes all of those — but only when someone runs it,
and until now nothing VERIFIED zero. This tool is the verification:
read-only enumeration of every debris class the 2026-07-29 killed
phase-4 roll actually produced, exit nonzero listing findings.

Usage:
    poetry run python tools/speedrun_clean_check.py \
        --repo /c/Users/mcwiz/Projects/boostgauge --issue 4

    # several issues at once
    ... --issue 4 --issue 2 --issue 5

Exit codes:
    0 — clean (no debris for the given issues)
    1 — debris found (every finding printed, one per line)
    2 — cannot answer (not a git repo, gh failure, ...)

Wired as:
  - launch preflight in the instrumented run wrapper (a roll must start
    from verified zero);
  - self-verification at the end of `speedrun_reset.py` (a reset that
    cannot prove it finished did not finish).

Read-only by design: this tool never deletes anything. It asks origin
directly (`git ls-remote`) rather than trusting possibly-stale local
remote-tracking refs. `graveyard/*` branches are intentionally exempt —
they are the operator's lab notebook, not debris.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True
    )


def _gh_repo(repo_root: Path) -> str:
    """owner/repo from the origin URL, or '' if undetermined."""
    result = _run(["git", "remote", "get-url", "origin"], cwd=repo_root)
    if result.returncode != 0:
        return ""
    url = result.stdout.strip()
    tail = url.split("github.com")[-1].lstrip(":/")
    return tail.removesuffix(".git")


def find_worktree_debris(repo_root: Path, issue: int) -> list[str]:
    """Worktrees at {repo}-{issue} and {repo}-{issue}-lld."""
    findings: list[str] = []
    result = _run(["git", "worktree", "list", "--porcelain"], cwd=repo_root)
    if result.returncode != 0:
        return [f"ERROR: git worktree list failed: {result.stderr.strip()}"]
    suffixes = {f"{repo_root.name}-{issue}", f"{repo_root.name}-{issue}-lld"}
    for line in result.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        path = Path(line.split(" ", 1)[1])
        if path.name in suffixes:
            findings.append(f"worktree: {path}")
    return findings


def find_local_branch_debris(repo_root: Path, issue: int) -> list[str]:
    """Local branches issue-{N} and {N}-* (graveyard/* exempt by pattern)."""
    # `--format` emits the bare refname. Plain `git branch --list` decorates the
    # current branch with `* ` and a worktree-checked-out branch with `+ `, and
    # the previous `lstrip('* ')` left that `+` in place (#1937) — mangling the
    # report text and, worse, any exact-name comparison downstream. Not parsing
    # decoration at all is the fix; widening the strip set only moves the bug.
    result = _run(
        [
            "git", "branch", "--list", "--format=%(refname:short)",
            f"issue-{issue}", f"{issue}-*",
        ],
        cwd=repo_root,
    )
    if result.returncode != 0:
        return [f"ERROR: git branch --list failed: {result.stderr.strip()}"]
    return [
        f"local branch: {name}"
        for name in (line.strip() for line in result.stdout.splitlines())
        if name
    ]


def find_remote_branch_debris(repo_root: Path, issue: int) -> list[str]:
    """Refs on origin itself — never trust stale remote-tracking state."""
    result = _run(["git", "ls-remote", "--heads", "origin"], cwd=repo_root)
    if result.returncode != 0:
        return [f"ERROR: git ls-remote failed: {result.stderr.strip()}"]
    findings: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        name = parts[1].removeprefix("refs/heads/")
        if name == f"issue-{issue}" or (
            name.startswith(f"{issue}-") and not name.startswith("graveyard/")
        ):
            findings.append(f"remote branch: origin/{name}")
    return findings


def find_open_pr_debris(repo_root: Path, issue: int) -> list[str]:
    """Open PRs whose head branch belongs to this issue's roll."""
    gh_repo = _gh_repo(repo_root)
    if not gh_repo:
        return ["ERROR: cannot determine owner/repo from origin URL"]
    result = _run(
        [
            "gh", "pr", "list", "--repo", gh_repo, "--state", "open",
            "--json", "number,headRefName,title",
        ],
        cwd=repo_root,
    )
    if result.returncode != 0:
        return [f"ERROR: gh pr list failed: {result.stderr.strip()}"]
    try:
        prs = json.loads(result.stdout or "[]")
    except ValueError:
        return ["ERROR: gh pr list returned unparseable JSON"]
    findings: list[str] = []
    for pr in prs:
        head = pr.get("headRefName", "")
        if head == f"issue-{issue}" or head.startswith(f"{issue}-"):
            findings.append(
                f"open PR: #{pr.get('number')} ({head}) {pr.get('title', '')!r}"
            )
    return findings


def _artifact_needles(issue: int) -> tuple[str, ...]:
    """Filename fragments identifying one issue's pipeline artifacts.

    Shared by the untracked and committed scans so the two cannot drift apart
    on what counts as this issue's artifact (#1959).
    """
    return (
        f"lld-{issue:03d}",
        f"lld-{issue}",
        f"spec-{issue:04d}",
        f"spec-{issue}",
    )


def find_artifact_debris(repo_root: Path, issue: int) -> list[str]:
    """Untracked pipeline artifacts under docs/lld for this issue.

    Left in place they make the next run resolve existing artifacts and
    skip stages (#1849) — the quietest debris class of all.
    """
    # -uall: porcelain collapses a fully-untracked directory to one
    # `?? docs/` line, which would hide every artifact inside it.
    result = _run(["git", "status", "--porcelain", "-uall"], cwd=repo_root)
    if result.returncode != 0:
        return [f"ERROR: git status failed: {result.stderr.strip()}"]
    needles = _artifact_needles(issue)
    findings: list[str] = []
    for line in result.stdout.splitlines():
        if not line.startswith("??"):
            continue
        path = line[2:].strip()
        lower = path.lower().replace("\\", "/")
        if lower.startswith("docs/lld/") and any(n in lower for n in needles):
            findings.append(f"untracked artifact: {path}")
    return findings


def find_committed_artifact_debris(repo_root: Path, issue: int) -> list[str]:
    """Pipeline artifacts for this issue already COMMITTED on the current branch.

    The untracked scan above reads `git status`, so it sees only what a killed
    roll left lying around. It cannot see the quieter case: a branch that
    already CONTAINS this issue's finished work. A roll started there finds the
    LLD present and the implementation's tests already green, so it runs fast,
    exits successfully, and produces nothing — while the preflight that exists
    to guarantee a run starts from verified zero signs off on it (#1959).

    That is the state boostgauge's `hardening-run-11` was in when this was
    found: six phases of committed LLDs, specs, and implementations, and a
    CLEAN verdict for every one of the six issues.
    """
    result = _run(["git", "ls-files", "--", "docs/lld"], cwd=repo_root)
    if result.returncode != 0:
        return [f"ERROR: git ls-files failed: {result.stderr.strip()}"]
    needles = _artifact_needles(issue)
    findings: list[str] = []
    for line in result.stdout.splitlines():
        path = line.strip()
        if not path:
            continue
        lower = path.lower().replace("\\", "/")
        if any(n in lower for n in needles):
            findings.append(f"committed artifact: {path}")
    return findings


def describe_base(repo_root: Path) -> str:
    """Current branch and its divergence from origin's default, for context.

    A CLEAN verdict is only meaningful relative to the branch it was measured
    on, so the verdict line carries that branch (#1959).
    """
    branch = _run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root
    )
    if branch.returncode != 0:
        return "unknown branch"
    name = branch.stdout.strip() or "unknown branch"
    count = _run(
        ["git", "rev-list", "--count", f"origin/HEAD..{name}"], cwd=repo_root
    )
    if count.returncode != 0 or not count.stdout.strip().isdigit():
        return f"branch {name}"
    ahead = int(count.stdout.strip())
    if ahead == 0:
        return f"branch {name}, level with origin's default"
    return f"branch {name}, {ahead} commit(s) ahead of origin's default"


def check_repo(repo_root: Path, issues: list[int]) -> list[str]:
    """All findings for the given issues. Empty list == verified clean."""
    findings: list[str] = []
    for issue in issues:
        findings.extend(find_worktree_debris(repo_root, issue))
        findings.extend(find_local_branch_debris(repo_root, issue))
        findings.extend(find_remote_branch_debris(repo_root, issue))
        findings.extend(find_open_pr_debris(repo_root, issue))
        findings.extend(find_artifact_debris(repo_root, issue))
        findings.extend(find_committed_artifact_debris(repo_root, issue))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a target repo carries zero speedrun debris (#1918)."
    )
    parser.add_argument("--repo", required=True, help="Target repo root path")
    parser.add_argument(
        "--issue", type=int, action="append", required=True,
        help="Issue number to check (repeatable)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo).resolve()
    if not (repo_root / ".git").exists():
        print(f"ERROR: {repo_root} is not a git repository root")
        return 2

    findings = check_repo(repo_root, args.issue)
    errors = [f for f in findings if f.startswith("ERROR:")]
    debris = [f for f in findings if not f.startswith("ERROR:")]

    issue_list = ", ".join(f"#{i}" for i in args.issue)
    base = describe_base(repo_root)
    if errors:
        for e in errors:
            print(e)
        return 2
    if debris:
        print(
            f"DEBRIS: {repo_root.name} is NOT clean for {issue_list} on "
            f"{base} -- {len(debris)} finding(s):"
        )
        for d in debris:
            print(f"  {d}")
        # The two artifact classes need opposite remedies, so name them
        # separately rather than leaving the operator to infer (#1959).
        if any(d.startswith("committed artifact:") for d in debris):
            print(
                "\n  The committed artifacts above mean this branch ALREADY "
                "CONTAINS the issue's work,\n  so it is the wrong base for a "
                "roll. A run started here would resolve the existing\n  "
                "artifacts, find the tests already green, and report success "
                "having built nothing.\n  Roll from a base that predates the "
                "work (or reset the issue) rather than deleting\n  these "
                "files: unlike untracked debris, they are somebody's merged "
                "commit."
            )
        return 1
    print(
        f"CLEAN: {repo_root.name} carries zero speedrun debris for "
        f"{issue_list} on {base}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
