# Implementation Report: the bench (#3566)

Parent: #3562. Built on #3563 (seats and profiles) and #3565 (the per-call record).

## What was asked

`--models` on the roll, `orchestrate.py` and the three standalone tools; the roll forwards it to every child; a roll refuses to resume under a profile other than the one the issue was rolled under, unless `--fresh`; `tools/compare_profiles.py` tables recorded rolls per profile and writes the table as Markdown; a runbook for the sequence and for what a new model costs to audition.

## What changed

| File | Change |
|---|---|
| `tools/orchestrate.py` | `--models` and `--seat` (`seats.add_profile_arguments`); the profile is loaded by the usual precedence (`--mock` selects `mock.toml`), printed as a seat table, announced to the run, and passed to `orchestrate()`. A profile that will not load exits 2 before any stage |
| `assemblyzero/workflows/orchestrator/graph.py` | `orchestrate(model_profile=...)`: a fresh state takes it; a resumed state keeps the snapshot it was persisted with, and a state from before profiles takes the invocation's; the state's snapshot becomes the run profile before the first stage |
| `assemblyzero/workflows/orchestrator/state.py` | `OrchestrationState.model_profile` declared |
| `assemblyzero/workflows/orchestrator/stages.py` | `_profile_keys(state)`: the lld, spec and impl stages put the snapshot into their sub-workflow's state, so every seat in every stage resolves under the run's profile |
| `tools/speedrun_roll.py` | `--models`; appended to the argv every `orchestrate.py` child receives, and carried on the detached relaunch; validated before any issue is reset or rolled (exit 91 names the problem); each run's START line names the profile; `profile_refusal` refuses a resume recorded under a different profile, naming both and both ways out, and stops with exit 93, having spent nothing |
| `tools/compare_profiles.py` (new) | reads the convergence record and every `calls.jsonl` under `docs/` and `data/`, and prints one row per profile: runs, issues rolled, issues landed, review verdicts, mean revisions per stage, calls per seat, wall time per stage, failures by node, and answer-key coverage; writes the table under `data/speedrun/comparisons/` |
| `docs/runbooks/0956-compare-model-profiles-on-boostgauge.md` (new) | the sequence, how to read the table, and what auditioning a new model costs: one profile file and one roll |

The three standalone tools gained `--models` in #3563.

## Decisions made here

- **The answer-key column is coverage, not a score.** `docs/audits/0907-answer-key-audit-boostgauge-2026-09-03.md` scores the pipeline's gates against the shipped code and defines no score for a roll's output. The column reports how many rolled issues the audit covers. Defining a score is a question for the operator (on #3562).
- **#3566's T1 names `speedrun_roll.py --dry-run`, which does not exist.** The flag is pinned instead by the parser, by the argv the detached relaunch receives, and by the run's START line. `orchestrate.py --dry-run` prints the profile's seat table before the plan.
- **`--models mock` is not a rehearsal.** It swaps the models, not the pipeline's mock mode, so the runbook says not to use it that way.
- **The runbook's commands are the roll's existing flags.** `--fresh` is the destructive one, and it keeps its own documented gates (#2409). The runbook went to `docs/runbooks/` as #3566 asks. Whether it needs the private runbook repository's review first is a question for the operator, recorded on #3562.

## What is not done

- The first real comparison, `gemini` against `claude` on boostgauge, is the operator's to run (#3566 requirement 5). The command is in the runbook and in the #3562 summary.
