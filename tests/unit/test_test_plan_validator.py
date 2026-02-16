"""Tests for mechanical test plan validation.

Issue #166: Test IDs match LLD Section 10.0.
"""

import pytest

from assemblyzero.core.validation.test_plan_validator import (
    COVERAGE_THRESHOLD,
    Requirement,
    LLDTestScenario,
    ValidationResult,
    check_human_delegation,
    check_requirement_coverage,
    check_type_consistency,
    check_vague_assertions,
    extract_requirements,
    extract_test_scenarios,
    map_tests_to_requirements,
    validate_test_plan,
)


# =============================================================================
# Test Fixtures (LLD markdown samples)
# =============================================================================

LLD_FULL_COVERAGE = """\
# 999 - Feature: Test Feature

## 1. Context & Goal
Something here.

## 2. Proposed Changes
Details.

## 3. Requirements

1. The system must validate input data
2. The system must return error codes on failure
3. The system must log all operations

## 4. Alternatives Considered
None.

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Validate input - valid data (Req 1) | Auto | Valid input | Accepted | Returns True |
| 020 | Validate input - invalid data (Req 1) | Auto | Bad input | Rejected | Returns False |
| 030 | Error codes on failure (Req 2) | Auto | Failure case | Error code | Code matches spec |
| 040 | Log operations on success (Req 3) | Auto | Success case | Log entry | Entry created |
| 050 | Log operations on failure (Req 3) | Auto | Failure case | Log entry | Entry created |
"""

LLD_83_COVERAGE = """\
# 141 - Feature: Something

## 3. Requirements

1. Requirement A
2. Requirement B
3. Requirement C
4. Requirement D
5. Requirement E
6. Requirement F

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Test for Requirement 1 | Auto | Input | Output | Pass |
| 020 | Test for Requirement 2 | Auto | Input | Output | Pass |
| 030 | Test for Requirement 3 | Auto | Input | Output | Pass |
| 040 | Test for Requirement 4 | Auto | Input | Output | Pass |
| 050 | Test for Requirement 5 | Auto | Input | Output | Pass |
"""

LLD_VAGUE_ASSERTIONS = """\
# 200 - Feature: Vague

## 3. Requirements

1. Must work

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Verify it works for Requirement 1 | Auto | Input | Output | Pass |
"""

LLD_HUMAN_DELEGATION = """\
# 201 - Feature: Delegation

## 3. Requirements

1. Feature must be visible

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Manual check of visual layout for Requirement 1 | Auto | Input | Output | Pass |
"""

LLD_HUMAN_DELEGATION_JUSTIFIED = """\
# 202 - Feature: Justified

## 3. Requirements

1. Feature must look good

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Manual check of layout for Requirement 1 | Manual | Input | Output | Pass |
"""

LLD_NO_SECTION_10 = """\
# 203 - Feature: Missing Section

## 3. Requirements

1. Requirement A
2. Requirement B

## 4. Alternatives Considered
None.
"""

LLD_MULTILINE_REQUIREMENTS = """\
# 204 - Feature: Multiline

## 3. Requirements

1. The system must validate input data
   ensuring all fields are checked and
   proper error messages are returned
2. The system must log operations

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Validate input fields ensuring proper error (Req 1) | Auto | Data | Result | Pass |
| 020 | Log operations check (Req 2) | Auto | Data | Result | Pass |
"""

LLD_TYPE_CONSISTENCY = """\
# 205 - Feature: Type Check

## 3. Requirements

1. Must call external API

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Test external API call for Requirement 1 | Auto | Request | Response | Pass |
"""

LLD_TABLE_VARIATIONS = """\
# 206 - Feature: Table Format

## 3. Requirements

1. Must validate data

## 10. Verification & Testing

### 10.1 Test Scenarios

|  ID  |  Scenario  |  Type  |  Input  |  Expected Output  |  Pass Criteria  |
|------|-----------|--------|---------|-------------------|-----------------|
|  010  |  Validate data check for Requirement 1  |  Auto  |  Data  |  Result  |  Pass  |
"""


# =============================================================================
# T010: Extract requirements - basic list
# =============================================================================

class TestExtractRequirementsBasic:
    """T010: Parses simple numbered list."""

    def test_extract_requirements_basic(self):
        """T010: Extract 3 requirements from numbered list."""
        reqs = extract_requirements(LLD_FULL_COVERAGE)
        assert len(reqs) == 3
        assert reqs[0]["id"] == "REQ-1"
        assert "validate input" in reqs[0]["text"].lower()
        assert reqs[1]["id"] == "REQ-2"
        assert "error codes" in reqs[1]["text"].lower()
        assert reqs[2]["id"] == "REQ-3"
        assert "log" in reqs[2]["text"].lower()


# =============================================================================
# T020: Extract requirements - multiline
# =============================================================================

class TestExtractRequirementsMultiline:
    """T020: Handles multi-line requirements."""

    def test_extract_requirements_multiline(self):
        """T020: Multi-line requirement text is concatenated."""
        reqs = extract_requirements(LLD_MULTILINE_REQUIREMENTS)
        assert len(reqs) == 2
        assert reqs[0]["id"] == "REQ-1"
        # Multi-line text should be joined
        assert "validate input" in reqs[0]["text"].lower()
        assert "error messages" in reqs[0]["text"].lower()


# =============================================================================
# T030: Extract test scenarios - table
# =============================================================================

class TestExtractLLDTestScenarios:
    """T030: Parses markdown table correctly."""

    def test_extract_test_scenarios_table(self):
        """T030: Parse 5 scenarios from table."""
        scenarios = extract_test_scenarios(LLD_FULL_COVERAGE)
        assert len(scenarios) == 5
        assert scenarios[0]["id"] == "T010"
        assert "auto" in scenarios[0]["test_type"]

    def test_extract_scenarios_from_83_coverage(self):
        """Parse scenarios from 83% coverage LLD."""
        scenarios = extract_test_scenarios(LLD_83_COVERAGE)
        assert len(scenarios) == 5


# =============================================================================
# T040: Coverage calculation - 100%
# =============================================================================

class TestCoverage100Percent:
    """T040: Returns passed=True for full coverage."""

    def test_coverage_100_percent(self):
        """T040: Full coverage passes."""
        reqs = extract_requirements(LLD_FULL_COVERAGE)
        tests = extract_test_scenarios(LLD_FULL_COVERAGE)
        passed, pct, violations = check_requirement_coverage(reqs, tests)
        assert passed is True
        assert pct == 100.0
        assert len([v for v in violations if v["severity"] == "error"]) == 0


# =============================================================================
# T050: Coverage calculation - below threshold
# =============================================================================

class TestCoverageBelowThreshold:
    """T050: Returns passed=False for 83% coverage."""

    def test_coverage_below_threshold(self):
        """T050: 5/6 requirements covered = ~83% fails 95% threshold."""
        reqs = extract_requirements(LLD_83_COVERAGE)
        tests = extract_test_scenarios(LLD_83_COVERAGE)
        passed, pct, violations = check_requirement_coverage(reqs, tests)
        assert passed is False
        assert pct < 95.0
        # Should have violation for uncovered requirement
        coverage_errors = [v for v in violations if v["check_type"] == "coverage"]
        assert len(coverage_errors) >= 1


# =============================================================================
# T060: Vague assertion detection
# =============================================================================

class TestVagueAssertionDetection:
    """T060: Flags "verify it works" patterns."""

    def test_vague_assertion_detection(self):
        """T060: Detects vague assertion in test description."""
        tests = extract_test_scenarios(LLD_VAGUE_ASSERTIONS)
        violations = check_vague_assertions(tests)
        assert len(violations) == 1
        assert violations[0]["check_type"] == "assertion"
        assert violations[0]["severity"] == "error"

    def test_no_vague_assertions_in_valid_lld(self):
        """Valid LLD has no vague assertions."""
        tests = extract_test_scenarios(LLD_FULL_COVERAGE)
        violations = check_vague_assertions(tests)
        assert len(violations) == 0


# =============================================================================
# T070: Human delegation - unjustified
# =============================================================================

class TestHumanDelegationDetection:
    """T070: Flags unjustified manual tests."""

    def test_human_delegation_detection(self):
        """T070: Detects manual check in auto test."""
        tests = extract_test_scenarios(LLD_HUMAN_DELEGATION)
        violations = check_human_delegation(tests)
        assert len(violations) == 1
        assert violations[0]["check_type"] == "delegation"

    def test_human_delegation_justified(self):
        """T080: Manual type tests don't trigger delegation violation."""
        tests = extract_test_scenarios(LLD_HUMAN_DELEGATION_JUSTIFIED)
        violations = check_human_delegation(tests)
        assert len(violations) == 0


# =============================================================================
# T080: Type consistency - warnings
# =============================================================================

class TestTypeConsistency:
    """T080: Returns warnings for type issues."""

    def test_type_consistency_warnings(self):
        """T080: Auto test mentioning external API gets warning."""
        tests = extract_test_scenarios(LLD_TYPE_CONSISTENCY)
        violations = check_type_consistency(tests)
        assert len(violations) >= 1
        assert violations[0]["severity"] == "warning"
        assert violations[0]["check_type"] == "consistency"


# =============================================================================
# T090: Full validation - pass
# =============================================================================

class TestValidateFullLLDPass:
    """T090: Full validation on valid LLD passes."""

    def test_validate_full_lld_pass(self):
        """T090: Complete valid LLD passes all checks."""
        result = validate_test_plan(LLD_FULL_COVERAGE)
        assert result["passed"] is True
        assert result["coverage_percentage"] == 100.0
        assert result["requirements_count"] == 3
        assert result["tests_count"] == 5
        assert result["execution_time_ms"] >= 0


# =============================================================================
# T100: Full validation - fail
# =============================================================================

class TestValidateFullLLDFail:
    """T100: Full validation on invalid LLD fails."""

    def test_validate_full_lld_fail(self):
        """T100: LLD with coverage gap fails."""
        result = validate_test_plan(LLD_83_COVERAGE)
        assert result["passed"] is False
        assert result["coverage_percentage"] < 95.0
        errors = [v for v in result["violations"] if v["severity"] == "error"]
        assert len(errors) >= 1


# =============================================================================
# T140: Malformed LLD handling
# =============================================================================

class TestMalformedLLDHandling:
    """T140: Graceful failure on missing sections."""

    def test_malformed_lld_handling(self):
        """T140: LLD without Section 10 returns failure."""
        result = validate_test_plan(LLD_NO_SECTION_10)
        assert result["passed"] is False
        assert result["tests_count"] == 0

    def test_empty_lld(self):
        """Empty LLD returns failure with no crash."""
        result = validate_test_plan("")
        assert result["passed"] is False
        assert result["requirements_count"] == 0
        assert result["tests_count"] == 0


# =============================================================================
# T150: Markdown table variations
# =============================================================================

class TestMarkdownTableVariations:
    """T150: Handles different spacing/alignment in tables."""

    def test_markdown_table_variations(self):
        """T150: Extra spaces in table cells still parse."""
        scenarios = extract_test_scenarios(LLD_TABLE_VARIATIONS)
        assert len(scenarios) == 1
        assert scenarios[0]["id"] == "T010"


# =============================================================================
# T160: Performance benchmark
# =============================================================================

class TestValidationPerformanceBenchmark:
    """T160: Completes within 500ms on 20KB LLD."""

    def test_validation_performance_benchmark(self):
        """T160: Validation on large LLD completes within budget."""
        # Build a ~20KB LLD with many requirements and tests
        reqs_section = "\n".join(
            f"{i}. Requirement {i} must do something important and useful"
            for i in range(1, 51)
        )
        tests_rows = "\n".join(
            f"| {i:03d} | Test for Requirement {i} functionality | Auto | Input | Output | Pass |"
            for i in range(1, 51)
        )
        big_lld = f"""\
# 999 - Feature: Performance Test

## 3. Requirements

{reqs_section}

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
{tests_rows}

### 10.2 Test Commands

```bash
poetry run pytest tests/ -v
```
"""
        # Pad to ~20KB
        padding = "\n<!-- padding comment for size testing purposes -->" * 300
        big_lld += padding

        assert len(big_lld.encode("utf-8")) >= 15000  # Verify size

        result = validate_test_plan(big_lld)
        assert result["execution_time_ms"] < 500
        assert result["requirements_count"] == 50
        assert result["tests_count"] == 50


# =============================================================================
# Additional edge case tests
# =============================================================================

class TestMapTestsToRequirements:
    """Test the mapping function directly."""

    def test_explicit_ref_mapping(self):
        """Explicit requirement_refs maps correctly."""
        reqs = [{"id": "REQ-1", "text": "Do something"}]
        tests = [{"id": "T010", "description": "Test X", "test_type": "auto", "requirement_refs": ["REQ-1"]}]
        mapping = map_tests_to_requirements(reqs, tests)
        assert "T010" in mapping["REQ-1"]

    def test_multi_ref_mapping(self):
        """Multiple requirement_refs map a single test to multiple requirements."""
        reqs = [{"id": "REQ-1", "text": "Do X"}, {"id": "REQ-2", "text": "Do Y"}]
        tests = [{"id": "T010", "description": "Test both", "test_type": "auto", "requirement_refs": ["REQ-1", "REQ-2"]}]
        mapping = map_tests_to_requirements(reqs, tests)
        assert "T010" in mapping["REQ-1"]
        assert "T010" in mapping["REQ-2"]

    def test_keyword_mapping(self):
        """Keyword matching maps test to requirement."""
        reqs = [{"id": "REQ-1", "text": "validate input data ensuring correctness"}]
        tests = [{"id": "T010", "description": "validate input data test ensuring correctness check", "test_type": "auto", "requirement_refs": []}]
        mapping = map_tests_to_requirements(reqs, tests)
        assert "T010" in mapping["REQ-1"]

    def test_no_match_returns_empty(self):
        """Completely different text produces no mapping."""
        reqs = [{"id": "REQ-1", "text": "authenticate users via LDAP"}]
        tests = [{"id": "T010", "description": "database migration script", "test_type": "auto", "requirement_refs": []}]
        mapping = map_tests_to_requirements(reqs, tests)
        assert mapping["REQ-1"] == []


class TestExtractRequirementRefs:
    """Test requirement reference extraction from table rows."""

    def test_req_in_scenario_column(self):
        """(Req 1) in Scenario column is found."""
        lld = """\
# 999

## 3. Requirements

1. Must validate

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Validate input (Req 1) | Auto | Data | Result | Pass |
"""
        scenarios = extract_test_scenarios(lld)
        assert len(scenarios) == 1
        assert "REQ-1" in scenarios[0]["requirement_refs"]

    def test_req_in_other_column(self):
        """Requirement reference in Pass Criteria column is still found."""
        lld = """\
# 999

## 3. Requirements

1. Must validate

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Validate input | Auto | Data | Result | Req 1 coverage |
"""
        scenarios = extract_test_scenarios(lld)
        assert "REQ-1" in scenarios[0]["requirement_refs"]

    def test_multi_ref_in_single_row(self):
        """(Req 5, Req 6) captures both refs."""
        lld = """\
# 999

## 3. Requirements

1. Req A
2. Req B

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Test both (Req 1, Req 2) | Auto | Data | Result | Pass |
"""
        scenarios = extract_test_scenarios(lld)
        assert "REQ-1" in scenarios[0]["requirement_refs"]
        assert "REQ-2" in scenarios[0]["requirement_refs"]


class TestCheckRequirementCoverageEdges:
    """Edge cases for coverage check."""

    def test_no_requirements_fails(self):
        """No requirements is an error."""
        passed, pct, violations = check_requirement_coverage([], [])
        assert passed is False
        assert len(violations) == 1

    def test_no_tests_fails(self):
        """Requirements with no tests fails."""
        reqs = [{"id": "REQ-1", "text": "Must do X"}]
        passed, pct, violations = check_requirement_coverage(reqs, [])
        assert passed is False
        assert pct == 0.0
