"""Tests for janitor graph construction and routing.

Issue #94: Lu-Tze: The Janitor
Test IDs: T190-T230, T310-T350
"""

from unittest.mock import MagicMock, patch

from assemblyzero.workflows.janitor.graph import (
    build_janitor_graph,
    route_after_fix,
    route_after_sweep,
)
from assemblyzero.workflows.janitor.state import (
    Finding,
    JanitorState,
)


class TestRouteAfterSweep:
    """Test conditional routing after sweep. T190-T210, T310-T330."""

    def test_no_findings_returns_end(self):
        """T190/T310: route_after_sweep returns __end__ when no findings."""
        state = {"all_findings": [], "auto_fix": True}
        assert route_after_sweep(state) == "__end__"

    def test_fixable_auto_fix_returns_fixer(self):
        """T200/T320: route_after_sweep returns n1_fixer with fixable findings + auto_fix."""
        state = {
            "all_findings": [
                Finding(probe="links", category="broken_link", message="m", severity="warning", fixable=True)
            ],
            "auto_fix": True,
        }
        assert route_after_sweep(state) == "n1_fixer"

    def test_fixable_no_auto_fix_returns_reporter(self):
        """route_after_sweep returns n2_reporter when fixable but auto_fix=False."""
        state = {
            "all_findings": [
                Finding(probe="links", category="broken_link", message="m", severity="warning", fixable=True)
            ],
            "auto_fix": False,
        }
        assert route_after_sweep(state) == "n2_reporter"

    def test_unfixable_only_returns_reporter(self):
        """T210/T330: route_after_sweep returns n2_reporter with only unfixable."""
        state = {
            "all_findings": [
                Finding(probe="todo", category="stale_todo", message="m", severity="info", fixable=False)
            ],
            "auto_fix": True,
        }
        assert route_after_sweep(state) == "n2_reporter"

    def test_mixed_fixable_and_unfixable_returns_fixer(self):
        """route_after_sweep returns n1_fixer when mixed findings + auto_fix."""
        state = {
            "all_findings": [
                Finding(probe="links", category="broken_link", message="m", severity="warning", fixable=True),
                Finding(probe="todo", category="stale_todo", message="m", severity="info", fixable=False),
            ],
            "auto_fix": True,
        }
        assert route_after_sweep(state) == "n1_fixer"

    def test_mixed_fixable_and_unfixable_no_auto_fix_returns_reporter(self):
        """route_after_sweep returns n2_reporter when mixed findings + auto_fix=False."""
        state = {
            "all_findings": [
                Finding(probe="links", category="broken_link", message="m", severity="warning", fixable=True),
                Finding(probe="todo", category="stale_todo", message="m", severity="info", fixable=False),
            ],
            "auto_fix": False,
        }
        assert route_after_sweep(state) == "n2_reporter"

    def test_empty_state_defaults(self):
        """route_after_sweep handles missing keys with defaults."""
        state = {}
        assert route_after_sweep(state) == "__end__"

    def test_multiple_fixable_returns_fixer(self):
        """route_after_sweep returns n1_fixer with multiple fixable findings."""
        state = {
            "all_findings": [
                Finding(probe="links", category="broken_link", message="m1", severity="warning", fixable=True),
                Finding(probe="links", category="broken_link", message="m2", severity="warning", fixable=True),
                Finding(probe="worktrees", category="stale_worktree", message="m3", severity="warning", fixable=True),
            ],
            "auto_fix": True,
        }
        assert route_after_sweep(state) == "n1_fixer"


class TestRouteAfterFix:
    """Test conditional routing after fix. T220, T230, T340, T350."""

    def test_all_fixed_returns_end(self):
        """T220/T340: route_after_fix returns __end__ when unfixable list empty."""
        state = {"unfixable_findings": []}
        assert route_after_fix(state) == "__end__"

    def test_unfixable_remain_returns_reporter(self):
        """T230/T350: route_after_fix returns n2_reporter when unfixable exist."""
        state = {
            "unfixable_findings": [
                Finding(probe="todo", category="stale_todo", message="m", severity="info", fixable=False)
            ]
        }
        assert route_after_fix(state) == "n2_reporter"

    def test_multiple_unfixable_returns_reporter(self):
        """route_after_fix returns n2_reporter with multiple unfixable findings."""
        state = {
            "unfixable_findings": [
                Finding(probe="todo", category="stale_todo", message="m1", severity="info", fixable=False),
                Finding(probe="harvest", category="cross_project_drift", message="m2", severity="warning", fixable=False),
            ]
        }
        assert route_after_fix(state) == "n2_reporter"

    def test_empty_state_defaults(self):
        """route_after_fix handles missing keys with defaults."""
        state = {}
        assert route_after_fix(state) == "__end__"


class TestBuildJanitorGraph:
    """Test graph construction."""

    def test_build_janitor_graph_compiles(self):
        """build_janitor_graph returns a compiled graph."""
        graph = build_janitor_graph()
        # Compiled graph should be callable (has invoke method)
        assert hasattr(graph, "invoke")

    def test_graph_with_no_findings(self):
        """Graph exits cleanly with no findings (all probes return ok)."""
        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[],
        ):
            graph = build_janitor_graph()
            initial_state: JanitorState = {
                "repo_root": "/fake/repo",
                "scope": [],
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
            final_state = graph.invoke(initial_state)

        assert final_state["all_findings"] == []
        assert final_state["exit_code"] == 0

    def test_graph_with_empty_scope(self):
        """Graph with empty scope produces no findings and exits cleanly."""
        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[],
        ):
            graph = build_janitor_graph()
            initial_state: JanitorState = {
                "repo_root": "/fake/repo",
                "scope": [],
                "auto_fix": False,
                "dry_run": True,
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
            final_state = graph.invoke(initial_state)

        assert final_state["probe_results"] == []
        assert final_state["all_findings"] == []
        assert final_state["exit_code"] == 0

    def test_graph_sweeper_to_end_no_findings(self):
        """Graph routes sweeper → END when probes return ok."""
        from assemblyzero.workflows.janitor.state import ProbeResult

        mock_probe = MagicMock(
            return_value=ProbeResult(probe="links", status="ok", findings=[])
        )

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("links", mock_probe)],
        ):
            graph = build_janitor_graph()
            initial_state: JanitorState = {
                "repo_root": "/fake/repo",
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
            final_state = graph.invoke(initial_state)

        assert final_state["exit_code"] == 0
        assert len(final_state["probe_results"]) == 1
        assert final_state["probe_results"][0].status == "ok"

    def test_graph_sweeper_to_reporter_unfixable_only(self, tmp_path):
        """Graph routes sweeper → reporter when only unfixable findings exist."""
        from assemblyzero.workflows.janitor.state import ProbeResult

        unfixable_finding = Finding(
            probe="todo",
            category="stale_todo",
            message="Old TODO",
            severity="info",
            fixable=False,
            file_path="helper.py",
            line_number=10,
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
            initial_state: JanitorState = {
                "repo_root": str(tmp_path),
                "scope": ["todo"],
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
            final_state = graph.invoke(initial_state)

        assert final_state["exit_code"] == 1
        assert final_state["report_url"] is not None
        assert len(final_state["unfixable_findings"]) == 1

    def test_graph_sweeper_to_fixer_to_end_all_fixed(self, tmp_path):
        """Graph routes sweeper → fixer → END when all findings are fixable and fixed."""
        from assemblyzero.workflows.janitor.state import ProbeResult

        # Create mock repo with broken link
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
            "assemblyzero.workflows.janitor.graph.create_fix_commit"
        ):
            graph = build_janitor_graph()
            initial_state: JanitorState = {
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
            final_state = graph.invoke(initial_state)

        assert final_state["exit_code"] == 0
        assert len(final_state["fix_actions"]) > 0
        assert final_state["unfixable_findings"] == []

    def test_graph_sweeper_to_fixer_to_reporter_mixed(self, tmp_path):
        """Graph routes sweeper → fixer → reporter when mixed findings."""
        from assemblyzero.workflows.janitor.state import ProbeResult

        readme = tmp_path / "README.md"
        readme.write_text("[guide](./docs/old-guide.md)\n")
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")

        fixable = Finding(
            probe="links",
            category="broken_link",
            message="Broken",
            severity="warning",
            fixable=True,
            file_path="README.md",
            line_number=1,
            fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
        )
        unfixable = Finding(
            probe="todo",
            category="stale_todo",
            message="Old TODO",
            severity="info",
            fixable=False,
            file_path="helper.py",
            line_number=10,
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
            "assemblyzero.workflows.janitor.graph.create_fix_commit"
        ):
            graph = build_janitor_graph()
            initial_state: JanitorState = {
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
            final_state = graph.invoke(initial_state)

        assert final_state["exit_code"] == 1
        assert len(final_state["fix_actions"]) > 0
        assert len(final_state["unfixable_findings"]) == 1
        assert final_state["report_url"] is not None

    def test_graph_dry_run_no_file_modifications(self, tmp_path):
        """Graph in dry-run mode does not modify files."""
        from assemblyzero.workflows.janitor.state import ProbeResult

        readme = tmp_path / "README.md"
        original_content = "[guide](./docs/old-guide.md)\n"
        readme.write_text(original_content)

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
            initial_state: JanitorState = {
                "repo_root": str(tmp_path),
                "scope": ["links"],
                "auto_fix": True,
                "dry_run": True,
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
            final_state = graph.invoke(initial_state)

        # File should not be modified in dry-run
        assert readme.read_text() == original_content
        assert len(final_state["fix_actions"]) > 0
        assert final_state["fix_actions"][0].applied is False

    def test_graph_auto_fix_false_skips_fixer(self, tmp_path):
        """Graph routes sweeper → reporter when auto_fix=False even with fixable findings."""
        from assemblyzero.workflows.janitor.state import ProbeResult

        fixable_finding = Finding(
            probe="links",
            category="broken_link",
            message="Broken link",
            severity="warning",
            fixable=True,
            file_path="README.md",
            line_number=1,
            fix_data={"old_link": "./docs/old.md", "new_link": "./docs/new.md"},
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
            initial_state: JanitorState = {
                "repo_root": str(tmp_path),
                "scope": ["links"],
                "auto_fix": False,
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
            final_state = graph.invoke(initial_state)

        # Should go directly to reporter, not fixer
        assert final_state["exit_code"] == 1
        assert final_state["report_url"] is not None
        # Fix actions should be empty since fixer was skipped
        assert final_state["fix_actions"] == []

    def test_graph_probe_error_handled(self, tmp_path):
        """Graph handles probe errors gracefully."""
        from assemblyzero.workflows.janitor.state import ProbeResult

        error_result = ProbeResult(
            probe="links",
            status="error",
            findings=[],
            error_message="RuntimeError: test error",
        )
        mock_probe = MagicMock(return_value=error_result)

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("links", mock_probe)],
        ):
            graph = build_janitor_graph()
            initial_state: JanitorState = {
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
            final_state = graph.invoke(initial_state)

        # Error probe with no findings → exit cleanly
        assert final_state["exit_code"] == 0
        assert len(final_state["probe_results"]) == 1
        assert final_state["probe_results"][0].status == "error"

    def test_graph_multiple_probes(self, tmp_path):
        """Graph processes multiple probes correctly."""
        from assemblyzero.workflows.janitor.state import ProbeResult

        links_result = ProbeResult(probe="links", status="ok", findings=[])
        todo_finding = Finding(
            probe="todo",
            category="stale_todo",
            message="Old TODO",
            severity="info",
            fixable=False,
            file_path="test.py",
            line_number=5,
        )
        todo_result = ProbeResult(
            probe="todo", status="findings", findings=[todo_finding]
        )

        mock_links_probe = MagicMock(return_value=links_result)
        mock_todo_probe = MagicMock(return_value=todo_result)

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("links", mock_links_probe), ("todo", mock_todo_probe)],
        ):
            graph = build_janitor_graph()
            initial_state: JanitorState = {
                "repo_root": str(tmp_path),
                "scope": ["links", "todo"],
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
            final_state = graph.invoke(initial_state)

        assert len(final_state["probe_results"]) == 2
        assert len(final_state["all_findings"]) == 1
        assert final_state["exit_code"] == 1  # Unfixable finding remains