"""Every test file under tests/ runs in some tier (#4756, #4278).

CI runs `tests/unit/` whole, and runs `tests/` three more times selecting
`-m integration`, `-m e2e` and `-m adversarial`. A test file outside
`tests/unit/` with none of those markers is collected by neither, so it runs
only when someone types a bare `pytest`. Four files in `tests/integration/` and
the whole of `tests/tools/` sat there for months, 597 tests that never ran on a
pull request, until #4756 and #4278 moved them into the unit tier.

This check walks `tests/` the way pytest does, reading the collection options
from `pyproject.toml` and any `collect_ignore` in a conftest, and parses each
test file with `ast`. A file passes when it is under `tests/unit/`, when every
test function and class in it carries a tier marker, or when it is named in
`NAMED_EXCEPTIONS` with its reason.
"""

from __future__ import annotations

import ast
import fnmatch
import os
import shlex
import tomllib
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

#: The markers a CI tier selects, besides the unit tier's whole folder.
TIER_MARKERS = frozenset({"integration", "e2e", "adversarial"})

#: Test files outside `tests/unit/` that no tier selects, each on purpose.
NAMED_EXCEPTIONS: dict[str, str] = {
    "tests/canary/test_box_canary.py": (
        "the launch health check's own micro suite, named by "
        "assemblyzero/speedrun/box_health.py"
    ),
    "tests/benchmark/test_cascade_detector_latency.py": (
        "a wall-clock budget marked `benchmark`, deselected on purpose (#4190)"
    ),
}

# pytest's own defaults, used when pyproject.toml does not set the option.
DEFAULT_PYTHON_FILES = ("test_*.py", "*_test.py")
DEFAULT_PYTHON_CLASSES = ("Test",)
DEFAULT_PYTHON_FUNCTIONS = ("test",)
DEFAULT_NORECURSEDIRS = (
    "*.egg", ".*", "_darcs", "build", "CVS", "dist", "node_modules", "venv", "{arch}",
)
IGNORE_NAMES = ("collect_ignore", "collect_ignore_glob")


class UnreadableCollection(Exception):
    """A conftest changes collection in a way this check cannot read statically."""


def _pytest_options(repo: Path) -> dict:
    pyproject = repo / "pyproject.toml"
    if not pyproject.exists():
        return {}
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return data.get("tool", {}).get("pytest", {}).get("ini_options", {})


def _addopts_ignores(repo: Path, options: Mapping) -> tuple[list[Path], list[str]]:
    """The `--ignore` and `--ignore-glob` values in `addopts`, as pytest reads them."""
    raw = options.get("addopts", "")
    args = shlex.split(raw) if isinstance(raw, str) else list(raw)
    paths: list[Path] = []
    globs: list[str] = []
    for i, arg in enumerate(args):
        for flag, sink in (("--ignore-glob", globs), ("--ignore", paths)):
            if arg == flag and i + 1 < len(args):
                value = args[i + 1]
            elif arg.startswith(flag + "="):
                value = arg[len(flag) + 1:]
            else:
                continue
            if sink is globs:
                globs.append(str(repo / value))
            else:
                paths.append((repo / value).resolve())
            break
    return paths, globs


def _conftest_ignores(conftest: Path) -> tuple[list[Path], list[str]]:
    """The literal `collect_ignore` and `collect_ignore_glob` of one conftest."""
    tree = ast.parse(conftest.read_text(encoding="utf-8", errors="replace"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and (
            node.name == "pytest_ignore_collect"
        ):
            raise UnreadableCollection(f"{conftest} defines pytest_ignore_collect")
    paths: list[Path] = []
    globs: list[str] = []
    read: set[int] = set()
    for node in tree.body:
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in IGNORE_NAMES
        ):
            continue
        try:
            values = ast.literal_eval(node.value)
        except ValueError as exc:
            raise UnreadableCollection(
                f"{conftest} sets {node.targets[0].id} to a non-literal") from exc
        read.add(id(node.targets[0]))
        for value in values:
            if node.targets[0].id == "collect_ignore":
                paths.append((conftest.parent / value).resolve())
            else:
                globs.append(str(conftest.parent / value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in IGNORE_NAMES and id(node) not in read:
            raise UnreadableCollection(f"{conftest} changes {node.id} at run time")
    return paths, globs


def _collected_test_files(repo: Path) -> Iterator[Path]:
    """Every file under `tests/` that pytest would collect as a test module."""
    options = _pytest_options(repo)
    python_files = options.get("python_files", DEFAULT_PYTHON_FILES)
    norecurse = options.get("norecursedirs", DEFAULT_NORECURSEDIRS)
    ignored, ignore_globs = _addopts_ignores(repo, options)
    tests = repo / "tests"
    for conftest in sorted(tests.rglob("conftest.py")):
        if "__pycache__" in conftest.parts:
            continue
        paths, globs = _conftest_ignores(conftest)
        ignored += paths
        ignore_globs += globs

    def skipped(path: Path) -> bool:
        return path.resolve() in ignored or any(
            fnmatch.fnmatch(str(path), glob) for glob in ignore_globs)

    for here, dirs, files in os.walk(tests):
        base = Path(here)
        dirs[:] = sorted(
            d for d in dirs
            if d != "__pycache__"
            and not any(fnmatch.fnmatch(d, pat) for pat in norecurse)
            and not (base / d / "pyvenv.cfg").exists()
            and not skipped(base / d)
        )
        for name in sorted(files):
            path = base / name
            if any(fnmatch.fnmatch(name, pat) for pat in python_files) and not skipped(path):
                yield path


def _marker_name(expr: ast.expr) -> str | None:
    """`X` for `pytest.mark.X`, `mark.X` or either one called."""
    if isinstance(expr, ast.Call):
        expr = expr.func
    if not isinstance(expr, ast.Attribute):
        return None
    owner = expr.value
    if (isinstance(owner, ast.Attribute) and owner.attr == "mark") or (
        isinstance(owner, ast.Name) and owner.id == "mark"
    ):
        return expr.attr
    return None


def _markers(exprs: list[ast.expr]) -> set[str]:
    names: set[str] = set()
    for expr in exprs:
        items = expr.elts if isinstance(expr, ast.List | ast.Tuple) else [expr]
        names.update(n for n in map(_marker_name, items) if n)
    return names


def _pytestmark(body: list[ast.stmt]) -> set[str]:
    """The markers a `pytestmark` assignment in this body applies."""
    values: list[ast.expr] = []
    for node in body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign | ast.AugAssign):
            targets = [node.target]
        else:
            continue
        if node.value is not None and any(
            isinstance(t, ast.Name) and t.id == "pytestmark" for t in targets
        ):
            values.append(node.value)
    return _markers(values)


def _matches(name: str, options: tuple[str, ...] | list[str]) -> bool:
    """pytest's prefix-or-glob test for a function or class name."""
    return any(
        name.startswith(opt) or (any(c in opt for c in "*?[") and fnmatch.fnmatch(name, opt))
        for opt in options
    )


def _untiered_items(tree: ast.Module, options: Mapping) -> list[str]:
    """The test functions and classes in a module that no tier marker reaches."""
    if _pytestmark(tree.body) & TIER_MARKERS:
        return []
    functions = options.get("python_functions", DEFAULT_PYTHON_FUNCTIONS)
    classes = options.get("python_classes", DEFAULT_PYTHON_CLASSES)
    missing: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and _matches(
            node.name, functions
        ):
            if not _markers(node.decorator_list) & TIER_MARKERS:
                missing.append(node.name)
        elif isinstance(node, ast.ClassDef) and _matches(node.name, classes):
            if (_markers(node.decorator_list) | _pytestmark(node.body)) & TIER_MARKERS:
                continue
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef) and _matches(
                    item.name, functions
                ) and not _markers(item.decorator_list) & TIER_MARKERS:
                    missing.append(f"{node.name}.{item.name}")
    return missing


def untiered_files(repo: Path, exceptions: Mapping[str, str]) -> dict[str, list[str]]:
    """Each test file no tier runs, with the tests in it no marker reaches."""
    options = _pytest_options(repo)
    found: dict[str, list[str]] = {}
    for path in _collected_test_files(repo):
        rel = path.relative_to(repo).as_posix()
        if rel.startswith("tests/unit/") or rel in exceptions:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        missing = _untiered_items(tree, options)
        if missing:
            found[rel] = missing
    return found


def assert_every_test_file_runs_in_a_tier(repo: Path, exceptions: Mapping[str, str]) -> None:
    found = untiered_files(repo, exceptions)
    assert not found, (
        "these test files run in no tier: CI runs tests/unit/ and the "
        f"{sorted(TIER_MARKERS)} markers, and none reaches them. Move the file "
        "into tests/unit/, mark every test in it with the tier it belongs to, or "
        "name it in NAMED_EXCEPTIONS with its reason (#4756):\n"
        + "\n".join(f"  {rel}: {', '.join(items)}" for rel, items in sorted(found.items()))
    )


def test_every_test_file_runs_in_a_tier():
    assert_every_test_file_runs_in_a_tier(REPO, NAMED_EXCEPTIONS)


def test_every_named_exception_still_exists():
    gone = [rel for rel in NAMED_EXCEPTIONS if not (REPO / rel).is_file()]
    assert gone == [], f"NAMED_EXCEPTIONS names files that are gone: {gone}"


def test_every_named_exception_has_a_reason():
    assert all(reason.strip() for reason in NAMED_EXCEPTIONS.values())


def _tree(root: Path, files: Mapping[str, str]) -> Path:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def test_an_unmarked_file_outside_the_unit_tier_fails_and_is_named(tmp_path):
    repo = _tree(tmp_path, {
        "tests/integration/test_x.py": "def test_one():\n    pass\n",
        "tests/unit/test_y.py": "def test_two():\n    pass\n",
    })
    with pytest.raises(AssertionError) as excinfo:
        assert_every_test_file_runs_in_a_tier(repo, {})
    message = str(excinfo.value)
    assert "tests/integration/test_x.py" in message
    assert "test_one" in message
    assert "tests/unit/test_y.py" not in message


def _src(*lines: str) -> str:
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("source", [
    _src("import pytest", "pytestmark = pytest.mark.integration",
         "def test_a():", "    pass"),
    _src("import pytest",
         "pytestmark = [pytest.mark.e2e, pytest.mark.skipif(True, reason='r')]",
         "def test_a():", "    pass"),
    _src("import pytest", "@pytest.mark.adversarial", "class TestA:",
         "    def test_a(self):", "        pass"),
    _src("import pytest", "class TestA:", "    pytestmark = pytest.mark.integration",
         "    def test_a(self):", "        pass"),
    _src("import pytest", "@pytest.mark.integration", "def test_a():", "    pass",
         "@pytest.mark.e2e", "def test_b():", "    pass"),
    _src("def helper():", "    pass"),
])
def test_a_tier_marker_in_any_position_passes(tmp_path, source):
    repo = _tree(tmp_path, {"tests/integration/test_x.py": source})
    assert untiered_files(repo, {}) == {}


@pytest.mark.parametrize("source, missing", [
    (_src("import pytest", "@pytest.mark.integration", "def test_a():", "    pass",
          "def test_b():", "    pass"), ["test_b"]),
    (_src("import pytest", "pytestmark = pytest.mark.benchmark",
          "def test_a():", "    pass"), ["test_a"]),
    (_src("import pytest", "class TestA:", "    @pytest.mark.e2e",
          "    def test_a(self):", "        pass",
          "    def test_b(self):", "        pass"), ["TestA.test_b"]),
])
def test_a_test_no_tier_marker_reaches_is_named(tmp_path, source, missing):
    repo = _tree(tmp_path, {"tests/integration/test_x.py": source})
    assert untiered_files(repo, {}) == {"tests/integration/test_x.py": missing}


def test_a_named_exception_passes(tmp_path):
    repo = _tree(tmp_path, {"tests/canary/test_c.py": "def test_c():\n    pass\n"})
    assert untiered_files(repo, {"tests/canary/test_c.py": "on purpose"}) == {}


def test_files_pytest_does_not_collect_are_skipped(tmp_path):
    unmarked = "def test_a():\n    pass\n"
    repo = _tree(tmp_path, {
        "tests/fixtures/sample.py": unmarked,
        "tests/fixtures/data/test_data.txt": unmarked,
        "tests/.hidden/test_h.py": unmarked,
        "tests/build/test_b.py": unmarked,
        "tests/ignored/test_i.py": unmarked,
        "tests/conftest.py": "collect_ignore = ['ignored']\n",
    })
    assert untiered_files(repo, {}) == {}


def test_a_conftest_this_check_cannot_read_stops_it(tmp_path):
    repo = _tree(tmp_path, {
        "tests/conftest.py": "collect_ignore = []\ncollect_ignore.append('x')\n",
    })
    with pytest.raises(UnreadableCollection):
        untiered_files(repo, {})
