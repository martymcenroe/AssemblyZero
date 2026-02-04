# Implementation Request

## Context

You are implementing code for Issue #141 using TDD.
This is iteration 2 of the implementation.

## Requirements

The tests have been scaffolded and need implementation code to pass.

### LLD Summary

# 141 - Fix: Implementation Workflow Should Archive LLD and Reports to done/ on Completion

<!-- Template Metadata
Last Updated: 2025-01-10
Updated By: LLD Workflow
Update Reason: Initial draft for Issue #141
-->

## 1. Context & Goal
* **Issue:** #141
* **Objective:** Automatically archive LLD and report files from `active/` to `done/` directories when the implementation workflow completes successfully.
* **Status:** Draft
* **Related Issues:** #139 (Rename workflows/testing/ to workflows/implementation/), #140 (Inhume deprecated workflows)

### Open Questions

- [x] Should archival happen on any completion or only on success? → Only on success (failed workflows may need rework)
- [x] What happens if `done/` directory doesn't exist? → Create it automatically
- [x] Should we handle the case where LLD doesn't exist (manual implementations)? → Yes, gracefully skip with log message

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `agentos/workflows/testing/nodes/finalize.py` | Modify | Add archival logic for LLD and reports |
| `tests/workflows/testing/nodes/test_finalize.py` | Modify | Add tests for archival functionality |

### 2.2 Dependencies

*No new dependencies required.*

```toml
# pyproject.toml additions (if any)
# None
```

### 2.3 Data Structures

```python
# No new data structures - uses existing TestingWorkflowState
# Relevant existing fields:
class TestingWorkflowState(TypedDict):
    lld_path: str  # Path to the active LLD file
    report_paths: list[str]  # Paths to generated reports in active/
    issue_number: int  # For logging purposes
```

### 2.4 Function Signatures

```python
# New helper function in finalize.py
def archive_file_to_done(active_path: Path) -> Path | None:
    """
    Move a file from active/ to done/ directory.
    
    Returns the new path if successful, No...

### Test Scenarios

- **test_010**: Happy path - LLD archived | integration | State with valid LLD path in active/ | LLD moved to done/, path returned | File exists in done/, not in active/, log contains success message
  - Requirement: 
  - Type: integration

- **test_020**: Happy path - Reports archived | integration | State with report paths in active/ | Reports moved to done/ | Files exist in done/, not in active/, log contains success message
  - Requirement: 
  - Type: integration

- **test_030**: LLD not found | integration | State with non-existent LLD path | Warning logged, None returned | No exception, log contains warning
  - Requirement: 
  - Type: integration

- **test_040**: LLD not in active/ | integration | State with LLD in arbitrary path | Skip archival, None returned | File unchanged, log indicates skip
  - Requirement: 
  - Type: integration

- **test_050**: done/ doesn't exist | integration | Valid LLD, no done/ directory | done/ created, LLD moved | Directory created, file moved
  - Requirement: 
  - Type: integration

- **test_060**: Destination file exists | integration | LLD exists in both active/ and done/ | Append timestamp to new name | No overwrite, both files preserved
  - Requirement: 
  - Type: integration

- **test_070**: Empty state | unit | State with no paths | Graceful no-op | No exception, empty archival list
  - Requirement: 
  - Type: unit

- **test_080**: Mixed success | integration | Some files exist, some don't | Archive existing, log missing | Partial archival succeeds
  - Requirement: 
  - Type: integration

- **test_090**: Workflow failed - no archival | integration | State with workflow_success=False, valid LLD path | No files moved, skip logged | Files remain in active/, log indicates skip
  - Requirement: 
  - Type: integration

- **test_100**: Exception during file rename | unit | Valid LLD, mock rename to raise OSError | None returned, error logged | No exception propagated, log contains error message
  - Requirement: 
  - Type: unit

- **test_110**: Generate summary | unit | Complete TestReportMetadata dict | Markdown summary string | Contains issue number, coverage %, file lists, E2E status
  - Requirement: 
  - Type: unit

- **test_120**: LLD archival fails via wrapper | unit | State with LLD path not in active/ | Skipped list includes LLD path | archived=[], skipped=[lld_path]
  - Requirement: 
  - Type: unit

- **test_130**: Impl report archival fails | unit | State with impl_report path not in active/ | Skipped list includes impl report | archived=[], skipped=[impl_path]
  - Requirement: 
  - Type: unit

- **test_140**: E2E evaluation (skip_e2e=False) | integration | State with skip_e2e=False, e2e_output="passed" | E2E passed evaluated from output | finalize completes, e2e logic exercised
  - Requirement: 
  - Type: integration

- **test_150**: Successful workflow with archival | integration | State with workflow_success=True (default), valid LLD | LLD archived, archival printed | archived_files populated, LLD moved to done/
  - Requirement: 
  - Type: integration

### Test File: C:\Users\mcwiz\Projects\AgentOS\tests\test_issue_141.py

```python
"""Test file for Issue #141.

Generated by AgentOS TDD Testing Workflow.
Tests for archival of LLD and report files from active/ to done/.
"""

import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentos.workflows.testing.audit import TestReportMetadata
from agentos.workflows.testing.nodes.finalize import (
    _archive_workflow_artifacts,
    _generate_summary,
    archive_file_to_done,
    finalize,
)
from agentos.workflows.testing.state import TestingWorkflowState


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary repository structure with active/ and done/ directories."""
    active_dir = tmp_path / "docs" / "LLDs" / "active"
    done_dir = tmp_path / "docs" / "LLDs" / "done"
    reports_active = tmp_path / "docs" / "reports" / "active"
    reports_done = tmp_path / "docs" / "reports" / "done"
    
    active_dir.mkdir(parents=True)
    done_dir.mkdir(parents=True)
    reports_active.mkdir(parents=True)
    reports_done.mkdir(parents=True)
    
    return tmp_path


@pytest.fixture
def sample_metadata() -> TestReportMetadata:
    """Sample TestReportMetadata for testing."""
    return {
        "issue_number": 141,
        "lld_path": "docs/LLDs/active/141-fix.md",
        "completed_at": "2025-01-15T10:30:00",
        "test_files": ["tests/test_foo.py", "tests/test_bar.py"],
        "implementation_files": ["agentos/foo.py", "agentos/bar.py"],
        "coverage_achieved": 92.5,
        "coverage_target": 90,
        "total_iterations": 3,
        "test_count": 15,
        "passed_count": 15,
        "failed_count": 0,
        "e2e_passed": True,
    }


# Unit Tests
# -----------

def test_070():
    """
    Empty state | unit | State with no paths | Graceful no-op | No
    exception, empty archival list
    """
    # TDD: Arrange
    state: TestingWorkflowState = {
        "issue_number": 141,
        "lld_path": "",
        "report_paths": [],
    }  # type: ignore

    # TDD: Act
    result = _archive_workflow_artifacts(state)

    # TDD: Assert
    assert result["archived"] == []
    assert result["skipped"] == []


def test_100(caplog):
    """
    Exception during file rename | unit | Valid LLD, mock rename to raise
    OSError | None returned, error logged | No exception propagated, log
    contains error message
    """
    # TDD: Arrange
    test_file = Path("/fake/docs/LLDs/active/141-test.md")
    
    with caplog.at_level(logging.ERROR):
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "rename", side_effect=OSError("Permission denied")):
                # TDD: Act
                result = archive_file_to_done(test_file)

    # TDD: Assert
    assert result is None
    assert "Failed to archive" in caplog.text
    assert "Permission denied" in caplog.text


def test_110(sample_metadata):
    """
    Generate summary | unit | Complete TestReportMetadata dict | Markdown
    summary string | Contains issue number, coverage %, file lists, E2E
    status
    """
    # TDD: Arrange
    # sample_metadata fixture provides complete metadata

    # TDD: Act
    summary = _generate_summary(sample_metadata)

    # TDD: Assert
    assert "# Testing Workflow Summary" in summary
    assert "## Issue #141" in summary
    assert "92.5%" in summary
    assert "test_foo.py" in summary
    assert "agentos/foo.py" in summary
    assert "E2E Status | Passed" in summary
    assert "Total Tests | 15" in summary


def test_120():
    """
    LLD archival fails via wrapper | unit | State with LLD path not in
    active/ | Skipped list includes LLD path | archived=[],
    skipped=[lld_path]
    """
    # TDD: Arrange
    state: TestingWorkflowState = {
        "issue_number": 141,
        "lld_path": "/some/other/path/141-test.md",
        "report_paths": [],
    }  # type: ignore

    # TDD: Act
    with patch.object(Path, "exists", return_value=True):
        result = _archive_workflow_artifacts(state)

    # TDD: Assert
    assert result["archived"] == []
    assert "/some/other/path/141-test.md" in result["skipped"]


def test_130():
    """
    Impl report archival fails | unit | State with impl_report path not
    in active/ | Skipped list includes impl report | archived=[],
    skipped=[impl_path]
    """
    # TDD: Arrange
    impl_report_path = "/some/other/path/141-impl.md"
    state: TestingWorkflowState = {
        "issue_number": 141,
        "lld_path": "",
        "report_paths": [impl_report_path],
    }  # type: ignore

    # TDD: Act
    with patch.object(Path, "exists", return_value=True):
        result = _archive_workflow_artifacts(state)

    # TDD: Assert
    assert result["archived"] == []
    assert impl_report_path in result["skipped"]


# Integration Tests
# -----------------

def test_010(temp_repo, caplog):
    """
    Happy path - LLD archived | integration | State with valid LLD path
    in active/ | LLD moved to done/, path returned | File exists in done/,
    not in active/, log contains success message
    """
    # TDD: Arrange
    active_lld = temp_repo / "docs" / "LLDs" / "active" / "141-test.md"
    active_lld.write_text("# LLD Content")
    
    with caplog.at_level(logging.INFO):
        # TDD: Act
        result = archive_file_to_done(active_lld)

    # TDD: Assert
    assert result is not None
    done_lld = temp_repo / "docs" / "LLDs" / "done" / "141-test.md"
    assert done_lld.exists()
    assert not active_lld.exists()
    assert "Archived 141-test.md" in caplog.text


def test_020(temp_repo, caplog):
    """
    Happy path - Reports archived | integration | State with report paths
    in active/ | Reports moved to done/ | Files exist in done/, not in
    active_, log contains success message
    """
    # TDD: Arrange
    report1 = temp_repo / "docs" / "reports" / "active" / "141-impl.md"
    report2 = temp_repo / "docs" / "reports" / "active" / "141-test.md"
    report1.write_text("# Implementation Report")
    report2.write_text("# Test Report")
    
    state: TestingWorkflowState = {
        "issue_number": 141,
        "lld_path": "",
        "report_paths": [str(report1), str(report2)],
    }  # type: ignore
    
    with caplog.at_level(logging.INFO):
        # TDD: Act
        result = _archive_workflow_artifacts(state)

    # TDD: Assert
    assert len(result["archived"]) == 2
    done_report1 = temp_repo / "docs" / "reports" / "done" / "141-impl.md"
    done_report2 = temp_repo / "docs" / "reports" / "done" / "141-test.md"
    assert done_report1.exists()
    assert done_report2.exists()
    assert not report1.exists()
    assert not report2.exists()
    assert "Archived 141-impl.md" in caplog.text


def test_030(caplog):
    """
    LLD not found | integration | State with non-existent LLD path |
    Warning logged, None returned | No exception, log contains warning
    """
    # TDD: Arrange
    non_existent = Path("/fake/path/docs/LLDs/active/999-missing.md")
    
    with caplog.at_level(logging.WARNING):
        # TDD: Act
        result = archive_file_to_done(non_existent)

    # TDD: Assert
    assert result is None
    assert "File not found for archival" in caplog.text


def test_040(temp_repo, caplog):
    """
    LLD not in active/ | integration | State with LLD in arbitrary path |
    Skip archival, None returned | File unchanged, log indicates skip
    """
    # TDD: Arrange
    arbitrary_path = temp_repo / "some" / "other" / "path" / "141-test.md"
    arbitrary_path.parent.mkdir(parents=True)
    arbitrary_path.write_text("# LLD Content")
    
    with caplog.at_level(logging.INFO):
        # TDD: Act
        result = archive_file_to_done(arbitrary_path)

    # TDD: Assert
    assert result is None
    assert arbitrary_path.exists()  # File unchanged
    assert "not in active/ directory, skipping archival" in caplog.text


def test_050(temp_repo):
    """
    done/ doesn't exist | integration | Valid LLD, no done/ directory |
    done/ created, LLD moved | Directory created, file moved
    """
    # TDD: Arrange
    # Create active/ but remove done/
    active_lld = temp_repo / "docs" / "LLDs" / "active" / "141-test.md"
    done_dir = temp_repo / "docs" / "LLDs" / "done"
    active_lld.write_text("# LLD Content")
    
    # Remove done directory to test creation
    import shutil
    if done_dir.exists():
        shutil.rmtree(done_dir)
    
    # TDD: Act
    result = archive_file_to_done(active_lld)

    # TDD: Assert
    assert result is not None
    assert done_dir.exists()  # Directory was created
    done_lld = temp_repo / "docs" / "LLDs" / "done" / "141-test.md"
    assert done_lld.exists()
    assert not active_lld.exists()


def test_060(temp_repo):
    """
    Destination file exists | integration | LLD exists in both active/
    and done/ | Append timestamp to new name | No overwrite, both files
    preserved
    """
    # TDD: Arrange
    active_lld = temp_repo / "docs" / "LLDs" / "active" / "141-test.md"
    done_lld = temp_repo / "docs" / "LLDs" / "done" / "141-test.md"
    
    active_lld.write_text("# New LLD Content")
    done_lld.write_text("# Old LLD Content")
    
    # TDD: Act
    result = archive_file_to_done(active_lld)

    # TDD: Assert
    assert result is not None
    assert result != done_lld  # Different path with timestamp
    assert done_lld.exists()  # Original preserved
    assert done_lld.read_text() == "# Old LLD Content"
    assert result.exists()  # New file created
    assert result.read_text() == "# New LLD Content"
    # Verify timestamp pattern in filename
    assert "141-test-" in str(result)


def test_080(temp_repo, caplog):
    """
    Mixed success | integration | Some files exist, some don't | Archive
    existing, log missing | Partial archival succeeds
    """
    # TDD: Arrange
    existing_file = temp_repo / "docs" / "reports" / "active" / "141-impl.md"
    existing_file.write_text("# Report")
    
    missing_file = str(temp_repo / "docs" / "reports" / "active" / "999-missing.md")
    
    state: TestingWorkflowState = {
        "issue_number": 141,
        "lld_path": "",
        "report_paths": [str(existing_file), missing_file],
    }  # type: ignore
    
    with caplog.at_level(logging.WARNING):
        # TDD: Act
        result = _archive_workflow_artifacts(state)

    # TDD: Assert
    assert len(result["archived"]) == 1
    assert len(result["skipped"]) == 1
    assert "File not found for archival" in caplog.text


def test_090(temp_repo):
    """
    Workflow failed - no archival | integration | State with
    workflow_success=False, valid LLD path | No files moved, skip logged |
    Files remain in active/, log indicates skip
    """
    # TDD: Arrange
    active_lld = temp_repo / "docs" / "LLDs" / "active" / "141-test.md"
    active_lld.write_text("# LLD Content")
    
    state: TestingWorkflowState = {
        "issue_number": 141,
        "lld_path": str(active_lld),
        "report_paths": [],
        "workflow_success": False,
    }  # type: ignore

    # TDD: Act
    result = _archive_workflow_artifacts(state)

    # TDD: Assert
    assert result["archived"] == []
    assert str(active_lld) in result["skipped"]
    assert active_lld.exists()  # File not moved


def test_140(temp_repo):
    """
    E2E evaluation (skip_e2e=False) | integration | State with
    skip_e2e=False, e2e_output="passed" | E2E passed evaluated from output
    | finalize completes, e2e logic exercised
    """
    # TDD: Arrange
    audit_dir = temp_repo / "docs" / "lineage" / "active" / "141-testing"
    audit_dir.mkdir(parents=True)
    
    state: TestingWorkflowState = {
        "issue_number": 141,
        "repo_root": str(temp_repo),
        "audit_dir": str(audit_dir),
        "lld_path": "",
        "report_paths": [],
        "skip_e2e": False,
        "e2e_output": "All tests passed successfully",
        "test_files": ["tests/test_foo.py"],
        "implementation_files": ["agentos/foo.py"],
        "coverage_achieved": 90.0,
        "coverage_target": 90,
        "iteration_count": 1,
        "green_phase_output": "15 passed in 1.23s",
    }  # type: ignore

    # TDD: Act
    with patch("agentos.workflows.testing.nodes.finalize.generate_test_report") as mock_report:
        mock_report.return_value = temp_repo / "docs" / "reports" / "active" / "141-test-report.md"
        result = finalize(state)

    # TDD: Assert
    assert "error_message" in result
    assert result["error_message"] == ""


def test_150(temp_repo):
    """
    Successful workflow with archival | integration | State with
    workflow_success=True (default), valid LLD | LLD archived, archival
    printed | archived_files populated, LLD moved to done/
    """
    # TDD: Arrange
    active_lld = temp_repo / "docs" / "LLDs" / "active" / "141-test.md"
    active_lld.write_text("# LLD Content")
    audit_dir = temp_repo / "docs" / "lineage" / "active" / "141-testing"
    audit_dir.mkdir(parents=True)
    
    state: TestingWorkflowState = {
        "issue_number": 141,
        "repo_root": str(temp_repo),
        "audit_dir": str(audit_dir),
        "lld_path": str(active_lld),
        "report_paths": [],
        "workflow_success": True,
        "test_files": ["tests/test_foo.py"],
        "implementation_files": ["agentos/foo.py"],
        "coverage_achieved": 92.0,
        "coverage_target": 90,
        "iteration_count": 2,
        "green_phase_output": "10 passed in 0.5s",
        "skip_e2e": True,
    }  # type: ignore

    # TDD: Act
    with patch("agentos.workflows.testing.nodes.finalize.generate_test_report") as mock_report:
        mock_report.return_value = temp_repo / "docs" / "reports" / "active" / "141-test-report.md"
        result = finalize(state)

    # TDD: Assert
    assert "archived_files" in result
    assert len(result["archived_files"]) == 1
    done_lld = temp_repo / "docs" / "LLDs" / "done" / "141-test.md"
    assert done_lld.exists()
    assert not active_lld.exists()
```

### Source Files to Modify

These are the existing files you need to modify:

#### agentos/workflows/testing/nodes/finalize.py (Modify)

Add archival logic for LLD and reports

```python
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

from agentos.workflows.testing.audit import (
    TestReportMetadata,
    generate_test_report,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    parse_pytest_output,
    save_audit_file,
    save_test_report_metadata,
)
from agentos.workflows.testing.state import TestingWorkflowState

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
        report_paths = state.get("report_paths", [])
        skipped.extend(report_paths)
        return {"archived": archived, "skipped": skipped}
    
    # Archive LLD if present
    lld_path = state.get("lld_path", "")
    if lld_path:
        result = archive_file_to_done(Path(lld_path))
        if result:
            archived.append(str(result))
        else:
            skipped.append(lld_path)
    
    # Archive reports if present
    report_paths = state.get("report_paths", [])
    for report_path in report_paths:
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

Generated by AgentOS TDD Testing Workflow
"""
```

### Previous Test Run (FAILED)

The previous implementation attempt failed. Here's the test output:

```
\workflows\testing\nodes\document.py                140    126    10%   41-61, 73-84, 96-103, 115-116, 128-141, 153-166, 179-214, 226-360
agentos\workflows\testing\nodes\e2e_validation.py           93     80    14%   44-88, 109, 130, 142-283, 293-311
agentos\workflows\testing\nodes\finalize.py                100      0   100%
agentos\workflows\testing\nodes\implement_code.py          208    194     7%   29-45, 57-184, 197-288, 306-401, 417-435, 447-536, 545-610
agentos\workflows\testing\nodes\load_lld.py                204    185     9%   39-60, 77-88, 105-135, 152-254, 259-260, 265-277, 282-293, 298-314, 331-343, 357-397, 409-513, 531-602
agentos\workflows\testing\nodes\review_test_plan.py        139    122    12%   49-63, 75-83, 100-119, 137-143, 148, 208-256, 268-382, 400-413, 426-441, 449-496
agentos\workflows\testing\nodes\scaffold_tests.py          157    145     8%   39-127, 145-215, 220-238, 257-262, 274-330, 339-372
agentos\workflows\testing\nodes\verify_phases.py           160    149     7%   42-78, 100-198, 219-404, 415-439, 449-497
agentos\workflows\testing\state.py                           9      0   100%
agentos\workflows\testing\templates\__init__.py              5      0   100%
agentos\workflows\testing\templates\cp_docs.py              73     65    11%   23-33, 45-60, 72-83, 105-189, 211-296
agentos\workflows\testing\templates\lessons.py             115    107     7%   31-161, 174-199, 215-231, 243-257, 279-304
agentos\workflows\testing\templates\runbook.py              94     86     9%   22-37, 49-59, 71-81, 93-103, 125-259
agentos\workflows\testing\templates\wiki_page.py            74     67     9%   22-32, 44-48, 60-72, 92-152, 165-207
--------------------------------------------------------------------------------------
TOTAL                                                     5273   4930     7%
FAIL Required test coverage of 95% not reached. Total coverage: 6.50%
======================= 15 passed, 10 warnings in 0.71s =======================


```

Please fix the issues and provide updated implementation.

## Instructions

1. Generate implementation code that makes all tests pass
2. Follow the patterns established in the codebase
3. Ensure proper error handling
4. Add type hints where appropriate
5. Keep the implementation minimal - only what's needed to pass tests

## Output Format (CRITICAL - MUST FOLLOW EXACTLY)

For EACH file you need to create or modify, provide a code block with this EXACT format:

```python
# File: path/to/implementation.py

def function_name():
    ...
```

**Rules:**
- The `# File: path/to/file` comment MUST be the FIRST line inside the code block
- Use the language-appropriate code fence (```python, ```gitignore, ```yaml, etc.)
- Path must be relative to repository root (e.g., `src/module/file.py`)
- Do NOT include "(append)" or other annotations in the path
- Provide complete file contents, not patches or diffs

**Example for .gitignore:**
```gitignore
# File: .gitignore

# Existing patterns...
*.pyc
__pycache__/

# New pattern
.agentos/
```

If multiple files are needed, provide each in a separate code block with its own `# File:` header.
