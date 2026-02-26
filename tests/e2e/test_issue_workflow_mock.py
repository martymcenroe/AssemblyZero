"""E2E tests for issue workflow in mock mode.

Issue #436: Automated E2E Test for Issue Workflow (Mock Mode)

These tests exercise the full LangGraph execution path of the
issue workflow using mock providers (mock:draft, mock:review).
No API credentials are required.

Run with:
    poetry run pytest tests/e2e/test_issue_workflow_mock.py -v -m e2e
"""

import os
import time
from pathlib import Path
from typing import Any

import pytest

from tests.e2e.conftest import API_KEY_ENV_VARS, run_workflow_to_completion


# ------------------------------------------------------------------
# Expected nodes in the issue workflow graph path.
# Issue workflow skips: N0b (codebase analysis), N1.5 (mechanical),
# N1b (test plan) — those are LLD-only.
# Human gates (N2, N4) are skipped when gates=False.
# ------------------------------------------------------------------
EXPECTED_ISSUE_NODES = [
    "N0_load_input",
    "N1_generate_draft",
    "N3_review",
    "N5_finalize",
]


@pytest.mark.e2e
@pytest.mark.timeout(120)
def test_issue_workflow_mock_completes_successfully(
    issue_workspace: Path,
    issue_workflow_config: dict,
) -> None:
    """E2E: Issue workflow runs to completion in mock mode. (REQ-1)

    T010: Verifies the graph executes nodes, returns with no exceptions,
    and exit status is "success".
    """
    result = run_workflow_to_completion(
        config=issue_workflow_config,
        workspace=issue_workspace,
    )

    assert result["exit_status"] == "success", (
        f"Workflow failed with error: {result['final_state'].get('error_message', 'unknown')}"
    )
    assert len(result["nodes_visited"]) > 0, "No nodes were visited"


@pytest.mark.e2e
@pytest.mark.timeout(120)
def test_issue_workflow_mock_no_api_credentials_required(
    issue_workspace: Path,
    issue_workflow_config: dict,
    monkeypatch: pytest.MonkeyPatch,
    api_call_tracker: list,
) -> None:
    """E2E: Issue workflow completes without API credentials. (REQ-2)

    T020: Strips all known API key env vars, runs the workflow, and
    verifies it completes successfully with zero real API calls.
    """
    for env_var in API_KEY_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)

    result = run_workflow_to_completion(
        config=issue_workflow_config,
        workspace=issue_workspace,
    )

    assert result["exit_status"] == "success", (
        f"Workflow failed without API credentials: "
        f"{result['final_state'].get('error_message', 'unknown')}"
    )
    assert result["api_calls_made"] == 0, (
        f"Expected 0 API calls in mock mode, got {result['api_calls_made']}"
    )


@pytest.mark.e2e
@pytest.mark.timeout(120)
def test_issue_workflow_mock_uses_auto_mode(
    issue_workspace: Path,
    issue_workflow_config: dict,
) -> None:
    """E2E: Issue workflow in auto mode requires no human interaction. (REQ-3)

    T030: Verifies the workflow completes without hitting human gate nodes.
    """
    result = run_workflow_to_completion(
        config=issue_workflow_config,
        workspace=issue_workspace,
    )

    assert result["exit_status"] == "success", (
        f"Workflow did not complete: {result['final_state'].get('error_message', 'unknown')}"
    )

    # Human gates should NOT be visited when gates=False
    visited_set = set(result["nodes_visited"])
    assert "N2_human_gate_draft" not in visited_set, (
        "Human gate N2 was visited despite gates_draft=False"
    )
    assert "N4_human_gate_verdict" not in visited_set, (
        "Human gate N4 was visited despite gates_verdict=False"
    )


@pytest.mark.e2e
@pytest.mark.timeout(120)
def test_issue_workflow_mock_visits_expected_nodes(
    issue_workspace: Path,
    issue_workflow_config: dict,
) -> None:
    """E2E: All expected issue workflow nodes are visited. (REQ-4)

    T040: Checks that the core issue workflow nodes were visited.
    """
    result = run_workflow_to_completion(
        config=issue_workflow_config,
        workspace=issue_workspace,
    )

    assert result["exit_status"] == "success", (
        f"Workflow failed: {result['final_state'].get('error_message', 'unknown')}"
    )

    visited_set = set(result["nodes_visited"])

    for node in EXPECTED_ISSUE_NODES:
        assert node in visited_set, (
            f"Expected node '{node}' not visited. Nodes visited: {result['nodes_visited']}"
        )

    # LLD-only nodes should NOT be visited
    assert "N0b_analyze_codebase" not in visited_set, (
        "N0b (LLD-only) was visited in issue workflow"
    )


@pytest.mark.e2e
@pytest.mark.timeout(120)
def test_issue_workflow_mock_state_transitions(
    issue_workspace: Path,
    issue_workflow_config: dict,
) -> None:
    """E2E: Issue workflow starts at N0 and visits multiple nodes. (REQ-4)

    T050: Verifies the node visit order starts with N0_load_input.
    """
    result = run_workflow_to_completion(
        config=issue_workflow_config,
        workspace=issue_workspace,
    )

    assert result["exit_status"] == "success", (
        f"Workflow failed: {result['final_state'].get('error_message', 'unknown')}"
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
def test_issue_workflow_mock_produces_final_state(
    issue_workspace: Path,
    issue_workflow_config: dict,
) -> None:
    """E2E: Issue workflow produces a non-empty final state. (REQ-5)

    T060: Checks that the final state dict is non-empty.
    """
    result = run_workflow_to_completion(
        config=issue_workflow_config,
        workspace=issue_workspace,
    )

    assert result["exit_status"] == "success", (
        f"Workflow failed: {result['final_state'].get('error_message', 'unknown')}"
    )

    final_state = result["final_state"]
    assert isinstance(final_state, dict), "Final state should be a dict"
    assert len(final_state) > 0, "Final state should not be empty"


@pytest.mark.e2e
@pytest.mark.timeout(120)
def test_issue_workflow_mock_idempotent_rerun(
    issue_workspace: Path,
    issue_workflow_config: dict,
    tmp_path: Path,
) -> None:
    """E2E: Running the issue workflow twice produces consistent results. (REQ-6)

    T070: Executes the workflow twice and verifies identical node visit order.
    """
    result_1 = run_workflow_to_completion(
        config=issue_workflow_config,
        workspace=issue_workspace,
    )

    assert result_1["exit_status"] == "success", (
        f"First run failed: {result_1['final_state'].get('error_message', 'unknown')}"
    )

    # Second run — create a fresh workspace
    workspace_2 = tmp_path / "run2"
    workspace_2.mkdir()
    for subdir in ["docs/lineage/active", "data", "logs"]:
        (workspace_2 / subdir).mkdir(parents=True, exist_ok=True)

    # Copy brief file to new workspace
    brief_dest = workspace_2 / "mock_brief.md"
    brief_src = Path(issue_workflow_config["brief_file"])
    brief_dest.write_text(brief_src.read_text(encoding="utf-8"), encoding="utf-8")

    config_2 = dict(issue_workflow_config)
    config_2["target_repo"] = str(workspace_2)
    config_2["brief_file"] = str(brief_dest)

    result_2 = run_workflow_to_completion(
        config=config_2,
        workspace=workspace_2,
    )

    assert result_2["exit_status"] == "success", (
        f"Second run failed: {result_2['final_state'].get('error_message', 'unknown')}"
    )

    assert result_1["nodes_visited"] == result_2["nodes_visited"], (
        f"Node visit order differs:\n"
        f"  Run 1: {result_1['nodes_visited']}\n"
        f"  Run 2: {result_2['nodes_visited']}"
    )


@pytest.mark.e2e
@pytest.mark.timeout(120)
def test_issue_workflow_mock_ci_compatible(
    issue_workspace: Path,
    issue_workflow_config: dict,
) -> None:
    """E2E: Issue workflow completes within CI time budget. (REQ-8, REQ-9)

    T080: Measures wall-clock time and asserts it stays within budget.
    """
    start = time.monotonic()

    result = run_workflow_to_completion(
        config=issue_workflow_config,
        workspace=issue_workspace,
    )

    elapsed = time.monotonic() - start

    assert result["exit_status"] == "success", (
        f"Workflow did not complete: {result['final_state'].get('error_message', 'unknown')}"
    )
    assert elapsed < 30, (
        f"Workflow took {elapsed:.1f}s, exceeding 30s CI budget"
    )


@pytest.mark.e2e
@pytest.mark.timeout(120)
def test_issue_workflow_mock_workspace_isolation(
    issue_workspace: Path,
    issue_workflow_config: dict,
    tmp_path: Path,
) -> None:
    """E2E: Issue workflow writes no files outside its workspace. (REQ-10)

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

    result = run_workflow_to_completion(
        config=issue_workflow_config,
        workspace=issue_workspace,
    )

    assert result["exit_status"] == "success", (
        f"Workflow failed: {result['final_state'].get('error_message', 'unknown')}"
    )

    post_cwd_docs = snapshot_dir(cwd / "docs", max_depth=3) if (cwd / "docs").exists() else set()
    new_docs_files = post_cwd_docs - pre_cwd_docs

    assert len(new_docs_files) == 0, (
        f"Workflow created files outside tmp_path in docs/: {new_docs_files}"
    )
