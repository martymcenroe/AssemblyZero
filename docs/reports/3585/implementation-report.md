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

### keep_passing_tests.py (7 rows)

- **A contract that cannot be decided stops** (98, 172, 214). A prior text, revised text, spec suite or plan file that does not parse is an ERROR line naming the side and the file, then SyntaxError. Each used to return its input unchanged. The functions take an optional path for the line; N4 passes it.
- **A passing test is never dropped without a word** (134). When a revision removes the class that held a passing test, the tests are named in an ERROR line and a ValueError.
- The three `# fail-open:` tags are gone (99, 173, 215).

Callers: N4 lets the raises reach the runner, which alerts. N5's `_align_plan_files_with_the_spec` (verify_phases.py, another batch) does not pass the paths, so its ERROR line names the side but not the file.

### parsers.py (6 rows)

- **The conftest option check (#2547) no longer passes when it cannot compare** (142, 197, 212). An ancestor conftest that does not parse or cannot be read, or a directory on the walk that cannot be resolved, is an ERROR line naming it, and the exception propagates. Each used to end the comparison and pass.
- The three `# fail-open:` tags are gone (143, 198, 213).

Callers: `validate_code_response` is called by N4's retry loop and batch path; neither catches, so the runner alerts.

### edit_script_fix.py (5 rows)

- **Attribution by test body (#2861) does not guess around a file it cannot read** (273, 303). A planned Python file or a failing test's file that cannot be read or does not parse is an ERROR line naming it, and the exception propagates. A file that is not on disk, or not Python, is still an answer: it defines or uses nothing.
- **497, 503, 507** are fallbacks the orchestrator takes; it alerts on them (see orchestrator.py above).
- The two `# fail-open:` tags are gone.

### deprecated.py (4 rows)

No run calls these batch-mode helpers; they keep the standard while they exist.

- **A read the batch prompt needs stops** (58, 87): an ERROR line naming the file, and the read error propagates.
- **No invented paths** (190): a code block that names no file is an ERROR line and a ValueError; it used to be written as `implementation_N.py`.
- **No partial write** (218): an entry with no path or no content is refused before anything is written.

## Compliance (standard 0034)

| Failure path | Loud | Logged | Stops | Alerts |
|---|---|---|---|---|
| `ImplementationError` raised in N4 | ERROR line at construction | file and reason; the runner's alert adds repo and issue | the run exits 1 | the runner |
| A read N4 depends on fails | ERROR line naming file and purpose | exception type and message | the read error propagates | the runner |
| `git ls-files` cannot answer | ERROR line with stderr | exit code and stderr | `CalledProcessError` | the runner |
| An edit-script or batch fallback | `alert_operator` writes the ERROR record | what, where, cause, consequence, repo, issue | the fallback is the designed recovery | `alert_operator` |
| The test contract cannot be decided | ERROR line naming side, file, line | syntax error or lost tests | SyntaxError or ValueError | the runner |
