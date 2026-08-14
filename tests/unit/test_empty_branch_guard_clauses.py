"""A guard clause is not an empty branch (#2340).

N4b's Layer 1 AST analysis reported, against the `config.py` the pipeline
generated for run-issue7-192332:

    empty_branch: Empty 'if' branch at line 83 -- body contains only
    pass/return None

Line 83 is::

    if not hand_changed_keys:
        return

An idiomatic early return, and exactly what the spec's "no hand changes
leaves the file byte-identical" requirement (T080) asks for. Most generated
files carry one, so the check fired on ordinary code and its warnings came to
mean nothing.

A check that fires on idiomatic code is worse than no check. It trains the
reader to skim past the line where a real finding would appear, which is why
this warning rode along un-acted-on for so long: it was not actionable.

The generated file is frozen at `tests/fixtures/issue7_run192332/`, so the
acceptance criterion is asserted against the artifact rather than against a
reconstruction of it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.workflows.testing.completeness import ast_analyzer as A
from assemblyzero.workflows.testing.completeness.ast_analyzer import (
    analyze_empty_branches,
)

ROOT = Path(__file__).resolve().parents[2]
GENERATED_CONFIG = ROOT / "tests" / "fixtures" / "issue7_run192332" / "generated_config.py"


def kinds(source: str) -> list[int]:
    """Line numbers of every empty-branch finding."""
    out = []
    for issue in analyze_empty_branches(source, "t.py"):
        data = issue if isinstance(issue, dict) else issue.__dict__
        out.append(data["line_number"])
    return out


class TestTheRealArtifact:
    @pytest.fixture(scope="class")
    def generated(self) -> str:
        return GENERATED_CONFIG.read_text(encoding="utf-8")

    def test_it_still_carries_the_guard_clause(self, generated):
        """Pin the input, so a fixture edit cannot make the next test vacuous."""
        lines = generated.splitlines()
        assert lines[82].strip() == "if not hand_changed_keys:"
        assert lines[83].strip() == "return"

    def test_it_produces_no_empty_branch_warning(self, generated):
        assert kinds(generated) == []

    def test_it_produces_no_layer_one_warning_at_all(self, generated):
        """The acceptance criterion, across every rule in the layer.

        The issue also asks whether the sibling rules carry the same shape of
        imprecision. Measured against this file and against the run's other
        generated module: they do not.
        """
        total = 0
        for name in dir(A):
            if not name.startswith("analyze_"):
                continue
            try:
                total += len(getattr(A, name)(generated, "config.py"))
            except TypeError:
                continue
        assert total == 0


class TestGuardClauseAgainstEmptyBranch:
    def test_a_guard_clause_does_not_warn(self):
        assert kinds("def f(x):\n    if not x:\n        return\n    return 1\n") == []

    def test_a_genuinely_empty_branch_still_does(self):
        assert kinds("def f(x):\n    if not x:\n        pass\n    return 1\n") == [2]

    def test_return_none_is_a_guard_too(self):
        source = "def f(x):\n    if not x:\n        return None\n    return 1\n"
        assert kinds(source) == []

    def test_a_return_with_nothing_after_it_is_an_empty_branch(self):
        """The precise line the issue draws.

        A bare return guards the code that FOLLOWS the if. With nothing
        following, the branch really does do nothing, and the original
        warning was right about that case.
        """
        assert kinds("def f(x):\n    if not x:\n        return\n") == [2]

    def test_ellipsis_is_still_an_empty_branch(self):
        assert kinds("def f(x):\n    if not x:\n        ...\n    return 1\n") == [2]

    def test_a_docstring_only_branch_is_still_empty(self):
        source = 'def f(x):\n    if not x:\n        "why"\n    return 1\n'
        assert kinds(source) == [2]

    def test_a_real_body_never_warned_and_still_does_not(self):
        source = "def f(x):\n    if not x:\n        raise ValueError()\n    return 1\n"
        assert kinds(source) == []


class TestContextIsWhatDecides:
    def test_a_guard_inside_a_loop_is_a_guard(self):
        source = (
            "def f(xs):\n"
            "    for x in xs:\n"
            "        if not x:\n"
            "            return\n"
            "        print(x)\n"
        )
        assert kinds(source) == []

    def test_the_same_branch_warns_when_it_ends_its_block(self):
        source = (
            "def f(xs):\n"
            "    for x in xs:\n"
            "        print(x)\n"
            "        if not x:\n"
            "            return\n"
        )
        assert kinds(source) == [4]

    def test_a_guard_inside_a_try_block_is_a_guard(self):
        source = (
            "def f(x):\n"
            "    try:\n"
            "        if not x:\n"
            "            return\n"
            "        g()\n"
            "    except OSError:\n"
            "        pass\n"
        )
        assert kinds(source) == []

    def test_function_bodies_are_judged_by_a_different_rule(self):
        """`_is_trivial_body` still calls a bare-return FUNCTION body trivial.

        Teaching that helper about guard clauses would have been the wrong
        repair: it also judges function bodies, where a bare return really is
        a stub. The difference is context, so context is where it is decided.
        """
        import ast

        body = ast.parse("def f():\n    return\n").body[0].body
        assert A._is_trivial_body(body) is True


class TestElseBranches:
    def test_an_empty_else_still_warns(self):
        source = (
            "def f(x):\n"
            "    if x:\n"
            "        y = 1\n"
            "    else:\n"
            "        pass\n"
            "    return 2\n"
        )
        assert kinds(source) == [5]

    def test_an_elif_with_an_empty_body_still_warns(self):
        source = (
            "def f(x):\n"
            "    if x:\n"
            "        y = 1\n"
            "    elif not x:\n"
            "        pass\n"
            "    return 2\n"
        )
        assert kinds(source) == [4]

    def test_an_elif_is_not_double_reported_as_an_else(self):
        """The pre-existing behaviour, preserved through the restructure."""
        source = (
            "def f(x):\n"
            "    if x:\n"
            "        pass\n"
            "    elif not x:\n"
            "        pass\n"
            "    return 2\n"
        )
        assert kinds(source) == [2, 4]


class TestFailOpenIsUntouched:
    def test_a_syntax_error_still_returns_no_issues(self):
        """WARN-and-route is designed behaviour and this issue does not change it.

        The node proceeds with verdict WARN when AST analysis cannot run. The
        defect was the warning being false, not the routing.
        """
        assert analyze_empty_branches("def f(:\n", "t.py") == []
