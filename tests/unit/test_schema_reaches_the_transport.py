"""#4483: inside a run, a gate's schema reaches the model.

Inside a run `get_provider` wraps the transport in `RecordingProvider`. Five
gates chose their schema argument with `isinstance(provider, GeminiProvider)`,
which the wrapper fails, so they passed `json_schema`, and `GeminiProvider.invoke`
dropped it. agy has no structured-output flag, so `GeminiClient.invoke` writes the
schema into the prompt, and that is the only way a Gemini model ever sees one. It
never ran. Two real LLD runs halted at the requirements gate on six valid JSON
answers in keys the model had invented, and `calls.jsonl` said `has_schema: true`
for every one.

So these tests stand where a real run stands: recording armed the way a run arms
it, every gate going through the wrapped provider, and the assertion made on the
system instruction at the last step before agy.
"""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from assemblyzero.core import call_recording as cr
from assemblyzero.core.call_recording import (
    RecordingProvider,
    ReplayProvider,
    SchemaNotDelivered,
)
from assemblyzero.core.gemini_client import GeminiClient
from assemblyzero.core.llm_provider import (
    ClaudeCLIProvider,
    GeminiProvider,
    LLMCallResult,
    LLMProvider,
    MockProvider,
    get_provider,
)
from assemblyzero.core.scripted_provider import ScriptedProvider

ar = importlib.import_module("assemblyzero.workflows.requirements.nodes.analyze_requirements")

REPO = Path(__file__).resolve().parents[2]
DIRECTIVE = "## Response Format (MANDATORY)"
SCHEMA = {"type": "object", "properties": {"shape_marker": {"type": "string"}}}
SPEC = "gemini:3.1-pro"


@pytest.fixture
def run(monkeypatch, tmp_path):
    """Recording armed as a run arms it, with agy replaced by a capture."""
    seen = {"system": [], "answer": "{}", "audit_dir": tmp_path}

    def capture(self, system_instruction, content, timeout_seconds=0):
        seen["system"].append(system_instruction)
        return True, seen["answer"], ""

    monkeypatch.setattr(GeminiClient, "_find_agy_cli", lambda self: "agy")
    monkeypatch.setattr(GeminiClient, "_invoke_via_cli", capture)
    cr.reset_context()
    cr.set_context("lld", "a-node", str(tmp_path))
    yield seen
    cr.reset_context()


def _recorded(audit_dir: Path) -> list[dict]:
    calls, _ = cr.read_calls(audit_dir)
    return calls


class TestTheTransportGetsTheSchema:
    def test_inside_a_run_the_provider_is_the_wrapper(self, run):
        # Why isinstance could not work, and why every test here stands here.
        provider = get_provider(SPEC)
        assert isinstance(provider, RecordingProvider)
        assert not isinstance(provider, GeminiProvider)

    @pytest.mark.parametrize("argument", ["json_schema", "response_schema"])
    def test_t1_either_name_reaches_the_system_instruction(self, run, argument):
        get_provider(SPEC).invoke("SYSTEM", "CONTENT", **{argument: SCHEMA})

        assert DIRECTIVE in run["system"][0]
        assert "shape_marker" in run["system"][0]

    def test_t1_with_no_schema_nothing_is_added(self, run):
        get_provider(SPEC).invoke("SYSTEM", "CONTENT")

        assert run["system"] == ["SYSTEM"]

    def test_t1_json_schema_wins_as_it_does_on_claude(self, run):
        get_provider(SPEC).invoke(
            "SYSTEM", "CONTENT",
            json_schema=SCHEMA,
            response_schema={"properties": {"the_other_one": {}}},
        )

        assert "shape_marker" in run["system"][0]
        assert "the_other_one" not in run["system"][0]


class TestEveryGate:
    """T2: each gate's own call path, on the provider a run hands it."""

    def test_requirements_consistency(self, run, monkeypatch):
        run["answer"] = json.dumps({"is_consistent": True, "conflicts": []})
        provider = get_provider(SPEC)
        monkeypatch.setattr(
            "assemblyzero.core.llm_provider.get_provider", lambda spec, *a, **k: provider,
        )

        out = ar.analyze_requirements({
            "issue_title": "t", "issue_body": "a requirement",
            "issue_number": 1, "target_repo": str(run["audit_dir"]),
        })

        assert out == {}
        assert DIRECTIVE in run["system"][0]
        assert "is_consistent" in run["system"][0]

    def test_requirements_review(self, run):
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )

        run["answer"] = json.dumps({
            "verdict": "APPROVED", "rationale": "ok", "feedback_items": [],
            "open_questions": [], "resolved_issues": [],
        })

        _invoke_reviewer_with_feedback_schema(get_provider(SPEC), "prompt", "system")

        assert DIRECTIVE in run["system"][0]

    def test_spec_review(self, run):
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        run["answer"] = json.dumps({
            "verdict": "APPROVED", "rationale": "ok", "feedback_items": [],
        })

        _invoke_reviewer_with_spec_schema(get_provider(SPEC), "prompt", "system")

        assert DIRECTIVE in run["system"][0]

    def test_contract_fidelity(self, run):
        from assemblyzero.workflows.requirements.contract_fidelity import (
            review_fidelity,
        )

        run["answer"] = json.dumps({"findings": []})
        brief = SimpleNamespace(
            ready=True, error="", contract_path="c.md", as_prompt=lambda: "the brief",
        )

        review = review_fidelity(brief, drafter_spec=SPEC)

        assert review.reached
        assert DIRECTIVE in run["system"][0]

    def test_test_plan_review(self, run, tmp_path):
        from assemblyzero.workflows.testing.nodes import review_test_plan as node

        module = importlib.import_module(
            "assemblyzero.workflows.testing.nodes.review_test_plan"
        )
        run["answer"] = json.dumps({"verdict": "APPROVED", "rationale": "ok"})
        state = {
            "test_scenarios": [
                {"name": "test_a", "type": "unit", "requirement_ref": "REQ-1"},
                {"name": "test_b", "type": "unit", "requirement_ref": "REQ-1"},
            ],
            "requirements": ["REQ-1: A", "REQ-2: B"],
            "lld_content": "a detailed low level design document with words " * 20,
            "issue_number": 42,
            "repo_root": str(tmp_path),
            "audit_dir": str(tmp_path),
            "mock_mode": False,
            "node_costs": {},
            "node_tokens": {},
            "file_counter": 0,
            "config_reviewer": SPEC,
        }
        provider = get_provider(SPEC)

        with patch.object(module, "log_workflow_execution"), \
                patch.object(module, "load_review_prompt", return_value="review prompt"), \
                patch.object(module, "get_repo_root", return_value=tmp_path), \
                patch.object(module, "get_cumulative_cost", return_value=0.0), \
                patch.object(module, "get_provider", return_value=provider):
            node(state)

        assert DIRECTIVE in run["system"][0]


class TestOneWayToPassASchema:
    def test_t3_no_code_chooses_by_testing_for_the_gemini_provider(self):
        found = []
        for root in ("assemblyzero", "tools"):
            for path in (REPO / root).rglob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8-sig"))
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "isinstance"
                        and len(node.args) == 2
                        and "GeminiProvider" in ast.dump(node.args[1])
                    ):
                        found.append(f"{path.relative_to(REPO)}:{node.lineno}")

        assert found == [], (
            "a wrapped provider is not a GeminiProvider, so this test is false "
            f"inside every run: {found}"
        )


class _Deaf(LLMProvider):
    """A transport that takes a schema and does nothing with it."""

    def __init__(self) -> None:
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "deaf"

    @property
    def model(self) -> str:
        return "deaf-1"

    def invoke(self, system_prompt, content, timeout_seconds=300,
               response_schema=None, json_schema=None) -> LLMCallResult:
        self.calls += 1
        return LLMCallResult(
            success=True, response="{}", raw_response="{}", error_message=None,
            provider="deaf", model_used="deaf-1", duration_ms=1, attempts=1,
        )


class TestARecordSaysWhatHappened:
    def test_t4_a_delivered_schema_is_recorded_true(self, run):
        get_provider(SPEC).invoke("SYSTEM", "CONTENT", json_schema=SCHEMA)

        assert _recorded(run["audit_dir"])[0]["has_schema"] is True

    def test_t4_no_schema_is_recorded_false(self, run):
        get_provider(SPEC).invoke("SYSTEM", "CONTENT")

        assert _recorded(run["audit_dir"])[0]["has_schema"] is False

    def test_t4_a_schema_a_double_ignored_is_recorded_false(self, tmp_path):
        # The field read true on six calls whose model never saw the schema.
        provider = RecordingProvider(MockProvider(model="review"), audit_dir=str(tmp_path))

        provider.invoke("SYSTEM", "CONTENT", json_schema=SCHEMA)

        assert _recorded(tmp_path)[0]["has_schema"] is False


class TestASchemaThatCannotBeDeliveredStopsTheRun:
    @pytest.mark.parametrize("argument", ["json_schema", "response_schema"])
    def test_t5_it_raises_before_any_call(self, tmp_path, argument):
        inner = _Deaf()
        provider = RecordingProvider(inner, audit_dir=str(tmp_path))

        with pytest.raises(SchemaNotDelivered, match="_Deaf"):
            provider.invoke("SYSTEM", "CONTENT", **{argument: SCHEMA})

        assert inner.calls == 0

    def test_t5_with_no_schema_there_is_nothing_to_refuse(self, tmp_path):
        inner = _Deaf()

        RecordingProvider(inner, audit_dir=str(tmp_path)).invoke("SYSTEM", "CONTENT")

        assert inner.calls == 1

    def test_t5_a_double_with_no_model_is_not_refused(self, tmp_path):
        provider = RecordingProvider(MockProvider(model="review"), audit_dir=str(tmp_path))

        assert provider.invoke("SYSTEM", "CONTENT", json_schema=SCHEMA).success

    def test_every_provider_we_ship_says_which_it_is(self):
        declared = {
            ClaudeCLIProvider: "delivers", GeminiProvider: "delivers",
            MockProvider: "script", ScriptedProvider: "script", ReplayProvider: "script",
        }
        shipped = {
            cls for cls in LLMProvider.__subclasses__()
            if cls.__module__.startswith("assemblyzero.") and cls is not RecordingProvider
        }

        assert shipped == set(declared)
        for cls, kind in declared.items():
            assert cls.delivers_schema is (kind == "delivers"), cls
            assert cls.answers_from_script is (kind == "script"), cls
