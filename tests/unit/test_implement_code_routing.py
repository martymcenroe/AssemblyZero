"""Unit tests for the coder's routing (Issue #641; seats since #3553/#3563).

The routing picks a SEAT: ``impl.code.small`` for scaffolds, ``__init__.py``,
``conftest.py`` and files under fifty lines, ``impl.code`` otherwise. Which
model answers each seat is the run profile's decision: Gemini in both under
``gemini.toml`` (the default, ADR 0234), and Sonnet/Haiku under ``claude.toml``,
which reproduces the pre-law routing exactly.
"""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core.seats import builtin_path, load_profile, using_profile
from assemblyzero.workflows.testing.nodes.implementation.routing import (
    CODE_SEAT,
    SMALL_FILE_LINE_THRESHOLD,
    SMALL_SEAT,
    select_model_for_file,
    select_seat_for_file,
)

ROUTING_LOGGER = "assemblyzero.workflows.testing.nodes.implementation.routing"


@pytest.fixture(autouse=True)
def _no_profile_from_the_environment(monkeypatch):
    """The active profile must come from the test, never the machine."""
    monkeypatch.delenv("AZ_MODEL_PROFILE", raising=False)


def _profile(name: str) -> dict:
    return load_profile(builtin_path(name))


# ---------------------------------------------------------------------------
# The routing rules pick a seat
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path, lines, scaffold, seat",
    [
        ("assemblyzero/__init__.py", 0, False, SMALL_SEAT),  # T010
        ("tests/conftest.py", 0, False, SMALL_SEAT),  # T020
        ("tests/unit/test_foo.py", 200, True, SMALL_SEAT),  # T030: scaffold wins
        ("assemblyzero/utils/helper.py", 49, False, SMALL_SEAT),  # T040
        ("assemblyzero/utils/helper.py", 50, False, CODE_SEAT),  # T050: < 50
        ("assemblyzero/core/engine.py", 0, False, CODE_SEAT),  # T060: unknown
        ("assemblyzero/workflows/testing/nodes/__init__.py", 0, False, SMALL_SEAT),  # T070
        ("assemblyzero/core/engine.py", -1, False, CODE_SEAT),  # T120
        ("assemblyzero/utils/tiny.py", 1, False, SMALL_SEAT),  # T130
        ("assemblyzero/utils/medium.py", 51, False, CODE_SEAT),  # T140
        ("tests/conftest.py", 0, True, SMALL_SEAT),
        ("assemblyzero/core/engine.py", 200, False, CODE_SEAT),
    ],
)
def test_routing_picks_the_seat(path, lines, scaffold, seat):
    assert select_seat_for_file(path, lines, scaffold) == seat


def test_type_error_on_non_string_path():
    with pytest.raises(TypeError, match="file_path must be a str"):
        select_seat_for_file(file_path=123)


def test_type_error_on_path_object():
    from pathlib import Path

    with pytest.raises(TypeError, match="file_path must be a str"):
        select_seat_for_file(file_path=Path("assemblyzero/__init__.py"))


def test_small_file_threshold_constant():
    assert SMALL_FILE_LINE_THRESHOLD == 50


# ---------------------------------------------------------------------------
# The profile decides the model (#3553)
# ---------------------------------------------------------------------------


def test_the_default_profile_puts_the_coder_on_gemini():
    """The operator's ruling of 2026-09-24: the coder moves to Gemini too."""
    with using_profile(_profile("gemini")):
        assert select_model_for_file("assemblyzero/core/engine.py", 200) == "gemini:3.1-pro"
        assert select_model_for_file("assemblyzero/__init__.py") == "gemini:3.1-pro"


def test_no_profile_in_hand_means_the_built_in_default():
    """Outside a node, the precedence falls to gemini.toml, never to Claude."""
    assert select_model_for_file("assemblyzero/core/engine.py", 200) == "gemini:3.1-pro"
    assert select_model_for_file("assemblyzero/__init__.py") == "gemini:3.1-pro"


def test_the_claude_profile_reproduces_the_pre_law_split():
    with using_profile(_profile("claude")):
        assert select_model_for_file("assemblyzero/core/engine.py", 200) == "claude:sonnet"
        assert select_model_for_file("assemblyzero/__init__.py") == "claude:haiku"


# ---------------------------------------------------------------------------
# call_claude_for_file resolves the seat it is handed
# ---------------------------------------------------------------------------


def _fake_provider(text="generated content"):
    provider = MagicMock()
    provider.invoke.return_value = SimpleNamespace(
        success=True, response=text, error_message=None, retryable=False
    )
    return provider


def test_the_seat_reaches_the_provider_spec():
    """T080 (#3490's seam): the resolved seat's spec is what get_provider gets."""
    from assemblyzero.workflows.testing.nodes.implementation import claude_client

    with using_profile(_profile("claude")), patch.object(
        claude_client, "get_provider", return_value=_fake_provider()
    ) as mock_get_provider:
        response, error = claude_client.call_claude_for_file("prompt text", seat=SMALL_SEAT)

    assert mock_get_provider.call_args.args[0] == "claude:haiku"
    assert response == "generated content"
    assert error == ""


def test_no_seat_means_impl_code_under_the_profile():
    """The other half: no seat and no model is `impl.code`, never a Claude default."""
    from assemblyzero.workflows.testing.nodes.implementation import claude_client

    with using_profile(_profile("gemini")), patch.object(
        claude_client, "get_provider", return_value=_fake_provider("x")
    ) as mock_get_provider:
        claude_client.call_claude_for_file("prompt text")

    assert mock_get_provider.call_args.args[0] == "gemini:3.1-pro"


def test_an_explicit_spec_wins_over_the_seat():
    from assemblyzero.workflows.testing.nodes.implementation import claude_client

    with using_profile(_profile("gemini")), patch.object(
        claude_client, "get_provider", return_value=_fake_provider()
    ) as mock_get_provider:
        claude_client.call_claude_for_file("prompt", model="claude:opus", seat=SMALL_SEAT)

    assert mock_get_provider.call_args.args[0] == "claude:opus"


def test_a_bare_model_id_is_refused():
    """The coder never falls to `claude:<id>` by string concatenation again."""
    from assemblyzero.workflows.testing.nodes.implementation import claude_client

    with patch.object(claude_client, "get_provider") as mock_get_provider:
        response, error = claude_client.call_claude_for_file(
            "prompt", model="claude-haiku-4-5-20251001"
        )

    mock_get_provider.assert_not_called()
    assert response == ""
    assert error.startswith("[NON-RETRYABLE]") and "not a provider spec" in error


def test_the_seat_effort_rides_along_unless_given():
    from assemblyzero.workflows.testing.nodes.implementation import claude_client

    with using_profile(_profile("claude")), patch.object(
        claude_client, "get_provider", return_value=_fake_provider()
    ) as mock_get_provider:
        claude_client.call_claude_for_file("prompt", seat=CODE_SEAT)
        seat_effort = mock_get_provider.call_args.kwargs["effort"]
        claude_client.call_claude_for_file("prompt", seat=CODE_SEAT, effort="low")
        given_effort = mock_get_provider.call_args.kwargs["effort"]

    assert seat_effort == "max"
    assert given_effort == "low"


# ---------------------------------------------------------------------------
# The orchestrator hands the routed seat on (REQ-8)
# ---------------------------------------------------------------------------


def test_generate_file_with_retry_passes_the_routed_seat():
    """T100: generate_file_with_retry routes, then passes the seat to the call."""
    base = "assemblyzero.workflows.testing.nodes.implementation.orchestrator"
    with patch(f"{base}.call_claude_for_file") as mock_call, patch(
        f"{base}.select_seat_for_file", return_value=SMALL_SEAT,
    ) as mock_route, patch(f"{base}.validate_code_response", return_value=True), patch(
        f"{base}.extract_code_block", return_value='"""Tests package."""\n',
    ), patch(f"{base}.detect_summary_response", return_value=False), patch(
        f"{base}.save_audit_file",
    ), patch(f"{base}.emit"):
        mock_call.return_value = ("'\"\"\"Tests package.\"\"\"\\n'", {"input_tokens": 10})

        from assemblyzero.workflows.testing.nodes.implementation.orchestrator import (
            generate_file_with_retry,
        )

        generate_file_with_retry(
            filepath="tests/__init__.py",
            base_prompt="generate init",
            estimated_line_count=5,
        )
        mock_route.assert_called_once_with("tests/__init__.py", 5, False)
        mock_call.assert_called_once()
        assert mock_call.call_args.kwargs.get("seat") == SMALL_SEAT


def test_the_n4_node_enters_the_run_profile():
    """N4 makes the run's snapshot the active profile for everything it calls."""
    from assemblyzero.core.seats import active_profile
    from assemblyzero.workflows.testing.nodes.implementation import orchestrator

    seen = {}

    def body(state):
        seen["name"] = active_profile()["name"]
        return {}

    with patch.object(orchestrator, "implement_code", side_effect=body):
        orchestrator.implement_code_under_profile({"model_profile": _profile("claude")})

    assert seen["name"] == "claude"


# ---------------------------------------------------------------------------
# Routing log emission (REQ-9)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path, lines, scaffold, reason",
    [
        ("assemblyzero/__init__.py", 0, False, "boilerplate_filename"),
        ("tests/unit/test_foo.py", 0, True, "test_scaffold"),
        ("assemblyzero/utils/tiny.py", 10, False, "small_file, lines=10"),
        ("assemblyzero/core/engine.py", 200, False, "default"),
    ],
)
def test_routing_logs_the_seat_and_reason(caplog, path, lines, scaffold, reason):
    with caplog.at_level(logging.INFO, logger=ROUTING_LOGGER):
        seat = select_seat_for_file(path, lines, scaffold)

    records = [r for r in caplog.records if r.name == ROUTING_LOGGER]
    assert len(records) == 1
    assert path in records[0].message
    assert seat in records[0].message
    assert reason in records[0].message
