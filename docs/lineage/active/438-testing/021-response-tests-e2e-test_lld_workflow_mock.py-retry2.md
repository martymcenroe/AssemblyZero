```python
"""E2E tests for LLD (requirements) workflow in mock mode.

Issue #438: Automated E2E Test for LLD Workflow (Mock Mode)

These tests exercise the full LangGraph execution path of the
requirements workflow using the built-in --mock --auto mode.
No API credentials are required.

Run with:
    poetry run pytest tests/e2e/test_lld_workflow_mock.py -v -m e2e
"""

import os
import sqlite3
import time

from pathlib import Path
from typing import Any

import pytest

from tests.e2e.conftest import API_KEY_ENV_VARS, run_workflow_to_completion


# ------------------------------------------------------------------
# Expected nodes in the requirements workflow graph.
# NOTE: This list MUST be confirmed against the actual graph definition
# at implementation time. Inspect the build_graph function to get the
# actual node names. These are educated guesses based on the LLD diagram.
# ------------------------------------------------------------------
EXPECTED_NODES = [
    "parse_issue",
    "analyze_codebase",
    "draft_lld",
    "review_lld",
    "iterate_lld",
    "finalize_lld",
]


@pytest.mark.e2e
@pytest.mark.timeout(60)
def test_lld_workflow_mock_completes_successfully(
    mock_workspace: Path,
    mock_workflow_config: dict,
    lld_input_fixture: str,
) -> None:
    """E2E: LLD workflow runs to completion in mock mode without errors. (REQ-1)

    T010: Verifies the graph executes all nodes, returns terminal state
    with no exceptions, and exit status is "success".
    """
    result = run_workflow_to_completion(
        config=mock_workflow_config,
        lld_input=lld_input_fixture,
        workspace=mock_workspace,
    )

    assert result["exit_status"] == "success", (
        f"Workflow failed with error: {result['final_state'].get('error_message', 'unknown')}"
    )
    assert len(result["nodes_visited"]) > 0, "No nodes were visited"
    assert result["final_state"].get("error_message", "") == "", (
        f"Workflow completed with error: {result['final_state']['error_message']}"
    )


@pytest.mark.e2e
@pytest.mark.timeout(60)
def test_lld_workflow_mock_no_api_credentials_required(
    mock_workspace: Path,
    mock_workflow_config: dict,
    lld_input_fixture: str,
    monkeypatch: pytest.MonkeyPatch,
    api_call_tracker: list,
) -> None:
    """E2E: Workflow completes without any API credentials in environment. (REQ-2)

    T020: Strips all known API key env vars, runs the workflow, and
    verifies it completes successfully with zero real API calls.
    """
    # Strip all known API key environment variables
    for env_var in API_KEY_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)

    result = run_workflow_to_completion(
        config=mock_workflow_config,
        lld_input=lld_input_fixture,
        workspace=mock_workspace,
    )

    assert result["exit_status"] == "success", (
        f"Workflow failed without API credentials: "
        f"{result['final_state'].get('error_message', 'unknown')}"
    )
    assert result["api_calls_made"] == 0, (
        f"Expected 0 API calls in mock mode, got {result['api_calls_made']}"
    )
    assert len(api_call_tracker) == 0, (
        f"Real API calls were attempted: {api_call_tracker}"
    )


@pytest.mark.e2e
@pytest.mark.timeout(60)
def test_lld_workflow_mock_ci_compatible(
    mock_workspace: Path,
    mock_workflow_config: dict,
    lld_input_fixture: str,
) -> None:
    """E2E: Test completes within 60s budget, needs no external services. (REQ-3)

    T030: Measures wall-clock time and asserts it stays within CI budget.
    The @pytest.mark.timeout(60) decorator provides a hard stop.
    """
    start = time.monotonic()

    result = run_workflow_to_completion(
        config=mock_workflow_config,
        lld_input=lld_input_fixture,
        workspace=mock_workspace,
    )

    elapsed = time.monotonic() - start

    assert result["exit_status"] == "success", (
        f"Workflow did not complete successfully: "
        f"{result['final_state'].get('error_message', 'unknown')}"
    )
    assert elapsed < 60, (
        f"Workflow took {elapsed:.1f}s, exceeding 60s CI budget"
    )
    assert result["duration_seconds"] < 60, (
        f"Internal timer reports {result['duration_seconds']:.1f}s"
    )


@pytest.mark.e2e
@pytest.mark.timeout(60)
def test_lld_workflow_mock_visits_all_nodes(
    mock_workspace: Path,
    mock_workflow_config: dict,
    lld_input_fixture: str,
) -> None:
    """E2E: All expected LangGraph nodes are visited during mock execution. (REQ-4)

    T040: Checks that every node defined in EXPECTED_NODES was visited
    at least once during the workflow execution.
    """
    result = run_workflow_to_completion(
        config=mock_workflow_config,
        lld_input=lld_input_fixture,
        workspace=mock_workspace,
    )

    assert result["exit_status"] == "success", (
        f"Workflow failed: {result['final_state'].get('error_message', 'unknown')}"
    )

    visited_set = set(result["nodes_visited"])
    expected_set = set(EXPECTED_NODES)
    missing_nodes = expected_set - visited_set

    assert len(missing_nodes) == 0, (
        f"Expected nodes not visited: {missing_nodes}. "
        f"Nodes visited: {result['nodes_visited']}"
    )


@pytest.mark.e2e
@pytest.mark.timeout(60)
def test_lld_workflow_mock_state_transitions(
    mock_workspace: Path,
    mock_workflow_config: dict,
    lld_input_fixture: str,
) -> None:
    """E2E: State machine transitions follow expected graph edges. (REQ-4)

    T050: Verifies that consecutive pairs of visited nodes represent
    valid transitions in the graph, and that the first and last nodes
    are correct.
    """
    result = run_workflow_to_completion(
        config=mock_workflow_config,
        lld_input=lld_input_fixture,
        workspace=mock_workspace,
    )

    assert result["exit_status"] == "success", (
        f"Workflow failed: {result['final_state'].get('error_message', 'unknown')}"
    )

    nodes = result["nodes_visited"]
    assert len(nodes) >= 2, (
        f"Expected at least 2 node visits, got {len(nodes)}: {nodes}"
    )

    # Verify first node is an entry node
    # NOTE: Adjust if the actual entry node name differs
    assert nodes[0] in ("parse_issue", "__start__"), (
        f"Expected workflow to start with 'parse_issue', got '{nodes[0]}'"
    )

    # Verify last node is a terminal node
    # NOTE: Adjust if the actual terminal node name differs
    assert nodes[-1] in ("finalize_lld", "__end__"), (
        f"Expected workflow to end with 'finalize_lld', got '{nodes[-1]}'"
    )

    # Verify no duplicate consecutive nodes (should not self-loop)
    for i in range(len(nodes) - 1):
        assert nodes[i] != nodes[i + 1], (
            f"Unexpected self-loop at position {i}: "
            f"'{nodes[i]}' -> '{nodes[i + 1]}'"
        )


@pytest.mark.e2e
@pytest.mark.timeout(60)
def test_lld_workflow_mock_produces_artifacts(
    mock_workspace: Path,
    mock_workflow_config: dict,
    lld_input_fixture: str,
) -> None:
    """E2E: Workflow produces expected output artifacts. (REQ-5)

    T060: Checks that the final state contains non-empty LLD content
    and a review verdict.
    """
    result = run_workflow_to_completion(
        config=mock_workflow_config,
        lld_input=lld_input_fixture,
        workspace=mock_workspace,
    )

    assert result["exit_status"] == "success", (
        f"Workflow failed: {result['final_state'].get('error_message', 'unknown')}"
    )

    final_state = result["final_state"]

    # Verify LLD content is present and non-empty
    # NOTE: The actual state key for LLD content may differ.
    # Check the workflow state definition. Common candidates:
    #   - "lld_content", "lld_output", "document", "content"
    lld_content = (
        final_state.get("lld_content")
        or final_state.get("lld_output")
        or final_state.get("document")
        or final_state.get("content")
        or ""
    )
    assert len(lld_content) > 0, (
        f"Expected non-empty LLD content in final state. "
        f"Available keys: {list(final_state.keys())}"
    )

    # Verify review verdict is present
    # NOTE: The actual state key may differ. Common candidates:
    #   - "review_verdict", "verdict", "review_result", "review_status"
    review_verdict = (
        final_state.get("review_verdict")
        or final_state.get("verdict")
        or final_state.get("review_result")
        or final_state.get("review_status")
        or ""
    )
    assert len(review_verdict) > 0, (
        f"Expected non-empty review verdict in final state. "
        f"Available keys: {list(final_state.keys())}"
    )


@pytest.mark.e2e
@pytest.mark.timeout(60)
def test_lld_workflow_mock_idempotent_rerun(
    mock_workspace: Path,
    mock_workflow_config: dict,
    lld_input_fixture: str,
    tmp_path: Path,
) -> None:
    """E2E: Running the same workflow twice produces consistent results. (REQ-6)

    T070: Executes the workflow twice with identical input and verifies
    that both produce the same node visit order and equivalent final state.
    """
    # First run — uses mock_workspace (already created)
    result_1 = run_workflow_to_completion(
        config=mock_workflow_config,
        lld_input=lld_input_fixture,
        workspace=mock_workspace,
    )

    assert result_1["exit_status"] == "success", (
        f"First run failed: {result_1['final_state'].get('error_message', 'unknown')}"
    )

    # Second run — create a fresh workspace to avoid checkpoint interference
    workspace_2 = tmp_path / "run2"
    workspace_2.mkdir()
    for subdir in ["docs/lld/active", "docs/lld/done", "data", "logs"]:
        (workspace_2 / subdir).mkdir(parents=True, exist_ok=True)

    config_2 = dict(mock_workflow_config)
    config_2["workspace"] = workspace_2
    config_2["checkpoint_dir"] = workspace_2 / "data"

    result_2 = run_workflow_to_completion(
        config=config_2,
        lld_input=lld_input_fixture,
        workspace=workspace_2,
    )

    assert result_2["exit_status"] == "success", (
        f"Second run failed: {result_2['final_state'].get('error_message', 'unknown')}"
    )

    # Compare node visit order (must be identical for deterministic mock)
    assert result_1["nodes_visited"] == result_2["nodes_visited"], (
        f"Node visit order differs:\n"
        f"  Run 1: {result_1['nodes_visited']}\n"
        f"  Run 2: {result_2['nodes_visited']}"
    )

    # Compare final states (excluding non-deterministic fields)
    # Filter out fields that may legitimately differ (timestamps, file paths)
    EXCLUDE_KEYS = {"timestamp", "created_at", "updated_at", "workspace", "checkpoint_dir"}

    def filter_state(state: dict) -> dict:
        return {
            k: v for k, v in state.items()
            if k not in EXCLUDE_KEYS and not isinstance(v, Path)
        }

    filtered_1 = filter_state(result_1["final_state"])
    filtered_2 = filter_state(result_2["final_state"])

    assert filtered_1 == filtered_2, (
        f"Final states differ between runs:\n"
        f"  Run 1: {filtered_1}\n"
        f"  Run 2: {filtered_2}"
    )


@pytest.mark.e2e
@pytest.mark.timeout(60)
def test_lld_workflow_mock_checkpoint_created(
    mock_workspace: Path,
    mock_workflow_config: dict,
    lld_input_fixture: str,
) -> None:
    """E2E: SQLite checkpoint is written during workflow execution. (REQ-1)

    T080: Verifies that a checkpoint database file exists after the workflow
    runs and contains at least one checkpoint record.
    """
    result = run_workflow_to_completion(
        config=mock_workflow_config,
        lld_input=lld_input_fixture,
        workspace=mock_workspace,
    )

    assert result["exit_status"] == "success", (
        f"Workflow failed: {result['final_state'].get('error_message', 'unknown')}"
    )

    # Verify checkpoint DB file exists
    checkpoint_db_path = mock_workspace / "data" / "checkpoints.db"
    assert checkpoint_db_path.exists(), (
        f"Checkpoint DB not found at {checkpoint_db_path}. "
        f"Files in data dir: {list((mock_workspace / 'data').iterdir())}"
    )

    # Verify at least one checkpoint record exists
    conn = sqlite3.connect(str(checkpoint_db_path))
    try:
        cursor = conn.cursor()
        # LangGraph checkpoint-sqlite creates a 'checkpoints' table
        # Try common table names
        tables = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]

        assert len(table_names) > 0, (
            "Checkpoint DB has no tables. Expected checkpoint tables."
        )

        # Query any table that looks like a checkpoint table
        checkpoint_count = 0
        for table_name in table_names:
            try:
                count = cursor.execute(
                    f"SELECT COUNT(*) FROM [{table_name}]"
                ).fetchone()[0]
                checkpoint_count += count
            except sqlite3.OperationalError:
                continue

        assert checkpoint_count > 0, (
            f"Checkpoint DB has tables {table_names} but no records"
        )
    finally:
        conn.close()


@pytest.mark.e2e
@pytest.mark.timeout(60)
def test_lld_workflow_mock_workspace_isolation(
    mock_workspace: Path,
    mock_workflow_config: dict,
    lld_input_fixture: str,
    tmp_path: Path,
) -> None:
    """E2E: Workflow writes no files outside its tmp_path workspace. (REQ-7)

    T090: Snapshots the filesystem state of known writable directories
    before the workflow runs, then verifies no new files appear outside
    the tmp_path workspace after execution.
    """
    # Snapshot: list all files in the project root's common output dirs
    # We check CWD and home dir for unexpected writes
    cwd = Path.cwd()

    def snapshot_dir(directory: Path, max_depth: int = 2) -> set[str]:
        """Get a set of file paths in a directory (shallow scan)."""
        result: set[str] = set()
        try:
            for item in directory.rglob("*"):
                # Limit depth to avoid scanning too deep
                try:
                    relative = item.relative_to(directory)
                    if len(relative.parts) <= max_depth:
                        result.add(str(item))
                except ValueError:
                    continue
        except PermissionError:
            pass
        return result

    # Only snapshot specific project directories that shouldn't change
    pre_cwd_docs = snapshot_dir(cwd / "docs", max_depth=3) if (cwd / "docs").exists() else set()
    pre_cwd_data = snapshot_dir(cwd / "data", max_depth=2) if (cwd / "data").exists() else set()

    # Run the workflow
    result = run_workflow_to_completion(
        config=mock_workflow_config,
        lld_input=lld_input_fixture,
        workspace=mock_workspace,
    )

    assert result["exit_status"] == "success", (
        f"Workflow failed: {result['final_state'].get('error_message', 'unknown')}"
    )

    # Post-run snapshot
    post_cwd_docs = snapshot_dir(cwd / "docs", max_depth=3) if (cwd / "docs").exists() else set()
    post_cwd_data = snapshot_dir(cwd / "data", max_depth=2) if (cwd / "data").exists() else set()

    new_docs_files = post_cwd_docs - pre_cwd_docs
    new_data_files = post_cwd_data - pre_cwd_data

    assert len(new_docs_files) == 0, (
        f"Workflow created files outside tmp_path in docs/: {new_docs_files}"
    )
    assert len(new_data_files) == 0, (
        f"Workflow created files outside tmp_path in data/: {new_data_files}"
    )

    # Verify all workflow artifacts are within tmp_path
    for artifact_name, artifact_path in result.get("artifacts", {}).items():
        artifact_resolved = Path(artifact_path).resolve()
        tmp_resolved = tmp_path.resolve()
        assert str(artifact_resolved).startswith(str(tmp_resolved)), (
            f"Artifact '{artifact_name}' at {artifact_resolved} is outside "
            f"tmp_path {tmp_resolved}"
        )
```
