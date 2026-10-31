"""scaffold_tests.py under standard 0034, one test per sweep site.

N2 writes the scaffold. Its quiet failures: an LLD with no Section 10 parsed
as no scenarios; a scenario no assertion could be derived from was emitted as
``assert True``, a test that passes against nothing; spec bodies that do not
parse, and a module finder that raised, were repaired as nothing; and a run
whose audit directory was missing wrote no scaffold record and said nothing.
Line numbers in the names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.graph import route_after_scaffold
from assemblyzero.workflows.testing.runner_registry import (
    checkpoint_safe,
    get_framework_config,
)

# The nodes package re-exports the `scaffold_tests` FUNCTION under the
# module's name, so the module is imported by its path.
st = importlib.import_module("assemblyzero.workflows.testing.nodes.scaffold_tests")

SCENARIO = {
    "id": "T010",
    "name": "test_adds",
    "description": "adds two numbers",
    "requirement_ref": "R010",
    "expected_behavior": "returns the sum",
    "test_type": "unit",
    "mock_needed": False,
    "assertions": ["returns the sum"],
}


def _state(tmp_path: Path, **overrides) -> dict:
    audit = tmp_path / "audit"
    audit.mkdir(exist_ok=True)
    state = {
        "issue_number": 7,
        "test_scenarios": [dict(SCENARIO)],
        "files_to_modify": [],
        "repo_root": str(tmp_path),
        "audit_dir": str(audit),
        "file_counter": 1,
    }
    state.update(overrides)
    return state


def _run_generated(code: str, name: str) -> None:
    namespace: dict = {}
    exec(compile(code, "<generated>", "exec"), namespace)  # noqa: S102 - the scaffold's own output
    namespace[name]()


# --- line 105: an LLD with no Section 10 ------------------------------------


def test_105_an_lld_with_no_section_10_raises_naming_the_headings():
    lld = "## 1. Context\n\nNo test plan here.\n\n## 2. Proposed Changes\n"
    with pytest.raises(ValueError) as raised:
        st.parse_lld_test_section(lld)
    message = str(raised.value)
    assert "Section 10" in message
    assert "10.0" in message and "10.1" in message


def test_an_lld_with_section_10_still_parses():
    """Kept: a test plan table is read as it was."""
    lld = (
        "### 10.0 Test Plan\n\n"
        "| Test ID | Test Description | Expected Behavior | Req ID | Status |\n"
        "|---|---|---|---|---|\n"
        "| T010 | test_add | add(1, 2) returns 3 | R010 | RED |\n"
    )
    assert [s["test_id"] for s in st.parse_lld_test_section(lld)["scenarios"]] == ["T010"]


# --- lines 325 and 342: no assertion can be derived ---------------------------


def _code_for(expected: str) -> str:
    return st.generate_test_code({
        "module_path": "",
        "scenarios": [{
            "test_id": "T010", "test_name": "test_derived",
            "description": "T010: derived", "expected_behavior": expected,
            "requirement_id": "",
        }],
        "imports_needed": [],
    })


def test_325_an_arrow_with_no_function_emits_a_failing_assertion():
    code = _code_for('"plain input" -> 5')
    assert "assert True" not in code
    with pytest.raises(AssertionError) as raised:
        _run_generated(code, "test_derived")
    assert "TDD RED" in str(raised.value)


def test_342_a_description_with_no_pattern_emits_a_failing_assertion():
    code = _code_for("the widget behaves itself")
    assert "assert True" not in code
    with pytest.raises(AssertionError) as raised:
        _run_generated(code, "test_derived")
    assert "the widget behaves itself" in str(raised.value)


def test_a_derivable_assertion_is_still_derived():
    """Kept: `f(x) returns y` becomes a real comparison."""
    assert "assert add(2, 3) == 5" in _code_for("add(2, 3) returns 5")


# --- line 435: an unsupported framework (kept) --------------------------------


def test_435_an_unsupported_framework_raises():
    with pytest.raises(ValueError) as raised:
        st.generate_ts_test_file_content([], {"framework": TestFramework.PYTEST}, 7)
    assert "Cannot generate TS content" in str(raised.value)


# --- lines 787 and 788: the spec's test bodies do not parse --------------------


def test_787_unparseable_bodies_raise_naming_the_syntax_error():
    with pytest.raises(st.ScaffoldImportError) as raised:
        st.unbound_names("def test_a(:\n    pass\n", None)
    assert "do not parse" in str(raised.value)
    assert "line 1" in str(raised.value)


def test_787_the_node_halts_on_unparseable_spec_bodies(tmp_path, capsys):
    state = _state(
        tmp_path,
        spec_test_suite={
            "imports": "",
            "functions": [{"name": "test_a", "source": "def test_a(:\n    pass"}],
        },
    )
    result = st.scaffold_tests(state)

    assert "do not parse" in result["error_message"]
    assert route_after_scaffold({**state, **result}) == "HALT"
    assert not (tmp_path / "tests" / "test_issue_7.py").exists(), "nothing is written"
    assert "ERROR [N2]" in capsys.readouterr().err


def _unbound_names_halves() -> tuple[str, str]:
    source = inspect.getsource(st.unbound_names)
    head, _, tail = source.partition("def _is_module")
    return head, tail


def test_788_the_parse_handler_carries_no_fail_open_tag():
    head, _ = _unbound_names_halves()
    assert "fail-open:" not in head


# --- lines 833 and 834: the module finder raises --------------------------------


def test_833_a_finder_error_raises_naming_the_name(monkeypatch):
    real_find_spec = st.importlib.util.find_spec

    def choke(name, *args, **kwargs):
        if name == "zz_unfindable":
            raise ValueError("zz_unfindable.__spec__ is None")
        return real_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(st.importlib.util, "find_spec", choke)

    with pytest.raises(st.ScaffoldImportError) as raised:
        st.unbound_names("def test_a():\n    zz_unfindable()\n", None)
    assert "zz_unfindable" in str(raised.value)
    assert "ValueError" in str(raised.value)


def test_834_the_finder_handler_carries_no_fail_open_tag():
    _, tail = _unbound_names_halves()
    assert tail, "the finder moved; this test reads its source"
    assert "fail-open:" not in tail


def test_an_unknown_name_the_finder_answers_is_a_symbol():
    """Kept: a name with no module spec is the implementation's, by name."""
    found = st.unbound_names("def test_a():\n    zz_no_such_module_here()\n", None)
    assert found == {"modules": [], "symbols": [("zz_no_such_module_here", "test_a")]}


# --- line 1069: the non-Python scaffold's audit directory is missing --------


def _playwright_state(tmp_path: Path, audit_dir: str) -> dict:
    return _state(
        tmp_path,
        framework_config=checkpoint_safe(get_framework_config(TestFramework.PLAYWRIGHT)),
        audit_dir=audit_dir,
    )


def test_1069_a_missing_audit_dir_halts_the_playwright_scaffold(tmp_path, capsys):
    missing = tmp_path / "no-such-audit"
    state = _playwright_state(tmp_path, str(missing))

    result = st.scaffold_tests(state)

    assert str(missing) in result["error_message"]
    assert route_after_scaffold({**state, **result}) == "HALT"
    assert not list(tmp_path.rglob("issue_7.spec.ts")), "nothing is written"
    assert "ERROR [N2]" in capsys.readouterr().err


def test_a_playwright_scaffold_with_its_audit_dir_records_it(tmp_path):
    """Kept: the scaffold and its audit copy are both written."""
    state = _playwright_state(tmp_path, str(tmp_path / "audit"))
    (tmp_path / "audit").mkdir(exist_ok=True)

    result = st.scaffold_tests(state)

    assert not result["error_message"]
    assert list((tmp_path / "audit").glob("*-test-scaffold.spec.ts"))


# --- line 1153: no scenarios (kept) -----------------------------------------


def test_1153_no_scenarios_halts(tmp_path):
    state = _state(tmp_path, test_scenarios=[])
    result = st.scaffold_tests(state)
    assert result["error_message"] == "GUARD: No test scenarios available"
    assert route_after_scaffold({**state, **result}) == "HALT"


# --- line 1199: the pytest scaffold's audit directory is missing ------------


def test_1199_a_missing_audit_dir_halts_the_pytest_scaffold(tmp_path, capsys):
    missing = tmp_path / "no-such-audit"
    state = _state(tmp_path, audit_dir=str(missing))

    result = st.scaffold_tests(state)

    assert str(missing) in result["error_message"]
    assert route_after_scaffold({**state, **result}) == "HALT"
    assert not (tmp_path / "tests" / "test_issue_7.py").exists(), "nothing is written"
    assert "ERROR [N2]" in capsys.readouterr().err


def test_1199_a_state_that_names_no_audit_dir_halts(tmp_path, monkeypatch):
    """An empty audit_dir is Path(""), the working directory, which exists:
    the record went into whatever directory the run was started in."""
    monkeypatch.chdir(tmp_path)
    state = _state(tmp_path, audit_dir="")

    result = st.scaffold_tests(state)

    assert "audit directory" in result["error_message"]
    assert route_after_scaffold({**state, **result}) == "HALT"
    assert not list(tmp_path.glob("*-test-scaffold.py"))


def test_a_pytest_scaffold_with_its_audit_dir_records_it(tmp_path):
    """Kept: the scaffold and its audit copy are both written."""
    state = _state(tmp_path)
    result = st.scaffold_tests(state)

    assert not result["error_message"]
    assert (tmp_path / "tests" / "test_issue_7.py").exists()
    assert list((tmp_path / "audit").glob("*-test-scaffold.py"))
