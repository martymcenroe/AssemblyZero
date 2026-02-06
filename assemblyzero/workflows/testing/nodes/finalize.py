"""N7: Finalize node for TDD Testing Workflow.

Generates test report and archives the audit trail:
- Creates docs/reports/active/{issue}-test-report.md
- Saves metadata to audit trail
- Logs workflow completion
- Archives LLD and reports to done/ directories on success
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from assemblyzero.workflows.testing.audit import (
    TestReportMetadata,
    generate_test_report,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    parse_pytest_output,
    save_audit_file,
    save_test_report_metadata,
)
from assemblyzero.workflows.testing.state import TestingWorkflowState

logger = logging.getLogger(__name__)


def archive_file_to_done(active_path: Path) -> Path | None:
    """
    Move a file from active/ to done/ directory.
    
    Args:
        active_path: Path to file in active/ directory
        
    Returns:
        The new path if successful, None if skipped or failed
    """
    try:
        # Verify the file exists
        if not active_path.exists():
            logger.warning(f"File not found for archival: {active_path}")
            return None
        
        # Verify it's in an active/ directory
        if "active" not in str(active_path):
            logger.info(f"File not in active/ directory, skipping archival: {active_path}")
            return None
        
        # Construct the done/ path
        done_path = Path(str(active_path).replace("/active/", "/done/").replace("\\active\\", "\\done\\"))
        
        # Create done/ directory if it doesn't exist
        done_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Handle name conflicts by appending timestamp
        if done_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            stem = done_path.stem
            suffix = done_path.suffix
            done_path = done_path.parent / f"{stem}-{timestamp}{suffix}"
        
        # Move the file
        active_path.rename(done_path)
        logger.info(f"Archived {active_path.name} to {done_path}")
        
        return done_path
        
    except OSError as e:
        logger.error(f"Failed to archive {active_path}: {e}")
        return None


def _archive_workflow_artifacts(state: TestingWorkflowState) -> dict[str, list[str]]:
    """
    Archive LLD and report files from active/ to done/ directories.
    
    Args:
        state: Current workflow state
        
    Returns:
        Dict with 'archived' and 'skipped' lists of file paths
    """
    archived = []
    skipped = []
    
    # Check if workflow was successful
    workflow_success = state.get("workflow_success", True)
    if not workflow_success:
        logger.info("Workflow not successful, skipping artifact archival")
        lld_path = state.get("lld_path", "")
        if lld_path:
            skipped.append(lld_path)
        # Collect report paths from individual state fields
        for report_key in ["test_report_path", "implementation_report_path"]:
            report_path = state.get(report_key, "")
            if report_path:
                skipped.append(report_path)
        return {"archived": archived, "skipped": skipped}

    # Archive LLD if present
    lld_path = state.get("lld_path", "")
    if lld_path:
        result = archive_file_to_done(Path(lld_path))
        if result:
            archived.append(str(result))
        else:
            skipped.append(lld_path)

    # Archive reports if present (using individual state fields)
    for report_key in ["test_report_path", "implementation_report_path"]:
        report_path = state.get(report_key, "")
        if report_path:
            result = archive_file_to_done(Path(report_path))
            if result:
                archived.append(str(result))
            else:
                skipped.append(report_path)
    
    return {"archived": archived, "skipped": skipped}


def finalize(state: TestingWorkflowState) -> dict[str, Any]:
    """N7: Generate test report and complete workflow.

    Args:
        state: Current workflow state.

    Returns:
        State updates with report paths.
    """
    print("\n[N7] Finalizing workflow...")

    issue_number = state.get("issue_number", 0)
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()

    # Gather metrics
    test_files = state.get("test_files", [])
    implementation_files = state.get("implementation_files", [])
    coverage_achieved = state.get("coverage_achieved", 0.0)
    coverage_target = state.get("coverage_target", 90)
    iteration_count = state.get("iteration_count", 0)
    lld_path = state.get("lld_path", "")

    # Parse test output for counts
    green_output = state.get("green_phase_output", "")
    parsed = parse_pytest_output(green_output)
    test_count = parsed.get("passed", 0) + parsed.get("failed", 0) + parsed.get("errors", 0)
    passed_count = parsed.get("passed", 0)
    failed_count = parsed.get("failed", 0) + parsed.get("errors", 0)

    # E2E status
    e2e_output = state.get("e2e_output", "")
    e2e_passed = "passed" in e2e_output.lower() and "failed" not in e2e_output.lower()
    if state.get("skip_e2e"):
        e2e_passed = None  # Skipped

    print(f"    Issue: #{issue_number}")
    print(f"    Tests: {passed_count}/{test_count} passed")
    print(f"    Coverage: {coverage_achieved:.1f}%")
    print(f"    Iterations: {iteration_count}")

    # Create metadata
    metadata: TestReportMetadata = {
        "issue_number": issue_number,
        "lld_path": lld_path,
        "completed_at": datetime.now().isoformat(),
        "test_files": test_files,
        "implementation_files": implementation_files,
        "coverage_achieved": coverage_achieved,
        "coverage_target": coverage_target,
        "total_iterations": iteration_count,
        "test_count": test_count,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "e2e_passed": e2e_passed,
    }

    # Generate test report
    report_path = generate_test_report(
        issue_number=issue_number,
        metadata=metadata,
        test_output=green_output,
        repo_root=repo_root,
    )
    print(f"    Test report: {report_path}")

    # Save to audit trail
    audit_dir = Path(state.get("audit_dir", ""))
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_test_report_metadata(audit_dir, file_num, metadata)

        # Save summary
        file_num = next_file_number(audit_dir)
        summary = _generate_summary(metadata)
        save_audit_file(audit_dir, file_num, "summary.md", summary)

    # Archive workflow artifacts (LLD and reports)
    archival_result = _archive_workflow_artifacts(state)
    archived_files = archival_result["archived"]
    
    if archived_files:
        print(f"\n    Archived artifacts:")
        for file_path in archived_files:
            print(f"      - {file_path}")

    # Log workflow completion
    log_workflow_execution(
        target_repo=repo_root,
        issue_number=issue_number,
        workflow_type="testing",
        event="complete",
        details={
            "test_count": test_count,
            "passed_count": passed_count,
            "coverage": coverage_achieved,
            "iterations": iteration_count,
            "report_path": str(report_path),
            "archived_files": archived_files,
        },
    )

    print(f"\n    Testing workflow COMPLETE for issue #{issue_number}!")
    print(f"    Report: {report_path}")

    return {
        "test_report_path": str(report_path),
        "archived_files": archived_files,
        "error_message": "",
    }


def _generate_summary(metadata: TestReportMetadata) -> str:
    """Generate a summary markdown for the audit trail.

    Args:
        metadata: Test report metadata.

    Returns:
        Summary markdown string.
    """
    e2e_status = "Passed" if metadata["e2e_passed"] else (
        "Skipped" if metadata["e2e_passed"] is None else "Failed"
    )

    return f"""# Testing Workflow Summary

## Issue #{metadata["issue_number"]}

**Completed:** {metadata["completed_at"]}

## Results

| Metric | Value |
|--------|-------|
| Total Tests | {metadata["test_count"]} |
| Passed | {metadata["passed_count"]} |
| Failed | {metadata["failed_count"]} |
| Coverage | {metadata["coverage_achieved"]:.1f}% |
| Target | {metadata["coverage_target"]}% |
| E2E Status | {e2e_status} |
| Iterations | {metadata["total_iterations"]} |

## Files

### Test Files
{chr(10).join(f"- {f}" for f in metadata["test_files"])}

### Implementation Files
{chr(10).join(f"- {f}" for f in metadata["implementation_files"])}

## LLD

{metadata["lld_path"]}

---

Generated by AssemblyZero TDD Testing Workflow
"""