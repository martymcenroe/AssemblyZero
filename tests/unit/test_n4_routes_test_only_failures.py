"""A failure that names only a test file reaches the code under test (#4694).

A real implementation run on a TypeScript target stopped at 28 of 29 Vitest
tests. The one failure's frame named only the test file, so #2851 left the
planned source file unchanged that iteration. The model on the test file
answered NO-EDIT and named the source file and the function where the fix
belonged, nothing routed the failure there, and N4 changed no file until the
iteration cap.

Same harness as `test_failed_patch_on_a_test_file_leaves_it.py`:
`implement_code` driven with the model calls stubbed, so what is asserted is
which file is offered which failure.
"""

from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.nodes import verify_phases
from assemblyzero.workflows.testing.nodes.implementation import (
    decline_routing,
    edit_script_fix,
    orchestrator,
)

BIG = "// " + ("x" * 900) + "\n"  # over MIN_BYTES_FOR_EDIT_SCRIPT, under the large-file line

SOURCE = "web/shared/settlement.ts"
UNRELATED = "web/shared/catalogue.ts"
TEST = "web/tests/settle.test.ts"

# The frame names the test file alone, as Vitest prints a failed assertion.
# Nothing here may carry a token of SOURCE or UNRELATED.
CORPUS = """\
FAIL web/tests/settle.test.ts > the shown value follows the turn
    AssertionError: expected 20 to be 25 // Object.is equality
     at web/tests/settle.test.ts:5:48
"""

REASON = (
    "The fix belongs in web/shared/settlement.ts where resolve() must update "
    "next.last_shown_price_usd_per_mwh to the next turn's value, e.g. after a step."
)


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "web" / "shared").mkdir(parents=True)
    (tmp_path / "web" / "tests").mkdir(parents=True)
    (tmp_path / SOURCE).write_text(BIG + "export function resolve() { return 20; }\n", encoding="utf-8")
    (tmp_path / UNRELATED).write_text(BIG + "export const shelf = [];\n", encoding="utf-8")
    return tmp_path


def _write_test(repo, imports_source: bool):
    head = 'import { resolve } from "../shared/settlement";\n' if imports_source else ""
    (repo / TEST).write_text(head + BIG + "it('x', () => {});\n", encoding="utf-8")


def _run(repo, capsys, order, no_edit_for=None, extra_state=None):
    """Drive one revision; return [(file, failure_context)] in call order, the output, the result."""
    offered: list[tuple[str, str]] = []

    def fake_edit(filepath, **kwargs):
        offered.append((filepath, kwargs["failure_context"]))
        if no_edit_for and filepath in no_edit_for:
            return edit_script_fix.EditScriptOutcome(
                kwargs["existing_content"], no_edit=no_edit_for[filepath]
            )
        return edit_script_fix.EditScriptOutcome(kwargs["existing_content"], failures=[])

    def fake_regen(filepath, **kwargs):
        raise AssertionError(f"no file should be regenerated here: {filepath}")

    state = {
        "repo_root": str(repo),
        "lld_content": "## 2.1 Files\n",
        "files_to_modify": [{"path": p, "change_type": "Modify"} for p in order],
        "test_files": [TEST],
        "iteration_count": 1,
        "test_failure_summary": CORPUS,
        "audit_dir": str(repo / "audit"),
        **(extra_state or {}),
    }
    with patch.object(orchestrator, "try_edit_script_fix", fake_edit), \
         patch.object(orchestrator, "generate_file_with_retry", fake_regen), \
         patch.object(orchestrator, "validate_files_to_modify", return_value=[]), \
         patch.object(orchestrator, "record_iteration_cost", return_value=0), \
         patch.object(orchestrator, "get_cumulative_cost", return_value=0.0), \
         patch.object(orchestrator, "registered_test_files", return_value=[TEST]):
        # registered_test_files: this fixture has no Vitest config to own the
        # test file, and test ownership is not what is under test here. With
        # it stubbed the node runs to its end, so nothing is swallowed.
        result = orchestrator.implement_code(state)
    return offered, capsys.readouterr().out, result


class TestATestOnlyFailureReachesTheCodeUnderTest:
    """R1, T1 and R4, T4."""

    def test_the_imported_source_is_offered_the_edit(self, repo, capsys):
        _write_test(repo, imports_source=True)
        offered, out, _ = _run(repo, capsys, [SOURCE, UNRELATED, TEST])

        assert SOURCE in [f for f, _ in offered], offered
        assert f"no failure attributed to {SOURCE}" not in out
        assert "the planned source file(s) they import are offered the edit too" in out

    def test_a_file_neither_named_nor_imported_stays_unchanged(self, repo, capsys):
        _write_test(repo, imports_source=True)
        offered, out, _ = _run(repo, capsys, [SOURCE, UNRELATED, TEST])

        assert UNRELATED not in [f for f, _ in offered], offered
        assert f"no failure attributed to {UNRELATED}; left unchanged" in out

    def test_without_the_import_the_skip_still_holds(self, repo, capsys):
        _write_test(repo, imports_source=False)
        offered, out, _ = _run(repo, capsys, [SOURCE, UNRELATED, TEST])

        assert [f for f, _ in offered] == [TEST], offered
        assert f"no failure attributed to {SOURCE}; left unchanged" in out


class TestADeclineRoutesTheFailureToTheFileItNames:
    """R2, T2."""

    def test_a_later_file_gets_the_failure_and_the_reason_this_iteration(self, repo, capsys):
        _write_test(repo, imports_source=False)
        offered, out, _ = _run(repo, capsys, [TEST, SOURCE, UNRELATED], no_edit_for={TEST: REASON})

        files = [f for f, _ in offered]
        assert files == [TEST, SOURCE], offered
        context = dict(offered)[SOURCE]
        assert "declined to edit it (NO-EDIT)" in context
        assert REASON in context
        assert CORPUS.strip() in context
        assert f"the decline names {SOURCE}; it gets this failure and the reason this iteration" in out

    def test_an_earlier_file_gets_it_first_next_iteration(self, repo, capsys):
        _write_test(repo, imports_source=False)
        offered, out, result = _run(repo, capsys, [SOURCE, UNRELATED, TEST], no_edit_for={TEST: REASON})

        assert [f for f, _ in offered] == [TEST], offered
        assert "already passed this iteration; it gets this failure first next iteration" in out
        assert result is not None, out
        assert result["declined_routes"] == {SOURCE: (TEST, REASON)}

    def test_the_next_iteration_offers_the_routed_file_first_with_the_reason(self, repo, capsys):
        _write_test(repo, imports_source=False)
        offered, _out, _ = _run(
            repo, capsys, [UNRELATED, TEST, SOURCE],
            extra_state={"declined_routes": {SOURCE: [TEST, REASON]}},
        )

        files = [f for f, _ in offered]
        assert files[0] == SOURCE, offered
        assert REASON in dict(offered)[SOURCE]
        assert UNRELATED not in files, offered


class TestADeclineOutsideThePlanIsReported:
    """R3, T3."""

    def test_it_is_named_at_once_and_in_the_stall(self, repo, capsys):
        _write_test(repo, imports_source=False)
        reason = "The fix belongs in web/worker/fold.ts, which builds the state."
        offered, out, result = _run(repo, capsys, [TEST, SOURCE], no_edit_for={TEST: reason})

        assert [f for f, _ in offered] == [TEST], offered
        assert "the decline names web/worker/fold.ts, which is not in the plan" in out
        assert result is not None, out
        assert result["declines_outside_plan"] == [(TEST, "web/worker/fold.ts")]
        assert "A NO-EDIT named a file outside the plan" in result["nothing_changed"]
        assert "web/worker/fold.ts" in result["nothing_changed"]

    def test_the_cap_halt_reports_it_when_the_last_pass_changed_something(self):
        state = {
            "nothing_changed": "",
            "declines_outside_plan": [[TEST, "web/worker/fold.ts"]],
        }
        reason = verify_phases._with_the_stall("Green phase failed after 3 iterations", state)

        assert "web/worker/fold.ts" in reason
        assert reason.startswith("Green phase failed after 3 iterations. A NO-EDIT named a file outside the plan")


class TestTheHelpers:
    def test_files_named_reads_paths_and_tails_not_dotted_words(self):
        planned = [SOURCE, UNRELATED, TEST]
        inside, outside = decline_routing.files_named(
            "Fix settlement.ts; see web/tests/settle.test.ts, e.g. "
            "next.last_shown_price_usd_per_mwh, and lib/other.py.",
            planned,
        )
        assert inside == [SOURCE, TEST]
        assert outside == ["lib/other.py"]

    def test_a_src_layout_python_test_reaches_its_module(self, tmp_path):
        (tmp_path / "src" / "pkg").mkdir(parents=True)
        (tmp_path / "tests" / "unit").mkdir(parents=True)
        (tmp_path / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "src" / "pkg" / "compiler.py").write_text("def validate(): pass\n", encoding="utf-8")
        (tmp_path / "tests" / "unit" / "test_compiler.py").write_text(
            "from pkg import compiler\nfrom pkg.compiler import validate\n", encoding="utf-8"
        )
        found = decline_routing.exercised_sources(
            ["tests/unit/test_compiler.py"],
            ["src/pkg/compiler.py", "tests/unit/test_compiler.py"],
            tmp_path,
        )
        assert found == {"src/pkg/compiler.py"}

    def test_is_test_path_reads_relative_plan_paths(self):
        assert decline_routing.is_test_path("tests/unit/test_compiler.py")
        assert decline_routing.is_test_path(TEST)
        assert not decline_routing.is_test_path(SOURCE)
        assert not decline_routing.is_test_path("src/pkg/compiler.py")
