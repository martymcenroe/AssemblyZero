

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

    def test_fix_broken_links_multiple_in_same_file(self, tmp_path):
        """fix_broken_links handles multiple broken links in the same file."""
        readme = tmp_path / "README.md"
        readme.write_text(
            "[guide](./docs/old-guide.md)\n"
            "[api](./docs/old-api.md)\n"
        )

        findings = [
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link 1",
                severity="warning",
                fixable=True,
                file_path="README.md",
                line_number=1,
                fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
            ),
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link 2",
                severity="warning",
                fixable=True,
                file_path="README.md",
                line_number=2,
                fix_data={"old_link": "./docs/old-api.md", "new_link": "./docs/api.md"},
            ),
        ]

        actions = fix_broken_links(findings, str(tmp_path), dry_run=False)

        assert len(actions) == 2
        content = readme.read_text()
        assert "./docs/guide.md" in content
        assert "./docs/api.md" in content
        assert "./docs/old-guide.md" not in content
        assert "./docs/old-api.md" not in content

    def test_fix_broken_links_missing_new_link(self, tmp_path):
        """fix_broken_links skips findings with fix_data missing new_link."""
        findings = [
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link",
                severity="warning",
                fixable=True,
                file_path="README.md",
                line_number=1,
                fix_data={"old_link": "./docs/old-guide.md"},
            )
        ]
        actions = fix_broken_links(findings, str(tmp_path), dry_run=False)
        assert actions == []

    def test_fix_broken_links_nonexistent_file(self, tmp_path):
        """fix_broken_links handles missing source file gracefully."""
        findings = [
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link",
                severity="warning",
                fixable=True,
                file_path="nonexistent.md",
                line_number=1,
                fix_data={"old_link": "./old.md", "new_link": "./new.md"},
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

    def test_fix_stale_worktrees_description_applied(self):
        """fix_stale_worktrees description says 'Pruned' when applied."""
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

        assert "Pruned" in actions[0].description
        assert "feature/old" in actions[0].description

    def test_fix_stale_worktrees_description_dry_run(self):
        """fix_stale_worktrees description says 'Would prune' in dry-run."""
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

        assert "Would prune" in actions[0].description

    def test_fix_stale_worktrees_missing_fix_data(self):
        """fix_stale_worktrees skips findings without fix_data."""
        findings = [
            Finding(
                probe="worktrees",
                category="stale_worktree",
                message="Stale worktree",
                severity="warning",
                fixable=True,
                file_path="/home/user/repo-42",
                line_number=None,
                fix_data=None,
            )
        ]

        with patch("subprocess.run") as mock_run:
            actions = fix_stale_worktrees(findings, "/home/user/repo", dry_run=False)

        assert actions == []
        mock_run.assert_not_called()

    def test_fix_stale_worktrees_multiple(self):
        """fix_stale_worktrees handles multiple worktrees."""
        findings = [
            Finding(
                probe="worktrees",
                category="stale_worktree",
                message="Stale worktree 1",
                severity="warning",
                fixable=True,
                file_path="/home/user/repo-42",
                line_number=None,
                fix_data={"worktree_path": "/home/user/repo-42", "branch": "feature/old"},
            ),
            Finding(
                probe="worktrees",
                category="stale_worktree",
                message="Stale worktree 2",
                severity="warning",
                fixable=True,
                file_path="/home/user/repo-99",
                line_number=None,
                fix_data={"worktree_path": "/home/user/repo-99", "branch": "feature/ancient"},
            ),
        ]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            actions = fix_stale_worktrees(findings, "/home/user/repo", dry_run=False)

        assert len(actions) == 2
        assert mock_run.call_count == 2


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

    def test_commit_message_deterministic(self):
        """generate_commit_message is deterministic (same input -> same output)."""
        msg1 = generate_commit_message("broken_link", 5, ["a.md", "b.md"])
        msg2 = generate_commit_message("broken_link", 5, ["a.md", "b.md"])
        assert msg1 == msg2

    def test_commit_message_includes_ref(self):
        """generate_commit_message always includes issue reference."""
        msg = generate_commit_message("broken_link", 1, [])
        assert "ref #94" in msg

        msg2 = generate_commit_message("stale_worktree", 1, [])
        assert "ref #94" in msg2

        msg3 = generate_commit_message("custom_category", 1, [])
        assert "ref #94" in msg3


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

    def test_create_fix_commit_multiple_files(self):
        """create_fix_commit stages multiple files in single git add."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            create_fix_commit(
                "/repo", "broken_link",
                ["README.md", "docs/guide.md"],
                "chore: fix links"
            )

        add_call = mock_run.call_args_list[0]
        assert add_call == call(
            ["git", "add", "README.md", "docs/guide.md"], cwd="/repo", check=True
        )

    def test_create_fix_commit_message_passed(self):
        """create_fix_commit passes correct commit message."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            create_fix_commit("/repo", "broken_link", ["README.md"], "chore: fix 1 broken markdown link(s) (ref #94)")

        commit_call = mock_run.call_args_list[1]
        assert commit_call == call(
            ["git", "commit", "-m", "chore: fix 1 broken markdown link(s) (ref #94)"],
            cwd="/repo",
            capture_output=True,
            text=True,
        )
```
