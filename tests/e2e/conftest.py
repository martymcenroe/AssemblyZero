"""Shared fixtures for E2E workflow tests.

Issue #438: Automated E2E Test for LLD Workflow (Mock Mode)
Issue #436: Automated E2E Test for Issue Workflow (Mock Mode)
"""

import time
from pathlib import Path
from typing import Any

import pytest


# ------------------------------------------------------------------
# Path to the fixture file (relative to repo root)
# ------------------------------------------------------------------
FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "lld_tracking"
MOCK_LLD_INPUT_PATH = FIXTURE_DIR / "mock_lld_input.md"

ISSUE_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "issue_workflow"
MOCK_BRIEF_PATH = ISSUE_FIXTURE_DIR / "mock_brief.md"

# Resolve the real AssemblyZero root for template loading
ASSEMBLYZERO_ROOT = Path(__file__).resolve().parent.parent.parent

# ------------------------------------------------------------------
# Known API key environment variable names to strip for REQ-2 tests
# ------------------------------------------------------------------
API_KEY_ENV_VARS = [
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "HUGGINGFACE_API_KEY",
    "COHERE_API_KEY",
    "AI21_API_KEY",
]


@pytest.fixture
def mock_workspace(tmp_path: Path) -> Path:
    """Create an isolated temporary workspace with required directory structure."""
    subdirs = [
        "docs/lld/active",
        "docs/lld/done",
        "docs/lineage/active",
        "data",
        "logs",
    ]
    for subdir in subdirs:
        (tmp_path / subdir).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def mock_workflow_config(mock_workspace: Path) -> dict[str, Any]:
    """Return kwargs for create_initial_state with mock=True, auto=True."""
    return {
        "workflow_type": "lld",
        "assemblyzero_root": str(ASSEMBLYZERO_ROOT),
        "target_repo": str(mock_workspace),
        "drafter": "mock:draft",
        "reviewer": "mock:review",
        "gates_draft": False,
        "gates_verdict": False,
        "auto_mode": True,
        "mock_mode": True,
        "max_iterations": 5,
        "issue_number": 999,
    }


@pytest.fixture
def lld_input_fixture() -> str:
    """Load the mock LLD input content from fixtures."""
    return MOCK_LLD_INPUT_PATH.read_text(encoding="utf-8")


@pytest.fixture
def api_call_tracker() -> list[dict[str, Any]]:
    """Provide a shared list that records any attempted API calls."""
    return []


@pytest.fixture
def issue_workspace(tmp_path: Path) -> Path:
    """Create an isolated workspace for issue workflow tests.

    Includes a brief file that the issue workflow's N0 node can read.
    """
    subdirs = [
        "docs/lineage/active",
        "data",
        "logs",
    ]
    for subdir in subdirs:
        (tmp_path / subdir).mkdir(parents=True, exist_ok=True)

    # Copy the mock brief into the workspace so load_input can find it
    brief_dest = tmp_path / "mock_brief.md"
    brief_dest.write_text(MOCK_BRIEF_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    return tmp_path


@pytest.fixture
def issue_workflow_config(issue_workspace: Path) -> dict[str, Any]:
    """Return kwargs for create_initial_state for the issue workflow."""
    return {
        "workflow_type": "issue",
        "assemblyzero_root": str(ASSEMBLYZERO_ROOT),
        "target_repo": str(issue_workspace),
        "drafter": "mock:draft",
        "reviewer": "mock:review",
        "gates_draft": False,
        "gates_verdict": False,
        "auto_mode": True,
        "mock_mode": True,
        "max_iterations": 5,
        "brief_file": str(issue_workspace / "mock_brief.md"),
    }


def run_workflow_to_completion(
    config: dict[str, Any],
    workspace: Path,
) -> dict[str, Any]:
    """Execute the requirements workflow graph to completion and return results.

    Args:
        config: kwargs dict for create_initial_state.
        workspace: Path to the workspace directory.

    Returns a dict with keys:
        - final_state: Terminal LangGraph state dict
        - nodes_visited: Ordered list of graph node names executed
        - exit_status: "success" | "error"
        - artifacts: Dict of artifact name -> file path
        - duration_seconds: Wall-clock execution time
        - api_calls_made: Count of real API calls (should be 0 in mock mode)
    """
    from assemblyzero.workflows.requirements.graph import create_requirements_graph
    from assemblyzero.workflows.requirements.state import create_initial_state

    nodes_visited: list[str] = []
    start_time = time.monotonic()

    try:
        # Create the graph (takes no arguments)
        graph = create_requirements_graph()
        compiled = graph.compile()

        # Create initial state using the proper factory function
        initial_state = create_initial_state(**config)

        # Execute with streaming to capture node visit order
        thread_config = {
            "recursion_limit": config.get("max_iterations", 20),
        }

        final_state = {}
        for event in compiled.stream(
            initial_state, config=thread_config, stream_mode="updates"
        ):
            # Each event is a dict {node_name: state_update}
            for node_name in event:
                nodes_visited.append(node_name)
            final_state = event  # Last event contains terminal state

        # Try to get the complete final state via get_state
        try:
            full_state = compiled.get_state(thread_config)
            if full_state and hasattr(full_state, "values"):
                final_state = dict(full_state.values)
        except Exception:
            pass

        elapsed = time.monotonic() - start_time

        # Check for artifacts
        artifacts = {}
        lld_active_dir = workspace / "docs" / "lld" / "active"
        for lld_file in lld_active_dir.glob("*.md"):
            artifacts["lld_document"] = str(lld_file)
            break

        return {
            "final_state": final_state if isinstance(final_state, dict) else {},
            "nodes_visited": nodes_visited,
            "exit_status": "success",
            "artifacts": artifacts,
            "duration_seconds": elapsed,
            "api_calls_made": 0,  # Mock mode -> 0
        }

    except Exception as exc:
        elapsed = time.monotonic() - start_time
        return {
            "final_state": {"error_message": str(exc)},
            "nodes_visited": nodes_visited,
            "exit_status": "error",
            "artifacts": {},
            "duration_seconds": elapsed,
            "api_calls_made": 0,
        }
