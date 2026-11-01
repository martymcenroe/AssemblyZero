"""The Gemini verification wiki page states the fleet's model rules (#4478).

It approved `gemini-3-pro-preview`, which is forbidden, and forbade the Flash
family, the only Gemini family the fleet may use. A reader who followed it
pinned a model `GeminiClient` refuses. The rules live in
`config/fleet-models.toml`, so the page is held to that file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.core.config import FORBIDDEN_MODELS, REVIEWER_MODEL

PAGE = Path(__file__).resolve().parents[2] / "wiki" / "Gemini-Verification.md"


def _table_models(heading: str) -> list[str]:
    """The first column of the table under `heading`, without its backticks."""
    section = PAGE.read_text(encoding="utf-8").split(f"### {heading}\n", 1)[1]
    section = section.split("\n#", 1)[0]
    return [
        line.split("|")[1].strip().strip("`")
        for line in section.splitlines()
        if line.startswith("| `")
    ]


def test_the_approved_table_has_rows() -> None:
    """Guards the tests below from passing vacuously."""
    assert len(_table_models("Acceptable Models")) >= 2


def test_t1_no_approved_model_is_forbidden() -> None:
    forbidden = [entry.lower() for entry in FORBIDDEN_MODELS]

    clashes = [
        model
        for model in _table_models("Acceptable Models")
        if any(entry in model.lower() for entry in forbidden)
    ]

    assert not clashes


def test_t1_the_reviewers_model_is_approved() -> None:
    assert REVIEWER_MODEL in _table_models("Acceptable Models")


@pytest.mark.parametrize(
    "model", sorted(set(_table_models("Forbidden Models")) | set(FORBIDDEN_MODELS))
)
def test_t1_the_forbidden_table_is_the_policy_table(model: str) -> None:
    assert model in FORBIDDEN_MODELS, model
    assert model in _table_models("Forbidden Models"), model


def test_t2_the_page_names_the_model_of_today() -> None:
    text = PAGE.read_text(encoding="utf-8").lower()

    assert "gemini 3 pro" not in text
    assert "gemini-3-pro-preview`" in text  # only in the forbidden table
    assert text.count("gemini-3-pro-preview") == 1
