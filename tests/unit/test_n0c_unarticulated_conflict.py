"""A conflict the gate could not articulate is never filed as a question (#2462).

boostgauge #344 was filed with a divergence condition of `?` -- a
launch-blocking must-resolve that no ruling could address, because the
must-resolve contract ("edit the issue so only one reading survives")
presupposes the filing names where the two readings part.

The `?` was this pipeline's own renderer default showing through a missing
field, so the reconstruction below is tested BOTH ways: with the key absent
(what the model most likely returned) and with a literal `?` (what the issue
body shows). Neither may be filed, and neither may be dropped silently.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from assemblyzero.core.llm_provider import LLMCallResult  # noqa: E402
from assemblyzero.speedrun.must_resolve import (  # noqa: E402
    build_body,
    conflict_from_rationale,
    file_must_resolve,
    unanswerable_reason,
)
from assemblyzero.workflows.requirements.nodes.analyze_requirements import (  # noqa: E402
    REQUIREMENTS_CONFLICT_MARKER,
    analyze_requirements,
)

# The #344 conflict block, verbatim from the issue body.
A_344 = (
    "alpha at distance 2 reads fully opaque; at 2.5 midway within +/-10; "
    "at 3 baseline"
)
B_344 = "additive bloom on the body"

#: What the issue body renders -- the placeholder made it into the text.
ISSUE_344_AS_RENDERED = {
    "criterion_a": A_344,
    "criterion_b": B_344,
    "diverging_situation": "?",
}

#: What the model most likely returned -- the field simply absent, with the
#: `?` supplied by the renderer's own default.
ISSUE_344_AS_RETURNED = {"criterion_a": A_344, "criterion_b": B_344}

GOOD = {
    "criterion_a": "floor = highest value still in the window",
    "criterion_b": "floor drifts toward the most recent value",
    "diverging_situation": "when the window maximum is not the latest sample",
}


class FakeGh:
    """Records every command instead of running it."""

    def __init__(self, listing: str = "[]") -> None:
        self.calls: list[list[str]] = []
        self.listing = listing

    def __call__(self, args):
        self.calls.append(list(args))
        if args[0] == "git":
            return subprocess.CompletedProcess(
                args, 0, "https://github.com/martymcenroe/boostgauge.git", ""
            )
        if "list" in args:
            return subprocess.CompletedProcess(args, 0, self.listing, "")
        if "create" in args:
            return subprocess.CompletedProcess(
                args, 0, "https://github.com/martymcenroe/boostgauge/issues/999", ""
            )
        return subprocess.CompletedProcess(args, 0, "", "")

    @property
    def created(self) -> list[list[str]]:
        return [c for c in self.calls if "issue" in c and "create" in c]


# ---------------------------------------------------------------------------
# The predicate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "conflict",
    [ISSUE_344_AS_RENDERED, ISSUE_344_AS_RETURNED],
    ids=["as-rendered", "as-returned"],
)
def test_the_344_payload_is_rejected(conflict):
    reason = unanswerable_reason(conflict)
    assert reason, "the #344 conflict must not be treated as answerable"
    assert "rule on" in reason or "diverge" in reason


@pytest.mark.parametrize(
    "value",
    ["", "   ", "?", "??", "-", "--", "...", "N/A", "n/a", "TBD", "unknown",
     "None", "unclear", "\t\n", "!!", "???"],
)
def test_placeholder_divergences_are_rejected(value):
    assert unanswerable_reason({**GOOD, "diverging_situation": value})


@pytest.mark.parametrize(
    "value",
    [
        "when the window maximum is not the latest sample",
        "at distance 2.5",
        "0 rpm",
        "if the needle is at its stop",
        "when both fire in the same frame",
    ],
)
def test_real_divergences_are_not_rejected(value):
    """The narrow half. A check that cries wolf gets skimmed, and this one
    files launch-blocking issues -- over-rejecting would silence a real gate."""
    assert unanswerable_reason({**GOOD, "diverging_situation": value}) is None


def test_the_reason_names_the_defect_rather_than_saying_invalid():
    """'Invalid response' tells the next reader nothing. The reason quotes what
    came back and says why it cannot be ruled on."""
    rendered = unanswerable_reason(ISSUE_344_AS_RENDERED)
    assert "'?'" in rendered and "nothing to rule on" in rendered

    returned = unanswerable_reason(ISSUE_344_AS_RETURNED)
    assert "no situation" in returned and "diverge" in returned

    word = unanswerable_reason({**GOOD, "diverging_situation": "TBD"})
    assert "placeholder" in word and "'TBD'" in word


# ---------------------------------------------------------------------------
# The filing boundary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "conflict",
    [ISSUE_344_AS_RENDERED, ISSUE_344_AS_RETURNED],
    ids=["as-rendered", "as-returned"],
)
def test_an_unanswerable_conflict_is_never_filed(tmp_path, conflict):
    gh = FakeGh()
    result = file_must_resolve(tmp_path, 332, conflict, runner=gh, log=lambda _m: None)

    assert result.action == "rejected"
    assert not result.ok
    assert gh.created == [], "no must-resolve issue may be created"


def test_the_rejection_is_surfaced_by_name_not_dropped(tmp_path):
    """It may sit near something real -- on #332 it did, and a human found it
    by reading around the empty filing."""
    said: list[str] = []
    file_must_resolve(
        tmp_path, 332, ISSUE_344_AS_RENDERED, runner=FakeGh(), log=said.append
    )

    text = "\n".join(said)
    assert "NOT FILED" in text
    assert A_344 in text and B_344 in text, "both readings must still be shown"


def test_a_well_formed_conflict_still_files(tmp_path):
    gh = FakeGh()
    result = file_must_resolve(tmp_path, 332, GOOD, runner=gh, log=lambda _m: None)

    assert result.action == "filed"
    assert gh.created, "the guard must not stop real findings from being filed"


def test_the_spec_reviewers_coarse_conflict_still_files(tmp_path):
    """#2192 emits an empty criterion_b ON PURPOSE when the reviewer's prose
    cannot be split in two: a coarse issue is worth having, a missing one is
    the defect. This guard is scoped to the divergence and must not undo it."""
    coarse = conflict_from_rationale(
        "REQUIREMENTS CONFLICT: the two acceptance criteria disagree about "
        "what happens at the stop."
    )
    assert coarse["criterion_b"] == "", "the fixture must exercise the coarse shape"

    gh = FakeGh()
    result = file_must_resolve(tmp_path, 332, coarse, runner=gh, log=lambda _m: None)

    assert result.action == "filed"
    assert gh.created


def test_a_rendered_body_never_shows_a_bare_question_mark():
    body = build_body(
        332,
        {"criterion_a": "only A was stated"},
        run_id="r", run_start="s", conflict_ts="t", fingerprint="f",
    )
    assert "- B: ?" not in body and "Diverge when: ?" not in body
    assert "(not stated)" in body


# ---------------------------------------------------------------------------
# The node
# ---------------------------------------------------------------------------


class _FakeProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[dict] = []

    def invoke(self, **kwargs) -> LLMCallResult:
        self.calls.append(kwargs)
        return LLMCallResult(
            success=True,
            response=self.response,
            raw_response=self.response,
            error_message=None,
            provider="fake",
            model_used="fake-model",
            duration_ms=1,
            attempts=1,
        )


@pytest.fixture
def node(monkeypatch, tmp_path):
    """Drive the live node, capturing filings and unverified records."""
    captured = {"filed": [], "unverified": []}

    monkeypatch.setattr(
        "assemblyzero.speedrun.must_resolve.file_all_conflicts",
        lambda repo, issue, conflicts, **k: captured["filed"].extend(conflicts),
    )
    monkeypatch.setattr(
        "assemblyzero.speedrun.prompt_telemetry.record_failures",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "assemblyzero.speedrun.requirements_status.record_unverified",
        lambda repo, **k: captured["unverified"].append(k),
    )

    def run(response: str) -> dict:
        provider = _FakeProvider(response)
        monkeypatch.setattr(
            "assemblyzero.core.llm_provider.get_provider",
            lambda spec, *a, **k: provider,
        )
        return analyze_requirements({
            "issue_title": "t",
            "issue_body": "some requirement text",
            "issue_number": 332,
            "target_repo": str(tmp_path),
            "config_drafter": "fake:model",
        })

    captured["run"] = run
    return captured


ALL_UNARTICULATED = (
    '{"is_consistent": false, "conflicts": [{"criterion_a": "%s", '
    '"criterion_b": "%s", "diverging_situation": "?"}]}' % (A_344, B_344)
)

MIXED = (
    '{"is_consistent": false, "conflicts": ['
    '{"criterion_a": "%s", "criterion_b": "%s", "diverging_situation": "?"}, '
    '{"criterion_a": "%s", "criterion_b": "%s", "diverging_situation": "%s"}]}'
    % (A_344, B_344, GOOD["criterion_a"], GOOD["criterion_b"],
       GOOD["diverging_situation"])
)

ONLY_GOOD = (
    '{"is_consistent": false, "conflicts": [{"criterion_a": "%s", '
    '"criterion_b": "%s", "diverging_situation": "%s"}]}'
    % (GOOD["criterion_a"], GOOD["criterion_b"], GOOD["diverging_situation"])
)


def test_an_all_unarticulated_verdict_files_nothing_and_does_not_halt(node, capsys):
    result = node["run"](ALL_UNARTICULATED)

    assert result == {}, "a finding the check could not state must not halt the roll"
    assert node["filed"] == [], "and must not become a launch-blocking question"
    out = capsys.readouterr().out
    assert "REJECTED" in out and A_344 in out


def test_an_all_unarticulated_verdict_is_recorded_as_unverified(node):
    """Failing open is recorded, never silent (#2290): 'not checked' and
    'checked and clean' are different roll outcomes."""
    node["run"](ALL_UNARTICULATED)

    assert len(node["unverified"]) == 1
    assert "divergence" in node["unverified"][0]["reason"]


def test_a_clean_verdict_is_not_recorded_as_unverified(node):
    node["run"]('{"is_consistent": true, "conflicts": []}')
    assert node["unverified"] == []


def test_a_mixed_verdict_halts_on_the_real_one_and_files_only_that(node):
    result = node["run"](MIXED)

    assert REQUIREMENTS_CONFLICT_MARKER in result["error_message"]
    assert [c["criterion_a"] for c in node["filed"]] == [GOOD["criterion_a"]]
    assert node["unverified"] == [], "it did produce a verdict"


def test_a_mixed_verdict_still_names_the_pairing_it_dropped(node):
    result = node["run"](MIXED)

    message = result["error_message"]
    assert A_344 in message, "the dropped pairing must be surfaced, not silently lost"
    assert "NOT raised as a question" in message


def test_a_well_formed_verdict_is_unchanged(node):
    result = node["run"](ONLY_GOOD)

    assert REQUIREMENTS_CONFLICT_MARKER in result["error_message"]
    assert len(node["filed"]) == 1
    assert node["unverified"] == []
