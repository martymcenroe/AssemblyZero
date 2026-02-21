"""N0: Load Implementation Spec node for TDD Testing Workflow.

Issue #384: The TDD workflow now requires an Implementation Spec (produced
by the #304 spec workflow), not a raw LLD. If no spec exists, the workflow
exits with a specific command to generate one.

Reads the spec from docs/lld/drafts/spec-{N}.md and extracts:
- Full spec content (used as LLD content downstream)
- Test plan from Section 10 (LLD format) or Section 9 (impl spec format)
- Test scenarios with metadata (from tables, headings, bold, or code blocks)
- Requirements for coverage tracking
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from assemblyzero.workflows.testing.audit import (
    create_testing_audit_dir,
    gate_log,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.testing.knowledge.patterns import detect_test_types
from assemblyzero.workflows.testing.state import TestingWorkflowState, TestScenario


# LLD directory relative to repo root (kept for backward-compatible helpers)
LLD_ACTIVE_DIR = Path("docs/lld/active")

# Implementation Spec directory (Issue #384)
SPEC_DRAFTS_DIR = Path("docs/lld/drafts")


def find_lld_path(issue_number: int, repo_root: Path) -> Path | None:
    """Find the LLD file for an issue number.

    Args:
        issue_number: GitHub issue number.
        repo_root: Repository root path.

    Returns:
        Path to LLD file if found, None otherwise.
    """
    lld_dir = repo_root / LLD_ACTIVE_DIR

    if not lld_dir.exists():
        return None

    # Search patterns in priority order
    patterns = [
        f"LLD-{issue_number:03d}.md",  # LLD-086.md
        f"LLD-{issue_number:03d}-*.md",  # LLD-086-desc.md
        f"LLD-{issue_number}.md",  # LLD-86.md (unpadded)
        f"LLD-{issue_number}-*.md",  # LLD-86-desc.md
    ]

    for pattern in patterns:
        matches = list(lld_dir.glob(pattern))
        if matches:
            # Return most recently modified if multiple
            if len(matches) > 1:
                matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return matches[0]

    return None


def find_spec_path(issue_number: int, repo_root: Path) -> Path | None:
    """Find the Implementation Spec file for an issue number.

    Issue #384: TDD workflow requires an implementation spec, not a raw LLD.

    Args:
        issue_number: GitHub issue number.
        repo_root: Repository root path.

    Returns:
        Path to spec file if found, None otherwise.
    """
    spec_dir = repo_root / SPEC_DRAFTS_DIR

    if not spec_dir.exists():
        return None

    # Search patterns in priority order
    patterns = [
        f"spec-{issue_number:04d}.md",   # spec-0305.md (4-digit padded)
        f"spec-{issue_number:04d}-*.md",  # spec-0305-desc.md
        f"spec-{issue_number:03d}.md",    # spec-305.md (3-digit padded)
        f"spec-{issue_number:03d}-*.md",  # spec-305-desc.md
        f"spec-{issue_number}.md",        # spec-305.md (unpadded)
        f"spec-{issue_number}-*.md",      # spec-305-desc.md
    ]

    for pattern in patterns:
        matches = list(spec_dir.glob(pattern))
        if matches:
            if len(matches) > 1:
                matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return matches[0]

    return None


def build_spec_command(issue_number: int, repo_root: Path) -> str:
    """Build the exact command to generate a missing implementation spec.

    Args:
        issue_number: GitHub issue number.
        repo_root: Repository root path.

    Returns:
        Full command string the user can copy-paste.
    """
    return (
        f"poetry run python tools/run_implementation_spec_workflow.py "
        f"--issue {issue_number} --repo {repo_root}"
    )


def extract_test_plan_section(lld_content: str) -> str:
    """Extract test plan section from LLD or Implementation Spec content.

    Supports two document formats:
    - LLD: Section 10 (Test Plan / Verification & Testing)
    - Implementation Spec: Section 9 (Test Mapping)

    Args:
        lld_content: Full LLD or Implementation Spec markdown content.

    Returns:
        Test plan section content, or empty string if not found.
    """
    # Pattern variations for Section 10 (LLD format):
    # - ## 10. Test Plan
    # - ## 10. Verification & Testing
    # - ## 10. Testing
    # Pattern variations for Section 9 (Implementation Spec format):
    # - ## 9. Test Mapping
    # Capture until next ## heading or end of document
    patterns = [
        r"##\s*10\.?\s*(?:Test\s*Plan|Verification\s*(?:&|and)?\s*Testing|Testing)\s*\n(.*?)(?=\n##\s*\d|\Z)",
        r"##\s*9\.?\s*Test\s*Mapping\s*\n(.*?)(?=\n##\s*\d|\Z)",
        r"##\s*Test\s*(?:Plan|Mapping)\s*\n(.*?)(?=\n##|\Z)",
        r"##\s*(?:Verification|Testing)\s*\n(.*?)(?=\n##|\Z)",
    ]

    for pattern in patterns:
        match = re.search(pattern, lld_content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Fallback: extract test scenarios from Python test code blocks in
    # Implementation Spec sections (e.g., ### 6.9 `tests/unit/test_*.py`)
    # This handles specs where tests are defined as complete file contents
    # rather than in a summary table.
    fallback = _extract_test_scenarios_from_code_blocks(lld_content)
    if fallback:
        return fallback

    return ""


def _extract_test_scenarios_from_code_blocks(content: str) -> str:
    """Extract test scenario information from Python test code blocks.

    Implementation specs include complete test file contents in code blocks
    under headings like `### 6.9 tests/unit/test_orchestrator_config.py`.
    This function extracts test class and method names to build a synthetic
    test plan section that parse_test_scenarios() can process.

    Args:
        content: Full spec content with code blocks.

    Returns:
        Synthetic test plan text with table rows, or empty string.
    """
    # Find test file code blocks: ### N.N `tests/...test_*.py`
    # followed by ```python ... ```
    test_block_pattern = re.compile(
        r"###\s*\d+\.\d+\s*`(tests/[^`]*test_[^`]*\.py)`.*?\n"
        r".*?```python\s*\n(.*?)```",
        re.DOTALL,
    )

    rows = []
    for match in test_block_pattern.finditer(content):
        file_path = match.group(1)
        code = match.group(2)

        # Extract test method names: def test_xxx(self, ...) or def test_xxx(...)
        method_pattern = re.compile(r"^\s*def\s+(test_\w+)\s*\(", re.MULTILINE)
        for method_match in method_pattern.finditer(code):
            method_name = method_match.group(1)

            # Try to extract docstring or inline comment for description
            desc = ""
            after_def = code[method_match.end():]
            doc_match = re.search(r'"""(.+?)"""', after_def[:200], re.DOTALL)
            if doc_match:
                desc = doc_match.group(1).strip().split("\n")[0]
            else:
                # Use method name as description
                desc = method_name.replace("_", " ").replace("test ", "")

            # Infer test type from file path
            if "integration" in file_path:
                test_type = "integration"
            elif "e2e" in file_path:
                test_type = "e2e"
            else:
                test_type = "unit"

            rows.append(f"| {method_name} | {desc} | {test_type} | {file_path} |")

    if not rows:
        return ""

    header = "| Test ID | Scenario | Type | Source |\n|---------|----------|------|--------|\n"
    return header + "\n".join(rows)


def extract_requirements(lld_content: str) -> list[str]:
    """Extract requirements from LLD content.

    Looks for patterns like:
    - ### REQ-1.1: Description
    - 1. Requirement text
    - - [ ] Requirement checkbox

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        List of requirement strings.
    """
    requirements = []

    # Pattern 1: ### REQ-X.Y: Description
    req_pattern = re.compile(r"###\s*(REQ-[\d.]+):\s*(.+)")
    for match in req_pattern.finditer(lld_content):
        req_id = match.group(1)
        req_desc = match.group(2).strip()
        requirements.append(f"{req_id}: {req_desc}")

    # Pattern 2: Numbered requirements in acceptance criteria
    # Look for section 3 (Requirements) or acceptance criteria
    req_section_pattern = re.compile(
        r"##\s*\d*\.?\s*(?:Requirements|Acceptance Criteria)\s*\n(.*?)(?=\n##|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    match = req_section_pattern.search(lld_content)
    if match:
        section = match.group(1)
        # Extract numbered items
        numbered_pattern = re.compile(r"^\s*(\d+)\.\s+(.+)$", re.MULTILINE)
        for item_match in numbered_pattern.finditer(section):
            num = item_match.group(1)
            text = item_match.group(2).strip()
            if text and f"REQ-{num}" not in [r.split(":")[0] for r in requirements]:
                requirements.append(f"REQ-{num}: {text}")

    # Pattern 3: Checkbox items - ONLY from Section 3 (Requirements)
    # Don't extract checkboxes from the entire document (Quality Gate, Compliance, etc.)
    # The numbered requirements in Section 3 are already captured by Pattern 2

    return requirements


def parse_test_scenarios(test_plan: str) -> list[TestScenario]:
    """Parse test scenarios from test plan section.

    Looks for patterns like:
    - ### Test: test_name
    - | Test Name | Description | Type |
    - **test_name**: description

    Args:
        test_plan: Test plan section content.

    Returns:
        List of TestScenario dicts.
    """
    scenarios: list[TestScenario] = []

    # Pattern 1: ### Test: test_name or ### test_name
    heading_pattern = re.compile(
        r"###\s*(?:Test:\s*)?(\w+)\s*\n(.*?)(?=\n###|\Z)",
        re.DOTALL,
    )
    for match in heading_pattern.finditer(test_plan):
        name = match.group(1)
        content = match.group(2).strip()

        # Extract metadata from content
        scenario: TestScenario = {
            "name": name,
            "description": content[:200] if content else "",
            "requirement_ref": _extract_requirement_ref(content),
            "test_type": _infer_test_type(name, content),
            "mock_needed": _needs_mock(content),
            "assertions": _extract_assertions(content),
        }
        scenarios.append(scenario)

    # Pattern 2: Table format - flexible to handle multiple formats:
    # Format A: | Test Name | Description | Type | Requirement |
    # Format B: | ID | Scenario | Type | Input | Expected Output | Pass Criteria |
    # We extract all rows and parse based on column count
    table_row_pattern = re.compile(r"^\|(.+)\|$", re.MULTILINE)
    rows = table_row_pattern.findall(test_plan)

    header_row = None
    for row in rows:
        cols = [c.strip() for c in row.split("|")]

        # Detect header row (contains common header words)
        header_words = {"id", "test", "name", "scenario", "type", "description", "input", "output", "criteria"}
        if any(c.lower() in header_words for c in cols[:3]):
            # Skip separator rows (----)
            if all("-" in c or not c for c in cols):
                continue
            header_row = cols
            continue

        # Skip separator rows
        if all("-" in c or not c for c in cols):
            continue

        # Parse data row based on header or position
        if len(cols) >= 3:
            # First non-empty column is typically ID/Name
            name_col = cols[0] if cols[0] else cols[1] if len(cols) > 1 else "unknown"
            # Second column is typically Description/Scenario
            desc_col = cols[1] if len(cols) > 1 else ""
            # Third column is typically Type
            type_col = cols[2] if len(cols) > 2 else ""

            # Skip if name looks like a header
            if name_col.lower() in ("id", "test", "name", "scenario", "test name"):
                continue

            # Clean up the name to be a valid test function name
            test_name = re.sub(r"[^\w]+", "_", name_col).strip("_").lower()
            if not test_name:
                continue

            # Detect test type from type column or infer
            test_type_val = type_col.lower() if type_col else "unit"
            if test_type_val not in ("unit", "integration", "e2e"):
                test_type_val = _infer_test_type(test_name, desc_col)

            # Build full description from all remaining columns
            full_desc = " | ".join(c for c in cols[1:] if c and "-" not in c[:3])

            scenario: TestScenario = {
                "name": f"test_{test_name}" if not test_name.startswith("test_") else test_name,
                "description": full_desc[:200],
                "requirement_ref": "",
                "test_type": test_type_val,
                "mock_needed": _needs_mock(full_desc),
                "assertions": [],
            }
            scenarios.append(scenario)

    # Pattern 3: Bold name with description
    bold_pattern = re.compile(r"\*\*(\w+)\*\*:\s*(.+?)(?=\n\*\*|\n\n|\Z)", re.DOTALL)
    for match in bold_pattern.finditer(test_plan):
        name = match.group(1)
        desc = match.group(2).strip()

        # Skip if already captured
        if any(s["name"] == name for s in scenarios):
            continue

        scenario: TestScenario = {
            "name": name,
            "description": desc,
            "requirement_ref": _extract_requirement_ref(desc),
            "test_type": _infer_test_type(name, desc),
            "mock_needed": _needs_mock(desc),
            "assertions": _extract_assertions(desc),
        }
        scenarios.append(scenario)

    return scenarios


def _extract_requirement_ref(content: str) -> str:
    """Extract requirement reference from content."""
    match = re.search(r"REQ-[\d.]+", content)
    return match.group(0) if match else ""


def _infer_test_type(name: str, content: str) -> str:
    """Infer test type from name and content."""
    name_lower = name.lower()
    content_lower = content.lower()

    if "e2e" in name_lower or "end-to-end" in content_lower:
        return "e2e"
    if "integration" in name_lower or "integration" in content_lower:
        return "integration"
    if "browser" in content_lower or "ui" in name_lower:
        return "browser"
    if "api" in name_lower and "integration" in content_lower:
        return "integration"

    return "unit"


def _needs_mock(content: str) -> bool:
    """Determine if mocking is needed based on content."""
    mock_indicators = [
        "mock",
        "stub",
        "fake",
        "api",
        "database",
        "external",
        "network",
        "filesystem",
    ]
    content_lower = content.lower()
    return any(indicator in content_lower for indicator in mock_indicators)


def _extract_assertions(content: str) -> list[str]:
    """Extract assertion descriptions from content."""
    assertions = []

    # Look for "verify" or "assert" statements
    patterns = [
        r"verify\s+(.+?)(?:\.|$)",
        r"assert\s+(.+?)(?:\.|$)",
        r"should\s+(.+?)(?:\.|$)",
        r"must\s+(.+?)(?:\.|$)",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            assertion = match.group(1).strip()
            if assertion and len(assertion) > 5:
                assertions.append(assertion)

    return assertions[:5]  # Limit to 5 assertions


def extract_coverage_target(lld_content: str) -> int:
    """Extract coverage target from LLD.

    Looks for patterns like:
    - Coverage: 90%
    - Target coverage: 85%
    - Code coverage >= 80%

    Args:
        lld_content: Full LLD content.

    Returns:
        Coverage target percentage (default 90).
    """
    patterns = [
        r"coverage[:\s]+(\d+)%",
        r"target coverage[:\s]+(\d+)%",
        r"code coverage[:\s]*>=?\s*(\d+)%",
        r"(\d+)%\s*coverage",
    ]

    for pattern in patterns:
        match = re.search(pattern, lld_content, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return 95  # Default (see ADR 0207: LLM Team Coverage Targets)


def extract_files_to_modify(lld_content: str) -> list[dict]:
    """Extract files to modify from LLD Section 2.1.

    Parses the "Files Changed" table to extract file paths and change types.

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        List of dicts with 'path', 'change_type', and 'description'.
    """
    files = []

    # Find Section 2.1 Files Changed table
    # Pattern: | File | Change Type | Description |
    # Rows: | `path/to/file.py` | Modify | Description text |
    table_pattern = re.compile(
        r"###?\s*2\.1[^\n]*Files Changed[^\n]*\n"  # Section header
        r"\n*"  # Optional blank lines
        r"\|[^\n]+\n"  # Table header row (starts with |)
        r"\|[-|\s]+\n"  # Separator row (|---|---|---|)
        r"((?:\|[^\n]+\n)+)",  # Table rows (start with |)
        re.IGNORECASE,
    )

    match = table_pattern.search(lld_content)
    if not match:
        return files

    table_rows = match.group(1)

    # Parse each row: | `path` | ChangeType | Description |
    row_pattern = re.compile(
        r"\|\s*`?([^`|]+)`?\s*\|\s*(\w+)\s*\|\s*([^|]*)\|"
    )

    for row_match in row_pattern.finditer(table_rows):
        path = row_match.group(1).strip()
        change_type = row_match.group(2).strip()
        description = row_match.group(3).strip()

        # Skip header-like rows
        if path.lower() in ("file", "path", "filename"):
            continue

        files.append({
            "path": path,
            "change_type": change_type,
            "description": description,
        })

    return files


def _load_from_issue(
    state: TestingWorkflowState,
    issue_number: int,
    repo_root: Path,
) -> dict[str, Any]:
    """Load issue body via gh CLI and construct synthetic LLD content.

    Issue #287: --issue-only mode for lightweight workflows.

    Args:
        state: Current workflow state.
        issue_number: GitHub issue number.
        repo_root: Target repository root path.

    Returns:
        State updates with synthetic LLD content from issue body.
    """
    gate_log(f"[N0] Issue-only mode: fetching issue #{issue_number} body...")

    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--json", "title,body"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            cwd=str(repo_root),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {"error_message": f"Failed to fetch issue #{issue_number}: {e}"}

    if result.returncode != 0:
        return {"error_message": f"Issue #{issue_number} not found: {result.stderr.strip()}"}

    try:
        issue_data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error_message": f"Invalid JSON from gh issue view: {result.stdout[:200]}"}

    title = issue_data.get("title", f"Issue #{issue_number}")
    body = issue_data.get("body", "")

    if not body:
        return {"error_message": f"Issue #{issue_number} has no body content"}

    # Construct synthetic LLD content from issue title + body
    lld_content = (
        f"# {issue_number} - {title}\n\n"
        f"**Status:** APPROVED (issue-only mode)\n\n"
        f"## Description\n\n{body}\n"
    )

    gate_log(f"    Issue title: {title}")
    gate_log(f"    Body length: {len(body)} chars")

    # Extract what we can from the issue body
    test_plan_section = extract_test_plan_section(lld_content)
    test_scenarios = parse_test_scenarios(test_plan_section) if test_plan_section else []
    detected_types = detect_test_types(lld_content)
    requirements = extract_requirements(lld_content)
    coverage_target = extract_coverage_target(lld_content) or 80
    files_to_modify = extract_files_to_modify(lld_content)

    gate_log(f"    Found {len(test_scenarios)} test scenarios")
    gate_log(f"    Detected test types: {detected_types}")

    # Create audit directory
    audit_dir = create_testing_audit_dir(issue_number, repo_root)

    # Save synthetic LLD to audit trail
    file_num = next_file_number(audit_dir)
    save_audit_file(audit_dir, file_num, "issue-only-spec.md", lld_content)

    # Log workflow start
    log_workflow_execution(
        target_repo=repo_root,
        issue_number=issue_number,
        workflow_type="testing",
        event="start",
        details={
            "mode": "issue-only",
            "title": title,
            "body_length": len(body),
            "scenario_count": len(test_scenarios),
        },
    )

    return {
        "lld_content": lld_content,
        "lld_path": f"issue-only:#{issue_number}",
        "test_plan_section": test_plan_section or "",
        "test_scenarios": test_scenarios,
        "detected_test_types": detected_types or ["unit"],
        "coverage_target": state.get("coverage_target", coverage_target),
        "requirements": requirements,
        "files_to_modify": files_to_modify,
        "audit_dir": str(audit_dir),
        "file_counter": next_file_number(audit_dir),
    }


def load_lld(state: TestingWorkflowState) -> dict[str, Any]:
    """N0: Load LLD and extract test plan.

    Args:
        state: Current workflow state.

    Returns:
        State updates with LLD content and test plan data.
    """
    issue_number = state.get("issue_number", 0)

    if not issue_number:
        return {"error_message": "No issue number provided"}

    gate_log(f"[N0] Loading implementation spec for issue #{issue_number}...")

    # Check for mock mode
    if state.get("mock_mode"):
        return _mock_load_lld(state)

    # Get repo root
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()

    # Issue #287: --issue-only mode — fetch issue body, skip spec/LLD search
    if state.get("issue_only"):
        return _load_from_issue(state, issue_number, repo_root)

    # Issue #384: Find Implementation Spec (NOT raw LLD)
    lld_path = state.get("lld_path", "")
    if lld_path:
        lld_path_obj = Path(lld_path)
    else:
        lld_path_obj = find_spec_path(issue_number, repo_root)

    # Issue #380: If not found in worktree, try original (main) repo
    if (not lld_path_obj or not lld_path_obj.exists()) and state.get("original_repo_root"):
        original_root = Path(state["original_repo_root"])
        if original_root != repo_root:
            print(f"    Spec not found in worktree, checking main repo: {original_root}")
            lld_path_obj = find_spec_path(issue_number, original_root)

    # Issue #384: No spec found — exit with specific command to generate one
    if not lld_path_obj or not lld_path_obj.exists():
        cmd = build_spec_command(issue_number, repo_root)
        error_msg = (
            f"\n"
            f"    ╔══════════════════════════════════════════════════════════════╗\n"
            f"    ║  No Implementation Spec found for issue #{issue_number:<20}║\n"
            f"    ║                                                              ║\n"
            f"    ║  The TDD workflow requires an implementation spec.           ║\n"
            f"    ║  Generate one first by running:                              ║\n"
            f"    ╚══════════════════════════════════════════════════════════════╝\n"
            f"\n"
            f"    {cmd}\n"
        )
        print(error_msg)
        return {
            "error_message": f"No implementation spec found for issue #{issue_number}. "
            f"Run: {cmd}"
        }

    print(f"    Spec path: {lld_path_obj}")

    # Read LLD content
    try:
        lld_content = lld_path_obj.read_text(encoding="utf-8")
    except OSError as e:
        return {"error_message": f"Failed to read LLD: {e}"}

    # --------------------------------------------------------------------------
    # GUARD: Validate LLD content
    # --------------------------------------------------------------------------
    if not lld_content or len(lld_content) < 100:
        print(f"    [GUARD] BLOCKED: LLD content too short ({len(lld_content)} chars)")
        return {"error_message": "GUARD: LLD content too short"}

    if "APPROVED" not in lld_content.upper():
        print("    [GUARD] WARNING: LLD may not be approved (no APPROVED marker)")
    # --------------------------------------------------------------------------

    # Extract test plan section
    test_plan_section = extract_test_plan_section(lld_content)
    if not test_plan_section:
        print("    [GUARD] WARNING: No test plan section found in LLD")

    # Parse test scenarios
    test_scenarios = parse_test_scenarios(test_plan_section)
    print(f"    Found {len(test_scenarios)} test scenarios")

    # Detect test types
    detected_types = detect_test_types(lld_content)
    print(f"    Detected test types: {detected_types}")

    # Extract requirements
    requirements = extract_requirements(lld_content)
    print(f"    Found {len(requirements)} requirements")

    # Extract coverage target
    coverage_target = extract_coverage_target(lld_content)
    print(f"    Coverage target: {coverage_target}%")

    # Extract files to modify from Section 2.1
    files_to_modify = extract_files_to_modify(lld_content)
    print(f"    Found {len(files_to_modify)} files to modify")

    # Create audit directory
    audit_dir = create_testing_audit_dir(issue_number, repo_root)
    print(f"    Audit dir: {audit_dir}")

    # Save LLD to audit trail
    file_num = next_file_number(audit_dir)
    save_audit_file(audit_dir, file_num, "lld.md", lld_content)

    # Save extracted test plan
    file_num = next_file_number(audit_dir)
    test_plan_content = f"# Extracted Test Plan\n\n## Scenarios\n\n"
    for scenario in test_scenarios:
        test_plan_content += f"### {scenario['name']}\n"
        test_plan_content += f"- Type: {scenario['test_type']}\n"
        test_plan_content += f"- Requirement: {scenario['requirement_ref']}\n"
        test_plan_content += f"- Mock needed: {scenario['mock_needed']}\n"
        test_plan_content += f"- Description: {scenario['description']}\n\n"
    save_audit_file(audit_dir, file_num, "test-plan.md", test_plan_content)

    # Log workflow start
    log_workflow_execution(
        target_repo=repo_root,
        issue_number=issue_number,
        workflow_type="testing",
        event="start",
        details={
            "lld_path": str(lld_path_obj),
            "scenario_count": len(test_scenarios),
            "test_types": detected_types,
        },
    )

    return {
        "lld_path": str(lld_path_obj),
        "lld_content": lld_content,
        "test_plan_section": test_plan_section,
        "test_scenarios": test_scenarios,
        "detected_test_types": detected_types,
        "coverage_target": coverage_target,
        "requirements": requirements,
        "files_to_modify": files_to_modify,
        "audit_dir": str(audit_dir),
        "file_counter": file_num,
        "iteration_count": 0,
        "error_message": "",
    }


def _mock_load_lld(state: TestingWorkflowState) -> dict[str, Any]:
    """Mock implementation for testing."""
    issue_number = state.get("issue_number", 42)

    # Get repo root for audit dir
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()

    audit_dir = create_testing_audit_dir(issue_number, repo_root)

    mock_lld = f"""# LLD-{issue_number:03d}: Mock Feature

## 1. Context & Goal

* **Issue:** #{issue_number}
* **Status:** Approved (Gemini Review, 2026-01-30)

## 3. Requirements

1. REQ-1: The system must handle user login
2. REQ-2: The system must validate input
3. REQ-3: The system must log errors

## 10. Test Plan

### test_login_success
Verify that valid credentials result in successful login.
Requirement: REQ-1

### test_login_failure
Verify that invalid credentials return error.
Requirement: REQ-1
Mock: authentication service

### test_input_validation
Verify that invalid input is rejected.
Requirement: REQ-2

**Final Status:** APPROVED
"""

    mock_scenarios: list[TestScenario] = [
        {
            "name": "test_login_success",
            "description": "Verify successful login with valid credentials",
            "requirement_ref": "REQ-1",
            "test_type": "unit",
            "mock_needed": False,
            "assertions": ["login returns success", "session is created"],
        },
        {
            "name": "test_login_failure",
            "description": "Verify error on invalid credentials",
            "requirement_ref": "REQ-1",
            "test_type": "unit",
            "mock_needed": True,
            "assertions": ["returns error", "no session created"],
        },
        {
            "name": "test_input_validation",
            "description": "Verify input validation",
            "requirement_ref": "REQ-2",
            "test_type": "unit",
            "mock_needed": False,
            "assertions": ["rejects invalid input"],
        },
    ]

    file_num = next_file_number(audit_dir)
    save_audit_file(audit_dir, file_num, "lld.md", mock_lld)

    print(f"    [MOCK] Loaded mock LLD for issue #{issue_number}")

    return {
        "lld_path": f"docs/lld/active/LLD-{issue_number:03d}.md",
        "lld_content": mock_lld,
        "test_plan_section": "### test_login_success\n...",
        "test_scenarios": mock_scenarios,
        "detected_test_types": ["unit"],
        "coverage_target": 90,
        "requirements": ["REQ-1: User login", "REQ-2: Input validation", "REQ-3: Error logging"],
        "audit_dir": str(audit_dir),
        "file_counter": file_num,
        "iteration_count": 0,
        "error_message": "",
    }
