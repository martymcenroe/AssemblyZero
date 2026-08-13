"""#2316: the scaffolder must emit the spec's executable test bodies.

The incident (boostgauge #7, `run-issue7-153937`): the spec shipped 23
complete pytest functions with 28 real assertions. Nothing read them.
Scenarios were parsed from the LLD's Section 10 tables instead, and the
scaffolder emitted one `assert False, 'TDD RED: ...'` stub per row -- 36 of
them, every one an unconditional failure. No implementation could pass that
suite, so two TDD iterations graded against a constant and the run halted
with the implementation already correct.

The fixtures here are the REAL artifacts from that run, preserved on
boostgauge's `graveyard/7-lld-run153937` and `graveyard/issue-7-run153937`:

    fixtures/spec-0007.md          the 862-line spec, §10.1 carries the 23
    fixtures/LLD-007.md            the 418-line LLD, two Section 10 tables
    fixtures/defective_scaffold.py what the scaffolder actually emitted

Using the real artifacts matters: a hand-written miniature would not have
reproduced the 36 (12 summary rows + 23 detail rows + 1 leaked header),
which is the number that made the failure legible.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.nodes.load_lld import (
    extract_spec_test_functions,
    extract_test_plan_section,
    parse_test_scenarios,
    scenarios_from_spec_functions,
)
from assemblyzero.workflows.testing.nodes.scaffold_tests import (
    generate_spec_test_file_content,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "issue7_run153937"


@pytest.fixture(scope="module")
def spec() -> str:
    return (FIXTURES / "spec-0007.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def lld() -> str:
    return (FIXTURES / "LLD-007.md").read_text(encoding="utf-8")


def _test_function_names(source: str) -> list[str]:
    tree = ast.parse(source)
    return [
        n.name for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    ]


def test_the_defective_scaffold_is_the_thing_we_are_fixing() -> None:
    """Characterise the bug, so the fixture cannot silently stop showing it."""
    source = (FIXTURES / "defective_scaffold.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    names = _test_function_names(source)
    assert len(names) == 36

    # Every single body is an unconditional failure.
    unconditional = 0
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Assert) and isinstance(stmt.test, ast.Constant):
                if stmt.test.value is False:
                    unconditional += 1
    assert unconditional == 36, "the whole suite was assert-False stubs"

    # And a table header leaked in as a test (#2318).
    assert "test_id" in names


def test_spec_functions_are_extracted_with_bodies(spec: str) -> None:
    """The 23 executable functions are found, with real assertions."""
    suite = extract_spec_test_functions(spec)

    assert len(suite["functions"]) == 23
    names = [f["name"] for f in suite["functions"]]
    assert names[0] == "test_req_1"
    assert names[-1] == "test_req_22"

    joined = "\n".join(f["source"] for f in suite["functions"])
    assert "assert False" not in joined, "spec functions are not stubs"
    assert joined.count("assert ") >= 28

    # The shared import block travels with them.
    assert "from boostgauge.config import" in suite["imports"]


def test_scaffold_emits_23_not_36(spec: str, lld: str) -> None:
    """The relaunch gate: the emitted suite is the spec's, not the tables'."""
    # What the table path yields, for contrast -- this is the 36 that shipped.
    table_scenarios = parse_test_scenarios(extract_test_plan_section(lld))
    assert len(table_scenarios) == 36

    suite = extract_spec_test_functions(spec)
    content = generate_spec_test_file_content(
        suite, issue_number=7,
        files_to_modify=[{"path": "src/boostgauge/config.py"}],
    )

    names = _test_function_names(content)
    assert len(names) == 23, f"expected the spec's 23, got {len(names)}"
    assert "test_id" not in names, "no table header may become a test"
    assert not any(n.startswith("test_t") for n in names), (
        "summary-table rows must not become tests alongside the functions"
    )


def test_emitted_suite_has_no_unconditional_failures(spec: str) -> None:
    """The property that makes the TDD loop able to converge at all."""
    suite = extract_spec_test_functions(spec)
    content = generate_spec_test_file_content(suite, issue_number=7)

    assert "TDD RED:" not in content
    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert) and isinstance(node.test, ast.Constant):
            assert node.test.value is not False, (
                "an unconditional assert False makes the suite unpassable"
            )


def test_emitted_suite_is_valid_python_and_bodies_are_verbatim(spec: str) -> None:
    """Transcription, not generation -- each body survives byte for byte."""
    suite = extract_spec_test_functions(spec)
    content = generate_spec_test_file_content(suite, issue_number=7)

    ast.parse(content)  # raises if the emitted file is not importable Python
    for fn in suite["functions"]:
        assert fn["source"] in content, f"{fn['name']} was altered in emission"


def test_scenarios_derived_from_functions_match_them(spec: str) -> None:
    """Scenario metadata cannot drift from the bodies -- both come from one source."""
    suite = extract_spec_test_functions(spec)
    scenarios = scenarios_from_spec_functions(suite["functions"])

    assert [s["name"] for s in scenarios] == [
        f["name"] for f in suite["functions"]
    ]
    assert all(s["description"] for s in scenarios), (
        "every scenario should carry the spec's own description"
    )


def test_spec_without_executable_functions_falls_back(lld: str) -> None:
    """A spec carrying only tables keeps the generated-stub path.

    The LLD has Section 10 tables and no executable functions, so it stands
    in for that shape. The fallback is why this is a preference, not a
    replacement -- removing it would break every spec that ships no code.
    """
    suite = extract_spec_test_functions(lld)

    assert suite["functions"] == []
    assert suite["imports"] == ""


def test_no_section_10_returns_empty() -> None:
    """Malformed input yields the fallback signal, never an exception."""
    assert extract_spec_test_functions("# Nothing here")["functions"] == []
    assert extract_spec_test_functions("")["functions"] == []
