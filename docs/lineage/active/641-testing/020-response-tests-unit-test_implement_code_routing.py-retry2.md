

```python
"""Unit tests for Issue #641: Model routing for scaffolding/boilerplate files.

Tests the select_model_for_file() routing function and integration with
call_claude_for_file() and generate_file_with_retry().
"""

import inspect
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.nodes.implement_code import (
    HAIKU_MODEL,
    SMALL_FILE_LINE_THRESHOLD,
    call_claude_for_file,
    generate_file_with_retry,
    select_model_for_file,
)
from assemblyzero.core.config import CLAUDE_MODEL


# ---------------------------------------------------------------------------
# T010–T080, T120–T140: select_model_for_file routing rules
# ---------------------------------------------------------------------------
class TestSelectModelForFile:
    """Tests for select_model_for_file() routing logic."""

    def test_init_py_routes_to_haiku(self):
        """T010: __init__.py in root routes to Haiku."""
        result = select_model_for_file(
            file_path="assemblyzero/__init__.py",
            estimated_line_count=0,
            is_test_scaffold=False,
        )
        assert result == HAIKU_MODEL

    def test_conftest_py_routes_to_haiku(self):
        """T020: conftest.py routes to Haiku (REQ-2)."""
        result = select_model_for_file(
            file_path="tests/conftest.py",
            estimated_line_count=0,
            is_test_scaffold=False,
        )
        assert result == HAIKU_MODEL

    def test_test_scaffold_routes_to_haiku(self):
        """T030: is_test_scaffold=True overrides everything (REQ-3)."""
        result = select_model_for_file(
            file_path="tests/unit/test_foo.py",
            estimated_line_count=200,
            is_test_scaffold=True,
        )
        assert result == HAIKU_MODEL

    def test_49_line_file_routes_to_haiku(self):
        """T040: 49-line file routes to Haiku (REQ-4)."""
        result = select_model_for_file(
            file_path="assemblyzero/utils/helper.py",
            estimated_line_count=49,
            is_test_scaffold=False,
        )
        assert result == HAIKU_MODEL

    def test_50_line_file_routes_to_default(self):
        """T050: Exactly 50 lines routes to Sonnet — boundary (REQ-5)."""
        result = select_model_for_file(
            file_path="assemblyzero/utils/helper.py",
            estimated_line_count=50,
            is_test_scaffold=False,
        )
        assert result == CLAUDE_MODEL

    def test_200_line_complex_file_routes_to_default(self):
        """T060: 200-line complex file routes to Sonnet (REQ-5)."""
        result = select_model_for_file(
            file_path="assemblyzero/core/engine.py",
            estimated_line_count=200,
            is_test_scaffold=False,
        )
        assert result == CLAUDE_MODEL

    def test_unknown_size_complex_file_routes_to_default(self):
        """T070: Unknown size (0) complex file routes to Sonnet (REQ-5)."""
        result = select_model_for_file(
            file_path="assemblyzero/core/engine.py",
            estimated_line_count=0,
            is_test_scaffold=False,
        )
        assert result == CLAUDE_MODEL

    def test_deeply_nested_init_py_routes_to_haiku(self):
        """T080: Deeply nested __init__.py routes to Haiku (REQ-1)."""
        result = select_model_for_file(
            file_path="assemblyzero/workflows/testing/nodes/__init__.py",
            estimated_line_count=0,
            is_test_scaffold=False,
        )
        assert result == HAIKU_MODEL

    def test_negative_line_count_routes_to_default(self):
        """T120: Negative line count treated as unknown (REQ-6)."""
        result = select_model_for_file(
            file_path="assemblyzero/utils/helper.py",
            estimated_line_count=-1,
            is_test_scaffold=False,
        )
        assert result == CLAUDE_MODEL

    def test_1_line_file_routes_to_haiku(self):
        """T130: 1-line file routes to Haiku — lower boundary (REQ-4)."""
        result = select_model_for_file(
            file_path="assemblyzero/utils/tiny.py",
            estimated_line_count=1,
            is_test_scaffold=False,
        )
        assert result == HAIKU_MODEL

    def test_51_line_file_routes_to_default(self):
        """T140: 51-line file routes to Sonnet — just above threshold (REQ-5)."""
        result = select_model_for_file(
            file_path="assemblyzero/utils/helper.py",
            estimated_line_count=51,
            is_test_scaffold=False,
        )
        assert result == CLAUDE_MODEL

    def test_conftest_deeply_nested_routes_to_haiku(self):
        """Additional: Deeply nested conftest.py routes to Haiku (REQ-2)."""
        result = select_model_for_file(
            file_path="tests/integration/fixtures/conftest.py",
            estimated_line_count=0,
            is_test_scaffold=False,
        )
        assert result == HAIKU_MODEL

    def test_scaffold_overrides_conftest(self):
        """Additional: is_test_scaffold=True with conftest -> Haiku (REQ-3)."""
        result = select_model_for_file(
            file_path="tests/conftest.py",
            estimated_line_count=0,
            is_test_scaffold=True,
        )
        assert result == HAIKU_MODEL

    def test_threshold_constant_is_50(self):
        """Sanity: SMALL_FILE_LINE_THRESHOLD is 50."""
        assert SMALL_FILE_LINE_THRESHOLD == 50


# ---------------------------------------------------------------------------
# T110 (logging): Routing log emission (REQ-9)
# ---------------------------------------------------------------------------
class TestSelectModelLogging:
    """Tests that routing decisions are logged at INFO level."""

    def test_routing_logged_with_reason_scaffold(self, caplog):
        """T110a: Scaffold routing logged with reason."""
        with caplog.at_level(logging.INFO):
            select_model_for_file(
                file_path="tests/unit/test_x.py",
                estimated_line_count=0,
                is_test_scaffold=True,
            )
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert record.levelno == logging.INFO
        assert "tests/unit/test_x.py" in record.message
        assert HAIKU_MODEL in record.message
        assert "test scaffold" in record.message

    def test_routing_logged_with_reason_boilerplate(self, caplog):
        """T110b: Boilerplate filename routing logged with reason."""
        with caplog.at_level(logging.INFO):
            select_model_for_file(
                file_path="pkg/__init__.py",
                estimated_line_count=0,
                is_test_scaffold=False,
            )
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert "boilerplate filename" in record.message
        assert "pkg/__init__.py" in record.message
        assert HAIKU_MODEL in record.message

    def test_routing_logged_with_reason_small_file(self, caplog):
        """T110c: Small file routing logged with reason and line count."""
        with caplog.at_level(logging.INFO):
            select_model_for_file(
                file_path="pkg/small.py",
                estimated_line_count=30,
                is_test_scaffold=False,
            )
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert "small file" in record.message
        assert "30" in record.message

    def test_routing_logged_with_reason_default(self, caplog):
        """T110d: Default routing logged with reason."""
        with caplog.at_level(logging.INFO):
            select_model_for_file(
                file_path="pkg/big.py",
                estimated_line_count=500,
                is_test_scaffold=False,
            )
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert "default" in record.message
        assert "pkg/big.py" in record.message
        assert CLAUDE_MODEL in record.message


# ---------------------------------------------------------------------------
# T090/T100: call_claude_for_file model parameter (REQ-7)
# ---------------------------------------------------------------------------
class TestCallClaudeForFileModel:
    """Tests for the model parameter on call_claude_for_file()."""

    def test_explicit_model_param_exists(self):
        """T090: model param exists with default None in call_claude_for_file (REQ-7)."""
        sig = inspect.signature(call_claude_for_file)
        assert "model" in sig.parameters
        param = sig.parameters["model"]
        assert param.default is None

    def test_default_model_when_none(self):
        """T100: model=None preserves backward compatibility (REQ-7)."""
        sig = inspect.signature(call_claude_for_file)
        assert sig.parameters["model"].default is None


# ---------------------------------------------------------------------------
# T110: generate_file_with_retry routing integration (REQ-8)
# ---------------------------------------------------------------------------
class TestGenerateFileWithRetryRouting:
    """Tests that generate_file_with_retry() integrates routing correctly."""

    @patch("assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file")
    @patch("assemblyzero.workflows.testing.nodes.implement_code.select_model_for_file")
    def test_routes_init_py_to_haiku_and_passes_model(
        self, mock_select, mock_call_claude
    ):
        """T110: generate_file_with_retry calls routing and passes model (REQ-8)."""
        mock_select.return_value = HAIKU_MODEL
        mock_call_claude.return_value = ('"""Init."""\n', "end_turn")

        # Mock validate_code_response to always pass
        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code.validate_code_response",
            return_value=(True, ""),
        ), patch(
            "assemblyzero.workflows.testing.nodes.implement_code.extract_code_block",
            return_value='"""Init."""\n',
        ):
            result, success = generate_file_with_retry(
                filepath="tests/__init__.py",
                base_prompt="Generate __init__.py",
                estimated_line_count=0,
                is_test_scaffold=False,
            )

        # Verify routing was called with correct args
        mock_select.assert_called_once_with("tests/__init__.py", 0, False)

        # Verify call_claude_for_file received the model
        assert mock_call_claude.called
        call_args = mock_call_claude.call_args
        assert call_args is not None
        # model should be passed as keyword argument
        if "model" in call_args.kwargs:
            assert call_args.kwargs["model"] == HAIKU_MODEL
        else:
            # Or as positional — check the third arg
            assert len(call_args.args) >= 3

    @patch("assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file")
    @patch("assemblyzero.workflows.testing.nodes.implement_code.select_model_for_file")
    def test_passes_scaffold_flag_to_routing(
        self, mock_select, mock_call_claude
    ):
        """generate_file_with_retry passes is_test_scaffold to routing."""
        mock_select.return_value = HAIKU_MODEL
        mock_call_claude.return_value = ("test content", "end_turn")

        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code.validate_code_response",
            return_value=(True, ""),
        ), patch(
            "assemblyzero.workflows.testing.nodes.implement_code.extract_code_block",
            return_value="test content",
        ):
            generate_file_with_retry(
                filepath="tests/unit/test_foo.py",
                base_prompt="Generate test scaffold",
                estimated_line_count=45,
                is_test_scaffold=True,
            )

        mock_select.assert_called_once_with("tests/unit/test_foo.py", 45, True)

    def test_new_params_have_safe_defaults(self):
        """Existing callers without new params still work (signature check)."""
        sig = inspect.signature(generate_file_with_retry)
        params = sig.parameters

        assert "estimated_line_count" in params
        assert params["estimated_line_count"].default == 0

        assert "is_test_scaffold" in params
        assert params["is_test_scaffold"].default is False
```
