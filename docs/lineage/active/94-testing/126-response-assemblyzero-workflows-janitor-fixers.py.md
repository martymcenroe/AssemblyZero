

```python
"""Auto-fix implementations for broken links and stale worktrees.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

import os
import subprocess
from collections import defaultdict
from datetime import datetime

from assemblyzero.workflows.janitor.state import Finding, FixAction

# Deterministic commit message templates — no LLM usage
COMMIT_TEMPLATES: dict[str, str] = {
    "broken_link": "chore: fix {count} broken markdown link(s) (ref #94)",
    "stale_worktree": "chore: prune {count} stale worktree(s) (ref #94)",
}


def fix_broken_links(
    findings: list[Finding], repo_root: str, dry_run: bool
) -> list[FixAction]:
    """Fix broken markdown links by updating references.

    Groups fixes by source file. In dry-run mode, reads files but
    does not write changes.
    """
    actions: list[FixAction] = []

    # Group findings by file
    by_file: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        if f.file_path and f.fix_data and "old_link" in f.fix_data and "new_link" in f.fix_data:
            by_file[f.file_path].append(f)

    files_modified: list[str] = []

    for rel_path, file_findings in by_file.items():
        abs_path = os.path.join(repo_root, rel_path)
        try:
            with open(abs_path, encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            continue

        original_content = content
        for finding in file_findings:
            old_link = finding.fix_data["old_link"]  # type: ignore[index]
            new_link = finding.fix_data["new_link"]  # type: ignore[index]
            content = content.replace(f"]({old_link})", f"]({new_link})")

        if content != original_content:
            if not dry_run:
                with open(abs_path, "w", encoding="utf-8") as fh:
                    fh.write(content)
            files_modified.append(rel_path)

            for finding in file_findings:
                old_link = finding.fix_data["old_link"]  # type: ignore[index]
                new_link = finding.fix_data["new_link"]  # type: ignore[index]
                actions.append(
                    FixAction(
                        category="broken_link",
                        description=f"Fixed broken link in {rel_path}: {old_link} \u2192 {new_link}",
                        files_modified=[rel_path],
                        commit_message=generate_commit_message(
                            "broken_link", len(file_findings), [rel_path]
                        ),
                        applied=not dry_run,
                    )
                )

    return actions


def fix_stale_worktrees(
    findings: list[Finding], repo_root: str, dry_run: bool
) -> list[FixAction]:
    """Prune stale git worktrees.

    Runs `git worktree remove <path>` for each stale worktree.
    In dry-run mode, returns actions without executing.
    """
    actions: list[FixAction] = []

    for finding in findings:
        if not finding.fix_data or "worktree_path" not in finding.fix_data:
            continue

        wt_path = finding.fix_data["worktree_path"]
        branch = finding.fix_data.get("branch", "unknown")

        if not dry_run:
            subprocess.run(
                ["git", "worktree", "remove", wt_path],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )

        actions.append(
            FixAction(
                category="stale_worktree",
                description=(
                    f"{'Pruned' if not dry_run else 'Would prune'} stale worktree "
                    f"at {wt_path} (branch: {branch})"
                ),
                files_modified=[],
                commit_message=generate_commit_message(
                    "stale_worktree", 1, [wt_path]
                ),
                applied=not dry_run,
            )
        )

    return actions


def create_fix_commit(
    repo_root: str, category: str, files: list[str], message: str
) -> None:
    """Stage modified files and create a git commit.

    Uses `git add` for specific files and `git commit -m`.
    Does nothing if no files are provided (idempotent).
    """
    if not files:
        return

    subprocess.run(["git", "add"] + files, cwd=repo_root, check=True)
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    # Ignore "nothing to commit" errors
    if result.returncode != 0 and "nothing to commit" not in result.stdout:
        result.check_returncode()


def generate_commit_message(
    category: str, count: int, details: list[str]
) -> str:
    """Generate a deterministic commit message from templates.

    No LLM usage — pure string formatting.
    """
    template = COMMIT_TEMPLATES.get(
        category, "chore: janitor fix {count} {category} issue(s) (ref #94)"
    )
    return template.format(count=count, category=category)


def create_fix_pr(
    repo_root: str, branch_name: str, commit_message: str
) -> str | None:
    """Create a PR from the current fix branch.

    Creates a new branch, pushes, and uses `gh pr create`.
    Returns the PR URL or None if creation fails.
    """
    try:
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", branch_name],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        result = subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--title",
                commit_message,
                "--body",
                "Automated janitor fixes. See commit history for details.",
                "--label",
                "maintenance",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None
```
