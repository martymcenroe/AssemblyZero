"""N0c: Requirements-ambiguity analysis before any generation spends tokens.

Issue #1899 (operator-commissioned after boostgauge#125): issue #41 carried
two different floors for a decaying peak — 'highest value still in the
window' vs 'drifts toward the most recent value' — and the contradiction
surfaced only after two campaign rolls burned three implementation
iterations each and a third burned all its spec-revision cycles
oscillating between the readings. The ambiguity was in the issue text the
whole time; every test case sat where both readings agree, so it survived
human review too.

This node reads the issue's behavior text, acceptance criteria, and test
plan as ONE document and checks internal consistency BEFORE the drafter
runs:

- Do any two criteria specify different outcomes for the same situation?
- Does every behavioral term have exactly one definition?
- Do the planned tests discriminate between plausible readings?

On conflict it halts with a message beginning ``REQUIREMENTS CONFLICT:``
naming the conflicting sentences verbatim and the situation where they
diverge — the same marker the spec reviewer uses for conflicts that
emerge mid-pipeline (#1900), so both classify as ``requirements_conflict``
(non-transient: no retry fixes an ambiguous requirement, the ISSUE needs
an operator ruling).

Fail-open by design: this gate is protective, not load-bearing. If the
analysis call itself fails (provider storm, parse noise), the workflow
proceeds to drafting with a printed warning rather than dying in a
pre-flight check.

Failing open is not the same as failing silently (#2290). Every path that
proceeds without a verdict records that fact where the roll's verdict block
and the operator summary will print it, because "requirements were not
checked" and "requirements were checked and were clean" are different roll
outcomes that used to look identical from the outside.
"""

from __future__ import annotations

import json
from typing import Any

REQUIREMENTS_CONFLICT_MARKER = "REQUIREMENTS CONFLICT:"

#: Wall-clock budget for the single analysis call.
#:
#: #2290, operator ruling. The previous bound was the provider default of 300s.
#: Measured on boostgauge #7 -- two decision tables, 21 acceptance criteria,
#: near the top of the size distribution this gate sees -- the same call timed
#: out at 300s on one attempt and returned a real CONFLICT verdict in 294s on
#: the next. Six seconds of margin, on opposite sides of the bound, minutes
#: apart, with a healthy transport throughout.
#:
#: 600s is sized to clear that measurement with room for a longer issue rather
#: than to sit just above it. Duration scales with issue size and the bound is a
#: constant, so the next issue with three tables must not re-open this.
REQUIREMENTS_GATE_TIMEOUT_SECONDS = 600

ANALYSIS_SYSTEM_PROMPT = """\
You are a requirements analyst performing a pre-flight consistency check \
on a GitHub issue before an autonomous pipeline builds from it.

Read the issue's behavior description, acceptance criteria, and test plan \
as ONE document. You are looking ONLY for internal contradictions and \
ambiguities that make the requirements unimplementable-as-written:

1. CONFLICTING CRITERIA: two statements that specify different outcomes \
for the same situation. Quote both VERBATIM and describe the concrete \
situation where they diverge (example: 'floor = highest value still in \
the window' vs 'floor drifts toward the most recent value' — these \
differ exactly when the window maximum is not the latest sample).
2. UNDEFINED OR MULTIPLY-DEFINED TERMS: a behavioral term used with two \
meanings, or two terms used interchangeably for what may be different \
things ('current value' vs 'most recent value' vs 'values in the window').
3. NON-DISCRIMINATING TESTS: planned test cases that sit only where all \
plausible readings agree, so they cannot reveal which reading is meant.

Do NOT flag: missing implementation detail, scope you consider too large, \
style, feasibility, or anything a competent drafter can decide one \
reasonable way. Flag ONLY genuine either-reading-is-defensible conflicts \
where building the wrong reading wastes the whole run.

Respond with JSON only."""

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "is_consistent": {"type": "boolean"},
        "conflicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion_a": {"type": "string"},
                    "criterion_b": {"type": "string"},
                    "diverging_situation": {"type": "string"},
                },
                "required": [
                    "criterion_a",
                    "criterion_b",
                    "diverging_situation",
                ],
            },
        },
    },
    "required": ["is_consistent", "conflicts"],
}


def _format_conflict_message(conflicts: list[dict]) -> str:
    """Build the halt message: marker + each conflict named verbatim."""
    lines = [
        f"{REQUIREMENTS_CONFLICT_MARKER} the issue's requirements are "
        f"internally inconsistent — no spec can satisfy both readings. "
        f"An operator ruling on the issue text is required before any roll."
    ]
    for i, c in enumerate(conflicts, 1):
        lines.append(
            f"\nConflict {i}:\n"
            f"  A: {c.get('criterion_a', '?')}\n"
            f"  B: {c.get('criterion_b', '?')}\n"
            f"  Diverge when: {c.get('diverging_situation', '?')}"
        )
    return "\n".join(lines)


def _parse_analysis(raw: str) -> dict | None:
    """Parse the analysis JSON, tolerating fenced or prefixed output."""
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    try:
        parsed = json.loads(text.strip())
    except ValueError:
        return None
    if not isinstance(parsed, dict) or "is_consistent" not in parsed:
        return None
    return parsed


def _is_timeout(result: Any) -> bool:
    """Did this call fail by exceeding its budget, as opposed to any other way?

    Keyed off the message the provider layer writes ("claude -p timed out after
    Ns", "agy spawn timed out") rather than an exception type, because the
    provider returns a result object instead of raising.
    """
    if getattr(result, "success", False):
        return False
    return "timed out" in (getattr(result, "error_message", "") or "").lower()


def _provider_storm_active() -> bool:
    """Is the provider in a storm right now? False if the counter is unavailable.

    Unavailable means we cannot prove a storm, and the retry is the cheaper
    error in that direction: one extra call, versus never retrying because a
    telemetry import failed.
    """
    try:
        from assemblyzero.core import provider_storm

        return bool(provider_storm.is_storm())
    except Exception:  # noqa: BLE001 - a storm probe must not break the gate
        return False


def _record_unverified(state: dict, reason: str) -> None:
    """Record a fail-open so the roll can say so. Never raises (#2290).

    Recorded on EVERY path that proceeds without a verdict, not only on the
    exhausted retry: an unparseable response and an invalid provider leave the
    requirements exactly as unchecked as a timeout does, and the operator's
    question is "were they checked", not "which way did the check fail".

    Not recorded for the standalone pre-check, which is not a roll: it reports
    its own failure with a non-zero exit and its own report, and a record
    written there would sit in the ledger waiting to mislabel some later roll.
    """
    if state.get("standalone_precheck"):
        return

    try:
        from assemblyzero.speedrun.must_resolve import run_context
        from assemblyzero.speedrun.requirements_status import record_unverified

        try:
            run_id, _ = run_context()
        except Exception:  # noqa: BLE001
            run_id = ""
        record_unverified(
            state.get("target_repo") or ".",
            issue=int(state.get("issue_number") or 0) or None,
            reason=reason,
            run_id=run_id,
        )
    except Exception as exc:  # noqa: BLE001 - never costs the run
        print(f"  [N0c] WARNING: could not record the unverified state: {exc}")


def analyze_requirements(state: dict) -> dict[str, Any]:
    """N0c node body. Returns {} to proceed, or error_message to halt."""
    if state.get("config_mock_mode"):
        return {}

    issue_title = state.get("issue_title", "")
    issue_body = state.get("issue_body", "")
    if not issue_body.strip():
        # Nothing to analyze — some entry paths carry file input instead.
        return {}

    print("  [N0c] Requirements-ambiguity analysis (#1899)...")

    from assemblyzero.core.llm_provider import GeminiProvider, get_provider

    drafter_spec = state.get("config_drafter", "gemini:3.1-pro")
    try:
        provider = get_provider(drafter_spec)
    except ValueError as e:
        print(f"  [N0c] WARNING: analysis skipped (invalid provider: {e})")
        _record_unverified(state, f"invalid provider '{drafter_spec}': {e}")
        return {}

    schema_kwargs: dict[str, Any] = {}
    if isinstance(provider, GeminiProvider):
        schema_kwargs["response_schema"] = ANALYSIS_SCHEMA
    else:
        schema_kwargs["json_schema"] = ANALYSIS_SCHEMA

    content = f"# Issue: {issue_title}\n\n{issue_body}"

    def _invoke():
        return provider.invoke(
            system_prompt=ANALYSIS_SYSTEM_PROMPT,
            content=content,
            timeout_seconds=REQUIREMENTS_GATE_TIMEOUT_SECONDS,
            **schema_kwargs,
        )

    result = _invoke()

    # One retry, and only for a timeout on a healthy transport (#2290). A
    # storm is the condition fail-open exists for -- retrying into it burns
    # another full budget to reach the same wall, which is what the storm
    # counter was built to stop (#2086). A non-timeout failure is not retried
    # either: it failed for a reason a second identical call will not change.
    if _is_timeout(result) and not _provider_storm_active():
        print(
            f"  [N0c] analysis timed out at {REQUIREMENTS_GATE_TIMEOUT_SECONDS}s "
            "and the transport is healthy -- retrying once."
        )
        result = _invoke()

    # Fail-open: a dead analysis call must not kill the roll (#1899).
    if not result.success or not result.response:
        reason = result.error_message or "empty response"
        print(f"  [N0c] WARNING: analysis unavailable ({reason}); proceeding.")
        _record_unverified(state, f"analysis unavailable: {reason}")
        return {}

    parsed = _parse_analysis(result.response)
    if parsed is None:
        print("  [N0c] WARNING: analysis response unparseable; proceeding.")
        _record_unverified(state, "analysis response was unparseable")
        return {}

    conflicts = parsed.get("conflicts") or []
    if parsed.get("is_consistent", True) or not conflicts:
        print("  [N0c] Requirements internally consistent.")
        return {}

    message = _format_conflict_message(conflicts)
    print(f"  [N0c] {message}")

    # #2072: the finding used to go to a run log and nowhere else, and N0c is
    # LLM-judged, so a lenient redraw could pass the same text minutes later and
    # roll over an unresolved ambiguity. File it where a human will see it.
    # Never changes the halt outcome: the roll was already halting, and a filing
    # failure is loud in the log but returns the same error_message.
    # #2074: count it too. The must-resolve issue is the human-facing record;
    # this is the one a rate is computed from.
    try:
        from assemblyzero.speedrun.must_resolve import run_context
        from assemblyzero.speedrun.prompt_telemetry import record_failures

        run_id, _ = run_context()
        record_failures(
            state.get("target_repo") or ".",
            [str(c.get("criterion_a", "")) for c in conflicts],
            stage="lld",
            check="requirements-conflict",
            issue=int(state.get("issue_number") or 0) or None,
            drafter_model=state.get("config_drafter", ""),
            run_id=run_id,
        )
    except Exception as exc:  # noqa: BLE001 - telemetry never breaks a halt
        print(f"  [telemetry] conflict telemetry skipped: {exc}")

    try:
        from assemblyzero.speedrun.must_resolve import file_all_conflicts

        file_all_conflicts(
            state.get("target_repo") or ".",
            int(state.get("issue_number") or 0),
            conflicts,
        )
    except Exception as exc:  # noqa: BLE001 - filing must never mask the halt
        print(f"  [N0c] WARNING: must-resolve filing failed ({exc}); halting anyway.")

    return {"error_message": message}
