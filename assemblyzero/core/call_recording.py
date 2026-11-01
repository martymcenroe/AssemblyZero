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

**A recording holds every call the run consumed, or the run stops** (ADR 0236,
#3772). A call the run used and the recording lacks makes every replay diverge
at it, as if the code had changed, which is the false finding this module exists
to replace. So a write that fails raises before the run consumes the call's
result, and a resume makes the call again and records it. A line that is not a
call record raises when the recording is read, naming the file and the line.
Writes here used to return False, which nothing read, and unreadable lines were
counted and dropped. One kind of line is still counted rather than read: a
final line with no newline, the write of a process that died in it, whose call
never reached the run. The replay says which source it used, so a run with no
recording reads as a run with no recording and never as a run that replayed
clean.

**The drafts and verdicts stay where they are.** They are what a human reads
when diagnosing a halt, and a raw call log is not a substitute for them.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from assemblyzero.core.llm_provider import LLMCallResult, LLMProvider

logger = logging.getLogger(__name__)

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


class RecordingError(RuntimeError):
    """The recording cannot be written, or read as a recording: the file, the
    line where there is one, and the cause (#3772).

    Not an ``OSError``, so no provider's transport handler reads it as a
    model call that could not be made.
    """


class SchemaNotDelivered(RuntimeError):
    """A run handed a schema to a transport that would not deliver it (#4483).

    Raised before the call, so the run does not pay for an answer in a shape
    nobody asked the model for, and the halt names the transport. Not an
    ``OSError``, for the reason ``RecordingError`` is not one.
    """


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


def _append(audit_dir: str, record: dict) -> None:
    """Append one call to the recording, or raise ``RecordingError`` (#3772).

    It used to return False, which nothing read: the run went on consuming a
    call the recording did not hold, and every replay of it diverged there.
    """
    path = calls_path(audit_dir)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError as exc:
        raise RecordingError(
            f"cannot append call {record.get('seq')} to the recording {path}: "
            f"{type(exc).__name__}: {exc}; the call's result is not used, so the "
            f"recording still holds every call the run consumed"
        ) from exc


def read_calls(audit_dir: Path | str) -> tuple[list[dict], int]:
    """Every call in the recording, in sequence order, and whether it ends in
    a write that did not complete (0 or 1).

    An absent recording is ``([], 0)``: a run that predates the recorder, or
    one with no audit directory, which is an answer.

    A final line with no newline is a write its process died in (a roll
    killed mid-write). The newline is part of every write, so the call it
    held never reached the run. It is not read and it is counted, so a
    caller can say the recording ends in one, and ``_next_seq`` refuses to
    append after it. It is not a failure of the recording, and is quiet.

    Every complete line must be a call record. One that is not JSON, or not
    an object with a ``seq``, raises ``RecordingError`` naming the file and
    the line (#3772). Such lines used to be counted and dropped: a replay of
    a recording with a call missing diverges at the gap as if the code had
    changed, and ``_next_seq`` numbered the next call into it.
    """
    path = calls_path(audit_dir)
    if not path.exists():
        return [], 0
    text = path.read_text(encoding="utf-8", errors="replace")
    complete, _, partial = text.rpartition("\n")
    calls: list[dict] = []
    for number, line in enumerate(complete.split("\n"), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except ValueError as exc:
            raise RecordingError(
                f"the recording {path} line {number} is not JSON ({exc}): {line[:80]!r}"
            ) from exc
        if not isinstance(parsed, dict) or "seq" not in parsed:
            raise RecordingError(
                f"the recording {path} line {number} is not a call record "
                f"(an object with a seq): {line[:80]!r}"
            )
        calls.append(parsed)
    calls.sort(key=lambda c: int(c.get("seq", 0) or 0))
    return calls, 1 if partial.strip() else 0


class RecordingProvider(LLMProvider):
    """A transport that writes down what it was asked and what it answered.

    Wraps rather than replaces: the inner provider does the work and every
    field of its result is passed through untouched. This class only writes a
    line, and only when the graph has told it where. A line it cannot write
    raises ``RecordingError`` and the call's result is not returned (#3772):
    the run never consumes a call its recording does not hold.
    """

    def __init__(
        self,
        inner: LLMProvider,
        *,
        audit_dir: str = "",
        spec: str = "",
        effort: str | None = None,
        seat: str = "",
    ) -> None:
        self.inner = inner
        self._audit_dir = audit_dir
        # #3565: what the call was asked for, so the record can say which
        # seat and spec it served and which model answered.
        self._spec = spec
        self._effort = effort
        self._seat = seat

    @property
    def provider_name(self) -> str:
        return self.inner.provider_name

    @property
    def model(self) -> str:
        return self.inner.model

    @property
    def delivers_schema(self) -> bool:
        return self.inner.delivers_schema

    @property
    def answers_from_script(self) -> bool:
        return self.inner.answers_from_script

    def invoke(
        self,
        system_prompt: str,
        content: str,
        timeout_seconds: int = 300,
        response_schema: dict | None = None,
        json_schema: dict | None = None,
    ) -> LLMCallResult:
        # #4483: every run passes through here, so this is where a schema that
        # would be dropped stops the run instead of reaching a model unasked.
        offered = bool(response_schema or json_schema)
        if offered and not self.delivers_schema and not self.answers_from_script:
            raise SchemaNotDelivered(
                f"{type(self.inner).__name__} ({self.inner.provider_name}) was "
                "handed a schema and does not deliver one to its model"
            )
        started = time.monotonic()
        result = self.inner.invoke(
            system_prompt, content, timeout_seconds, response_schema, json_schema
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        # #3565: the per-call model record, for every run with a record open,
        # whether or not an audit directory takes the bodies below.
        from assemblyzero.core.model_record import call_fields, record_call

        fields = call_fields(
            inner=self.inner, spec=self._spec, seat=self._seat,
            effort=self._effort, result=result, duration_ms=duration_ms,
        )
        context = current_context()
        record_call({**fields, "stage": context.stage, "node": context.node})
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
                "duration_ms": duration_ms,
                # #4483: what the model was given, not what a caller offered.
                # This read true on every call that lost its schema.
                "has_schema": offered and self.delivers_schema,
                # #3565: which seat and spec, and which model answered.
                # `provider` and `model` above stay as the replay reads them.
                **{k: v for k, v in fields.items() if k not in ("duration_ms", "success")},
            })
        return result


def _next_seq(audit_dir: str) -> int:
    """One past the highest sequence number already on disk.

    Counted from the file rather than from a counter in memory, so a resumed
    run appends after the calls the first process wrote instead of restarting
    at 1 and producing two call number 1s in one recording.

    A recording that ends in a write that did not complete raises
    ``RecordingError`` (#3772). The new call would be written onto the end
    of that partial line, and the two would read as one line that is not a
    call record. The count used to be discarded here, and that call was lost
    from the recording without a word.
    """
    calls, truncated = read_calls(audit_dir)
    if truncated:
        raise RecordingError(
            f"the recording {calls_path(audit_dir)} ends in a line whose write did "
            f"not complete (a process died in it), and a call appended now would be "
            f"joined to it; remove that partial last line, whose call never reached "
            f"the run, and resume"
        )
    return (max((int(c.get("seq", 0) or 0) for c in calls), default=0)) + 1


@dataclass
class Divergence:
    """Where a replay stopped fitting the recording."""

    seq: int
    field: str
    recorded_head: str
    actual_head: str
    diff: str
    #: Set when the recording itself cannot answer the call, rather than the
    #: prompt having changed: what is missing from the recorded call.
    why: str = ""

    def describe(self) -> str:
        if self.why:
            return (
                f"ReplayProvider: call {self.seq} cannot be answered from the "
                f"recording: {self.why}. Replay stops here rather than guess "
                f"(#3772).\n{self.diff}"
            )
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

    answers_from_script = True

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

        if "success" not in call:
            # #3772: this read a missing outcome as a success, so a failed
            # call recorded without one would replay as an answer.
            return self._refuse(Divergence(
                seq=seq, field="success",
                recorded_head="", actual_head="",
                diff=(
                    f"recorded call {seq} matches the prompt but carries no "
                    f"success field; the recorder writes one on every call"
                ),
                why="its record does not say whether the call succeeded",
            ))

        self._index += 1
        self.path.append((
            str(call.get("stage", "")),
            str(call.get("node", "")),
            int(call.get("round", 0) or 0),
        ))
        return LLMCallResult(
            success=bool(call["success"]),
            response=str(call.get("response", "") or ""),
            raw_response=None,
            error_message=str(call.get("error_message", "") or "") or None,
            provider="replay",
            model_used=str(call.get("model", self._model) or self._model),
            duration_ms=0,
            attempts=1,
        )

    def _refuse(self, divergence: Divergence) -> LLMCallResult:
        """A failed call naming where the replay stopped, loud where it stops.

        Returned, not raised: a failed ``LLMCallResult`` is every provider's
        contract, the node that asked reports it as its error, and the replay
        runner reads ``divergence``. What was missing is the ERROR line on
        stderr at the point of refusal (#3772).
        """
        self.divergence = divergence
        message = divergence.describe()
        logger.error("[REPLAY] %s", message)
        print(f"ERROR [REPLAY] {message}", file=sys.stderr, flush=True)
        return LLMCallResult(
            success=False,
            response=None,
            raw_response=None,
            error_message=message,
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
    #: 1 when the recording ends in a write that did not complete (see
    #: ``read_calls``); any other line that is not a call record raises.
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
