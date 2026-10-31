"""edit_script_fix.py under standard 0034 (ADR 0236), the #3585 sweep.

The test-body attribution rule (#2861) reads a planned file for the names it
defines and a test file for the names a test uses. Either read failing used
to return no names under a ``# fail-open:`` tag, so the block stayed
unattributed and the file could be left unchanged for an iteration on a
guess. Each read that cannot answer now writes an ERROR line naming the file
and raises. A file that is not on disk, or a planned file that is not Python,
defines nothing this rule can see: that is an answer, and stays quiet.

Ledger rows 497, 503 and 507 of this module are a fallback the orchestrator
takes; their tests are in ``test_orchestrator_loud_failure.py``. Test names
carry ledger 0908's line numbers at its base ``79e18ad1``.
"""

from __future__ import annotations

import io
import tokenize
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.nodes.implementation import edit_script_fix
from assemblyzero.workflows.testing.nodes.implementation.edit_script_fix import (
    is_attributed,
)

# The failure raises in the test's own body, so the frame rule matches no
# planned file and the test-body rule reads both files.
CORPUS = """\
test_req_1
    tests/test_issue_4.py:5: in test_req_1
    assert Sweeper().run_sweep() == 1
    E   assert 0 == 1
"""
TEST_FILE = "from pkg.collector import Sweeper\n\n\ndef test_req_1():\n    assert Sweeper().run_sweep() == 1\n"
PLANNED = "class Sweeper:\n    def run_sweep(self):\n        return 0\n"


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "pkg" / "collector.py").write_text(PLANNED, encoding="utf-8")
    (tmp_path / "tests" / "test_issue_4.py").write_text(TEST_FILE, encoding="utf-8")
    return tmp_path


@pytest.fixture
def unreadable(monkeypatch):
    """Make named paths raise PermissionError on read, on every platform."""
    blocked: set[str] = set()
    real = Path.read_text

    def read_text(self, *args, **kwargs):
        if str(Path(self).resolve()) in blocked:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    return lambda path: blocked.add(str(Path(path).resolve()))


def _loud(err: str, *needles: str) -> bool:
    return any(
        line.startswith("ERROR") and all(n in line for n in needles)
        for line in err.splitlines()
    )


def test_the_rule_attributes_when_both_files_read(repo):
    """Kept: the #2861 rule itself."""
    assert is_attributed(CORPUS, "src/pkg/collector.py", repo)


class TestAPlannedFileThatCannotBeRead:
    def test_273_an_unreadable_planned_file_raises(self, repo, unreadable, capsys):
        unreadable(repo / "src" / "pkg" / "collector.py")

        with pytest.raises(PermissionError):
            is_attributed(CORPUS, "src/pkg/collector.py", repo)

        assert _loud(capsys.readouterr().err, "collector.py", "could not read")

    def test_273_a_planned_python_file_that_does_not_parse_raises(self, repo, capsys):
        (repo / "src" / "pkg" / "collector.py").write_text("def (:\n", encoding="utf-8")

        with pytest.raises(SyntaxError):
            is_attributed(CORPUS, "src/pkg/collector.py", repo)

        assert _loud(capsys.readouterr().err, "collector.py", "does not parse")

    def test_a_planned_file_not_on_disk_defines_nothing(self, repo):
        """Kept: absence is an answer -- an unwritten file defines no names."""
        assert not is_attributed(CORPUS, "src/pkg/not_written.py", repo)

    def test_a_planned_file_that_is_not_python_defines_nothing(self, repo):
        """Kept: the rule reads Python; a TypeScript file is not a failure of it."""
        (repo / "src" / "pkg" / "widget.ts").write_text("export class Sweeper {}\n", encoding="utf-8")
        assert not is_attributed(CORPUS, "src/pkg/widget.ts", repo)


class TestATestFileThatCannotBeRead:
    def test_303_an_unreadable_test_file_raises(self, repo, unreadable, capsys):
        unreadable(repo / "tests" / "test_issue_4.py")

        with pytest.raises(PermissionError):
            is_attributed(CORPUS, "src/pkg/collector.py", repo)

        assert _loud(capsys.readouterr().err, "test_issue_4.py", "could not read")

    def test_303_a_test_file_that_does_not_parse_raises(self, repo, capsys):
        (repo / "tests" / "test_issue_4.py").write_text("def test_req_1(:\n", encoding="utf-8")

        with pytest.raises(SyntaxError):
            is_attributed(CORPUS, "src/pkg/collector.py", repo)

        assert _loud(capsys.readouterr().err, "test_issue_4.py", "does not parse")

    def test_a_test_file_not_on_disk_attributes_nothing(self, repo):
        """Kept: a frame naming a file that is not under repo_root says nothing."""
        (repo / "tests" / "test_issue_4.py").unlink()
        assert not is_attributed(CORPUS, "src/pkg/collector.py", repo)


def test_273_303_the_module_carries_no_fail_open_tag():
    source = Path(edit_script_fix.__file__).read_text(encoding="utf-8")
    tags = [
        tok.start[0]
        for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type == tokenize.COMMENT and "fail-open:" in tok.string
    ]
    assert tags == []
