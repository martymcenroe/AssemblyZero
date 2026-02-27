

```python
"""Integration test: full adversarial node execution with real Gemini call.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)

Requires:
- GOOGLE_API_KEY environment variable
- Network access to Gemini API
"""

import json
import os

import pytest

from assemblyzero.workflows.testing.adversarial_gemini import (
    AdversarialGeminiClient,
    GeminiModelDowngradeError,
    GeminiQuotaExhaustedError,
    GeminiTimeoutError,
)
from assemblyzero.workflows.testing.nodes.adversarial_node import (
    _parse_gemini_response,
)


@pytest.mark.integration
@pytest.mark.adversarial
@pytest.mark.expensive
class TestAdversarialIntegration:
    """Integration tests requiring real Gemini API access (T200)."""

    @pytest.fixture(autouse=True)
    def skip_without_api_key(self):
        """Skip if no API key available."""
        if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get(
            "GEMINI_API_KEY"
        ):
            pytest.skip("No Gemini API key available (set GOOGLE_API_KEY)")

    def test_full_gemini_invocation(self):
        """T200: Real Gemini call returns parseable adversarial analysis."""
        client = AdversarialGeminiClient()

        implementation = (
            "def add(a: int, b: int) -> int:\n"
            "    '''Add two numbers.'''\n"
            "    return a + b\n"
        )
        lld = (
            "# Add Function\n"
            "## Requirements\n"
            "1. Adds two integers\n"
            "2. Returns integer result\n"
            "3. Handles overflow gracefully\n"
        )
        existing_tests = (
            "def test_add_basic():\n"
            "    assert add(1, 2) == 3\n"
        )

        try:
            raw_response = client.generate_adversarial_tests(
                implementation_code=implementation,
                lld_content=lld,
                existing_tests=existing_tests,
                timeout=120,
            )
        except (GeminiQuotaExhaustedError, GeminiTimeoutError) as e:
            pytest.skip(f"Gemini unavailable: {e}")
        except GeminiModelDowngradeError as e:
            pytest.skip(f"Gemini model downgraded: {e}")

        # Should be parseable JSON
        analysis = _parse_gemini_response(raw_response)

        # Validate structure
        assert "uncovered_edge_cases" in analysis
        assert "false_claims" in analysis
        assert "missing_error_handling" in analysis
        assert "implicit_assumptions" in analysis
        assert "test_cases" in analysis
        assert isinstance(analysis["test_cases"], list)

        # Should generate at least one test
        assert len(analysis["test_cases"]) >= 1

        # Each test case should have required fields
        for tc in analysis["test_cases"]:
            assert "test_id" in tc
            assert "test_code" in tc
            assert "category" in tc
```
