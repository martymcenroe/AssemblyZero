"""Git operations for requirements workflow.

Encapsulates subprocess calls to git for committing and pushing files.
"""

import subprocess
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
        return f"docs: add LLD-{issue_number} via requirements workflow\n\nRef #{issue_number}"
    else:  # issue
        return f"docs: add lineage for {slug} via requirements workflow"


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
        result = subprocess.run(
            ["git", "add", file_path],
            cwd=str(target_repo),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise GitOperationError(f"Failed to stage {file_path}: {result.stderr}")
    
    # Commit with formatted message
    commit_message = format_commit_message(workflow_type, issue_number=issue_number, slug=slug)
    result = subprocess.run(
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
    result = subprocess.run(
        ["git", "push"],
        cwd=str(target_repo),
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        raise GitOperationError(f"Failed to push commit {commit_sha}: {result.stderr}")
    
    return commit_sha