"""Tests for Issue #309: Implementation workflow retry on validation failure.

These tests verify the retry logic added to implement_code.py:
- Retry on validation errors
- Retry on API errors
- Error context included in retry prompts
- Proper logging of retry attempts
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from assemblyzero.workflows.testing.nodes.implement_code import (
    MAX_FILE_RETRIES,
    build_retry_prompt,
    generate_file_with_retry,
    ImplementationError,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def valid_python_code():
    """Valid Python code that passes validation."""
    return '''"""Module docstring."""

def example_function():
    """Example function."""
    return True

def another_function(x, y):
    """Another function."""
    return x + y
'''


@pytest.fixture
def invalid_python_code():
    """Invalid Python code with syntax error."""
    return '''"""Module with syntax error."""

def broken_function(
    # Missing closing paren and body
'''


@pytest.fixture
def base_prompt():
    """Base prompt for testing."""
    return """# Implementation Request: test_file.py

## Task

Write the complete contents of `test_file.py`.

## Output Format

Output ONLY the file contents in a code block.

```python
# Your implementation here
```
"""


# =============================================================================
# T010: Success on First Attempt
# =============================================================================


class TestSuccessFirstAttempt:
    """Tests for successful first attempt (no retry needed)."""

    def test_success_first_attempt(self, base_prompt, valid_python_code):
        """T010: Code generates and validates on first try."""
        mock_response = f"```python\n{valid_python_code}\n```"

        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file"
        ) as mock_call:
            mock_call.return_value = (mock_response, "")

            code, success = generate_file_with_retry(
                filepath="test_file.py",
                base_prompt=base_prompt,
                audit_dir=None,
                max_retries=3,
            )

            assert success is True
            assert "def example_function" in code
            # Should only call API once
            assert mock_call.call_count == 1


# =============================================================================
# T020: Retry on Validation Error
# =============================================================================


class TestRetryOnValidationError:
    """Tests for retry behavior on validation errors."""

    def test_retry_on_validation_error_succeeds(
        self, base_prompt, invalid_python_code, valid_python_code
    ):
        """T020: Retries when validation fails, succeeds on retry."""
        invalid_response = f"```python\n{invalid_python_code}\n```"
        valid_response = f"```python\n{valid_python_code}\n```"

        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file"
        ) as mock_call:
            # First call returns invalid, second returns valid
            mock_call.side_effect = [
                (invalid_response, ""),
                (valid_response, ""),
            ]

            code, success = generate_file_with_retry(
                filepath="test_file.py",
                base_prompt=base_prompt,
                audit_dir=None,
                max_retries=3,
            )

            assert success is True
            assert "def example_function" in code
            # Should call API twice
            assert mock_call.call_count == 2


# =============================================================================
# T030: Retry on API Error
# =============================================================================


class TestRetryOnApiError:
    """Tests for retry behavior on API errors."""

    def test_retry_on_api_error_succeeds(self, base_prompt, valid_python_code):
        """T030: Retries when API call fails, succeeds on retry."""
        valid_response = f"```python\n{valid_python_code}\n```"

        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file"
        ) as mock_call:
            # First call fails, second succeeds
            mock_call.side_effect = [
                ("", "Connection timeout"),
                (valid_response, ""),
            ]

            code, success = generate_file_with_retry(
                filepath="test_file.py",
                base_prompt=base_prompt,
                audit_dir=None,
                max_retries=3,
            )

            assert success is True
            assert "def example_function" in code
            assert mock_call.call_count == 2


# =============================================================================
# T040: Exhaust Retries on Validation
# =============================================================================


class TestExhaustRetriesValidation:
    """Tests for exhausting retries on validation errors."""

    def test_exhaust_retries_validation(self, base_prompt, invalid_python_code):
        """T040: Raises ImplementationError after 3 failed validations."""
        invalid_response = f"```python\n{invalid_python_code}\n```"

        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file"
        ) as mock_call:
            # All calls return invalid code
            mock_call.return_value = (invalid_response, "")

            with pytest.raises(ImplementationError) as exc_info:
                generate_file_with_retry(
                    filepath="test_file.py",
                    base_prompt=base_prompt,
                    audit_dir=None,
                    max_retries=3,
                )

            assert "Validation failed after 3 attempts" in str(exc_info.value)
            assert mock_call.call_count == 3


# =============================================================================
# T050: Exhaust Retries on API Error
# =============================================================================


class TestExhaustRetriesApi:
    """Tests for exhausting retries on API errors."""

    def test_exhaust_retries_api(self, base_prompt):
        """T050: Raises ImplementationError after 3 API failures."""
        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file"
        ) as mock_call:
            # All calls fail with API error
            mock_call.return_value = ("", "Service unavailable")

            with pytest.raises(ImplementationError) as exc_info:
                generate_file_with_retry(
                    filepath="test_file.py",
                    base_prompt=base_prompt,
                    audit_dir=None,
                    max_retries=3,
                )

            assert "API error after 3 attempts" in str(exc_info.value)
            assert mock_call.call_count == 3


# =============================================================================
# T060: Error Context in Retry Prompt
# =============================================================================


class TestErrorContextInRetryPrompt:
    """Tests for error context being included in retry prompts."""

    def test_error_included_in_retry_prompt(self, base_prompt):
        """T060: Validation error appears in retry prompt."""
        validation_error = "Python syntax error: unexpected EOF"

        retry_prompt = build_retry_prompt(
            base_prompt=base_prompt,
            validation_error=validation_error,
            attempt=2,
        )

        # Error message should be in the prompt
        assert validation_error in retry_prompt
        # Attempt number should be indicated
        assert "Attempt 2" in retry_prompt
        # Should still have the output format section
        assert "## Output Format" in retry_prompt

    def test_retry_prompt_preserves_original_content(self, base_prompt):
        """Retry prompt preserves original prompt content."""
        retry_prompt = build_retry_prompt(
            base_prompt=base_prompt,
            validation_error="Some error",
            attempt=1,
        )

        # Original content should still be present
        assert "Implementation Request" in retry_prompt
        assert "test_file.py" in retry_prompt


# =============================================================================
# T070: Retry Logging Format
# =============================================================================


class TestRetryLogging:
    """Tests for retry logging format."""

    def test_logging_on_retry(self, base_prompt, invalid_python_code, valid_python_code, capsys):
        """T070: Retry attempts are logged with attempt number."""
        invalid_response = f"```python\n{invalid_python_code}\n```"
        valid_response = f"```python\n{valid_python_code}\n```"

        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file"
        ) as mock_call:
            mock_call.side_effect = [
                (invalid_response, ""),
                (valid_response, ""),
            ]

            generate_file_with_retry(
                filepath="test_file.py",
                base_prompt=base_prompt,
                audit_dir=None,
                max_retries=3,
            )

            captured = capsys.readouterr()
            # Should log retry attempt
            assert "[RETRY" in captured.out
            # Should log success after retry
            assert "[SUCCESS]" in captured.out


# =============================================================================
# Additional Edge Cases
# =============================================================================


class TestEdgeCases:
    """Additional edge case tests."""

    def test_max_file_retries_constant(self):
        """MAX_FILE_RETRIES constant is set correctly."""
        assert MAX_FILE_RETRIES == 3

    def test_no_code_block_triggers_retry(self, base_prompt, valid_python_code):
        """Missing code block triggers retry."""
        no_code_response = "Here is the implementation summary..."
        valid_response = f"```python\n{valid_python_code}\n```"

        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file"
        ) as mock_call:
            mock_call.side_effect = [
                (no_code_response, ""),
                (valid_response, ""),
            ]

            code, success = generate_file_with_retry(
                filepath="test_file.py",
                base_prompt=base_prompt,
                audit_dir=None,
                max_retries=3,
            )

            assert success is True
            assert mock_call.call_count == 2

    def test_summary_response_triggers_retry(self, base_prompt, valid_python_code):
        """Summary response (no code) triggers retry."""
        summary_response = "I've created the implementation with the following features..."
        valid_response = f"```python\n{valid_python_code}\n```"

        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file"
        ) as mock_call:
            mock_call.side_effect = [
                (summary_response, ""),
                (valid_response, ""),
            ]

            code, success = generate_file_with_retry(
                filepath="test_file.py",
                base_prompt=base_prompt,
                audit_dir=None,
                max_retries=3,
            )

            assert success is True
            assert mock_call.call_count == 2

    def test_audit_dir_none_doesnt_crash(self, base_prompt, valid_python_code):
        """None audit_dir doesn't cause errors."""
        valid_response = f"```python\n{valid_python_code}\n```"

        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file"
        ) as mock_call:
            mock_call.return_value = (valid_response, "")

            # Should not raise
            code, success = generate_file_with_retry(
                filepath="test_file.py",
                base_prompt=base_prompt,
                audit_dir=None,
            )

            assert success is True
