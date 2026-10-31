"""text_sanitizer.py under standard 0034, one test per sweep site (#3799).

``strip_emoji`` sanitizes a model's response text. Given something that is
not text, it returned ``str()`` of it, unstripped: a bytes response became the
string ``"b'...'"`` and a parsed object became its repr, each passed on as the
model's answer. It now raises TypeError naming the type. None is still the
empty string. Line numbers in the names are ledger 0908's, at its base
``79e18ad1``.
"""
from __future__ import annotations

import pytest

from assemblyzero.core.text_sanitizer import strip_emoji


@pytest.mark.parametrize("value", [42, b"Tests passed \xe2\x9c\x85", {"text": "hi"}, ["a"]])
def test_72_a_response_that_is_not_text_raises(value):
    with pytest.raises(TypeError, match=type(value).__name__):
        strip_emoji(value)  # type: ignore[arg-type]


def test_none_is_still_the_empty_string():
    """Kept: None is the documented "no text", returned as ""."""
    assert strip_emoji(None) == ""


def test_text_is_still_sanitized():
    """Kept."""
    assert strip_emoji("Tests passed ✅") == "Tests passed [PASS]"
