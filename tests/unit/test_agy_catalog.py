"""#4178: the Gemini ids AssemblyZero sends are ids agy actually offers.

`tests/fixtures/agy_models.txt` is the output of `agy models`, recorded on
2026-10-21. When agy's catalog changes, re-record it: a retired id still named
in `AGY_GEMINI_MODELS` then fails here instead of failing every live call.
"""

from pathlib import Path

import pytest

from assemblyzero.core.config import (
    AGY_GEMINI_FLASH_MODELS,
    AGY_GEMINI_MODELS,
    AGY_GEMINI_REVIEW_MODELS,
    FORBIDDEN_MODELS,
    REVIEWER_MODEL,
)
from assemblyzero.core.llm_provider import GeminiProvider
from assemblyzero.core.preflight import DEFAULT_PROBE_MODEL
from assemblyzero.workflows.testing.adversarial_gemini import (
    AdversarialGeminiClient,
    ForbiddenModelError,
    GeminiModelDowngradeError,
    resolve_adversarial_model,
)

CATALOG = Path(__file__).parent.parent / "fixtures" / "agy_models.txt"


def catalog_ids() -> set[str]:
    """The model ids in the recorded catalog: the first tab-separated field
    of each model line. The progress line agy prints first has no tab."""
    ids = set()
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        model_id, tab, _ = line.partition("\t")
        if tab:
            ids.add(model_id.strip())
    return ids


def test_catalog_fixture_is_readable():
    assert "gemini-4-argon-high" in catalog_ids()


def test_every_allowed_id_is_in_the_catalog():
    """AC1: an allowed id missing from agy's catalog fails here."""
    assert sorted(AGY_GEMINI_MODELS - catalog_ids()) == []


def test_every_map_value_is_in_the_catalog():
    assert sorted(set(GeminiProvider.MODEL_MAP.values()) - catalog_ids()) == []


def test_default_ids_are_in_the_review_tier():
    """The reviewer and the preflight probe default to the review tier."""
    assert REVIEWER_MODEL in AGY_GEMINI_REVIEW_MODELS
    assert DEFAULT_PROBE_MODEL in AGY_GEMINI_REVIEW_MODELS
    assert GeminiProvider()._model_id in AGY_GEMINI_REVIEW_MODELS


@pytest.mark.parametrize("tier", ["low", "medium", "high"])
def test_flash_resolves_by_name(tier):
    """AC2: a caller that asks for 3.8 Flash by name gets it."""
    provider = GeminiProvider(f"3.8-flash-{tier}")
    assert provider._model_id == f"gemini-3.8-flash-{tier}"
    assert provider._model_id in AGY_GEMINI_FLASH_MODELS
    assert provider._model_id not in FORBIDDEN_MODELS


def test_no_review_alias_resolves_to_flash():
    """Flash is reached only through an alias that says flash."""
    for alias, model_id in GeminiProvider.MODEL_MAP.items():
        if model_id in AGY_GEMINI_FLASH_MODELS:
            assert "flash" in alias, alias


def test_adversarial_seat_resolves_to_argon():
    assert resolve_adversarial_model("gemini:3.1-pro") == "gemini-4-argon-high"


def test_adversarial_seat_still_refuses_flash():
    """The adversarial gate keeps its own choice of model (#4178 req 2)."""
    with pytest.raises(ForbiddenModelError):
        resolve_adversarial_model("gemini:3.8-flash-high")


@pytest.mark.parametrize("model_id", sorted(AGY_GEMINI_REVIEW_MODELS))
def test_adversarial_reply_check_accepts_argon(model_id):
    client = AdversarialGeminiClient.__new__(AdversarialGeminiClient)
    assert client.verify_model_is_pro({"model": model_id}) is True


def test_adversarial_reply_check_refuses_flash():
    client = AdversarialGeminiClient.__new__(AdversarialGeminiClient)
    with pytest.raises(GeminiModelDowngradeError):
        client.verify_model_is_pro({"model": "gemini-3.8-flash-high"})
