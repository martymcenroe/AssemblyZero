"""The structured-output contract, end to end (#1843).

Two independent defects made every "structured" Gemini call parse as regex:

- the payload was read from a phantom ``.content`` field (fixed in #1871), and
- ``response_schema`` was accepted by GeminiClient.invoke() and then dropped —
  the agy CLI transport has no structured-output flag, so nothing ever told
  the model to emit JSON. The prompt asked for a markdown review template,
  markdown came back, json.loads failed at char 0, and the "fallback" was the
  only parser that ever ran.

These tests pin the repaired contract: the schema reaches the model as an
instruction, and the parsers accept the shapes a model actually returns.
"""

import json

from assemblyzero.core.gemini_client import _append_json_schema_directive
from assemblyzero.core.verdict_schema import (
    REVIEW_SPEC_SCHEMA,
    _loads_lenient,
    parse_structured_review_spec,
)


class TestSchemaReachesTheModel:
    """#1843: a transport that cannot carry a schema must say it in words."""

    def test_directive_names_json_and_forbids_prose(self):
        out = _append_json_schema_directive("You are a reviewer.", {"type": "object"})
        assert "You are a reviewer." in out
        assert "JSON" in out
        assert "no code fences" in out.lower() or "no code fences" in out

    def test_directive_embeds_the_schema_itself(self):
        schema = {"type": "object", "properties": {"verdict": {"type": "string"}}}
        out = _append_json_schema_directive("sys", schema)
        assert "verdict" in out
        # the schema is embedded as readable JSON, not repr()
        assert '"type": "object"' in out

    def test_directive_is_appended_not_substituted(self):
        original = "Original instructions that must survive."
        out = _append_json_schema_directive(original, REVIEW_SPEC_SCHEMA)
        assert out.startswith(original)


class TestLenientJsonRecovery:
    """#1843: accept the shapes models actually emit, not just the ideal one."""

    PAYLOAD = {"verdict": "APPROVED", "rationale": "ok", "feedback_items": []}

    def test_bare_json(self):
        assert _loads_lenient(json.dumps(self.PAYLOAD))["verdict"] == "APPROVED"

    def test_fenced_json(self):
        raw = f"```json\n{json.dumps(self.PAYLOAD)}\n```"
        assert _loads_lenient(raw)["verdict"] == "APPROVED"

    def test_unlabelled_fence(self):
        raw = f"```\n{json.dumps(self.PAYLOAD)}\n```"
        assert _loads_lenient(raw)["verdict"] == "APPROVED"

    def test_prose_wrapped_json(self):
        raw = f"Here is my review:\n{json.dumps(self.PAYLOAD)}\nHope that helps."
        assert _loads_lenient(raw)["verdict"] == "APPROVED"

    def test_pure_markdown_still_raises(self):
        """A markdown review has no JSON to recover — the caller's regex
        fallback must still get its turn."""
        try:
            _loads_lenient("## Verdict\n[x] **APPROVED**\n")
        except json.JSONDecodeError:
            pass
        else:  # pragma: no cover - failure path
            raise AssertionError("expected JSONDecodeError for markdown input")

    def test_empty_raises(self):
        try:
            _loads_lenient("")
        except json.JSONDecodeError:
            pass
        else:  # pragma: no cover - failure path
            raise AssertionError("expected JSONDecodeError for empty input")


class TestParsersUseLenientRecovery:
    """The recovery is wired into the parsers, not just available to them."""

    def test_fenced_review_spec_parses_as_structured(self):
        payload = {
            "verdict": "APPROVED",
            "rationale": "Spec is complete",
            "feedback_items": [],
        }
        result = parse_structured_review_spec(f"```json\n{json.dumps(payload)}\n```")
        assert result["source"] == "structured"
        assert result["verdict"] == "APPROVED"

    def test_markdown_review_spec_still_falls_back(self):
        result = parse_structured_review_spec("## Verdict\n[x] **APPROVED**\n")
        assert result["source"] == "regex_fallback"
