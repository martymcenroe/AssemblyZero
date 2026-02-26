"""Unit tests for _draft_has_open_questions() open-question detection.

Issue #469: "- [ ] None" placeholder was incorrectly detected as an
unchecked open question, causing an infinite LLD review loop.

Tests verify:
- "- [ ] None" (and variants) → False (placeholder, not a real question)
- Real unchecked questions → True
- Checked boxes → False
- Missing Open Questions section → False
- Mixed real and placeholder entries
"""

from __future__ import annotations

from assemblyzero.workflows.requirements.nodes.review import (
    _draft_has_open_questions,
)


def test_none_placeholder_returns_false():
    """Bare '- [ ] None' should not count as an open question."""
    content = "## Open Questions\n\n- [ ] None\n"
    assert _draft_has_open_questions(content) is False


def test_none_with_trailing_text_returns_false():
    """'- [ ] None — scope is well-defined' should not count."""
    content = "## Open Questions\n\n- [ ] None — scope is well-defined\n"
    assert _draft_has_open_questions(content) is False


def test_none_case_insensitive():
    """'- [ ] none', '- [ ] NONE' should all be filtered out."""
    for variant in ["none", "NONE", "None", "nOnE"]:
        content = f"## Open Questions\n\n- [ ] {variant}\n"
        assert _draft_has_open_questions(content) is False, f"Failed for: {variant}"


def test_real_question_returns_true():
    """A real unchecked question should be detected."""
    content = "## Open Questions\n\n- [ ] What about edge cases?\n"
    assert _draft_has_open_questions(content) is True


def test_checked_box_returns_false():
    """Checked boxes [x] should not count as open questions."""
    content = "## Open Questions\n\n- [x] Resolved question\n"
    assert _draft_has_open_questions(content) is False


def test_no_open_questions_section_returns_false():
    """Missing Open Questions heading → False."""
    content = "## Summary\n\nJust a summary.\n"
    assert _draft_has_open_questions(content) is False


def test_empty_content_returns_false():
    """Empty string → False."""
    assert _draft_has_open_questions("") is False


def test_mixed_none_and_real_question():
    """Mix of None placeholder + real question → True."""
    content = (
        "## Open Questions\n\n"
        "- [ ] None\n"
        "- [ ] Should we support batch mode?\n"
    )
    assert _draft_has_open_questions(content) is True


def test_bare_unchecked_box_no_text():
    """'- [ ] ' with trailing whitespace is ambiguous — treated as open question.

    This is the safer default: if a drafter left a bare checkbox, it's likely
    an incomplete entry that should be reviewed, not silently skipped.
    """
    content = "## Open Questions\n\n- [ ] \n"
    assert _draft_has_open_questions(content) is True
