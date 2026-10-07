# Implementation Report: the sweep ledger, and core batch 1, where every halt alerts the operator (#3724, part of #3581)

## The ledger

`docs/audits/0908-loud-failure-sweep-ledger.md` lists every tracked file under `assemblyzero/` and `tools/`, generated from `git ls-files` at base `79e18ad1`: 466 files and 155,893 lines, counted rather than estimated.

The 47 files of `assemblyzero/core/` are marked read on 2026-10-07. Two delegated readers read every line of them. Each finding was then checked by script: its quoted line had to match the named file at the named line, and all 215 did. The 215 findings are recorded with file:line, what fails, what the code does now, the property each violates, and the fix. 190 of them are violations; 25 are judged compliant, with the contract that makes them so named.

## Core batch 1: the alerting backbone

- **`assemblyzero/core/halt_node.py`** (#3724): every halt calls `assemblyzero.core.alert.alert_operator` with the workflow, the stage, the issue, the repository and the cause. The call comes after the state snapshot and the recovery plan are saved, so an undeliverable alert, which raises, never costs the halt's own record.
  - The two handlers around the resume contract and the evidence bundle used to print `[WARN]` to stdout, under `# fail-open:` tags. Each now sends its own alert naming its failure, and both tags are gone.
  - An `audit_dir` the state names but which does not exist used to be skipped silently. It now raises inside those blocks, so the operator is told.
- **`assemblyzero/core/alert.py`**: a failed email still tries the Windows toast, because every channel is attempted. Every failure in the chain is printed, not just the last.
- **`assemblyzero/core/fail_open_audit.py`**: a handler that calls `alert_operator` counts as handled, as standard 0034 and the loud-failure check already say. The two HALT-node handlers were exempt only by their tags. Without this rule, the older audit would have reported them as new sites once the tags came out.
- **`tests/unit/conftest.py`**: the new autouse `operator_alerts` fixture replaces `alert_operator` with a recorder, so failure paths reached in a test record their alerts without any I/O. `test_alert.py`, which tests the real function, is exempt.

## Ledger entries fixed by this batch

`halt_node.py:229`, `:291`, `:297`, `:298`, `:344`, `:345`; `alert.py:164`; `recovery_plan.py:144`. The halt summary stays on stdout, but the halt's alert now writes the `ERROR` line to stderr.

## Baselines

- **Loud-failure baseline:** 333 down to 329 (two tags and two swallowed handlers in `halt_node.py`), with `BASELINE_CEILING` at 329.
- **Fail-open baseline:** regenerated because its denominator moved. Its frozen set is unchanged at 438.

## Loud-failure compliance (standard 0034)

| Site | Loud | Logged | Stops | Alerts |
|---|---|---|---|---|
| The HALT node | `ERROR [ALERT]` on stderr | workflow, stage, issue, repo, cause, state and plan paths | the run has already stopped at HALT | `alert_operator` |
| The resume-contract and evidence-bundle handlers | `ERROR [ALERT]` | the failure and its cause | the halt is already reported; the halt still returns | `alert_operator` |
| `alert_operator` itself | `ERROR [ALERT] NOT DELIVERED`, with every failure in the chain | — | raises `AlertDeliveryError` | — |

## Correction made while building this

The first version of a new test assumed that patching `halt_node.STATE_DIR` redirects where snapshots go. It does not; `tests/conftest.py` already redirects every binding per test (#3531), and the session-end check guards the real home. No test writes the operator's home state, and none did.
