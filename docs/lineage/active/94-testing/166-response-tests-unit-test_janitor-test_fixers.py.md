

```python
"""Tests for janitor fixers.

Issue #94: Lu-Tze: The Janitor
Test IDs: T110-T140, T230-T260
"""

from unittest.mock import MagicMock, call, patch

from assemblyzero.workflows.janitor.fixers import (
    create_fix_commit,
    fix_broken_links,
    fix_stale_worktrees,
    generate_commit_message,
)
from assemblyzero.workflows.janitor.state import Finding


class TestFixBrokenLinks:
    """Test broken link fixer. T110, T120, T230, T240."""

    def test_fix_broken_links_updates_file(self, tmp_path):
        """T110/T230: fix_broken_links replaces broken link with correct target."""
        readme = tmp_path / "README.md"
        readme.write_text("[guide](./docs/old-guide.md)\n[other](./valid.md)\n")

        findings = [
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link",
                severity="warning",
                fixable=True,
                file_path="README.md",
                line_number=1,
                fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
            )
        ]

        actions = fix_broken_links(findings, str(tmp_path), dry_run=False)

        assert len(actions) == 1
        assert actions[0].applied is True
        content = readme.read_text()
        assert "./docs/guide.md" in content
        assert "./docs/old-guide.md" not in content
        assert "./valid.md" in content  # Other links untouched

    def test_fix_broken_links_dry_run(self, tmp_path):
        """T120/T240: fix_broken_links with dry_run=True does not modify files."""
        readme = tmp_path / "README.md"
        original_content = "[guide](./docs/old-guide.md)\n"
        readme.write_text(original_content)

        findings = [
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link",
                severity="warning",
                fixable=True,
                file_path="README.md",
                line_number=1,
                fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
            )
        ]

        actions = fix_broken_links(findings, str(tmp_path), dry_run=True)

        assert len(actions) == 1
        assert actions[0].applied is False
        assert readme.read_text() == original_content

    def test_fix_broken_links_no_fix_data(self, tmp_path):
        """fix_broken_links skips findings without fix_data."""
        findings = [
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link",
                severity="warning",
                fixable=True,
                file_path="README.md",
                line_number=1,
                fix_data=None,
            )
        ]
        actions = fix_broken_links(findings, str(tmp_path), dry_run=False)
        assert actions == []


class TestFixStaleWorktrees:
    """Test stale worktree fixer. T130, T250."""

    def test_fix_stale_worktrees_calls_git_remove(self):
        """T130/T250: fix_stale_worktrees invokes git worktree remove."""
        findings = [
            Finding(
                probe="worktrees",
                category="stale_worktree",
                message="Stale worktree",
                severity="warning",
                fixable=True,
                file_path="/home/user/repo-42",
                line_number=None,
                fix_data={"worktree_path": "/home/user/repo-42", "branch": "feature/old"},
            )
        ]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            actions = fix_stale_worktrees(findings, "/home/user/repo", dry_run=False)

        assert len(actions) == 1
        assert actions[0].applied is True
        assert actions[0].category == "stale_worktree"
        mock_run.assert_called_once_with(
            ["git", "worktree", "remove", "/home/user/repo-42"],
            cwd="/home/user/repo",
            capture_output=True,
            text=True,
        )

    def test_fix_stale_worktrees_dry_run(self):
        """fix_stale_worktrees in dry-run does not call subprocess."""
        findings = [
            Finding(
                probe="worktrees",
                category="stale_worktree",
                message="Stale worktree",
                severity="warning",
                fixable=True,
                file_path="/home/user/repo-42",
                line_number=None,
                fix_data={"worktree_path": "/home/user/repo-42", "branch": "feature/old"},
            )
        ]

        with patch("subprocess.run") as mock_run:
            actions = fix_stale_worktrees(findings, "/home/user/repo", dry_run=True)

        assert len(actions) == 1
        assert actions[0].applied is False
        mock_run.assert_not_called()


class TestCommitMessage:
    """Test commit message generation. T140, T260."""

    def test_links_commit_message(self):
        """T140/T260: generate_commit_message produces expected template for links."""
        msg = generate_commit_message("broken_link", 3, ["README.md", "docs/guide.md"])
        assert msg == "chore: fix 3 broken markdown link(s) (ref #94)"

    def test_worktrees_commit_message(self):
        """generate_commit_message produces expected template for worktrees."""
        msg = generate_commit_message("stale_worktree", 1, ["/path/to/wt"])
        assert msg == "chore: prune 1 stale worktree(s) (ref #94)"

    def test_single_link_commit_message(self):
        """generate_commit_message works for single link fix."""
        msg = generate_commit_message("broken_link", 1, ["README.md"])
        assert msg == "chore: fix 1 broken markdown link(s) (ref #94)"

    def test_unknown_category_fallback(self):
        """generate_commit_message uses fallback for unknown categories."""
        msg = generate_commit_message("unknown_thing", 2, [])
        assert "janitor fix" in msg
        assert "2" in msg


class TestCreateFixCommit:
    """Test git commit creation."""

    def test_create_fix_commit_stages_and_commits(self):
        """create_fix_commit calls git add and git commit."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            create_fix_commit("/repo", "broken_link", ["README.md"], "chore: fix links")

        assert mock_run.call_count == 2
        mock_run.assert_any_call(
            ["git", "add", "README.md"], cwd="/repo", check=True
        )

    def test_create_fix_commit_empty_files_noop(self):
        """create_fix_commit does nothing with empty files list."""
        with patch("subprocess.run") as mock_run:
            create_fix_commit("/repo", "broken_link", [], "chore: fix links")
        mock_run.assert_not_called()
```
