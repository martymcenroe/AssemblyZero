"""The Gemini review prompt templates name no forbidden model and no deleted wrapper (#3702)."""

from pathlib import Path

import pytest

from assemblyzero.core.config import FORBIDDEN_MODELS

TEMPLATES = Path(__file__).parent.parent.parent / ".claude" / "templates" / "gemini-prompts"
TEMPLATE_FILES = sorted(TEMPLATES.glob("*.txt"))


def test_templates_are_found():
    assert TEMPLATE_FILES


@pytest.mark.parametrize("path", TEMPLATE_FILES, ids=lambda p: p.name)
def test_template_names_no_forbidden_model(path):
    text = path.read_text(encoding="utf-8")
    assert [m for m in FORBIDDEN_MODELS if m in text] == []


@pytest.mark.parametrize("path", TEMPLATE_FILES, ids=lambda p: p.name)
def test_template_names_no_deleted_wrapper(path):
    assert "gemini-model-check" not in path.read_text(encoding="utf-8")
