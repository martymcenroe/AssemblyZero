# Audit 0855 — Orchestrator Analysis: Phase B Claim Enumeration

**Issue:** #1390
**Date:** 2026-05-29
**Status:** Phase B (claim enumeration) in progress
**Methodology:** As stated in #1390. Every claim is atomic, identified, commit-pinned. Phase C will add citations; Phase D will mark each as `CONFIRMED`, `REFUTED`, or `UNCERTAIN` after blind independent verification.

This document is the working artifact for Phases B through D. It is not yet the cross-reference deliverable (deliverable three of #1390); that will be written in Phase E from `CONFIRMED` claims only.

## Commit pins

Three commits are referenced by the claims below.

| Pin label | SHA | Description |
|-----------|-----|-------------|
| `PRE-1374` | `a88b21786ecdc3c9a310e6d63284c6249b66493c` | Parent of the #1374 squash. The state of `main` immediately before #1374 landed. Squash commit of #1366. |
| `POST-1374` | `9cbdde9b7` | The #1374 squash on `main`. The commit the prior-session handoff calls "current main." Closes #1374. |
| `CURRENT` | `3c00c6465be4e03e70c3920f32a06742ee7f8428` | Current `main` at the time of this enumeration. `git diff POST-1374 CURRENT -- assemblyzero/workflows/orchestrator/ tools/orchestrate.py` returns no changes, so any `POST-1374` claim about orchestrator code also holds on `CURRENT` unless noted otherwise. |

## Source documents under enumeration

1. `docs/orchestrator-stage-invocation-analysis.md` (untracked in the working tree as of `CURRENT`). This is the analysis document the prior session produced. Every factual assertion in it is enumerated below.
2. Prior-session chat statements about the orchestrator, as recorded in the session handoff (`data/handoff-log.md`, entry dated 2026-05-29 08:06:31 Central). These are enumerated separately under "Prior-session chat claims" so the transparency ledger can record their disposition.

## Pre-grounded claims (carried from the plan file)

These four claims were pre-pinned during the prior session's Phase 1 exploration. They are carried forward verbatim and will be verified in Phase D alongside the new claims.

- `ORCH-C001` (pin: `POST-1374`) — The status field of a stage result is constrained to one of the values `passed`, `skipped`, `failed`, or `blocked`. (Citation seed from the plan: `assemblyzero/workflows/orchestrator/state.py:15-22`.)
- `ORCH-C002` (pin: `POST-1374`) — Each orchestrator stage function that has a sub-workflow calls that sub-workflow's `.invoke(...)` method. (Citation seed from the plan: `assemblyzero/workflows/orchestrator/stages.py:129` and the analogous sites in the lld, spec, and impl stage functions.)
- `ORCH-C003` (pin: `POST-1374`) — There is no end-to-end test that runs the `orchestrate` function through real (non-mocked) sub-workflows. The orchestrator stage tests mock the graph factories. (Citation seeds from the plan: `tests/unit/test_orchestrator_repo_targeting.py:39-50` for the `_capturing_graph` fixture, and `tests/integration/test_orchestrator_graph.py` for the `STAGE_RUNNERS` patch.)
- `ORCH-C004` (pin: `POST-1374`) — On `POST-1374`, no sub-workflow graph module exports a function named `create_graph`. The graph factory functions that do exist are `create_requirements_graph`, `create_implementation_spec_graph`, and `build_testing_workflow`. (Citation seeds from the plan: `assemblyzero/workflows/orchestrator/stages.py:125,258,331` and the three sub-workflow `graph.py` `def` lines.)

## Claims extracted from the analysis document

### Group 1 — Orchestrator structure and the five-stage sequence

- `ORCH-C005` (pin: `CURRENT`) — A file `tools/orchestrate.py` exists.
- `ORCH-C006` (pin: `CURRENT`) — The orchestrator runs five stages in this order: `triage`, `lld`, `spec`, `impl`, `pr`.
- `ORCH-C007` (pin: `CURRENT`) — The `triage` stage's sub-workflow is the requirements graph configured with `workflow_type="issue"`.
- `ORCH-C008` (pin: `CURRENT`) — The `lld` stage's sub-workflow is the requirements graph configured with `workflow_type="lld"`.
- `ORCH-C009` (pin: `CURRENT`) — The `spec` stage's sub-workflow is the implementation_spec graph.
- `ORCH-C010` (pin: `CURRENT`) — The `impl` stage's sub-workflow is the testing graph.
- `ORCH-C011` (pin: `CURRENT`) — The `pr` stage does not call a sub-workflow graph. It invokes the GitHub CLI directly.
- `ORCH-C062` (pin: `CURRENT`) — A function named `orchestrate` is defined in `assemblyzero/workflows/orchestrator/graph.py` at or near line 190. (Numbered out of order to keep it adjacent to its topic; renumber in Phase E if required.)

### Group 2 — The workflow scripts

- `ORCH-C012` (pin: `CURRENT`) — A workflow script `tools/run_requirements_workflow.py` exists and drives the requirements graph when invoked from the command line.
- `ORCH-C013` (pin: `CURRENT`) — A workflow script `tools/run_implementation_spec_workflow.py` exists and drives the implementation_spec graph.
- `ORCH-C014` (pin: `CURRENT`) — A workflow script `tools/run_implement_from_lld.py` exists and drives the testing graph.
- `ORCH-C015` (pin: `CURRENT`) — `CLAUDE.md` documents the manual end-to-end workflow as a sequence of `tools/run_*.py` script invocations.

### Group 3 — How stages invoke sub-workflows today

- `ORCH-C016` (pin: `CURRENT`) — The orchestrator's stage functions perform their sub-workflow invocations as in-process Python calls. Each stage imports the graph factory, compiles the result if the factory returns an uncompiled `StateGraph`, and calls `.invoke(state, config)` on the compiled object.
- `ORCH-C017` (pin: `CURRENT`) — The stage functions `run_lld_stage`, `run_spec_stage`, and `run_impl_stage` use the same in-process invocation pattern as `run_triage_stage`, each against their respective sub-workflow graph.

### Group 4 — Layer 1: pre-#1374 brokenness

- `ORCH-C018` — PR #1376 closes issue #1374 and is the squash merge whose SHA is `POST-1374`. (Verifiable from the GitHub pull-request record and the git log.)
- `ORCH-C019` (pin: `PRE-1374`) — On `PRE-1374`, the orchestrator's worktree path was hardcoded as the literal string `../AssemblyZero-{N}` in three places in the orchestrator code.
- `ORCH-C020` (pin: `PRE-1374`) — On `PRE-1374`, four of the five stage functions (`triage`, `lld`, `spec`, `impl`) contained import statements that referenced a symbol named `create_graph` in their respective sub-workflow modules.
- `ORCH-C021` (pin: `PRE-1374`) — On `PRE-1374`, no sub-workflow `graph.py` module exported a function named `create_graph`.
- `ORCH-C022` (pin: `PRE-1374`) — On `PRE-1374`, the four `create_graph` import statements were written inside the bodies of the stage functions rather than at module scope.
- `ORCH-C023` (pin: `PRE-1374`) — On `PRE-1374`, no target repository identifier was threaded from the orchestrator CLI into the sub-workflow invocations.

### Group 5 — Layer 1 fix described

- `ORCH-C024` (pin: `POST-1374`) — The `POST-1374` commit adds a `--repo` flag to the orchestrator CLI.
- `ORCH-C025` (pin: `POST-1374`) — The `POST-1374` commit threads `target_repo` and `assemblyzero_root` through orchestrator state into every sub-workflow invocation.
- `ORCH-C026` (pin: `POST-1374`) — The `POST-1374` commit carves the worktree from the target repository rather than from a hardcoded path.
- `ORCH-C027` (pin: `POST-1374`) — The `POST-1374` commit makes artifact paths repo-aware.
- `ORCH-C028` (pin: `POST-1374`) — The `POST-1374` commit corrects the four broken import statements to reference the actual factory names (`create_requirements_graph`, `create_implementation_spec_graph`, `build_testing_workflow`).

### Group 6 — Behavior of the skip path and the pr stage

- `ORCH-C029` (pin: `CURRENT`) — In the `triage`, `lld`, and `spec` stages, the skip path returns a `StageResult` with status `skipped` before reaching the import line of the sub-workflow factory. As a consequence, a stage whose artifact already exists does not depend on the sub-workflow import resolving.
- `ORCH-C030` (pin: `CURRENT`) — A test exists named `test_skips_when_artifact_exists` that exercises the skip path and passes.
- `ORCH-C031` (pin: `CURRENT`) — The `pr` stage imports no sub-workflow graph and instead calls `gh pr create` via `run_command`.
- `ORCH-C032` — The `pr` stage's logic was unit-tested in PR #1366. (Verifiable from the merged pull-request diff.)

### Group 7 — Layer 2 (a): requirements sub-workflow input contract

- `ORCH-C033` (pin: `CURRENT`) — `assemblyzero/workflows/requirements/state.py` defines a function `create_initial_state` at or near line 256.
- `ORCH-C034` (pin: `CURRENT`) — `create_initial_state` assembles approximately fifteen input-state keys. (The exact count is itself a claim and will be verified by counting in Phase C; "approximately fifteen" is the claim under enumeration.)
- `ORCH-C035` (pin: `CURRENT`) — The keys assembled by `create_initial_state` include `config_drafter`, `config_reviewer`, `config_effort`, `config_gates_draft`, `config_auto_mode`, `config_mock_mode`, and `max_iterations`.
- `ORCH-C036` (pin: `CURRENT`) — `create_initial_state` raises `ValueError` when either `target_repo` or `assemblyzero_root` is empty, at lines 305 through 308.
- `ORCH-C037` (pin: `CURRENT`) — The orchestrator's triage and lld stages do not call `create_initial_state`. They construct a four-key dictionary by hand.
- `ORCH-C038` (pin: `CURRENT`) — `assemblyzero/workflows/requirements/nodes/load_input.py` reads the target repository as `Path(state.get("target_repo", ""))` at line 81.
- `ORCH-C039` (pin: `CURRENT`) — When the `target_repo` key is absent, `state.get("target_repo", "")` returns the empty string, and `Path("")` resolves to the current working directory.

### Group 8 — Layer 2 (b): the implementation_spec graph factory

- `ORCH-C040` (pin: `CURRENT`) — `assemblyzero/workflows/implementation_spec/graph.py` defines `create_implementation_spec_graph` at or near line 273.
- `ORCH-C041` (pin: `CURRENT`) — `create_implementation_spec_graph` returns the result of `graph.compile()` from a line at or near line 370 of the same file.
- `ORCH-C042` (pin: `CURRENT`) — The orchestrator's `run_spec_stage` function calls `.compile()` on the value returned by `create_implementation_spec_graph()`.
- `ORCH-C043` (pin: `CURRENT`) — The object returned by `create_implementation_spec_graph()` is an instance of `langgraph.graph.state.CompiledStateGraph`.
- `ORCH-C044` (pin: `CURRENT`) — `langgraph.graph.state.CompiledStateGraph` has no method named `compile`.
- `ORCH-C045` (pin: `CURRENT`) — At runtime against `POST-1374`, `hasattr(graph, "compile")` evaluates to `False` for the object returned by `create_implementation_spec_graph()`. (The handoff records this as having been verified at runtime; Phase C re-verifies it.)
- `ORCH-C046` (pin: `CURRENT`) — As a consequence of `ORCH-C042` and `ORCH-C044`, an unmocked execution of the orchestrator's `run_spec_stage` raises `AttributeError` when it reaches the `.compile()` call.

### Group 9 — Layer 2 (c): testing graph driver requirements

- `ORCH-C047` (pin: `CURRENT`) — `tools/run_implement_from_lld.py` calls `build_testing_workflow()` at or near line 819.
- `ORCH-C048` (pin: `CURRENT`) — `tools/run_implement_from_lld.py` sets `thread_id = f"{args.issue}-testing"` at or near line 822.
- `ORCH-C049` (pin: `CURRENT`) — `tools/run_implement_from_lld.py` opens a `SqliteSaver` checkpointer using `SqliteSaver.from_conn_string(str(db_path))` as a context manager at or near line 876.
- `ORCH-C050` (pin: `CURRENT`) — `tools/run_implement_from_lld.py` compiles the testing workflow with `workflow.compile(checkpointer=memory)` at or near line 877.
- `ORCH-C051` (pin: `CURRENT`) — `tools/run_implement_from_lld.py` sets a config dictionary that includes `{"configurable": {"thread_id": thread_id}, "recursion_limit": 50}` at or near lines 879 through 882.
- `ORCH-C052` (pin: `CURRENT`) — `tools/run_implement_from_lld.py` wraps the testing-workflow invocation inside a `WorkflowTimeout` context manager and contains resume and speedrun logic.
- `ORCH-C053` (pin: `CURRENT`) — The orchestrator's `run_impl_stage` function calls `build_testing_workflow().compile().invoke({...})` with no `checkpointer` argument supplied to `.compile()`.
- `ORCH-C054` (pin: `CURRENT`) — The orchestrator's `run_impl_stage` function supplies no `thread_id`, `recursion_limit`, or timeout in the config passed to `.invoke()`, and contains no resume or speedrun logic.

### Group 10 — Layer 2 summary: no shared input-state helper

- `ORCH-C055` (pin: `CURRENT`) — The requirements, implementation_spec, and testing sub-workflows do not share a common importable function for constructing their input state.
- `ORCH-C056` (pin: `CURRENT`) — The requirements sub-workflow has an input-state helper named `requirements.state.create_initial_state`.
- `ORCH-C057` (pin: `CURRENT`) — The implementation_spec sub-workflow has no equivalent input-state helper.
- `ORCH-C058` (pin: `CURRENT`) — The testing sub-workflow has no equivalent input-state helper.

### Group 11 — Workflow script details referenced by the analysis

- `ORCH-C059` (pin: `CURRENT`) — `tools/run_requirements_workflow.py` contains a function named `build_initial_state` at or near line 609.
- `ORCH-C060` (pin: `CURRENT`) — `tools/run_requirements_workflow.py` accepts a `--repo` flag, defined at or near line 469.
- `ORCH-C061` (pin: `CURRENT`) — `tools/run_implement_from_lld.py` accepts a `--repo` flag.

## Prior-session chat claims (for the transparency ledger)

These five statements were made in chat by the prior session and were identified as wrong by the operator. They are enumerated here so that Phase D can record their disposition in the transparency appendix of deliverable three.

- `ORCH-X001` (pin: `POST-1374`) — "No stage had ever successfully executed, for any repository." Expected disposition: `REFUTED`. The grounds are stated in `ORCH-C002` (stages do call `.invoke`), `ORCH-C029` and `ORCH-C030` (the skip path returns a `skipped` `StageResult` and is tested), and `ORCH-C031` and `ORCH-C032` (the `pr` stage uses a different mechanism and was unit-tested in #1366).
- `ORCH-X002` — "Every factual claim now has a checkable citation." Expected disposition: `REFUTED`. A completeness claim over an un-enumerated set is not falsifiable in either direction; the claim's universe was never established.
- `ORCH-X003` — "The harness placed [the plan file] there." Expected disposition: `REFUTED`. The plan file's location was attributed to an automated mechanism without evidence. The actual mechanism that produced the file was not investigated.
- `ORCH-X004` — Use of the phrase "shell out to the runners." Expected disposition: `REFUTED — VOCABULARY`. Neither "shell out" nor "runners" is the project's vocabulary. The accurate terms are "launch a child process" (or "subprocess") and "workflow scripts."
- `ORCH-X005` — "The pr stage works." Expected disposition: `REFUTED — OVERSTATED`. The grounds for the claim were a unit test in which the relevant call was mocked. A passing mocked test does not establish that the live call works.

## Explicit non-claims

To bound this enumeration, the following statements are explicitly NOT claims and are NOT under audit:

- The analysis document's recommendation that Option B is the sounder architecture. This is an opinion, not a falsifiable claim about code, and the operator has not ratified it.
- Any claim about what the orchestrator "should" do, as distinct from what it does.
- Any claim about pre-#1366 history. The scope is `PRE-1374` and later only.
- Any claim about the GitHub CLI's behavior beyond what the `pr` stage source explicitly invokes.

## Status

- Phase B: this enumeration. **In progress** — to be reviewed for completeness before Phase C begins.
- Phase C: citation pass. Not started.
- Phase D: independent verification pass. Not started.
- Phase E: cross-reference deliverable, built from `CONFIRMED` claims. Not started.

Claim count to date: 62 substantive claims, 5 prior-session chat claims for the transparency ledger.
