# Implementation Report: the testing workflow's implementation subpackage under standard 0034 (#3585 step 5, batch B)

The rule is ADR 0236 and standard 0034. This batch takes the ledger 0908 rows for `assemblyzero/workflows/testing/nodes/implementation/`, module by module. Each site is fixed or recorded as a won't-do with its reason, and each has a test named by its ledger line at the ledger's base `79e18ad1`.

## Modules

### orchestrator.py (28 rows), with `ImplementationError` in claude_client.py

- **Every `raise ImplementationError` is loud where it is raised** (239, 270, 301, 316, 344, 357, 933, 946, 1146). The raises are unchanged, so the halt-site walker and the gate registry still match them. The exception's constructor writes `ERROR [N4] FATAL: Failed to implement <file>: <reason>` to stderr. The runner, `tools/run_implement_from_lld.py`, alerts on it with the file, reason, repo and issue, and exits 1. An alert at each raise as well would send two for one failure.
- **A read N4 depends on stops N4** (589, 819, 912, 1016, 1065, 1120). The test files for the prompt, the Modify base, the edit script's base, an unattributed file's text, a test file left after a failed patch, and the spec suite each went to an empty string on a read error. `_read_or_stop` writes an ERROR line naming the file and what it was for, and re-raises.
- **`came_from_base` answers only what git answered** (439). Exit 1 is untracked. Any other exit, such as 128 outside a repository, is an ERROR line with git's stderr and a `CalledProcessError`; it used to read as "untracked", which resumes past a base file.
- **Every fallback alerts** (117, 125, 135, and edit_script_fix.py 497, 503, 507). An edit script that raised, met an API error, came back as a whole file, had no blocks, had blocks that did not apply, or emptied the file now alerts with the file, the cause, the repo, the issue and the consequence, then falls back as before. `try_edit_script_fix` takes `repo` and `issue`.
- **The batch path alerts** (693, 704, 717): once when the batch call fails, and once per batch for the files its response could not supply or that failed validation. Those files are then generated on their own, as before.
- **559, 572: won't do.** Both return an `error_message` that `route_after_implement` sends to HALT, which alerts. Pinned.
- The four `# fail-open:` tags are gone (913, 1017, 1066, 1121).

Callers: `assemblyzero/workflows/orchestrator/stages.py` turns any exception from the testing graph into a failed stage result, and `tools/orchestrate.py` exits 1 on it without an alert. That is the orchestrator's entry point, outside this batch.

## Compliance (standard 0034)

| Failure path | Loud | Logged | Stops | Alerts |
|---|---|---|---|---|
| `ImplementationError` raised in N4 | ERROR line at construction | file and reason; the runner's alert adds repo and issue | the run exits 1 | the runner |
| A read N4 depends on fails | ERROR line naming file and purpose | exception type and message | the read error propagates | the runner |
| `git ls-files` cannot answer | ERROR line with stderr | exit code and stderr | `CalledProcessError` | the runner |
| An edit-script or batch fallback | `alert_operator` writes the ERROR record | what, where, cause, consequence, repo, issue | the fallback is the designed recovery | `alert_operator` |
