"""Framework detection for multi-framework TDD workflow.

Issue #381: Detects test framework from LLD content and project files.
Supports pytest, Playwright, Jest, and Vitest.
"""

import json
import logging
import os
import re
import sys
from collections.abc import Callable
from enum import Enum
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


def _loud(message: str) -> None:
    """One ERROR line on stderr and in the log (ADR 0236 property 1). Every
    raise it precedes reaches N0, which halts, and HALT alerts."""
    logger.error("[FRAMEWORKS] %s", message)
    print(f"ERROR [FRAMEWORKS] {message}", file=sys.stderr, flush=True)


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
    #: #3089: an integer percentage, the unit of every coverage target in
    #: the run. It was `coverage_target: float`, a fraction nothing read.
    coverage_target_percent: int
    scaffold_template: str
    working_directory: Optional[str]


class TestRunResult(TypedDict):
    """Unified result from any test runner."""
    passed: int
    failed: int
    skipped: int
    errors: int
    total: int
    #: #4246: None when the run did not measure line coverage (it was not
    #: asked to, or its tests did not all pass); never 0% in place of one.
    coverage_percent: float | None
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
#: The suffix guesses for a JavaScript or TypeScript test file. Used only when
#: there is no project to read (`detect_framework_from_lld` without a root):
#: with a project, a named path resolves to the runner its own directory has
#: (#4237), because the suffix alone cannot tell Vitest from Jest.
_JS_FILE_PATTERNS: list[tuple[re.Pattern[str], TestFramework]] = [
    (re.compile(r"\.spec\.ts[`\"'\s|]"), TestFramework.PLAYWRIGHT),
    (re.compile(r"\.spec\.js[`\"'\s|]"), TestFramework.PLAYWRIGHT),
    (re.compile(r"\.test\.ts[`\"'\s|]"), TestFramework.JEST),
    (re.compile(r"\.test\.js[`\"'\s|]"), TestFramework.JEST),
]
_PYTEST_FILE_PATTERNS: list[tuple[re.Pattern[str], TestFramework]] = [
    (re.compile(r"test_.*\.py[`\"'\s|]"), TestFramework.PYTEST),
]
_FILE_PATTERNS = _JS_FILE_PATTERNS + _PYTEST_FILE_PATTERNS

#: The JavaScript and TypeScript test-file suffixes an LLD names (#4237).
#: Closed: the four the runners' default test patterns share.
JS_TEST_SUFFIXES: tuple[str, ...] = (".test.ts", ".test.js", ".spec.ts", ".spec.js")

#: Characters that delimit a path in markdown: code spans, quotes, table
#: cells, link targets and list punctuation. Closed.
_PATH_DELIMITERS = "`'\"|()[]<>,;"

#: Characters that make a token a pattern rather than a file. Closed.
_GLOB_CHARACTERS = "*?{}"


class FrameworkResolutionError(ValueError):
    """The run cannot say which runner tests a file, or where it runs (#4237).

    A ValueError, so a load site that already stops on an unreadable
    package.json (#3707) stops on this the same way.
    """

# --- Keyword indicators (third priority) ---
_KEYWORD_PATTERNS: list[tuple[re.Pattern[str], TestFramework]] = [
    (re.compile(r"@playwright/test", re.IGNORECASE), TestFramework.PLAYWRIGHT),
    (re.compile(r"playwright\.config\.(ts|js)", re.IGNORECASE), TestFramework.PLAYWRIGHT),
    (re.compile(r"npx\s+playwright\s+test", re.IGNORECASE), TestFramework.PLAYWRIGHT),
    (re.compile(r"\bjest\b", re.IGNORECASE), TestFramework.JEST),
    (re.compile(r"\bvitest\b", re.IGNORECASE), TestFramework.VITEST),
    (re.compile(r"\bpytest\b", re.IGNORECASE), TestFramework.PYTEST),
]


def _named_test_paths(lld_content: str, is_test_file: Callable[[str], bool]) -> list[str]:
    """Every token of the LLD that `is_test_file` calls a test file, in order.

    Markdown delimiters and sentence punctuation come off first. A token
    holding a glob character (`*.test.ts`) describes files and names none, so
    it is not a path. Paths come back with forward slashes and no leading `./`.
    """
    text = lld_content or ""
    for character in _PATH_DELIMITERS:
        text = text.replace(character, " ")
    found: list[str] = []
    for token in text.split():
        token = token.rstrip(".:").replace("\\", "/")
        if not is_test_file(token):
            continue
        if any(character in token for character in _GLOB_CHARACTERS):
            continue
        while token.startswith("./"):
            token = token[2:]
        if token and token not in found:
            found.append(token)
    return found


def named_js_test_paths(lld_content: str) -> list[str]:
    """Every JavaScript or TypeScript test file the LLD names, in order (#4237)."""
    return _named_test_paths(lld_content, lambda token: token.endswith(JS_TEST_SUFFIXES))


def named_test_files(lld_content: str) -> list[str]:
    """Every test file the LLD names, of any language, in order (#4437)."""
    return _named_test_paths(
        lld_content,
        lambda token: token.endswith(JS_TEST_SUFFIXES)
        or _is_python_test_file(token.rsplit("/", 1)[-1]),
    )


def frameworks_named_by_lld(
    lld_content: str, project_root: str | None = None,
) -> dict[TestFramework, str | None]:
    """The frameworks the LLD itself names, in priority order, each with the
    directory its own test paths place it in, or None when only the project
    can say where it lives (#4237).

    1. Explicit declarations ("Test Framework: Vitest"), highest priority.
    2. Test file paths. A JavaScript or TypeScript path resolves to the
       runner the project has in the directory that holds it
       (`runner_for_test_path`); with no project to read (`project_root` is
       None) the suffix is all there is, and `.test.ts` reads as Jest, as it
       always did. An explicit JavaScript declaration covers every
       JavaScript path, so none is inferred beside it. `test_*.py` is pytest.
    3. Keywords anywhere in the LLD.

    An empty dict means the LLD names no framework at all.
    """
    named: dict[TestFramework, str | None] = {}
    if not lld_content:
        return named

    for pattern, framework in _EXPLICIT_PATTERNS:
        if pattern.search(lld_content) and framework not in named:
            logger.info("Detected framework from explicit declaration: %s", framework.value)
            named[framework] = None
    explicit_js = any(framework != TestFramework.PYTEST for framework in named)

    if project_root is None:
        for pattern, framework in _JS_FILE_PATTERNS:
            if pattern.search(lld_content) and framework not in named:
                logger.info("Detected framework from file pattern: %s", framework.value)
                named[framework] = None
    elif not explicit_js:
        for path in named_js_test_paths(lld_content):
            framework, directory = runner_for_test_path(path, project_root)
            if named.get(framework) not in (None, directory):
                raise FrameworkResolutionError(
                    f"the LLD places {framework.value} tests in both "
                    f"{named[framework]} and {directory} (at {path}); one run "
                    f"tests one directory per framework"
                )
            if named.get(framework) is None:
                logger.info("Resolved %s to %s in %s", path, framework.value, directory)
                named[framework] = directory

    for pattern, framework in _PYTEST_FILE_PATTERNS:
        if pattern.search(lld_content) and framework not in named:
            logger.info("Detected framework from file pattern: %s", framework.value)
            named[framework] = None

    # #4437: the test files decide. `*_test.py` is pytest's too, and the
    # pattern above reads only `test_*.py`.
    file_paths = named_test_files(lld_content) if project_root is not None else []
    if TestFramework.PYTEST not in named and any(p.endswith(".py") for p in file_paths):
        logger.info("Detected framework from test file: pytest")
        named[TestFramework.PYTEST] = None

    # A keyword is the weakest signal. With a project to read, it names a
    # JavaScript runner only when no declaration and no test path has: prose
    # such as "Jest-compatible" beside a Vitest path must not add a runner
    # the project does not have and halt the run for it (#4237). #4437: nor
    # does prose such as "the Vitest suite still passes" beside a Python test.
    js_named = any(framework != TestFramework.PYTEST for framework in named)
    for pattern, framework in _KEYWORD_PATTERNS:
        if framework != TestFramework.PYTEST and pattern.search(lld_content) and framework not in named:
            if project_root is not None and (js_named or file_paths):
                logger.info("Keyword %s not taken: the LLD already names its "
                            "test files or its runner", framework.value)
                continue
            logger.info("Detected framework from keyword: %s", framework.value)
            named[framework] = None

    # Include PYTEST if there are pytest keywords but only if we didn't find it yet
    if (
        TestFramework.PYTEST not in named
        and not file_paths
        and re.search(r"\bpytest\b", lld_content, re.IGNORECASE)
    ):
        logger.info("Detected framework from keyword: pytest")
        named[TestFramework.PYTEST] = None

    return named


def detect_framework_from_lld(
    lld_content: str, project_root: str | None = None,
) -> list[TestFramework]:
    """The frameworks the LLD names (`frameworks_named_by_lld`), in order.

    Returns [TestFramework.PYTEST] as default if no framework detected.
    """
    named = list(frameworks_named_by_lld(lld_content, project_root))
    if not named:
        logger.info("No framework detected from LLD; defaulting to pytest")
        return [TestFramework.PYTEST]
    return named


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
            raise _unreadable_package_json(package_json_path, e) from e
    return detected


def _unreadable_package_json(path: str, error: Exception) -> ValueError:
    """The ValueError for a package.json the detector cannot read, after its
    ERROR line (ADR 0236): it raised, but said nothing where it failed."""
    message = f"{path} could not be read: {type(error).__name__}: {error}"
    _loud(message)
    return ValueError(message)


#: (file, section) pairs whose section declares pytest configuration (#3001).
#: Closed: pytest reads its configuration from exactly these.
_PYTEST_CONFIG_SECTIONS: tuple[tuple[str, str], ...] = (
    ("pyproject.toml", "[tool.pytest"),
    ("setup.cfg", "[tool:pytest]"),
    ("tox.ini", "[pytest]"),
)

#: Files whose presence at the root declares a pytest suite (#3001).
_PYTEST_ROOT_FILES: tuple[str, ...] = ("pytest.ini", "conftest.py")

#: The directories a Python suite conventionally lives in, searched to
#: MAX_DETECT_DEPTH levels for test files (#3001). Closed.
_PYTHON_TEST_DIRS: tuple[str, ...] = ("tests", "test")


def _is_python_test_file(name: str) -> bool:
    """pytest's default `python_files`: `test_*.py` and `*_test.py`."""
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def _has_pytest_suite(root: str) -> bool:
    """True when the root holds a pytest suite: a pytest configuration, or
    Python test files at the root or in its tests directory (#3001).

    A dependency line is not evidence. `pytest = "^8"` under
    `[tool.poetry.group.dev.dependencies]` says pytest is installed, which is
    true of nearly every Python repository whatever runs its tests; reading
    it as a suite made a JavaScript project with a tooling pyproject a pytest
    project too. A file that exists and cannot be read raises.
    """
    for name, section in _PYTEST_CONFIG_SECTIONS:
        path = os.path.join(root, name)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                if section in f.read():
                    return True
    if any(os.path.isfile(os.path.join(root, name)) for name in _PYTEST_ROOT_FILES):
        return True
    if any(_is_python_test_file(name) for name in os.listdir(root)
           if os.path.isfile(os.path.join(root, name))):
        return True
    for test_dir in _PYTHON_TEST_DIRS:
        top = os.path.join(root, test_dir)
        if not os.path.isdir(top):
            continue
        for current, dirnames, filenames in os.walk(top):
            depth = os.path.relpath(current, top).count(os.sep) + (current != top)
            dirnames[:] = sorted(
                d for d in dirnames if d not in SKIPPED_DIRS and not d.startswith(".")
            )
            if depth >= MAX_DETECT_DEPTH:
                dirnames[:] = []
            if "conftest.py" in filenames or any(_is_python_test_file(n) for n in filenames):
                return True
    return False


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
            message = (
                f"{path}: test_dirs names {name!r}, which is not a test framework "
                f"({[f.value for f in TestFramework]})"
            )
            _loud(message)
            raise ValueError(message) from e
        out[framework] = os.path.normpath(str(directory))
    return out


def detect_framework_dirs(project_root: str) -> dict[TestFramework, str]:
    """Which test frameworks the project has, and where each one lives, as a
    path relative to `project_root` ("." for the root) (#3707).

    pytest is looked for at the root, from a declaration or Python test
    files, never from a dependency line (`_has_pytest_suite`, #3001). The JavaScript
    frameworks are looked for at the root and up to MAX_DETECT_DEPTH levels
    below it, skipping SKIPPED_DIRS and hidden directories, so a target that
    keeps its web app in `web/` beside a Python package is seen as both. The
    first directory found for a framework wins: the root, then subdirectories
    in path order. A `test_dirs` declaration in the target's .unleashed.json
    wins over detection. Order: the root's JavaScript frameworks, pytest,
    then the subdirectories', which is the order the root-only detector gave.

    An empty dict means the project exists and declares no framework, which
    the callers read as pytest at the root. A project root that is empty or
    is not a directory raises FrameworkResolutionError naming it, after an
    ERROR line (ADR 0236): it used to be the same empty dict, so a project
    that was not there was tested as pytest.
    """
    if not project_root or not os.path.isdir(project_root):
        message = (
            f"the project root {project_root!r} is not a directory, so which "
            f"test frameworks the project has, and where, cannot be told"
        )
        _loud(message)
        raise FrameworkResolutionError(message)
    root = os.path.abspath(project_root)
    found: dict[TestFramework, str] = {}

    for framework in _js_frameworks_in(root):
        found.setdefault(framework, ".")

    if _has_pytest_suite(root):
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
    ran. Returns an empty list if nothing is found; raises
    FrameworkResolutionError when the project root is not a directory.
    """
    return list(detect_framework_dirs(project_root))


def _runner_evidence(directory: str) -> list[list[TestFramework]]:
    """The JavaScript test runners one directory declares, strongest
    evidence first (#4237): its config files; its package.json `test`
    script; the `vitest` and `jest` packages its package.json depends on.

    A config is a declaration. A dependency says only that the package is
    installed, so it decides nothing a config or the test script has decided.
    """
    configs: list[TestFramework] = []
    for filename, framework in _CONFIG_FILES.items():
        if os.path.isfile(os.path.join(directory, filename)) and framework not in configs:
            configs.append(framework)
    script: list[TestFramework] = []
    depends: list[TestFramework] = []
    package_json_path = os.path.join(directory, "package.json")
    if os.path.isfile(package_json_path):
        try:
            with open(package_json_path, "r", encoding="utf-8") as f:
                pkg = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise _unreadable_package_json(package_json_path, e) from e
        test_script = (pkg.get("scripts") or {}).get("test", "")
        for word, framework in (
            ("playwright", TestFramework.PLAYWRIGHT),
            ("vitest", TestFramework.VITEST),
            ("jest", TestFramework.JEST),
        ):
            if word in test_script:
                script.append(framework)
                break
        packages = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
        for name, framework in (("vitest", TestFramework.VITEST), ("jest", TestFramework.JEST)):
            if name in packages:
                depends.append(framework)
    return [configs, script, depends]


def choose_by_test_name(candidates: list[TestFramework], path: str) -> list[TestFramework]:
    """Two runners in one directory, told apart by the test file's own name:
    `.spec.` is Playwright's convention, `.test.` the unit runners'. Shared
    by path resolution here and test-file ownership in the phases (#4236)."""
    if len(candidates) < 2:
        return candidates
    name = os.path.basename(path)
    if ".spec." in name and TestFramework.PLAYWRIGHT in candidates:
        return [TestFramework.PLAYWRIGHT]
    if ".test." in name:
        unit = [c for c in candidates if c != TestFramework.PLAYWRIGHT]
        return unit or candidates
    return candidates


def runner_for_test_path(path: str, project_root: str) -> tuple[TestFramework, str]:
    """The runner that tests `path`, and the directory it runs in relative to
    the project root ("." for the root) (#4237).

    The directory that holds the file is read first, then each directory
    above it up to the root; the first that declares a runner decides, by
    its strongest evidence (`_runner_evidence`). Raises
    FrameworkResolutionError naming every directory searched when none
    declares one, or when one declares two the file's name cannot choose
    between. Nothing is ever placed at the root for want of a declaration.
    """
    if not project_root or not os.path.isdir(project_root):
        raise FrameworkResolutionError(
            f"the LLD names {path}, but there is no project at {project_root!r} "
            f"to say which runner runs it"
        )
    root = os.path.abspath(project_root)
    relative = os.path.normpath(path)
    if os.path.isabs(relative) or relative == ".." or relative.startswith(".." + os.sep):
        raise FrameworkResolutionError(
            f"the LLD names {path}, which is not a path inside the project {root}"
        )
    parts = os.path.dirname(relative).split(os.sep) if os.path.dirname(relative) else []
    chain = [os.path.join(*parts[:i]) for i in range(len(parts), 0, -1)] + ["."]
    searched: list[str] = []
    for directory in chain:
        searched.append(directory)
        absolute = os.path.join(root, directory)
        if not os.path.isdir(absolute):
            continue  # a new file's directory may be new too
        for tier in _runner_evidence(absolute):
            if not tier:
                continue
            chosen = choose_by_test_name(tier, relative)
            if len(chosen) == 1:
                return chosen[0], directory
            raise FrameworkResolutionError(
                f"the LLD names {path}, and {directory} declares "
                f"{' and '.join(f.value for f in chosen)}; the file's name "
                f"cannot choose between them. Declare one with a "
                f"'Test framework:' line in the LLD"
            )
    raise FrameworkResolutionError(
        f"the LLD names {path}, and no directory that holds it declares a "
        f"JavaScript test runner (searched: {', '.join(searched)}). Nothing "
        f"runs it from the root: a Vitest, Jest or Playwright config, test "
        f"script or dependency must be present in its project"
    )


def searched_directories(project_root: str) -> list[str]:
    """Every directory `detect_framework_dirs` reads, relative to the root."""
    if not project_root or not os.path.isdir(project_root):
        return []
    root = os.path.abspath(project_root)
    return ["."] + [os.path.relpath(d, root) for d in _candidate_dirs(root)]


def place_frameworks(
    frameworks: dict[TestFramework, str | None] | list[TestFramework],
    project_root: str,
) -> dict[TestFramework, str]:
    """Each framework with the directory it runs in, relative to the root
    (#3707, #4237).

    A `test_dirs` declaration in .unleashed.json wins; then the directory the
    LLD's own test path placed it in; then where detection found it. pytest
    runs at the root by construction and needs nothing installed there.
    Any other framework the project has nowhere raises
    FrameworkResolutionError naming it and every directory searched: it is
    never run from a root that does not have it.
    """
    wanted = dict(frameworks) if isinstance(frameworks, dict) else dict.fromkeys(frameworks)
    declared = _declared_test_dirs(project_root) if project_root and os.path.isdir(project_root) else {}
    detected = detect_framework_dirs(project_root)
    placed: dict[TestFramework, str] = {}
    for framework, directory in wanted.items():
        directory = declared.get(framework) or directory or detected.get(framework)
        if directory is None and framework == TestFramework.PYTEST:
            directory = "."
        if directory is None:
            searched = ", ".join(searched_directories(project_root)) or repr(project_root)
            raise FrameworkResolutionError(
                f"the LLD names {framework.value}, which the project has "
                f"nowhere (searched: {searched}). It is not run from the root"
            )
        placed[framework] = directory
    return placed


def _lld_decides(
    named: dict[TestFramework, str | None] | list[TestFramework], lld_content: str,
) -> bool:
    """The LLD outranks the project when it names a test file, or a runner
    other than pytest (#4437). It used to take a Python test file for no
    answer at all, so a run that named only `test_x.py` got every framework
    the project has, and had to write a Vitest test for a Python change.
    Naming no test file leaves the choice to the project.
    """
    return bool(named_test_files(lld_content)) or any(
        framework != TestFramework.PYTEST for framework in named
    )


def framework_source(lld_content: str, project_root: str) -> str:
    """Why a run's new tests use the frameworks they do, in words (#4437)."""
    files = named_test_files(lld_content)
    if files:
        return f"the LLD names its test files: {', '.join(files)}"
    if _lld_decides(frameworks_named_by_lld(lld_content, project_root), lld_content):
        return "the LLD names the runner"
    return "the LLD names no test file, so every framework the project has"


def resolve_framework(lld_content: str, project_root: str) -> list[TestFramework]:
    """Resolve test framework using LLD as primary signal, project files as fallback.

    Returns a list of all detected frameworks. A JavaScript or TypeScript
    test path the LLD names resolves to the runner its own directory has
    (#4237), and raises FrameworkResolutionError when no directory that
    holds it has one.
    """
    named = frameworks_named_by_lld(lld_content, project_root)

    # If the LLD names its test files or its runner, use it.
    if _lld_decides(named, lld_content):
        logger.info("Frameworks resolved from LLD: %s", [f.value for f in named])
        return list(named)

    # LLD returned default pytest — check if project files disagree or add more
    project_results = detect_framework_from_project(project_root)
    if project_results:
        logger.info("Frameworks resolved from project files: %s", [f.value for f in project_results])
        return project_results

    # Both returned default or None → use pytest
    logger.info("Framework resolved to default: pytest")
    return [TestFramework.PYTEST]


def resolve_framework_dirs(lld_content: str, project_root: str) -> dict[TestFramework, str]:
    """Every framework the run tests with, each with the directory it runs in
    (#4236, #4237): `resolve_framework`'s frameworks, placed by
    `place_frameworks`. Raises FrameworkResolutionError when a framework
    cannot be placed.
    """
    named = frameworks_named_by_lld(lld_content, project_root)
    if _lld_decides(named, lld_content):
        return place_frameworks(named, project_root)
    detected = detect_framework_dirs(project_root)
    if detected:
        return detected
    return {TestFramework.PYTEST: "."}