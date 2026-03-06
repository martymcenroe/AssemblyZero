"""Stale and detached git worktree detection probe.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

from assemblyzero.utils.shell import run_command
from datetime import datetime, timedelta, timezone

from assemblyzero.workflows.janitor.state import Finding, ProbeResult

# Worktrees with no commits in this many days AND branch merged are considered stale
STALE_DAYS_THRESHOLD = 14


def probe_worktrees(repo_root: str) -> ProbeResult:
    """Detect stale and detached git worktrees.

    A worktree is considered stale if:
    - No commits on its branch in 14+ days AND branch is merged to main, OR
    - The branch has been deleted (detached HEAD with no branch)
    """
    worktrees = list_worktrees(repo_root)
    findings: list[Finding] = []

    for wt in worktrees:
        # Skip bare worktrees
        if wt.get("bare"):
            continue

        branch = wt.get("branch")
        wt_path = wt["path"]

        # Skip main worktree (the repo root itself)
        if branch and branch.endswith("/main"):
            continue

        if wt.get("detached"):
            # Detached HEAD — branch deleted
            findings.append(
                Finding(
                    probe="worktrees",
                    category="stale_worktree",
                    message=f"Detached worktree at {wt_path}: branch deleted",
                    severity="warning",
                    fixable=True,
                    file_path=wt_path,
                    line_number=None,
                    fix_data={"worktree_path": wt_path, "branch": None},
                )
            )
            continue

        if not branch:
            continue

        # Extract short branch name from refs/heads/...
        short_branch = branch.replace("refs/heads/", "")

        last_commit = get_branch_last_commit_date(repo_root, short_branch)
        if last_commit is None:
            continue

        now = datetime.now(timezone.utc)
        age_days = (now - last_commit).days

        if age_days >= STALE_DAYS_THRESHOLD and is_branch_merged(
            repo_root, short_branch
        ):
            findings.append(
                Finding(
                    probe="worktrees",
                    category="stale_worktree",
                    message=(
                        f"Stale worktree at {wt_path}: branch {short_branch} "
                        f"merged to main, last commit {age_days} days ago"
                    ),
                    severity="warning",
                    fixable=True,
                    file_path=wt_path,
                    line_number=None,
                    fix_data={
                        "worktree_path": wt_path,
                        "branch": short_branch,
                    },
                )
            )

    if findings:
        return ProbeResult(probe="worktrees", status="findings", findings=findings)
    return ProbeResult(probe="worktrees", status="ok")


def list_worktrees(repo_root: str) -> list[dict]:
    """Parse output of `git worktree list --porcelain`.

    Returns list of dicts with keys: path, HEAD, branch, bare, detached.
    """
    result = run_command(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    worktrees: list[dict] = []
    current: dict = {}

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            if current:
                current.setdefault("bare", False)
                current.setdefault("detached", False)
                worktrees.append(current)
                current = {}
            continue

        if line.startswith("worktree "):
            current["path"] = line[len("worktree "):]
        elif line.startswith("HEAD "):
            current["HEAD"] = line[len("HEAD "):]
        elif line.startswith("branch "):
            current["branch"] = line[len("branch "):]
        elif line == "bare":
            current["bare"] = True
        elif line == "detached":
            current["detached"] = True

    # Don't forget the last entry
    if current:
        current.setdefault("bare", False)
        current.setdefault("detached", False)
        worktrees.append(current)

    return worktrees


def get_branch_last_commit_date(
    repo_root: str, branch: str
) -> datetime | None:
    """Get the date of the most recent commit on a branch.

    Returns None if the branch doesn't exist.
    """
    result = run_command(
        ["git", "log", "-1", "--format=%aI", branch],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    date_str = result.stdout.strip()
    if not date_str:
        return None

    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None


def is_branch_merged(
    repo_root: str, branch: str, target: str = "main"
) -> bool:
    """Check if branch has been merged into target branch."""
    result = run_command(
        ["git", "branch", "--merged", target],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False

    merged_branches = [b.strip().lstrip("* ") for b in result.stdout.splitlines()]
    return branch in merged_branches
