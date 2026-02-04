# Implementation Request

## Context

You are implementing code for Issue #141 using TDD.
This is iteration 0 of the implementation.

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
Each test starts with `assert False` - implementation will make them pass.
"""

import pytest


# Fixtures for mocking
@pytest.fixture
def mock_external_service():
    """Mock external service for isolation."""
    # TODO: Implement mock
    yield None


# Integration/E2E fixtures
@pytest.fixture
def test_client():
    """Test client for API calls."""
    # TODO: Implement test client
    yield None


# Unit Tests
# -----------

def test_070():
    """
    Empty state | unit | State with no paths | Graceful no-op | No
    exception, empty archival list
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_070"


def test_100(mock_external_service):
    """
    Exception during file rename | unit | Valid LLD, mock rename to raise
    OSError | None returned, error logged | No exception propagated, log
    contains error message
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_100"


def test_110():
    """
    Generate summary | unit | Complete TestReportMetadata dict | Markdown
    summary string | Contains issue number, coverage %, file lists, E2E
    status
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_110"


def test_120():
    """
    LLD archival fails via wrapper | unit | State with LLD path not in
    active/ | Skipped list includes LLD path | archived=[],
    skipped=[lld_path]
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_120"


def test_130():
    """
    Impl report archival fails | unit | State with impl_report path not
    in active/ | Skipped list includes impl report | archived=[],
    skipped=[impl_path]
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_130"



# Integration Tests
# -----------------

def test_010(test_client):
    """
    Happy path - LLD archived | integration | State with valid LLD path
    in active/ | LLD moved to done/, path returned | File exists in done/,
    not in active/, log contains success message
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_010"


def test_020(test_client):
    """
    Happy path - Reports archived | integration | State with report paths
    in active/ | Reports moved to done/ | Files exist in done/, not in
    active/, log contains success message
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_020"


def test_030(test_client):
    """
    LLD not found | integration | State with non-existent LLD path |
    Warning logged, None returned | No exception, log contains warning
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_030"


def test_040(test_client):
    """
    LLD not in active/ | integration | State with LLD in arbitrary path |
    Skip archival, None returned | File unchanged, log indicates skip
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_040"


def test_050(test_client):
    """
    done/ doesn't exist | integration | Valid LLD, no done/ directory |
    done/ created, LLD moved | Directory created, file moved
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_050"


def test_060(test_client):
    """
    Destination file exists | integration | LLD exists in both active/
    and done/ | Append timestamp to new name | No overwrite, both files
    preserved
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_060"


def test_080(test_client):
    """
    Mixed success | integration | Some files exist, some don't | Archive
    existing, log missing | Partial archival succeeds
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_080"


def test_090(test_client):
    """
    Workflow failed - no archival | integration | State with
    workflow_success=False, valid LLD path | No files moved, skip logged |
    Files remain in active/, log indicates skip
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_090"


def test_140(test_client):
    """
    E2E evaluation (skip_e2e=False) | integration | State with
    skip_e2e=False, e2e_output="passed" | E2E passed evaluated from output
    | finalize completes, e2e logic exercised
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_140"


def test_150(test_client):
    """
    Successful workflow with archival | integration | State with
    workflow_success=True (default), valid LLD | LLD archived, archival
    printed | archived_files populated, LLD moved to done/
    """
    # TDD: Arrange
    # TODO: Set up test data and mocks

    # TDD: Act
    # TODO: Call the function/method under test

    # TDD: Assert
    assert False, "TDD: Implementation pending for test_150"


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
"""

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
        },
    )

    print(f"\n    Testing workflow COMPLETE for issue #{issue_number}!")
    print(f"    Report: {report_path}")

    return {
        "test_report_path": str(report_path),
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
