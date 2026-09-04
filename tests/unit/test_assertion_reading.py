"""How the checker decides a test has an assertion (#2752, ruled on #2737).

`validate_test_structure` refused two tests boostgauge's hand build shipped.
Both are real tests that really pass, and neither was refused for the reason
the original issue gave. The two shapes are reproduced verbatim below as
fixtures, because a fix measured against a paraphrase is not measured against
the artifact that showed the problem.

Operator ruling, 2026-09-04: a test whose assertion lives in a helper it calls
counts as having an assertion; follow the call one level, to a function in the
same module or an imported one.
"""

from __future__ import annotations

import textwrap

import pytest

from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    imported_helper_sources,
    validate_test_structure,
)

#: `tests/visual/test_stingray_dynamic.py::test_dynamic_256_matches_baseline`,
#: reduced to the shape that mattered: every exit is `pytest.fail`, `pytest.skip`
#: or a bare `return`, and there is no `assert` anywhere. Refused before #2752.
STINGRAY_SHAPE = textwrap.dedent('''
    import pytest
    from PIL import Image, ImageChops, ImageStat

    def test_dynamic_256_matches_baseline(request, dyn_256):
        path = BASELINES / "stingray_dynamic_256.png"
        if not path.exists():
            pytest.fail(f"missing baseline {path}")
        baseline = Image.open(path).convert("RGB")
        if dyn_256.tobytes() == baseline.tobytes():
            return
        rms = max(ImageStat.Stat(ImageChops.difference(dyn_256, baseline)).rms)
        if rms > RMS_TOLERANCE:
            pytest.fail(f"dynamic composition drifted: rms={rms:.4f}")
''')

#: `tests/unit/test_telltale.py::test_V4_equal_timestamp_is_accepted`, verbatim
#: apart from the import line. Its contract is "this call must not raise" and
#: it has no assertion in its body or one level down -- `_fed` has none either.
#: Still refused; the ruling question is #2754.
MUST_NOT_RAISE_SHAPE = textwrap.dedent('''
    from boostgauge.telltale import Telltale

    def _fed(window, samples, decay_rate=None):
        t = Telltale(window, decay_rate=decay_rate)
        for ts, v in samples:
            t.update(ts, v)
        return t

    def test_V4_equal_timestamp_is_accepted():
        t = _fed(10.0, [(5.0, 1.0)])
        t.update(5.0, 3.0)  # must not raise
''')


def messages(source: str, imported=None) -> list[str]:
    return validate_test_structure(source, [], imported)


class TestTheShippedArtifacts:
    def test_the_stingray_test_is_no_longer_refused(self):
        """It reaches its verdict entirely through `pytest.fail`. The checker
        knew `assert` and `pytest.raises` and nothing else, so an entire way of
        failing a test was invisible to it."""
        assert messages(STINGRAY_SHAPE) == []

    def test_the_must_not_raise_test_is_now_accepted(self):
        """#2754 landed, and this is the test that was waiting for it.

        It was pinned as still-refused while the ruling was open --
        deliberately, so the count recorded the honest state rather than a
        number massaged to look finished. The operator ruled on 2026-09-04:
        a body that calls into the code under test and carries no `assert` is
        a test whose assertion is "does not raise".

        Accepted through the helper, not the body: the body never names
        `Telltale`, `_fed` constructs one. `t.update` is still an attribute on
        a local that no parser resolves, and still does not need to be.
        """
        assert messages(MUST_NOT_RAISE_SHAPE) == []


class TestFollowingTheCallOneLevel:
    def test_a_same_module_helper_carries_the_assertion(self):
        source = textwrap.dedent('''
            import pytest

            def _assert_accepted(value):
                assert value is not None

            def test_it():
                _assert_accepted(compute())
        ''')
        assert messages(source) == []

    def test_a_method_helper_is_found_by_its_bare_name(self):
        """`self._check(...)` is an attribute at the call site and a plain
        function definition in the module."""
        source = textwrap.dedent('''
            import pytest

            class TestThing:
                def _check(self, value):
                    assert value

                def test_it(self):
                    self._check(compute())
        ''')
        assert messages(source) == []

    def test_two_levels_down_is_not_followed(self):
        """One level is the ruling and the bound. A helper whose assertion is
        itself in another helper is not accepted, because every level past the
        first makes "this test asserts" depend on more code that is not the
        test."""
        source = textwrap.dedent('''
            import pytest

            def _inner(value):
                assert value

            def _outer(value):
                _inner(value)

            def test_it():
                _outer(compute())
        ''')
        assert len(messages(source)) == 1

    def test_a_helper_that_calls_itself_terminates(self):
        source = textwrap.dedent('''
            import pytest

            def _loop(n):
                if n:
                    _loop(n - 1)

            def test_it():
                _loop(3)
        ''')
        assert len(messages(source)) == 1

    def test_a_test_that_calls_nothing_useful_is_still_caught(self):
        """#2737's second criterion: a test with no assertion in its body or
        one level down must still be caught."""
        source = textwrap.dedent('''
            import pytest

            def test_it():
                x = compute(1)
        ''')
        errors = messages(source)
        assert len(errors) == 1
        assert "one level down" in errors[0]

    def test_an_empty_test_is_still_caught_with_its_own_message(self):
        source = textwrap.dedent('''
            import pytest

            def test_it():
                pass
        ''')
        assert messages(source) == [
            "Function 'test_it' has no assertions - only pass/docstring"
        ]


class TestTheWaysAVerdictCanBeReached:
    @pytest.mark.parametrize("body", [
        "assert compute() == 1",
        "with pytest.raises(ValueError):\n        compute()",
        "pytest.fail('nope')",
        "pytest.xfail('known')",
        "self.assertEqual(compute(), 1)",
        "self.assertRaises(ValueError, compute)",
    ])
    def test_each_one_counts(self, body):
        source = f"import pytest\n\ndef test_it(self):\n    {body}\n"
        assert messages(source) == []

    def test_a_bare_assert_false_is_not_a_real_assertion_but_draws_no_error(self):
        """Two rules meet here and the second one wins, unchanged by #2752.

        Issue #386 exempted `assert False, 'TDD RED: ...'` because the TDD
        scaffold emits it on purpose; a bare one carries no message, so it is
        not counted as a real assertion. But the fallback below asks only
        whether ANY `ast.Assert` exists before reporting, and a bare
        `assert False` is one -- so this function passes the structure check
        and is caught instead by `count_stub_tests`, which reads it as a body
        that can never pass. Pinned so the split stays deliberate."""
        source = "import pytest\n\ndef test_it():\n    assert False\n"
        assert messages(source) == []

        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            count_stub_tests,
        )
        total, stubs, names = count_stub_tests(source)
        assert (total, stubs, names) == (1, 1, ["test_it"])

    def test_a_tdd_red_placeholder_still_counts(self):
        source = "import pytest\n\ndef test_it():\n    assert False, 'TDD RED: x'\n"
        assert messages(source) == []


class TestTheImportedHalfOfTheRuling:
    def test_a_helper_imported_from_a_neighbour_is_followed(self, tmp_path):
        (tmp_path / "helpers.py").write_text(
            "def assert_accepted(value):\n    assert value is not None\n",
            encoding="utf-8",
        )
        source = textwrap.dedent('''
            from helpers import assert_accepted

            def test_it():
                assert_accepted(compute())
        ''')
        imported = imported_helper_sources(source, tmp_path)
        assert "assert_accepted" in imported
        assert messages(source, imported) == []

    def test_without_the_neighbour_the_same_test_is_refused(self):
        """The imported half depends on reaching the file. When the caller
        cannot supply it, the checker reads less and says so by refusing rather
        than by guessing."""
        source = textwrap.dedent('''
            from helpers import assert_accepted

            def test_it():
                assert_accepted(compute())
        ''')
        assert len(messages(source)) == 1

    def test_a_same_module_helper_wins_over_an_imported_one(self, tmp_path):
        (tmp_path / "helpers.py").write_text(
            "def check(value):\n    assert value\n", encoding="utf-8"
        )
        source = textwrap.dedent('''
            from helpers import check

            def check(value):
                pass

            def test_it():
                check(compute())
        ''')
        imported = imported_helper_sources(source, tmp_path)
        assert len(messages(source, imported)) == 1, (
            "the local definition is what runs, so it is what is read"
        )

    def test_a_missing_neighbour_costs_a_helper_not_the_run(self, tmp_path):
        source = "from nowhere import thing\n\ndef test_it():\n    thing()\n"
        assert imported_helper_sources(source, tmp_path) == {}

    def test_an_unparseable_neighbour_costs_a_helper_not_the_run(self, tmp_path):
        (tmp_path / "helpers.py").write_text("def broken(:\n", encoding="utf-8")
        source = "from helpers import broken\n\ndef test_it():\n    broken()\n"
        assert imported_helper_sources(source, tmp_path) == {}

    def test_unparseable_test_content_yields_no_helpers(self, tmp_path):
        assert imported_helper_sources("def broken(:\n", tmp_path) == {}
