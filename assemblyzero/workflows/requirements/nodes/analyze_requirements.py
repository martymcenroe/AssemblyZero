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

Fails CLOSED when it cannot reach a verdict (#2474, operator ruling
2026-08-16). It was fail-open from #1899 through #2290 on the reasoning
that a provider storm must not brick a launch. Measured against what that
bought: on boostgauge #331 the governance model was unreachable, the node
printed ``proceeding``, and the run went on to spend drafter budget with
the highest-value-per-dollar gate in the pipeline skipped. A storm that
bricks a launch is cheaper than a launch that drafts against unverified
requirements, so an unreachable gate is now a halt condition.

The halt is preceded by a backoff (``GATE_UNAVAILABLE_RETRY_BACKOFF_SECONDS``)
because the observed outage cleared within minutes -- halting on the first
storm would be brittle in the other direction.

Three outcomes, three destinations. The graph declares two successors for
this node, and until #2474 the node returned ``{}`` for BOTH "checked, and
clean" and "could not check" -- LangGraph routes on the return value, so
those collapsed onto the same edge and the distinction died inside the node
before routing ever saw it. Now:

- verified consistent      -> ``{}``                         -> drafting
- conflict found           -> ``error_message``              -> HALT
- no verdict reached       -> ``requirements_unverified``    -> HALT

Until #3585 one path still proceeded without a verdict: #2462's, where the
model answers but every conflict it reports lacks a divergence condition. It
recorded the unverified state for the end-of-run banner and went on to draft.
#3585 (ADR 0236) closed it. Such a verdict is no usable verdict, so it halts
as REQUIREMENTS UNVERIFIED with the pairings named, and nothing proceeds
without a verdict; the record that path wrote, and the helper that wrote it,
are gone. It still never becomes a must-resolve question, which #2462 ruled
out. An empty issue body and a bad escalation seat halt the same way, a
finding that is not an object makes the answer unparseable, and a failed
telemetry record or must-resolve filing beside a conflict halt alerts the
operator, since the halt itself does not name it.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from typing import Any

logger = logging.getLogger(__name__)

REQUIREMENTS_CONFLICT_MARKER = "REQUIREMENTS CONFLICT:"

#: Prefix on the halt message when the gate could not reach a verdict (#2474).
#:
#: Deliberately NOT the conflict marker. "The requirements contradict each
#: other" and "I could not check the requirements" call for opposite operator
#: responses -- one needs a ruling on the issue text, the other needs a re-run --
#: and sharing a marker is the same collapse at the reporting layer that #2474
#: fixed at the routing layer.
REQUIREMENTS_UNVERIFIED_MARKER = "REQUIREMENTS UNVERIFIED:"

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

#: Where a timed-out gate call goes on its one retry (#2375).
#:
#: #2290 added a retry for a timeout on a healthy transport, and it re-asked the
#: SAME model. Measured 2026-08-14 on boostgauge #1's converted body: claude
#: sonnet timed out at 600s three consecutive times (13:0x, 13:4x, 14:2x
#: Central), and claude opus returned a CLEAN verdict inside the bound on the
#: first attempt immediately afterwards. Transport healthy throughout -- a
#: trivial `claude -p` round-tripped in 5.0s between attempts. The same sonnet
#: call had completed boostgauge #7, a comparable-size comparably-tabled
#: document, in about five minutes that morning.
#:
#: So on this content class the model is the variable, and a same-model retry
#: spends a second full 600s budget to reach the same wall. Escalating instead
#: costs the same one retry and has a measured chance of returning a verdict.
#:
#: Deliberately narrow. A spec is escalated only where a measurement says the
#: escalation helps; everything else keeps #2290's same-model retry, because no
#: measurement says otherwise for it and inventing a ladder here would be the
#: guessing this issue's acceptance forbids.
GATE_DRAFTER_ESCALATION: dict[str, str] = {
    "claude:sonnet": "claude:opus",
}

#: How long to wait between attempts before halting an unreachable gate (#2474).
#:
#: One entry per retry, in seconds of sleep BEFORE that attempt. Measured
#: against boostgauge #331, where the node saw ``All credentials failed ...
#: riding 503/529 capacity storms`` and the same run logged ``[PREFLIGHT]
#: Gemini: 4/4 credentials`` minutes later. Capacity came back on its own, so a
#: halt on the first storm would trade one failure mode for another.
#:
#: Two retries spanning four minutes of waiting. The bound matters because each
#: attempt can itself burn the full ``REQUIREMENTS_GATE_TIMEOUT_SECONDS``, and
#: this schedule COMPOSES with the #2375 timeout retry above rather than
#: replacing it. Counted, not estimated:
#:
#:   no escalation: 3 calls x 600s + 240s sleep = 2040s (34 min)
#:   after a #2375 escalation: 4 calls x 600s + 240s sleep = 2640s (44 min)
#:
#: That ceiling is bought deliberately. It buys back rolls that would otherwise
#: halt on a transient storm, it is only reached when EVERY attempt burns its
#: full budget (a total outage, not the observed case), and it is gate time
#: rather than drafter spend -- which is the trade #2474 rules on. A run that
#: cannot get a verdict across four minutes of waiting is in a real outage, and
#: halting resumably beats waiting longer.
#:
#: Unlike the #2375 timeout retry above, this schedule deliberately DOES run
#: during a provider storm. #2086's objection is to re-asking immediately, which
#: burns a second budget against the same wall; waiting is the remedy for a
#: storm rather than an instance of the thing #2086 forbids.
GATE_UNAVAILABLE_RETRY_BACKOFF_SECONDS: tuple[int, ...] = (60, 180)


def escalated_drafter(spec: str) -> str | None:
    """The stronger drafter to retry a timeout on, or None to re-ask this one."""
    return GATE_DRAFTER_ESCALATION.get((spec or "").strip().lower())

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


def _format_conflict_message(
    conflicts: list[dict], unarticulated: list[tuple[dict, str]] | None = None
) -> str:
    """Build the halt message: marker + each conflict named verbatim.

    `unarticulated` are pairings the model reported without saying where the
    two readings diverge (#2462). They are named here rather than dropped: one
    of them sat beside a real latent tension on boostgauge #332, and a human
    found it by reading around the empty filing.
    """
    lines = [
        f"{REQUIREMENTS_CONFLICT_MARKER} the issue's requirements are "
        f"internally inconsistent — no spec can satisfy both readings. "
        f"An operator ruling on the issue text is required before any roll."
    ]
    for i, c in enumerate(conflicts, 1):
        lines.append(
            f"\nConflict {i}:\n"
            f"  A: {c.get('criterion_a') or '(not stated)'}\n"
            f"  B: {c.get('criterion_b') or '(not stated)'}\n"
            f"  Diverge when: {c.get('diverging_situation') or '(not stated)'}"
        )
    for c, reason in unarticulated or []:
        lines.append(
            f"\nAlso reported, NOT raised as a question ({reason}):\n"
            f"  A: {c.get('criterion_a') or '(not stated)'}\n"
            f"  B: {c.get('criterion_b') or '(not stated)'}\n"
            "  Worth a look by eye — the pairing may sit near something real "
            "even though the check could not say what."
        )
    return "\n".join(lines)


#: #2830: where a model puts its findings when it ignores the schema. Run 13
#: on boostgauge #4 answered three times -- `{"issues": [...]}`, a bare list,
#: `{"issues": [...]}` again with different item keys -- and the gate threw all
#: three away for want of the key `is_consistent`. The question the gate asks
#: is "two quoted criteria and where they diverge"; every answer carried it.
#: A closed set, authored from the recorded responses, not discovered.
_FINDINGS_KEYS = ("conflicts", "issues", "findings", "contradictions", "problems")
_CRITERION_A_KEYS = ("criterion_a", "quote_1", "quote_a", "first")
_CRITERION_B_KEYS = ("criterion_b", "quote_2", "quote_b", "second")
_SITUATION_KEYS = (
    "diverging_situation", "divergence", "explanation", "description",
    "situation", "reason",
)
_CATEGORY_KEYS = ("category", "type")


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def _first_str(item: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _findings_of(parsed: Any) -> list | None:
    """The list of findings, wherever the model put it; None when there is none."""
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in _FINDINGS_KEYS:
            value = parsed.get(key)
            if isinstance(value, list):
                return value
        if "is_consistent" in parsed:
            return []
    return None


def _normalise_finding(item: dict) -> dict:
    """One finding in the canonical keys, keeping everything else the model said."""
    out = dict(item)
    a = _first_str(item, _CRITERION_A_KEYS)
    b = _first_str(item, _CRITERION_B_KEYS)
    quotes = item.get("quotes")
    if isinstance(quotes, list):
        strs = [q.strip() for q in quotes if isinstance(q, str) and q.strip()]
        if not a and strs:
            a = strs[0]
        if not b and len(strs) >= 2:
            b = strs[1]
    out["criterion_a"] = a
    out["criterion_b"] = b
    out["diverging_situation"] = _first_str(item, _SITUATION_KEYS)
    category = _first_str(item, _CATEGORY_KEYS)
    if category:
        out["category"] = category
    return out


def _parse_analysis(raw: str) -> dict | None:
    """Parse the analysis JSON, tolerating fenced or prefixed output and, since
    #2830, a response that carries the findings under another key or at the
    root, with the two criteria and the diverging situation under other names.

    The result is always canonical: ``conflicts`` holds every finding that
    quotes two criteria; ``notes`` holds the rest (an undefined term, a
    non-discriminating test), which are for the operator to read and are never
    filed; ``is_consistent`` is the model's when it said so and "no conflict"
    otherwise. None when there is no findings list anywhere -- the gate
    does not invent a verdict -- and, since #3585, when a finding is not an
    object: it used to be dropped, which could turn a findings list into
    "consistent". Every caller treats None as no verdict and retries, then
    halts unverified.
    """
    if not raw:
        return None
    try:
        parsed = json.loads(_strip_fence(raw))
    except ValueError:
        return None
    findings = _findings_of(parsed)
    if findings is None:
        return None
    if not all(isinstance(item, dict) for item in findings):
        return None
    conflicts: list[dict] = []
    notes: list[dict] = []
    for item in findings:
        finding = _normalise_finding(item)
        if finding["criterion_a"] and finding["criterion_b"]:
            conflicts.append(finding)
        else:
            notes.append(finding)
    out: dict = dict(parsed) if isinstance(parsed, dict) else {}
    out["conflicts"] = conflicts
    out["notes"] = notes
    if not isinstance(out.get("is_consistent"), bool):
        out["is_consistent"] = not conflicts
    return out


def _is_timeout(result: Any) -> bool:
    """Did this call fail by exceeding its budget, as opposed to any other way?

    Keyed off the message the provider layer writes ("claude -p timed out after
    Ns", "agy spawn timed out") rather than an exception type, because the
    provider returns a result object instead of raising.
    """
    if getattr(result, "success", False):
        return False
    return "timed out" in (getattr(result, "error_message", "") or "").lower()


def _loud(message: str) -> str:
    """One ERROR line on stderr and in the log (ADR 0236 property 1)."""
    logger.error("[N0c] %s", message)
    print(f"ERROR [N0c] {message}", file=sys.stderr, flush=True)
    return message


def _provider_storm_active() -> bool:
    """Is the provider in a storm right now?

    #3585: a probe that raises is said and raised. It used to read as "no
    storm", so the gate retried into what may have been a storm on a guess.
    """
    from assemblyzero.core import provider_storm

    try:
        return bool(provider_storm.is_storm())
    except Exception as exc:
        _loud(f"the provider storm probe failed: {type(exc).__name__}: {exc}")
        raise


# #3585: `_record_unverified` is gone. It wrote the "proceeded without a
# verdict" record for the one path that did (#2462), and swallowed a failed
# run_context and a failed write; that path now halts, and a halt reports
# itself through its own message, recovery plan and alert.


def _sleep(seconds: float) -> None:
    """The backoff wait (#2474), as a seam the tests replace.

    A suite that really slept this schedule would pay four minutes per case,
    which is how a suite stops being run. Patching ``time.sleep`` globally from
    a test would reach every other sleeper in the process; one named function
    here is the narrower thing to replace.
    """
    time.sleep(seconds)


def _verdict_of(result: Any) -> dict | None:
    """The parsed verdict from one attempt, or None if it did not reach one.

    Collapses "the call failed", "the call returned nothing" and "the call
    returned something unparseable" into the single question the retry loop
    asks: is there a verdict yet?
    """
    if not getattr(result, "success", False) or not getattr(result, "response", ""):
        return None
    return _parse_analysis(result.response)


def _no_verdict_reason(result: Any) -> str:
    """Why this attempt produced no verdict, in the operator's words.

    One function so the backoff loop, the halt message and the log line cannot
    disagree about which of the two failures happened.
    """
    if not getattr(result, "success", False) or not getattr(result, "response", ""):
        return getattr(result, "error_message", "") or "empty response"
    return "the analysis response was unparseable"


def _halt_unverified(
    state: dict, answered_by: str, reason: str, *, retried: bool = True
) -> dict[str, Any]:
    """Stop the run because the gate could not run (#2474).

    Returns BOTH keys deliberately. ``requirements_unverified`` is what the
    router and the standalone pre-check read, because it is the only thing that
    separates this halt from a conflict halt; ``error_message`` is what the HALT
    node classifies, prints and writes into the recovery plan.

    ``retried`` is False for a halt that no wait could change (an invalid seat,
    an empty body, an answer that states no divergence); the message then says
    so rather than claim a backoff that never ran (#3585).
    """
    repo = state.get("target_repo") or "<repo>"
    issue = state.get("issue_number") or "<N>"
    attempts = (
        f"  Attempts: 1 + {len(GATE_UNAVAILABLE_RETRY_BACKOFF_SECONDS)} retries "
        f"over {sum(GATE_UNAVAILABLE_RETRY_BACKOFF_SECONDS)}s of backoff.\n"
        if retried else
        "  Attempts: not retried; waiting would not change this.\n"
    )
    message = (
        f"{REQUIREMENTS_UNVERIFIED_MARKER} the consistency gate did not run, so "
        f"nothing about this issue's requirements was checked. This is NOT a "
        f"clean requirements check and NOT a conflict finding -- the gate never "
        f"reached a verdict.\n"
        f"  Gate model: {answered_by}\n"
        f"  Why: {reason}\n"
        f"{attempts}"
        f"  The run stopped here rather than spend drafter budget against "
        f"unverified requirements (#2474).\n"
        f"  Resume: poetry run python tools/check_requirements.py --repo {repo} "
        f"--issue {issue}\n"
        f"  Then relaunch the roll once the gate returns a verdict."
    )
    print(f"  [N0c] {message}")
    return {"error_message": message, "requirements_unverified": reason}


#: A heading that opens the issue's provenance section -- the dated log of
#: rulings and the superseded text each one replaced. Any heading level,
#: case-insensitive, matched on a whole line outside fenced code (#2870).
_HISTORY_HEADING = re.compile(
    r"^\s{0,3}#{1,6}\s*(revision history|revision log|changelog|change log|"
    r"history|rulings|log of rulings)\b",
    re.IGNORECASE,
)


def _quote_key(text: Any) -> str:
    """A quoted criterion, compared without case or spacing (#3747)."""
    return " ".join(str(text or "").lower().split())


def _same_quote(a: str, b: str) -> bool:
    """Two quotes of the same criterion: one contains the other, since a model
    asked twice may quote a shorter or longer span of the same sentence."""
    return bool(a and b) and (a in b or b in a)


def _articulated_conflicts(parsed: dict) -> list[dict]:
    """The conflicts a verdict reports that the gate would file (#2462 rules
    out the rest); none when the verdict says the text is consistent."""
    from assemblyzero.speedrun.must_resolve import unanswerable_reason

    if parsed.get("is_consistent", True):
        return []
    return [c for c in parsed.get("conflicts") or [] if not unanswerable_reason(c)]


def _reported_again(conflict: dict, again: list[dict]) -> bool:
    """Does the second answer report the same pair of criteria, in either order?"""
    a = _quote_key(conflict.get("criterion_a"))
    b = _quote_key(conflict.get("criterion_b"))
    for other in again:
        oa = _quote_key(other.get("criterion_a"))
        ob = _quote_key(other.get("criterion_b"))
        if (_same_quote(a, oa) and _same_quote(b, ob)) or (
            _same_quote(a, ob) and _same_quote(b, oa)
        ):
            return True
    return False


def requirements_text(issue_body: str) -> tuple[str, int]:
    """The body above its revision history, and how many lines were set aside.

    #2870: boostgauge #4's launches 21 and 22 halted at this gate on
    requirements that had passed it six times that day. The second halt's
    reasoning said why -- "the historical recommendation mentioned in the
    revision history." The history is a dated log of rulings; each entry
    quotes the superseded sentence it replaced, because that is what a ruling
    record does. Handed to the model as part of the requirements, every one
    of those sentences reads as a live contradiction of the criterion that
    replaced it, and the log grows by one entry per ruling. The gate was
    being fed the record of its own past false positives.

    A body with no history heading is returned whole with zero excluded. A
    heading inside a fenced code block is text, not structure, and is not a
    cut point.
    """
    lines = issue_body.splitlines()
    in_fence = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and _HISTORY_HEADING.match(line):
            kept = "\n".join(lines[:index]).rstrip()
            return kept, len(lines) - index
    return issue_body, 0


def analyze_requirements(state: dict) -> dict[str, Any]:
    """N0c node body.

    Returns ``{}`` to proceed, ``error_message`` to halt on a conflict, or
    ``requirements_unverified`` (plus ``error_message``) to halt because no
    verdict could be reached (#2474).
    """
    if state.get("config_mock_mode"):
        return {}

    issue_title = state.get("issue_title", "")
    issue_body = state.get("issue_body") or ""
    if not issue_body.strip():
        # #3585: an empty body is a gate that cannot run, so it halts
        # unverified. It used to proceed on the reasoning that a run started
        # from a brief or a file has no issue body; but the LLD workflow
        # always loads its issue (N0 halts on an empty body since #3585), and
        # the issue workflow never reaches this node.
        return _halt_unverified(
            state, "(no model called)",
            f"issue #{state.get('issue_number') or '?'} has an empty body, so "
            f"there are no requirements for the gate to read",
            retried=False,
        )

    print("  [N0c] Requirements-ambiguity analysis (#1899)...")

    from assemblyzero.core.llm_provider import GeminiProvider, get_provider
    from assemblyzero.core.seats import resolve

    # #3563: the run profile's `requirements.analyze` seat, and its
    # `requirements.analyze.escalation` seat for the one timeout retry.
    drafter_spec = "(unresolved)"
    try:
        # #3577: the escalation seat first, so the analysis seat is the last
        # resolved before its provider is built and the call record names it.
        escalation_spec = resolve(state, "requirements.analyze.escalation").spec
        seat = resolve(state, "requirements.analyze")
        drafter_spec = seat.spec
        provider = get_provider(drafter_spec, effort=seat.effort)
    except ValueError as e:
        # #2474: halts immediately, with no backoff. The backoff exists to
        # outlast a transient outage; a provider spec that does not name a real
        # provider is not transient and no amount of waiting resolves it.
        return _halt_unverified(
            state, drafter_spec, f"invalid provider '{drafter_spec}': {e}",
            retried=False,
        )

    # #2870: the gate judges the requirements. The revision history below
    # them is provenance -- superseded text, quoted on purpose -- and is not
    # handed to the model as something to find contradictions in.
    judged, excluded = requirements_text(issue_body)
    if excluded:
        print(
            f"  [N0c] judging {len(judged.splitlines())} lines of requirements; "
            f"revision history ({excluded} lines) excluded as provenance (#2870)"
        )
    content = f"# Issue: {issue_title}\n\n{judged}"

    def _invoke(active_provider):
        schema_kwargs: dict[str, Any] = {}
        if isinstance(active_provider, GeminiProvider):
            schema_kwargs["response_schema"] = ANALYSIS_SCHEMA
        else:
            schema_kwargs["json_schema"] = ANALYSIS_SCHEMA
        return active_provider.invoke(
            system_prompt=ANALYSIS_SYSTEM_PROMPT,
            content=content,
            timeout_seconds=REQUIREMENTS_GATE_TIMEOUT_SECONDS,
            **schema_kwargs,
        )

    answered_by = drafter_spec
    result = _invoke(provider)

    # One retry, and only for a timeout on a healthy transport (#2290). A
    # storm is the condition fail-open exists for -- retrying into it burns
    # another full budget to reach the same wall, which is what the storm
    # counter was built to stop (#2086). A non-timeout failure is not retried
    # either: it failed for a reason a second identical call will not change.
    #
    # #2375: the retry escalates where a measurement says escalating helps.
    # Re-asking the model that just spent the full budget is the same call
    # again; on boostgauge #1's body sonnet did that three times for three
    # timeouts while opus answered inside the bound on its first attempt.
    if _is_timeout(result) and not _provider_storm_active():
        # The escalation seat names the model for the retry; the same spec as
        # the analysis seat means "re-ask the same model", #2290's retry.
        stronger = escalation_spec if escalation_spec != drafter_spec else None
        if stronger:
            print(
                f"  [N0c] analysis timed out at {REQUIREMENTS_GATE_TIMEOUT_SECONDS}s "
                f"on {drafter_spec} and the transport is healthy -- "
                f"escalating to {stronger} for the one retry (#2375)."
            )
            try:
                # #3577: named last, so the retry is recorded as this seat's.
                resolve(state, "requirements.analyze.escalation")
                provider = get_provider(stronger)
                answered_by = stronger
            except ValueError as e:
                # #3585: a bad escalation seat is a configuration error and
                # halts, naming it. It used to warn and re-ask the model that
                # had just timed out, the call #2375 measured as useless.
                return _halt_unverified(
                    state, drafter_spec,
                    f"the analysis timed out on {drafter_spec} and its "
                    f"escalation seat names '{stronger}', which is not a valid "
                    f"provider: {e}",
                    retried=False,
                )
        else:
            print(
                f"  [N0c] analysis timed out at {REQUIREMENTS_GATE_TIMEOUT_SECONDS}s "
                "and the transport is healthy -- retrying once."
            )
        result = _invoke(provider)

    # #2474: no verdict is a halt condition, not a warning -- but not before a
    # backoff, because the outage that prompted this ruling cleared on its own
    # within minutes. Unreachable and unparseable share this path because they
    # are the same fact from the graph's side ("no verdict"), and because both
    # are plausibly transient: one is the transport, the other is a sample. What
    # they must NOT share is the verified-clean return value, which is the
    # collapse #2474 is about.
    parsed = _verdict_of(result)
    if parsed is None:
        # #2375: every line below names the model. "The gate did not answer" and
        # "the gate did not answer ON SONNET" are different facts, and only the
        # second tells the next reader whether escalating is worth trying.
        reason = _no_verdict_reason(result)
        for attempt, delay in enumerate(GATE_UNAVAILABLE_RETRY_BACKOFF_SECONDS, 1):
            print(
                f"  [N0c] no verdict on {answered_by} ({reason}); waiting {delay}s "
                f"before retry {attempt} of "
                f"{len(GATE_UNAVAILABLE_RETRY_BACKOFF_SECONDS)} (#2474)."
            )
            _sleep(delay)
            result = _invoke(provider)
            parsed = _verdict_of(result)
            if parsed is not None:
                print(f"  [N0c] the retry reached a verdict on {answered_by}.")
                break
            reason = _no_verdict_reason(result)
        if parsed is None:
            return _halt_unverified(state, answered_by, reason)

    conflicts = parsed.get("conflicts") or []
    # #2830: a finding that quotes fewer than two criteria is not a conflict
    # and is never filed; it is still worth the operator's eye.
    for note in parsed.get("notes") or []:
        label = note.get("category") or "note"
        text = note.get("diverging_situation") or note.get("term") or ""
        print(f"  [N0c] noted, not a conflict ({label}): {text[:240]}")
    if parsed.get("is_consistent", True) or not conflicts:
        # CLEAN_MARKER is asserted verbatim by the pre-check's tests, so the
        # drafter goes on its own line rather than into that sentence.
        print("  [N0c] Requirements internally consistent.")
        print(f"  [N0c] Verdict from {answered_by}.")
        return {}

    # #2462: a conflict whose divergence condition is empty or a placeholder is
    # a malformed response, not a finding. Standard 0028 applied to this gate's
    # own output: what came back does not satisfy the contract, so it is
    # rejected by name rather than passed on as if it were a verdict. Observed
    # on boostgauge #344, whose entire divergence condition was `?` -- a
    # launch-blocking question no ruling could address.
    from assemblyzero.speedrun.must_resolve import unanswerable_reason

    articulated: list[dict] = []
    unarticulated: list[tuple[dict, str]] = []
    for c in conflicts:
        reason = unanswerable_reason(c)
        if reason:
            unarticulated.append((c, reason))
        else:
            articulated.append(c)
    conflicts = articulated

    for c, reason in unarticulated:
        print(
            f"  [N0c] REJECTED a reported conflict: {reason}. "
            "Not filed as a question."
        )
        print(f"          A: {c.get('criterion_a') or '(not stated)'}")
        print(f"          B: {c.get('criterion_b') or '(not stated)'}")

    if not conflicts:
        # #3585: every pairing it reported was one it could not articulate, so
        # this call produced no usable verdict, and it halts unverified. It
        # used to proceed and record the unverified state (#2462, #2475);
        # under ADR 0236 "not checked" never goes on to draft. Filing these
        # would still block every later launch with a question nobody can
        # close, so they are named in the halt and never filed.
        count = len(unarticulated)
        noun = "conflict" if count == 1 else "conflicts"
        pairings = "; ".join(
            f"A: {c.get('criterion_a') or '(not stated)'} / "
            f"B: {c.get('criterion_b') or '(not stated)'} ({reason})"
            for c, reason in unarticulated
        )
        return _halt_unverified(
            state, answered_by,
            f"the analysis reported {count} {noun} and stated no divergence "
            f"for any, so nothing was verifiable: {pairings}",
            retried=False,
        )

    # #3747: a conflict halts the roll and asks the operator for a ruling only
    # when it reproduces. N0c is model-judged: on boostgauge #2's body,
    # unedited since 2026-08-16, the same model ruled it consistent at 23:07
    # and found two conflicts at 01:10. One draw is not a finding.
    print(
        f"  [N0c] {len(conflicts)} conflict(s) reported; asking again to "
        "confirm before halting (#3747)."
    )
    second_result = _invoke(provider)
    second = _verdict_of(second_result)
    confirm_failure = ""
    if second is None:
        # Halting on the first answer is the conservative side: the second ask
        # failed to answer, it did not disagree. #3585: its cause is named, in
        # the log and in the halt message; it used to be dropped.
        confirm_failure = _no_verdict_reason(second_result)
        print(
            f"  [N0c] the confirming ask gave no verdict ({confirm_failure}); "
            "halting on the first answer's conflicts."
        )
    else:
        again = _articulated_conflicts(second)
        confirmed = [c for c in conflicts if _reported_again(c, again)]
        for c in conflicts:
            if c not in confirmed:
                print("  [N0c] not reproduced, not filed:")
                print(f"          A: {c.get('criterion_a') or '(not stated)'}")
                print(f"          B: {c.get('criterion_b') or '(not stated)'}")
        if confirmed:
            conflicts = confirmed
        else:
            # Not a failure path (#3767). The check ran twice and both asks
            # answered; #3747's rule is that a conflict halts only when it
            # reproduces, and none did. Proceeding is the check's verdict,
            # and each dropped conflict is printed above, never silent.
            print(
                "  [N0c] Requirements internally consistent: no reported "
                "conflict reproduced on a second ask."
            )
            print(f"  [N0c] Verdict from {answered_by}.")
            return {}

    message = _format_conflict_message(conflicts, unarticulated)
    if confirm_failure:
        message += (
            f"\n\nNot confirmed by a second ask: it gave no verdict "
            f"({confirm_failure}), so this halts on the first answer."
        )
    print(f"  [N0c] {message}")

    # #2072: the finding used to go to a run log and nowhere else, and N0c is
    # LLM-judged, so a lenient redraw could pass the same text minutes later and
    # roll over an unresolved ambiguity. File it where a human will see it.
    # Never changes the halt outcome: the roll was already halting, and a filing
    # failure returns the same error_message.
    # #2074: count it too. The must-resolve issue is the human-facing record;
    # this is the one a rate is computed from.
    # #3585: each failure below alerts the operator with its own record. The
    # halt alerts too, but names only the conflict, so a lost telemetry row
    # or an unfiled question would otherwise be known to nobody.
    from assemblyzero.core import alert

    repo = state.get("target_repo") or "."
    issue_number = int(state.get("issue_number") or 0)
    try:
        from assemblyzero.speedrun.must_resolve import run_context
        from assemblyzero.speedrun.prompt_telemetry import record_failures

        run_id, _ = run_context()
        record_failures(
            repo,
            [str(c.get("criterion_a", "")) for c in conflicts],
            stage="lld",
            check="requirements-conflict",
            issue=issue_number or None,
            drafter_model=drafter_spec,
            run_id=run_id,
        )
    except Exception as exc:  # noqa: BLE001 - alerted; the halt below stands
        alert.alert_operator(
            what=f"record the requirements-conflict telemetry for issue #{issue_number} in {repo}",
            where="assemblyzero.workflows.requirements.nodes.analyze_requirements.analyze_requirements (N0c)",
            cause=f"{type(exc).__name__}: {exc}",
            consequence="the conflict halt stands; its row is missing from the prompt-failure rate",
            repo=repo,
            issue=issue_number or None,
        )

    try:
        from assemblyzero.speedrun.must_resolve import file_all_conflicts

        file_all_conflicts(repo, issue_number, conflicts)
    except Exception as exc:  # noqa: BLE001 - alerted; the halt below stands
        # The stdout line is the standalone pre-check's contract: it reads
        # "must-resolve filing failed" from the gate's captured output.
        print(f"  [N0c] must-resolve filing failed ({exc}); halting anyway.")
        alert.alert_operator(
            what=f"file the must-resolve question(s) for issue #{issue_number} in {repo}",
            where="assemblyzero.workflows.requirements.nodes.analyze_requirements.analyze_requirements (N0c)",
            cause=f"{type(exc).__name__}: {exc}",
            consequence=(
                "the conflict halt stands, but no must-resolve issue records "
                "it; a lenient redraw could pass the same text later (#2072)"
            ),
            repo=repo,
            issue=issue_number or None,
        )

    return {"error_message": message}
