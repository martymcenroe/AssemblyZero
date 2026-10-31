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

### speedrun/prompt_telemetry.py (4 sites)

The store is where the rate of drafter validation failures is computed; each of these made the rate read lower than it was.

- **A failure with an empty detail is counted** (130), under the fingerprint `<stage>:<check>:empty-detail`, with the raw text kept. It returned None and wrote nothing.
- **A write that fails alerts and raises** (152), naming the store, the fingerprint and the cause. It printed through `log=print` and returned None. The `log` parameter only carried that message and is gone; `record_failure` always returns the record.
- **A store that exists but cannot be read alerts and raises** (180). An absent store is still `[]`, now by an existence check.
- **A line that is not a JSON object alerts and raises** (188), naming the line. It was skipped uncounted.

Callers that still swallow the raise: the three requirements nodes that record (`analyze_requirements.py`, `validate_mechanical.py`, `validate_test_plan.py`) and `orchestrator/stages.py` `_record_spec_convergence_failure` catch `Exception` and print or warn, so the halt they record is unchanged; the operator has been alerted first. The two readers, `factory_report.build_report` and `tools/prompt_failure_report.py`, let it out.

### workflows/telemetry/hallucination_log.py (3 sites)

The log is the baseline every invented-API detection is measured against.

- **An audit directory that was given but does not exist alerts and raises** `FileNotFoundError` (105). It was skipped silently. `None` still means "no such sink for this run".
- **A sink write that fails alerts and raises** (114, 123), naming the sink, the path and the cause. Each printed a WARNING to stdout and went on.
- Both sinks are always attempted; each failure alerts; the first is raised.

Caller that still swallows the raise: `workflows/implementation_spec/nodes/validate_completeness.py` wraps `_record_hallucination_telemetry` in `except Exception` and prints a WARNING, so the gate's verdict is unchanged; the operator has been alerted first.

Defect found, not fixed: a cold import of `assemblyzero.workflows.telemetry` (or of `hallucination_log`) fails with a circular import: `hallucination_log` imports `workflows.requirements.audit` at module level, which reaches `validate_completeness`, which imports the half-initialised telemetry package. A run imports the graphs first, so it never meets this; the new test file imports `validate_completeness` first for the same reason.

### visual_gate/config.py (2 sites)

- **A declared gate with no `renderer_cmd` is refused at load** (77). It got an empty command, which failed only at render time. Absent and empty both raise `ValueError` naming the key and the file.
- **A declared gate with no `separation_floor` is refused at load** (79). It got 0, which silently turned the palette-floor guardrail off, so a Modify that should have been refused passed. An explicit 0 is the repo's declared choice and still loads.
- No declaration file is still no gate (`None`).

Callers: `orchestrator/stages.py` `run_visual_stage` already turns a `ValueError` into a failed, non-transient stage result. `implementation_spec/nodes/compile_manifest.py` `_contract_text` catches `Exception`, prints, and compiles without the contract (a `# fail-open:` site of its own). `requirements/contract_fidelity.py` `resolve_contract` lets it out.

### utils/retry.py (1 site)

- **Giving up is an ERROR on stderr and in the log** (220). When `with_retry` stops (retries exhausted, or a failure not worth retrying) it still returns the last failed `LLMCallResult`, which is the declared contract every caller routes to HALT. What changed is how it says so: the halt line went to stdout and the log record was INFO. It now also writes `ERROR [RETRY] <call> failed after N attempt(s) [<class>]: <cause>; <reason>` to stderr and logs it at ERROR.

Callers: `workflows/testing/nodes/review_test_plan.py` and `revise_test_plan.py` return the failure as `error_message`; their routing to HALT is the testing package's.

### utils/process.py (2 sites)

`kill_process_tree` ends a timed-out model call and everything it spawned, so the drain after it does not block on a grandchild holding the pipes (the #1874 hang).

- **A `taskkill` that fails raises** (33). Its exit code was never read. Now 0 and 128 ("not found") are quiet; any other code raises `ProcessTreeKillError` with the code and stderr.
- **A kill the OS refuses, or a `taskkill` that times out, raises** (41). Every `OSError` and the timeout were swallowed as "already dead". Now only `ProcessLookupError` is quiet; the rest raise `ProcessTreeKillError` naming the pid and the cause, after an ERROR line on stderr and in the log.

Callers: `core/llm_provider.py` (`_kill_process_tree`, on the idle and wall timeouts and the storm probe) and `core/gemini_client.py` (the agy timeout). Neither catches it: a tree that survived its kill now ends the call loudly instead of reporting a clean timeout.

### utils/workflow_timeout.py (1 site)

- **The timeout alerts before it exits** (74). The timer printed a banner to stderr and called `os._exit(42)`, never reaching `alert_operator`, so a run that died on its wall clock told nobody away from the console. The handler is now `WorkflowTimeout._expire`: banner, then `alert_operator` with the limit, the workflow and the issue, then `os._exit(42)` in a `finally`, so the process still exits when the alert cannot be delivered.
- `WorkflowTimeout` takes optional `issue` and `workflow` keywords for the alert. The three runners do not pass them yet (they are not in this branch), so the alert says "workflow unnamed" until they do.

### telemetry/cost.py (1 site)

- **An unpriced model has no estimate, not a free one** (73). `estimate_cost` returned 0.0 with a WARNING, so the call record of an unpriced model read exactly like a call that cost nothing. It now returns None, the ledger's second option ("return None that callers must handle"). The record field `cost_usd_estimate` is already `Optional[float]`, the one caller (`InstrumentedCall.__exit__`) stores the value as given, and a sum that meets None raises instead of counting it as zero.

### utils/speedrun.py (3 sites)

The speed-run record is opt-in (`--speedrun`), and when it is on it is the durable cross-attempt record.

- **A lap split that cannot be written alerts and raises** (144), naming the file, the issue and the attempt. It was a WARNING.
- **A run-log entry that cannot be appended alerts and raises** (320). It was a WARNING.
- **A malformed run-log line alerts and raises** `ValueError` naming the log and the line (335). It was skipped with a WARNING, so the summary counted fewer attempts than the log holds.

Callers: the runners' `_finalize_speedrun` (`tools/run_requirements_workflow.py`, `tools/run_implement_from_lld.py`) and `tools/speedrun_summarize.py` do not catch.

### telemetry/store.py (4 sites)

- **A call record that cannot be written alerts and raises** (71). `CallStore.write` swallowed every exception at WARNING and the record was lost.
- **A corrupt line in a day's file alerts and raises** (88), naming the file and the line. It was skipped at WARNING.
- **A `calls-*.jsonl` file whose name holds no date alerts and raises** (114). It was skipped silently.
- **A corrupt line met by `query` alerts and raises** (127). It was skipped silently.
- A disabled store, and a day with no file, stay quiet.

Callers: `InstrumentedCall.__exit__` writes through it; its one user is `assemblyzero/nodes/anthropic_provider.py`, which no run reaches. Baseline: `CallStore.write`'s handler entry leaves.

### telemetry/emitter.py (9 sites: 7 fixed, 2 won't do, and 1 compliant row)

Every runner imports `emit`, `flush` and `track_tool`, and two register `flush` with `atexit`; graph routers and implementation nodes call `emit`. The module was fire-and-forget: every failure was a bare `pass` or a silent `None`.

- **A credentials file that exists but cannot be loaded raises** `TelemetryConfigError` (68), on every emit and flush, with an ERROR line each time and one alert per process. The cause names the exception type and the path, never the file's contents. Nothing is cached on failure.
- **An event the buffer cannot take alerts and raises** (84). It was dropped with a bare `pass`.
- **A failed DynamoDB write is an ERROR line, and the event is buffered** (151), with one alert per process: an outage fails every emit, and one email says so.
- **An event that cannot be built alerts and raises** (156). The outer `pass` is gone.
- **A buffered event that fails to upload stays buffered** (192), with an ERROR line naming the file and line, and one alert per process.
- **A buffer file that cannot be read or rewritten alerts and raises** (200), saying how many events were uploaded before it. The outer `pass` around the whole flush is gone (203).
- **Won't do, 54: no credentials file is local-only mode.** Every event is kept in the buffer, so nothing is lost, and the opt-out is `ASSEMBLYZERO_TELEMETRY=0`. An alert here would send one email per process from every machine without upload credentials, and would put an extra alert into whichever unit test emits first. Documented in the docstring and pinned.
- **Won't do, 171: `flush` with no client returns 0.** In local-only mode nothing was uploaded, so 0 is the true count; a raise would fail every runner's `atexit` flush on such a machine. Pinned. The sync CLI that prints "No buffered events to sync." on that 0 is `telemetry/sync.py`, which no run imports.
- The `track_tool` handler (237) re-raises; the ledger marks it compliant.

Callers: nothing catches the new raises, so a broken credentials file or a buffer that cannot take an event now stops the tool at its first emit. Baseline: seven entries leave.

### telemetry/actor.py (2 sites, loud but not raised)

`detect_github_user` labels every telemetry event.

- **`gh`'s exit code is read** (34). A non-zero exit was scanned anyway and fell through to "unknown". It now writes `ERROR [TELEMETRY] GitHub user not detected (gh auth status exited N)` to stderr, never `gh`'s output, and records "unknown".
- **`gh` missing or timing out is an ERROR line** (48), naming the exception type, instead of a bare `pass`. The handler is narrowed to `OSError` and `SubprocessError`.
- **`gh` is no longer asked for the token.** The call was `gh auth status --show-token`; the username line does not need it.
- **Not raised and not alerted, deliberately.** "unknown" is the label the docstring declares. Every `emit` calls this, and CI runs the unit tier with no `gh` login and with telemetry on, so a raise would fail every test that emits there, and an alert would land in whichever test emits first. Baseline: the handler entry leaves.

### speedrun/restore.py (4 sites)

`restore_artifact` rebuilds a missing pipeline input from the refs; the implementation run's `find_lld_path` calls it before concluding an LLD is absent.

- **A failing `git for-each-ref` raises** `RestoreError` with the command, the return code and stderr (46, 83). It returned no refs, so the search silently covered fewer of them.
- **A path outside the repo raises `ValueError`** (140). It was a tagged `return False`; the tag is gone.
- **A `git show` that fails for any reason but absence raises** `RestoreError` (150). Absence is a closed list of git's own messages: the ref does not exist, or the path is not on it. Those still move the search to the next ref.
- `False` now means only that no source holds the file.

Callers: `workflows/testing/nodes/load_lld.py` `find_lld_path` catches `Exception` around it and prints a WARN (a `# fail-open:` site of the testing package). `tools/speedrun_roll.py` (`_restore_artifact`, `_graveyard_leavings_refs`) lets it out. Baseline: the tag entry leaves.

### speedrun/must_resolve.py (18 sites, and 1 compliant row)

A requirements conflict halts the run and files a must-resolve question that the next launch refuses on. Every failure in that path printed a line to stdout and nothing more, and several read as success.

- **The halt is still never changed; every filing failure now alerts.** A new `_filing_failed` helper writes an ERROR line to the run log, calls `alert_operator` with what, where (the gate), the repository, the source issue, the cause and the consequence, and returns the failed result. That covers no GitHub remote (451), a recurrence comment that fails (465), an issue create that fails after the label retry (498), and a conflict with nothing to rule on (411, action still `rejected`).
- **A failed dedupe query is a failed filing, never "no existing issue"** (355, 359). `_find_existing` raises the new `MustResolveError` for a non-zero exit, an answer that is not JSON, or one that is not a list of issues; the filer files nothing, because filing without the check could duplicate an open question.
- **The label's own failure is reported** (372). `_ensure_label` returns gh's answer; when the retried create still fails, the cause names both exit codes and both stderrs. A label failure followed by a successful create is not reported: the created issue carries the label, which proves it exists.
- **An issue created with no number is a failure** (503): alert, nothing written to the ledger, the output named in the cause.
- **A ledger line that cannot be written is a failure** (443, 473, 509, 613). `record_filed` raises `OSError` naming the ledger (it returned False, which every call ignored) and `ValueError` for a call with neither a number nor a suppression reason; `file_must_resolve` alerts with the issue number and returns a failed result that still carries the number.
- **The ledger reads as empty only when it is absent** (630, 639). One that cannot be read alerts and re-raises; a line that is not JSON, not an object, or has a number that is not a whole number alerts and raises `ValueError` naming `path:line`. A line with no number (a suppressed replay filing) is still left out by contract.
- **The launch gate refuses when it cannot run** (527, 535, 539). `open_must_resolve_issues` keeps its `(issues, error)` contract and alerts on every error (no remote, gh failing, an answer that is not JSON or not a list). Its direct caller, `tools/speedrun_roll.py` at the launch gate, now prints BLOCKED and returns 91 where it warned and launched. `check_prereqs` already refused on the error; the run summary already says the list could not be read.
- **One conflict's filing raising alerts** (721) and is recorded failed; the remaining conflicts are still filed.
- 176 is compliant: `_default_runner` models a missing binary as exit 127, which every caller checks.

Callers that still swallow: `workflows/requirements/nodes/analyze_requirements.py` (around `file_all_conflicts`), `workflows/implementation_spec/nodes/review_spec.py` and `compile_manifest.py` (around `file_must_resolve`) catch `Exception` and print a WARNING. After this change only an undeliverable alert or a runner exception reaches them; the filing failures alert before they return. Those files are other branches' work.

Unit isolation: `tests/unit/conftest.py` gains `_must_resolve_gate_answers_offline`, which rebinds `speedrun_roll.open_must_resolve_issues` to "GitHub answered, nothing open". Twenty-three tests drive `speedrun_roll.main()` on a repository with no GitHub remote and relied on the gate warning and launching. The fixture follows the existing box-health bypass beside it.

Compliance: every failure path writes an ERROR line through `alert_operator` with what, where, identity, cause and consequence; the filer's halt is unchanged by contract, and the launch gate stops the launch. Baseline: the `file_all_conflicts` handler entry leaves.
