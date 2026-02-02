"""Tests for the LLD reviewer node.

Test Scenarios from LLD:
- 010: Valid LLD approved
- 020: Invalid LLD blocked
- 030: JSON parse failure (fail-safe)
- 080: Missing prompt file
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentos.core.audit import ReviewAuditLog
from agentos.core.gemini_client import GeminiCallResult, GeminiErrorType
from agentos.nodes.lld_reviewer import (
    _load_system_instruction,
    _parse_gemini_response,
    review_lld_node,
)


@pytest.fixture
def mock_state():
    """Create a mock AgentState."""
    return {
        "messages": [],
        "issue_id": 50,
        "worktree_path": "/tmp/test-worktree",
        "lld_content": "# Test LLD\n\n## Context\nTest context\n\n## Proposed Changes\nTest changes",
        "lld_status": "PENDING",
        "gemini_critique": "",
        "iteration_count": 0,
    }


@pytest.fixture
def temp_log_path():
    """Create a temporary log file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_governance.jsonl"


class TestParseGeminiResponse:
    """Tests for response parsing."""

    def test_010_parses_approved_response(self):
        """Test parsing of an approved response."""
        response = """
# LLD Review: #50-Governance-Node

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect.

## Pre-Flight Gate: PASSED

## Review Summary
The LLD meets all requirements and is ready for implementation.

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation.

## Verdict
[x] **APPROVED** - Ready for implementation
[ ] **REVISE** - Fix Tier 1/2 issues first
"""
        verdict, critique, tier_1_issues = _parse_gemini_response(response)

        assert verdict == "APPROVED"
        assert "meets all requirements" in critique
        assert len(tier_1_issues) == 0

    def test_020_parses_blocked_response(self):
        """Test parsing of a blocked response."""
        response = """
# LLD Review: #50-Governance-Node

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect.

## Pre-Flight Gate: PASSED

## Review Summary
The LLD has critical safety issues that must be addressed.

## Tier 1: BLOCKING Issues

### Safety
- [x] **Worktree Scope Violation:** Design allows operations outside worktree.
- [x] **No Human Confirmation:** Destructive operations need confirmation.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
"""
        verdict, critique, tier_1_issues = _parse_gemini_response(response)

        assert verdict == "BLOCK"
        assert "critical safety issues" in critique
        assert len(tier_1_issues) >= 1

    def test_030_malformed_response_defaults_to_block(self):
        """Test that malformed response defaults to BLOCK (fail-safe)."""
        response = "This is not a valid Gemini response format at all."

        verdict, critique, tier_1_issues = _parse_gemini_response(response)

        assert verdict == "BLOCK"
        assert "parse" in critique.lower() or "failed" in critique.lower()

    def test_preflight_failure_returns_block(self):
        """Test that Pre-Flight Gate failure returns BLOCK."""
        response = """
# LLD Review: Test

## Pre-Flight Gate: FAILED

The submitted LLD does not meet structural requirements.
"""
        verdict, critique, tier_1_issues = _parse_gemini_response(response)

        assert verdict == "BLOCK"


class TestReviewLldNode:
    """Tests for the review_lld_node function."""

    def test_010_valid_lld_approved(self, mock_state, temp_log_path):
        """Test that a valid LLD gets approved."""
        approved_response = """
## Identity Confirmation
I am Gemini 3 Pro.

## Review Summary
LLD is complete and ready.

## Tier 1: BLOCKING Issues
No blocking issues.

## Verdict
[x] **APPROVED** - Ready for implementation
"""
        mock_result = GeminiCallResult(
            success=True,
            response=approved_response,
            raw_response=approved_response,
            error_type=None,
            error_message=None,
            credential_used="test-key",
            rotation_occurred=False,
            attempts=1,
            duration_ms=5000,
            model_verified="gemini-3-pro-preview",
        )

        with patch("agentos.nodes.lld_reviewer.GeminiClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.invoke.return_value = mock_result
            mock_client_class.return_value = mock_client

            with patch("agentos.nodes.lld_reviewer._load_system_instruction") as mock_load:
                mock_load.return_value = "System instruction"

                with patch("agentos.nodes.lld_reviewer.ReviewAuditLog") as mock_log_class:
                    mock_log = MagicMock()
                    mock_log_class.return_value = mock_log

                    result = review_lld_node(mock_state)

        assert result["lld_status"] == "APPROVED"
        assert result["iteration_count"] == 1
        mock_log.log.assert_called_once()

    def test_020_invalid_lld_blocked(self, mock_state, temp_log_path):
        """Test that an invalid LLD gets blocked."""
        blocked_response = """
## Identity Confirmation
I am Gemini 3 Pro.

## Review Summary
Critical issues found.

## Tier 1: BLOCKING Issues

### Safety
- [x] Missing worktree scope

## Verdict
[x] **REVISE** - Fix Tier 1/2 issues first
"""
        mock_result = GeminiCallResult(
            success=True,
            response=blocked_response,
            raw_response=blocked_response,
            error_type=None,
            error_message=None,
            credential_used="test-key",
            rotation_occurred=False,
            attempts=1,
            duration_ms=5000,
            model_verified="gemini-3-pro-preview",
        )

        with patch("agentos.nodes.lld_reviewer.GeminiClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.invoke.return_value = mock_result
            mock_client_class.return_value = mock_client

            with patch("agentos.nodes.lld_reviewer._load_system_instruction") as mock_load:
                mock_load.return_value = "System instruction"

                with patch("agentos.nodes.lld_reviewer.ReviewAuditLog") as mock_log_class:
                    mock_log = MagicMock()
                    mock_log_class.return_value = mock_log

                    result = review_lld_node(mock_state)

        assert result["lld_status"] == "BLOCK"

    def test_no_lld_content_returns_block(self, temp_log_path):
        """Test that missing LLD content returns BLOCK."""
        state = {
            "messages": [],
            "issue_id": 50,
            "worktree_path": "/tmp/test",
            "lld_content": "",  # Empty
            "lld_status": "PENDING",
            "gemini_critique": "",
            "iteration_count": 0,
        }

        with patch("agentos.nodes.lld_reviewer.ReviewAuditLog") as mock_log_class:
            mock_log = MagicMock()
            mock_log_class.return_value = mock_log

            result = review_lld_node(state)

        assert result["lld_status"] == "BLOCKED"
        assert "No LLD content" in result["gemini_critique"]

    def test_api_failure_returns_block(self, mock_state, temp_log_path):
        """Test that API failure returns BLOCK."""
        mock_result = GeminiCallResult(
            success=False,
            response=None,
            raw_response=None,
            error_type=GeminiErrorType.QUOTA_EXHAUSTED,
            error_message="All credentials exhausted",
            credential_used="",
            rotation_occurred=True,
            attempts=3,
            duration_ms=10000,
            model_verified="",
        )

        with patch("agentos.nodes.lld_reviewer.GeminiClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.invoke.return_value = mock_result
            mock_client_class.return_value = mock_client

            with patch("agentos.nodes.lld_reviewer._load_system_instruction") as mock_load:
                mock_load.return_value = "System instruction"

                with patch("agentos.nodes.lld_reviewer.ReviewAuditLog") as mock_log_class:
                    mock_log = MagicMock()
                    mock_log_class.return_value = mock_log

                    result = review_lld_node(mock_state)

        assert result["lld_status"] == "BLOCKED"
        assert "All credentials exhausted" in result["gemini_critique"]

    def test_080_missing_prompt_file_returns_block(self, mock_state):
        """Test that missing prompt file returns BLOCK."""
        with patch("agentos.nodes.lld_reviewer._load_system_instruction") as mock_load:
            mock_load.side_effect = FileNotFoundError("Prompt file not found")

            with patch("agentos.nodes.lld_reviewer.ReviewAuditLog") as mock_log_class:
                mock_log = MagicMock()
                mock_log_class.return_value = mock_log

                result = review_lld_node(mock_state)

        assert result["lld_status"] == "BLOCKED"
        assert "Configuration error" in result["gemini_critique"]

    def test_iteration_count_increments(self, mock_state):
        """Test that iteration count is incremented."""
        mock_state["iteration_count"] = 5

        with patch("agentos.nodes.lld_reviewer._load_system_instruction") as mock_load:
            mock_load.side_effect = FileNotFoundError("Test")

            with patch("agentos.nodes.lld_reviewer.ReviewAuditLog") as mock_log_class:
                mock_log = MagicMock()
                mock_log_class.return_value = mock_log

                result = review_lld_node(mock_state)

        assert result["iteration_count"] == 6

    def test_120_model_verification_failure_blocks(self, mock_state):
        """Test that model verification failure causes BLOCK."""
        # Response is successful but model is wrong
        mock_result = GeminiCallResult(
            success=True,
            response="[x] **APPROVED**",
            raw_response="{}",
            error_type=None,
            error_message=None,
            credential_used="test-key",
            rotation_occurred=False,
            attempts=1,
            duration_ms=5000,
            model_verified="gemini-2.0-flash",  # Wrong model!
        )

        with patch("agentos.nodes.lld_reviewer.GeminiClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.invoke.return_value = mock_result
            mock_client_class.return_value = mock_client

            with patch("agentos.nodes.lld_reviewer._load_system_instruction") as mock_load:
                mock_load.return_value = "System instruction"

                with patch("agentos.nodes.lld_reviewer.ReviewAuditLog") as mock_log_class:
                    mock_log = MagicMock()
                    mock_log_class.return_value = mock_log

                    result = review_lld_node(mock_state)

        assert result["lld_status"] == "BLOCK"
        assert "Model verification failed" in result["gemini_critique"]
