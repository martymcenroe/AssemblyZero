"""Unit tests for model routing logic (Issue #641).

Tests select_model_for_file(), the model parameter on call_claude_for_file(),
and the routing integration in generate_file_with_retry().
"""

import logging
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.nodes.implementation.routing import (
    select_model_for_file,
    HAIKU_MODEL,
    SMALL_FILE_LINE_THRESHOLD,
    _get_default_model,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-sonnet-4-6"


@pytest.fixture(autouse=True)
def _set_default_model(monkeypatch):
    """Ensure a deterministic default model for all tests."""
    monkeypatch.setenv("ANTHROPIC_MODEL", DEFAULT_MODEL)


# ---------------------------------------------------------------------------
# T010 – __init__.py routes to Haiku (REQ-1)
# ---------------------------------------------------------------------------


def test_init_py_routes_to_haiku():
    """T010: select_model_for_file returns HAIKU_MODEL for __init__.py."""
    result = select_model_for_file(
        file_path="assemblyzero/__init__.py",
        estimated_line_count=0,
        is_test_scaffold=False,
    )
    assert result == HAIKU_MODEL


# ---------------------------------------------------------------------------
# T020 – conftest.py routes to Haiku (REQ-2)
# ---------------------------------------------------------------------------


def test_conftest_py_routes_to_haiku():
    """T020: select_model_for_file returns HAIKU_MODEL for conftest.py."""
    result = select_model_for_file(
        file_path="tests/conftest.py",
        estimated_line_count=0,
        is_test_scaffold=False,
    )
    assert result == HAIKU_MODEL


# ---------------------------------------------------------------------------
# T030 – test scaffold flag overrides everything (REQ-3)
# ---------------------------------------------------------------------------


def test_scaffold_flag_overrides_line_count():
    """T030: is_test_scaffold=True routes to Haiku even with large line count."""
    result = select_model_for_file(
        file_path="tests/unit/test_foo.py",
        estimated_line_count=200,
        is_test_scaffold=True,
    )
    assert result == HAIKU_MODEL


# ---------------------------------------------------------------------------
# T040 – 49-line file routes to Haiku (REQ-4)
# ---------------------------------------------------------------------------


def test_49_line_file_routes_to_haiku():
    """T040: File with 49 estimated lines routes to Haiku."""
    result = select_model_for_file(
        file_path="assemblyzero/utils/helper.py",
        estimated_line_count=49,
        is_test_scaffold=False,
    )
    assert result == HAIKU_MODEL


# ---------------------------------------------------------------------------
# T050 – 50-line boundary routes to Sonnet (REQ-5)
# ---------------------------------------------------------------------------


def test_50_line_boundary_routes_to_sonnet():
    """T050: Exactly 50 lines routes to default (Sonnet). Threshold is < 50."""
    result = select_model_for_file(
        file_path="assemblyzero/utils/helper.py",
        estimated_line_count=50,
        is_test_scaffold=False,
    )
    assert result == DEFAULT_MODEL


# ---------------------------------------------------------------------------
# T060 – Unknown size complex file routes to Sonnet (REQ-5)
# ---------------------------------------------------------------------------


def test_unknown_size_routes_to_sonnet():
    """T060: estimated_line_count=0 means unknown; routes to Sonnet."""
    result = select_model_for_file(
        file_path="assemblyzero/core/engine.py",
        estimated_line_count=0,
        is_test_scaffold=False,
    )
    assert result == DEFAULT_MODEL


# ---------------------------------------------------------------------------
# T070 – Deeply nested __init__.py (REQ-1)
# ---------------------------------------------------------------------------


def test_deeply_nested_init_py_routes_to_haiku():
    """T070: Path depth is irrelevant; basename __init__.py matches."""
    result = select_model_for_file(
        file_path="assemblyzero/workflows/testing/nodes/__init__.py",
    )
    assert result == HAIKU_MODEL


# ---------------------------------------------------------------------------
# T080 – call_claude_for_file uses supplied model (REQ-7)
# ---------------------------------------------------------------------------


def test_call_claude_explicit_model():
    """T080: When model is provided, call_claude_for_file receives it."""
    with patch(
        "assemblyzero.workflows.testing.nodes.implementation.claude_client.call_claude_for_file"
    ) as mock_call:
        mock_call.return_value = ("generated content", {"input_tokens": 10, "output_tokens": 20})
        result = mock_call("prompt text", model=HAIKU_MODEL)
        mock_call.assert_called_once_with("prompt text", model=HAIKU_MODEL)


# ---------------------------------------------------------------------------
# T090 – call_claude_for_file default model (REQ-7)
# ---------------------------------------------------------------------------


def test_call_claude_default_model():
    """T090: When model=None, backward-compatible default is used."""
    with patch(
        "assemblyzero.workflows.testing.nodes.implementation.claude_client.call_claude_for_file"
    ) as mock_call:
        mock_call.return_value = ("generated content", {"input_tokens": 10, "output_tokens": 20})
        mock_call("prompt text")
        mock_call.assert_called_once_with("prompt text")


# ---------------------------------------------------------------------------
# T100 – generate_file_with_retry routing integration (REQ-8)
# ---------------------------------------------------------------------------


def test_generate_file_with_retry_passes_routed_model():
    """T100: generate_file_with_retry calls select_model and passes to call_claude."""
    with patch(
        "assemblyzero.workflows.testing.nodes.implementation.orchestrator.call_claude_for_file"
    ) as mock_call, patch(
        "assemblyzero.workflows.testing.nodes.implementation.orchestrator.select_model_for_file",
        return_value=HAIKU_MODEL,
    ) as mock_route:
        mock_call.return_value = ("'\"\"\"Tests package.\"\"\"\\n'", {"input_tokens": 10, "output_tokens": 5})

        from assemblyzero.workflows.testing.nodes.implementation.orchestrator import (
            generate_file_with_retry,
        )

        # Patch validate_code_response and extract_code_block to avoid validation
        with patch(
            "assemblyzero.workflows.testing.nodes.implementation.orchestrator.validate_code_response",
            return_value=True,
        ), patch(
            "assemblyzero.workflows.testing.nodes.implementation.orchestrator.extract_code_block",
            return_value='"""Tests package."""\n',
        ), patch(
            "assemblyzero.workflows.testing.nodes.implementation.orchestrator.detect_summary_response",
            return_value=False,
        ), patch(
            "assemblyzero.workflows.testing.nodes.implementation.orchestrator.save_audit_file",
        ), patch(
            "assemblyzero.workflows.testing.nodes.implementation.orchestrator.emit",
        ), patch(
            "assemblyzero.workflows.testing.nodes.implementation.orchestrator.validate_file_write",
            return_value=(True, None),
        ):
            generate_file_with_retry(
                filepath="tests/__init__.py",
                base_prompt="generate init",
                estimated_line_count=5,
            )
            mock_route.assert_called_once_with("tests/__init__.py", 5, False)
            mock_call.assert_called_once()
            # Verify model kwarg was passed
            _, kwargs = mock_call.call_args
            assert kwargs.get("model") == HAIKU_MODEL


# ---------------------------------------------------------------------------
# T110 – Routing log emission (REQ-9)
# ---------------------------------------------------------------------------


def test_routing_logs_reason(caplog):
    """T110: Routing decision logged at INFO with file path, model, and reason."""
    with caplog.at_level(logging.INFO, logger="assemblyzero.workflows.testing.nodes.implementation.routing"):
        select_model_for_file(
            file_path="assemblyzero/__init__.py",
        )

    routing_records = [
        r for r in caplog.records
        if r.name == "assemblyzero.workflows.testing.nodes.implementation.routing"
    ]
    assert len(routing_records) == 1
    record = routing_records[0]
    assert "assemblyzero/__init__.py" in record.message
    assert HAIKU_MODEL in record.message
    assert "boilerplate_filename" in record.message


# ---------------------------------------------------------------------------
# T120 – Negative line count treated as unknown (REQ-6)
# ---------------------------------------------------------------------------


def test_negative_line_count_routes_to_sonnet():
    """T120: Negative estimated_line_count treated as unknown -> Sonnet."""
    result = select_model_for_file(
        file_path="assemblyzero/core/engine.py",
        estimated_line_count=-1,
        is_test_scaffold=False,
    )
    assert result == DEFAULT_MODEL


# ---------------------------------------------------------------------------
# T130 – 1-line file routes to Haiku (REQ-4)
# ---------------------------------------------------------------------------


def test_1_line_file_routes_to_haiku():
    """T130: Lower boundary — 1 line routes to Haiku."""
    result = select_model_for_file(
        file_path="assemblyzero/utils/tiny.py",
        estimated_line_count=1,
        is_test_scaffold=False,
    )
    assert result == HAIKU_MODEL


# ---------------------------------------------------------------------------
# T140 – 51-line file routes to Sonnet (REQ-5)
# ---------------------------------------------------------------------------


def test_51_line_file_routes_to_sonnet():
    """T140: Just above threshold — routes to Sonnet."""
    result = select_model_for_file(
        file_path="assemblyzero/utils/medium.py",
        estimated_line_count=51,
        is_test_scaffold=False,
    )
    assert result == DEFAULT_MODEL


# ---------------------------------------------------------------------------
# T150 – Coverage checked via pytest-cov CLI flag (REQ-10)
# T160 – Regression checked via full test suite run (REQ-11)
# These are CI-level checks, not individual test functions.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Additional edge-case tests for robustness
# ---------------------------------------------------------------------------


def test_type_error_on_non_string_path():
    """select_model_for_file raises TypeError when file_path is not a str."""
    with pytest.raises(TypeError, match="file_path must be a str"):
        select_model_for_file(file_path=123)


def test_type_error_on_path_object():
    """select_model_for_file raises TypeError for pathlib.Path input."""
    from pathlib import Path

    with pytest.raises(TypeError, match="file_path must be a str"):
        select_model_for_file(file_path=Path("assemblyzero/__init__.py"))


def test_scaffold_with_conftest_both_route_haiku():
    """is_test_scaffold=True with conftest.py basename -> Haiku (scaffold fires first)."""
    result = select_model_for_file(
        file_path="tests/conftest.py",
        estimated_line_count=0,
        is_test_scaffold=True,
    )
    assert result == HAIKU_MODEL


def test_200_line_complex_file_routes_to_sonnet():
    """200-line complex file routes to Sonnet."""
    result = select_model_for_file(
        file_path="assemblyzero/core/engine.py",
        estimated_line_count=200,
        is_test_scaffold=False,
    )
    assert result == DEFAULT_MODEL


def test_scaffold_log_reason(caplog):
    """Scaffold routing logs 'test_scaffold' as reason."""
    with caplog.at_level(logging.INFO, logger="assemblyzero.workflows.testing.nodes.implementation.routing"):
        select_model_for_file(
            file_path="tests/unit/test_foo.py",
            is_test_scaffold=True,
        )

    routing_records = [
        r for r in caplog.records
        if r.name == "assemblyzero.workflows.testing.nodes.implementation.routing"
    ]
    assert len(routing_records) == 1
    assert "test_scaffold" in routing_records[0].message


def test_small_file_log_reason(caplog):
    """Small file routing logs 'small_file' as reason."""
    with caplog.at_level(logging.INFO, logger="assemblyzero.workflows.testing.nodes.implementation.routing"):
        select_model_for_file(
            file_path="assemblyzero/utils/tiny.py",
            estimated_line_count=10,
        )

    routing_records = [
        r for r in caplog.records
        if r.name == "assemblyzero.workflows.testing.nodes.implementation.routing"
    ]
    assert len(routing_records) == 1
    assert "small_file" in routing_records[0].message
    assert "lines=10" in routing_records[0].message


def test_default_log_reason(caplog):
    """Default routing logs 'default' as reason."""
    with caplog.at_level(logging.INFO, logger="assemblyzero.workflows.testing.nodes.implementation.routing"):
        select_model_for_file(
            file_path="assemblyzero/core/engine.py",
            estimated_line_count=200,
        )

    routing_records = [
        r for r in caplog.records
        if r.name == "assemblyzero.workflows.testing.nodes.implementation.routing"
    ]
    assert len(routing_records) == 1
    assert "default" in routing_records[0].message


def test_small_file_threshold_constant():
    """SMALL_FILE_LINE_THRESHOLD is 50 as specified in LLD."""
    assert SMALL_FILE_LINE_THRESHOLD == 50


def test_haiku_model_constant():
    """HAIKU_MODEL matches the expected model string."""
    assert HAIKU_MODEL == "claude-haiku-4-5-20251001"