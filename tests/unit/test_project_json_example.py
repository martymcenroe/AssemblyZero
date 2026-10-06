"""`.claude/project.json.example` parses and names no retired client or forbidden model (#3703)."""

import json
from pathlib import Path

from assemblyzero.core.config import FORBIDDEN_MODELS

EXAMPLE = Path(__file__).parent.parent.parent / ".claude" / "project.json.example"


def test_example_is_valid_json():
    json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example_names_no_retired_gemini_cli():
    text = EXAMPLE.read_text(encoding="utf-8")
    assert "Gemini CLI" not in text
    assert "gemini-model-check" not in text


def test_example_names_no_forbidden_model():
    text = EXAMPLE.read_text(encoding="utf-8")
    assert [m for m in FORBIDDEN_MODELS if m in text] == []
