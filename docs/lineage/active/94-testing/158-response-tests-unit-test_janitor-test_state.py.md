

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

    def test_finding_severity_values(self):
        """Finding accepts all valid severity values."""
        for severity in ("info", "warning", "critical"):
            f = Finding(
                probe="links",
                category="test",
                message="test",
                severity=severity,
                fixable=False,
            )
            assert f.severity == severity

    def test_finding_probe_scope_values(self):
        """Finding accepts all valid probe scope values."""
        for probe in ("links", "worktrees", "harvest", "todo"):
            f = Finding(
                probe=probe,
                category="test",
                message="test",
                severity="info",
                fixable=False,
            )
            assert f.probe == probe

    def test_finding_fixable_flag(self):
        """Finding correctly stores fixable flag."""
        fixable = Finding(
            probe="links", category="c", message="m", severity="info", fixable=True
        )
        unfixable = Finding(
            probe="todo", category="c", message="m", severity="info", fixable=False
        )
        assert fixable.fixable is True
        assert unfixable.fixable is False


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

    def test_probe_result_with_findings(self):
        """ProbeResult with findings status contains findings list."""
        finding = Finding(
            probe="links",
            category="broken_link",
            message="Broken link",
            severity="warning",
            fixable=True,
        )
        pr = ProbeResult(probe="links", status="findings", findings=[finding])
        assert pr.status == "findings"
        assert len(pr.findings) == 1
        assert pr.findings[0] is finding

    def test_probe_result_default_findings_list(self):
        """ProbeResult default findings list is independent per instance."""
        pr1 = ProbeResult(probe="links", status="ok")
        pr2 = ProbeResult(probe="worktrees", status="ok")
        pr1.findings.append(
            Finding(probe="links", category="c", message="m", severity="info", fixable=False)
        )
        assert len(pr2.findings) == 0


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

    def test_fix_action_empty_files_modified(self):
        """FixAction can have empty files_modified (e.g., worktree prune)."""
        fa = FixAction(
            category="stale_worktree",
            description="Pruned worktree",
            files_modified=[],
            commit_message="chore: prune 1 stale worktree(s) (ref #94)",
            applied=True,
        )
        assert fa.files_modified == []

    def test_fix_action_commit_message(self):
        """FixAction stores commit message correctly."""
        msg = "chore: fix 3 broken markdown link(s) (ref #94)"
        fa = FixAction(
            category="broken_link",
            description="Fixed links",
            files_modified=["a.md", "b.md"],
            commit_message=msg,
            applied=True,
        )
        assert fa.commit_message == msg


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

    def test_state_full_scope(self):
        """JanitorState accepts all four probe scopes. T010."""
        state: JanitorState = {
            "repo_root": "/repo",
            "scope": ["links", "worktrees", "harvest", "todo"],
            "auto_fix": True,
            "dry_run": False,
            "silent": False,
            "create_pr": False,
            "reporter_type": "github",
            "probe_results": [],
            "all_findings": [],
            "fix_actions": [],
            "unfixable_findings": [],
            "report_url": None,
            "exit_code": 0,
        }
        assert len(state["scope"]) == 4
        assert state["reporter_type"] == "github"

    def test_state_with_populated_results(self):
        """JanitorState can hold populated probe results and findings."""
        finding = Finding(
            probe="links",
            category="broken_link",
            message="Broken",
            severity="warning",
            fixable=True,
            file_path="README.md",
            line_number=15,
            fix_data={"old_link": "./old.md", "new_link": "./new.md"},
        )
        probe_result = ProbeResult(
            probe="links", status="findings", findings=[finding]
        )
        fix_action = FixAction(
            category="broken_link",
            description="Fixed link",
            files_modified=["README.md"],
            commit_message="chore: fix 1 broken markdown link(s) (ref #94)",
            applied=True,
        )
        state: JanitorState = {
            "repo_root": "/repo",
            "scope": ["links"],
            "auto_fix": True,
            "dry_run": False,
            "silent": False,
            "create_pr": False,
            "reporter_type": "local",
            "probe_results": [probe_result],
            "all_findings": [finding],
            "fix_actions": [fix_action],
            "unfixable_findings": [],
            "report_url": "/repo/janitor-reports/report.md",
            "exit_code": 0,
        }
        assert len(state["probe_results"]) == 1
        assert len(state["all_findings"]) == 1
        assert len(state["fix_actions"]) == 1
        assert state["report_url"] is not None

    def test_state_reporter_type_values(self):
        """JanitorState accepts both reporter type values."""
        for reporter_type in ("github", "local"):
            state: JanitorState = {
                "repo_root": "/repo",
                "scope": [],
                "auto_fix": False,
                "dry_run": False,
                "silent": False,
                "create_pr": False,
                "reporter_type": reporter_type,
                "probe_results": [],
                "all_findings": [],
                "fix_actions": [],
                "unfixable_findings": [],
                "report_url": None,
                "exit_code": 0,
            }
            assert state["reporter_type"] == reporter_type

    def test_state_exit_codes(self):
        """JanitorState supports exit codes 0, 1, and 2."""
        for code in (0, 1, 2):
            state: JanitorState = {
                "repo_root": "/repo",
                "scope": [],
                "auto_fix": False,
                "dry_run": False,
                "silent": False,
                "create_pr": False,
                "reporter_type": "local",
                "probe_results": [],
                "all_findings": [],
                "fix_actions": [],
                "unfixable_findings": [],
                "report_url": None,
                "exit_code": code,
            }
            assert state["exit_code"] == code

    def test_state_boolean_flags(self):
        """JanitorState boolean flags store correctly."""
        state: JanitorState = {
            "repo_root": "/repo",
            "scope": [],
            "auto_fix": False,
            "dry_run": True,
            "silent": True,
            "create_pr": True,
            "reporter_type": "local",
            "probe_results": [],
            "all_findings": [],
            "fix_actions": [],
            "unfixable_findings": [],
            "report_url": None,
            "exit_code": 0,
        }
        assert state["auto_fix"] is False
        assert state["dry_run"] is True
        assert state["silent"] is True
        assert state["create_pr"] is True
```
