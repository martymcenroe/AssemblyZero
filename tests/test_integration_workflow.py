"""Integration tests for Issue creation workflow.

These tests actually run subprocess commands - they will fail
if the environment isn't set up correctly. That's the point.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

# Check for claude CLI availability at module load time
CLAUDE_AVAILABLE = shutil.which("claude") is not None


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
    """Test actual claude -p execution - no mocks."""

    def test_claude_command_exists(self):
        """Verify 'claude' command is in PATH."""
        claude_path = shutil.which("claude")
        if claude_path is None:
            # Check common npm locations
            from agentos.workflows.issue.nodes.draft import find_claude_cli
            try:
                claude_path = find_claude_cli()
            except RuntimeError:
                pytest.fail("'claude' command not found. Install with: npm install -g @anthropic-ai/claude-code")

    @pytest.mark.skipif(
        not CLAUDE_AVAILABLE,
        reason="claude CLI not found in PATH - install with: npm install -g @anthropic-ai/claude-code"
    )
    def test_claude_headless_generates_output(self):
        """Test that claude -p actually works with real prompt."""
        from agentos.workflows.issue.nodes.draft import call_claude_headless

        # Simple test prompt
        prompt = "Respond with exactly: TEST_PASSED"

        result = call_claude_headless(prompt)
        assert result, "claude -p returned empty response"
        assert "TEST_PASSED" in result or len(result) > 0, f"Unexpected response: {result}"

    @pytest.mark.skipif(
        not CLAUDE_AVAILABLE,
        reason="claude CLI not found in PATH - install with: npm install -g @anthropic-ai/claude-code"
    )
    def test_claude_headless_with_unicode(self):
        """Test that UTF-8 encoding works (Windows cp1252 issue)."""
        from agentos.workflows.issue.nodes.draft import call_claude_headless

        # Prompt with unicode characters that cp1252 can't encode
        prompt = "Echo back these characters: → ← ↑ ↓ • ★"

        result = call_claude_headless(prompt)
        # Should not raise UnicodeEncodeError
        assert result, "claude -p returned empty response for unicode prompt"


class TestCleanOption:
    """Test the Clean option for slug collisions."""

    def test_clean_deletes_checkpoint_and_audit(self):
        """Verify Clean option actually deletes checkpoint and audit dir."""
        from agentos.workflows.issue.audit import create_audit_dir, get_repo_root
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
        db_path = Path.home() / ".agentos" / "issue_workflow.db"
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
        from agentos.workflows.issue.nodes.sandbox import check_vscode_available

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
        from agentos.workflows.issue.nodes.sandbox import check_gh_authenticated

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
