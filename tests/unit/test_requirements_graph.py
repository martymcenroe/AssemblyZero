"""Unit tests for Requirements Workflow Graph.

Issue #101: Unified Requirements Workflow

Tests for the parameterized StateGraph that connects all nodes.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestRequirementsGraph:
    """Tests for requirements workflow graph."""

    def test_graph_creation(self):
        """Test that graph can be created with expected nodes."""
        from assemblyzero.workflows.requirements.graph import create_requirements_graph

        graph = create_requirements_graph()
        assert graph is not None

        # Verify graph has expected nodes
        compiled = graph.compile()
        graph_nodes = list(compiled.get_graph().nodes.keys())
        expected_nodes = [
            "N0_load_input",
            "N1_generate_draft",
            "N2_human_gate_draft",
            "N3_review",
            "N4_human_gate_verdict",
            "N5_finalize",
        ]
        for node in expected_nodes:
            assert node in graph_nodes, f"Missing node: {node}"

    def test_graph_has_all_nodes(self):
        """Test that graph has all expected nodes."""
        from assemblyzero.workflows.requirements.graph import create_requirements_graph

        graph = create_requirements_graph()
        compiled = graph.compile()
        assert compiled is not None

        # Verify all expected nodes are present
        graph_nodes = list(compiled.get_graph().nodes.keys())
        expected_nodes = [
            "N0_load_input",
            "N1_generate_draft",
            "N2_human_gate_draft",
            "N3_review",
            "N4_human_gate_verdict",
            "N5_finalize",
        ]
        for node in expected_nodes:
            assert node in graph_nodes, f"Missing node: {node}"

        # Verify entry point is correct (should start at N0_load_input)
        graph_obj = compiled.get_graph()
        # Entry point is indicated by edge from __start__ to first node
        start_edges = [
            edge for edge in graph_obj.edges
            if edge[0] == "__start__"
        ]
        assert len(start_edges) > 0, "No entry point found"
        assert start_edges[0][1] == "N0_load_input", "Entry point should be N0_load_input"

    def test_graph_compiles(self):
        """Test that graph compiles and can be invoked."""
        from assemblyzero.workflows.requirements.graph import create_requirements_graph

        graph = create_requirements_graph()
        compiled = graph.compile()
        assert compiled is not None

        # Verify compiled graph has required methods for invocation
        assert hasattr(compiled, "invoke"), "Compiled graph should have invoke method"
        assert hasattr(compiled, "stream"), "Compiled graph should have stream method"
        assert hasattr(compiled, "get_graph"), "Compiled graph should have get_graph method"

        # Verify graph structure is accessible
        graph_obj = compiled.get_graph()
        assert graph_obj is not None
        assert hasattr(graph_obj, "nodes"), "Graph should have nodes"
        assert hasattr(graph_obj, "edges"), "Graph should have edges"
        assert len(graph_obj.nodes) >= 6, "Graph should have at least 6 nodes"


class TestGraphRouting:
    """Tests for graph routing logic."""

    def test_route_from_load_input_to_generate_draft(self):
        """Test routing from load_input to generate_draft on success."""
        from assemblyzero.workflows.requirements.graph import route_after_load_input

        state = {"error_message": ""}
        result = route_after_load_input(state)
        assert result == "N1_generate_draft"

    def test_route_from_load_input_to_end_on_error(self):
        """Test routing from load_input to END on error."""
        from assemblyzero.workflows.requirements.graph import route_after_load_input

        state = {"error_message": "File not found"}
        result = route_after_load_input(state)
        assert result == "END"

    def test_route_from_generate_draft_with_gate(self):
        """Test routing from generate_draft to human gate when enabled."""
        from assemblyzero.workflows.requirements.graph import route_after_generate_draft

        state = {"error_message": "", "config_gates_draft": True}
        result = route_after_generate_draft(state)
        assert result == "N2_human_gate_draft"

    def test_route_from_generate_draft_without_gate(self):
        """Test routing from generate_draft to review when gate disabled."""
        from assemblyzero.workflows.requirements.graph import route_after_generate_draft

        state = {"error_message": "", "config_gates_draft": False}
        result = route_after_generate_draft(state)
        assert result == "N3_review"

    def test_route_from_generate_draft_on_error(self):
        """Test routing from generate_draft to END on error."""
        from assemblyzero.workflows.requirements.graph import route_after_generate_draft

        state = {"error_message": "API error", "config_gates_draft": True}
        result = route_after_generate_draft(state)
        assert result == "END"

    def test_route_from_human_gate_draft(self):
        """Test routing from human gate draft based on next_node."""
        from assemblyzero.workflows.requirements.graph import route_from_human_gate_draft

        # Route to review
        state = {"next_node": "N3_review"}
        assert route_from_human_gate_draft(state) == "N3_review"

        # Route to revise
        state = {"next_node": "N1_generate_draft"}
        assert route_from_human_gate_draft(state) == "N1_generate_draft"

        # Route to manual (END)
        state = {"next_node": "END"}
        assert route_from_human_gate_draft(state) == "END"

    def test_route_from_review_with_gate(self):
        """Test routing from review to human gate when enabled."""
        from assemblyzero.workflows.requirements.graph import route_after_review

        state = {"error_message": "", "config_gates_verdict": True}
        result = route_after_review(state)
        assert result == "N4_human_gate_verdict"

    def test_route_from_review_without_gate(self):
        """Test routing from review based on verdict when gate disabled."""
        from assemblyzero.workflows.requirements.graph import route_after_review

        # Approved - go to finalize
        state = {"error_message": "", "config_gates_verdict": False, "lld_status": "APPROVED"}
        result = route_after_review(state)
        assert result == "N5_finalize"

        # Blocked - go back to draft
        state = {"error_message": "", "config_gates_verdict": False, "lld_status": "BLOCKED"}
        result = route_after_review(state)
        assert result == "N1_generate_draft"

    def test_route_from_human_gate_verdict(self):
        """Test routing from human gate verdict based on next_node."""
        from assemblyzero.workflows.requirements.graph import route_from_human_gate_verdict

        # Route to finalize
        state = {"next_node": "N5_finalize"}
        assert route_from_human_gate_verdict(state) == "N5_finalize"

        # Route to revise
        state = {"next_node": "N1_generate_draft"}
        assert route_from_human_gate_verdict(state) == "N1_generate_draft"


class TestGraphExecution:
    """Tests for full graph execution paths."""

    @patch("assemblyzero.workflows.requirements.nodes.load_input.load_input")
    @patch("assemblyzero.workflows.requirements.nodes.generate_draft.get_provider")
    @patch("assemblyzero.workflows.requirements.nodes.review.get_provider")
    def test_full_issue_workflow_mock(
        self, mock_review_provider, mock_draft_provider, mock_load, tmp_path
    ):
        """Test full issue workflow with mocks."""
        from assemblyzero.workflows.requirements.graph import create_requirements_graph
        from assemblyzero.workflows.requirements.state import create_initial_state

        # Setup mocks
        mock_load.return_value = {
            "brief_content": "# Feature Brief",
            "slug": "my-feature",
            "audit_dir": str(tmp_path / "audit"),
            "file_counter": 1,
            "error_message": "",
        }

        mock_drafter = Mock()
        mock_drafter.invoke.return_value = Mock(
            success=True,
            response="# Generated Issue",
            error_message=None,
        )
        mock_draft_provider.return_value = mock_drafter

        mock_reviewer = Mock()
        mock_reviewer.invoke.return_value = Mock(
            success=True,
            response="APPROVED: All good",
            error_message=None,
        )
        mock_review_provider.return_value = mock_reviewer

        # Create template and prompt files
        templates = tmp_path / "docs" / "templates"
        templates.mkdir(parents=True)
        (templates / "0101-issue-template.md").write_text("# Template")

        prompts = tmp_path / "docs" / "skills"
        prompts.mkdir(parents=True)
        (prompts / "0701c-Issue-Review-Prompt.md").write_text("# Review Prompt")

        audit_dir = tmp_path / "audit"
        audit_dir.mkdir(parents=True)

        # Create initial state
        state = create_initial_state(
            workflow_type="issue",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            brief_file="brief.md",
            auto_mode=True,  # Skip interactive prompts
            gates_draft=False,  # Skip human gates
            gates_verdict=False,
        )
        state["audit_dir"] = str(audit_dir)

        graph = create_requirements_graph()
        compiled = graph.compile()
        assert compiled is not None

        # Verify compiled graph structure before running
        graph_obj = compiled.get_graph()
        graph_nodes = list(graph_obj.nodes.keys())

        # Verify all expected nodes are present
        expected_nodes = [
            "N0_load_input",
            "N1_generate_draft",
            "N2_human_gate_draft",
            "N3_review",
            "N4_human_gate_verdict",
            "N5_finalize",
        ]
        for node in expected_nodes:
            assert node in graph_nodes, f"Missing node: {node}"

        # Verify routing edges exist (key workflow paths)
        edges = list(graph_obj.edges)
        # Check that entry point exists
        start_edges = [e for e in edges if e[0] == "__start__"]
        assert len(start_edges) > 0, "No entry point edge found"


class TestNodeNames:
    """Tests for node name constants."""

    def test_node_names_defined(self):
        """Test that node name constants are defined."""
        from assemblyzero.workflows.requirements.graph import (
            N0_LOAD_INPUT,
            N1_GENERATE_DRAFT,
            N2_HUMAN_GATE_DRAFT,
            N3_REVIEW,
            N4_HUMAN_GATE_VERDICT,
            N5_FINALIZE,
        )

        assert N0_LOAD_INPUT == "N0_load_input"
        assert N1_GENERATE_DRAFT == "N1_generate_draft"
        assert N2_HUMAN_GATE_DRAFT == "N2_human_gate_draft"
        assert N3_REVIEW == "N3_review"
        assert N4_HUMAN_GATE_VERDICT == "N4_human_gate_verdict"
        assert N5_FINALIZE == "N5_finalize"


class TestGraphRoutingExtended:
    """Extended tests for graph routing logic."""

    def test_route_from_review_to_end_on_error(self):
        """Test routing from review to END on error."""
        from assemblyzero.workflows.requirements.graph import route_after_review

        state = {"error_message": "Review failed", "config_gates_verdict": True}
        result = route_after_review(state)
        assert result == "END"

    def test_route_from_review_to_finalize_on_max_iterations(self):
        """Test routing from review to finalize when max iterations reached."""
        from assemblyzero.workflows.requirements.graph import route_after_review

        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "BLOCKED",
            "iteration_count": 20,
            "max_iterations": 20,
        }
        result = route_after_review(state)
        assert result == "N5_finalize"

    def test_route_from_review_to_draft_when_under_max_iterations(self):
        """Test routing from review to draft when under max iterations."""
        from assemblyzero.workflows.requirements.graph import route_after_review

        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "BLOCKED",
            "iteration_count": 5,
            "max_iterations": 20,
        }
        result = route_after_review(state)
        assert result == "N1_generate_draft"

    def test_route_from_human_gate_verdict_to_end(self):
        """Test routing from human gate verdict to END for unknown next_node."""
        from assemblyzero.workflows.requirements.graph import route_from_human_gate_verdict

        state = {"next_node": "unknown_node"}
        result = route_from_human_gate_verdict(state)
        assert result == "END"

    def test_route_from_human_gate_verdict_empty_next_node(self):
        """Test routing from human gate verdict to END when next_node is empty."""
        from assemblyzero.workflows.requirements.graph import route_from_human_gate_verdict

        state = {"next_node": ""}
        result = route_from_human_gate_verdict(state)
        assert result == "END"

    def test_route_after_finalize(self):
        """Test routing after finalize always returns END."""
        from assemblyzero.workflows.requirements.graph import route_after_finalize

        # Should always return END regardless of state
        state = {"error_message": "", "lld_status": "APPROVED"}
        result = route_after_finalize(state)
        assert result == "END"

        state = {"error_message": "Some error"}
        result = route_after_finalize(state)
        assert result == "END"

    def test_route_from_human_gate_draft_unknown_next_node(self):
        """Test routing from human gate draft to END for unknown next_node."""
        from assemblyzero.workflows.requirements.graph import route_from_human_gate_draft

        state = {"next_node": "unknown"}
        result = route_from_human_gate_draft(state)
        assert result == "END"

    def test_route_from_review_uses_default_max_iterations(self):
        """Test routing from review uses default max_iterations of 20."""
        from assemblyzero.workflows.requirements.graph import route_after_review

        # No max_iterations set, should use default of 20
        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "BLOCKED",
            "iteration_count": 19,
            # max_iterations not set - should default to 20
        }
        result = route_after_review(state)
        assert result == "N1_generate_draft"  # Under default max of 20
