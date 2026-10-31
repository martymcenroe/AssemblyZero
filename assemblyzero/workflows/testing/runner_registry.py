"""Runner registry mapping framework types to configurations and runner instances.

Issue #381: Factory pattern for obtaining framework-specific test runners.
"""

import logging
from enum import Enum

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
)
from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner, loud

logger = logging.getLogger(__name__)


# --- Framework configuration registry ---
#: #3089: `coverage_target_percent` is each framework's own target, an integer
#: percentage like the run's `coverage_target`: ADR 0207's 95 for line
#: coverage, and 100 for Playwright's scenario coverage, where every scenario
#: must pass. N0 writes the LLD's declared target over it when the LLD
#: declares one, and the green phase judges each framework by its own. It
#: was `coverage_target`, a fraction (0.95) that nothing read; the new name
#: carries the unit, so a fraction left in an old checkpoint is never read as
#: 0.95% and made into a gate nothing can fail.
_FRAMEWORK_CONFIGS: dict[TestFramework, FrameworkConfig] = {
    TestFramework.PYTEST: {
        "framework": TestFramework.PYTEST,
        "test_runner_command": "pytest",
        "test_file_pattern": "test_*.py",
        "test_file_extension": ".py",
        "import_patterns": ["import pytest", "from pytest"],
        "result_parser": "pytest_json",
        "coverage_type": CoverageType.LINE,
        "coverage_target_percent": 95,
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
        "coverage_target_percent": 100,
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
        "coverage_target_percent": 95,
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
        "coverage_target_percent": 95,
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


def checkpoint_safe(config: FrameworkConfig | dict) -> dict:
    """The configuration as the checkpoint may hold it: enum members become
    their string values (#3708).

    LangGraph's serializer stores an Enum as a Python object and has announced
    it will refuse unregistered types; `TestFramework` and `CoverageType` in
    `framework_config` drew that warning on every implementation run. So the
    state carries strings and the checkpoint carries nothing LangGraph has to
    be told about. A reader must turn the framework back into its enum with
    `resolve_framework` before comparing it: `TestFramework` is a plain Enum,
    so `"pytest" != TestFramework.PYTEST`, and a raw comparison sent every
    pytest repository down the TypeScript scaffold path (#3732).
    """
    return {
        key: value.value if isinstance(value, Enum) else value
        for key, value in dict(config).items()
    }


_FRAMEWORKS_BY_VALUE: dict[str, TestFramework] = {fw.value: fw for fw in TestFramework}


class UnknownFrameworkError(ValueError):
    """A framework configuration names something that is not a framework
    this workflow runs (ADR 0236). Names the value and the frameworks."""


def resolve_framework(framework_config: FrameworkConfig | dict | None) -> TestFramework | None:
    """The `TestFramework` a framework configuration names, or None (#3732).

    The one place the state's framework is read back. The checkpoint carries
    the string value (#3708); a checkpoint written before that still carries
    the enum. Both resolve.

    None means the configuration names no framework: no config at all, no
    `framework` key, or a key holding None. That absence is a legitimate
    answer, which every caller reads as the pytest default, so it is quiet.

    Anything else -- a string that is no framework's value, or a value of
    another type -- raises UnknownFrameworkError after an ERROR line (ADR
    0236). It used to be None too, and `framework_ownership.run_frameworks`
    reads None on a one-framework run as pytest, so a run whose state named
    a framework this workflow cannot run was tested as a pytest run.
    """
    fw = (framework_config or {}).get("framework")
    if fw is None:
        return None
    if isinstance(fw, TestFramework):
        return fw
    if isinstance(fw, str) and fw in _FRAMEWORKS_BY_VALUE:
        return _FRAMEWORKS_BY_VALUE[fw]
    message = (
        f"the framework configuration names {fw!r}, which is not a test "
        f"framework this workflow runs ({', '.join(_FRAMEWORKS_BY_VALUE)})"
    )
    loud(message)
    raise UnknownFrameworkError(message)


def get_runner(
    framework: TestFramework,
    project_root: str = ".",
    working_directory: str | None = None,
) -> BaseTestRunner:
    """Factory method returning the appropriate runner instance.

    `working_directory` is where the framework's project lives beneath
    `project_root` (#3707: `web/` for a target whose web app is not at the
    root); the runner runs there. "." or None means the root.

    Raises ValueError for unsupported frameworks.
    Raises EnvironmentError if required external tools are missing
    (propagated from runner __init__).
    """
    config = get_framework_config(framework)
    if working_directory and working_directory != ".":
        config["working_directory"] = working_directory

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