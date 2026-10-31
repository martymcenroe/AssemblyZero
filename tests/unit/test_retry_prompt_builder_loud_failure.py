"""retry_prompt_builder under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md.
"""
from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from assemblyzero.workflows.implementation_spec.nodes import retry_prompt_builder as rpb

LLD = "# LLD\n\n## 2. Files\n\n### `src/a.py`\n\nThe a module.\n"


def _ctx(**overrides) -> rpb.RetryContext:
    ctx = rpb.RetryContext(
        lld_content=LLD, target_file="src/a.py", error_message="boom",
        retry_count=1, previous_attempt_snippet="x = 1", completed_files=[],
    )
    ctx.update(overrides)
    return ctx


def test_87_an_invalid_retry_context_raises():
    """Compliant, pinned."""
    with pytest.raises(ValueError, match="retry_count"):
        rpb.build_retry_prompt(_ctx(retry_count=0))


def test_101_tier_two_without_a_snippet_raises():
    """Compliant, pinned."""
    with pytest.raises(ValueError, match="previous_attempt_snippet"):
        rpb.build_retry_prompt(_ctx(retry_count=2, previous_attempt_snippet=None))


def test_174_a_missing_file_section_falls_back_to_the_full_lld_and_says_so():
    """WON'T DO, pinned: tier 2 is a token-saving prune. When the LLD has no
    section for the file, the fallback sends the WHOLE LLD, a superset of
    what tier 2 would have sent, and the result says tier 1 "[fallback]"."""
    result = rpb.build_retry_prompt(
        _ctx(retry_count=2, target_file="assemblyzero/nonexistent/zzz_module.py")
    )
    assert result["tier"] == 1
    assert any("fallback" in s for s in result["context_sections_included"])
    assert "The a module." in result["prompt_text"]


def test_232_a_token_estimate_that_fails_raises_and_logs_an_error(caplog):
    """It returned -1, an in-band number a caller could read as a count."""
    with patch.object(
        rpb.tiktoken, "get_encoding", side_effect=OSError("no encoding file"),
    ), caplog.at_level(logging.ERROR, logger=rpb.__name__), pytest.raises(
        OSError, match="no encoding file",
    ):
        rpb._estimate_tokens("some text")
    assert any(
        r.levelno == logging.ERROR and "OSError" in r.getMessage() for r in caplog.records
    )


def test_an_empty_text_is_zero_tokens():
    """Kept: no text, no tokens; nothing was estimated."""
    assert rpb._estimate_tokens("") == 0
