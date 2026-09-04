"""A test that calls the code and does not raise has asserted something (#2754).

Operator ruling, 2026-09-04. The scaffolder's structural validator refused
boostgauge's shipped `test_V4_equal_timestamp_is_accepted`:

    def test_V4_equal_timestamp_is_accepted():
        t = _fed(10.0, [(5.0, 1.0)])
        t.update(5.0, 3.0)  # must not raise

That test is correct, the operator wrote it, and the comment says what it
asserts. The gate refusing it was the last refusal in the answer-key audit --
the audit that runs the pipeline's mechanical gates over code known to be
right, where every refusal is a false positive by construction.

The ruling draws the line as a parser question, not a judgement:

- calls into the code under test, no `assert`  -> accepted, the assertion is
  "does not raise";
- no call into the code under test, no `assert` -> refused, it is a stub.

"Into the code under test" means a call resolving to a name imported from the
module the test file targets, directly or through a same-module helper one
level down. That last clause is load-bearing here: the shipped test never
names `Telltale`; `_fed` does.
"""

from __future__ import annotations

import ast
from pathlib import Path

from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    _code_under_test_names,
    _exercises_code_under_test,
    validate_test_structure,
)

#: The shipped case, verbatim from boostgauge `tests/unit/test_telltale.py`.
SHIPPED = '''\
from __future__ import annotations

import pytest

from boostgauge.telltale import Telltale


def _fed(window, samples, decay_rate=None):
    t = Telltale(window, decay_rate=decay_rate)
    for ts, v in samples:
        t.update(ts, v)
    return t


def test_V4_equal_timestamp_is_accepted():
    t = _fed(10.0, [(5.0, 1.0)])
    t.update(5.0, 3.0)  # must not raise
'''

#: The other side of the line: a body that calls nothing but the framework
#: and the standard library.
FIXTURES_AND_STDLIB_ONLY = '''\
import math

import pytest

from boostgauge.telltale import Telltale


def test_only_touches_fixtures_and_stdlib(tmp_path, request):
    value = math.floor(3.7)
    request.config.getoption("--quiet")
    tmp_path.joinpath("x").write_text(str(value))
'''

STUB_ONLY = '''\
from boostgauge.telltale import Telltale


def test_nothing_here():
    pass


def test_only_a_docstring():
    """TDD RED: implementation pending."""
'''

#: run-issue4-163140's approved spec, whose Section 10 shipped thirteen test
#: functions. The scaffolder emits them verbatim and its validator refused the
#: suite 3.4 seconds later.
RUN8_FIXTURE = (
    Path(__file__).parent.parent
    / "fixtures"
    / "boostgauge4_stub_tests"
    / "spec-0004-final-spec.md"
)


class TestWhatCountsAsTheCodeUnderTest:
    def test_first_party_imports_are_targets_and_the_rest_are_not(self):
        tree = ast.parse(SHIPPED)
        assert _code_under_test_names(tree) == {"Telltale"}, (
            "pytest and __future__ are not the code under test"
        )

    def test_stdlib_and_framework_roots_are_excluded(self):
        tree = ast.parse(FIXTURES_AND_STDLIB_ONLY)
        names = _code_under_test_names(tree)
        assert "Telltale" in names
        assert "math" not in names
        assert "pytest" not in names

    def test_a_relative_import_is_a_sibling_helper_not_a_target(self):
        tree = ast.parse("from . import helpers\n\ndef test_x():\n    helpers.go()\n")
        assert _code_under_test_names(tree) == set()

    def test_a_bare_module_import_is_a_helper_not_a_target(self):
        """The distinction that took a red suite to find.

        `from helpers import assert_accepted` is a test helper sitting beside
        the test file; `from boostgauge.telltale import Telltale` is the code
        under test in the package being built. Treating every first-party
        import as a target accepted a test whose only call was to a
        `pass`-bodied helper.
        """
        tree = ast.parse("from helpers import assert_accepted\n")
        assert _code_under_test_names(tree) == set()

    def test_an_aliased_module_import_binds_its_root(self):
        tree = ast.parse("import boostgauge.telltale as tt\n")
        assert _code_under_test_names(tree) == {"tt"}


class TestTheRulingOnTheArtifactThatShowedIt:
    def test_the_shipped_test_is_accepted(self):
        """The whole reason #2754 exists."""
        errors = validate_test_structure(SHIPPED, [])
        assert errors == [], errors

    def test_it_is_accepted_through_the_helper_not_the_body(self):
        """The body never names `Telltale`. Drop the helper's call into the
        code under test and the same body must be refused again -- otherwise
        this test would pass for the wrong reason."""
        hollowed = SHIPPED.replace(
            "    t = Telltale(window, decay_rate=decay_rate)\n"
            "    for ts, v in samples:\n"
            "        t.update(ts, v)\n"
            "    return t\n",
            "    return object()\n",
        )
        assert "return object()" in hollowed, "the fixture edit did not apply"
        errors = validate_test_structure(hollowed, [])
        assert any("test_V4_equal_timestamp_is_accepted" in e for e in errors), (
            f"accepted without any route to the code under test: {errors}"
        )


class TestTheOtherSideOfTheLine:
    def test_a_body_calling_only_fixtures_and_stdlib_is_refused(self):
        errors = validate_test_structure(FIXTURES_AND_STDLIB_ONLY, [])
        assert any(
            "test_only_touches_fixtures_and_stdlib" in e for e in errors
        ), errors

    def test_pass_and_docstring_bodies_are_still_refused(self):
        errors = validate_test_structure(STUB_ONLY, [])
        assert any("test_nothing_here" in e for e in errors), errors
        assert any("test_only_a_docstring" in e for e in errors), errors


class TestRunEightIsStillRefusedThirteenTimes:
    """The regression this ruling could most easily have caused.

    Widening "has an assertion" is exactly the change that could let the
    hollow suite through -- the one that cost 605 seconds of approved spec
    work before the scaffolder's validator caught it, byte-identical on
    regeneration, deterministic.
    """

    def test_the_fixture_is_on_disk(self):
        assert RUN8_FIXTURE.is_file(), RUN8_FIXTURE

    def test_eleven_of_the_thirteen_are_still_refused(self):
        """Counted, and the count is 11 of 13 rather than 13 of 13.

        The spec shipped thirteen test functions; eleven of them are a
        comment and `pass`, and the other two carry real assertions. Eleven
        is therefore the number the validator named before this ruling and
        the number it must still name after it -- widening "has an assertion"
        must not let a single one of them through.
        """
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (  # noqa: E501
            check_spec_test_functions_have_assertions,
        )

        spec = RUN8_FIXTURE.read_text(encoding="utf-8")
        result = check_spec_test_functions_have_assertions(spec, 4, [])

        assert result["passed"] is False, "the hollow suite from run 8 was accepted"
        assert "11 of 13" in result["details"], result["details"]

    def test_none_of_them_slipped_through_the_does_not_raise_reading(self):
        """The specific way this ruling could have broken it.

        A stub body is `pass` or a comment, so it calls nothing at all -- and
        a body that calls nothing cannot call into the code under test. This
        asserts that directly on the fixture's own suite rather than trusting
        the aggregate count above.
        """
        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (  # noqa: E501
            _spec_test_functions,
        )

        spec = RUN8_FIXTURE.read_text(encoding="utf-8")
        functions = _spec_test_functions(spec)["functions"]
        assert len(functions) == 13, len(functions)

        source = "\n\n".join(
            f["source"] if isinstance(f, dict) else str(f) for f in functions
        )
        targets = _code_under_test_names(ast.parse("import boostgauge"))
        tree = ast.parse(source) if source.strip() else ast.parse("")
        exercising = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
            and _exercises_code_under_test(node, targets, {})
        ]
        assert exercising == [], (
            f"a stub body was read as calling into the code under test: "
            f"{exercising}"
        )
