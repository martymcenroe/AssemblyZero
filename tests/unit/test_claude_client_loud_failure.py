"""claude_client.py under standard 0034 (ADR 0236), the #3585 sweep.

A timeout override that is not a positive whole number used to be replaced by
the default with a stdout line; it now raises, naming the variable and the
value, so a typo stops the run instead of quietly running on a limit nobody
chose. A provider that raises is an ERROR line naming the exception's type,
the seat and the file. Test names carry ledger 0908's line numbers at its
base ``79e18ad1``. No test reaches a model: the provider gate is replaced.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from assemblyzero.workflows.testing.nodes.implementation import claude_client


def _loud(err: str, *needles: str) -> bool:
    return any(
        line.startswith("ERROR") and all(n in line for n in needles)
        for line in err.splitlines()
    )


@pytest.fixture
def seat(monkeypatch):
    """A resolved seat, without reading a profile."""
    monkeypatch.setattr(
        claude_client, "resolve_active",
        lambda name: SimpleNamespace(spec="claude:sonnet", effort=None, name=name),
    )


class TestTimeoutOverrides:
    def test_61_an_override_that_is_not_an_integer_raises(self, monkeypatch, capsys):
        monkeypatch.setenv(claude_client.ENV_TIMEOUT_FLOOR, "ten")

        with pytest.raises(ValueError, match=claude_client.ENV_TIMEOUT_FLOOR):
            claude_client.compute_dynamic_timeout("prompt")

        assert _loud(capsys.readouterr().err, claude_client.ENV_TIMEOUT_FLOOR, "'ten'")

    def test_64_an_override_that_is_not_positive_raises(self, monkeypatch, capsys):
        monkeypatch.setenv(claude_client.ENV_TIMEOUT_CAP, "0")

        with pytest.raises(ValueError, match=claude_client.ENV_TIMEOUT_CAP):
            claude_client.compute_dynamic_timeout("prompt")

        assert _loud(capsys.readouterr().err, claude_client.ENV_TIMEOUT_CAP, "not positive")

    def test_a_valid_override_and_no_override_still_work(self, monkeypatch):
        """Kept: an unset variable is the default; a positive one is used."""
        monkeypatch.delenv(claude_client.ENV_TIMEOUT_FLOOR, raising=False)
        monkeypatch.delenv(claude_client.ENV_TIMEOUT_CAP, raising=False)
        assert claude_client.compute_dynamic_timeout("") == claude_client.FILE_TIMEOUT_FLOOR
        monkeypatch.setenv(claude_client.ENV_TIMEOUT_FLOOR, "100")
        monkeypatch.setenv(claude_client.ENV_TIMEOUT_CAP, "100")
        assert claude_client.compute_dynamic_timeout("") == 100


class TestTheProviderGate:
    def test_250_a_model_that_is_not_a_provider_spec_is_refused(self, seat, monkeypatch):
        """Kept, compliant: a non-retryable error the retry loop raises on."""
        def refuse(*_a, **_k):
            raise AssertionError("the provider gate must not be reached")

        monkeypatch.setattr(claude_client, "get_provider", refuse)

        response, error = claude_client.call_claude_for_file("p", model="haiku")

        assert response == ""
        assert error.startswith("[NON-RETRYABLE]")

    def test_270_a_provider_that_raises_is_an_error_line(self, seat, monkeypatch, capsys):
        def broken(*_a, **_k):
            raise RuntimeError("transport crashed")

        monkeypatch.setattr(claude_client, "get_provider", broken)

        response, error = claude_client.call_claude_for_file(
            "p", file_path="src/pkg/widget.py", seat="impl.code",
        )

        assert response == ""
        assert "RuntimeError" in error and "transport crashed" in error
        assert _loud(
            capsys.readouterr().err, "RuntimeError", "impl.code", "src/pkg/widget.py",
        )
