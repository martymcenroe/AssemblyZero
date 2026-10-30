# Implementation Report: the three workflow entry points fail loud (#4100, #4097, #4098)

Step 5 of the #3585 sweep, for the three workflow entry points. The #3581 sweep recorded their sites in ledger 0908 (line numbers from `79e18ad1`): 36 in `tools/run_requirements_workflow.py` (#4100), 23 in `tools/run_implement_from_lld.py` (#4097, 8 of them already fixed by PR #4159), and 10 in `tools/run_implementation_spec_workflow.py` (#4098). The rule is ADR 0236: every failure is loud, logged with details, stops what depends on it, and alerts the operator.

The pattern for an entry point is one handler at the top: it calls `alert.alert_operator` with the details and exits 1. Everything below it raises with its cause, instead of printing and continuing, returning a default, or exiting 0. A node's failure still goes to HALT inside the graph, which alerts; the entry point's handler is for what the tool itself owns. `alert.require_alert_channel` still runs first (#3729), outside the handler.

## `tools/run_requirements_workflow.py` (#4100): 36 sites

### The handler

`main()` runs the start-up channel check, then `_run(args)` inside `except Exception`. The handler prints `[requirements] ERROR: <cause>` on stderr, adds the traceback when the exception is not the tool's own `RunFailed`, and calls `alert.alert_operator` with what, where (`tools/run_requirements_workflow.py main` plus the issue or brief), cause, consequence, the resolved repository and the issue. It returns 1. `RunFailed` is the module's exception for a failure the tool names itself; its `alerted` flag is set when the HALT node already alerted for the same failure, and then the handler prints but does not alert again.

### What each site does now

- **Helpers that returned a default.** An unreadable checkpoint database raises naming the file (118); an empty one is still "no checkpoint". An unreadable brief raises naming it (175); a brief with no heading is still "(no title)". `--select` raises for a missing `ideas/active/` (192), no briefs (199), and gh failing, timing out, missing or printing something that is not JSON (259, 264, 267, 270), and for an empty issue list.
- **The target repository.** Git timing out or missing raises, for the brief's directory (560) and for the working directory (582). A working directory in no repository raises with git's stderr instead of becoming the target (585). A brief outside any repository still falls back to the working directory's repository, the order #115 documents. The AssemblyZero-root refusal raises, so it alerts (633).
- **The run.** A graph exception is kept in the run record and the speed-run log and re-raised (931, and 1175 for `--resume-review`). A failure in `build_initial_state` closes the run record and raises (on 1698's path). After the graph, `_run_failure` reads the final state: an `error_message` raises, printed on stderr by `print_result` (1541), and marked alerted when HALT ran, which it shows by setting `recovery_plan_path`. An end with no `issue_url` (1551) or no `final_lld_path` (1558) and no error raises too. The one end without a product that succeeds is the operator choosing manual handling at a human gate, which sets `next_node` to END.
- **`--resume-review`.** No resumable draft raises naming the lineage (967). A lineage with no `001-issue.md` refuses before the run record opens (991).
- **`--all`.** A missing `ideas/active/` raises (1203); an empty one returns 0, since zero briefs is the whole batch done. A brief that fails raises out of `run_single_workflow` and stops the batch, and the alert's where names the brief (1241). The Failed counter, which only carried swallowed failures, is deleted.
- **`--resume`.** The brief is resolved first and a missing one raises naming every path looked at (1306, 1330). No checkpoint and no audit directory raises instead of starting a fresh workflow (1291).
- **The pre-generation check.** A resumable draft without `--yes` raises naming both choices (1446). The merge-driver refusal raises (1687). The exit 0 after the check is reached only when the operator answers the regeneration prompt with anything but YES (1690).
- **Arguments.** The six refusals raise (1612, 1616, 1621, 1625, 1630, 1634).
- **Selection.** Because both selectors now raise on every failure, None, "Selection cancelled." and exit 0 mean only that the operator quit the menu (1662, 1668).

`--all` now stops at the first brief that fails. The ledger's prescription for 1241 named only loud and alerts; ADR 0236's loop rule and the work order's "raises instead of printing and continuing" both say stop, and the batch's summary is shaped by every brief.

### Compliance with standard 0034

| Failure path | Loud | Logged with details | Stops | Alerts |
|---|---|---|---|---|
| A `RunFailed` the tool raises (all sites but 931, 1175, 1698) | `[requirements] ERROR:` on stderr | `alert_operator`: what, where with issue or brief, cause naming the subject (file, command, exit code, stderr), consequence, repo, issue | exits 1; nothing after it runs; a batch stops | `alert_operator`, or the HALT node when it already ran |
| An exception from the graph or `build_initial_state` (931, 1175, 1698) | ERROR line with type, and the traceback, on stderr | the run record keeps the crash; `alert_operator` with the type and message | exits 1 | `alert_operator` |
| A run that ended in an error after HALT (1541) | the error on stderr from `print_result`, and the handler's ERROR line | the HALT node's state snapshot and recovery plan | exits 1 | the HALT node, once |

The three swallowed handlers are gone from the module (`checkpoint_exists`, `run_resume_review`, `run_single_workflow`); no `# fail-open:` tag was in it or is added. `main`'s handler carries `# noqa: BLE001`, as `halt_node.py`'s do.

### Not changed

- `assemblyzero/workflows/requirements/nodes/finalize.py` files the issue through `_finalize_issue`, which runs `gh issue create`, without checking `config_mock_mode`, so `--type issue --mock` files a real issue. The LLD half stops on mock. That package belongs to another agent's work.
- `run_single_workflow` compiles the graph with no checkpointer, so `--resume` does not resume from the checkpoint `checkpoint_exists` looks for: it reruns the brief from the start.
