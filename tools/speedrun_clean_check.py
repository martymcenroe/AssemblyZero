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
    needles = (
        f"lld-{issue:03d}",
        f"lld-{issue}",
        f"spec-{issue:04d}",
        f"spec-{issue}",
    )
    findings: list[str] = []
    for line in result.stdout.splitlines():
        if not line.startswith("??"):
            continue
        path = line[2:].strip()
        lower = path.lower().replace("\\", "/")
        if lower.startswith("docs/lld/") and any(n in lower for n in needles):
            findings.append(f"untracked artifact: {path}")
    return findings


def check_repo(repo_root: Path, issues: list[int]) -> list[str]:
    """All findings for the given issues. Empty list == verified clean."""
    findings: list[str] = []
    for issue in issues:
        findings.extend(find_worktree_debris(repo_root, issue))
        findings.extend(find_local_branch_debris(repo_root, issue))
        findings.extend(find_remote_branch_debris(repo_root, issue))
        findings.extend(find_open_pr_debris(repo_root, issue))
        findings.extend(find_artifact_debris(repo_root, issue))
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
    if errors:
        for e in errors:
            print(e)
        return 2
    if debris:
        print(
            f"DEBRIS: {repo_root.name} is NOT clean for {issue_list} — "
            f"{len(debris)} finding(s):"
        )
        for d in debris:
            print(f"  {d}")
        return 1
    print(f"CLEAN: {repo_root.name} carries zero speedrun debris for {issue_list}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
