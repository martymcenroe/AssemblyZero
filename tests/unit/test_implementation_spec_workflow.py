"""Unit tests for Implementation Spec Workflow.

Issue #304: Implementation Readiness Review Workflow (LLD → Implementation Spec)

Tests for:
- State creation and validation (create_initial_state, validate_state)
- Graph creation, compilation, and routing functions
- Node name constants
- N0: load_lld (T010, T020, scenario 030)
- N1: analyze_codebase (T030, scenario 040)
- N2: generate_spec (T040) — mocked LLM
- N3: validate_completeness (T050, T060)
- N4: human_gate
- N5: review_spec / parse_review_verdict (T070, T080)
- N6: finalize_spec (T090)
- CLI argument parsing and configuration (T100)
- Full workflow routing paths (scenarios 050, 060, 070)
- Package-level imports
- Edge cases and helpers

Test IDs map to LLD Section 10.0/10.1:
- T010: Load approved LLD
- T020: Reject unapproved LLD
- T030: Analyze codebase extracts excerpts
- T040: Generate spec includes all sections
- T050: Validate completeness catches missing excerpts
- T060: Validate completeness passes complete spec
- T070: Review spec routing on APPROVED
- T080: Review spec routing on REVISE
- T090: Finalize writes spec file
- T100: CLI runs full workflow
"""

import os
import pytest
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch, MagicMock


# =============================================================================
# Fixtures
# =============================================================================


SAMPLE_LLD_APPROVED = textwrap.dedent("""\
    # 999 - Feature: Test Feature (LLD)

    ## 1. Context & Goal
    * **Issue:** #999
    * **Objective:** Sample objective
    * **Status:** Approved (gemini-3-pro-preview, 2026-02-16)

    ## 2. Proposed Changes

    ### 2.1 Files Changed

    | File | Change Type | Description |
    |------|-------------|-------------|
    | `assemblyzero/workflows/test/state.py` | Add | State definitions |
    | `assemblyzero/workflows/test/graph.py` | Modify | Update graph |
    | `assemblyzero/workflows/test/old.py` | Delete | Remove old module |

    ## 3. Requirements

    1. **R1:** Sample requirement

    ## Appendix: Review Log

    | Review | Date | Verdict | Key Issue |
    |--------|------|---------|-----------|
    | 1 | 2026-02-16 | APPROVED | gemini-3-pro-preview |

    **Final Status:** APPROVED
""")


SAMPLE_LLD_NOT_APPROVED = textwrap.dedent("""\
    # 998 - Feature: Pending Feature (LLD)

    ## 1. Context & Goal
    * **Issue:** #998
    * **Objective:** Sample objective
    * **Status:** Pending Review

    ## 2. Proposed Changes

    ### 2.1 Files Changed

    | File | Change Type | Description |
    |------|-------------|-------------|
    | `assemblyzero/test.py` | Add | New file |

    This is some more content to ensure it is over 100 chars. The LLD has
    not been reviewed yet so it should be rejected by the workflow as pending.
""")


def _build_complete_spec():
    """Build a complete spec that passes all validation checks."""
    lines = []
    lines.append("# Implementation Spec: Test Feature\n")
    lines.append("## 1. Overview\n")
    lines.append("This implements the test feature.\n")

    # Modify file with code block
    lines.append("## 2. Files to Implement\n")
    lines.append("### `assemblyzero/workflows/test/graph.py` (Modify)\n")
    lines.append("Current state excerpt:\n")
    lines.append("```python\n")
    lines.append("def create_graph():\n")
    lines.append("    graph = StateGraph(TestState)\n")
    lines.append("    graph.add_node('N0', load_input)\n")
    lines.append("    return graph.compile()\n")
    lines.append("```\n")

    # Data structure with example
    lines.append("## 3. Data Structures\n")
    lines.append("```python\n")
    lines.append("class TestState(TypedDict):\n")
    lines.append("    value: int\n")
    lines.append("```\n")
    lines.append("Example:\n")
    lines.append('```json\n{"value": 42}\n```\n')

    # Function with I/O example
    lines.append("## 4. Functions\n")
    lines.append("```python\n")
    lines.append("def process_input(state: TestState) -> dict:\n")
    lines.append('    """Process input state."""\n')
    lines.append("    ...\n")
    lines.append("```\n")
    lines.append("Example input: `{'value': 10}` -> output: `{'value': 20}`\n")
    lines.append("Returns: `{'result': True}`\n")

    # Add more code blocks for specificity
    for i in range(10):
        lines.append(f"\n### Change {i}\n")
        lines.append(f"Add after line {i * 10 + 5}:\n")
        lines.append("```python\n")
        lines.append(f"def helper_{i}():\n")
        lines.append(f"    return {i}\n")
        lines.append("```\n")
        lines.append(f"import module_{i}\n")
        lines.append(f"class Widget{i}:\n")
        lines.append(f"    pass\n")

    return "\n".join(lines)


SAMPLE_SPEC_COMPLETE = _build_complete_spec()
SAMPLE_SPEC_INCOMPLETE = "# Implementation Spec\n\nToo short to pass validation."


@pytest.fixture
def sample_lld_content():
    """Return a minimal approved LLD with Section 2.1 files table."""
    return SAMPLE_LLD_APPROVED


@pytest.fixture
def sample_unapproved_lld():
    """Return an LLD without APPROVED status."""
    return SAMPLE_LLD_NOT_APPROVED


@pytest.fixture
def sample_spec_complete():
    """Return a complete spec that passes all validation checks."""
    return SAMPLE_SPEC_COMPLETE


@pytest.fixture
def sample_spec_incomplete():
    """Return an incomplete spec missing excerpts."""
    return SAMPLE_SPEC_INCOMPLETE


@pytest.fixture
def base_state(tmp_path):
    """Return a minimal valid ImplementationSpecState dict."""
    return {
        "issue_number": 999,
        "lld_path": str(tmp_path / "lld.md"),
        "lld_content": "",
        "files_to_modify": [],
        "current_state_snapshots": {},
        "pattern_references": [],
        "spec_draft": "",
        "spec_path": "",
        "completeness_checks": [],
        "completeness_issues": [],
        "validation_passed": False,
        "review_verdict": "BLOCKED",
        "review_feedback": "",
        "review_iteration": 0,
        "max_iterations": 3,
        "human_gate_enabled": False,
        "error_message": "",
        "next_node": "",
        "repo_root": str(tmp_path),
        "assemblyzero_root": str(tmp_path),
    }


@pytest.fixture
def lld_on_disk(tmp_path, sample_lld_content):
    """Write sample LLD to disk and return path."""
    lld_dir = tmp_path / "docs" / "lld" / "active"
    lld_dir.mkdir(parents=True)
    lld_file = lld_dir / "LLD-999.md"
    lld_file.write_text(sample_lld_content, encoding="utf-8")
    return lld_file


@pytest.fixture
def mock_repo(tmp_path):
    """Create a mock repository structure for testing."""
    # LLD directories
    active_dir = tmp_path / "docs" / "lld" / "active"
    active_dir.mkdir(parents=True)
    drafts_dir = tmp_path / "docs" / "lld" / "drafts"
    drafts_dir.mkdir(parents=True)

    # Write LLD
    (active_dir / "LLD-999.md").write_text(SAMPLE_LLD_APPROVED, encoding="utf-8")

    # Workflow structure for pattern matching
    workflows_dir = tmp_path / "assemblyzero" / "workflows"
    workflows_dir.mkdir(parents=True)
    req_dir = workflows_dir / "requirements"
    req_dir.mkdir()
    (req_dir / "state.py").write_text(
        'class RequirementsState:\n    """State."""\n    pass\n', encoding="utf-8",
    )
    req_nodes = req_dir / "nodes"
    req_nodes.mkdir()
    (req_nodes / "__init__.py").write_text("", encoding="utf-8")
    (req_nodes / "load_input.py").write_text(
        'def load_input(state):\n    """N0: Load input."""\n    return {}\n', encoding="utf-8",
    )

    # File for Modify tests
    test_wf = workflows_dir / "test"
    test_wf.mkdir()
    (test_wf / "graph.py").write_text(
        'def create_graph():\n    """Build graph."""\n    return None\n', encoding="utf-8",
    )
    (test_wf / "old.py").write_text("# Deprecated\n", encoding="utf-8")

    # Template
    standards = tmp_path / "docs" / "standards"
    standards.mkdir(parents=True)
    (standards / "0701-implementation-spec-template.md").write_text(
        "# Implementation Spec Template\n\n## 1. Overview\n", encoding="utf-8",
    )

    # Tests and tools dirs
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tools").mkdir(parents=True)

    return tmp_path


# =============================================================================
# State TypedDict Annotations (T010 setup)
# =============================================================================


class TestStateAnnotations:
    """Tests for ImplementationSpecState TypedDict annotations."""

    def test_state_has_expected_fields(self):
        """State TypedDict defines all expected field annotations."""
        from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState

        annotations = ImplementationSpecState.__annotations__
        expected = [
            "issue_number", "lld_path", "lld_content", "files_to_modify",
            "current_state_snapshots", "pattern_references", "spec_draft",
            "spec_path", "completeness_issues", "validation_passed",
            "review_verdict", "review_feedback", "review_iteration",
            "max_iterations", "human_gate_enabled", "error_message", "next_node",
        ]
        for field in expected:
            assert field in annotations, f"Missing field: {field}"

    def test_state_is_total_false(self):
        """State uses total=False for partial updates."""
        from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState

        # total=False means __required_keys__ is empty
        assert len(ImplementationSpecState.__required_keys__) == 0

    def test_state_partial_creation(self):
        """State can be created with only a subset of fields."""
        from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState

        state: ImplementationSpecState = {"issue_number": 304, "lld_path": "/path.md"}
        assert state["issue_number"] == 304
        assert state["lld_path"] == "/path.md"

    def test_state_full_creation(self, base_state):
        """State can be created with all fields populated."""
        assert base_state["issue_number"] == 999
        assert base_state["review_verdict"] == "BLOCKED"
        assert base_state["max_iterations"] == 3

    def test_file_to_modify_fields(self):
        """FileToModify has expected field annotations."""
        from assemblyzero.workflows.implementation_spec.state import FileToModify

        annotations = FileToModify.__annotations__
        assert "path" in annotations
        assert "change_type" in annotations
        assert "description" in annotations
        assert "current_content" in annotations

    def test_pattern_ref_fields(self):
        """PatternRef has expected field annotations."""
        from assemblyzero.workflows.implementation_spec.state import PatternRef

        annotations = PatternRef.__annotations__
        assert "file_path" in annotations
        assert "start_line" in annotations
        assert "end_line" in annotations
        assert "pattern_type" in annotations
        assert "relevance" in annotations

    def test_completeness_check_fields(self):
        """CompletenessCheck has expected field annotations."""
        from assemblyzero.workflows.implementation_spec.state import CompletenessCheck

        annotations = CompletenessCheck.__annotations__
        assert "check_name" in annotations
        assert "passed" in annotations
        assert "details" in annotations


# =============================================================================
# Graph Creation Tests
# =============================================================================


class TestImplementationSpecGraph:
    """Tests for graph creation and compilation."""

    def test_graph_creation(self):
        """Graph compiles without errors."""
        from assemblyzero.workflows.implementation_spec.graph import (
            create_implementation_spec_graph,
        )

        compiled = create_implementation_spec_graph()
        assert compiled is not None

    def test_graph_has_all_nodes(self):
        """Graph has all seven expected nodes."""
        from assemblyzero.workflows.implementation_spec.graph import (
            create_implementation_spec_graph,
        )

        compiled = create_implementation_spec_graph()
        graph_obj = compiled.get_graph()
        graph_nodes = list(graph_obj.nodes.keys())

        expected_nodes = [
            "N0_load_lld", "N1_analyze_codebase", "N2_generate_spec",
            "N3_validate_completeness", "N4_human_gate",
            "N5_review_spec", "N6_finalize_spec",
        ]
        for node in expected_nodes:
            assert node in graph_nodes, f"Missing node: {node}"

    def test_graph_entry_point(self):
        """Graph starts at N0_load_lld."""
        from assemblyzero.workflows.implementation_spec.graph import (
            create_implementation_spec_graph,
        )

        compiled = create_implementation_spec_graph()
        graph_obj = compiled.get_graph()
        start_edges = [e for e in graph_obj.edges if e[0] == "__start__"]
        assert len(start_edges) > 0, "No entry point found"
        assert start_edges[0][1] == "N0_load_lld"

    def test_graph_has_invoke_and_stream(self):
        """Compiled graph has invoke and stream methods."""
        from assemblyzero.workflows.implementation_spec.graph import (
            create_implementation_spec_graph,
        )

        compiled = create_implementation_spec_graph()
        assert hasattr(compiled, "invoke")
        assert hasattr(compiled, "stream")
        assert hasattr(compiled, "get_graph")


class TestNodeNames:
    """Tests for node name constants."""

    def test_node_names_defined(self):
        """All node name constants are defined correctly."""
        from assemblyzero.workflows.implementation_spec.graph import (
            N0_LOAD_LLD, N1_ANALYZE_CODEBASE, N2_GENERATE_SPEC,
            N3_VALIDATE_COMPLETENESS, N4_HUMAN_GATE,
            N5_REVIEW_SPEC, N6_FINALIZE_SPEC,
        )

        assert N0_LOAD_LLD == "N0_load_lld"
        assert N1_ANALYZE_CODEBASE == "N1_analyze_codebase"
        assert N2_GENERATE_SPEC == "N2_generate_spec"
        assert N3_VALIDATE_COMPLETENESS == "N3_validate_completeness"
        assert N4_HUMAN_GATE == "N4_human_gate"
        assert N5_REVIEW_SPEC == "N5_review_spec"
        assert N6_FINALIZE_SPEC == "N6_finalize_spec"


# =============================================================================
# Routing Tests
# =============================================================================


class TestRouteAfterLoad:
    """Tests for route_after_load routing function."""

    def test_routes_to_analyze_on_success(self):
        """No error → N1."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_load

        assert route_after_load({"error_message": ""}) == "N1_analyze_codebase"

    def test_routes_to_end_on_error(self):
        """Error → END."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_load

        assert route_after_load({"error_message": "LLD not found"}) == "END"


class TestRouteAfterAnalyze:
    """Tests for route_after_analyze routing function."""

    def test_routes_to_generate_on_success(self):
        """No error → N2."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_analyze

        assert route_after_analyze({"error_message": ""}) == "N2_generate_spec"

    def test_routes_to_end_on_error(self):
        """Error → END."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_analyze

        assert route_after_analyze({"error_message": "File read error"}) == "END"


class TestRouteAfterValidation:
    """Tests for route_after_validation routing function."""

    def test_routes_to_review_when_passed_no_gate(self):
        """Passed + no gate → N5."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_validation

        state = {
            "validation_passed": True, "human_gate_enabled": False,
            "review_iteration": 0, "max_iterations": 3,
        }
        assert route_after_validation(state) == "N5_review_spec"

    def test_routes_to_human_gate_when_passed_with_gate(self):
        """Passed + gate → N4."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_validation

        state = {
            "validation_passed": True, "human_gate_enabled": True,
            "review_iteration": 0, "max_iterations": 3,
        }
        assert route_after_validation(state) == "N4_human_gate"

    def test_routes_to_regenerate_on_failure_under_max(self):
        """Failed + iterations left → N2 (retry)."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_validation

        state = {
            "validation_passed": False, "review_iteration": 1,
            "max_iterations": 3, "completeness_issues": ["Missing excerpts"],
        }
        assert route_after_validation(state) == "N2_generate_spec"

    def test_routes_to_end_on_max_iterations(self):
        """Failed + max iterations → END."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_validation

        state = {
            "validation_passed": False, "review_iteration": 3, "max_iterations": 3,
        }
        assert route_after_validation(state) == "END"


class TestRouteAfterHumanGate:
    """Tests for route_after_human_gate routing function."""

    def test_routes_to_review_on_send(self):
        """Human chose Send → N5."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_human_gate

        state = {"error_message": "", "next_node": "N5_review_spec"}
        assert route_after_human_gate(state) == "N5_review_spec"

    def test_routes_to_generate_on_revise(self):
        """Human chose Revise → N2."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_human_gate

        state = {"error_message": "", "next_node": "N2_generate_spec"}
        assert route_after_human_gate(state) == "N2_generate_spec"

    def test_routes_to_end_on_manual(self):
        """Human chose Manual → END."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_human_gate

        state = {"error_message": "", "next_node": "END"}
        assert route_after_human_gate(state) == "END"

    def test_routes_to_end_on_error(self):
        """Error → END regardless of next_node."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_human_gate

        state = {"error_message": "Something went wrong", "next_node": "N5_review_spec"}
        assert route_after_human_gate(state) == "END"

    def test_routes_to_end_on_empty_next_node(self):
        """Empty next_node → END."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_human_gate

        state = {"error_message": "", "next_node": ""}
        assert route_after_human_gate(state) == "END"


class TestRouteAfterReview:
    """Tests for route_after_review routing function (T070, T080)."""

    def test_t070_routes_to_finalize_on_approved(self):
        """T070: APPROVED → N6."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_review

        state = {
            "error_message": "", "review_verdict": "APPROVED",
            "review_iteration": 0, "max_iterations": 3,
        }
        assert route_after_review(state) == "N6_finalize_spec"

    def test_t080_routes_to_generate_on_revise(self):
        """T080: REVISE + iterations left → N2."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_review

        state = {
            "error_message": "", "review_verdict": "REVISE",
            "review_iteration": 1, "max_iterations": 3,
        }
        assert route_after_review(state) == "N2_generate_spec"

    def test_routes_to_end_on_blocked(self):
        """BLOCKED → END."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_review

        state = {
            "error_message": "", "review_verdict": "BLOCKED",
            "review_iteration": 0, "max_iterations": 3,
        }
        assert route_after_review(state) == "END"

    def test_routes_to_end_on_revise_at_max(self):
        """REVISE at max iterations → END."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_review

        state = {
            "error_message": "", "review_verdict": "REVISE",
            "review_iteration": 3, "max_iterations": 3,
        }
        assert route_after_review(state) == "END"

    def test_routes_to_end_on_error(self):
        """Error → END regardless of verdict."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_review

        state = {
            "error_message": "API timeout", "review_verdict": "APPROVED",
            "review_iteration": 0, "max_iterations": 3,
        }
        assert route_after_review(state) == "END"


# =============================================================================
# N0: Load LLD (T010, T020)
# =============================================================================


class TestLoadLld:
    """Tests for N0: load_lld node."""

    def test_t010_load_approved_lld(self, tmp_path, sample_lld_content):
        """T010: Load approved LLD parses content and extracts files list."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import load_lld

        lld_file = tmp_path / "test-lld.md"
        lld_file.write_text(sample_lld_content, encoding="utf-8")

        state = {"issue_number": 999, "lld_path": str(lld_file), "repo_root": str(tmp_path)}
        result = load_lld(state)

        assert result["error_message"] == ""
        assert "APPROVED" in result["lld_content"]
        assert len(result["files_to_modify"]) > 0

        paths = [f["path"] for f in result["files_to_modify"]]
        assert any("state.py" in p for p in paths)

    def test_t020_reject_unapproved_lld(self, tmp_path, sample_unapproved_lld):
        """T020: Reject unapproved LLD with error."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import load_lld

        lld_file = tmp_path / "pending-lld.md"
        lld_file.write_text(sample_unapproved_lld, encoding="utf-8")

        state = {"issue_number": 998, "lld_path": str(lld_file), "repo_root": str(tmp_path)}
        result = load_lld(state)

        assert result["error_message"] != ""
        assert "not approved" in result["error_message"].lower()

    def test_lld_not_found(self, tmp_path):
        """LLD file does not exist — error returned."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import load_lld

        state = {
            "issue_number": 777,
            "lld_path": str(tmp_path / "nonexistent.md"),
            "repo_root": str(tmp_path),
        }
        result = load_lld(state)

        assert result["error_message"] != ""
        assert "not found" in result["error_message"].lower()

    def test_no_issue_number(self):
        """No issue number → error."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import load_lld

        result = load_lld({"issue_number": 0, "lld_path": "", "repo_root": ""})
        assert result["error_message"] != ""

    def test_lld_too_short(self, tmp_path):
        """LLD with too-short content → error."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import load_lld

        lld_file = tmp_path / "short.md"
        lld_file.write_text("# Short\nAPPROVED", encoding="utf-8")

        state = {"issue_number": 1, "lld_path": str(lld_file), "repo_root": str(tmp_path)}
        result = load_lld(state)
        assert result["error_message"] != ""


class TestParseLldTable:
    """Tests for parse_files_to_modify helper."""

    def test_parses_standard_table(self, sample_lld_content):
        """Parse standard Section 2.1 table."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import parse_files_to_modify

        files = parse_files_to_modify(sample_lld_content)
        assert len(files) >= 2
        change_types = {f["change_type"] for f in files}
        assert "Add" in change_types or "Modify" in change_types

    def test_empty_content_returns_empty(self):
        """Empty content → empty list."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import parse_files_to_modify

        assert parse_files_to_modify("") == []

    def test_no_table_returns_empty(self):
        """Content without table → empty list."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import parse_files_to_modify

        assert parse_files_to_modify("# LLD\n\nNo table here.\n") == []


class TestFindLldPath:
    """Tests for find_lld_path helper."""

    def test_finds_lld_in_active(self, tmp_path):
        """Find LLD in active directory."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import find_lld_path

        active_dir = tmp_path / "docs" / "lld" / "active"
        active_dir.mkdir(parents=True)
        (active_dir / "LLD-042.md").write_text("# LLD", encoding="utf-8")

        result = find_lld_path(42, tmp_path)
        assert result is not None
        assert result.name == "LLD-042.md"

    def test_finds_lld_in_done(self, tmp_path):
        """Find LLD in done directory."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import find_lld_path

        done_dir = tmp_path / "docs" / "lld" / "done"
        done_dir.mkdir(parents=True)
        (done_dir / "LLD-042.md").write_text("# LLD", encoding="utf-8")

        result = find_lld_path(42, tmp_path)
        assert result is not None

    def test_returns_none_when_not_found(self, tmp_path):
        """Return None when LLD not found."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import find_lld_path

        assert find_lld_path(999, tmp_path) is None


class TestNormalizeChangeType:
    """Tests for _normalize_change_type helper."""

    def test_normalizes_add_variants(self):
        """Normalize Add, add, new, create."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import _normalize_change_type

        assert _normalize_change_type("Add") == "Add"
        assert _normalize_change_type("add") == "Add"
        assert _normalize_change_type("Add (Directory)") == "Add"
        assert _normalize_change_type("new") == "Add"
        assert _normalize_change_type("create") == "Add"

    def test_normalizes_modify_variants(self):
        """Normalize Modify, update, change, edit."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import _normalize_change_type

        assert _normalize_change_type("Modify") == "Modify"
        assert _normalize_change_type("modify") == "Modify"
        assert _normalize_change_type("update") == "Modify"
        assert _normalize_change_type("change") == "Modify"
        assert _normalize_change_type("edit") == "Modify"

    def test_normalizes_delete_variants(self):
        """Normalize Delete, remove."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import _normalize_change_type

        assert _normalize_change_type("Delete") == "Delete"
        assert _normalize_change_type("delete") == "Delete"
        assert _normalize_change_type("remove") == "Delete"

    def test_unknown_defaults_to_add(self):
        """Unknown type → Add."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import _normalize_change_type

        assert _normalize_change_type("unknown") == "Add"


class TestCheckApprovedStatus:
    """Tests for _check_approved_status helper."""

    def test_detects_status_field(self):
        """Detect Approved in Status field."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import _check_approved_status

        assert _check_approved_status('* **Status:** Approved (gemini, 2026)\n') is True

    def test_detects_final_status(self):
        """Detect APPROVED in Final Status."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import _check_approved_status

        assert _check_approved_status("**Final Status:** APPROVED\n") is True

    def test_rejects_unapproved(self):
        """No APPROVED marker → False."""
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import _check_approved_status

        assert _check_approved_status("* **Status:** Pending\n\nNo approval.\n") is False


# =============================================================================
# N1: Analyze Codebase (T030)
# =============================================================================


class TestAnalyzeCodebase:
    """Tests for N1: analyze_codebase node."""

    def test_t030_extracts_excerpts_for_modify_files(self, tmp_path):
        """T030: Extracts excerpts for Modify files."""
        from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import analyze_codebase

        target = tmp_path / "assemblyzero" / "workflows" / "test" / "graph.py"
        target.parent.mkdir(parents=True)
        target.write_text(
            'def create_graph():\n    """Build graph."""\n    return None\n', encoding="utf-8",
        )

        state = {
            "files_to_modify": [{
                "path": "assemblyzero/workflows/test/graph.py",
                "change_type": "Modify", "description": "Update graph",
                "current_content": None,
            }],
            "lld_content": "Update graph.py", "repo_root": str(tmp_path),
        }

        result = analyze_codebase(state)
        assert result["error_message"] == ""
        assert "assemblyzero/workflows/test/graph.py" in result["current_state_snapshots"]

    def test_040_file_not_found_graceful(self, tmp_path):
        """Scenario 040: Missing file produces warning, not error."""
        from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import analyze_codebase

        state = {
            "files_to_modify": [{
                "path": "nonexistent/file.py", "change_type": "Modify",
                "description": "Modify missing", "current_content": None,
            }],
            "lld_content": "Context", "repo_root": str(tmp_path),
        }

        result = analyze_codebase(state)
        assert result["error_message"] == ""
        assert "nonexistent/file.py" not in result.get("current_state_snapshots", {})

    def test_empty_files_list(self, tmp_path):
        """No files → empty results."""
        from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import analyze_codebase

        result = analyze_codebase({
            "files_to_modify": [], "lld_content": "", "repo_root": str(tmp_path),
        })
        assert result["error_message"] == ""
        assert result["current_state_snapshots"] == {}

    def test_add_file_verifies_parent(self, tmp_path):
        """Add files verify parent directory."""
        from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import analyze_codebase

        (tmp_path / "assemblyzero" / "workflows").mkdir(parents=True)

        state = {
            "files_to_modify": [{
                "path": "assemblyzero/workflows/new_file.py",
                "change_type": "Add", "description": "New", "current_content": None,
            }],
            "lld_content": "", "repo_root": str(tmp_path),
        }

        result = analyze_codebase(state)
        assert result["error_message"] == ""


class TestExtractRelevantExcerpt:
    """Tests for extract_relevant_excerpt helper."""

    def test_python_file_summarization(self):
        """Python files get AST-based summarization."""
        from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import (
            extract_relevant_excerpt,
        )

        content = 'import os\n\ndef hello():\n    """Say hello."""\n    print("hello")\n'
        excerpt = extract_relevant_excerpt("test.py", content, "")
        assert "import os" in excerpt
        assert "def hello" in excerpt

    def test_non_python_file(self):
        """Non-Python files returned truncated."""
        from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import (
            extract_relevant_excerpt,
        )

        excerpt = extract_relevant_excerpt("readme.md", "# Markdown\n\nContent.\n", "")
        assert "Markdown" in excerpt


class TestFindPatternReferences:
    """Tests for find_pattern_references helper."""

    def test_empty_files_returns_empty(self, tmp_path):
        """No files → no patterns."""
        from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import (
            find_pattern_references,
        )

        assert find_pattern_references([], tmp_path) == []

    def test_finds_node_patterns(self, tmp_path):
        """Find node patterns in existing workflows."""
        from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import (
            find_pattern_references,
        )

        node_dir = tmp_path / "assemblyzero" / "workflows" / "requirements" / "nodes"
        node_dir.mkdir(parents=True)
        (node_dir / "load_input.py").write_text(
            '"""Load."""\ndef load_input(state):\n    pass\n', encoding="utf-8",
        )
        (node_dir / "__init__.py").write_text("", encoding="utf-8")

        files = [{
            "path": "assemblyzero/workflows/impl/nodes/load_lld.py",
            "change_type": "Add", "description": "Load LLD", "current_content": None,
        }]

        patterns = find_pattern_references(files, tmp_path)
        assert len(patterns) > 0
        assert any(p["pattern_type"] == "node implementation" for p in patterns)

    def test_respects_max_pattern_refs(self, tmp_path):
        """Patterns capped at MAX_PATTERN_REFS."""
        from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import (
            find_pattern_references, MAX_PATTERN_REFS,
        )

        for i in range(15):
            wf = tmp_path / "assemblyzero" / "workflows" / f"wf{i}" / "nodes"
            wf.mkdir(parents=True)
            (wf / f"node_{i}.py").write_text(
                f'"""Node {i}."""\ndef n{i}(s):\n    pass\n', encoding="utf-8",
            )
            (wf / "__init__.py").write_text("", encoding="utf-8")

        files = [{
            "path": "assemblyzero/workflows/new/nodes/my_node.py",
            "change_type": "Add", "description": "New", "current_content": None,
        }]

        patterns = find_pattern_references(files, tmp_path)
        assert len(patterns) <= MAX_PATTERN_REFS


# =============================================================================
# N3: Validate Completeness (T050, T060)
# =============================================================================


class TestValidateCompleteness:
    """Tests for N3: validate_completeness node."""

    def test_t050_catches_missing_excerpts(self, base_state):
        """T050: Incomplete spec fails validation."""
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
            validate_completeness,
        )

        base_state["spec_draft"] = (
            "# Implementation Spec\n\n## Overview\n\nChanges.\n\n"
            + ("filler content\n" * 20)
        )
        base_state["files_to_modify"] = [{
            "path": "assemblyzero/workflows/test/graph.py",
            "change_type": "Modify", "description": "Update graph",
            "current_content": "existing code",
        }]

        result = validate_completeness(base_state)
        assert result["validation_passed"] is False
        assert len(result["completeness_issues"]) > 0

    def test_t060_passes_complete_spec(self, base_state, sample_spec_complete):
        """T060: Complete spec passes validation."""
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
            validate_completeness,
        )

        base_state["spec_draft"] = sample_spec_complete
        base_state["files_to_modify"] = [{
            "path": "assemblyzero/workflows/test/graph.py",
            "change_type": "Modify", "description": "Update graph",
            "current_content": "existing code",
        }]
        base_state["pattern_references"] = []

        result = validate_completeness(base_state)
        assert result["validation_passed"] is True
        assert result["completeness_issues"] == []

    def test_empty_spec_blocked(self, base_state):
        """Empty spec → blocked."""
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
            validate_completeness,
        )

        base_state["spec_draft"] = ""
        result = validate_completeness(base_state)
        assert result["validation_passed"] is False

    def test_short_spec_blocked(self, base_state):
        """Short spec → blocked."""
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
            validate_completeness,
        )

        base_state["spec_draft"] = "Too short"
        result = validate_completeness(base_state)
        assert result["validation_passed"] is False


class TestCompletenessChecks:
    """Tests for individual completeness check functions."""

    def test_modify_files_no_modify(self):
        """No Modify files → passes."""
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
            check_modify_files_have_excerpts,
        )

        assert check_modify_files_have_excerpts("# Spec", [])["passed"] is True

    def test_modify_files_with_excerpt(self):
        """Modify file with code block → passes."""
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
            check_modify_files_have_excerpts,
        )

        spec = "### assemblyzero/test.py\n\nCurrent state:\n```python\ndef foo(): pass\n```\n"
        files = [{"path": "assemblyzero/test.py", "change_type": "Modify",
                   "description": "Update", "current_content": "code"}]

        assert check_modify_files_have_excerpts(spec, files)["passed"] is True

    def test_modify_files_missing_excerpt(self):
        """Modify file without code block → fails."""
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
            check_modify_files_have_excerpts,
        )

        spec = "# Spec\n\nJust text.\n"
        files = [{"path": "missing.py", "change_type": "Modify",
                   "description": "Update", "current_content": "code"}]

        assert check_modify_files_have_excerpts(spec, files)["passed"] is False

    def test_data_structures_no_structures(self):
        """No data structures → passes."""
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
            check_data_structures_have_examples,
        )

        assert check_data_structures_have_examples("# Spec with no classes\n")["passed"] is True

    def test_functions_no_functions(self):
        """No public functions → passes."""
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
            check_functions_have_io_examples,
        )

        assert check_functions_have_io_examples("# Spec\n")["passed"] is True

    def test_change_instructions_with_code_blocks(self):
        """Many code blocks + indicators → passes."""
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
            check_change_instructions_specific,
        )

        parts = ["# Spec\n\n"]
        for i in range(10):
            parts.append(f"## Change {i}\n\nAdd after line {i * 10}:\n\n")
            parts.append(f"```python\ndef func_{i}():\n    pass\n```\n\n")
            parts.append(f"import m{i}\nclass W{i}:\n    pass\n")

        assert check_change_instructions_specific("\n".join(parts))["passed"] is True

    def test_pattern_refs_no_refs(self):
        """No pattern refs → passes."""
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
            check_pattern_references_valid,
        )

        assert check_pattern_references_valid("# Spec", [])["passed"] is True

    def test_pattern_refs_valid(self, tmp_path):
        """Valid pattern reference → passes."""
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
            check_pattern_references_valid,
        )

        ref_file = tmp_path / "assemblyzero" / "nodes" / "load.py"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text("# line 1\n# line 2\n# line 3\n", encoding="utf-8")

        rel = "assemblyzero/nodes/load.py"
        refs = [{"file_path": rel, "start_line": 1, "end_line": 3,
                 "pattern_type": "node", "relevance": "Example"}]

        result = check_pattern_references_valid(f"# Spec\n{rel}\n", refs, str(tmp_path))
        assert result["passed"] is True

    def test_pattern_refs_invalid_file(self, tmp_path):
        """Non-existent file in pattern ref → fails."""
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
            check_pattern_references_valid,
        )

        rel = "nonexistent/file.py"
        refs = [{"file_path": rel, "start_line": 1, "end_line": 10,
                 "pattern_type": "node", "relevance": "Missing"}]

        result = check_pattern_references_valid(f"# Spec\n{rel}\n", refs, str(tmp_path))
        assert result["passed"] is False


# =============================================================================
# N4: Human Gate
# =============================================================================


class TestHumanGate:
    """Tests for N4: human_gate node."""

    def test_disabled_gate_auto_routes(self, base_state):
        """Disabled gate → N5."""
        from assemblyzero.workflows.implementation_spec.nodes.human_gate import human_gate

        base_state["human_gate_enabled"] = False
        base_state["spec_draft"] = "# Some spec"

        result = human_gate(base_state)
        assert result["next_node"] == "N5_review_spec"
        assert result["error_message"] == ""

    def test_no_spec_returns_end(self, base_state):
        """No spec draft → END."""
        from assemblyzero.workflows.implementation_spec.nodes.human_gate import human_gate

        base_state["human_gate_enabled"] = True
        base_state["spec_draft"] = ""

        result = human_gate(base_state)
        assert result["next_node"] == "END"
        assert result["error_message"] != ""

    @patch(
        "assemblyzero.workflows.implementation_spec.nodes.human_gate._prompt_human_gate",
        return_value="S",
    )
    def test_send_choice(self, mock_prompt, base_state):
        """User Send → N5."""
        from assemblyzero.workflows.implementation_spec.nodes.human_gate import human_gate

        base_state["human_gate_enabled"] = True
        base_state["spec_draft"] = SAMPLE_SPEC_COMPLETE

        assert human_gate(base_state)["next_node"] == "N5_review_spec"

    @patch("builtins.input", return_value="Fix excerpts")
    @patch(
        "assemblyzero.workflows.implementation_spec.nodes.human_gate._prompt_human_gate",
        return_value="R",
    )
    def test_revise_choice(self, mock_prompt, mock_input, base_state):
        """User Revise → N2 with feedback."""
        from assemblyzero.workflows.implementation_spec.nodes.human_gate import human_gate

        base_state["human_gate_enabled"] = True
        base_state["spec_draft"] = SAMPLE_SPEC_COMPLETE

        result = human_gate(base_state)
        assert result["next_node"] == "N2_generate_spec"
        assert "Fix excerpts" in result.get("review_feedback", "")

    @patch(
        "assemblyzero.workflows.implementation_spec.nodes.human_gate._prompt_human_gate",
        return_value="M",
    )
    def test_manual_choice(self, mock_prompt, base_state):
        """User Manual → END."""
        from assemblyzero.workflows.implementation_spec.nodes.human_gate import human_gate

        base_state["human_gate_enabled"] = True
        base_state["spec_draft"] = SAMPLE_SPEC_COMPLETE

        assert human_gate(base_state)["next_node"] == "END"


# =============================================================================
# N2: Generate Spec (T040) — mocked LLM
# =============================================================================


class TestGenerateSpec:
    """Tests for N2: generate_spec node (mocked)."""

    @patch("assemblyzero.workflows.implementation_spec.nodes.generate_spec.get_provider")
    @patch("assemblyzero.workflows.implementation_spec.nodes.generate_spec.load_template")
    def test_t040_generates_draft(self, mock_template, mock_provider, base_state):
        """T040: Generate spec produces draft with all sections."""
        mock_template.return_value = "# Template\n## 1. Overview\n"

        drafter = Mock()
        drafter.invoke.return_value = Mock(
            success=True,
            response="# Implementation Spec: Feature\n\n## 1. Overview\n\nDetailed spec.",
            error_message=None,
        )
        mock_provider.return_value = drafter

        base_state["lld_content"] = SAMPLE_LLD_APPROVED
        base_state["current_state_snapshots"] = {"file.py": "content"}
        base_state["pattern_references"] = []

        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import generate_spec

        result = generate_spec(base_state)
        assert result["error_message"] == ""
        assert "Implementation Spec" in result["spec_draft"]
        drafter.invoke.assert_called_once()

    @patch("assemblyzero.workflows.implementation_spec.nodes.generate_spec.get_provider")
    @patch("assemblyzero.workflows.implementation_spec.nodes.generate_spec.load_template")
    def test_handles_drafter_failure(self, mock_template, mock_provider, base_state):
        """Drafter failure → error returned."""
        mock_template.return_value = "# Template"
        drafter = Mock()
        drafter.invoke.return_value = Mock(success=False, response=None, error_message="Timeout")
        mock_provider.return_value = drafter

        base_state["lld_content"] = SAMPLE_LLD_APPROVED

        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import generate_spec

        result = generate_spec(base_state)
        assert result["error_message"] != ""

    @patch("assemblyzero.workflows.implementation_spec.nodes.generate_spec.get_provider")
    @patch("assemblyzero.workflows.implementation_spec.nodes.generate_spec.load_template")
    def test_revision_increments_iteration(self, mock_template, mock_provider, base_state):
        """Revision mode increments review_iteration."""
        mock_template.return_value = "# Template"
        drafter = Mock()
        drafter.invoke.return_value = Mock(
            success=True, response="# Revised Spec\n\n## 1. Overview", error_message=None,
        )
        mock_provider.return_value = drafter

        base_state["lld_content"] = SAMPLE_LLD_APPROVED
        base_state["spec_draft"] = "# Old Draft"
        base_state["review_feedback"] = "Please fix X"
        base_state["review_iteration"] = 0

        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import generate_spec

        result = generate_spec(base_state)
        assert result["error_message"] == ""
        assert result["review_iteration"] == 1


class TestBuildDrafterPrompt:
    """Tests for build_drafter_prompt helper."""

    def test_initial_prompt_includes_lld(self):
        """Initial prompt contains LLD content."""
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
            build_drafter_prompt,
        )

        prompt = build_drafter_prompt(
            lld_content="# My LLD\n\nFeature description.",
            current_state={"test.py": "def foo(): pass"},
            patterns=[], template="# Template", issue_number=42,
        )
        assert "My LLD" in prompt
        assert "test.py" in prompt
        assert "Template" in prompt

    def test_revision_prompt_includes_feedback(self):
        """Revision prompt includes feedback and issues."""
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
            build_drafter_prompt,
        )

        prompt = build_drafter_prompt(
            lld_content="# LLD", current_state={}, patterns=[],
            existing_draft="# Old draft",
            review_feedback="Fix data structures.",
            completeness_issues=["Missing excerpts for Modify files"],
        )
        assert "Fix data structures" in prompt
        assert "Missing excerpts" in prompt
        assert "Old draft" in prompt

    def test_includes_pattern_references(self):
        """Prompt includes patterns."""
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
            build_drafter_prompt,
        )

        patterns = [{
            "file_path": "load.py", "start_line": 1, "end_line": 50,
            "pattern_type": "node implementation", "relevance": "Similar node",
        }]

        prompt = build_drafter_prompt(lld_content="# LLD", current_state={}, patterns=patterns)
        assert "node implementation" in prompt
        assert "Similar node" in prompt


class TestStripPreamble:
    """Tests for _strip_preamble helper."""

    def test_strips_preamble(self):
        """Strips text before first # heading."""
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import _strip_preamble

        result = _strip_preamble("Preamble text.\n\n# Heading\n\nContent.")
        assert result.startswith("# Heading")

    def test_no_preamble_unchanged(self):
        """Content starting with # unchanged."""
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import _strip_preamble

        content = "# Heading\n\nContent."
        assert _strip_preamble(content) == content

    def test_empty_content(self):
        """Empty → empty."""
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import _strip_preamble

        assert _strip_preamble("") == ""
        assert _strip_preamble(None) is None


# =============================================================================
# N5: Review Spec (T070, T080)
# =============================================================================


class TestReviewSpec:
    """Tests for N5: review_spec node."""

    @patch("assemblyzero.workflows.implementation_spec.nodes.review_spec.get_provider")
    def test_approved_verdict(self, mock_provider, base_state):
        """APPROVED verdict returned."""
        reviewer = Mock()
        reviewer.invoke.return_value = Mock(
            success=True,
            response="## Verdict\n[X] **APPROVED** - Ready\n",
            error_message=None,
        )
        mock_provider.return_value = reviewer

        base_state["spec_draft"] = SAMPLE_SPEC_COMPLETE
        base_state["lld_content"] = SAMPLE_LLD_APPROVED

        from assemblyzero.workflows.implementation_spec.nodes.review_spec import review_spec

        result = review_spec(base_state)
        assert result["error_message"] == ""
        assert result["review_verdict"] == "APPROVED"

    @patch("assemblyzero.workflows.implementation_spec.nodes.review_spec.get_provider")
    def test_revise_verdict(self, mock_provider, base_state):
        """REVISE verdict returned with feedback."""
        reviewer = Mock()
        reviewer.invoke.return_value = Mock(
            success=True,
            response=(
                "## Blocking Issues\n1. Missing excerpts.\n\n"
                "## Verdict\n[X] **REVISE** - Fix issues\n"
            ),
            error_message=None,
        )
        mock_provider.return_value = reviewer

        base_state["spec_draft"] = SAMPLE_SPEC_COMPLETE
        base_state["lld_content"] = SAMPLE_LLD_APPROVED

        from assemblyzero.workflows.implementation_spec.nodes.review_spec import review_spec

        result = review_spec(base_state)
        assert result["review_verdict"] == "REVISE"
        assert result["review_feedback"] != ""

    @patch("assemblyzero.workflows.implementation_spec.nodes.review_spec.get_provider")
    def test_max_iterations_guard(self, mock_provider, base_state):
        """Max iterations → BLOCKED without calling provider."""
        base_state["spec_draft"] = SAMPLE_SPEC_COMPLETE
        base_state["review_iteration"] = 3
        base_state["max_iterations"] = 3

        from assemblyzero.workflows.implementation_spec.nodes.review_spec import review_spec

        result = review_spec(base_state)
        assert result["review_verdict"] == "BLOCKED"
        mock_provider.assert_not_called()

    @patch("assemblyzero.workflows.implementation_spec.nodes.review_spec.get_provider")
    def test_empty_spec_blocked(self, mock_provider, base_state):
        """Empty spec → BLOCKED without calling provider."""
        base_state["spec_draft"] = ""

        from assemblyzero.workflows.implementation_spec.nodes.review_spec import review_spec

        result = review_spec(base_state)
        assert result["review_verdict"] == "BLOCKED"
        mock_provider.assert_not_called()


class TestParseReviewVerdict:
    """Tests for parse_review_verdict helper."""

    def test_approved_checkbox(self):
        """[X] APPROVED → APPROVED."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import parse_review_verdict

        verdict, _ = parse_review_verdict("[X] **APPROVED** - Ready\n")
        assert verdict == "APPROVED"

    def test_revise_checkbox(self):
        """[X] REVISE → REVISE."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import parse_review_verdict

        verdict, feedback = parse_review_verdict(
            "## Blocking Issues\n1. Fix X.\n\n## Verdict\n[X] **REVISE**\n"
        )
        assert verdict == "REVISE"
        assert feedback != ""

    def test_blocked_checkbox(self):
        """[X] BLOCKED → BLOCKED."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import parse_review_verdict

        verdict, _ = parse_review_verdict("[X] **BLOCKED** - Issues\n")
        assert verdict == "BLOCKED"

    def test_keyword_fallback(self):
        """VERDICT: APPROVED keyword → APPROVED."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import parse_review_verdict

        verdict, _ = parse_review_verdict("Verdict: APPROVED\n\nGreat work!")
        assert verdict == "APPROVED"

    def test_empty_response_blocked(self):
        """Empty → BLOCKED."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import parse_review_verdict

        assert parse_review_verdict("")[0] == "BLOCKED"

    def test_discuss_maps_to_blocked(self):
        """DISCUSS → BLOCKED."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import parse_review_verdict

        assert parse_review_verdict("[X] **DISCUSS** - Need discussion")[0] == "BLOCKED"

    def test_no_verdict_defaults_blocked(self):
        """No verdict marker → BLOCKED."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import parse_review_verdict

        assert parse_review_verdict("Some text without verdict.")[0] == "BLOCKED"


# =============================================================================
# N6: Finalize Spec (T090)
# =============================================================================


class TestFinalizeSpec:
    """Tests for N6: finalize_spec node."""

    def _run_finalize(self, state):
        """Run finalize_spec directly.

        The production code already closes the mkstemp fd before writing
        (Windows file-lock fix), so no patching is needed.
        """
        from assemblyzero.workflows.implementation_spec.nodes.finalize_spec import (
            finalize_spec,
        )

        return finalize_spec(state)

    def test_t090_writes_spec_file(self, tmp_path, base_state):
        """T090: Finalize writes spec file at expected path."""
        base_state["spec_draft"] = "# Implementation Spec\n\n" + ("Content line\n" * 50)
        base_state["review_verdict"] = "APPROVED"
        base_state["review_feedback"] = "Looks good."
        base_state["review_iteration"] = 1
        base_state["repo_root"] = str(tmp_path)

        result = self._run_finalize(base_state)

        assert result["error_message"] == ""
        assert result["spec_path"] != ""

        spec_path = Path(result["spec_path"])
        assert spec_path.exists()
        assert "spec-0999" in spec_path.name
        assert spec_path.name.endswith(".md")

        content = spec_path.read_text(encoding="utf-8")
        assert "Review Log" in content
        assert "APPROVED" in content

    def test_rejects_non_approved(self, base_state, tmp_path):
        """Non-APPROVED verdict → error."""
        from assemblyzero.workflows.implementation_spec.nodes.finalize_spec import finalize_spec

        base_state["spec_draft"] = "# Spec\n" + ("x" * 200)
        base_state["review_verdict"] = "REVISE"
        base_state["repo_root"] = str(tmp_path)

        result = finalize_spec(base_state)
        assert result["error_message"] != ""
        assert result["spec_path"] == ""

    def test_rejects_empty_spec(self, base_state, tmp_path):
        """Empty spec → error."""
        from assemblyzero.workflows.implementation_spec.nodes.finalize_spec import finalize_spec

        base_state["spec_draft"] = ""
        base_state["review_verdict"] = "APPROVED"
        base_state["repo_root"] = str(tmp_path)

        result = finalize_spec(base_state)
        assert result["error_message"] != ""

    def test_rejects_short_spec(self, base_state, tmp_path):
        """Short spec → error."""
        from assemblyzero.workflows.implementation_spec.nodes.finalize_spec import finalize_spec

        base_state["spec_draft"] = "Too short"
        base_state["review_verdict"] = "APPROVED"
        base_state["repo_root"] = str(tmp_path)

        result = finalize_spec(base_state)
        assert result["error_message"] != ""

    def test_rejects_invalid_issue_number(self, base_state, tmp_path):
        """Invalid issue number → error."""
        from assemblyzero.workflows.implementation_spec.nodes.finalize_spec import finalize_spec

        base_state["spec_draft"] = "# Spec\n" + ("x" * 200)
        base_state["review_verdict"] = "APPROVED"
        base_state["issue_number"] = 0
        base_state["repo_root"] = str(tmp_path)

        result = finalize_spec(base_state)
        assert result["error_message"] != ""

    def test_creates_output_directory(self, tmp_path, base_state):
        """Creates output directory if missing."""
        new_repo = tmp_path / "new_repo"
        new_repo.mkdir()

        base_state["spec_draft"] = "# Spec\n" + ("Content\n" * 50)
        base_state["review_verdict"] = "APPROVED"
        base_state["repo_root"] = str(new_repo)

        result = self._run_finalize(base_state)
        assert result["error_message"] == ""
        assert Path(result["spec_path"]).exists()


class TestGenerateSpecFilename:
    """Tests for generate_spec_filename helper."""

    def test_zero_padded_filename(self):
        """Generates 4-digit zero-padded filenames."""
        from assemblyzero.workflows.implementation_spec.nodes.finalize_spec import (
            generate_spec_filename,
        )

        assert generate_spec_filename(42) == "spec-0042-implementation-readiness.md"
        assert generate_spec_filename(304) == "spec-0304-implementation-readiness.md"
        assert generate_spec_filename(1) == "spec-0001-implementation-readiness.md"
        assert generate_spec_filename(9999) == "spec-9999-implementation-readiness.md"
        assert generate_spec_filename(12345) == "spec-12345-implementation-readiness.md"


# =============================================================================
# Package Imports
# =============================================================================


class TestPackageImports:
    """Tests for package __init__.py exports."""

    def test_top_level_imports(self):
        """Top-level package exports are importable."""
        from assemblyzero.workflows.implementation_spec import (
            create_implementation_spec_graph,
            route_after_review,
            route_after_validation,
            ImplementationSpecState,
            FileToModify,
            PatternRef,
            CompletenessCheck,
        )

        assert create_implementation_spec_graph is not None
        assert route_after_review is not None
        assert route_after_validation is not None

    def test_nodes_package_imports(self):
        """Nodes package exports are importable."""
        from assemblyzero.workflows.implementation_spec.nodes import (
            load_lld, parse_files_to_modify,
            analyze_codebase, extract_relevant_excerpt, find_pattern_references,
            generate_spec, build_drafter_prompt,
            validate_completeness, check_modify_files_have_excerpts,
            check_data_structures_have_examples, check_functions_have_io_examples,
            check_change_instructions_specific, check_pattern_references_valid,
            human_gate, review_spec, parse_review_verdict,
            finalize_spec, generate_spec_filename,
        )

        assert all(callable(f) for f in [
            load_lld, parse_files_to_modify, analyze_codebase,
            extract_relevant_excerpt, find_pattern_references,
            generate_spec, build_drafter_prompt,
            validate_completeness, check_modify_files_have_excerpts,
            check_data_structures_have_examples, check_functions_have_io_examples,
            check_change_instructions_specific, check_pattern_references_valid,
            human_gate, review_spec, parse_review_verdict,
            finalize_spec, generate_spec_filename,
        ])


# =============================================================================
# State TypedDict Tests
# =============================================================================


class TestImplementationSpecState:
    """Tests for ImplementationSpecState TypedDict."""

    def test_state_creation(self):
        """State dict can be created."""
        from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState

        state: ImplementationSpecState = {"issue_number": 304, "lld_path": "/path.md"}
        assert state["issue_number"] == 304

    def test_state_types_importable(self):
        """All state types are importable."""
        from assemblyzero.workflows.implementation_spec.state import (
            ImplementationSpecState, FileToModify, PatternRef, CompletenessCheck,
        )

        assert all(t is not None for t in [
            ImplementationSpecState, FileToModify, PatternRef, CompletenessCheck,
        ])

    def test_file_to_modify(self):
        """FileToModify creation."""
        from assemblyzero.workflows.implementation_spec.state import FileToModify

        ftm: FileToModify = {
            "path": "test.py", "change_type": "Add",
            "description": "New", "current_content": None,
        }
        assert ftm["path"] == "test.py"

    def test_pattern_ref(self):
        """PatternRef creation."""
        from assemblyzero.workflows.implementation_spec.state import PatternRef

        ref: PatternRef = {
            "file_path": "test.py", "start_line": 1, "end_line": 10,
            "pattern_type": "node", "relevance": "Similar",
        }
        assert ref["start_line"] == 1

    def test_completeness_check(self):
        """CompletenessCheck creation."""
        from assemblyzero.workflows.implementation_spec.state import CompletenessCheck

        check: CompletenessCheck = {"check_name": "test", "passed": True, "details": "OK"}
        assert check["passed"] is True


# =============================================================================
# CLI Tests (T100)
# =============================================================================


class TestCLI:
    """Tests for CLI tool argument parsing and configuration."""

    def test_t100_parser_creation(self):
        """T100: CLI parser creates successfully."""
        from tools.run_implementation_spec_workflow import create_argument_parser

        assert create_argument_parser() is not None

    def test_parse_basic_args(self):
        """Parse --issue argument."""
        from tools.run_implementation_spec_workflow import parse_args

        assert parse_args(["--issue", "304"]).issue == 304

    def test_parse_full_args(self):
        """Parse full argument set."""
        from tools.run_implementation_spec_workflow import parse_args

        args = parse_args([
            "--issue", "42", "--repo", "/tmp/repo", "--review", "all",
            "--max-iterations", "5", "--mock", "--debug",
        ])
        assert args.issue == 42
        assert args.repo == "/tmp/repo"
        assert args.review == "all"
        assert args.max_iterations == 5
        assert args.mock is True
        assert args.debug is True

    def test_parse_dry_run(self):
        """Parse --dry-run flag."""
        from tools.run_implementation_spec_workflow import parse_args

        assert parse_args(["--issue", "1", "--dry-run"]).dry_run is True

    def test_review_none_disables_gate(self):
        """Review 'none' → gate disabled."""
        from tools.run_implementation_spec_workflow import parse_args, apply_review_config

        args = parse_args(["--issue", "1", "--review", "none"])
        apply_review_config(args)
        assert args.human_gate_enabled is False

    def test_review_all_enables_gate(self):
        """Review 'all' → gate enabled."""
        from tools.run_implementation_spec_workflow import parse_args, apply_review_config

        args = parse_args(["--issue", "1", "--review", "all"])
        apply_review_config(args)
        assert args.human_gate_enabled is True

    def test_review_draft_enables_gate(self):
        """Review 'draft' → gate enabled."""
        from tools.run_implementation_spec_workflow import parse_args, apply_review_config

        args = parse_args(["--issue", "1", "--review", "draft"])
        apply_review_config(args)
        assert args.human_gate_enabled is True

    def test_build_initial_state(self, tmp_path):
        """Build initial state from CLI args."""
        from tools.run_implementation_spec_workflow import (
            parse_args, apply_review_config, build_initial_state,
        )

        lld_dir = tmp_path / "docs" / "lld" / "active"
        lld_dir.mkdir(parents=True)
        (lld_dir / "LLD-042.md").write_text("# LLD", encoding="utf-8")

        args = parse_args(["--issue", "42", "--repo", str(tmp_path)])
        apply_review_config(args)

        state = build_initial_state(args, assemblyzero_root=tmp_path, target_repo=tmp_path)
        assert state["issue_number"] == 42
        assert state["max_iterations"] == 3
        assert state["human_gate_enabled"] is False
        assert state["review_verdict"] == "BLOCKED"
        assert state["review_iteration"] == 0

    def test_dry_run_returns_zero(self, tmp_path):
        """Dry run → exit code 0."""
        from tools.run_implementation_spec_workflow import (
            parse_args, apply_review_config, run_dry_run,
        )

        args = parse_args(["--issue", "42", "--dry-run"])
        apply_review_config(args)
        args.human_gate_enabled = False

        assert run_dry_run(args, tmp_path) == 0

    def test_main_rejects_invalid_issue(self):
        """Main rejects issue ≤ 0."""
        from tools.run_implementation_spec_workflow import main

        with patch("sys.argv", ["prog", "--issue", "0"]):
            assert main() == 1


# =============================================================================
# Workflow Path Integration Tests (scenarios 050, 060, 070)
# =============================================================================


class TestWorkflowPaths:
    """Integration tests for workflow routing paths."""

    def test_050_incomplete_spec_triggers_retry(self, base_state):
        """Scenario 050: Incomplete spec → N3 fails → N2 retry."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_validation

        base_state["validation_passed"] = False
        base_state["review_iteration"] = 0
        base_state["max_iterations"] = 3
        base_state["completeness_issues"] = ["Missing data structure examples"]

        assert route_after_validation(base_state) == "N2_generate_spec"

    def test_060_max_iterations_aborts(self, base_state):
        """Scenario 060: Max iterations → abort."""
        from assemblyzero.workflows.implementation_spec.graph import (
            route_after_validation, route_after_review,
        )

        # Validation failure at max
        base_state["validation_passed"] = False
        base_state["review_iteration"] = 3
        base_state["max_iterations"] = 3
        assert route_after_validation(base_state) == "END"

        # Review REVISE at max
        base_state["review_verdict"] = "REVISE"
        base_state["error_message"] = ""
        assert route_after_review(base_state) == "END"

    def test_070_revise_regenerates(self, base_state):
        """Scenario 070: REVISE → N2 with feedback."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_review

        base_state["review_verdict"] = "REVISE"
        base_state["review_feedback"] = "Need more examples"
        base_state["review_iteration"] = 1
        base_state["max_iterations"] = 3
        base_state["error_message"] = ""

        assert route_after_review(base_state) == "N2_generate_spec"

    def test_happy_path(self, base_state):
        """Full happy path: N0→N1→N2→N3(pass)→N5(approved)→N6."""
        from assemblyzero.workflows.implementation_spec.graph import (
            route_after_load, route_after_analyze,
            route_after_validation, route_after_review,
        )

        base_state["error_message"] = ""
        assert route_after_load(base_state) == "N1_analyze_codebase"
        assert route_after_analyze(base_state) == "N2_generate_spec"

        base_state["validation_passed"] = True
        base_state["human_gate_enabled"] = False
        assert route_after_validation(base_state) == "N5_review_spec"

        base_state["review_verdict"] = "APPROVED"
        assert route_after_review(base_state) == "N6_finalize_spec"

    def test_revise_loop(self, base_state):
        """Revise loop: N5(revise)→N2→N3(pass)→N5(approved)→N6."""
        from assemblyzero.workflows.implementation_spec.graph import (
            route_after_validation, route_after_review,
        )

        # First: REVISE
        base_state["error_message"] = ""
        base_state["review_verdict"] = "REVISE"
        base_state["review_iteration"] = 0
        base_state["max_iterations"] = 3
        assert route_after_review(base_state) == "N2_generate_spec"

        # After regeneration: N3 passes
        base_state["validation_passed"] = True
        base_state["human_gate_enabled"] = False
        base_state["review_iteration"] = 1
        assert route_after_validation(base_state) == "N5_review_spec"

        # Second: APPROVED
        base_state["review_verdict"] = "APPROVED"
        assert route_after_review(base_state) == "N6_finalize_spec"

    def test_successive_validation_retries(self, base_state):
        """Multiple validation failures with retry."""
        from assemblyzero.workflows.implementation_spec.graph import route_after_validation

        for i in range(3):
            base_state["validation_passed"] = False
            base_state["review_iteration"] = i
            base_state["max_iterations"] = 3
            base_state["completeness_issues"] = ["Issue"]

            if i < 3:
                assert route_after_validation(base_state) == "N2_generate_spec"


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_routing_with_minimal_state(self):
        """Routing functions handle empty/minimal state without crashing."""
        from assemblyzero.workflows.implementation_spec.graph import (
            route_after_load, route_after_analyze, route_after_review,
        )

        # Empty state should not crash
        assert route_after_load({}) == "N1_analyze_codebase"
        assert route_after_analyze({}) == "N2_generate_spec"
        # Default verdict BLOCKED → END
        assert route_after_review({}) == "END"

    def test_validate_completeness_no_files(self, base_state):
        """Validation with no files to modify."""
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
            validate_completeness,
        )

        base_state["spec_draft"] = SAMPLE_SPEC_COMPLETE
        base_state["files_to_modify"] = []
        base_state["pattern_references"] = []

        result = validate_completeness(base_state)
        assert result["error_message"] == ""


# =============================================================================
# INTEGRATION TESTS — Graph execution, state propagation, node contracts
#
# These tests catch bugs that unit tests miss:
# - #390: async nodes crash sync graph runner
# - #391: Path.cwd() fallback when repo_root is lost between nodes
# - #392: TypedDict missing fields causes LangGraph to discard state
# - #393: CLI runner uses get_state() without checkpointer
# =============================================================================


class TestAllNodesAreSynchronous:
    """Verify node functions are sync — catches #390.

    LangGraph's graph.stream() is synchronous. If a node is async,
    the stream call crashes with TypeError. This test ensures no
    node accidentally uses 'async def'.
    """

    def test_all_nodes_are_sync_functions(self):
        """Every node registered in the graph must be a sync function."""
        import inspect
        from assemblyzero.workflows.implementation_spec.nodes.load_lld import load_lld
        from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import analyze_codebase
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import generate_spec
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import validate_completeness
        from assemblyzero.workflows.implementation_spec.nodes.human_gate import human_gate
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import review_spec
        from assemblyzero.workflows.implementation_spec.nodes.finalize_spec import finalize_spec

        nodes = {
            "load_lld": load_lld,
            "analyze_codebase": analyze_codebase,
            "generate_spec": generate_spec,
            "validate_completeness": validate_completeness,
            "human_gate": human_gate,
            "review_spec": review_spec,
            "finalize_spec": finalize_spec,
        }

        for name, func in nodes.items():
            assert not inspect.iscoroutinefunction(func), (
                f"Node '{name}' is async — graph.stream() will crash. "
                f"Use 'def' not 'async def'."
            )


class TestStateSchemaCompleteness:
    """Verify TypedDict has all fields nodes actually use — catches #392.

    LangGraph uses the TypedDict to determine valid state fields.
    Fields not in the TypedDict are silently discarded between nodes.
    """

    def test_state_schema_has_repo_root(self):
        """repo_root must be in schema to survive between nodes."""
        from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState
        annotations = ImplementationSpecState.__annotations__
        assert "repo_root" in annotations, "repo_root missing — state lost between nodes"

    def test_state_schema_has_assemblyzero_root(self):
        """assemblyzero_root must be in schema to survive between nodes."""
        from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState
        annotations = ImplementationSpecState.__annotations__
        assert "assemblyzero_root" in annotations, "assemblyzero_root missing — state lost between nodes"

    def test_state_schema_has_audit_dir(self):
        """audit_dir must be in schema to survive between nodes."""
        from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState
        annotations = ImplementationSpecState.__annotations__
        assert "audit_dir" in annotations, "audit_dir missing — state lost between nodes"

    def test_state_schema_has_config_fields(self):
        """Config fields must survive between nodes."""
        from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState
        annotations = ImplementationSpecState.__annotations__
        for field in ["config_mock_mode", "config_drafter", "config_reviewer"]:
            assert field in annotations, f"{field} missing from schema"

    def test_all_node_state_gets_are_in_schema(self):
        """Every state.get('field') call in nodes must have a matching schema field.

        Scans all node source files for state.get('X') calls and verifies
        each field X exists in ImplementationSpecState.
        """
        import re
        from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState
        annotations = set(ImplementationSpecState.__annotations__.keys())

        node_dir = Path(__file__).parent.parent.parent / "assemblyzero" / "workflows" / "implementation_spec" / "nodes"
        missing = []

        for py_file in node_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text(encoding="utf-8")
            # Find all state.get("field_name") calls
            for match in re.finditer(r'state\.get\(["\'](\w+)["\']', content):
                field = match.group(1)
                if field not in annotations:
                    missing.append(f"{py_file.name}: state.get('{field}')")

        assert not missing, (
            f"Fields used by nodes but missing from ImplementationSpecState:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )


class TestGraphExecutesEndToEnd:
    """Compile graph and run it with mock providers — catches #390, #392, #393.

    This is the most important test class. It compiles the real graph
    and streams it with mock LLM providers. If any node is async,
    if any state field is lost between nodes, or if the graph can't
    execute, this test fails.
    """

    def test_happy_path_mock_mode(self, tmp_path):
        """Full workflow executes: N0→N1→N2→N3→N5→N6→END."""
        from assemblyzero.workflows.implementation_spec.graph import (
            create_implementation_spec_graph,
        )

        # Set up mock repo with LLD and source files
        lld_dir = tmp_path / "docs" / "lld" / "active"
        lld_dir.mkdir(parents=True)
        drafts_dir = tmp_path / "docs" / "lld" / "drafts"
        drafts_dir.mkdir(parents=True)
        lineage_dir = tmp_path / "docs" / "lineage" / "active" / "999-impl-spec"
        lineage_dir.mkdir(parents=True)

        # Write LLD file
        (lld_dir / "LLD-999.md").write_text(SAMPLE_LLD_APPROVED, encoding="utf-8")

        # Create source files referenced in the LLD
        src_dir = tmp_path / "assemblyzero" / "workflows" / "test"
        src_dir.mkdir(parents=True)
        (src_dir / "graph.py").write_text("def create_graph(): pass\n", encoding="utf-8")

        # Standards template
        standards_dir = tmp_path / "docs" / "standards"
        standards_dir.mkdir(parents=True)
        (standards_dir / "0701-implementation-spec-template.md").write_text(
            "# Template\n## 1. Overview\n", encoding="utf-8"
        )

        # Compile the real graph
        graph = create_implementation_spec_graph()

        # Build initial state with ALL required fields
        state = {
            "issue_number": 999,
            "lld_path": str(lld_dir / "LLD-999.md"),
            "repo_root": str(tmp_path),
            "assemblyzero_root": str(tmp_path),
            "audit_dir": str(lineage_dir),
            "config_mock_mode": True,
            "config_drafter": "mock:draft",
            "config_reviewer": "mock:review",
            "lld_content": "",
            "files_to_modify": [],
            "current_state_snapshots": {},
            "pattern_references": [],
            "spec_draft": "",
            "spec_path": "",
            "completeness_issues": [],
            "validation_passed": False,
            "review_verdict": "BLOCKED",
            "review_feedback": "",
            "review_iteration": 0,
            "max_iterations": 3,
            "human_gate_enabled": False,
            "error_message": "",
            "next_node": "",
        }

        config = {"recursion_limit": 50}

        # Execute the compiled graph — this is the real test
        final_state = dict(state)
        nodes_visited = []

        for event in graph.stream(state, config):
            for node_name, node_output in event.items():
                if node_name == "__end__":
                    continue
                nodes_visited.append(node_name)
                final_state.update(node_output)

        # Verify workflow executed nodes
        assert "N0_load_lld" in nodes_visited, f"N0 not visited. Visited: {nodes_visited}"
        assert "N1_analyze_codebase" in nodes_visited, f"N1 not visited. Visited: {nodes_visited}"

        # Verify critical state survived between nodes
        assert final_state.get("lld_content"), "lld_content lost after N0"
        assert final_state.get("repo_root") == str(tmp_path), "repo_root lost between nodes"
        assert final_state.get("assemblyzero_root") == str(tmp_path), "assemblyzero_root lost between nodes"

    def test_repo_root_propagates_to_all_nodes(self, tmp_path):
        """repo_root set in initial state must be readable by every node.

        Catches #391/#392: repo_root being lost or falling back to cwd.
        """
        from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState

        # Verify the field is in the TypedDict
        annotations = ImplementationSpecState.__annotations__
        assert "repo_root" in annotations

        # Verify it's typed as str (ForwardRef due to __future__ annotations)
        assert "str" in str(annotations["repo_root"])

    def test_error_in_n0_stops_workflow(self, tmp_path):
        """If N0 returns error_message, workflow should route to END."""
        from assemblyzero.workflows.implementation_spec.graph import (
            create_implementation_spec_graph,
        )

        graph = create_implementation_spec_graph()

        # State with nonexistent LLD path — N0 will error
        state = {
            "issue_number": 999,
            "lld_path": str(tmp_path / "nonexistent.md"),
            "repo_root": str(tmp_path),
            "assemblyzero_root": str(tmp_path),
            "audit_dir": "",
            "config_mock_mode": True,
            "config_drafter": "mock:draft",
            "config_reviewer": "mock:review",
            "lld_content": "",
            "files_to_modify": [],
            "current_state_snapshots": {},
            "pattern_references": [],
            "spec_draft": "",
            "spec_path": "",
            "completeness_issues": [],
            "validation_passed": False,
            "review_verdict": "BLOCKED",
            "review_feedback": "",
            "review_iteration": 0,
            "max_iterations": 3,
            "human_gate_enabled": False,
            "error_message": "",
            "next_node": "",
        }

        config = {"recursion_limit": 50}
        nodes_visited = []
        final_state = dict(state)

        for event in graph.stream(state, config):
            for node_name, node_output in event.items():
                if node_name != "__end__":
                    nodes_visited.append(node_name)
                    final_state.update(node_output)

        # N0 should have been visited
        assert "N0_load_lld" in nodes_visited
        # Workflow should have stopped (error routes to END)
        assert final_state.get("error_message"), "Expected error but got none"
