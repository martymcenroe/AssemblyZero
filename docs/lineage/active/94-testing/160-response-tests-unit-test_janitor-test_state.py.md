```python
"""Tests for janitor state structures.

Issue #94: Lu-Tze: The Janitor
Test IDs: T010, T390
"""

from assemblyzero.workflows.janitor.state import (
    Finding,
    FixAction,
    JanitorState,
    ProbeResult,
)


class TestFinding:
    """Test Finding dataclass."""

    def test_finding_creation_with_defaults(self):
        """Finding can be created with minimal fields."""
        f = Finding(
            probe="links",
            category="broken_link",
            message="test message",
            severity="warning",
            fixable=True,
        )
        assert f.probe == "links"
        assert f.file_path is None
        assert f.line_number is None
        assert f.fix_data is None

    def test_finding_creation_with_all_fields(self):
        """Finding can be created with all fields."""
        f = Finding(
            probe="links",
            category="broken_link",
            message="Broken link",
            severity="warning",
            fixable=True,
            file_path="README.md",
            line_number=15,
            fix_data={"old_link": "./old.md", "new_link": "./new.md"},
        )
        assert f.file_path == "README.md"
        assert f.line_number == 15
        assert f.fix_data["old_link"] == "./old.md"


class TestProbeResult:
    """Test ProbeResult dataclass."""

    def test_probe_result_ok(self):
        """ProbeResult with ok status has empty findings."""
        pr = ProbeResult(probe="links", status="ok")
        assert pr.findings == []
        assert pr.error_message is None

    def test_probe_result_error(self):
        """ProbeResult with error status has error message."""
        pr = ProbeResult(
            probe="links", status="error", error_message="RuntimeError: boom"
        )
        assert pr.status == "error"
        assert pr.error_message == "RuntimeError: boom"


class TestFixAction:
    """Test FixAction dataclass."""

    def test_fix_action_applied(self):
        """FixAction records applied fix."""
        fa = FixAction(
            category="broken_link",
            description="Fixed link",
            files_modified=["README.md"],
            commit_message="chore: fix 1 broken markdown link(s) (ref #94)",
            applied=True,
        )
        assert fa.applied is True
        assert fa.files_modified == ["README.md"]

    def test_fix_action_dry_run(self):
        """FixAction records dry-run (not applied)."""
        fa = FixAction(
            category="broken_link",
            description="Would fix link",
            files_modified=["README.md"],
            commit_message="chore: fix 1 broken markdown link(s) (ref #94)",
            applied=False,
        )
        assert fa.applied is False


class TestJanitorState:
    """Test JanitorState TypedDict. T010, T390."""

    def test_initial_state_construction(self):
        """JanitorState can be constructed with all required keys. T390."""
        state: JanitorState = {
            "repo_root": "/home/user/projects/repo",
            "scope": ["links", "worktrees"],
            "auto_fix": True,
            "dry_run": False,
            "silent": False,
            "create_pr": False,
            "reporter_type": "local",
            "probe_results": [],
            "all_findings": [],
            "fix_actions": [],
            "unfixable_findings": [],
            "report_url": None,
            "exit_code": 0,
        }
        assert state["repo_root"] == "/home/user/projects/repo"
        assert state["scope"] == ["links", "worktrees"]
        assert state["exit_code"] == 0
```
