

```python
"""Framework detection for multi-framework TDD workflow.

Issue #381: Detects test framework from LLD content and project files.
Supports pytest, Playwright, Jest, and Vitest.
"""

import json
import logging
import os
import re
from enum import Enum
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


class TestFramework(Enum):
    """Supported test frameworks."""
    PYTEST = "pytest"
    PLAYWRIGHT = "playwright"
    JEST = "jest"
    VITEST = "vitest"


class CoverageType(Enum):
    """How coverage is measured for this framework."""
    LINE = "line"
    SCENARIO = "scenario"
    NONE = "none"


class FrameworkConfig(TypedDict):
    """Configuration for a detected test framework."""
    framework: TestFramework
    test_runner_command: str
    test_file_pattern: str
    test_file_extension: str
    import_patterns: list[str]
    result_parser: str
    coverage_type: CoverageType
    coverage_target: float
    scaffold_template: str
    working_directory: Optional[str]


class TestRunResult(TypedDict):
    """Unified result from any test runner."""
    passed: int
    failed: int
    skipped: int
    errors: int
    total: int
    coverage_percent: float
    coverage_type: CoverageType
    raw_output: str
    exit_code: int
    framework: TestFramework


# --- Explicit declaration patterns (highest priority) ---
_EXPLICIT_PATTERNS: list[tuple[re.Pattern[str], TestFramework]] = [
    (re.compile(r"test\s*framework\s*:\s*playwright", re.IGNORECASE), TestFramework.PLAYWRIGHT),
    (re.compile(r"test\s*framework\s*:\s*jest", re.IGNORECASE), TestFramework.JEST),
    (re.compile(r"test\s*framework\s*:\s*vitest", re.IGNORECASE), TestFramework.VITEST),
    (re.compile(r"test\s*framework\s*:\s*pytest", re.IGNORECASE), TestFramework.PYTEST),
]

# --- File pattern indicators (second priority) ---
_FILE_PATTERNS: list[tuple[re.Pattern[str], TestFramework]] = [
    (re.compile(r"\.spec\.ts[`\"'\s|]"), TestFramework.PLAYWRIGHT),
    (re.compile(r"\.spec\.js[`\"'\s|]"), TestFramework.PLAYWRIGHT),
    (re.compile(r"\.test\.ts[`\"'\s|]"), TestFramework.JEST),
    (re.compile(r"\.test\.js[`\"'\s|]"), TestFramework.JEST),
    (re.compile(r"test_.*\.py[`\"'\s|]"), TestFramework.PYTEST),
]

# --- Keyword indicators (third priority) ---
_KEYWORD_PATTERNS: list[tuple[re.Pattern[str], TestFramework]] = [
    (re.compile(r"@playwright/test", re.IGNORECASE), TestFramework.PLAYWRIGHT),
    (re.compile(r"playwright\.config\.(ts|js)", re.IGNORECASE), TestFramework.PLAYWRIGHT),
    (re.compile(r"npx\s+playwright\s+test", re.IGNORECASE), TestFramework.PLAYWRIGHT),
    (re.compile(r"\bjest\b", re.IGNORECASE), TestFramework.JEST),
    (re.compile(r"\bvitest\b", re.IGNORECASE), TestFramework.VITEST),
    (re.compile(r"\bpytest\b", re.IGNORECASE), TestFramework.PYTEST),
]


def detect_framework_from_lld(lld_content: str) -> TestFramework:
    """Parse LLD content for test framework indicators.

    Scans for:
    1. Explicit declarations (e.g., "Test Framework: Playwright")
    2. File patterns in Section 2.1 (e.g., .spec.ts, .test.ts, test_*.py)
    3. Keywords anywhere in the LLD

    Returns TestFramework.PYTEST as default if no framework detected.
    """
    if not lld_content:
        return TestFramework.PYTEST

    # Priority 1: Explicit declarations
    for pattern, framework in _EXPLICIT_PATTERNS:
        if pattern.search(lld_content):
            logger.info("Detected framework from explicit declaration: %s", framework.value)
            return framework

    # Priority 2: File patterns
    for pattern, framework in _FILE_PATTERNS:
        if pattern.search(lld_content):
            logger.info("Detected framework from file pattern: %s", framework.value)
            return framework

    # Priority 3: Keywords (skip pytest keyword — it's the default fallback
    # and would match almost any Python project LLD)
    for pattern, framework in _KEYWORD_PATTERNS:
        if framework != TestFramework.PYTEST and pattern.search(lld_content):
            logger.info("Detected framework from keyword: %s", framework.value)
            return framework

    logger.info("No framework detected from LLD; defaulting to pytest")
    return TestFramework.PYTEST


def detect_framework_from_project(project_root: str) -> TestFramework | None:
    """Inspect project files to infer the test framework.

    Checks for:
    - playwright.config.ts / playwright.config.js
    - jest.config.ts / jest.config.js
    - vitest.config.ts / vitest.config.js
    - package.json "scripts.test" field
    - pyproject.toml with pytest configuration

    Returns None if ambiguous or not found.
    """
    if not project_root or not os.path.isdir(project_root):
        return None

    detected: list[TestFramework] = []

    # Check for config files
    config_map = {
        "playwright.config.ts": TestFramework.PLAYWRIGHT,
        "playwright.config.js": TestFramework.PLAYWRIGHT,
        "jest.config.ts": TestFramework.JEST,
        "jest.config.js": TestFramework.JEST,
        "jest.config.json": TestFramework.JEST,
        "vitest.config.ts": TestFramework.VITEST,
        "vitest.config.js": TestFramework.VITEST,
    }

    for filename, framework in config_map.items():
        if os.path.isfile(os.path.join(project_root, filename)):
            if framework not in detected:
                detected.append(framework)
                logger.info("Found config file %s → %s", filename, framework.value)

    # Check package.json scripts
    package_json_path = os.path.join(project_root, "package.json")
    if os.path.isfile(package_json_path):
        try:
            with open(package_json_path, "r") as f:
                pkg = json.load(f)
            test_script = pkg.get("scripts", {}).get("test", "")
            if "playwright" in test_script:
                if TestFramework.PLAYWRIGHT not in detected:
                    detected.append(TestFramework.PLAYWRIGHT)
            elif "vitest" in test_script:
                if TestFramework.VITEST not in detected:
                    detected.append(TestFramework.VITEST)
            elif "jest" in test_script:
                if TestFramework.JEST not in detected:
                    detected.append(TestFramework.JEST)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read package.json: %s", e)

    # Check pyproject.toml for pytest
    pyproject_path = os.path.join(project_root, "pyproject.toml")
    if os.path.isfile(pyproject_path):
        try:
            with open(pyproject_path, "r") as f:
                content = f.read()
            if "[tool.pytest" in content or "pytest" in content:
                if TestFramework.PYTEST not in detected:
                    detected.append(TestFramework.PYTEST)
        except OSError as e:
            logger.warning("Failed to read pyproject.toml: %s", e)

    if len(detected) == 1:
        return detected[0]
    elif len(detected) > 1:
        logger.warning("Ambiguous framework detection: %s", [d.value for d in detected])
        return None
    return None


def resolve_framework(lld_content: str, project_root: str) -> TestFramework:
    """Resolve test framework using LLD as primary signal, project files as fallback.

    Priority:
    1. LLD explicit declaration (e.g., "Test Framework: Playwright")
    2. LLD file patterns (e.g., .spec.ts files in Section 2.1)
    3. Project file inspection (package.json scripts, config files)
    4. Default: PYTEST
    """
    # Try LLD detection first
    lld_result = detect_framework_from_lld(lld_content)
    if lld_result != TestFramework.PYTEST:
        # LLD found a non-default framework → high confidence
        logger.info("Framework resolved from LLD: %s", lld_result.value)
        return lld_result

    # LLD returned default pytest — check if project files disagree
    project_result = detect_framework_from_project(project_root)
    if project_result is not None:
        logger.info("Framework resolved from project files: %s", project_result.value)
        return project_result

    # Both returned default or None → use pytest
    logger.info("Framework resolved to default: pytest")
    return TestFramework.PYTEST
```
