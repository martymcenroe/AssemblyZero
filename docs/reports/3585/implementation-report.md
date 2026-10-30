# Implementation Report: run-path modules outside the workflow packages under standard 0034 (#3585 step 5)

The rule is ADR 0236 and standard 0034. This branch takes the modules a workflow run passes through outside the three workflow packages: `workflows/narration.py`, `utils/`, `workflows/telemetry/` and `telemetry/`, `visual_gate/`, `hooks/` and `speedrun/`. Each module's ledger 0908 sites are fixed and tested, highest harm first: failures a run reads as success before failures that lose a record.

## Scope

A module is in scope when a run imports it. The import chain was read with `ast` from the three runners (`tools/run_requirements_workflow.py`, `tools/run_implement_from_lld.py`, `tools/run_implementation_spec_workflow.py`) and the three graph builders, following imports at module level and inside functions.

Not in this branch, because no run reaches them:
- utils: `github_metrics_client.py`, `markdown_inventory.py`, `metrics_aggregator.py`, `metrics_config.py`, `metrics_models.py`;
- telemetry: `telemetry/__main__.py`, `telemetry/sync.py`;
- visual_gate: `bundle.py`, `floor.py`, `gate.py`, `modify.py`, `server.py`, imported only inside the orchestrator's visual stage, which no runner runs (`run_implement_from_lld.py` takes only `impl_pr_body_path` from `orchestrator/stages.py`);
- speedrun: `answer_key.py`, `archive.py`, `box_health.py`, `emergency_stop.py`, `golden_disasters.py`, `healing.py` (imported only inside `factory_report.build_report`), `prompt_ranking.py`, `replay.py`, `roll_blockers.py`, `successes.py`, `timing.py`.

## Modules

### speedrun/requirements_status.py (3 sites)

The ledger exists so a roll whose requirements gate proceeded without a verdict cannot read as a verified roll. Losing a record, or a line of the ledger, hides that banner.

- **A record that cannot be written alerts and raises** (65). `record_unverified` used to return False, which its caller ignored. It now alerts with the ledger path and the cause and re-raises the `OSError` or `ValueError`.
- **A ledger line that cannot be read alerts and raises** (88, 90). A line that is not JSON, or is JSON but not an object, raises `ValueError` naming the file and line, after an alert. It used to be skipped.
- An absent ledger stays the quiet `[]`: no run has proceeded without a verdict.

Callers that still swallow the raise: `workflows/requirements/nodes/analyze_requirements.py` `_record_unverified` prints a WARNING; `tools/orchestrate.py` and `tools/speedrun_roll.py` `_requirements_unverified_lines` catch any exception around the read. Neither file is in this branch.

Compliance: each failure path writes an ERROR line through `alert_operator`, records what, where, cause and consequence, alerts, and raises.
