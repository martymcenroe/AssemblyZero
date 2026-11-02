"""The defects the first real TypeScript run found in the green phase.

#4512 the fix prompt hides the type a compiler error names.
#4513 the implementer strips the final newline from every file it writes.
#4514 a spec's test bodies reach the run unproven.
#4515 an iteration that changes nothing goes unremarked, and the halt hides why.
#4516 the green phase stops at the first failing framework.
#4517 a green-phase halt is recorded as stage N0_load and type unknown.
"""

import inspect
import json
import shutil
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core.halt_node import _infer_stage, classify_error
from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    CompletenessCannotCheck,
    check_spec_tests_name_filters_can_match,
    check_spec_tests_pass_target_lint,
    check_spec_tests_start_js_tools_in_their_project,
)
from assemblyzero.workflows.testing import graph as graph_module
from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.graph import _names_itself, build_testing_workflow
from assemblyzero.workflows.testing.nodes import verify_phases
from assemblyzero.workflows.testing.nodes.implementation import orchestrator
from assemblyzero.workflows.testing.nodes.implementation.edit_script_fix import (
    apply_code_edit_script,
    build_code_edit_script_prompt,
    is_attributed,
    type_declarations_for,
    type_names_in_failure,
)
from assemblyzero.workflows.testing.nodes.implementation.orchestrator import (
    _nothing_changed,
    implement_code,
)
from assemblyzero.workflows.testing.nodes.implementation.parsers import (
    final_newline_as_before,
)
from assemblyzero.workflows.testing.nodes.verify_phases import (
    _every_frameworks_failures,
    _first_compiler_error,
    _Leg,
    _stop_rank,
    _with_the_stall,
    verify_green_phase,
)
from assemblyzero.workflows.testing.runners.jest_runner import JestRunner

# Each name is also a function exported by its package, so the module has to be
# reached through sys.modules.
scaffold_tests = sys.modules["assemblyzero.workflows.testing.nodes.scaffold_tests"]
validate_completeness = sys.modules[
    "assemblyzero.workflows.implementation_spec.nodes.validate_completeness"
]

TS2339 = (
    "tests/replay.test.ts(376,18): error TS2339: Property 'cost_usd' does not "
    "exist on type 'Score'."
)
SCORE_SOURCE = textwrap.dedent(
    """\
    export interface Score {
      score_version: string;
      cost: {
        value_usd: number;
      };
    }

    export function computeScore(): Score {
      return { score_version: "1", cost: { value_usd: 0 } };
    }
    """
)


@pytest.fixture
def web_target(tmp_path):
    """A failing test file that imports a type from a module beside it."""
    (tmp_path / "web" / "shared").mkdir(parents=True)
    (tmp_path / "web" / "tests").mkdir()
    (tmp_path / "web" / "shared" / "scoring.ts").write_text(SCORE_SOURCE, encoding="utf-8")
    (tmp_path / "web" / "tests" / "replay.test.ts").write_text(
        'import { computeScore } from "../shared/scoring";\n'
        "const score = computeScore();\n"
        "expect(score.cost_usd).toBe(1);\n",
        encoding="utf-8",
    )
    return tmp_path


class TestT4512TheTypeReachesThePrompt:
    def test_t1_a_type_in_an_imported_file_is_shown(self, web_target):
        section = type_declarations_for("web/tests/replay.test.ts", TS2339, web_target)
        assert "web/shared/scoring.ts" in section
        assert "value_usd: number;" in section
        assert "computeScore" not in section, "the declaration alone, not the module"

    def test_t1_the_section_reaches_the_prompt(self, web_target):
        section = type_declarations_for("web/tests/replay.test.ts", TS2339, web_target)
        prompt = build_code_edit_script_prompt(
            "web/tests/replay.test.ts", "x" * 500, TS2339, type_declarations=section,
        )
        assert "value_usd: number;" in prompt

    def test_t2_a_type_nothing_here_declares_is_said_to_be_missing(self, web_target):
        failure = (
            "tests/replay.test.ts(1,1): error TS2339: Property 'x' does not exist "
            "on type 'Response'."
        )
        section = type_declarations_for("web/tests/replay.test.ts", failure, web_target)
        assert "`Response`: no declaration was found" in section

    def test_a_type_declared_in_the_file_itself_is_not_repeated(self, web_target):
        target = web_target / "web" / "tests" / "replay.test.ts"
        target.write_text("interface Score { a: number }\n", encoding="utf-8")
        assert type_declarations_for("web/tests/replay.test.ts", TS2339, web_target) == ""

    def test_a_type_reached_through_a_re_export_is_found(self, web_target):
        target = web_target / "web" / "tests" / "replay.test.ts"
        target.write_text('import { Score } from "../shared/index";\n', encoding="utf-8")
        (web_target / "web" / "shared" / "index.ts").write_text(
            'export * from "./scoring";\n', encoding="utf-8",
        )
        section = type_declarations_for("web/tests/replay.test.ts", TS2339, web_target)
        assert "value_usd: number;" in section

    def test_a_type_alias_ends_at_its_semicolon(self, web_target):
        (web_target / "web" / "shared" / "scoring.ts").write_text(
            "export type Score = { a: number } | null;\nconst other = 1;\n",
            encoding="utf-8",
        )
        section = type_declarations_for("web/tests/replay.test.ts", TS2339, web_target)
        assert "export type Score = { a: number }" in section
        assert "other" not in section

    def test_a_failure_with_no_compiler_error_adds_nothing(self, web_target):
        failure = "FAILED tests/replay.test.ts > it fails\n  on type 'Score'"
        assert type_declarations_for("web/tests/replay.test.ts", failure, web_target) == ""

    def test_builtin_types_are_not_searched_for(self):
        failure = "a.ts(1,1): error TS2322: Type 'string' is not assignable to type 'Score'."
        assert type_names_in_failure(failure) == ["Score"]

    def test_a_type_at_the_start_of_an_error_is_named(self):
        """The compiler opens TS2322 with a capital."""
        failure = "a.ts(1,1): error TS2322: Type 'Score' is not assignable to type 'Result'."
        assert type_names_in_failure(failure) == ["Score", "Result"]

    def test_t3_the_prompt_names_the_files_this_run_may_change(self):
        prompt = build_code_edit_script_prompt(
            "web/tests/replay.test.ts", "x" * 500, TS2339,
            run_files=["web/shared/engine.ts", "web/tests/replay.test.ts"],
        )
        assert "- web/shared/engine.ts" in prompt
        assert "A file not on this list cannot change in this run." in prompt

    def test_the_run_files_section_is_absent_when_none_are_given(self):
        prompt = build_code_edit_script_prompt("a.ts", "x" * 500, TS2339)
        assert "FILES THIS RUN MAY CHANGE" not in prompt


class TestT4513TheFinalNewline:
    def test_t1_a_file_that_had_one_keeps_it(self):
        assert final_newline_as_before("const a = 1;", "const a = 0;\n") == "const a = 1;\n"

    def test_t1_exactly_one(self):
        assert final_newline_as_before("a\n\n", "b\n") == "a\n"

    def test_t2_a_new_file_ends_in_one(self):
        assert final_newline_as_before("a", "") == "a\n"

    def test_t3_a_file_that_had_none_keeps_none(self):
        assert final_newline_as_before("a\n", "b") == "a"

    def test_an_empty_file_stays_empty(self):
        assert final_newline_as_before("", "") == ""


def _spec_file(tmp_path: Path, name: str, text: str) -> None:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _implement_state(tmp_path: Path, **overrides) -> dict:
    audit = tmp_path / "audit"
    audit.mkdir(exist_ok=True)
    lld = tmp_path / "lld.md"
    lld.write_text("# LLD\n", encoding="utf-8")
    state = {
        "issue_number": 7,
        "repo_root": str(tmp_path),
        "lld_content": "# LLD\n\n## 2.1 Files Changed\n",
        "lld_path": str(lld),
        "audit_dir": str(audit),
        "files_to_modify": [{
            "path": "src/app.py", "change_type": "Modify", "description": "the app",
        }],
        "iteration_count": 1,
        "test_failure_summary": "FAILED tests/test_app.py::test_a - app is wrong\n  in src/app.py",
        "test_files": [],
        "completed_files": [],
    }
    state.update(overrides)
    return state


class TestT4513TheWrite:
    """Through N4 itself, because the helper alone proves nothing is calling it."""

    def test_t1_an_edit_script_keeps_the_newline_and_counts_as_a_change(self, tmp_path):
        source = "value = 1\n" + "# padding line\n" * 40
        _spec_file(tmp_path, "src/app.py", source)
        reply = "<<<<<<< SEARCH\nvalue = 1\n=======\nvalue = 2\n>>>>>>> REPLACE\n"
        with patch.object(orchestrator, "call_claude_for_file", return_value=(reply, "")):
            result = implement_code(_implement_state(tmp_path))
        written = (tmp_path / "src" / "app.py").read_text(encoding="utf-8")
        assert not result.get("error_message")
        assert written.startswith("value = 2\n")
        assert written.endswith("\n")
        assert result["nothing_changed"] == "", "a change clears the last pass's stall"


class TestT4515AnUnchangedTreeIsNamed:
    def _declined(self, tmp_path, capsys) -> tuple[dict, str, str]:
        source = "value = 1\n" + "# padding line\n" * 40
        _spec_file(tmp_path, "src/app.py", source)
        with patch.object(
            orchestrator, "call_claude_for_file",
            return_value=("NO-EDIT: the fix belongs elsewhere", ""),
        ):
            result = implement_code(_implement_state(tmp_path))
        return result, capsys.readouterr().out, source

    def test_t1_every_file_declining_is_flagged_with_the_reason(self, tmp_path, capsys):
        result, printed, _source = self._declined(tmp_path, capsys)
        stall = result["nothing_changed"]
        assert "N4 changed no file on iteration 1" in stall
        assert "src/app.py: NO-EDIT: the fix belongs elsewhere" in stall
        assert "app is wrong" in stall, "it quotes the failure"
        assert "[STAGNANT]" in printed

    def test_t1_the_run_goes_on_to_the_cap(self, tmp_path, capsys):
        """A stall never ends a run: #2723 ruled that the cap ends this loop,
        and a new way to stop needs an operator ruling."""
        result, _printed, source = self._declined(tmp_path, capsys)
        assert not result.get("error_message")
        assert (tmp_path / "src" / "app.py").read_text(encoding="utf-8") == source

    def test_t2_the_cap_quotes_the_stall(self):
        state = {"nothing_changed": "N4 changed no file on iteration 2"}
        assert _with_the_stall("Green phase failed after 3 iterations", state) == (
            "Green phase failed after 3 iterations. N4 changed no file on iteration 2"
        )

    def test_a_cap_with_no_stall_is_as_it_was(self):
        assert _with_the_stall("Green phase failed", {"nothing_changed": ""}) == "Green phase failed"

    def test_a_first_pass_is_never_held_to_this(self, tmp_path):
        result = _implement_first_pass(tmp_path)
        assert result["nothing_changed"] == ""

    def test_4513_a_whole_file_reply_keeps_the_final_newline(self, tmp_path):
        """The path a real run took: `extract_code_block` strips the reply."""
        _implement_first_pass(tmp_path)
        assert (tmp_path / "src" / "app.py").read_text(encoding="utf-8") == "value = 2\n"

    def test_t3_a_failure_in_the_spec_suite_points_at_the_spec(self):
        message = _nothing_changed(
            1, "FAILED tests/test_issue_7.py::test_req_01 - bad fixture", [], 7,
        )
        assert "the spec must change" in message

    def test_t3_a_failure_elsewhere_does_not(self):
        message = _nothing_changed(1, "FAILED tests/test_app.py::test_a", [], 7)
        assert "the spec must change" not in message

    def test_the_stall_quotes_a_bounded_failure(self):
        message = _nothing_changed(1, "x" * 50_000, [], 7)
        assert len(message) < 2000

    def test_t2_the_first_compiler_error_is_named(self):
        output = f"\n> web@0.1.0 typecheck\n> tsc --noEmit\n\n{TS2339}\n"
        assert _first_compiler_error(output) == TS2339


def _implement_first_pass(tmp_path: Path) -> dict:
    _spec_file(tmp_path, "src/app.py", "value = 1\n")
    reply = "```python\nvalue = 2\n```"
    with (
        patch.object(orchestrator, "call_claude_for_file", return_value=(reply, "")),
        patch.object(orchestrator, "validate_code_response", return_value=(True, "")),
        patch.object(orchestrator, "came_from_base", return_value=True),
    ):
        return implement_code(_implement_state(
            tmp_path, iteration_count=0, test_failure_summary="",
        ))


class TestT4515TheVitestRunner:
    def _runner(self, tmp_path) -> JestRunner:
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        return JestRunner(
            {"framework": TestFramework.VITEST, "test_command": "", "file_pattern": ""},
            str(tmp_path),
        )

    def test_t3_a_failed_typecheck_says_no_test_ran(self, tmp_path):
        result = self._runner(tmp_path)._typecheck_failed_result(TS2339, 2)
        assert result["typecheck_failed"] is True
        assert result["failure_summary"] == TS2339

    def test_a_report_gives_each_failed_test_and_its_message(self, tmp_path):
        runner = self._runner(tmp_path)
        summary = runner._failure_summary({"testResults": [{
            "name": str(tmp_path / "tests" / "replay.test.ts"),
            "status": "failed",
            "assertionResults": [
                {"status": "passed", "fullName": "works"},
                {
                    "status": "failed", "fullName": "stocks > clamps",
                    "failureMessages": ["AssertionError: nope\n    at tests/replay.test.ts:9:3"],
                },
            ],
        }]})
        assert summary.startswith("FAILED tests/replay.test.ts > stocks > clamps")
        assert "AssertionError: nope" in summary
        assert "works" not in summary
        assert is_attributed(summary, "web/tests/replay.test.ts")

    def test_a_file_that_could_not_load_gives_its_own_message(self, tmp_path):
        runner = self._runner(tmp_path)
        summary = runner._failure_summary({"testResults": [{
            "name": str(tmp_path / "tests" / "broken.test.ts"),
            "status": "failed", "message": "Cannot find module", "assertionResults": [],
        }]})
        assert "Cannot find module" in summary

    def test_a_parsed_report_carries_its_summary(self, tmp_path):
        report = {
            "numPassedTests": 0, "numFailedTests": 1, "numPendingTests": 0,
            "testResults": [{
                "name": str(tmp_path / "a.test.ts"), "status": "failed",
                "assertionResults": [{
                    "status": "failed", "fullName": "it fails", "failureMessages": ["nope"],
                }],
            }],
        }
        result = self._runner(tmp_path).parse_results(json.dumps(report), 1)
        assert "FAILED a.test.ts > it fails" in result["failure_summary"]


class TestT4515TheGreenPhaseOnATypecheckStop:
    """Through `_verify_green_non_pytest`, the path the real run took."""

    def _green(self, tmp_path: Path, **overrides) -> dict:
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        audit = tmp_path / "audit"
        audit.mkdir(exist_ok=True)
        runner = MagicMock()
        runner.run_tests.return_value = JestRunner(
            {"framework": TestFramework.VITEST, "test_command": "", "file_pattern": ""},
            str(tmp_path),
        )._typecheck_failed_result(TS2339, 2)
        state = {
            "repo_root": str(tmp_path), "test_files": ["web/a.test.ts"],
            "iteration_count": 0, "max_iterations": 3, "audit_dir": str(audit),
            "file_counter": 0, **overrides,
        }
        with (
            patch.object(verify_phases, "get_runner", return_value=runner),
            patch.object(verify_phases, "_changed_source_lines", return_value={}),
        ):
            return verify_phases._verify_green_non_pytest(
                state, {"framework": TestFramework.VITEST}, TestFramework.VITEST,
            )

    def test_t3_the_report_says_no_test_ran(self, tmp_path, capsys):
        self._green(tmp_path)
        printed = capsys.readouterr().out
        assert "no test ran" in printed
        assert "0 passed, 1 failed" not in printed
        assert "Tests: 0/1" not in printed

    def test_the_failure_reaches_n4(self, tmp_path):
        result = self._green(tmp_path)
        assert result["next_node"] == "N4_implement_code"
        assert result["test_failure_summary"] == TS2339

    def test_t2_the_cap_names_the_compiler_error_and_the_stall(self, tmp_path):
        result = self._green(
            tmp_path, iteration_count=2, nothing_changed="N4 changed no file on iteration 2",
        )
        message = result["error_message"]
        assert "the typecheck still fails, so no test ran" in message
        assert TS2339 in message
        assert "N4 changed no file on iteration 2" in message
        assert "tests still failing" not in message


def _leg(framework: TestFramework, test_file: str) -> _Leg:
    return _Leg({"framework": framework}, framework, "", (test_file,))


LEGS = [_leg(TestFramework.VITEST, "a.test.ts"), _leg(TestFramework.PYTEST, "test_a.py")]
FAILING = {
    "green_phase_output": "vitest output", "test_failure_summary": "vitest failure",
    "next_node": "N4_implement_code", "error_message": "", "iteration_count": 1,
    "test_run_result": {"passed": 0, "failed": 1, "errors": 0, "total": 1},
}
PYTEST_FAILING = {
    "green_phase_output": "pytest output", "test_failure_summary": "pytest failure",
    "next_node": "N4_implement_code", "error_message": "", "iteration_count": 1,
    "test_run_result": {"passed": 3, "failed": 1, "errors": 0, "total": 4},
}
PYTEST_PASSING = {
    "green_phase_output": "pytest output", "test_failure_summary": "",
    "next_node": "N6_e2e_validation", "error_message": "", "coverage_achieved": 100.0,
    "test_run_result": {"passed": 4, "failed": 0, "errors": 0, "total": 4},
}


class TestT4516EveryFrameworkRuns:
    def _run(self, vitest: dict, pytest_result: dict, tmp_path: Path) -> tuple[dict, MagicMock]:
        state = {
            "repo_root": str(tmp_path), "iteration_count": 0, "file_counter": 0,
            "framework_configs": [], "test_files": [],
        }
        ran_pytest = MagicMock(return_value=pytest_result)
        with (
            patch.object(verify_phases, "_framework_legs", return_value=LEGS),
            patch.object(verify_phases, "_gate_only_legs", return_value=[]),
            patch.object(verify_phases, "_preflight_legs"),
            patch.object(verify_phases, "_leg_state", side_effect=lambda s, _leg: s),
            patch.object(verify_phases, "_rejoin_leg_files", side_effect=lambda _s, _l, r: r),
            patch.object(verify_phases, "_verify_green_non_pytest", return_value=vitest),
            patch.object(verify_phases, "_verify_green_pytest_single", ran_pytest),
        ):
            return verify_green_phase(state), ran_pytest

    def test_t1_the_second_framework_runs_after_the_first_fails(self, tmp_path):
        result, ran_pytest = self._run(FAILING, PYTEST_PASSING, tmp_path)
        ran_pytest.assert_called_once()
        assert result["next_node"] == "N4_implement_code"

    def test_t2_n4_hears_from_both(self, tmp_path):
        result, _ = self._run(FAILING, PYTEST_FAILING, tmp_path)
        assert "vitest failure" in result["test_failure_summary"]
        assert "pytest failure" in result["test_failure_summary"]

    def test_t2_the_output_holds_both(self, tmp_path):
        result, _ = self._run(FAILING, PYTEST_FAILING, tmp_path)
        assert "vitest output" in result["green_phase_output"]
        assert "pytest output" in result["green_phase_output"]

    def test_t2_a_halt_hears_from_both(self):
        joined = _every_frameworks_failures([
            {"next_node": "end", "error_message": "vitest stuck", "test_failure_summary": "v"},
            {"next_node": "end", "error_message": "pytest stuck", "test_failure_summary": "p"},
        ])
        assert joined["error_message"] == "vitest stuck; pytest stuck"
        assert joined["test_failure_summary"] == "v\n\np"

    def test_a_framework_with_no_summary_is_read_from_its_output(self):
        joined = _every_frameworks_failures([
            {"next_node": "N4_implement_code", "green_phase_output": "raw"},
            {"next_node": "N4_implement_code", "test_failure_summary": "p"},
        ])
        assert joined["test_failure_summary"] == "raw\n\np"

    def test_a_coverage_gap_gives_way_to_a_failing_framework(self):
        gap = {"next_node": "N4c_augment_tests"}
        failing = {"next_node": "N4_implement_code"}
        assert min([gap, failing], key=_stop_rank) is failing

    def test_a_halt_outranks_a_repair(self):
        repair = {"next_node": "N4_implement_code"}
        halt = {"next_node": "end", "error_message": "stuck"}
        assert min([repair, halt], key=_stop_rank) is halt

    def test_t3_a_framework_that_cannot_start_still_halts_the_phase(self, tmp_path):
        state = {"repo_root": str(tmp_path), "iteration_count": 0, "framework_configs": []}
        with (
            patch.object(verify_phases, "_framework_legs", return_value=LEGS),
            patch.object(verify_phases, "_gate_only_legs", return_value=[]),
            patch.object(
                verify_phases, "_preflight_legs",
                side_effect=verify_phases.FrameworkLegError("vitest cannot start"),
            ),
        ):
            result = verify_green_phase(state)
        assert "vitest cannot start" in result["error_message"]


class TestTheWiring:
    """Each fix reaches the code that runs, not only the helper beneath it."""

    def test_4512_the_type_reaches_the_call_the_run_makes(self, web_target):
        target = web_target / "web" / "tests" / "replay.test.ts"
        existing = target.read_text(encoding="utf-8") + "// padding\n" * 40
        target.write_text(existing, encoding="utf-8")
        reply = "NO-EDIT: nothing here"
        with patch.object(orchestrator, "call_claude_for_file", return_value=(reply, "")) as call:
            orchestrator.try_edit_script_fix(
                "web/tests/replay.test.ts", existing, TS2339,
                run_files=["web/tests/replay.test.ts"], repo_root=web_target,
            )
        prompt = call.call_args.args[0]
        assert "value_usd: number;" in prompt
        assert "- web/tests/replay.test.ts" in prompt

    def test_4512_n4_tells_the_prompt_every_file_of_the_run(self, tmp_path):
        source = "value = 1\n" + "# padding line\n" * 40
        _spec_file(tmp_path, "src/app.py", source)
        with patch.object(
            orchestrator, "call_claude_for_file", return_value=("NO-EDIT: nothing here", ""),
        ) as call:
            implement_code(_implement_state(tmp_path))
        assert "- src/app.py" in call.call_args.args[0]

    def test_4514_every_new_check_reaches_the_verdict(self):
        """Through `_run_checks` itself: a check that runs and is then dropped
        from the list would never fail a spec."""

        def verdict(name):
            return lambda *_args, **_kwargs: {"check_name": name, "passed": True, "details": ""}

        stubs = [
            patch.object(validate_completeness, name, side_effect=verdict(name))
            for name in dir(validate_completeness) if name.startswith("check_")
        ]
        for stub in stubs:
            stub.start()
        try:
            with patch.object(validate_completeness, "_record_hallucination_telemetry"):
                checks = validate_completeness._run_checks({"issue_number": 7}, "# Spec")
        finally:
            for stub in stubs:
                stub.stop()
        names = {check["check_name"] for check in checks}
        assert {
            "check_spec_tests_pass_target_lint",
            "check_spec_tests_start_js_tools_in_their_project",
            "check_spec_tests_name_filters_can_match",
        } <= names

    def test_4515_the_pytest_cap_quotes_the_stall(self):
        source = inspect.getsource(verify_phases._verify_green_pytest_single)
        assert "_with_the_stall(" in source

    def test_4517_a_node_of_the_graph_names_itself(self):
        with (
            patch("assemblyzero.workflows.narration.narrated", side_effect=lambda _n, fn, *a, **k: fn),
            patch.object(graph_module, "load_lld", return_value={"x": 1}),
        ):
            workflow = build_testing_workflow()
        runnable = getattr(workflow.nodes["N0_load_lld"], "runnable", workflow.nodes["N0_load_lld"])
        node = getattr(runnable, "func", runnable)
        assert node({})["last_node"] == "N0_load_lld"


class TestT4517TheHaltSaysWhere:
    def test_t1_the_node_that_ran_is_recorded(self):
        node = _names_itself("N5_verify_green", lambda state: {"error_message": "stuck"})
        assert node({})["last_node"] == "N5_verify_green"

    def test_t1_the_halt_reports_that_node(self):
        state = {"iteration_count": 3, "last_node": "N5_verify_green"}
        assert _infer_stage(state, "testing") == "N5_verify_green"

    def test_a_workflow_that_records_nothing_is_inferred_as_before(self):
        assert _infer_stage({"iteration_count": 0}, "testing") == "N0_load"

    def test_a_node_returning_nothing_is_left_alone(self):
        assert _names_itself("N0", lambda state: None)({}) is None

    def test_t2_an_exhausted_budget_has_its_own_type(self):
        message = "Green phase failed after 3 iterations: 1 tests still failing (vitest)"
        assert classify_error(message) == "iterations_exhausted"

    def test_a_quoted_failure_cannot_reclassify_the_halt(self):
        message = "Green phase failed after 3 iterations. The failure: status 529 overloaded"
        assert classify_error(message) == "iterations_exhausted"


def _spec_with_test(body: str) -> str:
    return textwrap.dedent(
        """\
        # Spec

        ## 10. Test Mapping

        ### 10.1 Test Functions

        ```python
        {body}
        ```
        """
    ).replace("{body}", body)


UNUSED_IMPORT = "import os\n\n\ndef test_req_01():\n    assert True"
CLEAN = "def test_req_01():\n    assert True"
NPX_NO_CWD = (
    "import subprocess\n\n\ndef test_req_01():\n"
    '    res = subprocess.run(["npx", "tsc"], capture_output=True, check=False)\n'
    "    assert res.returncode == 0"
)
NPX_WITH_CWD = NPX_NO_CWD.replace("capture_output=True", 'capture_output=True, cwd="web"')


class TestT4514TheSpecsTestsAreProven:
    @pytest.fixture
    def ruff_target(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.ruff.lint]\nselect = ["F"]\n', encoding="utf-8",
        )
        return tmp_path

    @pytest.mark.skipif(shutil.which("ruff") is None, reason="no ruff on PATH")
    def test_t1_an_unused_import_is_refused_naming_the_rule(self, ruff_target):
        check = check_spec_tests_pass_target_lint(
            _spec_with_test(UNUSED_IMPORT), 7, [], str(ruff_target),
        )
        assert check["passed"] is False
        assert "F401" in check["details"]

    @pytest.mark.skipif(shutil.which("ruff") is None, reason="no ruff on PATH")
    def test_a_clean_body_passes(self, ruff_target):
        check = check_spec_tests_pass_target_lint(
            _spec_with_test(CLEAN), 7, [], str(ruff_target),
        )
        assert check["passed"] is True, check["details"]

    def test_a_target_with_no_ruff_configuration_has_no_rule_to_break(self, tmp_path):
        with patch.object(shutil, "which", side_effect=AssertionError("must not look")):
            check = check_spec_tests_pass_target_lint(
                _spec_with_test(UNUSED_IMPORT), 7, [], str(tmp_path),
            )
        assert check["passed"] is True

    def test_a_configured_target_with_no_ruff_cannot_be_checked(self, ruff_target):
        with (
            patch("shutil.which", return_value=None),
            pytest.raises(CompletenessCannotCheck, match="no ruff is on PATH"),
        ):
            check_spec_tests_pass_target_lint(
                _spec_with_test(CLEAN), 7, [], str(ruff_target),
            )

    def test_a_ruff_that_breaks_is_loud(self, ruff_target):
        broken = SimpleNamespace(returncode=2, stdout="", stderr="bad config")
        with (
            patch("subprocess.run", return_value=broken),
            patch("shutil.which", return_value="ruff"),
            pytest.raises(CompletenessCannotCheck, match="bad config"),
        ):
            check_spec_tests_pass_target_lint(
                _spec_with_test(CLEAN), 7, [], str(ruff_target),
            )

    def test_no_repo_root_cannot_be_checked(self):
        with pytest.raises(CompletenessCannotCheck):
            check_spec_tests_pass_target_lint(_spec_with_test(CLEAN), 7, [], "")

    def test_t2_a_js_tool_with_no_cwd_is_refused(self, tmp_path):
        (tmp_path / "web").mkdir()
        (tmp_path / "web" / "package.json").write_text("{}", encoding="utf-8")
        check = check_spec_tests_start_js_tools_in_their_project(
            _spec_with_test(NPX_NO_CWD), 7, [], str(tmp_path),
        )
        assert check["passed"] is False
        assert "`test_req_01` runs npx" in check["details"]

    def test_t2_a_js_tool_with_cwd_passes(self, tmp_path):
        check = check_spec_tests_start_js_tools_in_their_project(
            _spec_with_test(NPX_WITH_CWD), 7, [], str(tmp_path),
        )
        assert check["passed"] is True, check["details"]

    def test_a_project_at_the_root_needs_no_cwd(self, tmp_path):
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        check = check_spec_tests_start_js_tools_in_their_project(
            _spec_with_test(NPX_NO_CWD), 7, [], str(tmp_path),
        )
        assert check["passed"] is True

    def test_a_python_tool_is_not_this_checks_business(self, tmp_path):
        body = NPX_NO_CWD.replace('"npx"', '"git"')
        check = check_spec_tests_start_js_tools_in_their_project(
            _spec_with_test(body), 7, [], str(tmp_path),
        )
        assert check["passed"] is True, check["details"]

    def test_t2_a_tool_held_in_a_variable_is_seen_too(self, tmp_path):
        body = NPX_NO_CWD.replace('["npx", "tsc"]', '[npx, "tsc"]').replace(
            "    res = ", '    npx = "x"\n    res = ',
        )
        check = check_spec_tests_start_js_tools_in_their_project(
            _spec_with_test(body), 7, [], str(tmp_path),
        )
        assert check["passed"] is False
        assert "runs npx" in check["details"]

    def test_t4_a_filter_with_a_bare_group_is_refused(self):
        body = (
            "import subprocess\n\n\ndef test_req_01():\n"
            '    res = subprocess.run(["npx", "vitest", "run", "-t", "REQ-5 (row 080)"], cwd="web")\n'
            "    assert res.returncode == 0"
        )
        check = check_spec_tests_name_filters_can_match(_spec_with_test(body), 7, [])
        assert check["passed"] is False
        assert "`test_req_01` filters on REQ-5 (row 080)" in check["details"]

    def test_t4_an_escaped_filter_passes(self):
        body = (
            "import subprocess\n\n\ndef test_req_01():\n"
            '    res = subprocess.run(["npx", "vitest", "run", "-t", r"REQ-5 \\(row 080\\)"], cwd="web")\n'
            "    assert res.returncode == 0"
        )
        check = check_spec_tests_name_filters_can_match(_spec_with_test(body), 7, [])
        assert check["passed"] is True, check["details"]

    def test_t4_a_group_that_alternates_is_a_real_filter(self):
        body = (
            "import subprocess\n\n\ndef test_req_01():\n"
            '    res = subprocess.run(["npx", "vitest", "run", "-t", "(a|b)"], cwd="web")\n'
            "    assert res.returncode == 0"
        )
        check = check_spec_tests_name_filters_can_match(_spec_with_test(body), 7, [])
        assert check["passed"] is True, check["details"]


    @pytest.mark.parametrize("check", [
        lambda spec, root: check_spec_tests_pass_target_lint(spec, 7, [], root),
        lambda spec, root: check_spec_tests_start_js_tools_in_their_project(spec, 7, [], root),
        lambda spec, root: check_spec_tests_name_filters_can_match(spec, 7, []),
    ], ids=["lint", "js_tools", "name_filters"])
    def test_a_file_that_cannot_be_emitted_fails_every_check(self, check, ruff_target):
        with patch.object(
            scaffold_tests, "generate_spec_test_file_content",
            side_effect=scaffold_tests.ScaffoldImportError("imports nothing it names"),
        ):
            result = check(_spec_with_test(CLEAN), str(ruff_target))
        assert result["passed"] is False, "fails closed, never on another check's word"
        assert "imports nothing it names" in result["details"]

    @pytest.mark.skipif(shutil.which("ruff") is None, reason="no ruff on PATH")
    def test_a_finding_names_the_function_the_drafter_may_change(self, ruff_target):
        body = "def test_req_01():\n    unused_name = 1\n    assert True"
        (ruff_target / "pyproject.toml").write_text(
            '[tool.ruff.lint]\nselect = ["F841"]\n', encoding="utf-8",
        )
        check = check_spec_tests_pass_target_lint(_spec_with_test(body), 7, [], str(ruff_target))
        assert check["passed"] is False
        assert "`test_req_01`" in check["details"]


class TestTheEditScriptStillDeclines:
    def test_no_edit_leaves_the_file_as_it_was(self):
        outcome = apply_code_edit_script("NO-EDIT: nothing here", "body\n")
        assert outcome.code == "body\n"
        assert outcome.no_edit == "nothing here"
