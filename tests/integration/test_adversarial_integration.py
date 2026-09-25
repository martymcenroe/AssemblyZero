"""Integration test: one real adversarial call over the sanctioned transport.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)

#2926: the call goes through ``get_provider("gemini:3.1-pro")``, which is
``agy`` over stdin (ADR 0220). Opt-in, because it spends one Gemini call and
needs a logged-in ``agy`` plus the credential roster ``GeminiClient`` reads:

    AZ_LIVE_ADVERSARIAL_PROBE=1 poetry run pytest tests/integration/test_adversarial_integration.py -m integration

It does not skip on a transport error. Until #2926 it skipped on the very
exception the defect raised (an invalid API key, reported as a timeout), which
is how the node's two-month silence went unnoticed -- #2281's lesson, again.
"""

import os

import pytest

from assemblyzero.workflows.testing.adversarial_gemini import AdversarialGeminiClient
from assemblyzero.workflows.testing.nodes.adversarial_node import (
    _parse_gemini_response,
)


@pytest.mark.integration
@pytest.mark.adversarial
@pytest.mark.expensive
@pytest.mark.skipif(
    os.environ.get("AZ_LIVE_ADVERSARIAL_PROBE") != "1",
    reason="live agy call; set AZ_LIVE_ADVERSARIAL_PROBE=1 to run",
)
class TestAdversarialIntegration:
    """One real call (T200). A failure here is a failure, never a skip."""

    def test_full_gemini_invocation(self):
        """T200: a real call returns a parseable adversarial analysis."""
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

        raw_response = client.generate_adversarial_tests(
            implementation_code=implementation,
            lld_content=lld,
            existing_tests=existing_tests,
            timeout=120,
        )

        analysis = _parse_gemini_response(raw_response)

        assert "uncovered_edge_cases" in analysis
        assert "false_claims" in analysis
        assert "missing_error_handling" in analysis
        assert "implicit_assumptions" in analysis
        assert isinstance(analysis["test_cases"], list)
        assert len(analysis["test_cases"]) >= 1
        for tc in analysis["test_cases"]:
            assert "test_id" in tc
            assert "test_code" in tc
            assert "category" in tc
