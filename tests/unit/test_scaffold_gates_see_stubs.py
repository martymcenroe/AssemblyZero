"""#2317 / #2322: the two gates that let a hollow suite through.

boostgauge #7 scaffolded 36 tests, every one an unconditional `assert False`.
Two gates stood between that and the implementation stage, and both passed it:

  #2317  validate_tests_mechanical printed "Validation PASSED: 36 real tests".
         Issue #386 had exempted the `assert False, 'TDD RED: ...'` pattern
         wholesale to stop a regeneration loop, so the node could no longer
         tell a few placeholders among real tests from a suite that is
         entirely placeholders.
  #2322  the red phase accepted `exit 2 -> ImportError` as a valid red
         signal. Collection died before any body ran, so the stubs were
         invisible to it.

Between them a suite that no implementation could satisfy reached N4, and
two implementation iterations were spent grading against a constant.

The real defective scaffold is the negative fixture, so these tests fail if
either gate regresses to blessing it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    count_stub_tests,
)
from assemblyzero.workflows.testing.nodes.verify_phases import (
    _describe_hollow_suite,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "issue7_run153937"

REAL_SUITE = '''
def test_writes_defaults(tmp_path):
    path = tmp_path / "c.json"
    write_config(path)
    assert path.exists()
'''

MIXED_SUITE = '''
def test_real_one(tmp_path):
    assert compute(2) == 4

def test_placeholder():
    """Not written yet."""
    assert False, 'TDD RED: test_placeholder not implemented'
'''

ALL_STUBS = '''
def test_a():
    assert False, 'TDD RED: test_a not implemented'

def test_b():
    raise NotImplementedError

def test_c():
    """Nothing here."""
'''

# Hollow, but structurally well-formed: imports present and every body holds
# an assert, so it clears the pre-existing structure checks and isolates the
# hollow-suite behaviour under test. This is the shape the real scaffolder
# emits, and the shape that shipped on boostgauge #7.
ALL_STUBS_WELL_FORMED = '''
import pytest

def test_a():
    assert False, 'TDD RED: test_a not implemented'

def test_b():
    assert False, 'TDD RED: test_b not implemented'
'''


# ---------------------------------------------------------------- #2317


def test_the_real_defective_scaffold_is_all_stubs() -> None:
    """The counter sees the actual shipped scaffold for what it was."""
    source = (FIXTURES / "defective_scaffold.py").read_text(encoding="utf-8")
    total, stubs, names = count_stub_tests(source)

    assert total == 36
    assert stubs == 36, "every body was an unconditional failure"
    assert "test_t010" in names


def test_real_tests_are_not_counted_as_stubs() -> None:
    total, stubs, _ = count_stub_tests(REAL_SUITE)
    assert (total, stubs) == (1, 0)


def test_mixed_suite_counts_only_the_placeholder() -> None:
    """#386's case: placeholders among real tests remain acceptable."""
    total, stubs, names = count_stub_tests(MIXED_SUITE)
    assert (total, stubs) == (2, 1)
    assert names == ["test_placeholder"]


def test_empty_and_notimplemented_bodies_are_stubs() -> None:
    total, stubs, _ = count_stub_tests(ALL_STUBS)
    assert (total, stubs) == (3, 3)


def test_a_test_merely_mentioning_a_stub_phrase_is_real() -> None:
    """Why this is decided on the AST and not by regex.

    The line-based STUB_PATTERNS match the words, not the behaviour. A test
    asserting ON that text is a genuine test, and misreading it as a stub is
    the kind of false positive that got detection disabled wholesale.
    """
    source = '''
def test_error_message_wording():
    assert render_error() == "not implemented"
'''
    total, stubs, _ = count_stub_tests(source)
    assert (total, stubs) == (1, 0)


def test_unparseable_source_reports_nothing() -> None:
    """Never invent a finding from input that cannot be read."""
    assert count_stub_tests("def test_broken(:\n") == (0, 0, [])


# ---------------------------------------------------------------- #2322


def test_red_phase_names_the_real_defective_scaffold() -> None:
    """The suite that reached N4 is now named before it."""
    source = (FIXTURES / "defective_scaffold.py").read_text(encoding="utf-8")
    described = _describe_hollow_suite({"generated_tests": source})

    assert described
    assert "36 test(s) fail unconditionally" in described
    assert "no implementation can make this suite green" in described


def test_validator_rejects_a_hollow_suite_when_the_spec_had_bodies() -> None:
    """The boostgauge case: bodies were available and ignored.

    Rejection is gated on being able to help. `should_regenerate` escalates
    a deterministic scaffolder on its hash check, and escalate routes to
    N4_implement_code -- so failing a suite that regeneration cannot improve
    reaches implementation anyway, minus the red phase. Since #2316 the
    fixable case is exactly this one.
    """
    from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
        validate_tests_mechanical_node,
    )

    state = {
        "generated_tests": ALL_STUBS_WELL_FORMED,
        "parsed_scenarios": {"scenarios": []},
        "scaffold_attempts": 0,
        "spec_test_suite": {
            "imports": "",
            "functions": [{"name": "test_a", "source": "def test_a():\n    assert 1"}],
        },
    }
    result = validate_tests_mechanical_node(state)
    validation = result["validation_result"]

    assert validation["is_valid"] is False
    assert validation["stub_count"] == 2
    assert validation["real_test_count"] == 0
    assert any("executable Section 10" in e for e in validation["errors"])


def test_validator_reports_but_allows_a_hollow_suite_with_no_spec_bodies(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Where rejection cannot help, the suite is named rather than bounced.

    This is also what preserves #386: a stub-only scaffold from a spec that
    ships no test code is still accepted, so the regeneration loop that
    issue closed does not reopen.
    """
    from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
        validate_tests_mechanical_node,
    )

    state = {
        "generated_tests": ALL_STUBS_WELL_FORMED,
        "parsed_scenarios": {"scenarios": []},
        "scaffold_attempts": 0,
    }
    result = validate_tests_mechanical_node(state)
    validation = result["validation_result"]

    assert validation["is_valid"] is True, "must not reopen the #386 loop"
    assert validation["stub_count"] == 2
    assert validation["real_test_count"] == 0, (
        "the count must stop calling placeholders real tests"
    )
    assert "[HOLLOW SCAFFOLD]" in capsys.readouterr().out


def test_red_phase_passes_a_legitimate_suite() -> None:
    """A real red phase -- real tests, module absent -- still proceeds."""
    assert _describe_hollow_suite({"generated_tests": REAL_SUITE}) == ""


def test_red_phase_passes_a_mixed_suite() -> None:
    """Placeholders alongside real tests are not a hollow suite."""
    assert _describe_hollow_suite({"generated_tests": MIXED_SUITE}) == ""


def test_red_phase_reads_test_files_when_state_lacks_source(
    tmp_path: Path,
) -> None:
    """Resumed runs carry the files but not always the generated source."""
    path = tmp_path / "test_scaffolded.py"
    path.write_text(ALL_STUBS, encoding="utf-8")

    described = _describe_hollow_suite({"test_files": [str(path)]})
    assert "3 test(s) fail unconditionally" in described


@pytest.mark.parametrize("state", [
    {},
    {"generated_tests": ""},
    {"generated_tests": "   \n"},
    {"test_files": ["/nonexistent/path/test_x.py"]},
    {"generated_tests": "def test_broken(:\n"},
])
def test_red_phase_never_invents_a_failure(state: dict) -> None:
    """Unreadable input is not evidence of a hollow suite."""
    assert _describe_hollow_suite(state) == ""
