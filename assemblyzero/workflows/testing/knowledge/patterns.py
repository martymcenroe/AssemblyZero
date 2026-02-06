"""Test type detection patterns for TDD Testing Workflow.

Provides detection logic for inferring which types of tests are needed
based on LLD content. This becomes the retrieval corpus when RAG is implemented.
"""

import re
from pathlib import Path
from typing import Any

import yaml


# Load test type definitions from YAML
def load_test_types() -> dict[str, Any]:
    """Load test type definitions from types.yaml.

    Returns:
        Dict of test type definitions.
    """
    yaml_path = Path(__file__).parent / "types.yaml"

    if not yaml_path.exists():
        # Fallback to inline definitions
        return _default_test_types()

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("test_types", {})
    except Exception:
        return _default_test_types()


def _default_test_types() -> dict[str, Any]:
    """Default test type definitions if YAML not available."""
    return {
        "unit": {
            "name": "Unit Tests",
            "description": "Test individual functions/classes in isolation",
            "tools": ["pytest"],
            "coverage_target": 80,
            "detection_patterns": ["function", "class", "method", "utility"],
            "mock_guidance": "Mock external dependencies (APIs, DB, filesystem)",
        },
        "integration": {
            "name": "Integration Tests",
            "description": "Test component interactions",
            "tools": ["pytest", "docker-compose"],
            "coverage_target": 60,
            "detection_patterns": ["database", "api", "workflow", "service", "integration"],
        },
        "e2e": {
            "name": "End-to-End Tests",
            "description": "Test complete user flows",
            "tools": ["pytest", "playwright"],
            "coverage_target": 40,
            "detection_patterns": ["user flow", "end-to-end", "e2e", "complete flow"],
        },
        "browser": {
            "name": "Browser/UI Tests",
            "description": "Test web UI interactions",
            "tools": ["playwright", "selenium"],
            "detection_patterns": ["html", "frontend", "ui", "web", "browser", "button", "form"],
            "mock_guidance": "Real browser required, mock backend APIs",
        },
        "terminal": {
            "name": "Terminal/CLI Tests",
            "description": "Test command-line interfaces",
            "tools": ["pytest", "pexpect"],
            "detection_patterns": ["cli", "argparse", "input()", "command line", "terminal"],
        },
        "performance": {
            "name": "Performance Tests",
            "description": "Test speed and resource usage",
            "tools": ["locust", "pytest-benchmark"],
            "detection_patterns": ["latency", "throughput", "load", "performance", "benchmark"],
        },
        "security": {
            "name": "Security Tests",
            "description": "Test security controls",
            "tools": ["bandit", "safety", "pytest"],
            "detection_patterns": ["auth", "password", "token", "credential", "security", "permission"],
        },
    }


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
