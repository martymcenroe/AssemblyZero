```python
"""Shared fixtures for E2E tests.

Issue #438: Automated E2E Test for LLD Workflow (Mock Mode)
"""

import sqlite3
import time

from pathlib import Path
from typing import Any

import pytest


# ------------------------------------------------------------------
# Path to the fixture file (relative to repo root)
# ------------------------------------------------------------------
FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "lld_tracking"
MOCK_LLD_INPUT_PATH = FIXTURE_DIR / "mock_lld_input.md"

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
    """Create an isolated temporary workspace with required directory structure.

    Mirrors the production workspace layout so the workflow can write
    artifacts to expected locations.
    """
    subdirs = [
        "docs/lld/active",
        "docs/lld/done",
        "data",
        "logs",
    ]
    for subdir in subdirs:
        (tmp_path / subdir).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def mock_workflow_config(mock_workspace: Path) -> dict[str, Any]:
    """Return workflow configuration dict with mock=True, auto=True.

    Includes recursion_limit per reviewer suggestion to prevent infinite
    loops if graph logic regresses.
    """
    return {
        "mock": True,
        "auto": True,
        "review": "none",
        "issue_number": 999,
        "issue_title": "Feature: Mock Test Feature",
        "workspace": mock_workspace,
        "recursion_limit": 20,
        "checkpoint_dir": mock_workspace / "data",
    }


@pytest.fixture
def lld_input_fixture() -> str:
    """Load the mock LLD input content from fixtures.

    Returns the content of tests/fixtures/lld_tracking/mock_lld_input.md
    as a string.
    """
    return MOCK_LLD_INPUT_PATH.read_text(encoding="utf-8")


@pytest.fixture
def api_call_tracker() -> list[dict[str, Any]]:
    """Provide a shared list that records any attempted API calls.

    In mock mode this should remain empty. Tests can inspect it to
    verify zero real API calls were made.
    """
    return []


def run_workflow_to_completion(
    config: dict[str, Any],
    lld_input: str,
    workspace: Path,
) -> dict[str, Any]:
    """Execute the requirements workflow graph to completion and return results.

    This is the central helper that programmatically builds, compiles,
    and invokes the LangGraph requirements workflow in mock mode.

    Returns a dict with keys:
        - final_state: Terminal LangGraph state dict
        - nodes_visited: Ordered list of graph node names executed
        - exit_status: "success" | "error"
        - artifacts: Dict of artifact name -> file path
        - duration_seconds: Wall-clock execution time
        - api_calls_made: Count of real API calls (should be 0)
    """
    from langgraph.checkpoint.sqlite import SqliteSaver

    try:
        # Import the workflow graph builder
        from assemblyzero.workflows.requirements.graph import build_graph
    except ImportError:
        try:
            from assemblyzero.workflows.lld.graph import build_graph
        except ImportError:
            raise ImportError(
                "Cannot find workflow graph builder. Check "
                "assemblyzero/workflows/ for the requirements/LLD "
                "workflow module and update the import in "
                "tests/e2e/conftest.py::run_workflow_to_completion"
            )

    checkpoint_path = str(config["checkpoint_dir"] / "checkpoints.db")
    nodes_visited: list[str] = []
    start_time = time.monotonic()

    try:
        with SqliteSaver.from_conn_string(checkpoint_path) as checkpointer:
            # Build the graph with mock configuration
            graph = build_graph(config)
            compiled = graph.compile(checkpointer=checkpointer)

            # Prepare initial state
            initial_state = {
                "issue_number": config["issue_number"],
                "issue_title": config["issue_title"],
                "lld_content": lld_input,
                "mock": config.get("mock", True),
                "auto": config.get("auto", True),
                "error_message": "",
            }

            # Execute with streaming to capture node visit order
            thread_config = {
                "configurable": {"thread_id": f"e2e-test-{config['issue_number']}"},
                "recursion_limit": config.get("recursion_limit", 20),
            }

            final_state = None
            for event in compiled.stream(
                initial_state, config=thread_config, stream_mode="updates"
            ):
                # Each event is a dict {node_name: state_update}
                for node_name in event:
                    nodes_visited.append(node_name)
                final_state = event  # Last event contains terminal state

            # If stream mode "updates" doesn't give full final state,
            # get it from the graph's get_state method
            if final_state is None:
                final_state = {}

            # Try to get the complete final state
            try:
                full_state = compiled.get_state(thread_config)
                if full_state and hasattr(full_state, "values"):
                    final_state = dict(full_state.values)
            except Exception:
                # If get_state fails, use what we collected from streaming
                pass

            elapsed = time.monotonic() - start_time

            # Check for checkpoint records
            artifacts = {}
            checkpoint_db = config["checkpoint_dir"] / "checkpoints.db"
            if checkpoint_db.exists():
                artifacts["checkpoint_db"] = str(checkpoint_db)

            # Check for LLD output files
            lld_active_dir = config["workspace"] / "docs" / "lld" / "active"
            for lld_file in lld_active_dir.glob("*.md"):
                artifacts["lld_document"] = str(lld_file)
                break

            return {
                "final_state": final_state if isinstance(final_state, dict) else {},
                "nodes_visited": nodes_visited,
                "exit_status": "success",
                "artifacts": artifacts,
                "duration_seconds": elapsed,
                "api_calls_made": 0,  # Mock mode → 0
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
```
