"""The convergence record the graph writes for itself (#2721).

`factory_report.py` learned to say how each run ended by parsing the closing
`STAGE / VERDICT` table and the `Error:` line out of a prose log (#2717). That
is a bridge, and it has the failure a parser of prose always has: a run whose
banner never printed -- the process died mid-call, 19 of boostgauge's 180 runs
-- leaves nothing to read, and a change to the banner's wording silently
changes what the report counts.

The operator's ruling of 2026-09-02: the convergence number is not a prose field
in a handoff and not a line in CLAUDE.md. It is a row the graph wrote.

So the graph writes it. Three event kinds, appended to one JSONL beside the
other per-repo speedrun stores:

* ``stage.enter`` -- the orchestrator entering a pipeline stage, with its
  position in `STAGE_ORDER`.
* ``node.enter`` -- a sub-workflow node, with its position in that graph's
  atlas. Emitted from `narrated()`, which is already the single place every
  graph announces a node, so no graph can grow a node that forgets to record.
* ``run.terminal`` -- one per run, written where the outcome is actually known:
  the outcome, the furthest stage and node reached, and the registry key of the
  gate that ended it.

**A record never costs a run.** Every function here returns False rather than
raising, exactly as `record_heal` does. That is a deliberate fall-through and it
is loud in the only way that matters: `read_records` reports what it could not
read, and the report says which source it used, so a run with no record is
visible as a run with no record rather than as a run that passed.

**Why the tag can be empty.** `SPEEDRUN_RUN_TAG` is set by the launcher, so a
roll has one and a standalone workflow invocation does not. An unknown tag is
recorded as `""` and the reader keys on it honestly, rather than inventing a
tag that would merge unrelated runs into one.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

#: One store, beside `heals.jsonl` and `prompt-failures.jsonl`. Under
#: `data/speedrun/telemetry/`, which is structurally exempt from every janitor.
RECORDS_FILENAME = "run-records.jsonl"

#: Set by `speedrun_roll.py` for the whole roll. Absent outside a roll.
RUN_TAG_ENV = "SPEEDRUN_RUN_TAG"

EVENT_STAGE_ENTER = "stage.enter"
EVENT_NODE_ENTER = "node.enter"
EVENT_RUN_TERMINAL = "run.terminal"
EVENTS: tuple[str, ...] = (
    EVENT_STAGE_ENTER, EVENT_NODE_ENTER, EVENT_RUN_TERMINAL,
)

OUTCOME_PASSED = "passed"
OUTCOME_FAILED = "failed"
OUTCOMES: tuple[str, ...] = (OUTCOME_PASSED, OUTCOME_FAILED)

#: What ended the run, when it was not a registry gate. `cap:` is a budget
#: naming itself; `finalize` is a run that reached the end.
KEY_FINALIZE = "finalize"
CAP_PREFIX = "cap:"

#: How the reader says where a fact came from. The report prints this, because
#: "the record said so" and "a banner was parsed" are different evidence and a
#: reader deciding whether to launch is entitled to know which they have.
SOURCE_RECORD = "record"
SOURCE_BANNER = "banner"


def records_path(repo_root: Path | str) -> Path:
    return Path(repo_root) / "data" / "speedrun" / "telemetry" / RECORDS_FILENAME


def current_run_tag() -> str:
    """The roll's tag, or "" outside a roll. Never invented."""
    return os.environ.get(RUN_TAG_ENV, "").strip()


def _append(repo_root: Path | str, record: dict) -> bool:
    try:
        path = records_path(repo_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        return True
    except Exception:  # noqa: BLE001 - the record must never cost a roll
        # fail-open: a run that cannot write its record still has to finish.
        # The absence is visible downstream -- `read_records` returns nothing
        # for the run and the report falls back to the banner and says so --
        # so nothing here is mistaken for a run that passed.
        return False


def _base(event: str, run_tag: str) -> dict:
    return {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event,
        "run_tag": run_tag or current_run_tag(),
    }


def record_stage_enter(
    repo_root: Path | str,
    stage: str,
    ordinal: int,
    total: int,
    *,
    run_tag: str = "",
) -> bool:
    """The orchestrator entering one pipeline stage."""
    record = _base(EVENT_STAGE_ENTER, run_tag)
    record.update({"stage": stage, "ordinal": ordinal, "total": total})
    return _append(repo_root, record)


def record_node_enter(
    repo_root: Path | str,
    stage: str,
    node: str,
    ordinal: int,
    total: int,
    *,
    run_tag: str = "",
) -> bool:
    """One sub-workflow node, at the moment it is entered."""
    record = _base(EVENT_NODE_ENTER, run_tag)
    record.update(
        {"stage": stage, "node": node, "ordinal": ordinal, "total": total}
    )
    return _append(repo_root, record)


def record_terminal(
    repo_root: Path | str,
    *,
    outcome: str,
    furthest_stage: str,
    furthest_node: str = "",
    gate_key: str = "",
    run_tag: str = "",
) -> bool:
    """The one record per run that says how it ended.

    Written where the outcome is known rather than where it is printed, so a run
    whose banner never reached the log still leaves the fact behind.
    """
    record = _base(EVENT_RUN_TERMINAL, run_tag)
    record.update(
        {
            "outcome": outcome,
            "furthest_stage": furthest_stage,
            "furthest_node": furthest_node,
            "gate_key": gate_key,
        }
    )
    return _append(repo_root, record)


def read_records(repo_root: Path | str) -> tuple[list[dict], int]:
    """Every readable record, and how many lines were not readable.

    The unreadable count is returned rather than logged, because a caller that
    reports "12 runs recorded" while silently dropping three corrupt lines is
    stating a number it did not count.
    """
    path = records_path(repo_root)
    if not path.exists():
        return [], 0
    records: list[dict] = []
    unreadable = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            # fail-open: one truncated line -- a roll killed mid-write -- must
            # not make the whole store unreadable. It is COUNTED rather than
            # dropped, and the count is returned, so no caller can report a
            # number of runs while silently having lost some.
            unreadable += 1
            continue
        if isinstance(parsed, dict) and parsed.get("event") in EVENTS:
            records.append(parsed)
        else:
            unreadable += 1
    return records, unreadable


def terminals_by_run(records: list[dict]) -> dict[str, dict]:
    """The terminal record for each run that wrote one.

    The LAST terminal for a tag wins. A resumed run appends a second terminal,
    and the later one is the one that describes how the run actually ended.
    Records with no tag are dropped rather than merged under one blank key,
    which would make several unrelated runs look like one.
    """
    out: dict[str, dict] = {}
    for record in records:
        if record.get("event") != EVENT_RUN_TERMINAL:
            continue
        tag = record.get("run_tag") or ""
        if not tag:
            continue
        out[tag] = record
    return out


def furthest_by_run(records: list[dict]) -> dict[str, tuple[str, str]]:
    """(stage, node) of the highest-ordinal entry each run reached.

    Read from the entry events rather than from the terminal record, so a run
    that died before writing a terminal still says how far it got -- which is
    exactly the 19 killed runs the banner parse can say nothing about.
    """
    # A stage ordinal and a node ordinal are different scales and must never be
    # compared to each other: the stage decides how far the run got, and the
    # node only says how far INTO that stage. So the best stage is tracked
    # first, and a node counts only while it belongs to that stage -- a node
    # ordinal from an earlier stage cannot overtake a later stage's.
    best_stage: dict[str, tuple[int, str]] = {}
    best_node: dict[str, tuple[int, str]] = {}
    for record in records:
        event = record.get("event")
        tag = record.get("run_tag") or ""
        if not tag or event not in (EVENT_STAGE_ENTER, EVENT_NODE_ENTER):
            continue
        stage = str(record.get("stage", ""))
        ordinal = int(record.get("ordinal", 0) or 0)
        if event == EVENT_STAGE_ENTER:
            if ordinal > best_stage.get(tag, (-1, ""))[0]:
                best_stage[tag] = (ordinal, stage)
                best_node.pop(tag, None)
            continue
        if stage != best_stage.get(tag, (-1, ""))[1]:
            continue
        if ordinal > best_node.get(tag, (-1, ""))[0]:
            best_node[tag] = (ordinal, str(record.get("node", "")))
    return {
        tag: (stage, best_node.get(tag, (0, ""))[1])
        for tag, (_, stage) in best_stage.items()
    }
