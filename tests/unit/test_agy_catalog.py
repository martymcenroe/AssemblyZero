"""#4178: the Gemini ids AssemblyZero sends are ids agy offers, and never Argon.

`tests/fixtures/agy_models.txt` is the output of `agy models`, recorded on
2026-10-21. When agy's catalog changes, re-record it: a retired id still named
in `AGY_GEMINI_MODELS` then fails here instead of failing every live call.

The catalog's Gemini models are 3.8 Flash and Argon. The operator forbids
Argon (2026-10-16, and again 2026-10-21: "DO NOT USE ARGON"), so nothing may
resolve to it and every path that builds a Gemini call refuses it.
"""

from pathlib import Path

import pytest

from assemblyzero.core.config import AGY_GEMINI_MODELS, FORBIDDEN_MODELS, REVIEWER_MODEL
from assemblyzero.core.gemini_client import GeminiClient
from assemblyzero.core.llm_provider import GeminiProvider
from assemblyzero.core.preflight import DEFAULT_PROBE_MODEL
from assemblyzero.core.seats import ProfileError, check_spec
from assemblyzero.workflows.testing.adversarial_gemini import (
    AdversarialGeminiClient,
    GeminiModelDowngradeError,
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


ARGON_IDS = sorted(i for i in catalog_ids() if "argon" in i)


def forbidden(model_id: str) -> bool:
    """FORBIDDEN_MODELS read as every check reads it: exact, then family."""
    lowered = model_id.lower()
    return any(entry.lower() in lowered for entry in FORBIDDEN_MODELS)


def test_the_catalog_lists_argon():
    """The refusals below are only meaningful while agy offers Argon."""
    assert ARGON_IDS == ["gemini-4-argon-high", "gemini-4-argon-low", "gemini-4-argon-medium"]


def test_every_allowed_id_is_in_the_catalog():
    """AC1: an allowed id missing from agy's catalog fails here."""
    assert sorted(AGY_GEMINI_MODELS - catalog_ids()) == []


def test_every_map_value_is_in_the_catalog_and_allowed():
    values = set(GeminiProvider.MODEL_MAP.values())
    assert sorted(values - catalog_ids()) == []
    assert sorted(v for v in values if forbidden(v)) == []


@pytest.mark.parametrize("model_id", ARGON_IDS)
def test_argon_is_forbidden(model_id):
    assert forbidden(model_id)
    assert model_id not in AGY_GEMINI_MODELS
    assert model_id not in GeminiProvider.MODEL_MAP.values()


@pytest.mark.parametrize("model_id", ARGON_IDS)
def test_the_client_refuses_argon(model_id):
    with pytest.raises(ValueError, match="forbidden"):
        GeminiClient(model=model_id)


@pytest.mark.parametrize("spec", ["gemini:gemini-4-argon-high", "gemini:4-argon"])
def test_a_seat_naming_argon_is_refused(spec):
    with pytest.raises(ProfileError, match="gemini-4-argon"):
        check_spec(spec, "test.seat")


def test_the_adversarial_reply_check_refuses_argon():
    client = AdversarialGeminiClient.__new__(AdversarialGeminiClient)
    with pytest.raises(GeminiModelDowngradeError):
        client.verify_model_is_pro({"model": "gemini-4-argon-high"})


def test_the_defaults_are_allowed_ids():
    assert REVIEWER_MODEL in AGY_GEMINI_MODELS
    assert DEFAULT_PROBE_MODEL in AGY_GEMINI_MODELS
    assert GeminiProvider()._model_id in AGY_GEMINI_MODELS


@pytest.mark.parametrize("tier", ["low", "medium", "high"])
def test_flash_resolves_by_name(tier):
    """AC2: a caller that asks for 3.8 Flash by name gets it."""
    provider = GeminiProvider(f"3.8-flash-{tier}")
    assert provider._model_id == f"gemini-3.8-flash-{tier}"
    assert not forbidden(provider._model_id)
