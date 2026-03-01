"""Tests for text_sanitizer.strip_emoji().

Issue #527: Strip emoji from all LLM output.
"""

from assemblyzero.core.text_sanitizer import strip_emoji


class TestSemanticReplacements:
    """Emojis with meaning get replaced with ASCII equivalents."""

    def test_checkmark_to_pass(self):
        assert strip_emoji("Tests passed \u2705") == "Tests passed [PASS]"

    def test_heavy_checkmark_to_pass(self):
        assert strip_emoji("\u2714 All good") == "[PASS] All good"

    def test_ballot_check_to_pass(self):
        assert strip_emoji("\u2611 Done") == "[PASS] Done"

    def test_cross_to_fail(self):
        assert strip_emoji("Build \u274C") == "Build [FAIL]"

    def test_heavy_x_to_fail(self):
        assert strip_emoji("\u2716 Error") == "[FAIL] Error"

    def test_warning_to_warn(self):
        assert strip_emoji("\u26A0 Caution") == "[WARN] Caution"

    def test_warning_with_variation_selector(self):
        assert strip_emoji("\u26A0\uFE0F Caution") == "[WARN] Caution"

    def test_lightbulb_to_tip(self):
        assert strip_emoji("\U0001F4A1 Idea") == "[TIP] Idea"

    def test_info_to_note(self):
        assert strip_emoji("\u2139 See docs") == "[NOTE] See docs"

    def test_right_arrow(self):
        assert strip_emoji("A \u27A1 B") == "A -> B"

    def test_left_arrow(self):
        assert strip_emoji("B \u2B05 A") == "B <- A"

    def test_unicode_arrows(self):
        assert strip_emoji("input \u2192 output") == "input -> output"
        assert strip_emoji("output \u2190 input") == "output <- input"


class TestEmojiStripping:
    """Remaining emojis get stripped completely."""

    def test_emoticons_stripped(self):
        assert strip_emoji("Hello \U0001F600 world") == "Hello  world"

    def test_transport_stripped(self):
        assert strip_emoji("Ship it \U0001F680") == "Ship it "

    def test_misc_symbols_stripped(self):
        assert strip_emoji("Weather \u2600 report") == "Weather  report"

    def test_multiple_emojis_stripped(self):
        result = strip_emoji("\U0001F600\U0001F601\U0001F602 text \U0001F680")
        assert result == " text "

    def test_flag_emojis_stripped(self):
        assert strip_emoji("Flag \U0001F1FA\U0001F1F8 here") == "Flag  here"

    def test_zwj_sequences_stripped(self):
        # Family emoji: man + ZWJ + woman + ZWJ + girl
        assert strip_emoji("Family \U0001F468\u200D\U0001F469\u200D\U0001F467 here") == "Family  here"

    def test_variation_selectors_stripped(self):
        assert strip_emoji("Star \u2B50\uFE0F here") == "Star  here"

    def test_star_emoji_stripped(self):
        assert strip_emoji("\u2B50") == ""


class TestCleanPassthrough:
    """Non-emoji text passes through unchanged."""

    def test_plain_text(self):
        text = "This is plain text with no emojis."
        assert strip_emoji(text) == text

    def test_code_block_indentation_preserved(self):
        text = "```python\ndef foo():\n    return 42\n```"
        assert strip_emoji(text) == text

    def test_markdown_table_alignment_preserved(self):
        text = "| Col1 | Col2 |\n|------|------|\n| a    | b    |"
        assert strip_emoji(text) == text

    def test_markdown_headers(self):
        text = "# Header\n## Subheader\n### Third"
        assert strip_emoji(text) == text

    def test_urls_preserved(self):
        text = "Visit https://example.com/path?q=1&r=2"
        assert strip_emoji(text) == text

    def test_ascii_symbols_preserved(self):
        text = "Result: pass/fail [OK] (done) {key: value} @user #tag"
        assert strip_emoji(text) == text

    def test_numbers_and_math(self):
        text = "Score: 95.5% (19/20) = 0.975"
        assert strip_emoji(text) == text

    def test_multiple_spaces_preserved(self):
        """Intentional multiple spaces are not collapsed."""
        text = "A   B"
        assert strip_emoji(text) == text

    def test_newlines_preserved(self):
        text = "Line 1\n\nLine 3"
        assert strip_emoji(text) == text

    def test_tabs_preserved(self):
        text = "Col1\tCol2\tCol3"
        assert strip_emoji(text) == text


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_none_returns_empty(self):
        assert strip_emoji(None) == ""

    def test_empty_string(self):
        assert strip_emoji("") == ""

    def test_only_emojis(self):
        result = strip_emoji("\U0001F600\U0001F601\U0001F602")
        assert result == ""

    def test_non_string_input(self):
        assert strip_emoji(42) == "42"

    def test_mixed_semantic_and_strip(self):
        result = strip_emoji("\u2705 Test passed \U0001F680 deploying")
        assert result == "[PASS] Test passed  deploying"

    def test_repeated_semantic_emojis(self):
        result = strip_emoji("\u2705 first \u2705 second \u2705 third")
        assert result == "[PASS] first [PASS] second [PASS] third"

    def test_emoji_only_line_in_multiline(self):
        text = "Line 1\n\U0001F680\nLine 3"
        assert strip_emoji(text) == "Line 1\n\nLine 3"
