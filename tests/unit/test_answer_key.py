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
        """What this audit needs is a gate whose CHECK reads a shipped
        artifact. Until #2723 that was the same set as `judges in
        (model_output, upstream_artifact)`, and the test read the column as
        "what the check inspects".

        The 2026-09-04 ruling separated the two. `judges` now records who owns
        the HALT: for a gate that revises to its cap, the cap owns it, so
        `lld.mechanical_validation` and `impl.file_generation_failed` are
        `budget` while still inspecting exactly the drafts and files they
        always did. Reading the column the old way would have retired two
        runnable gates -- 18 of the audit's 50 verdicts -- to keep a test
        green, which is the audit losing coverage to make a number tidy.

        So a #2723-reclassified row is admitted BY THAT RULING and nothing
        else. A gate that merely judges a budget -- a cost cap, a wall clock --
        has no `justified_by` of #2723 and is still rejected, because an
        answer key genuinely cannot speak to it.
        """
        keys = registry_by_key()
        for gate, _ in RUNNABLE_GATES:
            assert gate in keys, gate
            row = keys[gate]
            reclassified_by_ruling = row.justified_by == "#2723"
            assert (
                row.judges in (JUDGES_MODEL_OUTPUT, JUDGES_UPSTREAM)
                or reclassified_by_ruling
            ), (
                f"{gate} judges {row.judges} and carries no #2723 ruling; an "
                f"answer key cannot speak to that"
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
        refused = [v for v in verdicts if v.refused]
        assert not refused, [(v.gate, v.message) for v in refused]
        gates = {v.gate for v in verdicts}
        # `pr.commit_message_guard` was the fourth member here until #2787
        # retired it: no graph runs the function its sites lived in, so the
        # verdicts it contributed measured a check no run performs.
        assert gates == {
            "impl.file_generation_failed", "impl.scaffold_suite_invalid",
            "impl.deterministic_failure",
        }

    def test_stub_tests_are_refused_by_the_scaffolder_gates(self, answer_repo):
        verdicts, _ = audit(answer_repo, ARC[1:2])
        refused = {v.gate for v in verdicts if v.refused}
        assert "impl.scaffold_suite_invalid" in refused
        assert "impl.deterministic_failure" in refused
        stub = next(v for v in verdicts if v.gate == "impl.deterministic_failure")
        assert "2 of 2" in stub.message

    # #2787 removed `test_a_commit_without_the_close_is_refused` and
    # `test_a_target_that_is_not_a_git_checkout_is_counted`. Both exercised
    # the merged-commit-subject arm, which was read only to score
    # `pr.commit_message_guard`. That gate is retired -- no graph runs it --
    # so the reader, its two coverage counters and the report line for them
    # went with it, and there is nothing left for either test to assert.

    def test_missing_files_are_counted_not_skipped_silently(self, answer_repo):
        _, coverage = audit(answer_repo, ARC[2:3])
        assert coverage.files_missing == ["src/widget/nope.py"]
        assert coverage.files_examined == 0



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
