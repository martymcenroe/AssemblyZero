"""Test type detection patterns for TDD Testing Workflow.

Provides detection logic for inferring which types of tests are needed
based on LLD content. This becomes the retrieval corpus when RAG is implemented.
"""

import logging
import sys
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

#: The test-type knowledge base, shipped beside this module.
TYPES_YAML = Path(__file__).parent / "types.yaml"


class KnowledgeBaseError(ValueError):
    """types.yaml cannot be read, does not parse, or holds no `test_types`
    mapping (ADR 0236). Names the file and the cause."""


def _loud(message: str) -> None:
    """One ERROR line on stderr and in the log (ADR 0236 property 1)."""
    logger.error("[KNOWLEDGE] %s", message)
    print(f"ERROR [KNOWLEDGE] {message}", file=sys.stderr, flush=True)


def load_test_types() -> dict[str, Any]:
    """Load test type definitions from types.yaml (`TYPES_YAML`).

    Returns:
        Dict of test type definitions.

    Raises:
        FileNotFoundError: when the file is missing, after an ERROR line.
        KnowledgeBaseError: when it cannot be read, does not parse, or holds
            no `test_types` mapping, after an ERROR line.

    ADR 0236: both used to fall back, silently, to a shorter inline copy of
    the definitions, so test types were detected and guidance written from
    data nobody had chosen. That copy, which existed only to stand in for
    these failures, is deleted. The file ships in the package.
    """
    yaml_path = TYPES_YAML
    if not yaml_path.is_file():
        message = (
            f"the test-type knowledge base {yaml_path} is missing, so test "
            f"types cannot be detected"
        )
        _loud(message)
        raise FileNotFoundError(message)

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, ValueError, yaml.YAMLError) as e:
        message = (
            f"the test-type knowledge base {yaml_path} cannot be read: "
            f"{type(e).__name__}: {e}"
        )
        _loud(message)
        raise KnowledgeBaseError(message) from e

    types = data.get("test_types") if isinstance(data, dict) else None
    if not isinstance(types, dict) or not types:
        message = (
            f"the test-type knowledge base {yaml_path} holds no `test_types` "
            f"mapping, so test types cannot be detected"
        )
        _loud(message)
        raise KnowledgeBaseError(message)
    return types


def detect_test_types(content: str) -> list[str]:
    """Detect which test types are needed based on content.

    Args:
        content: LLD or test plan content.

    Returns:
        List of detected test type names.
    """
    content_lower = content.lower()
    detected = set()
    test_types = load_test_types()

    for type_name, type_def in test_types.items():
        patterns = type_def.get("detection_patterns", [])
        for pattern in patterns:
            if pattern.lower() in content_lower:
                detected.add(type_name)
                break

    # Always include unit tests if any other type detected
    if detected and "unit" not in detected:
        detected.add("unit")

    # Default to unit if nothing detected
    if not detected:
        detected.add("unit")

    return sorted(list(detected))


def get_test_type_info(type_name: str) -> dict[str, Any]:
    """Get information about a specific test type.

    Args:
        type_name: Test type name (e.g., "unit", "integration").

    Returns:
        Test type definition dict, or empty dict if not found.
    """
    test_types = load_test_types()
    return test_types.get(type_name, {})


def get_required_tools(type_names: list[str]) -> list[str]:
    """Get list of tools required for the given test types.

    Args:
        type_names: List of test type names.

    Returns:
        Deduplicated list of required tools.
    """
    test_types = load_test_types()
    tools = set()

    for type_name in type_names:
        type_def = test_types.get(type_name, {})
        for tool in type_def.get("tools", []):
            tools.add(tool)

    return sorted(list(tools))


def get_mock_guidance(type_names: list[str]) -> str:
    """Get combined mock guidance for the given test types.

    Args:
        type_names: List of test type names.

    Returns:
        Combined mock guidance string.
    """
    test_types = load_test_types()
    guidance_parts = []

    for type_name in type_names:
        type_def = test_types.get(type_name, {})
        guidance = type_def.get("mock_guidance", "")
        if guidance and guidance not in guidance_parts:
            guidance_parts.append(f"**{type_def.get('name', type_name)}:** {guidance}")

    return "\n".join(guidance_parts) if guidance_parts else "No specific mock guidance."


def calculate_coverage_target(type_names: list[str]) -> int:
    """Calculate coverage target based on test types.

    Uses the highest coverage target among detected types.

    Args:
        type_names: List of test type names.

    Returns:
        Coverage target percentage.
    """
    test_types = load_test_types()
    max_target = 80  # Default

    for type_name in type_names:
        type_def = test_types.get(type_name, {})
        target = type_def.get("coverage_target", 0)
        if target > max_target:
            max_target = target

    return max_target
