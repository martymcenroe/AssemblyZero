"""Runner registry mapping framework types to configurations and runner instances.

Issue #381: Factory pattern for obtaining framework-specific test runners.
"""

import logging

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
)
from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner

logger = logging.getLogger(__name__)


# --- Framework configuration registry ---
_FRAMEWORK_CONFIGS: dict[TestFramework, FrameworkConfig] = {
    TestFramework.PYTEST: {
        "framework": TestFramework.PYTEST,
        "test_runner_command": "pytest",
        "test_file_pattern": "test_*.py",
        "test_file_extension": ".py",
        "import_patterns": ["import pytest", "from pytest"],
        "result_parser": "pytest_json",
        "coverage_type": CoverageType.LINE,
        "coverage_target": 0.95,
        "scaffold_template": "pytest_standard",
        "working_directory": None,
    },
    TestFramework.PLAYWRIGHT: {
        "framework": TestFramework.PLAYWRIGHT,
        "test_runner_command": "npx playwright test",
        "test_file_pattern": "*.spec.ts",
        "test_file_extension": ".spec.ts",
        "import_patterns": ["import { test", "from '@playwright/test'"],
        "result_parser": "playwright_json",
        "coverage_type": CoverageType.SCENARIO,
        "coverage_target": 1.0,
        "scaffold_template": "playwright_spec",
        "working_directory": None,
    },
    TestFramework.JEST: {
        "framework": TestFramework.JEST,
        "test_runner_command": "npx jest",
        "test_file_pattern": "*.test.ts",
        "test_file_extension": ".test.ts",
        "import_patterns": ["describe(", "it(", "expect("],
        "result_parser": "jest_json",
        "coverage_type": CoverageType.LINE,
        "coverage_target": 0.95,
        "scaffold_template": "jest_standard",
        "working_directory": None,
    },
    TestFramework.VITEST: {
        "framework": TestFramework.VITEST,
        "test_runner_command": "npx vitest run",
        "test_file_pattern": "*.test.ts",
        "test_file_extension": ".test.ts",
        "import_patterns": ["import { describe", "from 'vitest'"],
        "result_parser": "jest_json",  # Vitest JSON output is jest-compatible
        "coverage_type": CoverageType.LINE,
        "coverage_target": 0.95,
        "scaffold_template": "vitest_standard",
        "working_directory": None,
    },
}


def get_framework_config(framework: TestFramework) -> FrameworkConfig:
    """Return the full configuration for a given test framework.

    Raises ValueError if the framework is not registered.
    """
    if framework not in _FRAMEWORK_CONFIGS:
        raise ValueError(f"Unsupported framework: {framework}")
    # Return a copy to prevent mutation
    return dict(_FRAMEWORK_CONFIGS[framework])  # type: ignore[return-value]


def get_runner(framework: TestFramework, project_root: str = ".") -> BaseTestRunner:
    """Factory method returning the appropriate runner instance.

    Raises ValueError for unsupported frameworks.
    Raises EnvironmentError if required external tools are missing
    (propagated from runner __init__).
    """
    config = get_framework_config(framework)

    if framework == TestFramework.PYTEST:
        from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner
        return PytestRunner(config, project_root)
    elif framework == TestFramework.PLAYWRIGHT:
        from assemblyzero.workflows.testing.runners.playwright_runner import PlaywrightRunner
        return PlaywrightRunner(config, project_root)
    elif framework in (TestFramework.JEST, TestFramework.VITEST):
        from assemblyzero.workflows.testing.runners.jest_runner import JestRunner
        return JestRunner(config, project_root)
    else:
        raise ValueError(f"No runner registered for framework: {framework}")