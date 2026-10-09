"""A review that cannot run is a failure, never "skipped" (#3725, ADR 0236).

Also the #3581 sweep sites in the same review code: #3817 (adversarial_node),
#3808 (adversarial_gemini), #3818 (adversarial_validator) and #3819
(adversarial_writer). Each failure is loud (ERROR on stderr), carries its
details, stops the run (error_message, routed to HALT) and alerts (the HALT
node, #3724).
"""

from __future__ import annotations

import ast
import importlib
import inspect
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core.llm_provider import LLMProvider
from assemblyzero.workflows.testing import adversarial_gemini as ag
from assemblyzero.workflows.testing.graph import route_after_adversarial

# Imported by module path: a nodes package may re-export a node function
# under its module's name.
an = importlib.import_module("assemblyzero.workflows.testing.nodes.adversarial_node")
av = importlib.import_module("assemblyzero.workflows.testing.nodes.adversarial_validator")
aw = importlib.import_module("assemblyzero.workflows.testing.nodes.adversarial_writer")

CLIENT = "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
WRITE = "assemblyzero.workflows.testing.nodes.adversarial_node.write_adversarial_tests"
VALIDATE = "assemblyzero.workflows.testing.nodes.adversarial_node.validate_adversarial_tests"
SPEC = "gemini:3.1-pro"  # the default profile's impl.adversarial seat

GOOD_JSON = (
    '{"uncovered_edge_cases": [], "false_claims": [], "missing_error_handling": [], '
    '"implicit_assumptions": [], "test_cases": [{"test_id": "ADV_001", '
    '"target_function": "m.f", "category": "boundary", "description": "d", '
    '"test_code": "def test_x():\\n    assert True", "claim_challenged": "c", '
    '"severity": "high"}]}'
)


@pytest.fixture
def state(tmp_path):
    impl = tmp_path / "module.py"
    impl.write_text("def f(x):\n    return x\n", encoding="utf-8")
    return {
        "implementation_files": [str(impl)],
        "lld_content": "# LLD",
        "test_files": [],
        "issue_id": 3725,
        "repo_root": str(tmp_path),
    }


def _assert_halts(result, *, what, exc_type, exc_text, capsys, spec=SPEC):
    """The result routes to HALT and names the seat, spec, type and message."""
    assert route_after_adversarial(result) == "HALT"
    message = result["error_message"]
    assert what in message
    assert "impl.adversarial" in message
    assert spec in message
    assert exc_type in message
    assert exc_text in message
    assert result["adversarial_verdict"] == "error"
    assert result["adversarial_verdict"] != "skipped"
    assert "ERROR [ADV]" in capsys.readouterr().err


# ---- #3725 requirement 1-2: one test per caught exception type ----


CALL_FAILURES = [
    (ag.GeminiQuotaExhaustedError("429 quota"), "quota is exhausted", "RateLimitError", "429 quota"),
    (ag.ForbiddenModelError("alias resolves to a flash tier"), "not permitted", "ForbiddenModelError", "flash tier"),
    (ag.GeminiModelDowngradeError("received gemini-2.0-flash"), "Gemini Pro model", "GeminiModelDowngradeError", "gemini-2.0-flash"),
    (ag.GeminiTimeoutError("exceeded 120s timeout"), "Gemini call failed", "TimeoutError_", "exceeded 120s"),
    (ag.GeminiEmptyResponseError("empty response"), "empty response", "GeminiEmptyResponseError", "empty response"),
]


@pytest.mark.parametrize("exc, what, exc_type, exc_text", CALL_FAILURES,
                         ids=[c[2] for c in CALL_FAILURES])
def test_a_failed_call_halts_with_its_details(exc, what, exc_type, exc_text, state, capsys):
    with patch(CLIENT) as client_cls:
        client_cls.return_value.generate_adversarial_tests.side_effect = exc
        result = an.run_adversarial_node(state)
    _assert_halts(result, what=what, exc_type=exc_type, exc_text=exc_text, capsys=capsys)


CLIENT_FAILURES = [
    (ValueError("Unknown provider 'gemini'"), "ValueError", "Unknown provider"),
    (ag.ForbiddenModelError("alias '3.1-flash' is forbidden"), "ForbiddenModelError", "forbidden"),
]


@pytest.mark.parametrize("exc, exc_type, exc_text", CLIENT_FAILURES,
                         ids=[c[1] for c in CLIENT_FAILURES])
def test_a_client_that_cannot_be_built_halts(exc, exc_type, exc_text, state, capsys):
    with patch(CLIENT, side_effect=exc):
        result = an.run_adversarial_node(state)
    _assert_halts(result, what="could not be built", exc_type=exc_type,
                  exc_text=exc_text, capsys=capsys)


# ---- #3725: no non-mock path returns "skipped" ----


def test_only_the_mock_branch_calls_skipped():
    """_skipped is called exactly once, inside the mock_mode branch."""
    tree = ast.parse(inspect.getsource(an.run_adversarial_node))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_skipped"
    ]
    assert len(calls) == 1
    mock_branch = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.If) and "mock_mode" in ast.unparse(node.test)
    )
    assert any(node is calls[0] for node in ast.walk(mock_branch))


@pytest.mark.parametrize("exc", [c[0] for c in CALL_FAILURES], ids=[c[2] for c in CALL_FAILURES])
def test_no_failure_path_returns_skipped(exc, state):
    with patch(CLIENT) as client_cls:
        client_cls.return_value.generate_adversarial_tests.side_effect = exc
        assert an.run_adversarial_node(state)["adversarial_verdict"] != "skipped"


def test_the_mock_run_still_skips(state):
    result = an.run_adversarial_node({**state, "mock_mode": True})
    assert result["adversarial_verdict"] == "skipped"
    assert route_after_adversarial(result) == "N8_document"


# ---- #3725 requirement 3: HALT alerts the operator ----


def test_the_halt_reached_from_n7_5_alerts(state, operator_alerts):
    """Through the graph: N7.5 fails, the router picks HALT, HALT alerts."""
    from langgraph.graph import END, StateGraph

    from assemblyzero.core.halt_node import create_halt_node
    from assemblyzero.workflows.testing.state import TestingWorkflowState

    graph = StateGraph(TestingWorkflowState)
    graph.add_node("N7_5_adversarial", an.run_adversarial_node)
    graph.add_node("HALT", create_halt_node("testing"))
    graph.add_node("N8_document", lambda s: s)
    graph.set_entry_point("N7_5_adversarial")
    graph.add_conditional_edges(
        "N7_5_adversarial", route_after_adversarial,
        {"N8_document": "N8_document", "HALT": "HALT"},
    )
    graph.add_edge("HALT", END)
    graph.add_edge("N8_document", END)

    with patch(CLIENT) as client_cls:
        client_cls.return_value.generate_adversarial_tests.side_effect = (
            ag.GeminiQuotaExhaustedError("429 quota")
        )
        graph.compile().invoke({**state, "issue_number": 3725})

    assert len(operator_alerts) == 1
    assert "quota is exhausted" in operator_alerts[0]["cause"]


# ---- #3817: the rest of adversarial_node ----


def test_no_implementation_files_halts(state, capsys):
    """Decided on #3725: a failure, not a declared contract."""
    result = an.run_adversarial_node({**state, "implementation_files": []})
    assert route_after_adversarial(result) == "HALT"
    assert "no implementation files" in result["error_message"]


def test_an_unreadable_context_file_halts(state, capsys):
    with patch(CLIENT):
        result = an.run_adversarial_node({**state, "test_files": ["/nonexistent/test_x.py"]})
    _assert_halts(result, what="could not be read", exc_type="FileNotFoundError",
                  exc_text="/nonexistent/test_x.py", capsys=capsys)


def test_a_malformed_response_halts(state, capsys):
    with patch(CLIENT) as client_cls:
        client_cls.return_value.generate_adversarial_tests.return_value = "{broken"
        result = an.run_adversarial_node(state)
    _assert_halts(result, what="malformed", exc_type="ValueError", exc_text="Malformed JSON",
                  capsys=capsys)


def test_a_rejected_file_that_cannot_be_removed_is_named(state, tmp_path, capsys):
    bad = str(tmp_path / "test_bad.py")
    with patch(CLIENT) as client_cls, \
         patch(WRITE, return_value={bad: "def test_x():\n    pass\n"}), \
         patch(VALIDATE, return_value={"valid": False, "errors": [f"{bad}: test_x has no assertions"],
                                       "warnings": [], "mock_violations": []}):
        client_cls.return_value.generate_adversarial_tests.return_value = GOOD_JSON
        result = an.run_adversarial_node(state)
    assert route_after_adversarial(result) == "HALT"
    assert "has no assertions" in result["error_message"]
    assert "could not remove" in result["error_message"]
    assert "FileNotFoundError" in result["error_message"]


def test_zero_valid_tests_halts(state, tmp_path):
    f = str(tmp_path / "test_empty.py")
    with patch(CLIENT) as client_cls, \
         patch(WRITE, return_value={f: "# no tests\n"}), \
         patch(VALIDATE, return_value={"valid": True, "errors": [], "warnings": [], "mock_violations": []}):
        client_cls.return_value.generate_adversarial_tests.return_value = GOOD_JSON
        result = an.run_adversarial_node(state)
    assert route_after_adversarial(result) == "HALT"
    assert "zero valid tests" in result["error_message"]


def test_a_write_failure_halts(state):
    with patch(CLIENT) as client_cls, \
         patch(WRITE, side_effect=aw.AdversarialWriteError("disk full")):
        client_cls.return_value.generate_adversarial_tests.return_value = GOOD_JSON
        result = an.run_adversarial_node(state)
    assert route_after_adversarial(result) == "HALT"
    assert "AdversarialWriteError: disk full" in result["error_message"]


# ---- #3808: adversarial_gemini ----


def _llm_provider(response: str, model: str = "gemini-3.1-pro"):
    provider = MagicMock(spec=LLMProvider)
    provider.invoke.return_value = MagicMock(
        success=True, response=response, model_used=model, rate_limited=False,
    )
    return provider


def test_an_empty_success_raises():
    client = ag.AdversarialGeminiClient(provider=_llm_provider(""))
    with pytest.raises(ag.GeminiEmptyResponseError, match="empty response"):
        client.generate_adversarial_tests("code", "lld", "")


def test_an_unknown_model_reply_raises():
    client = ag.AdversarialGeminiClient(provider=_llm_provider("{}", model="gemini-ultra"))
    with pytest.raises(ag.GeminiModelDowngradeError, match="gemini-ultra"):
        client.generate_adversarial_tests("code", "lld", "")


def test_an_unexpected_exception_keeps_its_type(caplog):
    def boom(**_kwargs):
        raise RuntimeError("socket closed")

    client = ag.AdversarialGeminiClient(provider=boom)
    with pytest.raises(ag.GeminiTimeoutError, match="RuntimeError"):
        client.generate_adversarial_tests("code", "lld", "")
    assert any(r.levelname == "ERROR" and "RuntimeError" in r.getMessage() for r in caplog.records)


# ---- #3818: adversarial_validator ----


def test_a_test_without_assertions_is_an_error():
    result = av.validate_adversarial_tests({"t.py": "def test_x():\n    y = 1\n"})
    assert result["valid"] is False
    assert any("no assertions" in e for e in result["errors"])


def test_a_parse_failure_after_compile_is_recorded(monkeypatch, caplog):
    real_parse = av.ast.parse
    calls = {"n": 0}

    def parse(source, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:  # the duplicate check's parse
            raise SyntaxError("unexpected", ("t.py", 1, 1, ""))
        return real_parse(source, *args, **kwargs)

    monkeypatch.setattr(av.ast, "parse", parse)
    result = av.validate_adversarial_tests({"t.py": "def test_x():\n    assert True\n"})
    assert result["valid"] is False
    assert any("compiled but did not parse" in e for e in result["errors"])
    assert any(r.levelname == "ERROR" for r in caplog.records)


# ---- #3819: adversarial_writer ----


ANALYSIS = {
    "uncovered_edge_cases": [], "false_claims": [], "missing_error_handling": [],
    "implicit_assumptions": [],
    "test_cases": [{"test_id": "ADV_001", "category": "boundary",
                    "test_code": "def test_x():\n    assert True"}],
}


def test_no_test_cases_raises(tmp_path):
    with pytest.raises(aw.AdversarialWriteError, match="no test cases"):
        aw.write_adversarial_tests({**ANALYSIS, "test_cases": []}, 3725, str(tmp_path))


def test_a_case_with_no_code_raises(tmp_path):
    cases = [{"test_id": "ADV_009", "category": "boundary", "test_code": "  "}]
    with pytest.raises(aw.AdversarialWriteError, match="ADV_009"):
        aw.write_adversarial_tests({**ANALYSIS, "test_cases": cases}, 3725, str(tmp_path))


def test_a_write_failure_raises_the_halting_error(tmp_path, monkeypatch):
    def refuse(*_args):
        raise PermissionError("read-only")

    monkeypatch.setattr(aw.os, "replace", refuse)
    with pytest.raises(aw.AdversarialWriteError, match="PermissionError: read-only"):
        aw.write_adversarial_tests(ANALYSIS, 3725, str(tmp_path))


def test_a_staging_dir_that_cannot_be_removed_raises(tmp_path, monkeypatch, caplog):
    def refuse(path):
        raise OSError("busy")

    monkeypatch.setattr(aw.shutil, "rmtree", refuse)
    with pytest.raises(aw.AdversarialWriteError, match="could not remove the staging directory"):
        aw.write_adversarial_tests(ANALYSIS, 3725, str(tmp_path))
    assert any(r.levelname == "ERROR" for r in caplog.records)
