"""Git operations for requirements workflow.

Encapsulates subprocess calls to git for committing and pushing files.

#1459 (this PR): LLD outputs now flow through a per-issue worktree + PR
rather than being committed directly to the target's current branch. The
new helpers `lld_worktree_path_for`, `setup_lld_worktree`, and
`commit_and_pr` mirror the impl-stage pattern at
`orchestrator/stages.py:493-532`. `commit_and_push` is kept for the
issue-workflow path which still commits to the operator's checkout.
"""

from assemblyzero.utils.shell import run_command
from pathlib import Path
from typing import Optional


class GitOperationError(Exception):
    """Raised when a git operation fails."""
    pass


def format_commit_message(workflow_type: str, issue_number: Optional[int] = None, slug: Optional[str] = None) -> str:
    """Format commit message based on workflow type.

    Args:
        workflow_type: Either "lld" or "issue"
        issue_number: Issue number (required for lld workflow)
        slug: Issue slug (required for issue workflow)

    Returns:
        Formatted commit message
    """
    if workflow_type == "lld":
        # Issue #238: LLDs reference, not close. The original issue stays open
        # through the implementation phase; the impl PR closes it. Preserved
        # across the worktree+PR rewire (#1459) — the LLD PR body uses
        # `No-Issue:` for pr-sentinel rather than `Closes #N`.
        return (
            f"docs: add LLD-{issue_number} via requirements workflow\n\n"
            f"Ref #{issue_number}"
        )
    else:  # issue
        return f"docs: add lineage for {slug} via requirements workflow"


def lld_worktree_path_for(target_repo: Path | str, issue_number: int) -> Path:
    """Return the worktree path for an LLD workflow run.

    Mirrors `orchestrator/artifacts.worktree_path_for` (impl stage) but with
    a `-lld` suffix so the LLD worktree is distinct from any later impl
    worktree for the same issue. Closes #1459.

    Args:
        target_repo: Path to the target repository.
        issue_number: GitHub issue number.

    Returns:
        Sibling path: {target_parent}/{target_name}-{issue_number}-lld
    """
    repo = Path(target_repo)
    return repo.parent / f"{repo.name}-{issue_number}-lld"


def setup_lld_worktree(target_repo: Path | str, issue_number: int) -> tuple[Path, str]:
    """Carve (or reuse) a worktree for the LLD workflow.

    Branch name is ``{issue_number}-lld``. If the worktree path already
    exists (e.g. a prior LLD run for the same issue), it is reused; we do
    not re-create. Closes #1459.

    Args:
        target_repo: Path to the target repository.
        issue_number: GitHub issue number.

    Returns:
        (worktree_path, branch_name)

    Raises:
        GitOperationError: If worktree creation fails.
    """
    target_repo = Path(target_repo)
    worktree_path = lld_worktree_path_for(target_repo, issue_number)
    branch_name = f"{issue_number}-lld"

    if worktree_path.is_dir():
        # Reuse existing worktree from a prior LLD run for the same issue.
        return worktree_path, branch_name

    result = run_command(
        ["git", "-C", str(target_repo), "worktree", "add",
         str(worktree_path), "-b", branch_name],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Branch may already exist from a prior aborted run; try without -b
        result2 = run_command(
            ["git", "-C", str(target_repo), "worktree", "add",
             str(worktree_path), branch_name],
            capture_output=True,
            text=True,
        )
        if result2.returncode != 0:
            raise GitOperationError(
                f"Failed to create LLD worktree at {worktree_path}: "
                f"{result.stderr or result2.stderr}"
            )
    return worktree_path, branch_name


def commit_and_pr(
    created_files: list[str],
    worktree_path: Path | str,
    target_repo: Path | str,
    issue_number: int,
    branch_name: str,
    base_branch: str,
) -> tuple[str, str]:
    """Commit, push, and open a PR for LLD-workflow outputs.

    Stages files relative to the worktree (the file paths in
    ``created_files`` should be within ``worktree_path``), commits with a
    ``Closes #N`` message, pushes the branch with --set-upstream, and
    opens a PR via the gh CLI carrying ``Closes #N`` in both title and
    body. Closes #1459.

    Args:
        created_files: List of absolute file paths inside the worktree.
        worktree_path: Path to the LLD worktree.
        target_repo: Path to the target repository (used for --repo).
        issue_number: GitHub issue number for Closes #N.
        branch_name: Branch checked out in the worktree.
        base_branch: Integration branch the PR targets (#1754
            attempt-branch model — the branch the target repo was
            standing on at invocation, never a hardcoded main).

    Returns:
        (commit_sha, pr_url). Empty strings if there was nothing to do.

    Raises:
        GitOperationError: If git or gh operation fails.
    """
    if not created_files:
        return "", ""

    worktree_path = Path(worktree_path)
    target_repo = Path(target_repo)

    # Stage files.
    for file_path in created_files:
        result = run_command(
            ["git", "add", file_path],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise GitOperationError(
                f"Failed to stage {file_path} in worktree {worktree_path}: "
                f"{result.stderr}"
            )

    # Commit.
    commit_message = format_commit_message(
        workflow_type="lld", issue_number=issue_number
    )
    result = run_command(
        ["git", "commit", "-m", commit_message],
        cwd=str(worktree_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitOperationError(
            f"Failed to commit in worktree {worktree_path}: {result.stderr}"
        )

    commit_sha = ""
    if result.stdout:
        parts = result.stdout.split()
        if len(parts) >= 2:
            commit_sha = parts[1].rstrip("]")

    # Push branch with --set-upstream.
    result = run_command(
        ["git", "push", "--set-upstream", "origin", branch_name],
        cwd=str(worktree_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitOperationError(
            f"Failed to push branch {branch_name}: {result.stderr}"
        )

    # Determine --repo argument from target_repo's origin remote so the PR
    # lands in the right GitHub repo regardless of the operator's cwd.
    repo_arg = _resolve_repo_arg(target_repo)

    # Open PR. Issue #238 establishes that LLDs reference (not close) the
    # issue — the impl PR is what closes it. pr-sentinel demands Closes #N
    # OR a No-Issue: exemption; we use the latter with a specific reason so
    # the issue stays open through the implementation phase. Closes #1459.
    pr_title = (
        f"docs: add LLD-{issue_number} via requirements workflow "
        f"(Ref #{issue_number})"
    )
    pr_body = (
        f"No-Issue: LLD design artifact for issue #{issue_number}; the "
        f"issue remains open through the implementation phase, which is "
        f"what closes it. Ref #{issue_number}.\n\n"
        "LLD generated by the requirements workflow. Review the LLD "
        "content under `docs/lld/active/` and merge to land it on "
        f"`{base_branch}`."
    )
    # #1754: the PR base is the integration branch captured at invocation
    # (attempt-branch model) — never a hardcoded main.
    pr_cmd = ["gh", "pr", "create",
              "--title", pr_title, "--body", pr_body,
              "--base", base_branch, "--head", branch_name]
    if repo_arg:
        pr_cmd += ["--repo", repo_arg]
    result = run_command(
        pr_cmd,
        cwd=str(worktree_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitOperationError(
            f"Failed to create PR for {branch_name}: {result.stderr}"
        )

    pr_url = result.stdout.strip()
    return commit_sha, pr_url


def _resolve_repo_arg(target_repo: Path) -> str:
    """Best-effort extract `{owner}/{repo}` from the target's origin remote.

    Returns an empty string if the remote cannot be parsed; gh CLI will then
    fall back to its own auto-detection. Closes #1459.
    """
    result = run_command(
        ["git", "-C", str(target_repo), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    url = result.stdout.strip()
    # Handle https://github.com/owner/repo(.git) and git@github.com:owner/repo.git
    for prefix in ("https://github.com/", "git@github.com:"):
        if url.startswith(prefix):
            tail = url[len(prefix):]
            if tail.endswith(".git"):
                tail = tail[:-4]
            return tail
    return ""


def commit_and_push(
    created_files: list[str],
    workflow_type: str,
    target_repo: Path | str,
    issue_number: Optional[int] = None,
    slug: Optional[str] = None,
) -> str:
    """Commit and push created files.
    
    Args:
        created_files: List of file paths to commit (relative to repo root)
        workflow_type: Either "lld" or "issue"
        target_repo: Path to target repository
        issue_number: Issue number (required for lld workflow)
        slug: Issue slug (required for issue workflow)
        
    Returns:
        Commit SHA (short form) if commit was created, empty string if no files
        
    Raises:
        GitOperationError: If git operation fails
    """
    if not created_files:
        return ""
    
    target_repo = Path(target_repo)
    
    # Stage each file individually
    for file_path in created_files:
        result = run_command(
            ["git", "add", file_path],
            cwd=str(target_repo),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise GitOperationError(f"Failed to stage {file_path}: {result.stderr}")
    
    # Commit with formatted message
    commit_message = format_commit_message(workflow_type, issue_number=issue_number, slug=slug)
    result = run_command(
        ["git", "commit", "-m", commit_message],
        cwd=str(target_repo),
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        raise GitOperationError(f"Failed to commit: {result.stderr}")
    
    # Extract commit SHA from output (format: "[branch sha] message")
    commit_sha = ""
    if result.stdout:
        parts = result.stdout.split()
        if len(parts) >= 2:
            commit_sha = parts[1].rstrip("]")
    
    # Push to remote
    result = run_command(
        ["git", "push"],
        cwd=str(target_repo),
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        raise GitOperationError(f"Failed to push commit {commit_sha}: {result.stderr}")
    
    return commit_sha
