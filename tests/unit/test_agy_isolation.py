"""No test tier sees this machine's agy (#4253).

The operator's machines have agy and CI has none, so a test whose client
found the machine's agy behaved one way here and another on CI. The autouse
fixture ``no_agy_from_the_machine`` in ``tests/conftest.py`` makes both
lookups find nothing. These tests fail before that fixture on any machine with
agy installed, and pass on CI either way.
"""
from __future__ import annotations

import pytest

from assemblyzero.core import gemini_client
from assemblyzero.core.gemini_client import GeminiClient

MODEL = "gemini-3.1-pro-high"


def test_t1_a_client_with_no_stand_in_finds_no_agy():
    client = GeminiClient(model=MODEL)

    assert client._agy_cli is None


def test_t1_neither_lookup_finds_the_machines_agy():
    assert gemini_client._find_linux_agy() is None
    assert gemini_client._find_wsl_agy() is None


def test_t1_a_windows_client_finds_no_agy_inside_wsl(monkeypatch):
    """The Windows branch asks WSL; it finds nothing there either."""
    monkeypatch.setattr(gemini_client, "_ON_WINDOWS", True)

    client = GeminiClient(model=MODEL)

    assert client._agy_cli is None


def test_r2_a_test_that_needs_agy_gives_its_client_a_stand_in():
    """Requirement 2: a test that needs agy present says so with a path."""
    client = GeminiClient(model=MODEL)
    client._agy_cli = "/stand-in/agy"

    assert client._agy_argv("/work", "--model", MODEL) == [
        "/stand-in/agy", "--model", MODEL,
    ]


@pytest.mark.real_agy_lookup
def test_a_test_of_the_lookup_itself_gets_the_real_functions():
    """The marker is the one way back to the real lookup."""
    assert gemini_client._find_linux_agy.__module__ == "assemblyzero.core.gemini_client"
    assert gemini_client._find_wsl_agy.__module__ == "assemblyzero.core.gemini_client"
