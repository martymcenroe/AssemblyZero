"""A method name attributes a planned file only when its class is used too
(#2865).

`run-issue4-151141`, iteration 3:

    [N4] failures attributed to 4 of 6 file(s): src/boostgauge/collector.py,
    src/boostgauge/collectors/windows.py,
    tests/benchmark/test_windows_collector_bench.py, tests/unit/test_collector.py

The two source files were right: they define `WindowsCollector`, which the
failing tests construct. The two test files were wrong: each defines a test
double, `DummyCollector`, with a `collect` method, and the failing tests call
`collector.collect()`. #2861 counted a method of a top-level class as a
defined name, so a method name shared with a double attributed the double's
file. Six files became four instead of two.

The rule now: a top-level class or function the test uses attributes the
file that defines it; a METHOD name is evidence only when the class that
defines it is itself among the names the test uses.
"""

import pytest

from assemblyzero.workflows.testing.nodes.implementation.edit_script_fix import (
    is_attributed,
)

CORPUS = """\
test_req_7
    tests/test_issue_4.py:100: in test_req_7
    assert len(calls) == 1
    E   assert 0 == 1

test_req_8
    tests/test_issue_4.py:111: in test_req_8
    assert (time.process_time() - start) / 8.0 < 0.020
    E   AssertionError: assert ((3.84375 - 1.71875) / 8.0) < 0.02
"""

TEST_FILE = '''\
def test_req_7(monkeypatch):
    calls = []
    collector = WindowsCollector({})
    collector.collect()
    assert len(calls) == 1


def test_req_8():
    import time
    collector = WindowsCollector({})
    collector.collect()
    start = time.process_time()
    for _ in range(8):
        collector.collect()
    assert (time.process_time() - start) / 8.0 < 0.020
'''

WINDOWS_PY = '''\
class WindowsCollector:
    def collect(self):
        return 0
'''

# The shape from the run: a test double with the same method name.
BENCH_PY = '''\
class DummyCollector:
    def __init__(self, config=None):
        self.config = config

    def collect(self):
        return 0

    def _read_cmdline_safe(self, pid):
        return []


def test_bench_collect_is_cheap():
    assert DummyCollector().collect() == 0
'''

# A double whose CLASS the failing test also names.
USED_DOUBLE_PY = '''\
class WindowsCollector:
    """A stand-in with the production name; a test that constructs
    WindowsCollector is exercising whichever file defines it."""

    def collect(self):
        return 0
'''


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "tests" / "benchmark").mkdir(parents=True)
    (tmp_path / "src" / "boostgauge" / "collectors").mkdir(parents=True)
    (tmp_path / "tests" / "test_issue_4.py").write_text(TEST_FILE, encoding="utf-8")
    (tmp_path / "tests" / "benchmark" / "test_windows_collector_bench.py").write_text(
        BENCH_PY, encoding="utf-8"
    )
    (tmp_path / "src" / "boostgauge" / "collectors" / "windows.py").write_text(
        WINDOWS_PY, encoding="utf-8"
    )
    (tmp_path / "tests" / "conftest_double.py").write_text(USED_DOUBLE_PY, encoding="utf-8")
    return tmp_path


class TestMethodNamesNeedTheirClass:
    def test_a_double_sharing_only_a_method_name_is_not_attributed(self, repo):
        assert not is_attributed(
            CORPUS, "tests/benchmark/test_windows_collector_bench.py", repo
        )

    def test_the_file_defining_the_constructed_class_still_is(self, repo):
        assert is_attributed(CORPUS, "src/boostgauge/collectors/windows.py", repo)

    def test_a_file_whose_class_the_test_names_is_attributed_through_it(self, repo):
        """Same method name, but this file's class is the one the test
        constructs -- the method is evidence because its class is used."""
        assert is_attributed(CORPUS, "tests/conftest_double.py", repo)


class TestTopLevelFunctionsStillCount:
    def test_a_top_level_function_the_test_calls_attributes(self, repo):
        (repo / "src" / "boostgauge" / "helpers.py").write_text(
            "def process_time():\n    return 0.0\n", encoding="utf-8"
        )
        # `process_time` is used as an attribute of `time` in the test; the
        # helper defines it at top level. Attribute use of a top-level name
        # still counts -- the rule tightened METHODS, not functions.
        assert is_attributed(CORPUS, "src/boostgauge/helpers.py", repo)
