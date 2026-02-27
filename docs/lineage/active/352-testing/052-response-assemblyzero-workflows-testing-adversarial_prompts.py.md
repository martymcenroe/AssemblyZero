

```python
"""Prompt templates for Gemini adversarial analysis.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

import json


_ADVERSARIAL_ANALYSIS_SCHEMA = {
    "type": "object",
    "required": [
        "uncovered_edge_cases",
        "false_claims",
        "missing_error_handling",
        "implicit_assumptions",
        "test_cases",
    ],
    "properties": {
        "uncovered_edge_cases": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Edge cases not covered by existing tests",
        },
        "false_claims": {
            "type": "array",
            "items": {"type": "string"},
            "description": "LLD claims not backed by implementation",
        },
        "missing_error_handling": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Error paths without handlers",
        },
        "implicit_assumptions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Undocumented assumptions in the code",
        },
        "test_cases": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "test_id",
                    "target_function",
                    "category",
                    "description",
                    "test_code",
                    "claim_challenged",
                    "severity",
                ],
                "properties": {
                    "test_id": {"type": "string"},
                    "target_function": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "boundary",
                            "injection",
                            "concurrency",
                            "state",
                            "contract",
                            "resource",
                        ],
                    },
                    "description": {"type": "string"},
                    "test_code": {"type": "string"},
                    "claim_challenged": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "high", "medium"],
                    },
                },
            },
        },
    },
}


def build_adversarial_system_prompt() -> str:
    """System prompt establishing Gemini's adversarial tester persona.

    Key constraints:
    - You are a hostile reviewer trying to break the implementation.
    - NEVER generate mocks, stubs, or fakes.
    - Tests must exercise real code paths.
    - Focus on boundary conditions, error paths, and contract violations.
    - Output strict JSON.
    - Your analysis MUST include: uncovered_edge_cases, false_claims,
      missing_error_handling, and implicit_assumptions.
    """
    return (
        "You are an expert adversarial software tester. Your goal is to "
        "BREAK the implementation by finding edge cases, false claims, "
        "missing error handling, and implicit assumptions.\n\n"
        "CRITICAL CONSTRAINTS:\n"
        "- NEVER generate mocks, stubs, fakes, or monkey-patches in your test code\n"
        "- Every test MUST exercise real code paths with real function calls\n"
        "- NEVER use unittest.mock, MagicMock, Mock, AsyncMock, @patch, or monkeypatch\n"
        "- Tests must contain at least one assert statement\n"
        "- Each test function name MUST start with 'test_'\n\n"
        "OUTPUT FORMAT:\n"
        "- Respond with ONLY valid JSON matching the AdversarialAnalysis schema\n"
        "- Do NOT wrap in markdown code blocks\n"
        "- Do NOT include any text before or after the JSON\n\n"
        "REQUIRED ANALYSIS CATEGORIES (all four must be populated with at least "
        "one finding each, or explicitly state 'none found' as a list item):\n"
        "- uncovered_edge_cases: Edge cases not covered by existing tests\n"
        "- false_claims: LLD claims not backed by implementation\n"
        "- missing_error_handling: Error paths without handlers\n"
        "- implicit_assumptions: Undocumented assumptions in the code\n\n"
        "SEVERITY LEVELS for test_cases:\n"
        "- critical: Would cause data loss or security vulnerability\n"
        "- high: Would cause incorrect behavior or crashes\n"
        "- medium: Could cause issues under specific conditions\n\n"
        "Generate a maximum of 15 test cases. Focus on quality over quantity."
    )


def build_adversarial_analysis_prompt(
    implementation_code: str,
    lld_content: str,
    existing_tests: str,
    adversarial_patterns: list[str],
) -> str:
    """Build the user prompt for Gemini adversarial analysis.

    The prompt instructs Gemini to:
    1. Read the implementation and LLD.
    2. Identify claims in the LLD not backed by code.
    3. Find edge cases missing from existing tests.
    4. Generate aggressive test cases that use NO mocks.
    5. Return structured JSON matching AdversarialAnalysis schema.

    The prompt explicitly requires Gemini to populate all four analysis
    categories: uncovered_edge_cases, false_claims, missing_error_handling,
    and implicit_assumptions.
    """
    schema_json = json.dumps(_ADVERSARIAL_ANALYSIS_SCHEMA, indent=2)

    sections = []

    sections.append("## Implementation Code Under Test\n")
    sections.append(f"```python\n{implementation_code}\n```\n")

    sections.append("## Low-Level Design (LLD) Claims\n")
    sections.append(f"```markdown\n{lld_content}\n```\n")

    if existing_tests:
        sections.append("## Existing Test Suite\n")
        sections.append(f"```python\n{existing_tests}\n```\n")
    else:
        sections.append(
            "## Existing Test Suite\n\nNo existing tests provided. "
            "Generate comprehensive adversarial coverage.\n"
        )

    sections.append("## Adversarial Testing Patterns to Apply\n")
    for pattern in adversarial_patterns:
        sections.append(f"- {pattern}")
    sections.append("")

    sections.append("## Instructions\n")
    sections.append(
        "Analyze the implementation code against the LLD claims. "
        "Identify discrepancies, missing error handling, implicit assumptions, "
        "and uncovered edge cases. Then generate adversarial test cases that "
        "attempt to break the implementation.\n\n"
        "Your response MUST be valid JSON matching this schema:\n\n"
        f"```json\n{schema_json}\n```\n\n"
        "IMPORTANT REMINDERS:\n"
        "- NO mocks, stubs, fakes, or monkey-patches\n"
        "- Every test must call real functions\n"
        "- Every test must have at least one assert\n"
        "- All four analysis categories must be populated\n"
        "- Maximum 15 test cases\n"
        "- Respond with ONLY the JSON object, no surrounding text"
    )

    return "\n".join(sections)
```
