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

### utils/ast_sentinel.py (2 sites)

- **A file that does not parse raises** (472). `analyze_source` raises `SentinelCannotRun` naming the file, the line and the syntax error, chained from the `SyntaxError`. It used to return a `<syntax>` finding, which the mechanical validator filed as the advisory "symbol '<syntax>' may not be imported".
- **A file that cannot be read raises** (498). `analyze_file` raises `SentinelCannotRun` for an `OSError` or `UnicodeDecodeError`, naming the path. It used to return an `<io>` finding.
- An undefined name is still a finding in the result; only "could not check" moved to a raise.

Caller that still swallows the raise: `workflows/requirements/nodes/validate_mechanical.py` `run_ast_sentinel_on_modify_files` catches `Exception` and logs at DEBUG (its own loud-failure baseline entry). Until it is fixed, a broken file goes from an advisory warning to nothing.

Compliance: the raise carries what and where (the file) and the cause; stopping and alerting fall to the caller, which is in the requirements package.

### utils/lld_verification.py (1 site; 1 compliant row)

- **The path check always runs** (307). `run_verification_gate` validated the LLD path only when a `project_root` was passed; without one the security check was skipped and the gate went on to pass the file. It now always calls `validate_lld_path`, which uses the current directory when no root is given, as its docstring says.
- The `ValueError` handler at 282 already raises `LLDVerificationError`; the ledger marks it compliant and it is unchanged.

No caller in `assemblyzero/` or `tools/` calls `run_verification_gate`; `utils/__init__.py` re-exports it.

### utils/lld_path_enforcer.py (1 site, won't do)

- **No Section 2.1 stays an empty spec** (97, won't do). The ledger asks for a raise. On a real implementation run the content passed in is the implementation spec (`load_lld` stores it under `lld_content`), whose files table is `## 2. Files to Implement`; it has no Section 2.1 by design. The implementation node adds every path of that table to the allowed set itself. A raise would halt every implementation run, so the empty answer is the contract. The docstring now says so, and a test pins it.

### utils/codebase_reader.py (7 sites)

The reader builds the codebase context the requirements drafter works from. A file it selected that could not be read used to come back empty and was dropped from the batch, so the draft was built on a partial context with nothing said.

- **A file that cannot be stat'd, resolved or read raises** (152, 171, 201) `CodebaseReadError` naming the file and the cause. `read_files_within_budget` stops on it instead of dropping the file.
- **A symlink that escapes the repo raises** (164), naming the link and where it resolves, and none of the content. It was a WARNING and an empty result.
- **A text file that is not valid in its encoding raises** (198). Binary extensions are still skipped before the read; a file that reaches the read was taken to be text.
- **A `pyproject.toml` or `package.json` that does not parse raises** (340, 369), naming the file. It read as `{}`, and a broken `pyproject.toml` silently fell through to `package.json`.
- Kept quiet, by contract and in the docstrings: a file that does not exist, is not a regular file, has a binary extension or matches a sensitive pattern, and a repo with no config file.

Caller: `workflows/requirements/nodes/analyze_codebase.py` has no handler around these calls, so the raise leaves the node uncaught; it is not routed to HALT. Baseline: the two `parse_project_metadata` handler entries leave.

### speedrun/convergence.py (5 sites) and the one consumer line in factory_report.py (802)

- **A record that cannot be appended alerts and raises** (90, 91). `_append` returned False, which every caller ignored, so the factory report fell back to the banner for that run. It now alerts with the store path, the event, stage and node, and the cause, then raises. `record_stage_enter`, `record_node_enter` and `record_terminal` return True only once the line is on disk. A follow-up commit moves the store-path computation inside the alerted region: a root the path cannot be built from (a NUL byte) raised unalerted in the first version.
- **A line that is not a record alerts and raises** (185, 186, 195). `read_records` counted such a line, and its one consumer, `factory_report.apply_records` (802), threw the count away, so the report stated numbers from a store it had not fully read. It now alerts and raises `ValueError` naming the store and the line. The count only ever carried those lines, so it is gone: `read_records` returns the list of records, and `apply_records` takes the list.
- An absent store is still the quiet `[]`.
- The two `# fail-open:` tags are gone.

Callers that still swallow the raise: `workflows/narration.py` `_record_entry` (fixed in the next commit); `workflows/orchestrator/graph.py` `_record_stage_entry` and `_record_terminal` catch `Exception` and return. The operator is alerted before either swallows.

Baseline: three entries leave (`_append`'s handler and tag, `read_records`'s tag).

### workflows/narration.py (4 sites; 1 compliant row)

`narrated()` wraps every node of all three graphs, so each of these ran on every node of every run.

- **A node with no atlas entry fails the graph build** (64). It printed a plain line once and the run went on. `narrated()` now raises `ValueError` naming the node and the stage at wrap time; `test_graph_atlas.py` already holds every real graph to a complete atlas.
- **A narration line that cannot be built or printed alerts and raises** (114). A broken atlas entry, a state that raises, or a closed stdout was dropped with a bare `pass` and the node ran. Now the node does not run.
- **A convergence record that cannot be written stops the node** (160). The store alerts and raises; the wrap no longer swallows it, and adds no second alert. The `# fail-open:` tag is gone.
- **A call-recording context that cannot be set alerts and raises** (181). It was swallowed, so the node's model calls were recorded against the node before it. The tag is gone.
- The `TypeError` handler in `_gate_is_off` (55) is the documented "unknown gate" answer; the ledger marks it compliant and a test pins it.
- Kept, and documented: a state with no `repo_root` records nothing.

Defect found, not fixed (outside the ledger rows): the requirements workflow's state has no `repo_root` key (it carries `target_repo`), and no requirements node sets one. So `_record_entry` returns at its first check on every LLD node, and the LLD stage writes no `node.enter` records at all.

Baseline: five entries leave (`narrated._wrapped`'s handler; `_record_entry`'s handler and tag; `_set_call_context`'s handler and tag).
