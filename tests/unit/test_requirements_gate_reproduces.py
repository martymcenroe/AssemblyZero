"""A requirements conflict halts a roll only when it reproduces (#3747).

On boostgauge #2's body, unedited since 2026-08-16, the requirements gate on
gemini-3.1-pro-high ruled the text consistent at 23:07 (run-issue2-230238) and
found two conflicts at 01:10 (run-issue2-010349), halting the roll and filing
two questions for the operator that the text already answered. The gate now
asks once more before halting, and files only what the second answer repeats.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from assemblyzero.core.llm_provider import LLMCallResult
from assemblyzero.workflows.requirements.nodes.analyze_requirements import (
    REQUIREMENTS_CONFLICT_MARKER,
    analyze_requirements,
)

A1 = "Needle drawing — axis, opacity, visibility, color — is #332's, cited never asserted here."
B1 = "needle presence is detected by classifying sampled pixels against the aesthetic doc's palette rows"
A2 = "the four windows are telltale_windows.short, telltale_windows.medium, telltale_windows.long"
B2 = "identifying the four telltale windows by their aesthetic-doc colors"


def _conflict(a, b):
    return {"criterion_a": a, "criterion_b": b,
            "diverging_situation": "when the palette changes, one reading fails the test"}


def _result(payload):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return LLMCallResult(
        success=True, response=text, raw_response=text, error_message=None,
        provider="fake", model_used="fake-model", duration_ms=1, attempts=1,
    )


CONSISTENT = _result({"is_consistent": True, "conflicts": []})
BOTH = _result({"is_consistent": False, "conflicts": [_conflict(A1, B1), _conflict(A2, B2)]})
ONLY_SECOND = _result({"is_consistent": False, "conflicts": [_conflict(A2, B2)]})
UNPARSEABLE = _result("I think the requirements look mostly fine, but")


class _Provider:
    def __init__(self, *results):
        self._results = list(results)
        self.calls = 0

    def invoke(self, **kwargs):
        self.calls += 1
        return self._results[min(self.calls - 1, len(self._results) - 1)]


@pytest.fixture
def gate(monkeypatch, tmp_path):
    """Run the gate against scripted answers; record what it would file."""
    filed: list[list[dict]] = []
    monkeypatch.setattr("assemblyzero.core.provider_storm.is_storm", lambda: False)
    monkeypatch.setattr(
        "assemblyzero.speedrun.must_resolve.file_all_conflicts",
        lambda repo, issue, conflicts: filed.append(list(conflicts)),
    )
    monkeypatch.setattr(
        "assemblyzero.speedrun.prompt_telemetry.record_failures", lambda *a, **k: None,
    )

    def run(*results):
        provider = _Provider(*results)
        monkeypatch.setattr(
            "assemblyzero.core.llm_provider.get_provider", lambda *a, **k: provider,
        )
        out = analyze_requirements({
            "issue_title": "feat: telltale wiring",
            "issue_body": f"- {A1}\n- {B1}\n- {A2}\n- {B2}\n",
            "issue_number": 2,
            "target_repo": str(tmp_path),
        })
        return out, filed, provider

    return run


def test_a_conflict_that_does_not_reproduce_neither_halts_nor_files(gate, capsys):
    out, filed, provider = gate(BOTH, CONSISTENT)

    assert out == {}
    assert filed == []
    assert provider.calls == 2
    printed = capsys.readouterr().out
    assert printed.count("not reproduced, not filed:") == 2
    assert "no reported conflict reproduced on a second ask" in printed


def test_a_reproduced_conflict_halts_and_files_as_before(gate):
    out, filed, _ = gate(BOTH, BOTH)

    assert out["error_message"].startswith(REQUIREMENTS_CONFLICT_MARKER)
    assert len(filed) == 1 and len(filed[0]) == 2


def test_only_the_reproduced_conflict_is_filed(gate, capsys):
    out, filed, _ = gate(BOTH, ONLY_SECOND)

    assert out["error_message"].startswith(REQUIREMENTS_CONFLICT_MARKER)
    assert [c["criterion_a"] for c in filed[0]] == [A2]
    assert "not reproduced, not filed:" in capsys.readouterr().out


def test_a_confirming_ask_with_no_verdict_halts_on_the_first_answer(gate, capsys):
    """The second ask failed to answer; it did not disagree."""
    out, filed, _ = gate(BOTH, UNPARSEABLE)

    assert out["error_message"].startswith(REQUIREMENTS_CONFLICT_MARKER)
    assert len(filed[0]) == 2
    assert "confirming ask gave no verdict" in capsys.readouterr().out


def test_a_consistent_first_answer_asks_nothing_more(gate):
    out, filed, provider = gate(CONSISTENT)

    assert out == {}
    assert filed == []
    assert provider.calls == 1


@pytest.mark.parametrize(
    "again",
    [
        [_conflict(A1, B1)],                                   # verbatim
        [_conflict(B1, A1)],                                   # order swapped
        [_conflict("Needle drawing — axis, opacity, visibility, color — is #332's", B1.upper())],
        [_conflict(f"  {A1}  ", f"{B1} (V1)")],                # spacing, longer span
    ],
)
def test_the_same_pair_is_recognised_across_quotings(again):
    from assemblyzero.workflows.requirements.nodes.analyze_requirements import (
        _reported_again,
    )

    assert _reported_again(_conflict(A1, B1), again)


def test_a_different_pair_is_not_the_same_conflict():
    from assemblyzero.workflows.requirements.nodes.analyze_requirements import (
        _reported_again,
    )

    assert not _reported_again(_conflict(A1, B1), [_conflict(A1, B2)])
