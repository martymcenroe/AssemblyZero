# Implementation Report: the testing graph and three of its nodes under standard 0034 (#3585 step 5, batch C)

The rule is ADR 0236 and standard 0034. This branch, `3585-testing-graph`, is batch C of the testing workflow's sweep: `assemblyzero/workflows/testing/graph.py` with its routers, and the nodes `load_lld.py`, `augment_tests.py` and `e2e_validation.py`. One commit per module, each ledger 0908 row fixed and tested, or kept and pinned. The other batches of the testing workflow are on their own branches. When the branches meet, each keeps its own sections of this file and its sibling.

## Modules

### graph.py (15 ledger rows: 14 fixed, 1 fixed earlier by #3725 and pinned)

- **Every stop a router decides reaches HALT (232, 245, 318, 355, 438, 447, 451, 471, 478, 488, 513).** The iteration caps, the cost budget, the spent coverage attempts, a BLOCKED plan under the strict policy or out of revisions, an exhausted scaffold that named no reason, and a route a node did not name each ended the run at END, which writes no halt bundle and alerts no one; the stage then read the empty `error_message` as a pass. Each condition now lives in one `_stop_after_*` function. The router consults it and routes to HALT. The node in front of the router is wrapped by `_records_its_stop`, which applies the same function to the node's result and records the reason as `error_message` at ERROR on stderr, so HALT's alert carries it.
- **auto_mode no longer hides a failed gate (217, 227).** `--review none`, the default, sets `auto_mode`, under which an N1 error was ignored and a BLOCKED test plan was walked past to N2. Any error now halts; a BLOCKED plan is revised under auto as under the default policy and halts when the revisions are spent.
- **A failed checkpoint stops the run (128).** The wrapper printed the error and carried on. It now writes an ERROR line naming the checkpoint, node, worktree and issue, and raises `CheckpointFailed` from the cause. Both callers of the graph alert on it, so it does not alert a second time.
- **The adversarial review's halt is pinned (557).** #3725 already routes N7.5's recorded reason to HALT.
- **Structure.** The edge maps of N1, N2.5, N3, N5 and N6 lose their `end` entries, which nothing can take now, and `testing/atlas.py` follows. The gate registry names the twelve new halt sites; three new impl rows (`impl.coverage_augment_spent`, `impl.budget.cost`, `impl.route_unrecognised`) cite the operator's ruling of 2026-10-06, and the impl ratchet in `tests/fixtures/gate_registry_baseline.json` goes from 44 to 47.

### nodes/load_lld.py (18 ledger rows: 10 fixed, 8 compliant and pinned)

- **N0 stops on every input it cannot build from (896, 1001, 1146, 1182, 1224).** A spec with no APPROVED marker, no Section 10 test plan in the LLD or the spec, no requirements, or no files to implement, and in issue-only mode a body with no test plan or no files, each halts at N0 naming the source. Each used to be a warning or nothing, and the run spent its reviews before a later gate, or nothing, stopped it. `extract_files_to_modify` raises when there is no table or the table names no file; it returned an empty list.
- **An LLD that cannot be read or rebuilt halts (324, 325, 1164).** A rebuild from refs that raises is said at ERROR and raised as `LLDRebuildFailed`, and the fail-open tag is gone; an LLD found and unreadable halts naming the path and cause. Both used to print a WARN and go on with the spec standing in for the LLD. A clean miss is still the quiet answer for absence.
- **Section 10's reason is never hidden (202, 1180).** `extract_spec_test_functions` returns the reason beside the empty suite when Section 10 fails the structure rule, so "no executable functions" and "no test plan" read differently. It does not raise, because the spec workflow's completeness checks call it on drafts. N0 records each source's reason and prints the LLD's when the spec's Section 10 serves instead. The rule now lives in `spec_structure_error`, so neither path catches an exception.
- **Kept and pinned (835, 969, 972, 977, 983, 1099, 1136, 1142).** The ADR 0207 default target, and the halts the ledger found compliant.
- **Structure.** The halts go through `_halt_spec_unusable` and `_halt_input_unreadable`, registered under the existing rows `impl.lld_not_usable` and `impl.input_precondition`; no row is added. The `requirements_empty_reason` state key is no longer written.

### nodes/augment_tests.py (26 ledger rows: 25 fixed, 1 compliant and pinned)

- **Every failure of N4c halts (347, 537, 554, 581, 593, 613, 645, 650, 671, 721, 734, 755, 761).** No test file, a report that names no uncovered line, an unreadable test file, no audit dir, no seat, a failed or empty model call, generation attempts spent, a vetting run that executed nothing, a repair that cannot be made, and no added test passing each used to return to N5 with an empty `error_message`, and N5 sent the same shortfall back. Each now halts with its cause, through `_halt_augment_cannot_run` (the node's machinery failed) or `_halt_augment_spent` (an allowance is spent), which `route_after_augment` sends to HALT. A reply with no code is a rejected attempt, revised like an import problem.
- **Nothing it reads is skipped (101, 106, 134, 209, 218, 223).** A malformed range in a coverage report raises `CoverageRangeUnreadable`, and an unreadable source raises its `OSError`; the node halts on either before any model call. `_read_lines` reads its ranges through `_line_numbers`, so there is one parser.
- **Broken invariants raise (317, 318, 389, 390, 735).** An addition that does not parse raises `AugmentInvariantBroken`, and the node restores the suite and re-raises. `_without_named_tests` raises on source that does not parse. The three fail-open tags are gone.
- **A dropped test is said at ERROR (701).** The passing additions are kept, as #2902 designed, and the node returns to N5 with them; the tests still dropped after the repair pass are counted in one ERROR line.
- **The suite left on disk always passes.** Before any halt after vetting, the file is what was there plus only the additions that ran and passed.
- **Kept and pinned (142).** The fallback to bare lines for a source that does not parse.
- **Structure.** A new registry row, `impl.coverage_augment_cannot_run`, cites the operator's ruling of 2026-10-06, and the impl ratchet goes from 47 to 48; the spent halt joins `impl.coverage_augment_spent`.

### nodes/e2e_validation.py (13 ledger rows: 10 fixed, two of them in part; 3 compliant and pinned)

- **A run that cannot be made halts with its cause (182, 188, 291).** A timeout or a runner that cannot start raises `E2ERunFailed` naming the ceiling, the command and the cause; both returned code -1 with a fixed string. An unset or absent audit dir halts before the run; an unset one used to write the results into the working directory.
- **The sandbox stubs stop claiming success (210, 231, 300).** The safety check and the cleanup raise `NotImplementedError` instead of reporting "safe" and "cleaned", so a run given a sandbox repo halts before any test runs. A cleanup that reports failure halts with its error.
- **Only exit 1 is a test failure (331, 334).** Exit 2, 3, 4 and any other code halt, naming the code's meaning, the issue and the output tail. Exit 2 and unknown codes used to loop to N4 as test failures.
- **E2E files that collect nothing halt (313, 337, in part).** A run whose E2E or integration files collect no marked test halts naming the files. A run with no such file and no marked test still goes to finalize, with a line saying there was nothing to validate: the orchestrator never sets `skip_e2e`, so halting there would stop every orchestrated run on a target without E2E tests after its green phase. Whether such a run is a failure is the operator's decision; the halt is one line. Files are now judged by their path inside the repository, not the whole path.
- **Kept and pinned (45, 394, 417).** The advisory pass count, the circuit breaker and the retry cap.
- **Structure.** The new halts join the existing registry row `impl.e2e_error`; no row is added.

## Compliance

Every failure path above meets the four properties of standard 0034: it writes an ERROR line on stderr naming what failed and its subject, it stops what depends on it (a HALT route, or a raise the entry point owns), and it alerts the operator, through HALT or through the caller's handler.


---

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

### claude_client.py (4 rows)

- **A timeout override that cannot be used raises** (61, 64). `AZ_FILE_TIMEOUT_FLOOR` or `AZ_FILE_TIMEOUT_CAP` set to something that is not a positive whole number is an ERROR line naming the variable and value, then ValueError, as `AZ_LLM_IDLE_TIMEOUT` does since #3780. Unset or empty is the default.
- **A provider exception is an ERROR line** (270) naming its type, the seat and the file, and the returned error carries the type. It is still returned as the call's error, which is the function's contract: the retry loop raises after its budget and the runner alerts.
- **250: won't do.** Compliant: a model that is not a provider spec is a non-retryable error the retry loop raises on. Pinned.
- `ImplementationError` writes its ERROR line at construction (see orchestrator.py above).

### import_validator.py (3 rows)

- **The import gate (#842) does not judge on what it could not read** (85, 119). Installed-package metadata that cannot be read, or a `pyproject.toml` that cannot be read or does not parse, is an ERROR line naming it, and the exception propagates. Reading the second as "no dependencies" had flagged every third-party import. No `pyproject.toml` still declares nothing.
- **Code that does not parse does not pass** (229): it is a failed verdict carrying the syntax error, with an ERROR line. In a run, `validate_code_response` checks syntax first.

Callers: N4's validation and, for the pyproject reader, `scaffold_tests.py` (another batch); neither catches.

### routing.py (1 row)

- **62: won't do.** Compliant: a file path that is not a string raises TypeError naming its type. Pinned.

### prompts.py (1 row)

- **The Modify prompt is never built without the file** (153). A Modify file that cannot be read is an ERROR line naming it, and the read error propagates; the model used to be asked to modify a file it was never shown.

### context.py (1 row)

- **A Python file that does not parse is said aloud** (40). The summary for later files still carries its first 50 lines, now with an ERROR line naming the file and the syntax error. The summary is context, not a gate, so it goes on. A file that is not Python is summarized by its head, quietly. The prompt builder passes the path.

## Compliance (standard 0034)

| Failure path | Loud | Logged | Stops | Alerts |
|---|---|---|---|---|
| `ImplementationError` raised in N4 | ERROR line at construction | file and reason; the runner's alert adds repo and issue | the run exits 1 | the runner |
| A read N4 depends on fails | ERROR line naming file and purpose | exception type and message | the read error propagates | the runner |
| `git ls-files` cannot answer | ERROR line with stderr | exit code and stderr | `CalledProcessError` | the runner |
| An edit-script or batch fallback | `alert_operator` writes the ERROR record | what, where, cause, consequence, repo, issue | the fallback is the designed recovery | `alert_operator` |
| The test contract cannot be decided | ERROR line naming side, file, line | syntax error or lost tests | SyntaxError or ValueError | the runner |
