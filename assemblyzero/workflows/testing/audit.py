"""Audit trail utilities for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization

Provides functions for:
- Sequential file numbering (001, 002, 003...)
- Saving audit files (lld, test-plan, verdict, tests, etc.)
- Test report generation
- Workflow audit logging
"""

import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

# Module logger for GUARD messages
logger = logging.getLogger(__name__)


class TestReportMetadata(TypedDict):
    """Schema for test-report.json metadata file."""

    issue_number: int
    lld_path: str
    completed_at: str  # ISO8601
    test_files: list[str]
    implementation_files: list[str]
    coverage_achieved: float
    coverage_target: int
    total_iterations: int
    test_count: int
    passed_count: int
    failed_count: int
    e2e_passed: bool


# Base directories relative to repo root
AUDIT_ACTIVE_DIR = Path("docs/lineage/active")
REPORTS_ACTIVE_DIR = Path("docs/reports/active")
WORKFLOW_AUDIT_FILE = Path("docs/lineage/workflow-audit.jsonl")


def get_repo_root() -> Path:
    """Detect repository root via git rev-parse.

    Returns:
        Path to repository root.

    Raises:
        RuntimeError: If not in a git repository.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Not in a git repository: {result.stderr.strip()}")
    return Path(result.stdout.strip())


def create_testing_audit_dir(issue_number: int, repo_root: Path | None = None) -> Path:
    """Create audit directory for this testing workflow.

    Args:
        issue_number: GitHub issue number.
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        Path to created directory (docs/lineage/active/{issue_number}-testing/).
    """
    root = repo_root or get_repo_root()
    audit_dir = root / AUDIT_ACTIVE_DIR / f"{issue_number}-testing"

    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir


def next_file_number(audit_dir: Path) -> int:
    """Get next sequential file number.

    Scans audit_dir for NNN-*.* files and returns max + 1.

    Args:
        audit_dir: Path to the audit directory.

    Returns:
        Next file number (starts at 1 if directory is empty).
    """
    if not audit_dir.exists():
        return 1

    max_num = 0
    for f in audit_dir.iterdir():
        if f.is_file():
            match = re.match(r"^(\d{3})-", f.name)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)

    return max_num + 1


def save_audit_file(
    audit_dir: Path,
    number: int,
    suffix: str,
    content: str,
) -> Path:
    """Save an audit file with sequential numbering.

    Args:
        audit_dir: Path to the audit directory.
        number: File number (1-999).
        suffix: File suffix (e.g., "lld.md", "test-plan.md", "verdict.md").
        content: File content.

    Returns:
        Path to the saved file.
    """
    filename = f"{number:03d}-{suffix}"
    file_path = audit_dir / filename
    file_path.write_text(content, encoding="utf-8")
    return file_path


def save_test_report_metadata(
    audit_dir: Path,
    number: int,
    metadata: TestReportMetadata,
) -> Path:
    """Save test report metadata file.

    Args:
        audit_dir: Path to the audit directory.
        number: File number.
        metadata: Test report metadata.

    Returns:
        Path to the saved test-report.json file.
    """
    filename = f"{number:03d}-test-report.json"
    file_path = audit_dir / filename
    file_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return file_path


def generate_test_report(
    issue_number: int,
    metadata: TestReportMetadata,
    test_output: str,
    repo_root: Path | None = None,
) -> Path:
    """Generate test report markdown file.

    Args:
        issue_number: GitHub issue number.
        metadata: Test report metadata.
        test_output: Raw pytest output.
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        Path to generated report file.
    """
    root = repo_root or get_repo_root()
    reports_dir = root / REPORTS_ACTIVE_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_path = reports_dir / f"{issue_number}-test-report.md"

    # Generate markdown report
    report_content = f"""# Test Report: Issue #{issue_number}

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**LLD:** {metadata["lld_path"]}

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | {metadata["test_count"]} |
| Passed | {metadata["passed_count"]} |
| Failed | {metadata["failed_count"]} |
| Coverage | {metadata["coverage_achieved"]:.1f}% |
| Target | {metadata["coverage_target"]}% |
| E2E Passed | {"Yes" if metadata["e2e_passed"] else "No" if metadata.get("e2e_passed") is not None else "Skipped"} |
| Iterations | {metadata["total_iterations"]} |

## Test Files

{chr(10).join(f"- `{f}`" for f in metadata["test_files"])}

## Implementation Files

{chr(10).join(f"- `{f}`" for f in metadata["implementation_files"])}

## Test Output

```
{test_output[:5000]}{"..." if len(test_output) > 5000 else ""}
```

---

Generated by AssemblyZero Testing Workflow
"""

    report_path.write_text(report_content, encoding="utf-8")
    return report_path


def log_workflow_execution(
    target_repo: Path,
    issue_number: int,
    workflow_type: str,
    event: str,
    details: dict | None = None,
) -> None:
    """Log workflow execution to central audit file.

    Creates a JSONL (JSON Lines) audit trail of all workflow executions.
    This enables post-hoc analysis of workflow runs, failures, and patterns.

    Args:
        target_repo: Path to the target repository.
        issue_number: GitHub issue number being processed.
        workflow_type: Type of workflow ("testing", "lld", "issue").
        event: Event type ("start", "complete", "error", "phase_complete").
        details: Optional dict with additional event details.
    """
    log_file = target_repo / WORKFLOW_AUDIT_FILE

    # Ensure directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workflow_type": workflow_type,
        "issue_number": issue_number,
        "target_repo": str(target_repo),
        "event": event,
    }

    if details:
        entry["details"] = details

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        # Don't fail the workflow if audit logging fails
        logger.warning(f"Failed to write workflow audit log: {e}")


def parse_pytest_output(output: str) -> dict:
    """Parse pytest output to extract test results.

    Args:
        output: Raw pytest output string.

    Returns:
        Dict with passed, failed, error counts and coverage.
    """
    result = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "coverage": 0.0,
        "test_names": [],
    }

    # Parse summary line: "5 passed, 2 failed, 1 error in 1.23s"
    summary_pattern = re.compile(
        r"(\d+)\s+passed|(\d+)\s+failed|(\d+)\s+error|(\d+)\s+skipped"
    )
    for match in summary_pattern.finditer(output):
        if match.group(1):
            result["passed"] = int(match.group(1))
        if match.group(2):
            result["failed"] = int(match.group(2))
        if match.group(3):
            result["errors"] = int(match.group(3))
        if match.group(4):
            result["skipped"] = int(match.group(4))

    # Parse coverage percentage: "TOTAL ... 85%"
    coverage_pattern = re.compile(r"TOTAL\s+\d+\s+\d+\s+(\d+)%")
    match = coverage_pattern.search(output)
    if match:
        result["coverage"] = float(match.group(1))

    # Parse individual test names
    test_pattern = re.compile(r"(test_\w+)\s+(PASSED|FAILED|ERROR|SKIPPED)")
    for match in test_pattern.finditer(output):
        result["test_names"].append({
            "name": match.group(1),
            "status": match.group(2).lower(),
        })

    return result
