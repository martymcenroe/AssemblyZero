"""validate_tests_mechanical.py under standard 0034, one test per sweep site.

N2.5 judges the scaffold before the red phase. Three of its failures were
quiet: a neighbouring helper file it could not read or parse was dropped
without a word, a suite made wholly of placeholders was named only on
stdout, and the legacy routing fallback ended an exhausted run at ``end``
with no error, where nothing halts and nothing alerts. The parse handlers
that answer "nothing here" for text another check already reports stay, and
are pinned. Line numbers in the names are ledger 0908's, at its base
``79e18ad1``.
"""
from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.graph import route_after_validate
from assemblyzero.workflows.testing.nodes import validate_tests_mechanical as vtm

VALID_SUITE = "import pytest\n\n\ndef test_x():\n    assert 1 == 1\n"
INVALID_SUITE = "def test_x():\n    pass\n"
UNPARSEABLE = "import pytest\n\ndef test_broken(:\n    assert 1\n"
HOLLOW = (
    "import pytest\n\n\n"
    "def test_alpha():\n    assert False, \"TDD RED: alpha\"\n\n\n"
    "def test_beta():\n    assert False, \"TDD RED: beta\"\n"
)
USES_HELPER = "from helpers import check\n\n\ndef test_it():\n    check(1)\n"


def _state(**overrides) -> dict:
    state = {
        "generated_tests": VALID_SUITE,
        "parsed_scenarios": {"scenarios": []},
        "scaffold_attempts": 0,
        "issue_number": 4242,
    }
    state.update(overrides)
    return state


# --- line 101: count_stub_tests on text that does not parse (kept) ----------


def test_101_an_unparseable_suite_counts_no_stubs_and_the_node_lists_the_syntax_error():
    """Kept: (0, 0, []) is the count's answer for text with no functions it
    can read; the node reports the syntax error itself, in the same pass."""
    assert vtm.count_stub_tests(UNPARSEABLE) == (0, 0, [])

    result = vtm.validate_tests_mechanical_node(_state(generated_tests=UNPARSEABLE))

    assert result["validation_result"]["is_valid"] is False
    assert any(
        e.startswith("Syntax error in generated tests")
        for e in result["validation_result"]["errors"]
    )


# --- line 418: the generated tests do not parse (kept) -----------------------


def test_418_a_syntax_error_is_a_validation_error():
    errors = vtm.validate_test_structure(UNPARSEABLE, [])
    assert len(errors) == 1
    assert errors[0].startswith("Syntax error in generated tests")


# --- line 499: imported_helper_sources on text that does not parse (kept) ----


def test_499_unparseable_test_text_has_no_helpers(tmp_path):
    """Kept: the caller parses the same text and reports its syntax error."""
    (tmp_path / "helpers.py").write_text("def check(v):\n    assert v\n", encoding="utf-8")
    assert vtm.imported_helper_sources(UNPARSEABLE, tmp_path) == {}


# --- lines 500 and 523: the withdrawn fail-open tags --------------------------


def _helper_source_halves() -> tuple[str, str]:
    source = inspect.getsource(vtm.imported_helper_sources)
    head, _, tail = source.partition("for local_name, module_head in wanted.items()")
    return head, tail


def test_500_the_text_parse_handler_carries_no_fail_open_tag():
    head, _ = _helper_source_halves()
    assert "fail-open:" not in head


def test_523_the_neighbour_parse_handler_carries_no_fail_open_tag():
    _, tail = _helper_source_halves()
    assert tail, "the neighbour loop moved; this test reads its source"
    assert "fail-open:" not in tail


# --- line 522: a neighbouring helper cannot be read or parsed ----------------


def test_522_an_unparseable_neighbour_raises_naming_the_file(tmp_path):
    helper = tmp_path / "helpers.py"
    helper.write_text("def check(:\n", encoding="utf-8")

    with pytest.raises(vtm.HelperSourceUnreadable) as raised:
        vtm.imported_helper_sources(USES_HELPER, tmp_path)

    assert raised.value.path == helper
    assert "SyntaxError" in raised.value.cause
    assert str(helper) in str(raised.value)


def test_522_an_unreadable_neighbour_raises_naming_the_file(tmp_path, monkeypatch):
    helper = tmp_path / "helpers.py"
    helper.write_text("def check(v):\n    assert v\n", encoding="utf-8")
    real_read_text = Path.read_text

    def refuse(self, *args, **kwargs):
        if self == helper:
            raise PermissionError(13, "Permission denied", str(self))
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", refuse)

    with pytest.raises(vtm.HelperSourceUnreadable) as raised:
        vtm.imported_helper_sources(USES_HELPER, tmp_path)

    assert raised.value.path == helper
    assert "PermissionError" in raised.value.cause


def test_522_the_node_halts_naming_the_unreadable_neighbour(tmp_path, capsys):
    """The assertion check cannot follow into the file, so it cannot run:
    the node halts through HALT, which alerts, as an unreadable test file
    does (#3081)."""
    helper = tmp_path / "helpers.py"
    helper.write_text("def check(:\n", encoding="utf-8")
    state = _state(
        generated_tests=USES_HELPER, test_files=[str(tmp_path / "test_it.py")],
    )

    result = vtm.validate_tests_mechanical_node(state)

    assert result["validation_result"]["is_valid"] is False
    message = result["error_message"]
    assert str(helper) in message and "SyntaxError" in message
    assert "#4242" in message
    assert route_after_validate({**state, **result}) == "HALT"
    err = capsys.readouterr().err
    assert "ERROR [N2.5]" in err
    assert str(helper) in err


def test_a_neighbour_that_is_not_there_is_not_a_failure(tmp_path):
    """Kept: a name imported from a module with no file beside the test (an
    installed package, the code under test) is not a helper to follow."""
    source = "from nowhere import thing\n\n\ndef test_it():\n    thing()\n"
    assert vtm.imported_helper_sources(source, tmp_path) == {}


# --- line 557: validate_scenario_coverage on text that does not parse (kept) -


def test_557_coverage_of_unparseable_text_adds_nothing_and_the_syntax_error_stands():
    scenarios = [{"test_id": "T1", "test_name": "test_x"}]
    assert vtm.validate_scenario_coverage(UNPARSEABLE, scenarios) == []

    result = vtm.validate_tests_mechanical_node(
        _state(generated_tests=UNPARSEABLE, parsed_scenarios={"scenarios": scenarios})
    )
    errors = result["validation_result"]["errors"]
    assert [e for e in errors if e.startswith("Syntax error")], errors
    assert not [e for e in errors if e.startswith("Missing test function")]


# --- line 676: every test fails unconditionally and the spec has no bodies ---


def test_676_a_hollow_suite_without_spec_bodies_is_an_error_on_stderr_and_alerts(
    capsys, operator_alerts,
):
    result = vtm.validate_tests_mechanical_node(_state(generated_tests=HOLLOW))

    # Kept (#386): the suite is not bounced, because regenerating cannot
    # improve on it; the red phase judges it.
    assert result["validation_result"]["is_valid"] is True
    assert result["scaffold_route"] == "continue"

    err = capsys.readouterr().err
    assert "ERROR [N2.5]" in err
    assert "#4242" in err
    assert "test_alpha" in err and "test_beta" in err

    assert len(operator_alerts) == 1
    alert = operator_alerts[0]
    assert alert["issue"] == 4242
    assert "test_alpha" in alert["cause"]
    assert "validate_tests_mechanical" in alert["where"]


def test_676_a_hollow_suite_rejected_for_other_errors_is_named_without_its_own_alert(
    capsys, operator_alerts,
):
    """The rejection routes back to the scaffolder, and out of attempts to
    HALT, which alerts; this node names the placeholders but does not alert
    a second time."""
    result = vtm.validate_tests_mechanical_node(_state(generated_tests=INVALID_SUITE))

    assert result["validation_result"]["is_valid"] is False
    assert result["scaffold_route"] == "regenerate"
    err = capsys.readouterr().err
    assert "ERROR [N2.5] [HOLLOW SCAFFOLD]" in err
    assert "test_x" in err
    assert operator_alerts == []


# --- lines 963 and 975: the scaffold budget is spent (kept) ------------------


def test_963_a_spent_budget_on_a_valid_suite_halts():
    state = _state(scaffold_attempts=vtm.MAX_SCAFFOLD_ATTEMPTS)
    result = vtm.validate_tests_mechanical_node(state)

    assert result["validation_result"]["is_valid"] is True
    assert vtm.DETERMINISTIC_FAILURE in result["error_message"]
    assert route_after_validate({**state, **result}) == "HALT"


def test_975_an_invalid_suite_out_of_regenerations_halts():
    state = _state(
        generated_tests=INVALID_SUITE,
        scaffold_attempts=vtm.MAX_SCAFFOLD_ATTEMPTS - 1,
    )
    result = vtm.validate_tests_mechanical_node(state)

    assert result["validation_result"]["is_valid"] is False
    assert vtm.DETERMINISTIC_FAILURE in result["error_message"]
    assert route_after_validate({**state, **result}) == "HALT"


# --- line 1043: the legacy fallback out of moves -----------------------------


def test_1043_a_legacy_state_out_of_attempts_raises_instead_of_ending(capsys):
    state = {
        "validation_result": {"is_valid": False},
        "scaffold_attempts": vtm.MAX_SCAFFOLD_ATTEMPTS,
    }

    with pytest.raises(vtm.ScaffoldExhausted) as raised:
        vtm.should_regenerate(state)
    assert vtm.DETERMINISTIC_FAILURE in str(raised.value)
    assert "limit of" in str(raised.value)
    assert "ERROR [N2.5]" in capsys.readouterr().err

    with pytest.raises(vtm.ScaffoldExhausted):
        route_after_validate(state)


def test_1043_a_legacy_byte_identical_state_raises_instead_of_ending():
    state = {
        "validation_result": {"is_valid": False},
        "scaffold_attempts": 1,
        "generated_tests": INVALID_SUITE,
        "previous_scaffold_hash": hashlib.sha256(INVALID_SUITE.encode()).hexdigest(),
    }
    with pytest.raises(vtm.ScaffoldExhausted) as raised:
        vtm.should_regenerate(state)
    assert "byte for byte" in str(raised.value)


def test_1043_a_carried_escalate_with_no_recorded_reason_raises():
    """The node always names the halt with its escalate; a state that carries
    the route without the reason would end the run as if nothing failed."""
    with pytest.raises(vtm.ScaffoldExhausted):
        vtm.should_regenerate({"scaffold_route": "escalate"})


def test_a_carried_escalate_with_its_reason_still_routes_to_halt():
    """Kept: the node's own escalate carries error_message, which HALT reads."""
    state = _state(
        generated_tests=INVALID_SUITE,
        scaffold_attempts=vtm.MAX_SCAFFOLD_ATTEMPTS - 1,
    )
    merged = {**state, **vtm.validate_tests_mechanical_node(state)}
    assert vtm.should_regenerate(merged) == "escalate"
    assert route_after_validate(merged) == "HALT"
