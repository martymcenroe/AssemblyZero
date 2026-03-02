"""Generate implementation verification reports.

Issue #147: Implementation Completeness Gate (Anti-Stub Detection)
Related: #181 (Implementation Report)

Generates implementation verification reports that include:
- LLD requirement verification table (parsed from Section 3)
- Completeness analysis summary (from AST Layer 1)
- Review materials preparation for Gemini Layer 2 (user-controlled)

Reports are written to docs/reports/active/{issue}-implementation-report.md.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, TypedDict

from assemblyzero.workflows.testing.completeness.ast_analyzer import (
    CompletenessCategory,
    CompletenessIssue,
    CompletenessResult,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Data Structures
# =============================================================================


class RequirementVerification(TypedDict):
    """Single LLD requirement verification status."""

    requirement_id: int
    requirement_text: str
    status: Literal["IMPLEMENTED", "PARTIAL", "MISSING"]
    evidence: str  # File:line or explanation


class ImplementationReport(TypedDict):
    """Full implementation verification report."""

    issue_number: int
    requirements: list[RequirementVerification]
    completeness_result: CompletenessResult
    generated_at: str  # ISO timestamp


class ReviewMaterials(TypedDict):
    """Materials prepared for Gemini semantic review."""

    lld_requirements: list[tuple[int, str]]  # (id, text) pairs
    code_snippets: dict[str, str]  # file_path -> relevant code
    issue_number: int


# =============================================================================
# Requirement Extraction
# =============================================================================


def extract_lld_requirements(lld_path: Path) -> list[tuple[int, str]]:
    """Parse Section 3 requirements from LLD markdown.

    Issue #147, Requirement 10: Extracts numbered requirements from
    the LLD's Section 3 (Requirements) for verification against
    the implementation.

    Handles formats:
    - "1. Requirement text"
    - "1. **Bold requirement** with description"
    - Numbered lists within Section 3

    Args:
        lld_path: Path to the LLD markdown file.

    Returns:
        List of (requirement_id, requirement_text) tuples.
        Returns empty list if file cannot be read or Section 3 not found.
    """
    try:
        content = lld_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.warning("Cannot read LLD file %s: %s", lld_path, e)
        return []

    # Find Section 3 (Requirements)
    # Match patterns: "## 3. Requirements", "## 3 Requirements", "## 3. Requirements\n"
    section_3_pattern = re.compile(
        r"^##\s+3\.?\s+Requirements\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    match = section_3_pattern.search(content)
    if not match:
        logger.warning("Section 3 (Requirements) not found in %s", lld_path)
        return []

    # Extract content from Section 3 until the next section (## N.)
    section_start = match.end()
    next_section_pattern = re.compile(r"^##\s+\d+", re.MULTILINE)
    next_match = next_section_pattern.search(content, section_start)
    if next_match:
        section_content = content[section_start:next_match.start()]
    else:
        section_content = content[section_start:]

    # Parse numbered requirements from the section content
    # Match: "1. Some requirement text" (possibly spanning continuation lines)
    requirement_pattern = re.compile(
        r"^\s*(\d+)\.\s+(.+?)(?=\n\s*\d+\.\s|\n\s*$|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    requirements: list[tuple[int, str]] = []

    for req_match in requirement_pattern.finditer(section_content):
        req_id = int(req_match.group(1))
        req_text = req_match.group(2).strip()
        # Clean up multi-line text: collapse newlines to spaces
        req_text = re.sub(r"\s+", " ", req_text).strip()
        if req_text:
            requirements.append((req_id, req_text))

    return requirements


# =============================================================================
# Review Materials Preparation
# =============================================================================


def prepare_review_materials(
    issue_number: int,
    lld_path: Path,
    implementation_files: list[Path],
) -> ReviewMaterials:
    """Prepare materials for Gemini semantic review submission by user.

    Issue #147, Requirement 13: Prepares structured review materials
    containing LLD requirements and code snippets for the user
    to submit to Gemini for Layer 2 semantic review.

    The user controls Gemini submission per WORKFLOW.md — this
    function only prepares the materials, it does not call Gemini directly.

    Args:
        issue_number: The issue number being verified.
        lld_path: Path to the LLD markdown file.
        implementation_files: List of implementation file paths.

    Returns:
        ReviewMaterials with requirements and code snippets.
    """
    # Extract requirements from LLD
    lld_requirements = extract_lld_requirements(lld_path)

    # Read code snippets from implementation files
    code_snippets: dict[str, str] = {}

    for file_path in implementation_files:
        # Skip non-Python files
        if file_path.suffix != ".py":
            continue

        try:
            source = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning(
                "Cannot read file %s for review materials: %s", file_path, e
            )
            continue

        # Skip empty files
        if not source.strip():
            continue

        code_snippets[str(file_path)] = source

    return ReviewMaterials(
        lld_requirements=lld_requirements,
        code_snippets=code_snippets,
        issue_number=issue_number,
    )


# =============================================================================
# Report Generation
# =============================================================================


def _format_verdict_badge(verdict: Literal["PASS", "WARN", "BLOCK"]) -> str:
    """Format a verdict as a readable badge string.

    Args:
        verdict: The completeness verdict.

    Returns:
        Formatted badge string.
    """
    badges = {
        "PASS": "PASS",
        "WARN": "WARNING",
        "BLOCK": "BLOCKED",
    }
    return badges.get(verdict, verdict)


def _format_category(category: CompletenessCategory) -> str:
    """Format a CompletenessCategory enum for display.

    Args:
        category: The category enum value.

    Returns:
        Human-readable category string.
    """
    display_names = {
        CompletenessCategory.DEAD_CLI_FLAG: "Dead CLI Flag",
        CompletenessCategory.EMPTY_BRANCH: "Empty Branch",
        CompletenessCategory.DOCSTRING_ONLY: "Docstring-Only Function",
        CompletenessCategory.TRIVIAL_ASSERTION: "Trivial Assertion",
        CompletenessCategory.UNUSED_IMPORT: "Unused Import",
    }
    return display_names.get(category, str(category.value))


def _format_issues_table(issues: list[CompletenessIssue]) -> str:
    """Format completeness issues as a markdown table.

    Args:
        issues: List of completeness issues.

    Returns:
        Markdown table string, or "No issues detected." if empty.
    """
    if not issues:
        return "No issues detected."

    lines = [
        "| Severity | Category | File | Line | Description |",
        "|----------|----------|------|------|-------------|",
    ]

    for issue in issues:
        severity = issue["severity"]
        category = _format_category(issue["category"])
        file_path = issue["file_path"]
        line_number = issue["line_number"]
        description = issue["description"]
        lines.append(
            f"| {severity} | {category} | `{file_path}` "
            f"| {line_number} | {description} |"
        )

    return "\n".join(lines)


def _format_requirements_table(
    requirements: list[tuple[int, str]],
) -> str:
    """Format LLD requirements as a verification table.

    Since we only have AST-level analysis (not semantic verification),
    requirements are listed with PENDING status for the user/Gemini
    to verify at Layer 2.

    Args:
        requirements: List of (id, text) requirement tuples.

    Returns:
        Markdown table string.
    """
    if not requirements:
        return "No requirements found in LLD Section 3."

    lines = [
        "| # | Requirement | Status | Evidence |",
        "|---|-------------|--------|----------|",
    ]

    for req_id, req_text in requirements:
        lines.append(
            f"| {req_id} | {req_text} | PENDING | Awaiting verification |"
        )

    return "\n".join(lines)


def generate_implementation_report(
    issue_number: int,
    lld_path: Path,
    implementation_files: list[Path],
    completeness_result: CompletenessResult,
) -> Path:
    """Generate implementation report to docs/reports/active/{issue}-implementation-report.md.

    Issue #147, Requirement 9: Generates a comprehensive implementation
    verification report that includes:
    - LLD requirement verification table (Requirement 10)
    - Completeness analysis summary (Requirement 11)
    - Issue details and timing information

    The report is written to the standard reports directory. If the
    directory does not exist, it is created.

    Args:
        issue_number: The issue number being verified.
        lld_path: Path to the LLD markdown file.
        implementation_files: List of implementation file paths.
        completeness_result: Results from AST completeness analysis.

    Returns:
        Path to the generated report file.
    """
    # Extract requirements for the report
    requirements = extract_lld_requirements(lld_path)

    # Build the report content
    generated_at = datetime.now(timezone.utc).isoformat()
    verdict = completeness_result["verdict"]
    verdict_badge = _format_verdict_badge(verdict)
    issues = completeness_result["issues"]
    ast_ms = completeness_result["ast_analysis_ms"]
    gemini_ms = completeness_result.get("gemini_review_ms")

    # Count issues by severity
    error_count = sum(1 for i in issues if i["severity"] == "ERROR")
    warning_count = sum(1 for i in issues if i["severity"] == "WARNING")

    # Format file list
    file_list_lines = []
    for f in implementation_files:
        file_list_lines.append(f"- `{f}`")
    file_list = (
        "\n".join(file_list_lines) if file_list_lines else "No files analyzed."
    )

    # Format timing
    timing_parts = [f"AST analysis: {ast_ms}ms"]
    if gemini_ms is not None:
        timing_parts.append(f"Gemini review: {gemini_ms}ms")
    timing_str = " | ".join(timing_parts)

    # Build report markdown
    report = (
        f"# {issue_number} - Implementation Verification Report\n"
        f"\n"
        f"**Issue:** #{issue_number}\n"
        f"**Generated:** {generated_at}\n"
        f"**Verdict:** {verdict_badge}\n"
        f"\n"
        f"---\n"
        f"\n"
        f"## Completeness Analysis Summary\n"
        f"\n"
        f"**Overall Verdict:** {verdict_badge}\n"
        f"**Errors:** {error_count} | **Warnings:** {warning_count}\n"
        f"**Timing:** {timing_str}\n"
        f"\n"
        f"### Issues Detected\n"
        f"\n"
        f"{_format_issues_table(issues)}\n"
        f"\n"
        f"## LLD Requirement Verification\n"
        f"\n"
        f"{_format_requirements_table(requirements)}\n"
        f"\n"
        f"## Files Analyzed\n"
        f"\n"
        f"{file_list}\n"
        f"\n"
        f"---\n"
        f"\n"
        f"*Generated by Implementation Completeness Gate (N4b) — Issue #147*\n"
    )

    # Determine output path
    # Navigate up from the completeness module to find project root
    # Standard path: docs/reports/active/{issue}-implementation-report.md
    report_dir = _find_reports_dir(lld_path)
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = report_dir / f"{issue_number}-implementation-report.md"
    try:
        report_path.write_text(report, encoding="utf-8")
        logger.info("Implementation report written to %s", report_path)
    except OSError as e:
        logger.error(
            "Failed to write implementation report to %s: %s", report_path, e
        )

    return report_path


def _find_reports_dir(lld_path: Path) -> Path:
    """Find the docs/reports/active directory relative to the project root.

    Walks up from the LLD path to find a directory containing
    'docs/reports/active'. Falls back to creating relative to the
    project root if not found.

    Args:
        lld_path: Path to the LLD file, used to locate the project root.

    Returns:
        Path to the docs/reports/active directory.
    """
    # Walk up from the LLD path looking for project markers
    current = lld_path.resolve().parent
    for _ in range(10):  # Max 10 levels up
        candidate = current / "docs" / "reports" / "active"
        if candidate.exists():
            return candidate
        # Check for project root markers
        if (current / "pyproject.toml").exists() or (
            current / ".git"
        ).exists():
            return current / "docs" / "reports" / "active"
        parent = current.parent
        if parent == current:
            break
        current = parent

    # Fallback: relative to LLD path's parent
    return lld_path.resolve().parent / "docs" / "reports" / "active"