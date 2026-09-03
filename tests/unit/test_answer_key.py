"""The answer-key audit (#2722): the gates run over code known to be right.

Driven against a synthetic repo so the suite does not depend on boostgauge
being checked out beside this one.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = REPO_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import answer_key_audit as cli  # noqa: E402

from assemblyzero.core.gate_registry import (  # noqa: E402
    JUDGES_MODEL_OUTPUT,
    JUDGES_UPSTREAM,
    registry_by_key,
)
from assemblyzero.speedrun.answer_key import (  # noqa: E402
    BOOSTGAUGE_ARC,
    NOT_RUNNABLE_HERE,
    RUNNABLE_GATES,
    Feature,
    audit,
    render,
)

GOOD_SOURCE = '''"""A module."""

from __future__ import annotations


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def sub(a: int, b: int) -> int:
    return a - b
'''

GOOD_TEST = '''"""Tests."""

from __future__ import annotations

import pytest

from widget.core import add


def test_add():
    assert add(1, 2) == 3


def test_add_raises_on_none():
    with pytest.raises(TypeError):
        add(None, 1)
'''

STUB_TEST = '''"""Stubs."""

import pytest


def test_one():
    pass


def test_two():
    """TODO"""
'''


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(repo), check=True,
                   capture_output=True, text=True)


@pytest.fixture()
def answer_repo(tmp_path) -> Path:
    repo = tmp_path / "widget"
    (repo / "src" / "widget").mkdir(parents=True)
    (repo / "tests" / "unit").mkdir(parents=True)
    (repo / "src" / "widget" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "src" / "widget" / "core.py").write_text(GOOD_SOURCE, encoding="utf-8")
    (repo / "tests" / "unit" / "test_core.py").write_text(GOOD_TEST, encoding="utf-8")
    (repo / "tests" / "unit" / "test_stubs.py").write_text(STUB_TEST, encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
         "-m", "feat: the core (Closes #9)")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
         "--allow-empty", "-m", "feat: stubs, closes nothing")
    return repo


ARC = (
    Feature(9, "the core", ("src/widget/core.py",), ("tests/unit/test_core.py",)),
    Feature(10, "stubs", (), ("tests/unit/test_stubs.py",)),
    Feature(11, "missing", ("src/widget/nope.py",), ()),
)


class TestTheGateListIsHonest:
    def test_every_runnable_gate_is_registered_and_judges_a_draft(self):
        keys = registry_by_key()
        for gate, _ in RUNNABLE_GATES:
            assert gate in keys, gate
            assert keys[gate].judges in (JUDGES_MODEL_OUTPUT, JUDGES_UPSTREAM), (
                f"{gate} judges {keys[gate].judges}; an answer key cannot speak to that"
            )

    def test_every_not_runnable_gate_is_registered(self):
        keys = registry_by_key()
        for gate, reason in NOT_RUNNABLE_HERE:
            assert gate in keys, gate
            assert reason

    def test_runnable_and_not_runnable_do_not_overlap(self):
        assert not {g for g, _ in RUNNABLE_GATES} & {g for g, _ in NOT_RUNNABLE_HERE}

    def test_the_arc_names_six_features_with_files(self):
        assert [f.issue for f in BOOSTGAUGE_ARC] == [4, 41, 332, 7, 2, 5]
        for feature in BOOSTGAUGE_ARC:
            assert feature.sources and feature.tests, feature.issue


class TestAudit:
    def test_good_code_passes_every_gate(self, answer_repo):
        verdicts, coverage = audit(answer_repo, ARC[:1])
        assert coverage.files_examined == 2
        assert coverage.commits_examined == 1
        refused = [v for v in verdicts if v.refused]
        assert not refused, [(v.gate, v.message) for v in refused]
        gates = {v.gate for v in verdicts}
        assert gates == {
            "impl.file_generation_failed", "impl.test_file_validation",
            "impl.deterministic_failure", "pr.commit_message_guard",
        }

    def test_stub_tests_are_refused_by_the_scaffolder_gates(self, answer_repo):
        verdicts, _ = audit(answer_repo, ARC[1:2])
        refused = {v.gate for v in verdicts if v.refused}
        assert "impl.test_file_validation" in refused
        assert "impl.deterministic_failure" in refused
        stub = next(v for v in verdicts if v.gate == "impl.deterministic_failure")
        assert "2 of 2" in stub.message

    def test_a_commit_without_the_close_is_refused(self, answer_repo):
        verdicts, coverage = audit(answer_repo, ARC[1:2])
        # No commit on main carries "Closes #10", so the guard never ran.
        assert coverage.commits_examined == 0
        assert not [v for v in verdicts if v.gate == "pr.commit_message_guard"]

    def test_missing_files_are_counted_not_skipped_silently(self, answer_repo):
        _, coverage = audit(answer_repo, ARC[2:3])
        assert coverage.files_missing == ["src/widget/nope.py"]
        assert coverage.files_examined == 0

    def test_a_target_that_is_not_a_git_checkout_is_counted(self, tmp_path):
        plain = tmp_path / "plain"
        (plain / "src" / "widget").mkdir(parents=True)
        (plain / "src" / "widget" / "core.py").write_text(GOOD_SOURCE, encoding="utf-8")
        verdicts, coverage = audit(plain, ARC[:1])
        assert coverage.git_unreadable == 1
        assert coverage.commits_examined == 0
        assert not [v for v in verdicts if v.gate == "pr.commit_message_guard"]
        text = render(plain, verdicts, coverage, generated_at="x")
        assert "git unreadable for 1 feature(s)" in text


class TestRender:
    def test_names_the_denominator_and_each_refusal(self, answer_repo):
        verdicts, coverage = audit(answer_repo, ARC)
        text = render(answer_repo, verdicts, coverage, generated_at="2026-09-03 01:00:00")
        assert "Files examined: 3 (missing: src/widget/nope.py)" in text
        assert "| impl.deterministic_failure | 2 | 1 |" in text
        assert "#10 `impl.deterministic_failure` on `tests/unit/test_stubs.py`" in text
        assert "## Not runnable against a finished artifact" in text

    def test_is_deterministic_for_a_fixed_stamp(self, answer_repo):
        verdicts, coverage = audit(answer_repo, ARC)
        a = render(answer_repo, verdicts, coverage, generated_at="x")
        b = render(answer_repo, verdicts, coverage, generated_at="x")
        assert a == b


class TestCli:
    def test_missing_repo_is_reported(self, tmp_path, capsys):
        assert cli.main(["--repo", str(tmp_path / "nope")]) == 2
        assert "No such repository" in capsys.readouterr().out

    def test_default_save_path(self):
        from datetime import datetime

        path = cli.default_save_path(Path("/c/x/boostgauge"), datetime(2026, 9, 3))
        assert path.name == "0907-answer-key-audit-boostgauge-2026-09-03.md"
