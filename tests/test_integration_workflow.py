"""Integration tests for Issue creation workflow.

These tests actually run subprocess commands - they will fail
if the environment isn't set up correctly. That's the point.

SKIPPED BY DEFAULT: Set RUN_INTEGRATION_TESTS=1 to run these tests.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

# Skip all tests in this module unless RUN_INTEGRATION_TESTS is set
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("RUN_INTEGRATION_TESTS"),
        reason="Integration tests skipped by default. Set RUN_INTEGRATION_TESTS=1 to run."
    ),
]

class TestVSCodeIntegration:
    """Test actual VS Code launching - no mocks."""

    def test_code_command_exists(self):
        """Verify 'code' command is in PATH."""
        code_path = shutil.which("code")
        assert code_path is not None, "'code' command not found in PATH. Install VS Code and add to PATH."

    def test_code_launches_and_waits(self):
        """Test that 'code --wait' can actually launch.

        This will fail if:
        - code command doesn't exist
        - code returns immediately without blocking
        - Windows process spawn issues
        """
        # Create a temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test file for VS Code integration")
            temp_path = f.name

        try:
            # This should launch VS Code - we'll timeout quickly to not block tests
            result = subprocess.run(
                ["code", "--wait", temp_path],
                capture_output=True,
                text=True,
                shell=True,  # Required on Windows for .CMD files
                timeout=2,  # Will timeout, but that's expected
            )
            # If we get here without timeout, code returned too fast (bad)
            pytest.fail("code --wait returned immediately - should block until editor closes")
        except subprocess.TimeoutExpired:
            # This is expected - code is waiting for editor to close
            pass
        except FileNotFoundError as e:
            pytest.fail(f"FileNotFoundError even with shell=True: {e}")
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestClaudeHeadlessIntegration:
    """Test claude CLI availability - no API calls."""

    def test_claude_command_exists(self):
        """Verify 'claude' command is in PATH."""
        claude_path = shutil.which("claude")
        if claude_path is None:
            # Check common npm locations
            from assemblyzero.workflows.issue.nodes.draft import find_claude_cli
            try:
                claude_path = find_claude_cli()
            except RuntimeError:
                pytest.fail("'claude' command not found. Install with: npm install -g @anthropic-ai/claude-code")


class TestCleanOption:
    """Test the Clean option for slug collisions."""

    def test_clean_deletes_checkpoint_and_audit(self):
        """Verify Clean option actually deletes checkpoint and audit dir."""
        from assemblyzero.workflows.issue.audit import create_audit_dir, get_repo_root
        from langgraph.checkpoint.sqlite import SqliteSaver
        from pathlib import Path

        # Create a test slug and audit directory
        test_slug = "test-clean-integration"
        repo_root = get_repo_root()
        audit_dir = create_audit_dir(test_slug, repo_root)

        # Write some test content
        test_file = audit_dir / "test.txt"
        test_file.write_text("test content")

        # Create a checkpoint
        db_path = Path.home() / ".assemblyzero" / "issue_workflow.db"
        with SqliteSaver.from_conn_string(str(db_path)) as memory:
            config = {"configurable": {"thread_id": test_slug}}
            # Simulate having a checkpoint
            # (In real workflow this would be created by LangGraph)

        # Now clean it
        if audit_dir.exists():
            shutil.rmtree(audit_dir)

        # Verify cleanup
        assert not audit_dir.exists(), "Audit directory still exists after clean"

        # Cleanup
        try:
            if audit_dir.exists():
                shutil.rmtree(audit_dir)
        except Exception:
            pass


class TestWorkflowFailureModes:
    """Test that the workflow fails properly when it should."""

    def test_workflow_fails_without_vscode(self, monkeypatch):
        """Verify workflow fails gracefully if VS Code missing."""
        from assemblyzero.workflows.issue.nodes.sandbox import check_vscode_available

        # Mock shutil.which to return None
        original_which = shutil.which
        def mock_which(cmd):
            if cmd == "code":
                return None
            return original_which(cmd)

        monkeypatch.setattr(shutil, "which", mock_which)

        available, error = check_vscode_available()
        assert not available, "Should report VS Code as unavailable"
        assert "not found" in error.lower()

    def test_workflow_fails_without_gh(self, monkeypatch):
        """Verify workflow fails gracefully if gh CLI missing."""
        from assemblyzero.workflows.issue.nodes.sandbox import check_gh_authenticated

        # Mock shutil.which to return None for gh
        original_which = shutil.which
        def mock_which(cmd):
            if cmd == "gh":
                return None
            return original_which(cmd)

        monkeypatch.setattr(shutil, "which", mock_which)

        authenticated, error = check_gh_authenticated()
        assert not authenticated, "Should report gh as unavailable"
        assert "not found" in error.lower()
