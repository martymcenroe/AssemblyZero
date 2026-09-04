"""Every model call, as sent and as received (#2731).

The launch gate. Twelve launches were allowed on boostgauge #421 and all twelve
are spent; nothing relaunches until the recorded runs replay past the walls that
killed them (#2724). That question cannot be answered for two of the four
recorded runs, and the reason is here rather than in the replay runner.

## What the pipeline persisted, and why a replay outgrew it

The pipeline writes the artifacts it DERIVED from each response, not the
response. ``NNN-spec-draft.md`` is written after preamble stripping, pinning
adjudication and decision-table re-assertion; ``NNN-readiness-verdict.md`` is
markdown assembled from a parsed verdict. Neither is what the model said, and
nothing at all recorded the edit script a revision round sent or the prompt any
call was given.

So `assemblyzero.speedrun.replay` reconstructs: it derives SEARCH/REPLACE blocks
that carry recorded draft N to recorded draft N+1 and answers the round with
those. Counted over the four runs replayed on 2026-09-03, 0 of 18 synthesised
scripts failed to PARSE and the first APPLICATION failure landed at round 5 or
6 — the reconstruction is faithful for about five rounds, and then the
accumulated difference exceeds one exact-match anchor and the replay stops for a
reason that has nothing to do with the gate under test.

## What this module does instead

`RecordingProvider` wraps any transport and writes one line per call to
``calls.jsonl`` in the run-scoped lineage directory the run already claims. The
prompt as sent, the response as received, in call order, tagged with the stage,
the node and how many times that node has been entered.

`ReplayProvider` reads that file back and answers call N with recorded response
N — but only if the prompt the code sends at call N is the prompt the recording
holds. When it is not, it refuses and says where they differ, which turns "the
derived blocks stopped applying" into "the prompt at call 6 differs, here is the
diff". That is the difference between a replay that cannot reach the wall and
one that reports what changed on the way.

**A recording never costs a run.** Every write here returns False rather than
raising, exactly as `record_heal` and the convergence record do. The absence is
visible at the other end: `read_calls` reports what it could not read, and the
replay says which source it used, so a run with no recording reads as a run with
no recording and never as a run that replayed clean.

**The drafts and verdicts stay where they are.** They are what a human reads
when diagnosing a halt, and a raw call log is not a substitute for them.
"""

from __future__ import annotations

import difflib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from assemblyzero.core.llm_provider import LLMCallResult, LLMProvider

#: The recording, beside the lineage the run already writes. One per run,
#: because the lineage directory is run-scoped (#1467).
CALLS_FILENAME = "calls.jsonl"

#: Set by `speedrun_roll.py` for the whole roll. Absent outside a roll, and
#: recorded as "" rather than invented, for the reason `convergence` gives.
RUN_TAG_ENV = "SPEEDRUN_RUN_TAG"

#: How a replay says which source answered it. The report prints this, because
#: "the recording said so" and "a draft was reconstructed into a rule" are
#: different evidence and a reader deciding whether to launch is entitled to
#: know which they have.
SOURCE_RECORDING = "recording"
SOURCE_RECONSTRUCTION = "reconstruction"

#: How many lines of prompt difference a divergence report carries. A whole
#: 60,000-character prompt in an error message is unreadable; the first lines
#: that differ are the finding.
DIFF_LINES = 24


@dataclass
class CallContext:
    """Where the next model call is coming from, as the graph knows it.

    Set by `narrated()` on every node entry -- the one place every node already
    announces itself -- so a graph cannot grow a node whose calls are recorded
    without a stage and a node name.

    ``entry`` is how many times this node has been entered in this run. For a
    loop node that is the round, which is the number a replay's divergence
    report needs and which no transport could work out for itself.
    """

    stage: str = ""
    node: str = ""
    entry: int = 0
    audit_dir: str = ""


_context = CallContext()
_entries: dict[tuple[str, str], int] = {}


def set_context(stage: str, node: str, audit_dir: str) -> CallContext:
    """Record that the run has entered ``node`` of ``stage``."""
    key = (stage, node)
    _entries[key] = _entries.get(key, 0) + 1
    global _context
    _context = CallContext(
        stage=stage, node=node, entry=_entries[key], audit_dir=audit_dir or ""
    )
    return _context


def current_context() -> CallContext:
    return _context


def reset_context() -> None:
    """Forget the current node and every entry count.

    Called between rolls. Without it a second roll in one process continues the
    first roll's round numbering, and a recording that says round 7 for the
    first call of a run is worse than one that says nothing.
    """
    global _context
    _context = CallContext()
    _entries.clear()


def calls_path(audit_dir: Path | str) -> Path:
    return Path(audit_dir) / CALLS_FILENAME


def recording_is_armed() -> bool:
    """Whether there is somewhere to write. False outside a run."""
    return bool(_context.audit_dir)


def current_run_tag() -> str:
    """The roll's tag, or "" outside a roll. Never invented."""
    return os.environ.get(RUN_TAG_ENV, "").strip()


def _append(audit_dir: str, record: dict) -> bool:
    try:
        path = calls_path(audit_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except Exception:  # noqa: BLE001 - a recording must never cost a roll
        # fail-open: a run that cannot write its recording still has to finish.
        # The absence is visible downstream -- `read_calls` returns nothing and
        # the replay reports that it fell back to reconstruction -- so nothing
        # here can be mistaken for a run that replayed clean.
        return False


def read_calls(audit_dir: Path | str) -> tuple[list[dict], int]:
    """Every readable call, in sequence order, and how many lines were not.

    The unreadable count is returned rather than logged, for the reason
    `convergence.read_records` gives: a caller that reports "11 calls" while
    silently dropping two corrupt lines is stating a number it did not count.
    """
    path = calls_path(audit_dir)
    if not path.exists():
        return [], 0
    calls: list[dict] = []
    unreadable = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            # fail-open: one truncated line -- a roll killed mid-write -- must
            # not make the whole recording unreadable. It is COUNTED rather
            # than dropped, so no caller reports a call count it did not count.
            unreadable += 1
            continue
        if isinstance(parsed, dict) and "seq" in parsed:
            calls.append(parsed)
        else:
            unreadable += 1
    calls.sort(key=lambda c: int(c.get("seq", 0) or 0))
    return calls, unreadable


class RecordingProvider(LLMProvider):
    """A transport that writes down what it was asked and what it answered.

    Wraps rather than replaces: the inner provider does the work and every
    field of its result is passed through untouched. This class only writes a
    line, and only when the graph has told it where.
    """

    def __init__(self, inner: LLMProvider, *, audit_dir: str = "") -> None:
        self.inner = inner
        self._audit_dir = audit_dir

    @property
    def provider_name(self) -> str:
        return self.inner.provider_name

    @property
    def model(self) -> str:
        return self.inner.model

    def invoke(
        self,
        system_prompt: str,
        content: str,
        timeout_seconds: int = 300,
        response_schema: dict | None = None,
        json_schema: dict | None = None,
    ) -> LLMCallResult:
        started = time.monotonic()
        result = self.inner.invoke(
            system_prompt, content, timeout_seconds, response_schema, json_schema
        )
        context = current_context()
        destination = self._audit_dir or context.audit_dir
        if destination:
            _append(destination, {
                "seq": _next_seq(destination),
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "run_tag": current_run_tag(),
                "stage": context.stage,
                "node": context.node,
                "round": context.entry,
                "provider": self.inner.provider_name,
                "model": self.inner.model,
                # Verbatim, both of them. A length or a hash would answer
                # "did something change" and not "what changed", and the
                # second question is the one a divergence report exists for.
                "system_prompt": system_prompt or "",
                "content": content or "",
                "response": result.response or "",
                "success": bool(result.success),
                "error_message": result.error_message or "",
                "duration_ms": int((time.monotonic() - started) * 1000),
                "has_schema": bool(response_schema or json_schema),
            })
        return result


def _next_seq(audit_dir: str) -> int:
    """One past the highest sequence number already on disk.

    Counted from the file rather than from a counter in memory, so a resumed
    run appends after the calls the first process wrote instead of restarting
    at 1 and producing two call number 1s in one recording.
    """
    calls, _ = read_calls(audit_dir)
    return (max((int(c.get("seq", 0) or 0) for c in calls), default=0)) + 1


@dataclass
class Divergence:
    """Where a replay stopped fitting the recording."""

    seq: int
    field: str
    recorded_head: str
    actual_head: str
    diff: str

    def describe(self) -> str:
        return (
            f"ReplayProvider: the {self.field} at call {self.seq} differs from "
            f"the recording, so the recorded response is no longer the response "
            f"this prompt would have drawn. Replay stops here rather than "
            f"answering with it (#2731).\n{self.diff}"
        )


class ReplayProvider(LLMProvider):
    """A transport made of one run's recorded calls, answered in order.

    The difference from `ScriptedProvider`, and the whole of #2731: this
    matches on the PROMPT, byte for byte, rather than on a regex over a
    reconstructed rule. Call N is answered with recorded response N only when
    the code sends recorded prompt N. Anything else is a divergence with a
    diff, which is a finding a reader can act on, rather than a rule that
    quietly stopped applying.
    """

    def __init__(self, calls: list[dict], *, model: str = "replay") -> None:
        self._calls = sorted(calls, key=lambda c: int(c.get("seq", 0) or 0))
        self._model = model
        self._index = 0
        self.divergence: Divergence | None = None
        #: (stage, node, round) of each call served, in order. A replay that
        #: reaches the right end state by the wrong route is a defect an
        #: end-state assertion does not catch.
        self.path: list[tuple[str, str, int]] = []

    @property
    def provider_name(self) -> str:
        return "replay"

    @property
    def model(self) -> str:
        return self._model

    @property
    def served(self) -> int:
        return self._index

    @property
    def recorded(self) -> int:
        return len(self._calls)

    def invoke(
        self,
        system_prompt: str,
        content: str,
        timeout_seconds: int = 300,
        response_schema: dict | None = None,
        json_schema: dict | None = None,
    ) -> LLMCallResult:
        seq = self._index + 1
        if self._index >= len(self._calls):
            return self._refuse(Divergence(
                seq=seq, field="call count",
                recorded_head="", actual_head="",
                diff=(
                    f"the recording holds {len(self._calls)} call(s) and the "
                    f"code is making call {seq}. The run has gone further than "
                    f"the recording did, so there is nothing faithful to "
                    f"answer with."
                ),
            ))

        call = self._calls[self._index]
        for field_name, actual in (
            ("system prompt", system_prompt or ""),
            ("content", content or ""),
        ):
            key = "system_prompt" if field_name == "system prompt" else "content"
            recorded = str(call.get(key, "") or "")
            if recorded != actual:
                return self._refuse(Divergence(
                    seq=seq,
                    field=field_name,
                    recorded_head=recorded[:200],
                    actual_head=actual[:200],
                    diff=_diff(recorded, actual),
                ))

        self._index += 1
        self.path.append((
            str(call.get("stage", "")),
            str(call.get("node", "")),
            int(call.get("round", 0) or 0),
        ))
        return LLMCallResult(
            success=bool(call.get("success", True)),
            response=str(call.get("response", "") or ""),
            raw_response=None,
            error_message=str(call.get("error_message", "") or "") or None,
            provider="replay",
            model_used=str(call.get("model", self._model) or self._model),
            duration_ms=0,
            attempts=1,
        )

    def _refuse(self, divergence: Divergence) -> LLMCallResult:
        self.divergence = divergence
        return LLMCallResult(
            success=False,
            response=None,
            raw_response=None,
            error_message=divergence.describe(),
            provider="replay",
            model_used=self._model,
            duration_ms=0,
            attempts=1,
        )


def _diff(recorded: str, actual: str) -> str:
    """The first lines where two prompts differ, as a unified diff."""
    lines = list(difflib.unified_diff(
        recorded.splitlines(), actual.splitlines(),
        fromfile="recorded", tofile="sent", lineterm="", n=1,
    ))
    if not lines:
        return "(the texts differ only in trailing whitespace or line endings)"
    shown = lines[:DIFF_LINES]
    if len(lines) > DIFF_LINES:
        shown.append(f"... and {len(lines) - DIFF_LINES} more diff line(s)")
    return "\n".join(shown)


@dataclass
class RecordingSummary:
    """What a recording holds, counted for the report."""

    calls: int = 0
    unreadable: int = 0
    stages: list[str] = field(default_factory=list)
    run_tags: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.calls > 0


def summarize(audit_dir: Path | str) -> RecordingSummary:
    """Read a recording and say what is in it, without loading it into a rule."""
    calls, unreadable = read_calls(audit_dir)
    return RecordingSummary(
        calls=len(calls),
        unreadable=unreadable,
        stages=sorted({str(c.get("stage", "")) for c in calls if c.get("stage")}),
        run_tags=sorted({str(c.get("run_tag", "")) for c in calls if c.get("run_tag")}),
    )
