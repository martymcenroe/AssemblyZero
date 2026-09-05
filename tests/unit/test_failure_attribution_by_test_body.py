"""A failure raised inside a test body is attributed by the names the test
uses (#2861).

`run-issue4-141013`, green-loop iteration 2, the two failures left:

    test_req_7
        tests/test_issue_4.py:100: in test_req_7
        assert len(calls) == 1
        E   assert 0 == 1

    test_req_8
        tests/test_issue_4.py:111: in test_req_8
        assert (time.process_time() - start) / 8.0 < 0.020
        E   AssertionError: ...

Both raise in the test itself, so the innermost frame is the test file and
the #2851 frame rule matches no planned file -- N4 printed `failures
attributed to no file by traceback` and every file received the whole corpus.
The test bodies say what they exercise: `WindowsCollector({})` and
`.collect()`. The planned files that define those names are the ones the
failures are about.

The repository here is a real temporary tree with the same shape: a test
file whose functions raise in their own bodies, two source files that define
`WindowsCollector`/`collect`, and a planned test file that defines only
`test_*` functions.
"""

import pytest

from assemblyzero.workflows.testing.nodes.implementation.edit_script_fix import (
    failures_for_file,
    is_attributed,
)

CORPUS = """\
test_req_7
    tests/test_issue_4.py:100: in test_req_7
    assert len(calls) == 1
    E   assert 0 == 1
    E    +  where 0 = len([])

test_req_8
    tests/test_issue_4.py:111: in test_req_8
    assert (time.process_time() - start) / 8.0 < 0.020
    E   AssertionError: assert ((3.84375 - 1.71875) / 8.0) < 0.02
"""

TEST_FILE = '''\
from boostgauge.collector import *  # noqa: F401, F403


def test_req_7(monkeypatch):
    import ctypes
    calls = []
    def mock_query(*args):
        calls.append(1)
        return 0
    monkeypatch.setattr(ctypes.windll.ntdll, "NtQuerySystemInformation", mock_query)
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
        return self._sweep()

    def _sweep(self):
        return (0, 0, 0, 0)
'''

COLLECTOR_PY = '''\
class DataCollector:
    def start(self):
        pass


class SystemSnapshot:
    pass
'''

PLANNED_TEST_PY = '''\
def test_collector_starts():
    assert True
'''


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "boostgauge" / "collectors").mkdir(parents=True)
    (tmp_path / "tests" / "test_issue_4.py").write_text(TEST_FILE, encoding="utf-8")
    (tmp_path / "tests" / "test_collector.py").write_text(PLANNED_TEST_PY, encoding="utf-8")
    (tmp_path / "src" / "boostgauge" / "collectors" / "windows.py").write_text(
        WINDOWS_PY, encoding="utf-8"
    )
    (tmp_path / "src" / "boostgauge" / "collector.py").write_text(
        COLLECTOR_PY, encoding="utf-8"
    )
    return tmp_path


class TestAttributionByWhatTheTestUses:
    def test_the_file_defining_the_class_the_test_constructs_is_attributed(self, repo):
        assert is_attributed(CORPUS, "src/boostgauge/collectors/windows.py", repo)

    def test_a_source_file_the_test_never_touches_is_not(self, repo):
        """collector.py defines DataCollector, SystemSnapshot and a `start`
        method. Neither test names the classes, and `start` in test_req_8 is
        a LOCAL the test assigns (`start = time.process_time()`) -- a name the
        test binds itself is not a reference to anything a planned file
        defines, and must not attribute one."""
        assert not is_attributed(CORPUS, "src/boostgauge/collector.py", repo)

    def test_a_planned_test_file_is_not_attributed_by_another_tests_body(self, repo):
        assert not is_attributed(CORPUS, "tests/test_collector.py", repo)

    def test_both_blocks_travel_to_the_attributed_file(self, repo):
        scoped = failures_for_file(CORPUS, "src/boostgauge/collectors/windows.py", repo)
        assert "test_req_7" in scoped and "test_req_8" in scoped
        assert "E   assert 0 == 1" in scoped

    def test_without_a_repo_root_the_frame_rule_stands_alone(self):
        """Callers that cannot read the tree keep #2851's behaviour exactly."""
        assert not is_attributed(CORPUS, "src/boostgauge/collectors/windows.py")
        assert failures_for_file(CORPUS, "src/boostgauge/collectors/windows.py") == CORPUS


class TestTheRuleStaysConservative:
    def test_a_short_common_name_does_not_attribute(self, repo):
        """`run`, `get`, `name` -- three letters or a bare attribute -- say
        nothing about which planned file a test exercises."""
        (repo / "src" / "boostgauge" / "misc.py").write_text(
            "def run():\n    pass\n\n\ndef len():\n    pass\n", encoding="utf-8"
        )
        assert not is_attributed(CORPUS, "src/boostgauge/misc.py", repo)

    def test_a_block_whose_frame_is_not_a_test_uses_the_frame_rule_only(self, repo):
        corpus = (
            "test_x\n"
            "    src/boostgauge/collector.py:12: in start\n"
            "    raise ValueError\n"
            "    E   ValueError"
        )
        assert is_attributed(corpus, "src/boostgauge/collector.py", repo)
        assert not is_attributed(corpus, "src/boostgauge/collectors/windows.py", repo)

    def test_an_unparseable_planned_file_attributes_nothing(self, repo):
        (repo / "src" / "boostgauge" / "broken.py").write_text(
            "def (:\n", encoding="utf-8"
        )
        assert not is_attributed(CORPUS, "src/boostgauge/broken.py", repo)

    def test_a_missing_test_file_attributes_nothing(self, repo):
        corpus = CORPUS.replace("tests/test_issue_4.py", "tests/test_gone.py")
        assert not is_attributed(corpus, "src/boostgauge/collectors/windows.py", repo)


class TestTheFrameRuleStillWinsFirst:
    def test_a_src_frame_attributes_without_reading_any_test(self, repo, monkeypatch):
        """The identifier rule is consulted only for blocks the frame rule
        left unattributed; a block the frame names must not depend on the
        test file being readable."""
        corpus = (
            "test_req_4\n"
            "    src/boostgauge/collector.py:116: in _is_unleashed_session\n"
            "    return 'unleashed' in name\n"
            "    E   TypeError: argument of type 'int' is not a container"
        )
        (repo / "tests" / "test_issue_4.py").unlink()
        assert is_attributed(corpus, "src/boostgauge/collector.py", repo)
