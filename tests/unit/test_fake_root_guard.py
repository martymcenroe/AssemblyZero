"""The fake-root guard refuses a test's write into a fake absolute root and
fails the session that made it (#4706).

On Windows a fake absolute path is a real folder at the root of the drive:
``/nonexistent`` is ``C:\\nonexistent``, where 785 test drafts were found on
2026-11-11. ``tests/fake_root_guard.py`` says why the guard is an audit hook.

Nothing here writes into a real fake root. The session tests run a child
pytest whose guard watches a folder under this test's tmp_path; the armed
check raises the audit event by hand with ``sys.audit``, which touches no
file whether the hook is armed or not.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests import fake_root_guard as guard

CHECKOUT = Path(__file__).resolve().parents[2]


def _roots(*paths: Path) -> tuple[tuple[str, bool], ...]:
    return tuple((guard.normalize(str(path)), True) for path in paths)


class TestWhatCountsAsAWrite:
    @pytest.mark.parametrize("mode", ["w", "wb", "a", "x", "r+", "rb+"])
    def test_an_open_for_writing_is_a_write(self, mode):
        assert guard.written_paths("open", ("/fake/x", mode, 0)) == ("/fake/x",)

    @pytest.mark.parametrize("mode", ["r", "rb", "rt"])
    def test_an_open_for_reading_is_not(self, mode):
        assert guard.written_paths("open", ("/fake/x", mode, 0)) == ()

    def test_os_open_is_judged_by_its_flags(self):
        flags = os.O_WRONLY | os.O_CREAT
        assert guard.written_paths("open", ("/fake/x", None, flags)) == ("/fake/x",)
        assert guard.written_paths("open", ("/fake/x", None, os.O_RDONLY)) == ()

    def test_a_copy_writes_its_destination_only(self):
        assert guard.written_paths("shutil.copyfile", ("/src", "/fake/dst")) == ("/fake/dst",)

    def test_a_rename_changes_both_ends(self):
        event = ("/fake/a", "/elsewhere/b", None, None)
        assert guard.written_paths("os.rename", event) == ("/fake/a", "/elsewhere/b")

    def test_mkdir_and_remove_change_their_path(self):
        assert guard.written_paths("os.mkdir", ("/fake/d", 0o777, None)) == ("/fake/d",)
        assert guard.written_paths("os.remove", ("/fake/f", None)) == ("/fake/f",)

    def test_an_event_that_changes_nothing(self):
        assert guard.written_paths("os.listdir", ("/fake",)) == ()
        assert guard.written_paths("os.scandir", ("/fake",)) == ()


class TestWhichPathsAreLeaks:
    def test_a_path_inside_a_root_is_a_leak(self, tmp_path):
        roots = _roots(tmp_path / "fake")
        assert guard.is_leak(guard.normalize(str(tmp_path / "fake" / "a" / "b.md")), roots)

    def test_the_root_itself_is_a_leak(self, tmp_path):
        roots = _roots(tmp_path / "fake")
        assert guard.is_leak(guard.normalize(str(tmp_path / "fake")), roots)

    def test_a_path_that_only_shares_a_prefix_is_not(self, tmp_path):
        roots = _roots(tmp_path / "fake")
        assert not guard.is_leak(guard.normalize(str(tmp_path / "fakeroot" / "x")), roots)

    def test_a_children_only_root_lets_the_root_itself_be(self):
        roots = ((guard.normalize("/dev/null"), False),)
        assert not guard.is_leak(guard.normalize("/dev/null"), roots)
        assert guard.is_leak(guard.normalize("/dev/null/impossible/x.log"), roots)

    def test_an_allowed_store_inside_a_root_is_not(self, tmp_path):
        roots = _roots(tmp_path / "tmp")
        allowed = (guard.normalize(str(tmp_path / "tmp" / "store")),)
        path = guard.normalize(str(tmp_path / "tmp" / "store" / "x"))
        assert not guard.is_leak(path, roots, allowed)

    def test_a_relative_path_or_a_descriptor_is_never_judged(self):
        assert guard.normalize("data/x.jsonl") is None
        assert guard.normalize(3) is None
        assert guard.normalize(None) is None


class TestTheRootsOnEachPlatform:
    def test_ubuntu_watches_the_named_roots_and_leaves_its_temp_alone(self):
        roots = dict(guard.roots_for_this_machine(on_windows=False))
        for spelled in ("/tmp/repo", "/tmp/audit", "/tmp/test_project",
                        "/nonexistent", "/fake", "/path"):
            assert roots[guard.normalize(spelled)] is True, spelled
        # /dev/null itself is the null device on Ubuntu; only below it is a leak.
        assert roots[guard.normalize("/dev/null")] is False
        # /tmp is where pytest's own tmp_path and tempfile write on Ubuntu.
        assert guard.normalize("/tmp") not in roots
        assert guard.normalize("/dev") not in roots

    def test_windows_watches_all_of_tmp_and_dev(self):
        roots = dict(guard.roots_for_this_machine(on_windows=True))
        for spelled in ("/tmp", "/dev", "/dev/null", "/tmp/repo", "/nonexistent", "/fake", "/path"):
            assert roots[guard.normalize(spelled)] is True, spelled


@pytest.mark.windows_paths
def test_this_suite_runs_with_the_guard_armed(request):
    """The suite's own guard watches this machine's roots and refuses a write.

    Marked ``windows_paths``: on Windows the roots are folders at the drive
    root, which is where the leaks landed, so the Windows job runs it too.

    ``sys.audit`` raises the event by hand, so the probe reaches no file
    whether the hook is armed or not; the probe's record is this test's own and
    is taken back off, so the session does not fail on it.
    """
    assert guard.installed()
    assert guard.armed_roots() == guard.roots_for_this_machine()
    before = len(guard.RECORDS)
    with pytest.raises(PermissionError, match="#4706"):
        sys.audit("open", "/nonexistent/fake-root-guard-probe.md", "w", 0)
    probe = guard.RECORDS[before:]
    del guard.RECORDS[before:]
    assert probe == [
        (request.node.nodeid, "open", guard.normalize("/nonexistent/fake-root-guard-probe.md"))
    ]


INNER_CONFTEST = """
import sys

sys.path.insert(0, {checkout!r})

from tests import fake_root_guard


def pytest_sessionstart(session):
    fake_root_guard.install(roots=[(fake_root_guard.normalize({root!r}), True)])


def pytest_runtest_logstart(nodeid, location):
    fake_root_guard.enter(nodeid)


def pytest_runtest_logfinish(nodeid, location):
    fake_root_guard.leave()


def pytest_sessionfinish(session, exitstatus):
    fake_root_guard.fail_session_on_leaks(session)
"""

LEAKING_TEST = """
from pathlib import Path


def test_writes_into_the_fake_root():
    try:
        Path({target!r}).write_text("leak", encoding="utf-8")
    except PermissionError:
        pass  # swallowed, as code under test may; the session must still fail
"""

CLEAN_TEST = """
from pathlib import Path


def test_reads_the_fake_root_and_writes_its_own(tmp_path):
    assert not Path({target!r}).exists()
    (tmp_path / "own.txt").write_text("fine", encoding="utf-8")
"""


def _inner_session(tmp_path: Path, body: str) -> tuple[subprocess.CompletedProcess, Path]:
    root = tmp_path / "fake-root"
    root.mkdir()
    target = root / "leak.txt"
    inner = tmp_path / "inner"
    inner.mkdir()
    (inner / "conftest.py").write_text(
        INNER_CONFTEST.format(checkout=str(CHECKOUT), root=str(root)), encoding="utf-8"
    )
    (inner / "test_inner.py").write_text(body.format(target=str(target)), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(inner)],
        cwd=inner,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,  # the exit code is the verdict under test
    )
    return result, target


def test_a_write_into_a_fake_root_fails_the_session_and_reaches_no_disk(tmp_path):
    result, target = _inner_session(tmp_path, LEAKING_TEST)
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert guard.HEADLINE in output
    assert "test_inner.py::test_writes_into_the_fake_root" in output
    assert guard.normalize(str(target)) in output
    assert "1 passed" in output, "the test itself passed; the session is what fails"
    assert not target.exists(), "the refused write reached the disk"


def test_a_session_that_only_reads_the_root_passes(tmp_path):
    result, _target = _inner_session(tmp_path, CLEAN_TEST)
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert guard.HEADLINE not in output
