# Implementation Report — Every standalone run leaves a record (#3503)

Backfilled 2026-09-25 after the merge, from PR #3520 (merge `0a178b00`) and its body (#3559). The report gate did not see the worktree-shaped commit that landed this PR, so no report was written at the time. Nothing was re-run for the backfill; every claim below is the PR's own.

Parent: #3502, stage 1.

## What changed

`assemblyzero/core/run_record.py` is new: `RunRecord` opens two files per run in the target repo's `data/speedrun/runs/`, beside the roll's, with the roll's tag shape (`<tool>-issue<N>-<HHMMSS>`). `<tag>.log` is everything the tool printed (stdout and stderr, teed); `<tag>-events.log` is start, node transitions, the crash record, the end, and what was left in place. The prefix is the tool's name rather than `run-`, because `factory_report.py` parses `run-issue*` as roll logs and a standalone run is not a roll.

Both standalone tools write it on every run, not only with `--speedrun`:

- `tools/run_requirements_workflow.py`: `run_single_workflow` opens the record before the header so the tag and log path are the first line; `run_resume_review` opens its own. Every exit path finishes the record; the generic `except` writes the crash record first.
- `tools/run_implement_from_lld.py`: the record opens after the dry-run exit, in the checkout's `data/`, not the worktree's. The stream loop reports each node, so the crash record names the last node. Every exit path finishes the record, including the `ImplementationError` branch and the fall-through `return 0`.

"Left in place" is read from the target by inspection: registered worktrees other than the main checkout, local and remote branches named `<issue>-*`, and the checkout's `git status --porcelain` (capped at 40 lines). It is written to the events log on crash and at the end, and printed at the end.

The record never raises into the run it records; every failure inside it becomes a warning line.

## What it does not do

The LLD graph is driven with `stream_mode="values"`, which carries no node names, so an LLD crash record says `last_node=unknown`. The speedrun instrumentation stays opt-in.

## Files

`assemblyzero/core/run_record.py`, `tests/fixtures/fail_open_baseline.json`, `tests/unit/test_run_record.py`, `tools/run_implement_from_lld.py`, `tools/run_requirements_workflow.py`.
