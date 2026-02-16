"""Mechanical test plan validation for LLD documents.

Issue #166: Shared module used by both requirements and testing workflows.
Extracts requirements from Section 3, test scenarios from Section 10.1,
and runs deterministic coverage, assertion, delegation, and consistency checks.

All checks are regex-based with no external API calls (<500ms budget).
"""

import re
import time
from typing import Literal, TypedDict


# =============================================================================
# Data Types
# =============================================================================


class Requirement(TypedDict):
    """A requirement extracted from LLD Section 3."""

    id: str
    text: str


class LLDTestScenario(TypedDict):
    """A test scenario extracted from LLD Section 10.1."""

    id: str
    description: str
    test_type: str
    requirement_refs: list[str]


class ValidationViolation(TypedDict):
    """A single validation finding."""

    check_type: Literal["coverage", "assertion", "delegation", "consistency"]
    severity: Literal["error", "warning"]
    requirement_id: str | None
    test_id: str | None
    message: str
    line_number: int | None


class ValidationResult(TypedDict):
    """Aggregated result of all validation checks."""

    passed: bool
    coverage_percentage: float
    requirements_count: int
    tests_count: int
    mapped_count: int
    violations: list[ValidationViolation]
    summary: str
    execution_time_ms: float


# =============================================================================
# Thresholds (module-level constants for easy tuning)
# =============================================================================

COVERAGE_THRESHOLD = 0.95  # 95% requirement coverage required
MAX_VALIDATION_ATTEMPTS = 3

# Vague assertion patterns that indicate untestable tests
VAGUE_PATTERNS = [
    r"\bverify\s+it\s+works\b",
    r"\bcheck\s+everything\b",
    r"\bensure\s+proper\s+behavior\b",
    r"\btest\s+that\s+it\s+is\s+correct\b",
    r"\bvalidate\s+functionality\b",
    r"\bconfirm\s+it\s+functions\b",
    r"\bshould\s+work\s+properly\b",
    r"\bworks\s+as\s+expected\b",
]

# Human delegation patterns
HUMAN_DELEGATION_PATTERNS = [
    r"\bmanual\s+verification\b",
    r"\bmanual\s+check\b",
    r"\bvisual\s+check\b",
    r"\bvisual\s+verification\b",
    r"\bhuman\s+review\b",
    r"\bmanual\s+inspection\b",
    r"\bvisually\s+inspect\b",
    r"\bmanually\s+verify\b",
]


# =============================================================================
# Extraction Functions
# =============================================================================


def extract_requirements(lld_content: str) -> list[Requirement]:
    """Extract requirements from LLD Section 3.

    Parses numbered list items, handling multi-line requirements.
    Requirements look like:
        1. First requirement text
        2. Second requirement that
           spans multiple lines
        3. Third requirement

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        List of Requirement objects with id and text.
    """
    # Find Section 3
    section_pattern = re.compile(
        r"^#{1,3}\s*3\.\s*Requirements\b.*?\n(.*?)(?=^#{1,3}\s*\d|^#{1,3}\s*[A-Z]|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = section_pattern.search(lld_content)
    if not match:
        return []

    section_content = match.group(1)

    # Parse numbered list items (1., 2., etc.)
    # Each item starts with a number followed by a period
    requirements: list[Requirement] = []
    current_id = ""
    current_text = ""

    for line in section_content.splitlines():
        stripped = line.strip()

        # Skip empty lines and markdown emphasis/headers
        if not stripped or stripped.startswith("*") and stripped.endswith("*"):
            if current_id and not current_text:
                continue
            if current_id and current_text:
                # Empty line between items — keep accumulating
                continue
            continue

        # Check for new numbered item
        num_match = re.match(r"^(\d+)\.\s+(.+)", stripped)
        if num_match:
            # Save previous if any
            if current_id and current_text:
                requirements.append({
                    "id": current_id,
                    "text": current_text.strip(),
                })
            current_id = f"REQ-{num_match.group(1)}"
            current_text = num_match.group(2)
        elif current_id:
            # Continuation line of current requirement
            current_text += " " + stripped

    # Save last requirement
    if current_id and current_text:
        requirements.append({
            "id": current_id,
            "text": current_text.strip(),
        })

    return requirements


def extract_test_scenarios(lld_content: str) -> list[LLDTestScenario]:
    """Extract test scenarios from LLD Section 10.1.

    Parses the markdown table in Section 10.1 with columns:
    | ID | Scenario | Type | Input | Expected Output | Pass Criteria |

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        List of TestScenario objects.
    """
    # Find Section 10.1
    section_pattern = re.compile(
        r"#{2,4}\s*10\.1\b.*?\n(.*?)(?=#{2,4}\s*10\.\d|\Z)",
        re.DOTALL,
    )
    match = section_pattern.search(lld_content)
    if not match:
        return []

    section_content = match.group(1)
    scenarios: list[LLDTestScenario] = []

    for line in section_content.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue

        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]

        if len(cells) < 3:
            continue

        # Skip header and separator rows
        if all(set(c) <= set("-: ") for c in cells):
            continue
        if cells[0].lower() in ("id", "test id", "#"):
            continue

        scenario_id = cells[0].strip()
        description = cells[1].strip() if len(cells) > 1 else ""
        test_type = cells[2].strip().lower() if len(cells) > 2 else "unit"

        # Skip non-numeric IDs (likely header)
        if not re.match(r"\d+|T\d+", scenario_id, re.IGNORECASE):
            continue

        # Normalize ID to T-prefixed format
        if not scenario_id.upper().startswith("T"):
            scenario_id = f"T{scenario_id.zfill(3)}"
        else:
            scenario_id = scenario_id.upper()

        # Extract requirement references from ALL columns (not just description)
        full_row_text = " ".join(cells)
        requirement_refs = _extract_requirement_refs(full_row_text)

        scenarios.append({
            "id": scenario_id,
            "description": description,
            "test_type": test_type,
            "requirement_refs": requirement_refs,
        })

    return scenarios


def _extract_requirement_refs(text: str) -> list[str]:
    """Extract ALL requirement references from text.

    Searches the entire row text (all columns) for patterns like:
    - "Req 1", "REQ-1", "requirement 1"
    - "(Req 5, Req 6)" — finds both
    - "Requirement 3"

    Args:
        text: Full row text (all columns concatenated).

    Returns:
        List of normalized requirement references (e.g., ["REQ-1", "REQ-3"]).
    """
    refs = []
    for match in re.finditer(r"\b(?:req(?:uirement)?)\s*[-.]?\s*(\d+)\b", text, re.IGNORECASE):
        ref = f"REQ-{match.group(1)}"
        if ref not in refs:
            refs.append(ref)
    return refs


# =============================================================================
# Mapping Functions
# =============================================================================


def map_tests_to_requirements(
    requirements: list[Requirement],
    tests: list[LLDTestScenario],
) -> dict[str, list[str]]:
    """Map test IDs to the requirements they cover.

    Uses two strategies:
    1. Explicit requirement_ref in test scenarios
    2. Keyword matching between requirement text and test description

    Args:
        requirements: List of Requirements.
        tests: List of TestScenarios.

    Returns:
        Mapping: requirement_id -> [test_id, ...]
    """
    mapping: dict[str, list[str]] = {r["id"]: [] for r in requirements}

    for test in tests:
        # Strategy 1: Explicit requirement references
        if test["requirement_refs"]:
            matched = False
            for ref in test["requirement_refs"]:
                ref_upper = ref.upper()
                if ref_upper in mapping:
                    if test["id"] not in mapping[ref_upper]:
                        mapping[ref_upper].append(test["id"])
                    matched = True
            if matched:
                continue

        # Strategy 2: Keyword matching
        test_desc_lower = test["description"].lower()
        for req in requirements:
            # Extract key words from requirement (>3 chars, not common words)
            req_words = _extract_key_words(req["text"])
            matches = sum(1 for w in req_words if w in test_desc_lower)
            # Require at least 2 keyword matches for implicit mapping
            if matches >= 2:
                if test["id"] not in mapping[req["id"]]:
                    mapping[req["id"]].append(test["id"])

    return mapping


def _extract_key_words(text: str) -> list[str]:
    """Extract meaningful keywords from text for matching.

    Filters out common words and short words.

    Args:
        text: Input text.

    Returns:
        List of lowercase keywords.
    """
    stop_words = {
        "the", "and", "for", "that", "this", "with", "from", "are", "was",
        "will", "has", "have", "been", "must", "should", "can", "all",
        "any", "each", "when", "than", "also", "into", "not", "between",
    }
    words = re.findall(r"\b[a-z]{4,}\b", text.lower())
    return [w for w in words if w not in stop_words]


# =============================================================================
# Validation Check Functions
# =============================================================================


def check_requirement_coverage(
    requirements: list[Requirement],
    tests: list[LLDTestScenario],
    threshold: float = COVERAGE_THRESHOLD,
) -> tuple[bool, float, list[ValidationViolation]]:
    """Check if requirements have sufficient test coverage.

    Args:
        requirements: List of Requirements.
        tests: List of TestScenarios.
        threshold: Minimum coverage ratio (0.0-1.0).

    Returns:
        Tuple of (passed, coverage_percentage, violations).
    """
    if not requirements:
        return (False, 0.0, [{
            "check_type": "coverage",
            "severity": "error",
            "requirement_id": None,
            "test_id": None,
            "message": "No requirements found in Section 3",
            "line_number": None,
        }])

    mapping = map_tests_to_requirements(requirements, tests)
    total = len(requirements)
    covered = sum(1 for tests_list in mapping.values() if tests_list)
    coverage_pct = (covered / total) * 100 if total > 0 else 0.0

    violations: list[ValidationViolation] = []
    for req_id, test_ids in mapping.items():
        if not test_ids:
            violations.append({
                "check_type": "coverage",
                "severity": "error",
                "requirement_id": req_id,
                "test_id": None,
                "message": f"Requirement {req_id} has no test coverage",
                "line_number": None,
            })

    passed = (coverage_pct / 100) >= threshold
    return (passed, round(coverage_pct, 1), violations)


def check_vague_assertions(tests: list[LLDTestScenario]) -> list[ValidationViolation]:
    """Find tests with vague assertion language.

    Flags phrases like "verify it works", "check everything" that
    indicate untestable assertions.

    Args:
        tests: List of TestScenarios.

    Returns:
        List of violations for vague assertions.
    """
    violations: list[ValidationViolation] = []

    for test in tests:
        desc = test["description"]
        for pattern in VAGUE_PATTERNS:
            if re.search(pattern, desc, re.IGNORECASE):
                violations.append({
                    "check_type": "assertion",
                    "severity": "error",
                    "requirement_id": None,
                    "test_id": test["id"],
                    "message": f"Test {test['id']} has vague assertion: matches '{pattern}'",
                    "line_number": None,
                })
                break  # One violation per test is enough

    return violations


def check_human_delegation(tests: list[LLDTestScenario]) -> list[ValidationViolation]:
    """Find tests that inappropriately delegate to humans.

    Flags phrases like "manual verification", "visual check" unless
    the test type is explicitly "Manual".

    Args:
        tests: List of TestScenarios.

    Returns:
        List of violations for human delegation.
    """
    violations: list[ValidationViolation] = []

    for test in tests:
        desc = test["description"]
        test_type = test.get("test_type", "").lower()

        for pattern in HUMAN_DELEGATION_PATTERNS:
            if re.search(pattern, desc, re.IGNORECASE):
                # Justified if test type is explicitly "manual"
                if test_type == "manual":
                    break
                violations.append({
                    "check_type": "delegation",
                    "severity": "error",
                    "requirement_id": None,
                    "test_id": test["id"],
                    "message": f"Test {test['id']} delegates to human: matches '{pattern}' but type is '{test_type}'",
                    "line_number": None,
                })
                break

    return violations


def check_type_consistency(
    tests: list[LLDTestScenario],
    mock_guidance: dict | None = None,
) -> list[ValidationViolation]:
    """Check test types are consistent with expected patterns.

    Returns warnings (not errors) for type inconsistencies.

    Args:
        tests: List of TestScenarios.
        mock_guidance: Optional mock guidance dict (unused for now).

    Returns:
        List of warning violations for type inconsistencies.
    """
    violations: list[ValidationViolation] = []

    for test in tests:
        test_type = test.get("test_type", "").lower()
        desc = test["description"].lower()

        # Flag "auto" tests that mention live/external interactions
        if test_type == "auto":
            live_indicators = ["api call", "network", "database", "external service", "live"]
            for indicator in live_indicators:
                if indicator in desc:
                    violations.append({
                        "check_type": "consistency",
                        "severity": "warning",
                        "requirement_id": None,
                        "test_id": test["id"],
                        "message": f"Test {test['id']} is type 'auto' but mentions '{indicator}' — consider 'integration' or 'live' type",
                        "line_number": None,
                    })
                    break

    return violations


# =============================================================================
# Main Entry Point
# =============================================================================


def validate_test_plan(
    lld_content: str,
    coverage_threshold: float = COVERAGE_THRESHOLD,
) -> ValidationResult:
    """Run all mechanical validation checks on an LLD.

    Main entry point for validation. Runs all checks and aggregates results.
    Records execution time for performance monitoring.

    Args:
        lld_content: Full LLD markdown content.
        coverage_threshold: Minimum coverage ratio (0.0-1.0).

    Returns:
        ValidationResult with aggregated findings.
    """
    start = time.perf_counter()

    requirements = extract_requirements(lld_content)
    tests = extract_test_scenarios(lld_content)

    all_violations: list[ValidationViolation] = []

    # Run coverage check
    cov_passed, cov_pct, cov_violations = check_requirement_coverage(
        requirements, tests, coverage_threshold,
    )
    all_violations.extend(cov_violations)

    # Run vague assertion check
    all_violations.extend(check_vague_assertions(tests))

    # Run human delegation check
    all_violations.extend(check_human_delegation(tests))

    # Run type consistency check (warnings only)
    all_violations.extend(check_type_consistency(tests))

    # Determine pass/fail (errors block, warnings don't)
    error_count = sum(1 for v in all_violations if v["severity"] == "error")
    passed = cov_passed and error_count == 0

    # Calculate mapped count
    mapping = map_tests_to_requirements(requirements, tests)
    mapped_count = sum(1 for tests_list in mapping.values() if tests_list)

    elapsed_ms = (time.perf_counter() - start) * 1000

    # Build summary
    summary_parts = [
        f"Coverage: {cov_pct}% ({mapped_count}/{len(requirements)} requirements mapped)",
        f"Tests: {len(tests)}",
        f"Errors: {error_count}",
        f"Warnings: {sum(1 for v in all_violations if v['severity'] == 'warning')}",
    ]
    if passed:
        summary = f"PASSED — {', '.join(summary_parts)}"
    else:
        summary = f"FAILED — {', '.join(summary_parts)}"

    return {
        "passed": passed,
        "coverage_percentage": cov_pct,
        "requirements_count": len(requirements),
        "tests_count": len(tests),
        "mapped_count": mapped_count,
        "violations": all_violations,
        "summary": summary,
        "execution_time_ms": round(elapsed_ms, 2),
    }
