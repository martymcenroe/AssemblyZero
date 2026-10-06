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


#: The extensions each framework's IMPLEMENTATION is written in (#2805).
#:
#: Distinct from `test_file_extension`, which is the extension of the TEST
#: file: `.spec.ts` says nothing about whether the implementation is `.ts`,
#: `.tsx` or `.js`. #2796 could not port #2337's red-phase check to the
#: non-pytest path because this fact existed nowhere in the repo, and the two
#: helpers that decide it filter on `.py` -- so on a Playwright, Jest or
#: Vitest target they select nothing and can never return True.
#:
#: Closed and enumerated, one entry per `TestFramework` member, which
#: `test_every_framework_declares_its_source_extensions` enforces: adding a
#: framework without saying what its implementation looks like fails the
#: suite rather than quietly making that path undecidable again.
SOURCE_EXTENSIONS: dict[TestFramework, tuple[str, ...]] = {
    TestFramework.PYTEST: (".py",),
    TestFramework.PLAYWRIGHT: (".ts", ".tsx", ".js", ".jsx"),
    TestFramework.JEST: (".ts", ".tsx", ".js", ".jsx"),
    TestFramework.VITEST: (".ts", ".tsx", ".js", ".jsx"),
}


def source_extensions(framework: TestFramework | None) -> tuple[str, ...]:
    """What an implementation file looks like for this framework (#2805).

    Falls back to `.py` for an unknown or absent framework, which is the
    behaviour every caller had before this table existed -- so a caller that
    cannot say which framework it is under is no worse off than it was.
    """
    if framework is None:
        return (".py",)
    return SOURCE_EXTENSIONS.get(framework, (".py",))


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


def detect_framework_from_lld(lld_content: str) -> list[TestFramework]:
    """Parse LLD content for test framework indicators.

    Scans for:
    1. Explicit declarations (e.g., "Test Framework: Playwright")
    2. File patterns in Section 2.1 (e.g., .spec.ts, .test.ts, test_*.py)
    3. Keywords anywhere in the LLD

    Returns [TestFramework.PYTEST] as default if no framework detected.
    """
    if not lld_content:
        return [TestFramework.PYTEST]

    detected = []

    # Priority 1: Explicit declarations
    for pattern, framework in _EXPLICIT_PATTERNS:
        if pattern.search(lld_content) and framework not in detected:
            logger.info("Detected framework from explicit declaration: %s", framework.value)
            detected.append(framework)

    # Priority 2: File patterns
    for pattern, framework in _FILE_PATTERNS:
        if pattern.search(lld_content) and framework not in detected:
            logger.info("Detected framework from file pattern: %s", framework.value)
            detected.append(framework)

    # Priority 3: Keywords
    for pattern, framework in _KEYWORD_PATTERNS:
        if framework != TestFramework.PYTEST and pattern.search(lld_content) and framework not in detected:
            logger.info("Detected framework from keyword: %s", framework.value)
            detected.append(framework)
            
    # Include PYTEST if there are pytest keywords but only if we didn't find it yet
    if TestFramework.PYTEST not in detected and re.search(r"\bpytest\b", lld_content, re.IGNORECASE):
        logger.info("Detected framework from keyword: pytest")
        detected.append(TestFramework.PYTEST)

    if not detected:
        logger.info("No framework detected from LLD; defaulting to pytest")
        return [TestFramework.PYTEST]
        
    return detected


#: Directories the detector never descends into (#3707).
SKIPPED_DIRS = frozenset({
    "node_modules", "data", "dist", "build", "coverage", "__pycache__",
    ".git", ".venv", "venv",
})

#: How far below the project root the detector looks for a JavaScript
#: project. Two levels covers `web/` and `apps/web/`; deeper is a monorepo
#: question nobody has asked.
MAX_DETECT_DEPTH = 2

_CONFIG_FILES: dict[str, TestFramework] = {
    "playwright.config.ts": TestFramework.PLAYWRIGHT,
    "playwright.config.js": TestFramework.PLAYWRIGHT,
    "jest.config.ts": TestFramework.JEST,
    "jest.config.js": TestFramework.JEST,
    "jest.config.json": TestFramework.JEST,
    "vitest.config.ts": TestFramework.VITEST,
    "vitest.config.js": TestFramework.VITEST,
}


def _js_frameworks_in(directory: str) -> list[TestFramework]:
    """The JavaScript test frameworks one directory declares: by its config
    files first, then by its package.json `test` script."""
    detected: list[TestFramework] = []
    for filename, framework in _CONFIG_FILES.items():
        if os.path.isfile(os.path.join(directory, filename)) and framework not in detected:
            detected.append(framework)
            # Closes #1493: ASCII-only log (Windows cp1252).
            logger.info("Found config file %s in %s -> %s", filename, directory, framework.value)
    package_json_path = os.path.join(directory, "package.json")
    if os.path.isfile(package_json_path):
        try:
            with open(package_json_path, "r") as f:
                pkg = json.load(f)
            test_script = pkg.get("scripts", {}).get("test", "")
            for word, framework in (
                ("playwright", TestFramework.PLAYWRIGHT),
                ("vitest", TestFramework.VITEST),
                ("jest", TestFramework.JEST),
            ):
                if word in test_script:
                    if framework not in detected:
                        detected.append(framework)
                    break
        except (json.JSONDecodeError, OSError) as e:
            # A package.json that cannot be read is a broken project, not a
            # missing one; the run stops here rather than testing half of it.
            raise ValueError(f"{package_json_path} could not be read: {e}") from e
    return detected


def _candidate_dirs(root: str) -> list[str]:
    """Subdirectories of `root` to MAX_DETECT_DEPTH, in path order, skipping
    SKIPPED_DIRS and hidden directories."""
    out: list[str] = []
    for current, dirnames, _files in os.walk(root):
        depth = 0 if current == root else os.path.relpath(current, root).count(os.sep) + 1
        dirnames[:] = sorted(
            d for d in dirnames if d not in SKIPPED_DIRS and not d.startswith(".")
        )
        if depth >= MAX_DETECT_DEPTH:
            dirnames[:] = []
        if current != root:
            out.append(current)
    return out


def _declared_test_dirs(project_root: str) -> dict[TestFramework, str]:
    """`test_dirs` from the target's .unleashed.json, e.g. {"vitest": "web"}:
    where a framework's project lives, when the target says so (#3707). A
    declaration wins over detection. A name that is not a framework, or a
    file that is not JSON, raises: a wrong declaration is not a missing one.
    """
    path = os.path.join(project_root, ".unleashed.json")
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)
    declared = config.get("test_dirs") or {}
    out: dict[TestFramework, str] = {}
    for name, directory in declared.items():
        try:
            framework = TestFramework(name)
        except ValueError as e:
            raise ValueError(
                f"{path}: test_dirs names {name!r}, which is not a test framework "
                f"({[f.value for f in TestFramework]})"
            ) from e
        out[framework] = os.path.normpath(str(directory))
    return out


def detect_framework_dirs(project_root: str) -> dict[TestFramework, str]:
    """Which test frameworks the project has, and where each one lives, as a
    path relative to `project_root` ("." for the root) (#3707).

    pytest is looked for at the root (`pyproject.toml`). The JavaScript
    frameworks are looked for at the root and up to MAX_DETECT_DEPTH levels
    below it, skipping SKIPPED_DIRS and hidden directories, so a target that
    keeps its web app in `web/` beside a Python package is seen as both. The
    first directory found for a framework wins: the root, then subdirectories
    in path order. A `test_dirs` declaration in the target's .unleashed.json
    wins over detection. Order: the root's JavaScript frameworks, pytest,
    then the subdirectories', which is the order the root-only detector gave.
    """
    if not project_root or not os.path.isdir(project_root):
        return {}
    root = os.path.abspath(project_root)
    found: dict[TestFramework, str] = {}

    for framework in _js_frameworks_in(root):
        found.setdefault(framework, ".")

    pyproject_path = os.path.join(root, "pyproject.toml")
    if os.path.isfile(pyproject_path):
        with open(pyproject_path, "r") as f:
            toml_content = f.read()
        if "[tool.pytest" in toml_content or "pytest" in toml_content:
            found.setdefault(TestFramework.PYTEST, ".")

    for directory in _candidate_dirs(root):
        for framework in _js_frameworks_in(directory):
            found.setdefault(framework, os.path.relpath(directory, root))

    for framework, directory in _declared_test_dirs(root).items():
        found[framework] = directory

    if found:
        logger.info("Detected frameworks from project files: %s",
                    {k.value: v for k, v in found.items()})
    return found


def detect_framework_from_project(project_root: str) -> list[TestFramework]:
    """The frameworks `detect_framework_dirs` finds, in that order.

    Before #3707 this looked at the root alone, so a target with its web app
    in a subdirectory was seen as pytest only and its JavaScript suite never
    ran. Returns an empty list if nothing is found.
    """
    return list(detect_framework_dirs(project_root))


def resolve_framework(lld_content: str, project_root: str) -> list[TestFramework]:
    """Resolve test framework using LLD as primary signal, project files as fallback.

    Returns a list of all detected frameworks.
    """
    # Try LLD detection first
    lld_results = detect_framework_from_lld(lld_content)
    
    # If LLD is explicitly something other than just PYTEST default, use it.
    if len(lld_results) > 1 or (len(lld_results) == 1 and lld_results[0] != TestFramework.PYTEST):
        logger.info("Frameworks resolved from LLD: %s", [f.value for f in lld_results])
        return lld_results

    # LLD returned default pytest — check if project files disagree or add more
    project_results = detect_framework_from_project(project_root)
    if project_results:
        logger.info("Frameworks resolved from project files: %s", [f.value for f in project_results])
        return project_results

    # Both returned default or None → use pytest
    logger.info("Framework resolved to default: pytest")
    return [TestFramework.PYTEST]