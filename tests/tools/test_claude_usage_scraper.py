"""Unit tests for claude-usage-scraper.py parsing functions.

Issue #434: Add Tests for claude-usage-scraper.py Regex Parsing

Tests cover: ANSI stripping, token parsing, cost parsing, model extraction,
usage line extraction, full block parsing, regression, import safety,
and ReDoS resilience.
"""

import io
import json
import re
import sys
import time
import socket
import importlib
import importlib.util
from pathlib import Path
from unittest import mock

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Import module under test using importlib to handle the hyphenated filename.
# This relies on the __main__ guard being present — importing must not trigger execution.
_scraper_path = Path(__file__).resolve().parents[2] / "tools" / "claude-usage-scraper.py"
_spec = importlib.util.spec_from_file_location("claude_usage_scraper", _scraper_path)
scraper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scraper)

# Import fixtures
from tests.fixtures.scraper import ansi_samples, usage_outputs


# ── Test Helper ──

def make_ansi(text: str, code: int = 32) -> str:
    """Wrap text in ANSI escape codes for test fixture generation."""
    return f"\033[{code}m{text}\033[0m"


# ── T010-T050: TestStripAnsiCodes ──

class TestStripAnsiCodes:
    """Tests for strip_ansi_codes() function."""

    def test_strip_ansi_basic_sgr(self):
        """T010: Removes basic SGR codes like \\033[32m."""
        assert scraper.strip_ansi_codes("\033[32mGreen\033[0m") == "Green"

    def test_strip_ansi_nested(self):
        """T020: Handles overlapping/nested ANSI sequences."""
        assert scraper.strip_ansi_codes("\033[1m\033[31mBold Red\033[0m") == "Bold Red"

    def test_strip_ansi_no_codes(self):
        """T030: Returns input unchanged when no ANSI present."""
        assert scraper.strip_ansi_codes("plain text") == "plain text"

    def test_strip_ansi_empty_string(self):
        """T040: Returns empty string."""
        assert scraper.strip_ansi_codes("") == ""

    def test_strip_ansi_cursor_movement(self):
        """T050: Removes cursor positioning sequences."""
        assert scraper.strip_ansi_codes("\033[2J\033[HText") == "Text"


# ── T060-T100: TestParseTokenCount ──

class TestParseTokenCount:
    """Tests for parse_token_count() function."""

    def test_parse_token_count_simple(self):
        """T060: Simple integer string."""
        assert scraper.parse_token_count("1234") == 1234

    def test_parse_token_count_commas(self):
        """T070: Comma-separated token count."""
        assert scraper.parse_token_count("1,234,567") == 1234567

    def test_parse_token_count_whitespace(self):
        """T080: Token count with leading/trailing whitespace."""
        assert scraper.parse_token_count(" 500 ") == 500

    def test_parse_token_count_zero(self):
        """T090: Zero token count."""
        assert scraper.parse_token_count("0") == 0

    def test_parse_token_count_invalid(self):
        """T100: Non-numeric string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse token count"):
            scraper.parse_token_count("abc")

    @pytest.mark.parametrize("raw,expected", list(usage_outputs.TOKEN_COUNT_CASES.items()))
    def test_parse_token_count_parametrized(self, raw, expected):
        """Parametrized token count cases from fixtures."""
        assert scraper.parse_token_count(raw) == expected

    @pytest.mark.parametrize("raw", usage_outputs.TOKEN_COUNT_ERROR_CASES)
    def test_parse_token_count_error_cases(self, raw):
        """Parametrized error cases from fixtures."""
        with pytest.raises(ValueError):
            scraper.parse_token_count(raw)


# ── T110-T150: TestParseCostValue ──

class TestParseCostValue:
    """Tests for parse_cost_value() function."""

    def test_parse_cost_with_dollar(self):
        """T110: Cost string with $ prefix."""
        assert scraper.parse_cost_value("$0.0042") == pytest.approx(0.0042)

    def test_parse_cost_without_dollar(self):
        """T120: Cost string without $ prefix."""
        assert scraper.parse_cost_value("0.0042") == pytest.approx(0.0042)

    def test_parse_cost_zero(self):
        """T130: Zero cost."""
        assert scraper.parse_cost_value("$0.00") == 0.0

    def test_parse_cost_whitespace(self):
        """T140: Cost with whitespace."""
        assert scraper.parse_cost_value(" $1.23 ") == pytest.approx(1.23)

    def test_parse_cost_invalid(self):
        """T150: Unparseable cost string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse cost value"):
            scraper.parse_cost_value("free")

    @pytest.mark.parametrize("raw,expected", list(usage_outputs.COST_VALUE_CASES.items()))
    def test_parse_cost_parametrized(self, raw, expected):
        """Parametrized cost cases from fixtures."""
        assert scraper.parse_cost_value(raw) == pytest.approx(expected)

    @pytest.mark.parametrize("raw", usage_outputs.COST_VALUE_ERROR_CASES)
    def test_parse_cost_error_cases(self, raw):
        """Parametrized error cases from fixtures."""
        with pytest.raises(ValueError):
            scraper.parse_cost_value(raw)


# ── T160-T190: TestExtractUsageLine ──

class TestExtractUsageLine:
    """Tests for extract_usage_line() function."""

    def test_extract_usage_line_valid(self):
        """T160: Returns complete record from clean usage line."""
        result = scraper.extract_usage_line(usage_outputs.CLEAN_USAGE_LINE)
        assert result is not None
        assert result["session_id"] == "abc123"
        assert result["input_tokens"] == 15234
        assert result["output_tokens"] == 3421
        assert result["cache_read_tokens"] == 8000
        assert result["cache_write_tokens"] == 1200
        assert result["total_cost_usd"] == pytest.approx(0.0847)
        assert result["model"] == "claude-sonnet-4-20250514"
        assert result["timestamp"] is None

    def test_extract_usage_line_with_ansi(self):
        """T170: Strips ANSI then parses correctly."""
        result = scraper.extract_usage_line(ansi_samples.ANSI_USAGE_LINE)
        assert result is not None
        assert result["session_id"] == "abc123"
        assert result["input_tokens"] == 15234
        assert result["output_tokens"] == 3421
        assert result["model"] == "claude-sonnet-4-20250514"

    def test_extract_usage_line_no_match(self):
        """T180: Returns None for non-usage lines."""
        assert scraper.extract_usage_line("Starting session...") is None

    def test_extract_usage_line_partial(self):
        """T190: Returns None for truncated lines."""
        assert scraper.extract_usage_line("abc123  claude-sonnet") is None

    @pytest.mark.parametrize("line", usage_outputs.MALFORMED_LINES)
    def test_extract_usage_line_malformed(self, line):
        """All malformed lines return None."""
        assert scraper.extract_usage_line(line) is None


# ── T200-T240: TestExtractModelName ──

class TestExtractModelName:
    """Tests for extract_model_name() function."""

    def test_extract_model_name_sonnet(self):
        """T200: Extracts sonnet model."""
        result = scraper.extract_model_name("model: claude-sonnet-4-20250514")
        assert result == "claude-sonnet-4-20250514"

    def test_extract_model_name_opus(self):
        """T210: Extracts opus model."""
        result = scraper.extract_model_name("model: claude-opus-4-20250514")
        assert result == "claude-opus-4-20250514"

    def test_extract_model_name_haiku(self):
        """T220: Extracts haiku model."""
        result = scraper.extract_model_name("model: claude-haiku-3-20250514")
        assert result == "claude-haiku-3-20250514"

    def test_extract_model_name_none(self):
        """T230: Returns None when no model present."""
        assert scraper.extract_model_name("no model info here") is None

    def test_extract_model_name_multiple(self):
        """T240: Returns first match when multiple present."""
        text = "claude-sonnet-4-20250514 and claude-opus-4-20250514"
        result = scraper.extract_model_name(text)
        assert result == "claude-sonnet-4-20250514"

    @pytest.mark.parametrize(
        "text,expected",
        list(usage_outputs.MODEL_STRINGS.items()),
    )
    def test_extract_model_name_parametrized(self, text, expected):
        """Parametrized model name cases from fixtures."""
        assert scraper.extract_model_name(text) == expected


# ── T250-T290: TestParseUsageBlock ──

class TestParseUsageBlock:
    """Tests for parse_usage_block() function."""

    def test_parse_usage_block_full(self):
        """T250: Parses multi-line block into list of records."""
        results = scraper.parse_usage_block(usage_outputs.FULL_USAGE_BLOCK)
        assert len(results) == 2
        assert results[0]["session_id"] == "abc123"
        assert results[0]["input_tokens"] == 15234
        assert results[1]["session_id"] == "def456"
        assert results[1]["input_tokens"] == 22100

    def test_parse_usage_block_mixed(self):
        """T260: Skips non-usage lines, parses valid ones."""
        results = scraper.parse_usage_block(usage_outputs.MIXED_BLOCK)
        assert len(results) == usage_outputs.MIXED_BLOCK_EXPECTED_COUNT

    def test_parse_usage_block_empty(self):
        """T270: Returns empty list for empty input."""
        assert scraper.parse_usage_block("") == []

    def test_parse_usage_block_ansi_heavy(self):
        """T280: Correctly parses fully ANSI-encoded block."""
        results = scraper.parse_usage_block(ansi_samples.ANSI_FULL_BLOCK)
        assert len(results) == 2
        assert results[0]["session_id"] == "abc123"
        assert results[0]["model"] == "claude-sonnet-4-20250514"
        assert results[1]["session_id"] == "def456"

    def test_parse_usage_block_single_line(self):
        """T290: Handles block with exactly one usage line."""
        results = scraper.parse_usage_block(usage_outputs.CLEAN_USAGE_LINE)
        assert len(results) == 1
        assert results[0]["session_id"] == "abc123"


# ── T300: TestRegression ──

class TestRegression:
    """Regression test comparing output against golden files."""

    def test_scraper_regression_output_unchanged(self):
        """T300: Scraper parse output matches golden file after refactor."""
        golden_input_path = Path(__file__).resolve().parents[1] / "fixtures" / "scraper" / "golden_input.txt"
        golden_output_path = Path(__file__).resolve().parents[1] / "fixtures" / "scraper" / "golden_output.txt"

        if not golden_input_path.exists() or not golden_output_path.exists():
            pytest.skip(
                "Golden files not generated yet. Run: "
                "python tools/claude-usage-scraper.py < tests/fixtures/scraper/golden_input.txt "
                "> tests/fixtures/scraper/golden_output.txt"
            )

        golden_input = golden_input_path.read_text(encoding="utf-8")
        golden_output = golden_output_path.read_text(encoding="utf-8").strip()

        if not golden_output:
            pytest.skip("Golden output file is empty — needs to be generated.")

        # Run the refactored parse function against the same input
        result = scraper.parse_usage_data(golden_input)

        # Normalize the timestamp field since it changes on each run
        # Both golden and actual should be compared without volatile fields
        expected = json.loads(golden_output)
        result.pop("timestamp", None)
        expected.pop("timestamp", None)

        actual_normalized = json.dumps(result, indent=None, sort_keys=True)
        expected_normalized = json.dumps(expected, indent=None, sort_keys=True)

        assert actual_normalized == expected_normalized, (
            f"Regression detected!\n"
            f"Expected: {expected_normalized}\n"
            f"Actual:   {actual_normalized}"
        )


# ── T310: TestImportSafety ──

class TestImportSafety:
    """Test that importing the module has no side effects."""

    def test_import_no_side_effects(self):
        """T310: Importing module does not execute scraper logic."""
        # Capture stdout during a fresh import
        captured = io.StringIO()
        with mock.patch("sys.stdout", captured):
            # Force re-import
            fresh_spec = importlib.util.spec_from_file_location(
                "claude_usage_scraper_fresh", _scraper_path
            )
            fresh_mod = importlib.util.module_from_spec(fresh_spec)
            fresh_spec.loader.exec_module(fresh_mod)

        output = captured.getvalue()
        # Should produce no output on import
        assert output == "", (
            f"Module produced output on import (side effect detected): {output!r}"
        )


# ── T320-T330: TestRealisticFixtures ──

class TestRealisticFixtures:
    """Tests using realistic CLI fixture data."""

    def test_strip_ansi_with_realistic_cli_output(self):
        """T320: ANSI stripping works on actual Claude CLI fixture data."""
        result = scraper.strip_ansi_codes(ansi_samples.ANSI_USAGE_LINE)
        assert result == ansi_samples.ANSI_USAGE_LINE_EXPECTED_CLEAN

    def test_parse_usage_block_realistic_fixture(self):
        """T330: Full block parse against realistic fixture matches expected records."""
        results = scraper.parse_usage_block(usage_outputs.FULL_USAGE_BLOCK)
        assert len(results) == len(usage_outputs.FULL_USAGE_BLOCK_EXPECTED)

        for actual, expected in zip(results, usage_outputs.FULL_USAGE_BLOCK_EXPECTED):
            assert actual["session_id"] == expected["session_id"]
            assert actual["input_tokens"] == expected["input_tokens"]
            assert actual["output_tokens"] == expected["output_tokens"]
            assert actual["cache_read_tokens"] == expected["cache_read_tokens"]
            assert actual["cache_write_tokens"] == expected["cache_write_tokens"]
            assert actual["total_cost_usd"] == pytest.approx(expected["total_cost_usd"])
            assert actual["model"] == expected["model"]


# ── T340: TestNoNetworkAccess ──

class TestNoNetworkAccess:
    """Verify tests run without network access."""

    def test_no_network_access(self):
        """T340: All parsing functions complete without any socket calls."""
        original_connect = socket.socket.connect
        connect_calls = []

        def mock_connect(self, *args, **kwargs):
            connect_calls.append(args)
            raise ConnectionError("Network access blocked by test")

        with mock.patch.object(socket.socket, "connect", mock_connect):
            # Run all parsing functions
            scraper.strip_ansi_codes("\033[32mtest\033[0m")
            scraper.parse_token_count("1,234")
            scraper.parse_cost_value("$0.01")
            scraper.extract_model_name("claude-sonnet-4-20250514")
            scraper.extract_usage_line(usage_outputs.CLEAN_USAGE_LINE)
            scraper.parse_usage_block(usage_outputs.FULL_USAGE_BLOCK)

        assert len(connect_calls) == 0, (
            f"Network access detected: {len(connect_calls)} socket.connect calls"
        )


# ── T350: TestReDoSResilience ──

class TestReDoSResilience:
    """ReDoS resilience tests with adversarial long strings.

    Simple parsing functions (strip_ansi, parse_token_count, parse_cost_value)
    use a tight 100ms budget. The extract_usage_line function uses a multi-group
    regex that must attempt matching at each position in the input, so it gets a
    more generous 2s budget on long non-matching strings — still well below the
    exponential blowup (minutes+) that a truly vulnerable regex would exhibit.
    """

    TIMEOUT_SECONDS = 0.1  # 100ms budget for simple parsers
    REGEX_MATCH_TIMEOUT = 2.0  # 2s budget for complex regex on long non-matching input

    def test_redos_strip_ansi_long_string(self):
        """T350a: strip_ansi_codes completes within timeout on >10k char input."""
        long_input = ansi_samples.LONG_ADVERSARIAL_PLAIN  # "x" * 15000
        start = time.monotonic()
        result = scraper.strip_ansi_codes(long_input)
        elapsed = time.monotonic() - start

        assert elapsed < self.TIMEOUT_SECONDS, (
            f"strip_ansi_codes took {elapsed:.3f}s on {len(long_input)} chars "
            f"(budget: {self.TIMEOUT_SECONDS}s)"
        )
        # Plain string with no ANSI should return unchanged
        assert result == long_input

    def test_redos_strip_ansi_adversarial_ansi(self):
        """T350b: strip_ansi_codes handles adversarial ANSI-like sequence."""
        long_input = ansi_samples.LONG_ADVERSARIAL_ANSI_LIKE
        start = time.monotonic()
        result = scraper.strip_ansi_codes(long_input)
        elapsed = time.monotonic() - start

        assert elapsed < self.TIMEOUT_SECONDS, (
            f"strip_ansi_codes took {elapsed:.3f}s (budget: {self.TIMEOUT_SECONDS}s)"
        )

    def test_redos_parse_token_count_long_string(self):
        """T350c: parse_token_count handles >10k char adversarial input."""
        long_input = ansi_samples.LONG_ADVERSARIAL_TOKEN  # "1" * 12000 + "abc"
        start = time.monotonic()
        with pytest.raises(ValueError):
            scraper.parse_token_count(long_input)
        elapsed = time.monotonic() - start

        assert elapsed < self.TIMEOUT_SECONDS, (
            f"parse_token_count took {elapsed:.3f}s on {len(long_input)} chars "
            f"(budget: {self.TIMEOUT_SECONDS}s)"
        )

    def test_redos_parse_cost_long_string(self):
        """T350d: parse_cost_value handles >10k char adversarial input."""
        long_input = ansi_samples.LONG_ADVERSARIAL_COST  # "$" + "9" * 11000
        start = time.monotonic()
        # May either parse (as a huge number) or raise ValueError
        try:
            scraper.parse_cost_value(long_input)
        except ValueError:
            pass
        elapsed = time.monotonic() - start

        assert elapsed < self.TIMEOUT_SECONDS, (
            f"parse_cost_value took {elapsed:.3f}s on {len(long_input)} chars "
            f"(budget: {self.TIMEOUT_SECONDS}s)"
        )

    def test_redos_extract_usage_line_long_string(self):
        """T350e: extract_usage_line handles >10k char adversarial input.

        The multi-group _USAGE_LINE_PATTERN regex performs linear-time scanning
        but must attempt matching at each position in a long non-matching string,
        so we allow a more generous budget than simple parsers while still
        verifying no exponential backtracking occurs.
        """
        long_input = "x" * 15000
        start = time.monotonic()
        result = scraper.extract_usage_line(long_input)
        elapsed = time.monotonic() - start

        assert result is None
        assert elapsed < self.REGEX_MATCH_TIMEOUT, (
            f"extract_usage_line took {elapsed:.3f}s on {len(long_input)} chars "
            f"(budget: {self.REGEX_MATCH_TIMEOUT}s) — possible ReDoS vulnerability"
        )