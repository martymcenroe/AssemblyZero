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

## `tools/run_implement_from_lld.py` (#4097): 23 sites

Eight rows were fixed by PR #4159 (#4150): lines 296, 345, 353, 1344, 1377, 1442, 1458 and 1484. Each was checked against the code here and holds as the ledger's FIXED note says; their tests are in `tests/unit/test_impl_lands_through_driver.py`. This change fixes the other fifteen, and keeps everything the branch's earlier commits added to the module: the transport preflight, the issue-branch refusal and worktree provisioning.

### The handler

`main()` parses the arguments and runs the start-up channel check, then calls `_main(args)` inside `except Exception`. The handler prints `[implement] ERROR: <cause>` on stderr, adds the traceback when the exception is not the tool's own `RunFailed`, calls `alert.alert_operator` with what, where, cause, the exception's consequence, the resolved repository and the issue, closes the run record when `_main` opened one, and returns 1 (line 1489). The refusals the earlier commits added still print, alert and exit 1 where they happen.

### What each site does now

- **Git reads.** `get_current_branch` raises with git's exit code and stderr when `rev-parse` fails (77); it used to return "" and the caller refused as if the HEAD were detached. `_worktree_entries` raises with git's stderr instead of returning None, so `find_existing_worktree` and `create_worktree`'s reuse check can no longer read a failed listing as "no worktree" (123).
- **The status file.** `_write_status_file` raises when the file cannot be written (961). Inside the run, the inner handler closes the record and re-raises it, and `main` alerts once: agents that read the file to tell a success from a failure cannot see this run's outcome.
- **Refusals before anything ran.** A missing `--repo` (990), a repository that cannot be detected (996), a non-positive issue (1008), another issue's work branch (1087), a detached HEAD (1096) and a worktree that could not be cut (1123) each raise. The dry run's "(unreadable)" fallback is deleted, since an unreadable branch now raises.
- **`--select`.** No LLD directory, no LLD files, no file named `LLD-<number>.md`, and an answer that selects nothing each raise, so exit 0 is only the operator cancelling with 0, Ctrl-C or Ctrl-D (1003).
- **Inputs.** Any rejected context file stops the run before the graph is built, listing every rejection; it used to run with the context that was left (1181, 1183). A bad model profile raises (1199).
- **`--resume`.** `resume_checkpoint_refusal` checks for the issue's checkpoint before the worktree is touched. No database, or one with no checkpoint for the issue's thread, refuses; it used to print "starting fresh" and run from the start (1331). It does not create a database to look in.

### Compliance with standard 0034

| Failure path | Loud | Logged with details | Stops | Alerts |
|---|---|---|---|---|
| A `RunFailed` before the worktree (77, 123, 990, 996, 1003, 1008, 1087, 1096, 1123, 1331) | `[implement] ERROR:` on stderr | `alert_operator`: what, where, cause with git's exit code and stderr or the path, consequence "nothing ran", repo, issue | exits 1; no worktree cut, no model called | `alert_operator` |
| A `RunFailed` after the record opened (1181, 1183, 1199) | same | same, and the run record finishes `fail` | exits 1 before the graph is built | `alert_operator` |
| The status file not written (961) | same | same, with the file and the OSError; the record finishes `fail` | exits 1 | `alert_operator`, once |
| Any other exception outside the graph's try (1489) | ERROR line with type, and the traceback | `alert_operator` with type and message; the record is closed | exits 1 | `alert_operator` |

The loud-failure baseline held no entry for this module after PR #4159; no `# fail-open:` tag was in it or is added. `main`'s handler carries `# noqa: BLE001`.
