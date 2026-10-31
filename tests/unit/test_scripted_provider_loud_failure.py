"""scripted_provider.py under standard 0034, one test per sweep site (#3792).

The scripted provider answers mock rolls and replays from committed fixtures.
A script that cannot answer is a failed run, never a quiet default answer. A
rule with no response, no fixture and no scripted failure used to answer ""
as a success; it now raises naming its stage. A call no rule answers was
already a failed result, which the caller routes to HALT; it is now also an
ERROR line on stderr and in the log at the point it happens. Line numbers in
the names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import pytest

from assemblyzero.core.scripted_provider import ScriptedProvider, ScriptedRule


def test_136_a_rule_with_nothing_to_answer_raises():
    provider = ScriptedProvider([ScriptedRule("drafter", system_pattern="draft")])

    with pytest.raises(ValueError, match="'drafter'") as raised:
        provider.invoke("You draft the LLD", "issue 42")
    assert "no response" in str(raised.value)


def test_an_explicit_empty_response_is_still_scripted():
    """Kept: response="" is an answer the script wrote down (a recorded empty
    reply replays as one), not a missing one."""
    provider = ScriptedProvider([ScriptedRule("drafter", response="")])
    result = provider.invoke("You draft the LLD", "issue 42")
    assert result.success is True
    assert result.response == ""


class TestAnUnansweredCallIsLoud:
    def test_241_an_unmatched_call_is_an_error_line_and_a_failed_result(
        self, capsys, caplog
    ):
        provider = ScriptedProvider([ScriptedRule("drafter", system_pattern="draft", response="x")])

        result = provider.invoke("You review the spec", "issue 42")

        assert result.success is False
        assert "matched no rule" in result.error_message
        err = capsys.readouterr().err
        assert "ERROR [SCRIPTED]" in err
        assert "matched no rule" in err
        assert any(r.levelname == "ERROR" for r in caplog.records)

    def test_241_a_call_past_the_scripted_rounds_is_an_error_line(self, capsys):
        provider = ScriptedProvider(
            [ScriptedRule("reviewer", system_pattern="review", response="ok", on_call=1)]
        )
        provider.invoke("You review", "round 1")
        capsys.readouterr()

        result = provider.invoke("You review", "round 2")

        assert result.success is False
        assert "ERROR [SCRIPTED]" in capsys.readouterr().err

    def test_a_scripted_failure_is_not_an_error_line(self, capsys):
        """Kept: fail_with is the script answering with a failure on purpose
        (ledger line 260, compliant); the halt it drives is the loud part."""
        provider = ScriptedProvider([ScriptedRule("drafter", fail_with="429 quota")])

        result = provider.invoke("You draft", "issue 42")

        assert result.success is False
        assert result.error_message == "429 quota"
        assert "ERROR" not in capsys.readouterr().err
