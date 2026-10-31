"""section_utils.py under standard 0034, one test per sweep site (#3794).

``drafter_authored`` removes the machine-owned injected block before
requirement extraction. When the stripper could not be imported it handed the
document back unstripped, and the extractor then read the injected table as
the text of whichever requirement sat above it. The import failure now
propagates. Line numbers in the names are ledger 0908's, at its base
``79e18ad1``.
"""
from __future__ import annotations

import inspect
import sys

import pytest

from assemblyzero.core import section_utils

STRIPPER = "assemblyzero.workflows.requirements.table_injection"


def test_146_a_stripper_that_cannot_be_imported_propagates(monkeypatch):
    monkeypatch.setitem(sys.modules, STRIPPER, None)  # import now raises ImportError

    with pytest.raises(ImportError, match="table_injection"):
        section_utils.drafter_authored("## 3. Requirements\n\n1. One\n")


def test_the_stripper_runs_when_it_imports():
    """Kept: with the stripper there, the drafter's text comes back."""
    text = "## 3. Requirements\n\n1. One\n"
    assert section_utils.drafter_authored(text) == text
    assert section_utils.drafter_authored(None) == ""  # type: ignore[arg-type]


def test_147_no_fail_open_tag_remains():
    assert "fail-open" not in inspect.getsource(section_utils)
