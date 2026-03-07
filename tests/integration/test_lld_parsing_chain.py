"""Integration test: full LLD parsing chain.

Issue #656: Verifies that ALL parsers extract non-empty results from
a known-good LLD. This catches format mismatches between what LLD
drafters produce and what downstream parsers expect.
"""

import pytest
from pathlib import Path

from assemblyzero.core.validation.test_plan_validator import (
    extract_requirements,
    extract_test_scenarios,
    validate_test_plan,
)
from assemblyzero.workflows.testing.nodes.load_lld import (
    extract_test_plan_section,
    parse_test_scenarios,
    extract_requirements as load_lld_extract_requirements,
)
from assemblyzero.workflows.testing.nodes.scaffold_tests import (
    parse_lld_test_section,
)
from assemblyzero.workflows.testing.completeness.report_generator import (
    extract_lld_requirements,
)


# ---------------------------------------------------------------------------
# Fixture: canonical LLD content matching the standard template format
# ---------------------------------------------------------------------------

CANONICAL_LLD = """\
# 999 - Test: Canonical LLD for Parsing Chain

## 1. Context & Goal

* **Issue:** #999
* **Status:** Approved (gemini-3.1-pro-preview, 2026-01-01)

---

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/core/example.py` | Add | New module |
| `tests/unit/test_example.py` | Add | Unit tests |

---

## 3. Requirements

1. The system must accept a valid input string.
2. The system must reject empty strings with ValueError.
3. The system must log all operations at INFO level.
4. The system must return a normalized result.
5. No existing tests are broken by this change.

---

## 10. Verification & Testing

### 10.0 Test Plan (TDD - Complete Before Implementation)

| Test ID | Test Description | Expected Behavior | Req ID | Status |
|---------|------------------|-------------------|--------|--------|
| T010 | Accept valid input | Returns normalized string | R1 | RED |
| T020 | Reject empty string | Raises ValueError | R2 | RED |
| T030 | Log operations | Logger called at INFO | R3 | RED |

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Valid input accepted (REQ-1) | Auto | `"hello"` | `"HELLO"` | `assert result == "HELLO"` |
| 020 | Empty string rejected (REQ-2) | Auto | `""` | `ValueError` | `pytest.raises(ValueError)` |
| 030 | Operations logged (REQ-3) | Auto | `"test"` | INFO log emitted | `mock_logger.info.assert_called()` |
| 040 | Normalized result (REQ-4) | Auto | `"HeLLo"` | `"HELLO"` | `assert result == "HELLO"` |
| 050 | No regressions (REQ-5) | Auto | Full test suite | All pass | Exit code 0 |

### 10.2 Test Commands

```bash
poetry run pytest tests/unit/test_example.py -v
```

---

**Final Status:** APPROVED
"""


class TestParsingChainIntegration:
    """Verify all parsers extract non-empty results from canonical LLD."""

    def test_validator_extract_requirements(self):
        """test_plan_validator.extract_requirements finds Section 3 items."""
        reqs = extract_requirements(CANONICAL_LLD)
        assert len(reqs) >= 5, f"Expected >=5 requirements, got {len(reqs)}: {reqs}"
        assert reqs[0]["id"] == "REQ-1"

    def test_validator_extract_test_scenarios(self):
        """test_plan_validator.extract_test_scenarios finds Section 10.1 table rows."""
        scenarios = extract_test_scenarios(CANONICAL_LLD)
        assert len(scenarios) >= 5, f"Expected >=5 scenarios, got {len(scenarios)}: {scenarios}"
        # Verify requirement refs are parsed
        refs = [ref for s in scenarios for ref in s["requirement_refs"]]
        assert len(refs) >= 3, f"Expected >=3 requirement refs, got {refs}"

    def test_validator_full_validation_passes(self):
        """validate_test_plan returns PASSED for canonical LLD."""
        result = validate_test_plan(CANONICAL_LLD)
        assert result["requirements_count"] >= 5
        assert result["tests_count"] >= 5
        assert result["coverage_percentage"] > 0

    def test_load_lld_extract_test_plan_section(self):
        """load_lld.extract_test_plan_section returns non-empty Section 10."""
        section = extract_test_plan_section(CANONICAL_LLD)
        assert len(section) > 100, f"Section 10 too short: {len(section)} chars"
        assert "Test Scenarios" in section or "|" in section

    def test_load_lld_parse_test_scenarios(self):
        """load_lld.parse_test_scenarios parses table rows from Section 10."""
        section = extract_test_plan_section(CANONICAL_LLD)
        scenarios = parse_test_scenarios(section)
        assert len(scenarios) >= 3, f"Expected >=3 scenarios, got {len(scenarios)}"

    def test_load_lld_extract_requirements(self):
        """load_lld.extract_requirements finds requirements."""
        reqs = load_lld_extract_requirements(CANONICAL_LLD)
        assert len(reqs) >= 5, f"Expected >=5 requirements, got {len(reqs)}: {reqs}"

    def test_scaffold_parse_lld_test_section(self):
        """scaffold_tests.parse_lld_test_section finds 10.0 test plan table."""
        parsed = parse_lld_test_section(CANONICAL_LLD)
        assert len(parsed["scenarios"]) >= 3, (
            f"Expected >=3 scenarios from 10.0, got {len(parsed['scenarios'])}"
        )

    def test_report_generator_extract_lld_requirements(self, tmp_path):
        """report_generator.extract_lld_requirements reads from file path."""
        lld_file = tmp_path / "LLD-999.md"
        lld_file.write_text(CANONICAL_LLD, encoding="utf-8")
        reqs = extract_lld_requirements(lld_file)
        assert len(reqs) >= 5, f"Expected >=5 requirements, got {len(reqs)}: {reqs}"


class TestRealLLDParsing:
    """Parse actual LLD files from the repo to catch real-world format issues."""

    @pytest.fixture(params=["LLD-641.md", "LLD-642.md"])
    def lld_content(self, request):
        """Load a real LLD from the active directory."""
        lld_path = Path("docs/lld/active") / request.param
        if not lld_path.exists():
            pytest.skip(f"{request.param} not found")
        return lld_path.read_text(encoding="utf-8")

    def test_extract_requirements_nonempty(self, lld_content):
        reqs = extract_requirements(lld_content)
        assert len(reqs) > 0, "extract_requirements returned empty for real LLD"

    def test_extract_test_scenarios_nonempty(self, lld_content):
        scenarios = extract_test_scenarios(lld_content)
        assert len(scenarios) > 0, "extract_test_scenarios returned empty for real LLD"

    def test_validate_test_plan_has_coverage(self, lld_content):
        result = validate_test_plan(lld_content)
        assert result["requirements_count"] > 0, "No requirements found"
        assert result["tests_count"] > 0, "No test scenarios found"
