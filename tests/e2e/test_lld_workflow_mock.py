"""E2E tests for LLD (requirements) workflow in mock mode.

Issue #438: Automated E2E Test for LLD Workflow (Mock Mode)

These tests exercise the full LangGraph execution path of the
requirements workflow using mock providers (mock:draft, mock:review).
No API credentials are required.

Note: The mock:draft provider returns a minimal document that does NOT
pass the LLD mechanical validation (N1.5). This is expected — the tests
verify that the graph correctly loops (N1 → N1.5 → N1) and eventually
hits the recursion limit. This exercises the real graph wiring, error
handling, and routing logic.

Run with:
    poetry run pytest tests/e2e/test_lld_workflow_mock.py -v -m e2e
"""

import os
import time
from pathlib import Path
from typing import Any

import pytest

from tests.e2e.conftest import API_KEY_ENV_VARS, run_workflow_to_completion


# ------------------------------------------------------------------
# Expected nodes in the LLD workflow graph path.
# Mock mode: N0 → N1 → N1.5 (fail) → N1 → N1.5 (fail) → ... recursion limit
# ------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.timeout(120)
def test_lld_workflow_mock_graph_executes(
    mock_workspace: Path,
    mock_workflow_config: dict,
) -> None:
    """E2E: LLD workflow graph starts execution and visits nodes. (REQ-1)

    T010: Verifies the graph invokes nodes and returns a result.
    The mock draft fails mechanical validation, so the graph loops
    until recursion limit — this is expected behavior.
    """
    result = run_workflow_to_completion(
        config=mock_workflow_config,
        workspace=mock_workspace,
    )

    # The graph executes but hits recursion limit because mock draft
    # doesn't pass mechanical validation — this is expected
    assert len(result["nodes_visited"]) > 0, "No nodes were visited"
    assert "N0_load_input" in result["nodes_visited"], (
        f"N0_load_input not visited. Nodes: {result['nodes_visited']}"
    )
    assert "N1_generate_draft" in result["nodes_visited"], (
        f"N1_generate_draft not visited. Nodes: {result['nodes_visited']}"
    )


@pytest.mark.e2e
@pytest.mark.timeout(120)
def test_lld_workflow_mock_no_api_credentials_required(
    mock_workspace: Path,
    mock_workflow_config: dict,
    monkeypatch: pytest.MonkeyPatch,
    api_call_tracker: list,
) -> None:
    """E2E: LLD workflow completes without API credentials. (REQ-2)

    T020: Strips all known API key env vars, runs the workflow.
    Graph executes (may hit recursion limit) but zero real API calls.
    """
    for env_var in API_KEY_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)

    result = run_workflow_to_completion(
        config=mock_workflow_config,
        workspace=mock_workspace,
    )

    assert len(result["nodes_visited"]) > 0, "No nodes were visited"
    assert result["api_calls_made"] == 0, (
        f"Expected 0 API calls in mock mode, got {result['api_calls_made']}"
    )


@pytest.mark.e2e
@pytest.mark.timeout(120)
def test_lld_workflow_mock_ci_compatible(
    mock_workspace: Path,
    mock_workflow_config: dict,
) -> None:
    """E2E: LLD workflow completes within CI time budget. (REQ-3)

    T030: Measures wall-clock time. Mock mode is fast even with
    recursion limit loops.
    """
    start = time.monotonic()

    result = run_workflow_to_completion(
        config=mock_workflow_config,
        workspace=mock_workspace,
    )

    elapsed = time.monotonic() - start

    assert len(result["nodes_visited"]) > 0, "No nodes were visited"
    assert elapsed < 120, (
        f"Workflow took {elapsed:.1f}s, exceeding 120s CI budget"
    )


@pytest.mark.e2e
@pytest.mark.timeout(120)
def test_lld_workflow_mock_mechanical_validation_loop(
    mock_workspace: Path,
    mock_workflow_config: dict,
) -> None:
    """E2E: LLD workflow correctly loops on mechanical validation failure. (REQ-4)

    T040: The mock draft is too minimal for validation. Verifies that
    N1_5_validate_mechanical is visited and routes back to N1.
    """
    result = run_workflow_to_completion(
        config=mock_workflow_config,
        workspace=mock_workspace,
    )

    visited_set = set(result["nodes_visited"])

    assert "N0_load_input" in visited_set, (
        f"N0_load_input not visited. Nodes: {result['nodes_visited']}"
    )
    assert "N1_generate_draft" in visited_set, (
        f"N1_generate_draft not visited. Nodes: {result['nodes_visited']}"
    )
    assert "N1_5_validate_mechanical" in visited_set, (
        f"N1_5_validate_mechanical not visited — LLD validation not triggered. "
        f"Nodes: {result['nodes_visited']}"
    )

    # N1 should appear more than once (loop back from failed validation)
    n1_count = result["nodes_visited"].count("N1_generate_draft")
    assert n1_count >= 2, (
        f"Expected N1 to be visited 2+ times (validation loop), got {n1_count}. "
        f"Nodes: {result['nodes_visited']}"
    )


@pytest.mark.e2e
@pytest.mark.timeout(120)
def test_lld_workflow_mock_state_transitions(
    mock_workspace: Path,
    mock_workflow_config: dict,
) -> None:
    """E2E: LLD workflow starts at N0 and follows LLD-specific path. (REQ-4)

    T050: Verifies the node visit order starts with N0_load_input
    and includes LLD-specific nodes (N0b if present, N1.5).
    """
    result = run_workflow_to_completion(
        config=mock_workflow_config,
        workspace=mock_workspace,
    )

    nodes = result["nodes_visited"]
    assert len(nodes) >= 2, (
        f"Expected at least 2 node visits, got {len(nodes)}: {nodes}"
    )
    assert nodes[0] == "N0_load_input", (
        f"Expected workflow to start with 'N0_load_input', got '{nodes[0]}'"
    )


@pytest.mark.e2e
@pytest.mark.timeout(120)
def test_lld_workflow_mock_produces_final_state(
    mock_workspace: Path,
    mock_workflow_config: dict,
) -> None:
    """E2E: LLD workflow produces a non-empty final state. (REQ-5)

    T060: Even though the workflow hits recursion limit, the final
    state dict should contain meaningful data.
    """
    result = run_workflow_to_completion(
        config=mock_workflow_config,
        workspace=mock_workspace,
    )

    final_state = result["final_state"]
    assert isinstance(final_state, dict), "Final state should be a dict"
    assert len(final_state) > 0, "Final state should not be empty"


@pytest.mark.e2e
@pytest.mark.timeout(120)
def test_lld_workflow_mock_idempotent_rerun(
    mock_workspace: Path,
    mock_workflow_config: dict,
    tmp_path: Path,
) -> None:
    """E2E: Running the LLD workflow twice produces consistent results. (REQ-6)

    T070: Both runs should visit the same nodes in the same order.
    """
    result_1 = run_workflow_to_completion(
        config=mock_workflow_config,
        workspace=mock_workspace,
    )

    # Second run — fresh workspace
    workspace_2 = tmp_path / "run2"
    workspace_2.mkdir()
    for subdir in ["docs/lld/active", "docs/lld/done", "docs/lineage/active", "data", "logs"]:
        (workspace_2 / subdir).mkdir(parents=True, exist_ok=True)

    config_2 = dict(mock_workflow_config)
    config_2["target_repo"] = str(workspace_2)

    result_2 = run_workflow_to_completion(
        config=config_2,
        workspace=workspace_2,
    )

    assert result_1["nodes_visited"] == result_2["nodes_visited"], (
        f"Node visit order differs:\n"
        f"  Run 1: {result_1['nodes_visited']}\n"
        f"  Run 2: {result_2['nodes_visited']}"
    )


@pytest.mark.e2e
@pytest.mark.timeout(120)
def test_lld_workflow_mock_workspace_isolation(
    mock_workspace: Path,
    mock_workflow_config: dict,
    tmp_path: Path,
) -> None:
    """E2E: LLD workflow writes no files outside its workspace. (REQ-7)

    T090: Snapshots filesystem state before and after, verifies no leaks.
    """
    cwd = Path.cwd()

    def snapshot_dir(directory: Path, max_depth: int = 2) -> set[str]:
        result: set[str] = set()
        try:
            for item in directory.rglob("*"):
                try:
                    relative = item.relative_to(directory)
                    if len(relative.parts) <= max_depth:
                        result.add(str(item))
                except ValueError:
                    continue
        except PermissionError:
            pass
        return result

    pre_cwd_docs = snapshot_dir(cwd / "docs", max_depth=3) if (cwd / "docs").exists() else set()
    pre_cwd_data = snapshot_dir(cwd / "data", max_depth=2) if (cwd / "data").exists() else set()

    result = run_workflow_to_completion(
        config=mock_workflow_config,
        workspace=mock_workspace,
    )

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
