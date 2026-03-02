"""Shared fixtures for unit tests."""

from dataclasses import dataclass, field
from unittest.mock import patch

import pytest


@dataclass
class _FakePreflightResult:
    passed: bool = True
    available_credentials: int = 1
    total_credentials: int = 1
    exhausted_names: list[str] = field(default_factory=list)
    model_reachable: bool = True
    warnings: list[str] = field(default_factory=list)


@pytest.fixture(autouse=True)
def _bypass_gemini_preflight():
    """Unit tests never depend on real Gemini credentials."""
    with patch(
        "assemblyzero.core.preflight.check_gemini_available",
        return_value=_FakePreflightResult(),
    ):
        yield
