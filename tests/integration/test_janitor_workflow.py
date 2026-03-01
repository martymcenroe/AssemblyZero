"""Integration test for full janitor workflow using LocalFileReporter.

Issue #94: Lu-Tze: The Janitor
Test IDs: T290, T300, T310, T320, T330, T400
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.janitor.graph import build_janitor_graph
from assemblyzero.workflows.janitor.state import (
    Finding,
    JanitorState,
    ProbeResult,
)


def _make_initial_state(tmp_path: Path, **overrides) -> JanitorState:
    """Helper to build a test JanitorState."""
    defaults: JanitorState = {
        "repo_root": str(tmp_path),
        "scope": ["links"],
        "auto_fix": True,
        "dry_run": False,
        "silent": True,
        "create_pr": False,
        "reporter_type": "local",
        "probe_results": [],
        "all_findings": [],
        "fix_actions": [],
        "unfixable_findings": [],
        "report_url": None,
        "exit_code": 0,
    }
    defaults.update(overrides)
    return defaults


class TestFullWorkflowIntegration:
    """Integration tests for complete janitor workflow. T290, T400."""

    def test_clean_run_exits_zero(self, tmp_path):
        """T290/T400: Full workflow with no findings exits cleanly."""
        mock_probe = MagicMock(return_value=ProbeResult(probe="links", status="ok"))

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("links", mock_probe)],
        ):
            graph = build_janitor_graph()
            state = _make_initial_state(tmp_path)
            final = graph.invoke(state)

        assert final["exit_code"] == 0
        assert final["all_findings"] == []

    def test_unfixable_findings_create_local_report(self, tmp_path):
        """Integration: unfixable findings create local report file."""
        unfixable_finding = Finding(
            probe="todo",
            category="stale_todo",
            message="Stale TODO in helper.py:42",
            severity="info",
            fixable=False,
            file_path="tools/helper.py",
            line_number=42,
        )
        mock_probe = MagicMock(
            return_value=ProbeResult(
                probe="todo", status="findings", findings=[unfixable_finding]
            )
        )

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("todo", mock_probe)],
        ):
            graph = build_janitor_graph()
            state = _make_initial_state(tmp_path, scope=["todo"])
            final = graph.invoke(state)

        assert final["exit_code"] == 1
        assert final["report_url"] is not None
        assert Path(final["report_url"]).exists()
        report_content = Path(final["report_url"]).read_text(encoding="utf-8")
        assert "Janitor Report" in report_content
        assert "stale_todo" in report_content

    def test_fixable_findings_auto_fixed(self, tmp_path):
        """T320: Broken link auto-fixed with unique target."""
        # Create mock repo
        readme = tmp_path / "README.md"
        readme.write_text("[guide](./docs/old-guide.md)\n")
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")

        fixable_finding = Finding(
            probe="links",
            category="broken_link",
            message="Broken link",
            severity="warning",
            fixable=True,
            file_path="README.md",
            line_number=1,
            fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
        )
        mock_probe = MagicMock(
            return_value=ProbeResult(
                probe="links", status="findings", findings=[fixable_finding]
            )
        )

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("links", mock_probe)],
        ), patch(
            "assemblyzero.workflows.janitor.fixers.create_fix_commit"
        ):
            graph = build_janitor_graph()
            state = _make_initial_state(tmp_path)
            final = graph.invoke(state)

        assert final["exit_code"] == 0
        assert len(final["fix_actions"]) > 0
        assert final["fix_actions"][0].applied is True
        # Verify file was actually modified
        assert "./docs/guide.md" in readme.read_text()

    def test_dry_run_no_modifications(self, tmp_path):
        """T310: Dry-run prevents file modification."""
        readme = tmp_path / "README.md"
        original = "[guide](./docs/old-guide.md)\n"
        readme.write_text(original)

        fixable_finding = Finding(
            probe="links",
            category="broken_link",
            message="Broken link",
            severity="warning",
            fixable=True,
            file_path="README.md",
            line_number=1,
            fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
        )
        mock_probe = MagicMock(
            return_value=ProbeResult(
                probe="links", status="findings", findings=[fixable_finding]
            )
        )

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("links", mock_probe)],
        ):
            graph = build_janitor_graph()
            state = _make_initial_state(tmp_path, dry_run=True)
            final = graph.invoke(state)

        # File should not be modified in dry-run
        assert readme.read_text() == original
        assert len(final["fix_actions"]) > 0
        assert final["fix_actions"][0].applied is False

    def test_mixed_findings_fix_then_report(self, tmp_path):
        """T330: Mixed fixable/unfixable → fix, then report unfixable."""
        readme = tmp_path / "README.md"
        readme.write_text("[guide](./docs/old-guide.md)\n")
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")

        fixable = Finding(
            probe="links", category="broken_link", message="Broken",
            severity="warning", fixable=True, file_path="README.md",
            line_number=1,
            fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
        )
        unfixable = Finding(
            probe="todo", category="stale_todo", message="Old TODO",
            severity="info", fixable=False, file_path="helper.py", line_number=10,
        )
        mock_probe = MagicMock(
            return_value=ProbeResult(
                probe="links", status="findings", findings=[fixable, unfixable]
            )
        )

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("links", mock_probe)],
        ), patch(
            "assemblyzero.workflows.janitor.fixers.create_fix_commit"
        ):
            graph = build_janitor_graph()
            state = _make_initial_state(tmp_path)
            final = graph.invoke(state)

        assert final["exit_code"] == 1  # Unfixable remain
        assert len(final["fix_actions"]) > 0
        assert len(final["unfixable_findings"]) == 1
        assert final["report_url"] is not None