"""A name bound under a module-level `if` is exported (#2895).

boostgauge #4, `run-issue4-014544` (2026-09-06 01:45): the first fully green
measurement of the campaign -- 38 of 38 at 91 % -- and N4c set out to close
the 4-point gap to the 95 % target:

    [LLM] provider=claude model=opus ... output=50126 ... duration=795.9s
    [N4c] rejected: boostgauge.collector has no 'WindowsCollector'. Did you mean: DataCollector?
    [N4c] revising (attempt 2/2)
    [N4c] rejected: boostgauge.collector has no 'WindowsCollector'. Did you mean: DataCollector?
    [N4c] 2 attempt(s) did not produce importable tests; suite left unchanged

boostgauge.collector HAS WindowsCollector -- the scaffold's own red-phase
import takes it from there and passes in the same measurement. The module
binds it the way LLD-004 s2.5 asks, by platform:

    if sys.platform == "win32":
        from boostgauge.collectors.windows import WindowsCollector

`exported_names` walked `tree.body` and recorded only what sat directly at
the top level. A binding inside a module-level `if` is in the `If` node's
body, not in `tree.body`, and the scan never looked there. Thirteen minutes
and $1.47 of generation went into the bin on a correct import.

Every case here uses a real file on disk and the public functions, the way
N4c does.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.workflows.testing.symbol_validator import (
    exported_names,
    validate_test_imports,
)

# collector.py as run 32 left it, reduced to its bindings.
RUN_32_COLLECTOR = '''\
"""Abstract collector and platform dispatch."""
from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Band:
    lo: float
    hi: float


def normalize(value: float, band: Band) -> float:
    return 0.0


def _psutil_cmdline(proc) -> list[str]:
    return []


class DataCollector:
    def collect(self):
        raise NotImplementedError


if sys.platform == "win32":
    from boostgauge.collectors.windows import WindowsCollector


def make_collector(thresholds=None) -> DataCollector:
    if sys.platform == "win32":
        from boostgauge.collectors.windows import WindowsCollector as _Impl
        chosen = _Impl(thresholds)
        return chosen
    raise NotImplementedError(f"Platform {sys.platform} not supported")
'''


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    pkg = tmp_path / "src" / "boostgauge"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "collector.py").write_text(RUN_32_COLLECTOR, encoding="utf-8")
    return tmp_path


def _module(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "mod.py"
    path.write_text(source, encoding="utf-8")
    return path


class TestRun32sCollector:
    def test_windows_collector_is_exported(self, repo: Path):
        names = exported_names(repo / "src" / "boostgauge" / "collector.py")

        assert "WindowsCollector" in names

    def test_the_rest_of_the_module_is_still_seen(self, repo: Path):
        names = exported_names(repo / "src" / "boostgauge" / "collector.py")

        assert {"Band", "normalize", "_psutil_cmdline", "DataCollector", "make_collector"} <= names

    def test_a_function_body_binding_is_not_exported(self, repo: Path):
        """`_Impl` and `chosen` live inside make_collector."""
        names = exported_names(repo / "src" / "boostgauge" / "collector.py")

        assert "_Impl" not in names
        assert "chosen" not in names

    def test_n4cs_import_is_accepted(self, repo: Path):
        test_source = (
            "from boostgauge.collector import WindowsCollector, DataCollector\n"
            "\n"
            "def test_it():\n"
            "    assert WindowsCollector\n"
        )

        assert validate_test_imports(test_source, repo) == []

    def test_a_near_miss_is_still_refused_with_its_hint(self, repo: Path):
        """#2336's case survives: the validator still catches a wrong name."""
        test_source = "from boostgauge.collector import DataCollecter\n"

        problems = validate_test_imports(test_source, repo)

        assert len(problems) == 1
        assert "has no 'DataCollecter'" in problems[0]
        assert "DataCollector" in problems[0]


class TestCompoundStatements:
    def test_try_except_else_finally(self, tmp_path: Path):
        names = exported_names(_module(tmp_path, (
            "try:\n"
            "    from fast import impl\n"
            "except ImportError as missing:\n"
            "    from slow import impl\n"
            "else:\n"
            "    ready = True\n"
            "finally:\n"
            "    checked = True\n"
        )))

        assert {"impl", "missing", "ready", "checked"} <= names

    def test_with_and_for_and_while(self, tmp_path: Path):
        names = exported_names(_module(tmp_path, (
            "with open('x') as handle:\n"
            "    content = handle.read()\n"
            "for index, item in enumerate(()):\n"
            "    last = item\n"
            "while False:\n"
            "    never = 1\n"
        )))

        assert {"handle", "content", "index", "item", "last", "never"} <= names

    def test_nested_compound_statements(self, tmp_path: Path):
        names = exported_names(_module(tmp_path, (
            "import sys\n"
            "if sys.platform == 'win32':\n"
            "    try:\n"
            "        from a import Deep\n"
            "    except ImportError:\n"
            "        Deep = None\n"
            "else:\n"
            "    Deep = None\n"
        )))

        assert "Deep" in names

    def test_tuple_targets_and_augmented_assignment(self, tmp_path: Path):
        names = exported_names(_module(tmp_path, (
            "first, (second, *rest) = 1, (2, 3)\n"
            "total = 0\n"
            "total += 1\n"
        )))

        assert {"first", "second", "rest", "total"} <= names

    def test_a_class_body_is_not_module_level(self, tmp_path: Path):
        names = exported_names(_module(tmp_path, (
            "class Holder:\n"
            "    inner = 1\n"
            "    if True:\n"
            "        also_inner = 2\n"
        )))

        assert "Holder" in names
        assert "inner" not in names
        assert "also_inner" not in names

    def test_an_unparseable_module_is_still_none(self, tmp_path: Path):
        assert exported_names(_module(tmp_path, "def broken(:\n")) is None
