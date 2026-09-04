"""A roll records its calls, and the recording replays it exactly (#2731).

The launch gate. Replay proves that the gate which killed a recorded run no
longer kills that run's content, and until now it proved it from a
reconstruction: rules derived from the drafts and verdicts a run left behind,
because the pipeline never wrote down the calls themselves. Counted over the
four runs replayed on 2026-09-03, that reconstruction was faithful for about
five rounds and then one edit anchor missed, and the replay stopped for a reason
that had nothing to do with the gate under test.

This suite is the acceptance for the recorder that replaces it. Both rolls below
run the REAL implementation-spec graph -- the routers, the janitors, the gates,
the pinning enforcement, the file writes and the halt path -- against a
throwaway git repository, with only the transport scripted. Each is run twice:
once answered by fixtures while the recorder writes `calls.jsonl`, and once
answered by that recording. The two runs must reach the same terminal record.

**Byte-exact is the point.** `ReplayProvider` refuses a call whose prompt is not
the prompt the recording holds, and the second pass is run against a restored
copy of the repository at the same absolute path for exactly that reason: a
replay that tolerated a changed prompt would be answering a question nobody
asked, which is the failure the reconstruction had and could not name.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from assemblyzero.core.call_recording import (
    ReplayProvider,
    read_calls,
    reset_context,
    summarize,
)
from assemblyzero.core.scripted_provider import (
    ScriptedProvider,
    ScriptedRule,
    set_active,
)
from assemblyzero.speedrun.convergence import (
    OUTCOME_FAILED,
    OUTCOME_PASSED,
    read_records,
    record_terminal,
    terminals_by_run,
)

ROOT = Path(__file__).resolve().parents[2]

LLD = """# LLD-999: Add a greeting

* **Status:** Approved 2026-09-04

## 1. Requirements

- REQ-1: `greet(name)` returns `"hello, <name>"`.

## 2. Files Changed

| file | change |
|---|---|
| `src/greet.py` | Add |

## 10. Test Plan

| id | scenario | expects |
|---|---|---|
| S1 | greet("world") | returns "hello, world" |
"""

SPEC = """# Implementation Spec: greeting

## 1. Overview

Implements REQ-1.

## 2. Files

- `src/greet.py` (Add)

## 10. Test Plan

### 10.1 Test Functions

```python
def test_S1_greet_world():
    from greet import greet
    assert greet("world") == "hello, world"
```
"""

APPROVED = json.dumps({
    "verdict": "APPROVED",
    "rationale": "covers REQ-1",
    "feedback_items": [],
})

#: The shape that killed run 12 of boostgauge #4: the reviewer escalates a
#: contradiction in the issue's own acceptance criteria, which no spec can
#: satisfy, and the run stops at `spec.requirements_conflict`.
BLOCKED = json.dumps({
    "verdict": "BLOCKED",
    "rationale": (
        "REQUIREMENTS CONFLICT: REQ-1 asks for a lower-case greeting and the "
        "test plan expects a capitalised one. No spec can satisfy both."
    ),
    "feedback_items": ["rule on the casing before this can be drafted"],
})

PATTERN_DRAFTER = "technical architect creating an Implementation Specification"
PATTERN_REVIEWER = "Implementation Readiness Review"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
        encoding="utf-8", errors="replace",
    )


@pytest.fixture
def workspace(tmp_path: Path):
    """A throwaway target repo, plus a pristine copy to restore between passes.

    The restore is what makes the second pass byte-comparable: the spec stage
    reads the repository to build its prompt, so a replay against a tree the
    first pass had already written to would be sent a different prompt and
    would -- correctly -- refuse it.
    """
    repo = tmp_path / "target"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)],
        capture_output=True, text=True, check=True,
    )
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")

    lld_path = tmp_path / "LLD-999.md"
    lld_path.write_text(LLD, encoding="utf-8")

    pristine = tmp_path / "pristine"
    shutil.copytree(repo, pristine)

    def restore() -> None:
        _rmtree(repo)
        shutil.copytree(pristine, repo)
        # The lineage directory too, and this one is load-bearing. Left in
        # place, `generate_spec` recovers the previous pass's draft by globbing
        # `*-spec-draft.md` out of it and never calls the drafter at all -- the
        # second pass would start mid-loop, its first call would be the
        # reviewer's, and the replay would report a divergence that is an
        # artifact of the harness rather than of the code. Caught exactly that
        # way while building this test.
        lineage = tmp_path / "lineage"
        if lineage.exists():
            _rmtree(lineage)

    return tmp_path, repo, lld_path, restore


def _rmtree(path: Path) -> None:
    """Remove a tree that contains a git object store, on Windows.

    Git writes its loose objects read-only, and Windows refuses to unlink a
    read-only file, so a plain `rmtree` raises PermissionError partway through
    and leaves half a repository behind. Clearing the bit and retrying is the
    documented remedy.
    """
    def _clear_readonly(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    shutil.rmtree(path, onexc=_clear_readonly)


def _state(tmp_path: Path, repo: Path, lld_path: Path) -> dict:
    return {
        "issue_number": 999,
        "lld_path": str(lld_path),
        "repo_root": str(repo),
        "assemblyzero_root": str(ROOT),
        "audit_dir": str(tmp_path / "lineage"),
        "base_branch": "main",
        "lld_content": "",
        "files_to_modify": [],
        "current_state_snapshots": {},
        "pattern_references": [],
        "spec_draft": "",
        "spec_path": "",
        "completeness_issues": [],
        "validation_passed": False,
        "review_verdict": "BLOCKED",
        "review_feedback": "",
        "review_iteration": 0,
        "review_feedback_history": [],
        "max_iterations": 3,
        "human_gate_enabled": False,
        "next_node": "",
        "error_message": "",
        "cost_budget_usd": 0.0,
        "config_reviewer": "scripted:reviewer",
        "config_drafter": "scripted:drafter",
        "config_mock_mode": False,
        "config_effort": "",
        "node_costs": {},
        "node_tokens": {},
    }


def _roll(tmp_path: Path, repo: Path, lld_path: Path, provider) -> dict:
    """Run the real spec graph with ``provider`` as the only thing mocked."""
    from assemblyzero.workflows.implementation_spec.graph import (
        create_implementation_spec_graph,
    )

    reset_context()
    set_active(provider)
    state = _state(tmp_path, repo, lld_path)
    final = dict(state)
    try:
        graph = create_implementation_spec_graph()
        for event in graph.stream(state, {"recursion_limit": 60}):
            for node_name, node_output in event.items():
                if node_name == "__end__" or not node_output:
                    continue
                final.update(node_output)
    finally:
        set_active(None)
        reset_context()
    return final


def _recording_in(root: Path) -> Path:
    """Where the roll actually wrote its recording.

    Discovered rather than assumed, and searched from the whole workspace
    rather than from the repository, because the two rolls put it in different
    places: the loader replaces `audit_dir` with a run-scoped lineage directory
    (#1467) and the finalizer moves that from `active` to `done`, while a roll
    that halts before finalizing leaves it where the halt found it.
    """
    found = sorted(root.glob("**/calls.jsonl"))
    assert len(found) == 1, (
        f"expected one recording under {root}, found {found}"
    )
    return found[0].parent


def _terminal(final: dict, calls: int) -> tuple[str, int, int]:
    """(gate, round, call count) -- the triple a terminal record carries."""
    error = str(final.get("error_message", "") or "")
    gate = "finalize" if final.get("spec_path") and not error else (
        "spec.requirements_conflict" if "REQUIREMENTS CONFLICT" in error
        else (error.splitlines() or [""])[0][:60]
    )
    return gate, int(final.get("review_iteration", 0) or 0), calls


@pytest.mark.parametrize(
    "name,verdict,expected_gate",
    [
        ("a passed roll", APPROVED, "finalize"),
        ("a halted roll", BLOCKED, "spec.requirements_conflict"),
    ],
    ids=["passed", "halted"],
)
class TestARecordedRollReplaysExactly:
    def test_the_roll_records_its_calls_and_the_recording_replays_it(
        self, workspace, name, verdict, expected_gate
    ):
        tmp_path, repo, lld_path, restore = workspace
        rules = [
            ScriptedRule("spec-drafter", system_pattern=PATTERN_DRAFTER,
                         response=SPEC),
            ScriptedRule("spec-reviewer", system_pattern=PATTERN_REVIEWER,
                         response=verdict),
        ]

        # Pass one: fixtures answer, and the recorder writes down every call.
        scripted = ScriptedProvider(rules, model="mock-roll")
        first = _roll(tmp_path, repo, lld_path, scripted)
        recording_dir = _recording_in(tmp_path)
        calls, unreadable = read_calls(recording_dir)
        assert unreadable == 0
        assert calls, "the roll recorded no model calls"

        first_terminal = _terminal(first, len(calls))
        assert first_terminal[0] == expected_gate, (
            f"{name} did not reach the gate this test is about: {first}"
        )
        record_terminal(
            tmp_path, outcome=(
                OUTCOME_PASSED if expected_gate == "finalize" else OUTCOME_FAILED
            ),
            furthest_stage="spec", furthest_node="N5_review_spec",
            gate_key=first_terminal[0], run_tag="pass-one",
        )

        # Pass two: the recording answers, against a restored tree at the same
        # absolute path, so every prompt is the prompt pass one sent.
        restore()
        replay = ReplayProvider(calls)
        second = _roll(tmp_path, repo, lld_path, replay)

        assert replay.divergence is None, (
            f"the replay diverged: {replay.divergence.describe()}"
            if replay.divergence else ""
        )
        assert replay.served == len(calls), (
            f"served {replay.served} of {len(calls)} recorded call(s)"
        )

        second_terminal = _terminal(second, replay.served)
        record_terminal(
            tmp_path, outcome=(
                OUTCOME_PASSED if expected_gate == "finalize" else OUTCOME_FAILED
            ),
            furthest_stage="spec", furthest_node="N5_review_spec",
            gate_key=second_terminal[0], run_tag="pass-two",
        )

        assert second_terminal == first_terminal, (
            "the replay reached a different place than the roll it replays"
        )

        # And the same claim read back off the terminal records themselves,
        # rather than off the two dictionaries this test happens to be holding.
        records, bad = read_records(tmp_path)
        assert bad == 0
        terminals = terminals_by_run(records)
        assert terminals["pass-one"]["gate_key"] == terminals["pass-two"]["gate_key"]
        assert terminals["pass-one"]["outcome"] == terminals["pass-two"]["outcome"]

    def test_the_recording_is_tagged_by_stage_node_and_round(
        self, workspace, name, verdict, expected_gate
    ):
        tmp_path, repo, lld_path, _restore = workspace
        rules = [
            ScriptedRule("spec-drafter", system_pattern=PATTERN_DRAFTER,
                         response=SPEC),
            ScriptedRule("spec-reviewer", system_pattern=PATTERN_REVIEWER,
                         response=verdict),
        ]
        _roll(tmp_path, repo, lld_path, ScriptedProvider(rules, model="mock-roll"))
        recording_dir = _recording_in(tmp_path)
        calls, _ = read_calls(recording_dir)

        assert [c["seq"] for c in calls] == list(range(1, len(calls) + 1))
        assert {c["stage"] for c in calls} == {"spec"}
        assert calls[0]["node"] == "N2_generate_spec"
        assert calls[0]["round"] == 1
        for call in calls:
            assert call["system_prompt"], "the prompt as sent is the point"
            assert call["round"] >= 1
            assert "duration_ms" in call

        summary = summarize(recording_dir)
        assert summary.usable
        assert summary.calls == len(calls)
        assert summary.stages == ["spec"]


class TestADivergenceIsNamedRatherThanAnswered:
    def test_a_code_change_to_the_prompt_stops_the_replay_and_says_where(
        self, workspace, monkeypatch
    ):
        """The whole reason #2731 exists, reproduced.

        A code change edits a prompt, so the recorded response is no longer the
        response that prompt would have drawn. Under reconstruction that
        surfaced four rounds later as "the derived blocks stopped applying",
        which names neither the change nor the call. Here it is the call number
        and the diff, at the first call the change touches.
        """
        tmp_path, repo, lld_path, restore = workspace
        rules = [
            ScriptedRule("spec-drafter", system_pattern=PATTERN_DRAFTER,
                         response=SPEC),
            ScriptedRule("spec-reviewer", system_pattern=PATTERN_REVIEWER,
                         response=APPROVED),
        ]
        _roll(tmp_path, repo, lld_path, ScriptedProvider(rules, model="mock-roll"))
        calls, _ = read_calls(_recording_in(tmp_path))
        restore()

        # Someone edits the drafter's system prompt, the way half the PRs in
        # this repository do.
        # `importlib`, not `from ... import generate_spec`: the package
        # re-exports the NODE FUNCTION under that name, so the plain import
        # hands back a function with no module attributes to patch.
        module = importlib.import_module(
            "assemblyzero.workflows.implementation_spec.nodes.generate_spec"
        )
        monkeypatch.setattr(
            module, "DRAFTER_SYSTEM_PROMPT",
            module.DRAFTER_SYSTEM_PROMPT + "\nAlways cite the LLD line.",
        )

        replay = ReplayProvider(calls)
        final = _roll(tmp_path, repo, lld_path, replay)

        assert replay.divergence is not None
        assert replay.divergence.seq == 1, "the first call the change touches"
        assert replay.divergence.field == "system prompt"
        assert "Always cite the LLD line." in replay.divergence.diff
        assert "ReplayProvider:" in str(final.get("error_message", ""))
        assert replay.served == 0, "nothing is answered after a divergence"

    def test_running_past_the_recording_is_a_divergence_not_a_guess(self):
        replay = ReplayProvider([
            {"seq": 1, "system_prompt": "s", "content": "c", "response": "r",
             "success": True},
        ])
        assert replay.invoke("s", "c").response == "r"
        second = replay.invoke("s", "c")
        assert second.success is False
        assert "holds 1 call(s)" in second.error_message
        assert replay.divergence.seq == 2
