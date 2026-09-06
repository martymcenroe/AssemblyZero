"""A passing test is the contract; a revision keeps it as written (#2905).

boostgauge #4, `run-issue4-042724` (2026-09-06 04:27). N4c took coverage from
91 % to 99 % and left two of its thirteen tests failing. N4's patches to
`tests/unit/test_collector.py` in iterations 2 and 4 fixed those and rewrote
three passing tests on the way: `test_req_13` went from
`pytest.raises(NotImplementedError)` to `pytest.raises(OSError)`; req_9 and
req_10 gained `WindowsCollector(ntdll=mock)`, a keyword the constructor never
had. The loop measured 49 -> 47 -> 48 of 51 and ran out at the cap.

Every case here is the shape of that file: a test that passed keeps its text,
a test that failed is the patch's to change, a deleted passing test comes
back, and the verifier tells the implementer which tests those are.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.nodes.implementation.keep_passing_tests import (
    Kept,
    keep_passing_tests_as_written,
    passing_test_names,
)
from assemblyzero.workflows.testing.nodes.verify_phases import _hill_climb
from assemblyzero.workflows.testing.state import TestingWorkflowState

# run 32's test file, reduced: three passing spec tests and one failing
# coverage test the patch is entitled to change.
RUN_32 = '''\
"""Tests for the collector."""
import unittest.mock

import pytest

from boostgauge.collector import make_collector
from boostgauge.collectors.windows import WindowsCollector


def test_req_9_buffer_growth_on_mismatch(monkeypatch):
    c = WindowsCollector(sweep=lambda: [])
    initial_len = len(c._buffer)
    c.nt_sweep()
    assert len(c._buffer) > initial_len


@pytest.mark.parametrize("status", [-1, -1073741820])
def test_req_10_oserror_fallback(status):
    c = WindowsCollector(sweep=lambda: [])
    with pytest.raises(OSError):
        c.nt_sweep()


def test_req_13_mac_linux_raises_notimplemented(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    with pytest.raises(NotImplementedError):
        make_collector()


def test_collect_with_thresholds_computes_composite():
    c = WindowsCollector()
    assert c.collect().composite == 0.0
'''

# iteration 4's patch: the failing coverage test fixed, and the three
# passing tests rewritten on the way.
RUN_39 = '''\
"""Tests for the collector."""
import unittest.mock

import pytest

from boostgauge.collector import make_collector
from boostgauge.collectors.windows import WindowsCollector


def test_req_9_buffer_growth_on_mismatch(monkeypatch):
    mock_ntdll = unittest.mock.MagicMock()
    mock_ntdll.NtQuerySystemInformation.side_effect = [-1073741820, 0]
    c = WindowsCollector(ntdll=mock_ntdll)
    initial_len = len(c._buffer)
    c.nt_sweep()
    assert len(c._buffer) > initial_len


@pytest.mark.parametrize("status", [-1, -1073741820])
def test_req_10_oserror_fallback(status):
    mock_ntdll = unittest.mock.MagicMock()
    mock_ntdll.NtQuerySystemInformation.return_value = status
    c = WindowsCollector(ntdll=mock_ntdll)
    with pytest.raises(OSError):
        c.nt_sweep()


def test_req_13_mac_linux_raises_notimplemented(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    with pytest.raises(OSError):
        make_collector()


def test_collect_with_thresholds_computes_composite():
    c = WindowsCollector(sweep=lambda: [])
    assert c.collect().composite == 10.0
'''

PASSING = {
    "test_req_9_buffer_growth_on_mismatch",
    "test_req_10_oserror_fallback",
    "test_req_13_mac_linux_raises_notimplemented",
}

GREEN_OUTPUT = """\
tests/unit/test_collector.py::test_req_9_buffer_growth_on_mismatch PASSED [ 25%]
tests/unit/test_collector.py::test_req_10_oserror_fallback[-1] PASSED   [ 50%]
tests/unit/test_collector.py::test_req_10_oserror_fallback[-1073741820] PASSED [ 62%]
tests/unit/test_collector.py::test_req_13_mac_linux_raises_notimplemented PASSED [ 75%]
tests/unit/test_collector.py::test_collect_with_thresholds_computes_composite FAILED [100%]
tests/unit/test_other.py::TestGroup::test_inside_a_class PASSED          [100%]

=================================== FAILURES ===================================
FAILED tests/unit/test_collector.py::test_collect_with_thresholds_computes_composite - assert 0.0 == 10.0
"""


def _function_text(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
            return "\n".join(lines[first - 1:node.end_lineno])
    raise AssertionError(f"{name} not in source")


class TestRun39sPatch:
    def test_the_three_passing_tests_keep_run_32s_text(self):
        kept = keep_passing_tests_as_written(RUN_32, RUN_39, PASSING)

        for name in PASSING:
            assert _function_text(kept.source, name) == _function_text(RUN_32, name)
        assert sorted(kept.restored) == sorted(PASSING)
        assert kept.returned == []

    def test_req_13_asserts_notimplementederror_again(self):
        kept = keep_passing_tests_as_written(RUN_32, RUN_39, PASSING)

        body = _function_text(kept.source, "test_req_13_mac_linux_raises_notimplemented")
        assert "pytest.raises(NotImplementedError)" in body
        assert "ntdll" not in kept.source

    def test_the_failing_coverage_test_keeps_the_patch(self):
        kept = keep_passing_tests_as_written(RUN_32, RUN_39, PASSING)

        body = _function_text(kept.source, "test_collect_with_thresholds_computes_composite")
        assert body == _function_text(RUN_39, "test_collect_with_thresholds_computes_composite")

    def test_the_decorator_travels_with_the_test(self):
        kept = keep_passing_tests_as_written(RUN_32, RUN_39, PASSING)

        body = _function_text(kept.source, "test_req_10_oserror_fallback")
        assert body.startswith("@pytest.mark.parametrize")
        assert kept.source.count("@pytest.mark.parametrize") == 1

    def test_the_result_still_parses_and_ends_with_a_newline(self):
        kept = keep_passing_tests_as_written(RUN_32, RUN_39, PASSING)

        ast.parse(kept.source)
        assert kept.source.endswith("\n")
        assert not kept.source.endswith("\n\n")

    def test_the_names_come_from_the_green_output(self):
        names = passing_test_names(GREEN_OUTPUT)

        assert names == PASSING | {"test_inside_a_class"}

    def test_with_the_output_as_the_contract_the_result_is_the_same(self):
        by_output = keep_passing_tests_as_written(
            RUN_32, RUN_39, passing_test_names(GREEN_OUTPUT),
        )

        assert by_output == keep_passing_tests_as_written(RUN_32, RUN_39, PASSING)


class TestNothingToKeep:
    def test_no_passing_tests_means_no_change(self):
        assert keep_passing_tests_as_written(RUN_32, RUN_39, set()) == Kept(RUN_39, [], [])

    def test_an_identical_file_is_untouched(self):
        assert keep_passing_tests_as_written(RUN_32, RUN_32, PASSING) == Kept(RUN_32, [], [])

    def test_a_patch_that_left_the_passing_tests_alone_is_untouched(self):
        only_the_failing_one = RUN_32.replace(
            "assert c.collect().composite == 0.0",
            "assert c.collect().composite == 10.0",
        )

        kept = keep_passing_tests_as_written(RUN_32, only_the_failing_one, PASSING)

        assert kept == Kept(only_the_failing_one, [], [])

    def test_an_unparseable_patch_is_left_for_the_syntax_gate(self):
        broken = RUN_39 + "\ndef broken(:\n"

        assert keep_passing_tests_as_written(RUN_32, broken, PASSING) == Kept(broken, [], [])

    def test_an_unparseable_prior_keeps_nothing(self):
        assert keep_passing_tests_as_written("def x(:\n", RUN_39, PASSING) == Kept(RUN_39, [], [])


class TestADeletedPassingTestComesBack:
    def test_a_module_level_test_is_appended(self):
        without_req_13 = RUN_39.replace(
            _function_text(RUN_39, "test_req_13_mac_linux_raises_notimplemented") + "\n\n\n",
            "",
        )
        assert "test_req_13" not in without_req_13

        kept = keep_passing_tests_as_written(RUN_32, without_req_13, PASSING)

        assert kept.returned == ["test_req_13_mac_linux_raises_notimplemented"]
        assert _function_text(kept.source, "test_req_13_mac_linux_raises_notimplemented") == \
            _function_text(RUN_32, "test_req_13_mac_linux_raises_notimplemented")
        ast.parse(kept.source)

    def test_a_method_goes_back_into_its_class(self):
        before = (
            "class TestGroup:\n"
            "    def test_kept(self):\n"
            "        assert 1\n"
            "\n"
            "    def test_gone(self):\n"
            "        assert 2\n"
        )
        after = (
            "class TestGroup:\n"
            "    def test_kept(self):\n"
            "        assert 1\n"
        )

        kept = keep_passing_tests_as_written(before, after, {"test_kept", "test_gone"})

        assert kept.returned == ["test_gone"]
        tree = ast.parse(kept.source)
        methods = [n.name for n in tree.body[0].body if isinstance(n, ast.FunctionDef)]
        assert methods == ["test_kept", "test_gone"]

    def test_a_method_whose_class_is_gone_is_not_re_homed(self):
        before = "class TestGroup:\n    def test_gone(self):\n        assert 2\n"
        after = "def test_new():\n    assert 3\n"

        kept = keep_passing_tests_as_written(before, after, {"test_gone"})

        assert kept == Kept(after, [], [])

    def test_a_changed_method_is_restored_in_place(self):
        before = "class TestGroup:\n    def test_kept(self):\n        assert 1\n"
        after = "class TestGroup:\n    def test_kept(self):\n        assert 99\n"

        kept = keep_passing_tests_as_written(before, after, {"test_kept"})

        assert kept.restored == ["test_kept"]
        assert kept.source == before


class TestTheVerifierNamesTheContract:
    """`_hill_climb` records the passing set and hands N4 the one that matches
    the files in the worktree: the best's after a restore, else the latest."""

    @pytest.fixture
    def tree(self, tmp_path):
        repo = tmp_path / "worktree"
        (repo / "src").mkdir(parents=True)
        (repo / "tests").mkdir()
        impl = repo / "src" / "collector.py"
        test = repo / "tests" / "test_collector.py"
        impl.write_text("BEST = 1\n", encoding="utf-8")
        test.write_text(RUN_32, encoding="utf-8")
        audit = tmp_path / "audit"
        audit.mkdir()
        return repo, impl, test, audit

    @staticmethod
    def _state(repo, impl, test, audit, best=None):
        return {
            "implementation_files": [str(impl)],
            "test_files": [str(test)],
            "audit_dir": str(audit),
            "best_iteration": best,
        }

    def test_a_new_best_records_its_passing_tests(self, tree):
        repo, impl, test, audit = tree
        updates = {}

        _hill_climb(self._state(repo, impl, test, audit), repo, 49, 99.0, ["t_x"],
                    updates, passing_tests=sorted(PASSING))

        assert updates["best_iteration"]["passing"] == sorted(PASSING)
        assert updates["contract_tests"] == sorted(PASSING)

    def test_a_restore_hands_n4_the_bests_passing_tests(self, tree):
        repo, impl, test, audit = tree
        first = {}
        _hill_climb(self._state(repo, impl, test, audit), repo, 49, 99.0, ["t_x"],
                    first, passing_tests=sorted(PASSING))
        best = first["best_iteration"]
        impl.write_text("WORSE = 1\n", encoding="utf-8")
        worse = {}

        _hill_climb(self._state(repo, impl, test, audit, best), repo, 47, 99.0,
                    ["t_x", "t_y", "test_req_13_mac_linux_raises_notimplemented"],
                    worse, passing_tests=["test_req_9_buffer_growth_on_mismatch"])

        assert worse["contract_tests"] == sorted(PASSING)
        assert impl.read_text(encoding="utf-8") == "BEST = 1\n"

    def test_an_equal_iteration_hands_n4_the_latest_passing_tests(self, tree):
        repo, impl, test, audit = tree
        first = {}
        _hill_climb(self._state(repo, impl, test, audit), repo, 49, 99.0, ["t_x"],
                    first, passing_tests=sorted(PASSING))
        best = first["best_iteration"]
        latest = ["test_a", "test_b"]
        same = {}

        _hill_climb(self._state(repo, impl, test, audit, best), repo, 49, 99.0,
                    ["t_y"], same, passing_tests=latest)

        assert same["contract_tests"] == latest
        assert "best_iteration" not in same

    def test_the_channel_is_declared(self):
        assert "contract_tests" in TestingWorkflowState.__annotations__


def test_the_implementer_keeps_passing_tests_before_it_writes():
    """Structural: the guard sits between the model's code and the write."""
    source = (
        Path(__file__).resolve().parents[2]
        / "assemblyzero" / "workflows" / "testing" / "nodes" / "implementation"
        / "orchestrator.py"
    ).read_text(encoding="utf-8")

    guard = source.index("keep_passing_tests_as_written(prior_text, code, contract)")
    write = source.index("# Write file (atomic: write to temp, then rename)")
    assert guard < write
    assert "(#2905)" in source


SPEC_SUITE = '''\
"""Spec suite for #4."""
import pytest

from boostgauge.collector import make_collector


def test_req_13_mac_linux_raises_notimplemented(monkeypatch):
    # Mac/Linux (REQ-13)
    monkeypatch.setattr("sys.platform", "linux")
    with pytest.raises(NotImplementedError):
        make_collector()
'''


class TestTheSpecSuiteGovernsASharedName:
    """#2910: run 40's plan-file copy of test_req_13 asserted OSError against
    the spec's NotImplementedError; held as the contract it walled the loop."""

    def test_run_40s_twin_is_released_and_the_rest_are_kept(self):
        from assemblyzero.workflows.testing.nodes.implementation.keep_passing_tests import (
            release_spec_twins,
        )

        contract, released = release_spec_twins(PASSING, SPEC_SUITE)

        assert released == {"test_req_13_mac_linux_raises_notimplemented"}
        assert contract == {
            "test_req_9_buffer_growth_on_mismatch", "test_req_10_oserror_fallback",
        }

    def test_the_released_copy_is_the_patchs_to_change(self):
        from assemblyzero.workflows.testing.nodes.implementation.keep_passing_tests import (
            release_spec_twins,
        )
        contract, _ = release_spec_twins(PASSING, SPEC_SUITE)

        kept = keep_passing_tests_as_written(RUN_32, RUN_39, contract)

        assert sorted(kept.restored) == [
            "test_req_10_oserror_fallback", "test_req_9_buffer_growth_on_mismatch",
        ]
        body = _function_text(kept.source, "test_req_13_mac_linux_raises_notimplemented")
        assert "pytest.raises(OSError)" in body

    def test_no_spec_suite_releases_nothing(self):
        from assemblyzero.workflows.testing.nodes.implementation.keep_passing_tests import (
            release_spec_twins,
        )

        assert release_spec_twins(PASSING, None) == (PASSING, set())
        assert release_spec_twins(PASSING, "") == (PASSING, set())
        assert release_spec_twins(set(), SPEC_SUITE) == (set(), set())

    def test_an_unparseable_spec_suite_releases_nothing(self):
        from assemblyzero.workflows.testing.nodes.implementation.keep_passing_tests import (
            release_spec_twins,
        )

        assert release_spec_twins(PASSING, "def broken(:\n") == (PASSING, set())

    def test_a_method_in_the_spec_suite_counts(self):
        from assemblyzero.workflows.testing.nodes.implementation.keep_passing_tests import (
            release_spec_twins,
        )
        suite = "class TestReq:\n    def test_req_9_buffer_growth_on_mismatch(self):\n        assert 1\n"

        _, released = release_spec_twins(PASSING, suite)

        assert released == {"test_req_9_buffer_growth_on_mismatch"}

    def test_the_implementer_releases_before_it_keeps(self):
        source = (
            Path(__file__).resolve().parents[2]
            / "assemblyzero" / "workflows" / "testing" / "nodes" / "implementation"
            / "orchestrator.py"
        ).read_text(encoding="utf-8")

        release = source.index("release_spec_twins(contract, spec_source)")
        keep = source.index("keep_passing_tests_as_written(prior_text, code, contract)")
        assert release < keep
        assert "(#2910)" in source


# The spec suite as run 41's scaffold emitted it, reduced to the twin and
# an import the plan file lacks.
RUN_41_SPEC_SUITE = '''\
"""Spec suite for #4."""
import pytest

from boostgauge.collector import make_collector
from boostgauge.thresholds import Thresholds


def test_req_13_mac_linux_raises_notimplemented(monkeypatch):
    # Mac/Linux (REQ-13)
    monkeypatch.setattr("sys.platform", "linux")
    with pytest.raises(NotImplementedError):
        make_collector()


def test_req_14_thresholds_default():
    assert Thresholds()
'''


class TestTheVerifierAlignsTwins:
    """#2912: before a measurement, a plan file's copy of a spec test carries
    the spec's text. run-issue4-135112's implementer read the drifted copy's
    `DID NOT RAISE OSError` as the implementation's fault, twice."""

    def test_run_41s_twin_takes_the_specs_text(self):
        from assemblyzero.workflows.testing.nodes.implementation.keep_passing_tests import (
            align_spec_twins,
        )

        aligned = align_spec_twins(RUN_39, RUN_41_SPEC_SUITE)

        assert aligned.aligned == ["test_req_13_mac_linux_raises_notimplemented"]
        body = _function_text(aligned.source, "test_req_13_mac_linux_raises_notimplemented")
        assert body == _function_text(RUN_41_SPEC_SUITE, "test_req_13_mac_linux_raises_notimplemented")
        assert "pytest.raises(OSError)" not in body

    def test_the_other_tests_are_untouched(self):
        from assemblyzero.workflows.testing.nodes.implementation.keep_passing_tests import (
            align_spec_twins,
        )

        aligned = align_spec_twins(RUN_39, RUN_41_SPEC_SUITE)

        for name in (
            "test_req_9_buffer_growth_on_mismatch", "test_req_10_oserror_fallback",
            "test_collect_with_thresholds_computes_composite",
        ):
            assert _function_text(aligned.source, name) == _function_text(RUN_39, name)
        assert "def test_req_14_thresholds_default" not in aligned.source

    def test_the_imports_the_copy_needs_are_carried_over(self):
        from assemblyzero.workflows.testing.nodes.implementation.keep_passing_tests import (
            align_spec_twins,
        )

        aligned = align_spec_twins(RUN_39, RUN_41_SPEC_SUITE)

        assert aligned.imports_added == ["from boostgauge.thresholds import Thresholds"]
        tree = ast.parse(aligned.source)
        imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        assert imports[-1].lineno < next(
            n.lineno for n in tree.body if isinstance(n, ast.FunctionDef)
        )
        assert aligned.source.count("import pytest") == 1

    def test_an_aligned_file_is_a_fixed_point(self):
        from assemblyzero.workflows.testing.nodes.implementation.keep_passing_tests import (
            align_spec_twins,
        )
        once = align_spec_twins(RUN_39, RUN_41_SPEC_SUITE)

        again = align_spec_twins(once.source, RUN_41_SPEC_SUITE)

        assert again == (once.source, [], [])

    def test_a_copy_already_matching_aligns_nothing(self):
        from assemblyzero.workflows.testing.nodes.implementation.keep_passing_tests import (
            align_spec_twins,
        )
        spec = _function_text(RUN_32, "test_req_13_mac_linux_raises_notimplemented")

        assert align_spec_twins(RUN_32, spec + "\n") == (RUN_32, [], [])

    def test_a_method_is_never_aligned_with_a_function(self):
        from assemblyzero.workflows.testing.nodes.implementation.keep_passing_tests import (
            align_spec_twins,
        )
        plan = "class TestReq:\n    def test_req_13_mac_linux_raises_notimplemented(self):\n        assert 1\n"

        assert align_spec_twins(plan, RUN_41_SPEC_SUITE) == (plan, [], [])

    def test_an_unparseable_side_aligns_nothing(self):
        from assemblyzero.workflows.testing.nodes.implementation.keep_passing_tests import (
            align_spec_twins,
        )

        assert align_spec_twins(RUN_39, "def broken(:\n") == (RUN_39, [], [])
        assert align_spec_twins("def broken(:\n", RUN_41_SPEC_SUITE) == ("def broken(:\n", [], [])

    def test_the_verifier_rewrites_the_plan_file_and_says_so(self, tmp_path, capsys):
        from assemblyzero.workflows.testing.nodes.verify_phases import (
            _align_plan_files_with_the_spec,
        )
        (tmp_path / "tests" / "unit").mkdir(parents=True)
        suite = tmp_path / "tests" / "test_issue_4.py"
        plan = tmp_path / "tests" / "unit" / "test_collector.py"
        suite.write_text(RUN_41_SPEC_SUITE, encoding="utf-8")
        plan.write_text(RUN_39, encoding="utf-8")

        rewritten = _align_plan_files_with_the_spec(
            {"issue_number": 4}, tmp_path, [str(suite), str(plan)],
        )

        assert rewritten == ["tests/unit/test_collector.py"]
        assert "pytest.raises(NotImplementedError)" in plan.read_text(encoding="utf-8")
        assert suite.read_text(encoding="utf-8") == RUN_41_SPEC_SUITE
        out = capsys.readouterr().out
        assert "[N5] aligned 1 test(s) in tests/unit/test_collector.py" in out
        assert "test_req_13_mac_linux_raises_notimplemented (#2912)" in out

    def test_without_a_spec_suite_nothing_is_touched(self, tmp_path):
        from assemblyzero.workflows.testing.nodes.verify_phases import (
            _align_plan_files_with_the_spec,
        )
        (tmp_path / "tests" / "unit").mkdir(parents=True)
        plan = tmp_path / "tests" / "unit" / "test_collector.py"
        plan.write_text(RUN_39, encoding="utf-8")

        assert _align_plan_files_with_the_spec({"issue_number": 4}, tmp_path, [str(plan)]) == []
        assert plan.read_text(encoding="utf-8") == RUN_39

    def test_the_verifier_aligns_before_it_measures(self):
        source = (
            Path(__file__).resolve().parents[2]
            / "assemblyzero" / "workflows" / "testing" / "nodes" / "verify_phases.py"
        ).read_text(encoding="utf-8")
        node = source.index("def verify_green_phase(")
        align = source.index("_align_plan_files_with_the_spec(state, repo_root, test_files)", node)
        measure = source.index("Running pytest with coverage target", node)
        assert align < measure
