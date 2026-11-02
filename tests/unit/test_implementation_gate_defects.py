"""Four defects a real implementation run showed in its own gates.

#4525: one failed test was counted as eleven regressions.
#4523: a run passed all its steps and failed the target's CI at once.
#4521: the import check refused an import the file already had, and the retry
rewrote the line to get past it.
#4522: a whole-file reply changed a line nothing asked it to, and every gate
passed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

import assemblyzero.workflows.implementation_spec.nodes.validate_completeness  # noqa: F401
from assemblyzero.workflows.testing.audit import parse_pytest_output
from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.graph import (
    _stop_after_final_suite,
    route_after_final_suite,
)
from assemblyzero.workflows.testing.nodes import verify_phases
from assemblyzero.workflows.testing.nodes.implementation import orchestrator
from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
    validate_imports,
)
from assemblyzero.workflows.testing.nodes.implementation.parsers import (
    dynamic_imports,
    validate_code_response,
)
from assemblyzero.workflows.testing.nodes.implementation.schema_keywords import (
    unknown_schema_keywords,
)
from assemblyzero.workflows.testing.nodes.implementation.unrequested_changes import (
    spec_hunks,
    unrequested_lines,
)
from assemblyzero.workflows.testing.nodes.verify_phases import (
    _late_files_to_repair,
    verify_final_suite,
)
from assemblyzero.workflows.testing.runners.jest_runner import JestRunner
from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner

#: The module, not the node function of the same name its package exports.
validate_completeness = sys.modules[
    "assemblyzero.workflows.implementation_spec.nodes.validate_completeness"
]

# ---------------------------------------------------------------------------
# #4525: the regression count
# ---------------------------------------------------------------------------

#: The shape of the run's output: a target's own lint test, failing with what
#: ruff printed, whose last line is ruff's own count.
LINT_TEST = '''\
def test_ruff_reports_nothing():
    findings = "\\n".join(
        f"tests/unit/test_x.py:{n}:5: F811 Redefinition of unused `a`" for n in range(1, 11)
    )
    raise AssertionError(findings + "\\nFound 10 errors.")


def test_a():
    assert True
'''


def _real_pytest(tmp_path: Path, source: str) -> str:
    """What pytest really prints for `source`, in the form the gate reads."""
    (tmp_path / "test_target.py").write_text(source, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-vv", "--tb=short", "-p", "no:cacheprovider", "."],
        cwd=tmp_path, capture_output=True, text=True, timeout=60, check=False,
    )
    return result.stdout + result.stderr


class TestT4525TheRegressionCount:
    def test_t1_a_failed_test_whose_message_counts_ten_is_one_regression(self, tmp_path):
        parsed = parse_pytest_output(_real_pytest(tmp_path, LINT_TEST))
        assert (parsed["failed"], parsed["errors"], parsed["passed"]) == (1, 0, 1)

    def test_t1_the_gate_reports_one(self, tmp_path, capsys):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        output = _real_pytest(tmp_path, LINT_TEST)
        with (
            patch.object(verify_phases, "run_pytest", return_value={
                "stdout": output, "stderr": "", "returncode": 1,
                "parsed": parse_pytest_output(output),
            }),
            patch.object(verify_phases, "log_workflow_execution"),
        ):
            gate = verify_phases._full_suite_gate(
                {"repo_root": str(tmp_path), "issue_number": 1},
                tmp_path, TestFramework.PYTEST, None, 0, 3,
            )
        assert "1 regression(s) detected" in capsys.readouterr().out
        assert gate["next_node"] == "N4_implement_code"
        assert len(gate["full_suite_regressions"]) == 1

    def test_t2_three_failed_tests_count_three(self, tmp_path):
        source = "\n".join(f"def test_{n}():\n    assert False\n" for n in "abc")
        parsed = parse_pytest_output(_real_pytest(tmp_path, source))
        assert (parsed["failed"], parsed["errors"]) == (3, 0)

    def test_a_real_collection_error_is_still_counted(self, tmp_path):
        parsed = parse_pytest_output(_real_pytest(tmp_path, "import no_such_module_at_all\n"))
        assert parsed["errors"] == 1

    @pytest.mark.parametrize(
        "line, failed, passed",
        [
            ("===== 1 failed, 104 passed, 2 warnings in 3.21s =====", 1, 104),
            ("1 failed, 104 passed in 62.30s (0:01:02)", 1, 104),
            ("================ 1 failed, 3 subtests passed in 0.10s ================", 1, 0),
        ],
    )
    def test_the_closing_line_in_each_shape_pytest_writes_it(self, line, failed, passed):
        parsed = parse_pytest_output(f"E   Found 10 errors.\nE   7 failed earlier\n{line}\n")
        assert (parsed["failed"], parsed["passed"], parsed["errors"]) == (failed, passed, 0)

    def test_output_with_no_closing_line_counts_nothing(self):
        """An interrupted run is not read from whatever its output mentions.
        The gate's exit check then says it cannot be read as clean."""
        parsed = parse_pytest_output("E   Found 10 errors.\nKilled\n")
        assert (parsed["failed"], parsed["errors"], parsed["passed"]) == (0, 0, 0)

    def test_the_runner_reads_the_same_line(self, tmp_path):
        runner = PytestRunner(
            {"framework": TestFramework.PYTEST, "test_command": "", "file_pattern": ""},
            str(tmp_path),
        )
        result = runner.parse_results(_real_pytest(tmp_path, LINT_TEST), 1)
        assert (result["failed"], result["errors"], result["passed"]) == (1, 0, 1)


# ---------------------------------------------------------------------------
# #4521: the import check
# ---------------------------------------------------------------------------

BASE_WITH_NUMPY = textwrap.dedent('''\
    """A module."""

    def f():
        import numpy as np
        return np.zeros(1)

    def g():
        return 1
''')


def _target(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir(exist_ok=True)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "pkg"\nversion = "0"\n', encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def this_interpreter():
    """The target's environment is this one: only the lookup of its path is
    replaced, and the probe itself really runs."""
    with patch.object(
        validate_completeness, "_target_env_python", return_value=sys.executable,
    ):
        yield


class TestT4521TheImportCheck:
    def test_t1_a_modify_keeping_an_undeclared_import_passes(self, tmp_path):
        target = _target(tmp_path)
        code = BASE_WITH_NUMPY.replace("return 1", "return 2")
        with patch.object(
            validate_completeness, "_probe_target_env", return_value={"numpy": False},
        ):
            valid, message = validate_code_response(
                code, "pkg/mod.py", BASE_WITH_NUMPY, repo_root=str(target),
            )
        assert valid, message

    def test_t1_an_add_on_a_file_the_base_ships_passes_too(self, tmp_path):
        """N4 calls such a file Add and hands the validator no base, so the
        base is read from the tree."""
        target = _target(tmp_path)
        (target / "pkg" / "mod.py").write_text(BASE_WITH_NUMPY, encoding="utf-8")
        with patch.object(
            validate_completeness, "_probe_target_env", return_value={"numpy": False},
        ):
            valid, message = validate_code_response(
                BASE_WITH_NUMPY, "pkg/mod.py", "", repo_root=str(target),
            )
        assert valid, message

    def test_t2_a_new_import_the_environment_has_passes(self, tmp_path, this_interpreter):
        target = _target(tmp_path)
        ok, bad = validate_imports("import yaml\n", "pkg/new.py", target)
        assert (ok, bad) == (True, [])

    def test_t2_a_new_import_the_environment_lacks_is_refused(self, tmp_path, this_interpreter):
        target = _target(tmp_path)
        ok, bad = validate_imports("import no_such_module_at_all\n", "pkg/new.py", target)
        assert not ok
        assert bad == ["no_such_module_at_all (line 1)"]

    def test_a_first_party_name_is_never_passed_by_the_environment(
        self, tmp_path, this_interpreter,
    ):
        """The hallucination #842 catches: the package is real and importable,
        and the submodule is not."""
        target = _target(tmp_path)
        (target / "yaml").mkdir()
        (target / "yaml" / "__init__.py").write_text("", encoding="utf-8")
        ok, bad = validate_imports("import yaml.no_such_thing.deeper\n", "pkg/new.py", target)
        assert not ok
        assert "yaml.no_such_thing.deeper (line 1)" in bad

    def test_an_environment_that_cannot_answer_stops_the_check(self, tmp_path):
        """Neither a pass nor a refusal: nobody answered (ADR 0236)."""
        target = _target(tmp_path)
        with (
            patch.object(
                validate_completeness, "_target_env_python",
                side_effect=validate_completeness.CompletenessCannotCheck("poetry is gone"),
            ),
            pytest.raises(validate_completeness.CompletenessCannotCheck, match="poetry is gone"),
        ):
            validate_imports("import yaml_like_thing\n", "pkg/new.py", target)

    def test_a_base_that_does_not_parse_stops_the_check(self, tmp_path, capsys):
        target = _target(tmp_path)
        with pytest.raises(SyntaxError):
            validate_code_response(
                "import no_such_module_at_all\n\nx = 1\n", "pkg/mod.py", "def broken(:\n",
                repo_root=str(target),
            )
        assert "does not parse" in capsys.readouterr().err

    def test_the_base_is_not_read_when_nothing_needs_it(self, tmp_path):
        target = _target(tmp_path)
        valid, message = validate_code_response(
            "import os\n\nx = os.sep\n", "pkg/mod.py", "def broken(:\n", repo_root=str(target),
        )
        assert valid, message

    def test_a_target_with_no_project_is_not_asked(self, tmp_path):
        with patch.object(validate_completeness, "_probe_target_env") as probe:
            ok, _ = validate_imports("import yaml_like_thing\n", "new.py", tmp_path)
        assert not ok
        probe.assert_not_called()

    @pytest.mark.parametrize("line", [
        'np = importlib.import_module("numpy")',
        'np = sys.modules.get("numpy") or importlib.import_module("numpy")',
        'np = sys.modules["numpy"]',
        'from importlib import import_module\nnp = import_module("numpy")',
        'from sys import modules\nnp = modules["numpy"]',
        'np = __import__("numpy")',
    ])
    def test_t3_a_dynamic_import_the_file_did_not_have_is_refused(self, tmp_path, line):
        target = _target(tmp_path)
        base = "import importlib\nimport sys\n\n\ndef f():\n    return 1\n"
        code = base + "\n\n" + line + "\n"
        valid, message = validate_code_response(code, "pkg/mod.py", base, repo_root=str(target))
        assert not valid
        assert "Dynamic import" in message
        assert f"line {len(base.splitlines()) + 3}" in message

    def test_t3_the_refusal_says_what_to_write_instead(self, tmp_path):
        target = _target(tmp_path)
        code = 'import importlib\n\n\nnp = importlib.import_module("numpy")\n'
        _, message = validate_code_response(code, "pkg/mod.py", "x = 1\n", repo_root=str(target))
        assert "a plain import statement" in message

    def test_a_file_that_already_had_a_dynamic_import_keeps_it(self, tmp_path):
        target = _target(tmp_path)
        base = 'import importlib\n\n\ndef load(n):\n    return importlib.import_module(n)\n'
        valid, message = validate_code_response(
            base + "\n\nVALUE = 1\n", "pkg/mod.py", base, repo_root=str(target),
        )
        assert valid, message

    def test_a_spec_that_asks_for_it_is_not_refused(self, tmp_path):
        target = _target(tmp_path)
        code = 'import importlib\n\n\ndef load(n):\n    return importlib.import_module(n)\n'
        valid, message = validate_code_response(
            code, "pkg/mod.py", "x = 1\n", repo_root=str(target),
            spec_text="Load it with `importlib.import_module(name)`.",
        )
        assert valid, message

    def test_only_a_call_of_the_family_is_found(self):
        code = '"""sys.modules and importlib.import_module, in a docstring."""\nimport sys\nx = sys.path\n'
        assert dynamic_imports(code) == []


# ---------------------------------------------------------------------------
# #4522: what a reply changed that nothing asked for
# ---------------------------------------------------------------------------

SCHEMA_BASE = textwrap.dedent('''\
    {
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "type": "object",
      "properties": {
        "step_minutes": { "type": "integer", "minimum": 1 },
        "site": {
          "type": "object",
          "properties": {
            "fuel": { "type": "number" }
          }
        }
      }
    }
''')

SPEC = textwrap.dedent('''\
    ## 5. Functions

    ### 5.1 `schema/pack.schema.json`

    ```diff
    @@ -1,1 +1,1 @@
    -"not": "section six",
    +"not": "this either",
    ```

    ## 6. Change Instructions

    ### 6.1 `schema/pack.schema.json` (Modify)

    Add `stocks` to `site.properties`.

    ```diff
    @@ -6,6 +6,7 @@
             "type": "object",
             "properties": {
    -          "fuel": { "type": "number" }
    +          "fuel": { "type": "number" },
    +          "stocks": { "type": "array" }
             }
           }
         }
    ```

    ### 6.2 `src/app.py` (Add)

    ```python
    value = 1
    ```

    ## 7. Tests
''')

ASKED_FOR = SCHEMA_BASE.replace(
    '"fuel": { "type": "number" }\n',
    '"fuel": { "type": "number" },\n          "stocks": { "type": "array" }\n',
)

STEP_MINUTES = (
    '"step_minutes": { "integer": { "type": "integer", "minimum": 1 }, '
    '"type": "integer", "minimum": 1 },'
)


class TestT4522WhatTheReplyChanged:
    def _changed(self, new_text: str, base: str = SCHEMA_BASE) -> list:
        return unrequested_lines(base, new_text, spec_hunks(SPEC)["schema/pack.schema.json"])

    def test_the_hunks_come_from_section_six_alone(self):
        hunks = spec_hunks(SPEC)
        assert list(hunks) == ["schema/pack.schema.json"]
        assert len(hunks["schema/pack.schema.json"]) == 1
        assert '"not": "this either",' not in hunks["schema/pack.schema.json"][0].added

    def test_t1_a_line_outside_the_hunks_is_reported_by_name(self):
        reply = ASKED_FOR.replace('"step_minutes": { "type": "integer", "minimum": 1 },', STEP_MINUTES)
        changed = self._changed(reply)
        assert [(c.line, c.text) for c in changed] == [(5, STEP_MINUTES)]

    def test_t2_a_reply_changing_only_the_specified_lines_reports_nothing(self):
        assert self._changed(ASKED_FOR) == []

    def test_t2_a_line_reworded_inside_a_hunk_reports_nothing(self):
        """Inside the hunk is what R1 asks, whatever the wording: a reformat of
        an asked-for line is not an unrequested change."""
        assert self._changed(ASKED_FOR.replace('"array"', '"array", "minItems": 0')) == []

    def test_a_line_removed_outside_the_hunks_is_reported(self):
        changed = self._changed(ASKED_FOR.replace('  "type": "object",\n  "properties": {\n    "step', '  "properties": {\n    "step'))
        assert [c.text for c in changed] == ['"type": "object",']
        assert changed[0].kind == "removed"

    def test_an_unchanged_file_reports_nothing(self):
        assert self._changed(SCHEMA_BASE) == []

    def test_a_hunk_with_elided_context_still_covers_its_lines(self):
        spec = textwrap.dedent('''\
            ## 6. Change Instructions

            ### 6.1 `src/app.py` (Modify)

            ```diff
            @@ -95,6 +95,8 @@
                 ...

            +def added():
            +    return 1
            +
             def kept():
                 return 2
            ```
        ''')
        base = "def before():\n    return 0\n\n\ndef kept():\n    return 2\n"
        new = "def before():\n    return 0\n\n\ndef added():\n    return 1\n\n\ndef kept():\n    return 2\n"
        assert unrequested_lines(base, new, spec_hunks(spec)["src/app.py"]) == []

    def test_a_diff_fence_for_a_file_with_no_diff_gives_no_hunks(self):
        assert "src/app.py" not in spec_hunks(SPEC)


class TestT4522N4ReportsIt:
    def _run(self, tmp_path: Path, on_disk: str, capsys) -> tuple[dict, str]:
        repo = tmp_path
        schema = repo / "schema" / "pack.schema.json"
        schema.parent.mkdir()
        schema.write_text(SCHEMA_BASE, encoding="utf-8")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"],
            cwd=repo, check=True,
        )
        base = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True,
        ).stdout.strip()
        schema.write_text(on_disk, encoding="utf-8")
        with patch.object(orchestrator, "log_workflow_execution") as logged:
            found = orchestrator._report_unrequested_changes(
                {"repo_root": str(repo), "lld_content": SPEC, "base_commit": base,
                 "issue_number": 7, "base_branch": ""},
                repo,
                [{"path": "schema/pack.schema.json", "change_type": "Modify"}],
            )
        self.logged = logged
        return found, capsys.readouterr().out

    def test_t1_the_line_is_printed_and_the_run_goes_on(self, tmp_path, capsys):
        reply = ASKED_FOR.replace('"step_minutes": { "type": "integer", "minimum": 1 },', STEP_MINUTES)
        found, printed = self._run(tmp_path, reply, capsys)
        assert "schema/pack.schema.json line 5" in printed
        assert '"integer"' in printed
        assert "the run continues" in printed
        assert found == {"schema/pack.schema.json": [f"line 5: {STEP_MINUTES}"]}
        assert self.logged.call_args.kwargs["event"] == "unrequested_changes"

    def test_t2_nothing_is_reported_for_the_specified_lines(self, tmp_path, capsys):
        found, printed = self._run(tmp_path, ASKED_FOR, capsys)
        assert found == {}
        assert "IMPL" not in printed and "unrequested" not in printed.lower()
        self.logged.assert_not_called()


class TestT4522AJsonSchemasKeywords:
    def _validate(self, code: str, base: str = SCHEMA_BASE, spec_text: str = "") -> tuple[bool, str]:
        return validate_code_response(
            code, "schema/pack.schema.json", base, spec_text=spec_text,
        )

    def test_t3_the_step_minutes_line_is_refused(self):
        reply = ASKED_FOR.replace('"step_minutes": { "type": "integer", "minimum": 1 },', STEP_MINUTES)
        valid, message = self._validate(reply)
        assert not valid
        assert "/properties/step_minutes/integer" in message

    def test_a_property_named_like_nothing_is_a_name_not_a_keyword(self):
        assert unknown_schema_keywords(json.loads(ASKED_FOR)) == []

    def test_a_keyword_of_the_draft_passes(self):
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": {"a": {"type": "string", "pattern": "x", "description": "d"}},
            "prefixItems": [{"const": {"integer": 1}}],
            "if": {"required": ["a"]}, "then": True, "else": {"not": {"enum": [{"integer": 1}]}},
            "dependentSchemas": {"a": {"minimum": 1}},
        }
        assert unknown_schema_keywords(schema) == []

    def test_a_keyword_of_another_draft_is_refused(self):
        draft_07 = {"$schema": "http://json-schema.org/draft-07/schema#", "prefixItems": []}
        assert unknown_schema_keywords(draft_07) == ["/prefixItems"]

    def test_a_key_the_base_already_had_stays(self):
        base = SCHEMA_BASE.replace('"type": "object",\n  "properties"', '"x-note": "ok",\n  "type": "object",\n  "properties"')
        valid, message = self._validate(base.replace('"minimum": 1', '"minimum": 2'), base=base)
        assert valid, message

    def test_a_key_the_spec_asks_for_is_not_refused(self):
        reply = SCHEMA_BASE.replace('"type": "object",\n  "properties"', '"x-note": "ok",\n  "type": "object",\n  "properties"')
        valid, message = self._validate(reply, spec_text='add `"x-note"` at the top')
        assert valid, message

    def test_json_that_is_no_schema_is_left_alone(self):
        valid, message = validate_code_response(
            '{"integer": 1, "a": 2, "b": 3, "c": 4}', "data/x.json", "",
        )
        assert valid, message

    def test_a_reply_declaring_a_draft_that_is_not_json_is_refused(self):
        reply = SCHEMA_BASE.replace('"type": "object",\n  "properties"', '// a comment\n  "type": "object",\n  "properties"')
        valid, message = self._validate(reply)
        assert not valid
        assert "does not parse as JSON" in message

    def test_a_file_with_comments_that_declares_no_draft_is_not_read(self):
        tsconfig = '{\n  // comments are allowed here\n  "compilerOptions": {"strict": true}\n}\n'
        valid, message = validate_code_response(tsconfig, "web/tsconfig.json", "")
        assert valid, message

    def test_a_draft_nothing_knows_is_left_alone(self):
        schema = {"$schema": "https://example.com/my/own", "integer": 1}
        assert unknown_schema_keywords(schema) == []


# ---------------------------------------------------------------------------
# #4523 R1: the project's lint script
# ---------------------------------------------------------------------------

npm_runs = pytest.mark.skipif(shutil.which("npm") is None, reason="npm is not on this machine")


def _vitest_runner(tmp_path: Path, scripts: dict) -> JestRunner:
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "t", "version": "1.0.0", "scripts": scripts}), encoding="utf-8",
    )
    return JestRunner(
        {"framework": TestFramework.VITEST, "test_command": "", "file_pattern": ""},
        str(tmp_path),
    )


ALL_PASS = {
    "passed": 3, "failed": 0, "skipped": 0, "errors": 0, "total": 3,
    "coverage_percent": 100.0, "raw_output": "ok", "exit_code": 0,
    "failure_summary": "",
}


def _green(tmp_path: Path, runner: JestRunner, **overrides) -> dict:
    audit = tmp_path / "audit"
    audit.mkdir(exist_ok=True)
    state = {
        "repo_root": str(tmp_path), "test_files": ["a.test.ts"], "iteration_count": 0,
        "max_iterations": 3, "audit_dir": str(audit), "file_counter": 0,
        "coverage_target": 0, **overrides,
    }
    with (
        patch.object(verify_phases, "get_runner", return_value=runner),
        patch.object(verify_phases, "_changed_source_lines", return_value={}),
        patch.object(runner, "run_tests", return_value=dict(ALL_PASS)),
        patch.object(runner, "require_dependencies"),
        patch.object(runner, "read_line_coverage", return_value={}),
        patch.object(verify_phases, "_full_suite_gate", return_value=None),
        patch.object(verify_phases, "_note_measurement", return_value=None),
        patch.object(verify_phases, "log_workflow_execution"),
    ):
        return verify_phases._verify_green_non_pytest(
            state, {"framework": TestFramework.VITEST}, TestFramework.VITEST,
        )


@npm_runs
class TestT4523TheProjectsLint:
    def test_t1_a_failing_lint_routes_back_to_n4(self, tmp_path):
        script = "node -e \"console.log('a.test.ts  7:3  error  prefer-const'); process.exit(1)\""
        result = _green(tmp_path, _vitest_runner(tmp_path, {"lint": script}))
        assert result["next_node"] == "N4_implement_code"
        assert "prefer-const" in result["test_failure_summary"]
        assert "npm run lint" in result["test_failure_summary"]
        assert result["error_message"] == ""

    def test_t1_the_cap_says_it_was_the_lint(self, tmp_path):
        script = "node -e \"console.log('prefer-const'); process.exit(1)\""
        result = _green(
            tmp_path, _vitest_runner(tmp_path, {"lint": script}), iteration_count=2,
        )
        assert result["next_node"] == "end"
        assert "the project's lint still fails" in result["error_message"]

    def test_t2_a_target_with_no_lint_script_is_unaffected(self, tmp_path):
        runner = _vitest_runner(tmp_path, {"typecheck": "tsc"})
        assert runner.run_lint() is None
        result = _green(tmp_path, runner)
        assert result["next_node"] != "N4_implement_code"
        assert not result["error_message"]

    def test_a_passing_lint_goes_on(self, tmp_path):
        result = _green(tmp_path, _vitest_runner(tmp_path, {"lint": "node -e \"process.exit(0)\""}))
        assert result["next_node"] != "N4_implement_code"

    def test_a_project_with_no_package_json_has_no_lint(self, tmp_path):
        runner = JestRunner(
            {"framework": TestFramework.VITEST, "test_command": "", "file_pattern": ""},
            str(tmp_path),
        )
        assert runner.run_lint() is None


class TestT4523TheFinalSuite:
    """What N7.5 and N8 write reaches the full-suite gate before the landing."""

    def _state(self, tmp_path: Path, **overrides) -> dict:
        return {
            "repo_root": str(tmp_path), "issue_number": 7, "iteration_count": 1,
            "max_iterations": 5, "audit_dir": str(tmp_path / "audit"),
            "files_to_modify": [{"path": "src/app.py", "change_type": "Modify"}],
            "generated_test_files": {
                str(tmp_path / "tests/adversarial/test_adversarial_7.py"): "x",
            },
            **overrides,
        }

    def _final(self, tmp_path: Path, output: str, **overrides) -> dict:
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        state = self._state(tmp_path, **overrides)
        with (
            patch.object(verify_phases, "_framework_legs", return_value=[
                verify_phases._Leg({"framework": TestFramework.PYTEST}, TestFramework.PYTEST, ".", ()),
            ]),
            patch.object(verify_phases, "_gate_only_legs", return_value=[]),
            patch.object(verify_phases, "run_pytest", return_value={
                "stdout": output, "stderr": "",
                "returncode": 1 if " failed" in output else 0,
                "parsed": parse_pytest_output(output),
            }),
            patch.object(verify_phases, "log_workflow_execution"),
        ):
            return verify_final_suite(state)

    #: A target's lint test failing on a file the adversarial review wrote,
    #: as pytest reports it.
    LINT_ON_ADVERSARIAL = '''\
def test_ruff_reports_nothing():
    raise AssertionError(
        "tests/adversarial/test_adversarial_7.py:3:1: F811 Redefinition of unused `x`\\n"
        "Found 1 error."
    )


def test_a():
    assert True
'''

    def _failed(self, tmp_path: Path) -> str:
        suite = tmp_path / "suite"
        suite.mkdir()
        return _real_pytest(suite, self.LINT_ON_ADVERSARIAL)

    def test_t3_a_lint_failure_on_an_adversarial_file_stops_the_landing(self, tmp_path):
        result = self._final(tmp_path, self._failed(tmp_path))
        assert result["next_node"] == "N4_implement_code"
        assert route_after_final_suite({**self._state(tmp_path), **result}) == "N4_implement_code"
        assert "tests/adversarial/test_adversarial_7.py" in result["test_failure_summary"]
        assert result["late_failures"] == ["tests/adversarial/test_adversarial_7.py"]

    def test_t3_at_the_cap_the_halt_names_the_file(self, tmp_path):
        result = self._final(
            tmp_path, self._failed(tmp_path), iteration_count=4, full_suite_repair_passes=2,
        )
        state = {**self._state(tmp_path), **result}
        assert route_after_final_suite(state) == "HALT"
        assert "tests/adversarial/test_adversarial_7.py" in _stop_after_final_suite(state)["error_message"]

    def test_t3_the_file_becomes_n4s_to_repair(self, tmp_path):
        result = self._final(tmp_path, self._failed(tmp_path))
        paths = [f["path"] for f in result["files_to_modify"]]
        assert paths == ["src/app.py", "tests/adversarial/test_adversarial_7.py"]
        assert result["files_to_modify"][1]["change_type"] == "Modify"

    def test_a_clean_suite_lands(self, tmp_path, capsys):
        result = self._final(tmp_path, "===== 105 passed in 3.00s =====\n")
        assert result["next_node"] == "N9_cleanup"
        assert route_after_final_suite({**self._state(tmp_path), **result}) == "N9_cleanup"

    def test_a_suite_that_cannot_run_halts(self, tmp_path):
        result = self._final(tmp_path, "===== no tests ran in 0.01s =====\n")
        assert result["error_message"]
        assert route_after_final_suite({**self._state(tmp_path), **result}) == "HALT"

    def test_a_mock_run_lands(self, tmp_path):
        assert verify_final_suite({"mock_mode": True})["next_node"] == "N9_cleanup"


class TestT4523AFailingAdversarialTestIsEvidence:
    """A test the review wrote that fails is not N4's to rewrite: that would
    pass the review by editing it. A file a lint test names is."""

    FILE = "tests/adversarial/test_adversarial_7.py"

    def test_a_failing_adversarial_test_stays_as_written(self, tmp_path):
        state = {"repo_root": str(tmp_path), "generated_test_files": {str(tmp_path / self.FILE): "x"}}
        regressions = [f"{self.FILE}::test_overflow"]
        summary = f"FAILED {self.FILE}::test_overflow\nAssertionError\n"
        assert _late_files_to_repair(state, regressions, summary) == []

    def test_a_file_a_lint_test_names_is_repaired(self, tmp_path):
        state = {"repo_root": str(tmp_path), "generated_test_files": {str(tmp_path / self.FILE): "x"}}
        regressions = ["tests/unit/test_lint.py::test_ruff_reports_nothing"]
        summary = f"{self.FILE}:3:1: F811 Redefinition\n"
        assert _late_files_to_repair(state, regressions, summary) == [self.FILE]


def test_the_graph_runs_the_final_suite_before_the_landing():
    from assemblyzero.workflows.testing.graph import build_testing_workflow

    graph = build_testing_workflow().compile().get_graph()
    edges = {(e.source, e.target) for e in graph.edges}
    assert ("N8_document", "N8_5_final_suite") in edges
    assert ("N8_5_final_suite", "N9_cleanup") in edges
    assert ("N8_document", "N9_cleanup") not in edges
