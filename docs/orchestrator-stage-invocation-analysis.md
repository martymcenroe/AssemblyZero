# AssemblyZero Orchestrator — How Should Stages Invoke the Sub-Workflows?

**Status:** Decision needed (second opinion requested)
**Date:** 2026-05-29
**Scope:** `tools/orchestrate.py` and the `assemblyzero/workflows/orchestrator/` package.

This document is self-contained. A reader who has never seen this codebase should be
able to judge the decision from it. Every factual claim cites a file, a function, and
(where stable) a line number so it can be checked.

---

## 0. Terms, defined precisely (no hand-waving)

These terms are used throughout. Two of them I had previously used loosely; the precise
meanings are below.

- **LangGraph `StateGraph`** — an object describing a workflow as nodes and edges. It is a
  *definition*, not yet runnable.
- **`.compile()`** — turns a `StateGraph` into a `CompiledStateGraph`, which is the runnable
  form. You call `.compile()` exactly once on a `StateGraph`.
- **`.invoke(state, config)`** — runs a `CompiledStateGraph`. `state` is a Python `dict`
  holding the workflow's inputs; `config` carries runtime options (e.g. a checkpointer
  thread id). The function call happens **inside the current Python process**.
- **In-process call** — the orchestrator imports a sub-workflow's graph object and calls
  `.invoke(...)` on it. Everything runs inside one Python process; data is passed as a
  Python `dict` in memory.
- **Child process (subprocess)** — the orchestrator launches a *separate* program — for
  example `python tools/run_requirements_workflow.py --issue 5 --repo /path` — using
  Python's `subprocess` module. The operating system runs it as its own process, exactly as
  if a person had typed that command in a terminal. The parent program reads its exit code
  and output. (Earlier I called this "shelling out," which is colloquial and imprecise. A
  **shell** — bash, PowerShell — is the program that reads typed commands and launches other
  programs; `subprocess.run([...])` launches a child process directly and does **not**
  require a shell. The accurate phrase is "run X as a child process.")
- **"workflow scripts"** — AssemblyZero's term (per `CLAUDE.md`) for the files in `tools/`
  named `run_*.py`. There are four relevant ones:
  `run_requirements_workflow.py`, `run_implementation_spec_workflow.py`,
  `run_implement_from_lld.py`, and `run_scout_workflow.py`. (Earlier I called these
  "runners," which is **not** a word in this codebase. I should have said "workflow
  scripts.")

---

## 1. What the orchestrator is supposed to do

`tools/orchestrate.py` is meant to take a single GitHub issue all the way to a merged pull
request in one command, by running five stages in order:

`triage → lld → spec → impl → pr`

Each stage corresponds to a sub-workflow that already exists and already works on its own
when run by hand:

| Stage | Sub-workflow (LangGraph) | Workflow script that runs it by hand |
|-------|--------------------------|--------------------------------------|
| triage | requirements (`workflow_type="issue"`) | `tools/run_requirements_workflow.py` |
| lld | requirements (`workflow_type="lld"`) | `tools/run_requirements_workflow.py` |
| spec | implementation_spec | `tools/run_implementation_spec_workflow.py` |
| impl | testing | `tools/run_implement_from_lld.py` |
| pr | (gh CLI directly, no sub-workflow) | — |

## 2. The manual sequence the orchestrator is meant to automate

Per `CLAUDE.md`, the way a human builds an issue today is to run the workflow scripts in
sequence, each pointed at a target repository with `--repo`:

```bash
# 1. write the LLD for the issue
poetry run python tools/run_requirements_workflow.py --type lld --issue N --repo /path/to/TARGET --yes
# 2. implement the code from the LLD
poetry run python tools/run_implement_from_lld.py --issue N --repo /path/to/TARGET
```

The orchestrator's job is to do this automatically. **The orchestrator is, in essence, a
script that runs the same commands a person runs by hand.** Hold this thought — it is the
crux of the decision in §5.

## 3. How the orchestrator invokes the sub-workflows *today*

In `assemblyzero/workflows/orchestrator/stages.py`, each stage runs its sub-workflow with an
**in-process call**: it imports the graph factory, compiles it, and invokes it with a small
Python `dict`. For example, the triage stage does (paraphrased):

```python
from assemblyzero.workflows.requirements.graph import create_requirements_graph
graph = create_requirements_graph()
app = graph.compile()
sub_result = app.invoke({"issue_number": issue_number, "workflow_type": "issue", ...})
```

The other three stages (`run_lld_stage`, `run_spec_stage`, `run_impl_stage`) follow the same
pattern with their respective graphs.

## 4. What is broken, with evidence

There are three independent layers of breakage. Layer 1 is already fixed and merged; Layer 2
is the open question this document is about.

### Layer 1 — FIXED and merged (PR #1376, closes #1374)
1. The worktree path was hardcoded to `../AssemblyZero-{N}` in three places, so the
   orchestrator could only ever build AssemblyZero itself.
2. Four of the five stages (triage, lld, spec, impl) import a sub-workflow graph, and all
   four import statements referenced a symbol `create_graph` that exists in **none** of the
   sub-workflow graph modules (the real names are `create_requirements_graph`,
   `create_implementation_spec_graph`, `build_testing_workflow`). The imports are written
   *inside* the stage functions, so they only raise when a stage reaches that line at
   runtime. **Net effect: whenever one of those four stages needed to actually run its
   sub-workflow, it raised `ImportError`, so the orchestrator could never *generate* a new
   artifact through them.** This is narrower than "nothing ran," and the distinction matters:
   - The `pr` stage (the fifth) imports no graph — it calls `gh pr create` directly via
     `run_command` — so it is unaffected and does execute (it was fixed and unit-tested in
     #1366).
   - The skip path of triage/lld/spec returns a `"skipped"` result *before* reaching the
     import line, so those stages return successfully when an artifact already exists (the
     passing test `test_skips_when_artifact_exists` exercises exactly that).
   - Whether the imports worked before the graph factories were renamed is a historical
     question this document does not settle.
3. No target repository was threaded into the sub-workflow calls.

The merged fix added a `--repo` flag, threaded a `target_repo` + `assemblyzero_root` through
the orchestrator's state into every sub-workflow call, carved the worktree from the target
repo, made artifact paths repo-aware, and corrected the import names.

### Layer 2 — OPEN (issue #1375) — the subject of this document
Even with Layer 1 fixed, a real run still cannot complete, because the in-process calls do
not match what each sub-workflow actually requires to run. Evidence:

**(a) The requirements sub-workflow needs a large, validated input state.**
`assemblyzero/workflows/requirements/state.py` defines `create_initial_state(...)` (line 256)
which builds ~15 input keys (`config_drafter`, `config_reviewer`, `config_effort`,
`config_gates_draft`, `config_auto_mode`, `config_mock_mode`, `max_iterations`, …) and
**raises `ValueError` if `target_repo` or `assemblyzero_root` is empty** (lines 305–308). The
orchestrator does not call this builder; it passes a hand-made 4-key dict. The graph's entry
node `requirements/nodes/load_input.py` reads `Path(state.get("target_repo", ""))` (line 81)
— a missing key becomes `Path("")`, i.e. the current directory.

**(b) The implementation_spec graph factory returns an ALREADY-compiled graph.**
`assemblyzero/workflows/implementation_spec/graph.py`: `create_implementation_spec_graph()`
(line 273) ends with `return graph.compile()` (line 370). But the orchestrator's spec stage
calls `.compile()` again on the result. The returned object is a
`langgraph.graph.state.CompiledStateGraph`, which has no `.compile()` method (verified at
runtime: `hasattr(graph, "compile")` is `False`), so the second call raises `AttributeError`.

**(c) The testing graph is normally driven with a checkpointer, a thread id, a recursion
limit, and a timeout — none of which the orchestrator supplies.**
`tools/run_implement_from_lld.py` (the script that runs the testing workflow by hand) does:

```python
workflow = build_testing_workflow()                     # line 819
thread_id = f"{args.issue}-testing"                      # line 822
with SqliteSaver.from_conn_string(str(db_path)) as memory:   # line 876
    app = workflow.compile(checkpointer=memory)          # line 877  (compiled WITH a checkpointer)
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}   # 879-882
    # ... invoked with that config, inside a WorkflowTimeout, with resume + speedrun logic
```

The orchestrator's impl stage does a bare `build_testing_workflow().compile().invoke({...})`
— no checkpointer, no thread id, no recursion limit, no timeout, no resume handling.

**Summary of Layer 2:** the three sub-workflows do **not** share a common "build my input
state" helper. Each is driven by its own workflow script in `tools/` that performs
non-trivial setup (full input state; for testing, a SQLite checkpointer + thread id +
timeout). The orchestrator's in-process calls reproduce none of that.

## 5. The decision

To make the orchestrator actually run a stage end-to-end, there are two coherent paths.

### Option A — keep in-process calls; replicate each script's setup inside the stages
Each stage builds the full input state its sub-workflow requires (for requirements, by
calling `requirements.state.create_initial_state`; for spec and testing, which have **no**
such builder, by assembling the dict inline), fixes the double-compile for spec, and
replicates the checkpointer + thread id + timeout machinery for testing.

- **Pros:** keeps the current in-process structure; no subprocess management.
- **Cons:** the orchestrator must duplicate setup logic that already lives, tested, in three
  separate workflow scripts. When those scripts change, the orchestrator silently drifts. The
  testing checkpointer/timeout/resume logic is substantial to reproduce faithfully.

### Option B — the orchestrator runs the existing workflow scripts as child processes
Each stage launches the corresponding `tools/run_*.py` script as a child process (via
`subprocess`), passing `--issue`, `--repo`, and the non-interactive flags those scripts
already support (e.g. `--yes` / `--auto` / `--review none`). After a stage's child process
exits, the orchestrator detects the produced artifact (issue brief / LLD / spec / worktree)
using the artifact-detection code that PR #1376 already made repo-aware, and passes it to the
next stage.

- **Pros:** reuses the exact scripts that already work by hand and already accept `--repo`;
  no duplication; the orchestrator becomes a thin coordinator that runs the same commands a
  person runs (see §2). The state/checkpointer/timeout setup stays in one place (the
  scripts). Lowest risk.
- **Cons:** the orchestrator manages child processes (exit codes, captured output) instead of
  Python return values; stage-to-stage handoff happens through files on disk rather than an
  in-memory object. (PR #1376 already implemented repo-aware artifact detection, so the
  file-based handoff exists.)

### Tradeoff summary

| | A: in-process | B: child processes |
|---|---|---|
| Reuses the working `tools/run_*.py` scripts | No — duplicates their setup | Yes |
| Risk of drift when scripts change | High | Low |
| Must reproduce testing checkpointer/timeout/resume | Yes | No |
| Matches the documented manual workflow (§2) | No | Yes |
| Inter-stage handoff | in-memory dict | artifact files (already repo-aware) |
| Amount of new/changed code | Larger, spread across stages | Moderate, concentrated in the stage functions |

## 6. Recommendation and the question for review

**Recommendation: Option B.** §2 shows the orchestrator's purpose is to automate a fixed
sequence of `tools/run_*.py` commands that already work and already accept `--repo`. Option A
asks the orchestrator to re-implement, in a second place, the setup those scripts already
contain — including a SQLite checkpointer and timeout for the testing stage — which is
duplicative and prone to silent drift. Option B keeps that logic in one place and makes the
orchestrator a thin coordinator over the same commands a human runs.

**Questions for the reviewer (Gemini):**
1. Is the in-process vs child-process framing correct, and is Option B the sounder
   architecture for this orchestrator — or is there a reason to prefer A (or a third option,
   e.g. extracting each script's setup into a shared importable function that both the script
   and the orchestrator call)?
2. For Option B specifically: is launching the existing CLI scripts as child processes and
   handing off via artifact files an acceptable pattern here, given the scripts are the
   tested, supported entry points and already take `--repo`?
3. Are there failure modes in B (non-interactive flag coverage, error propagation from child
   to parent, partial-failure resume) that should be designed for up front?

## Appendix — checkable references

| Claim | Location |
|---|---|
| Orchestrator CLI entry | `tools/orchestrate.py` |
| Stage definitions / in-process calls | `assemblyzero/workflows/orchestrator/stages.py` (`run_triage_stage`, `run_lld_stage`, `run_spec_stage`, `run_impl_stage`) |
| Orchestrator graph driver | `assemblyzero/workflows/orchestrator/graph.py` (`orchestrate`, line 190) |
| requirements input-state builder + repo validation | `assemblyzero/workflows/requirements/state.py:256`, raises at 305–308 |
| requirements reads target_repo at entry | `assemblyzero/workflows/requirements/nodes/load_input.py:81` |
| implementation_spec factory returns compiled graph | `assemblyzero/workflows/implementation_spec/graph.py:273`, `return graph.compile()` at 370 |
| testing graph factory | `assemblyzero/workflows/testing/graph.py:436` (`build_testing_workflow`) |
| testing driven with checkpointer + thread id + timeout | `tools/run_implement_from_lld.py:819, 822, 876-882` |
| requirements script builds full state | `tools/run_requirements_workflow.py:609` (`build_initial_state`), `637`/`654` |
| `--repo` already supported by the scripts | `tools/run_requirements_workflow.py:469`; `run_implement_from_lld.py` `--repo` |
| Manual workflow sequence | `CLAUDE.md` ("Running Workflows") |
| Layer 1 fix (merged) | PR #1376, closes #1374 |
| Layer 2 (this decision) | issue #1375 |
