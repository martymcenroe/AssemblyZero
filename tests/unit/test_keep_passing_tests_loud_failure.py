"""keep_passing_tests.py under standard 0034 (ADR 0236), the #3585 sweep.

Each function here decides which tests are the contract. When a side does not
parse, it used to return its input unchanged under a ``# fail-open:`` tag, and
a passing test whose class a patch deleted was dropped without a word. A
contract that cannot be decided is a failure: each now writes an ERROR line
naming what does not parse (or which tests were lost) and raises. Test names
carry ledger 0908's line numbers at its base ``79e18ad1``.
"""

from __future__ import annotations

import io
import tokenize
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.nodes.implementation import (
    keep_passing_tests as kpt,
)

VALID = "def test_a():\n    assert 1\n\n\ndef test_b():\n    assert 2\n"
BROKEN = "def test_a(:\n    assert 1\n"


def _loud(err: str, *needles: str) -> bool:
    return any(
        line.startswith("ERROR") and all(n in line for n in needles)
        for line in err.splitlines()
    )


class TestKeepPassingTestsAsWritten:
    def test_98_a_revision_that_does_not_parse_raises(self, capsys):
        with pytest.raises(SyntaxError):
            kpt.keep_passing_tests_as_written(
                VALID, BROKEN, {"test_a"}, path="tests/test_x.py",
            )

        assert _loud(capsys.readouterr().err, "tests/test_x.py", "revised text", "does not parse")

    def test_98_a_prior_text_that_does_not_parse_raises(self, capsys):
        with pytest.raises(SyntaxError):
            kpt.keep_passing_tests_as_written(
                BROKEN, VALID, {"test_a"}, path="tests/test_x.py",
            )

        assert _loud(capsys.readouterr().err, "tests/test_x.py", "prior text", "does not parse")

    def test_134_a_passing_test_whose_class_the_edit_deleted_raises(self, capsys):
        before = (
            "class TestA:\n    def test_kept(self):\n        assert 1\n\n"
            "    def test_gone(self):\n        assert 2\n"
        )
        after = "def test_other():\n    assert 3\n"

        with pytest.raises(ValueError, match="TestA.test_kept"):
            kpt.keep_passing_tests_as_written(
                before, after, {"test_kept"}, path="tests/test_x.py",
            )

        assert _loud(capsys.readouterr().err, "tests/test_x.py", "TestA.test_kept")

    def test_nothing_to_keep_returns_the_revision_untouched(self):
        """Kept: no passing set, or no change, is an answer, not a failure."""
        assert kpt.keep_passing_tests_as_written(VALID, BROKEN, set()).source == BROKEN
        assert kpt.keep_passing_tests_as_written(BROKEN, BROKEN, {"test_a"}).source == BROKEN

    def test_a_deleted_module_level_test_still_comes_back(self):
        """Kept: #2905's return of a deleted passing test."""
        kept = kpt.keep_passing_tests_as_written(
            VALID, "def test_b():\n    assert 2\n", {"test_a"},
        )
        assert kept.returned == ["test_a"]
        assert "def test_a" in kept.source


class TestReleaseSpecTwins:
    def test_172_a_spec_suite_that_does_not_parse_raises(self, capsys):
        with pytest.raises(SyntaxError):
            kpt.release_spec_twins({"test_a"}, BROKEN, path="tests/test_issue_7.py")

        assert _loud(capsys.readouterr().err, "tests/test_issue_7.py", "does not parse")

    def test_no_spec_suite_releases_nothing(self):
        """Kept: an empty suite defines no twins."""
        assert kpt.release_spec_twins({"test_a"}, "") == ({"test_a"}, set())


class TestAlignSpecTwins:
    def test_214_a_plan_file_that_does_not_parse_raises(self, capsys):
        with pytest.raises(SyntaxError):
            kpt.align_spec_twins(BROKEN, VALID, plan_path="tests/test_x.py")

        assert _loud(capsys.readouterr().err, "tests/test_x.py", "does not parse")

    def test_214_a_spec_suite_that_does_not_parse_raises(self, capsys):
        with pytest.raises(SyntaxError):
            kpt.align_spec_twins(VALID, BROKEN, spec_path="tests/test_issue_7.py")

        assert _loud(capsys.readouterr().err, "tests/test_issue_7.py", "does not parse")

    def test_no_spec_source_aligns_nothing(self):
        """Kept: no spec suite is nothing to align to."""
        assert kpt.align_spec_twins(VALID, "").source == VALID


def test_99_173_215_the_module_carries_no_fail_open_tag():
    source = Path(kpt.__file__).read_text(encoding="utf-8")
    tags = [
        tok.start[0]
        for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type == tokenize.COMMENT and "fail-open:" in tok.string
    ]
    assert tags == []
