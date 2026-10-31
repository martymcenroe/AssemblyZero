# Implementation Reports: the testing workflow under standard 0034 (#3585 step 5)

The package was swept in five batches from `fc1b2b0f` and merged on one branch. Each batch's report follows whole, under its own title, in merge order: C (the graph and three nodes), B (the implementation subpackage), D (the remaining nodes), E (runners, templates and top-level modules), A (checkpoints, verify_phases and cleanup).

---

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


---

# Implementation Report: the testing workflow's remaining nodes under standard 0034 (#3585 step 5, batch D)

The rule is ADR 0236 and standard 0034. This branch, `3585-testing-nodes`, is batch D of the testing workflow's sweep: the nodes under `assemblyzero/workflows/testing/nodes/` that no other batch owns. One commit per module, each ledger 0908 row fixed and tested, or kept and pinned. The other batches of the testing workflow are on their own branches. When the branches meet, each keeps its own sections of this file and its sibling.

## Modules

### nodes/validate_tests_mechanical.py (11 ledger rows: 5 fixed, 6 compliant and pinned)

- **An unreadable helper halts (522, 523).** A helper file beside the tests that the tests import from, and that cannot be read or parsed, raises `HelperSourceUnreadable` naming the file, the imported name and the cause. N2.5 returns it through `_halt_validation_cannot_run`: an ERROR line on stderr and an `error_message` that `route_after_validate` sends to HALT, which alerts. It used to drop the helper silently, and the test that relied on it was refused with a message that never named the file. The ledger's "record it as a validation error" was not taken: the assertion check cannot follow into the file, so it cannot run, as with an unreadable test file (#3081), and regenerating the scaffold cannot repair a file the scaffolder did not write.
- **A placeholders-only suite is named at ERROR (676).** When every generated test fails unconditionally and the spec ships no test bodies, the node writes an ERROR line on stderr naming the issue and every placeholder. When the suite otherwise passes and goes on to the red phase, nothing stops the run there (#386, #2331), so the node also alerts the operator. When the suite is rejected for other errors, the rejection routes back to the scaffolder or, out of attempts, to HALT, which alerts, so the node does not alert a second time.
- **An exhausted run never ends quietly (1043).** `should_regenerate` returns "escalate" only when state carries the node's `error_message`, which reaches HALT. Out of moves with no recorded reason, the legacy fallback for resumed state or a carried escalate whose reason is gone, it writes an ERROR line and raises `ScaffoldExhausted` with `DETERMINISTIC FAILURE` and the reason. It used to return "escalate", which `route_after_validate` maps to `end`, and the run ended as if nothing failed. The raise leaves the graph, and `tools/run_implement_from_lld.py` prints it at ERROR and alerts.
- **The tags are gone (500, 523).** `imported_helper_sources` has no handler for unparseable test text any more: it asks `count_stub_tests` whether the text holds a test function, and parses only when it does, so the syntax error is reported once, by `validate_test_structure`.
- **Kept and pinned (101, 418, 499, 557, 963, 975).** The parse answers that say "nothing here" for text whose syntax error another check reports, now documented in their docstrings, and the two budget halts, which already reach HALT.
- **Where the raises go.** `HelperSourceUnreadable` is handled by the node and also reaches `assemblyzero/speedrun/answer_key.py`, which has no handler, so the answer key stops on an unreadable neighbour. `ScaffoldExhausted` is raised inside graph execution and reaches the entry point's handler. In `assemblyzero/workflows/testing/graph.py`, `route_after_validate` still maps "escalate" to `end`; that return is now reached only with `error_message` set, which the router sends to HALT first.

### nodes/scaffold_tests.py (11 ledger rows: 9 fixed, 2 compliant and pinned)

- **No Section 10 raises (105).** `parse_lld_test_section` raises ValueError naming the headings it looked for. It returned no scenarios, which read the same as an empty test plan.
- **No `assert True` (325, 342).** Where no assertion can be derived from a scenario's expected behaviour, the generated test is `assert False` with a "TDD RED" message naming that behaviour. `assert True` passed with no implementation at all, so a scaffold no one replaced read as green.
- **Bodies that do not parse halt N2 (787, 788).** `unbound_names` raises `ScaffoldImportError` naming the line of the emitted file and the parser's message; `_scaffold_python_tests` returns it as `error_message`, routed to HALT, before anything is written. It used to repair nothing and leave the refusal to N2.5, which then regenerated a transcription that comes out byte for byte the same.
- **A finder that raises halts N2 (833, 834).** A name `importlib`'s finder raises on is reported with the test that uses it and the cause, by the same route.
- **A missing audit directory halts N2 (1069, 1199).** `_require_audit_dir` runs before either scaffold writes anything: a state naming no directory, or one that is not a directory, raises FileNotFoundError, and N2 halts through `_halt_scaffold_framework`. The single-pytest path now catches ValueError and OSError into that halt, as the multi-framework path already did. An unset `audit_dir` used to be `Path("")`, the working directory, so the scaffold's audit copy landed wherever the run was started.
- **Kept and pinned (435, 1153).** An unsupported framework raises; no scenarios is the GUARD halt.
- **Where the raises go.** `parse_lld_test_section` and the assertion generator have no caller outside the tests. `ScaffoldImportError`'s new causes also reach `implementation_spec/nodes/validate_completeness.py`, which already catches it and fails its Section 10 check with the message.

### nodes/review_test_plan.py (7 ledger rows: 2 fixed, 5 fixed in the node and waiting on the router)

- **The prompt is AssemblyZero's, and a missing one raises (156).** `load_review_prompt` read `docs/skills/0706c-Test-Plan-Review-Prompt.md` under the TARGET repository's root, where it never is, and a missing file became a built-in default prompt without a word: every review of another repository's plan ran on a prompt nobody maintained. It now reads this checkout's file (`projects_root.REPO_ROOT`) and raises FileNotFoundError naming the path; the default prompt is deleted. The raise reaches the entry point, which alerts.
- **A BLOCKED verdict sends real feedback or is rejected (710).** The schema-required rationale was never read, so a JSON BLOCKED verdict with no blocking issues sent the reviser "See full verdict for details." The feedback is now the summary and blocking issues, else the Required Changes section or numbered list, else the rationale. A BLOCKED verdict naming none of them is rejected through the existing "Test-plan reviewer response rejected" return, which halts.
- **Every error is an ERROR line on stderr (428, 489, 553, 579, 609).** The GUARD block, an unresolvable reviewer, a failed call, an unexpected error (now named with its type) and an unusable verdict each write `ERROR [N1]` on stderr and return `error_message` as before.
- **The router half is batch C's.** `route_after_review` in `graph.py` (line 218) sends an error to HALT only when `auto_mode` is off: `if error and not auto_mode`. It must be `if error`. Until then, those five errors continue to N2 under `auto_mode`.
- **Halt sites unchanged.** The five error returns keep their order, so the gate registry needs no change; the line-579 broad handler and its loud-failure baseline entry stay for that reason.

### nodes/document.py (7 ledger rows: 5 fixed, 2 kept and pinned)

- **An artifact that cannot be written stops N8 (292, 308, 338, 350).** The wiki page, runbook, c/p docs and README steps each printed "SKIPPED" on stdout and went on, the c/p step with a partial list. Each now raises `DocumentationError` naming the issue, the artifact and the cause, after an ERROR line on stderr. N8 has no route to HALT and returns no `error_message`, so the raise reaches the run's entry point, which reports it and alerts.
- **A missing README raises (182).** When N8 decides a README needs a feature entry and there is no README.md, `update_readme` raises FileNotFoundError naming it. It returned False, printed as "no update needed".
- **Kept: no Features section (215).** A README that keeps no feature list has none to add to. Five READMEs in the Projects tree have a Features section and AssemblyZero's has none, while N8 decides to update one from LLD keywords; raising would stop most runs that reach N8. It is left unchanged and said as that, no longer as "no update needed".
- **Kept: no wiki sidebar (289).** `update_wiki_sidebar` returns False for a wiki with no `_Sidebar.md` or a page already listed, both absences; `generate_wiki_page` makes the wiki directory itself, so a repository with no wiki gets a page and no sidebar. The result is now checked and said, and a sidebar that cannot be read or written raises and is no longer swallowed.

### nodes/mechanical_hooks.py (5 ledger rows: 1 fixed, 4 compliant and pinned)

- **A staging that fails halts (108).** After a successful hook, `git add .` ran with `check=False` and its return code was never read, so a staging that failed went on to the tests as if the hook's output were in the tree. Its exit code is read now: non-zero, or git that cannot start, halts through `_halt` with the directory, the exit code or exception, and git's stderr.
- **Every halt is an ERROR line (74, 91, 98).** `_halt` now also writes the reason at ERROR on stderr; the unreadable config, the hook that cannot start and the hook that fails were already halts and are pinned.
- **Kept (70).** No `.unleashed.json` is no hook.

### nodes/revise_test_plan.py (4 ledger rows: 4 compliant and pinned)

- **Pinned, and said where they happen (226, 246, 266, 307).** No requirements, an invalid revisor spec, a failed revision call and a short plan at the revision cap each record a reason that `route_after_revision` sends to HALT. Each now also writes an ERROR line on stderr, naming the spec where there is one. The docstring said these route "to END"; it says HALT now.

### nodes/finalize.py (4 ledger rows: 4 fixed)

- **No test counts, no report (152).** A green-phase output with no passed, failed or error count was reported as 0 of 0 tests passed, and the run as COMPLETE. N7 now raises `FinalizeError` naming the issue and the head of the output, before the report is written or anything archived.
- **A file to archive that is missing raises (46).** `archive_file_to_done` raises FileNotFoundError naming it when it is in neither active/ nor done/. One already in done/ with no copy in active/ is the file an earlier pass of N7 archived, and its done/ path is returned, so a resumed N7 does not fail on its own work.
- **A move that fails raises (74).** `FinalizeError` names the source, the destination and the cause, after an ERROR line; it was an ERROR naming the file only, and the run went on to COMPLETE.
- **Failures are no longer "skipped" (216).** The skipped list held failures nothing read. They raise now; the list holds only files with nothing to archive, and N7 prints it.
- **Why a raise.** `route_after_finalize` does send `error_message` to HALT, but N7 has no registered halt site and the gate registry is not this batch's file. The raise reaches the entry point, which alerts.

### nodes/adversarial_validator.py (3 open ledger rows: 3 compliant and pinned)

- **Pinned (114, 227, 251).** A file that does not compile is an error and makes the result invalid. The mock and assertion scans answer "nothing found" for source that does not parse because their only caller runs them after `compile` accepted the file; their docstrings now say so. Lines 63 and 79 were fixed in #3725.

### nodes/completeness_gate.py (1 open ledger row: compliant and pinned)

- **Pinned (119).** Zero requirements is a BLOCK whose `error_message` routes to HALT. The refusal is now an ERROR line on stderr instead of a stdout print. The gate's other rows were fixed in #3811.

## Compliance

Every failure path above meets the four properties of standard 0034: it writes an ERROR line on stderr naming what failed and its subject, it stops what depends on it (a HALT route, or a raise the entry point owns), and it alerts the operator, through HALT, through the entry point's handler, or from the node when nothing stops.


---

# Implementation Report: the testing workflow's runners, templates and top-level modules under standard 0034 (#3585 step 5)

The rule is ADR 0236 and standard 0034. This branch, `3585-testing-runners`, is batch E of the testing workflow's sweep: the runners, the runner registry, the exit-code router, the framework detector, the coverage report, the audit helpers, the path and symbol validators, the knowledge patterns and the three documentation templates under `assemblyzero/workflows/testing/`. One commit per module, each site fixed and tested against ledger 0908. The other batches of the testing workflow are on their own branches. When the branches meet, each keeps its own sections of this file and its sibling.

## Modules

### runners/jest_runner.py (7 ledger rows: 6 fixed, 1 compliant and pinned)

- **A run nobody can read raises.** A run whose stdout carries no JSON report (110), or whose report does not parse (124), raises `RunnerError` after an ERROR line on stderr and in the log. The message names the framework, the project directory, the exit code and the head of both streams.
- **The fallback is gone (169).** It read zero failures and zero errors at exit 0, so a run nobody could read was judged as one where nothing failed. The only result the runner builds without a report is a failed typecheck's, now `_typecheck_failed_result`, which always carries one failure and one error.
- **package.json is read or refused (57, 58).** `_has_typecheck_script` decides whether a Vitest project declares a typecheck. No package.json declares none, quietly. One that cannot be read, does not parse, or is not an object with an object of scripts raises `RunnerError` naming the file, and no suite runs. The fail-open tag and its handler are deleted.
- **npx missing is loud (33).** The constructor prints an ERROR line naming the framework and the project directory, then raises the EnvironmentError every caller already turns into a halt.
- **Kept (72).** A typecheck that exits non-zero is the run's answer and comes back as a failing result.
- **New in `base_runner.py`** for every runner: `RunnerError`, `loud()` and `output_head()`.
- **Where the raise goes.** `nodes/verify_phases.py` calls `run_tests` in N3, N5 and the full-suite gate. None of them catches `RunnerError`, so it ends the run through `tools/run_implement_from_lld.py main`, which prints it at ERROR, alerts the operator and exits 1. Catching it beside `CoverageReportError` and returning it as `error_message` would end the run at HALT instead, with its saved state; that file belongs to another batch.

### runners/base_runner.py (4 ledger rows: 4 fixed)

- **A test command that did not run raises.** A timeout (129), a missing command (132) or another OS error (135) raises `RunnerError` naming the framework, the command, the working directory and the cause, after an ERROR line. They came back as exit code -1 with the cause where stderr would be, and the runners parsed that as a run, so a suite that never started read as one that failed.
- **No scenarios is not 0% (96).** `compute_scenario_coverage` with no scenarios raises ValueError after an ERROR line. It returned 0.0 with a WARNING, which the green phase read as a measured 0%.
- **Where the raises go.** Both reach `nodes/verify_phases.py`, which catches neither, so each ends the run through the entry point's handler, which alerts. Catching them in N5 and returning them as `error_message` would end the run at HALT instead.

### runners/pytest_runner.py (2 ledger rows: 2 fixed)

- **The exit code is read (45).** 0 and 1 are finished runs, read from the summary line. Any other code raises `RunnerError` after an ERROR line, naming the code, what pytest means by it (interrupted or stopped at collection, internal error, usage error, no tests collected) and the head of the output. Those runs used to come back as counts read off their output, mostly zero.
- **No coverage table is not 0% (57).** `coverage_percent` is None, not measured, when the output carries no TOTAL row, as the Jest runner reports it since #4246.
- **No caller swallows it.** Nothing in `assemblyzero/` or `tools/` calls `PytestRunner.run_tests`; the phases run pytest through `run_pytest`.

### runners/playwright_runner.py (2 ledger rows: 2 fixed)

- **A run nobody can read raises.** No JSON report (91), a report that does not parse (104), or a report whose suites are not the shape Playwright writes raises `RunnerError` after an ERROR line, naming the project, the exit code and the head of both streams.
- **The fallback is gone.** It read zero failures and zero errors at exit 0.
- **Where the raise goes.** As for the Jest runner: N3, N5 and the full-suite gate do not catch it, so the run ends through the entry point's handler, which alerts.

### runner_registry.py (1 ledger row: fixed)

- **An unknown framework raises (117).** `resolve_framework` raises `UnknownFrameworkError`, a ValueError, after an ERROR line, naming the value and the four frameworks. It returned None, the same answer as no framework, and `framework_ownership.run_frameworks` reads None on a one-framework run as pytest.
- **No framework named is still None, quietly.** No config, no `framework` key, or a key holding None is the pytest default every caller documents.
- **Where the raise goes.** `run_frameworks` does not catch it, and its four callers catch only `TestFileOwnershipError`, so the run ends through the entry point's handler, which alerts. Wrapping it in `TestFileOwnershipError` in `run_frameworks` would end it at HALT instead; that file belongs to another batch.

### exit_code_router.py (4 ledger rows: 4 fixed)

- **The unused router is deleted (47, 60, 68, 71).** `route_by_exit_code` sent a red phase that passed, an interrupted or broken pytest, a timeout and an unknown code to a plain end, never to HALT. Nothing called it: the routing that runs is inline in `nodes/verify_phases.py` on the same constants (see #2690). The ledger allowed routing to HALT or deletion; deletion leaves no second copy with silent ends to wire in, and changes no route.
- **What verify_phases reads stays.** The constants, `describe_exit_code` and `describe_run_outcome` are unchanged.

### framework_detector.py (3 ledger rows: 3 fixed)

- **Two raises are now loud.** An unreadable package.json (215) and a `test_dirs` declaration naming no framework (252) raised with nothing said where they failed. Each now prints an ERROR line first. The path resolver's read of the same package.json, added by #4237 after the ledger's base, does the same.
- **A missing project is not pytest (273).** `detect_framework_dirs` with a project root that is empty or not a directory raises `FrameworkResolutionError` naming it, after an ERROR line. It returned no frameworks, which the callers read as pytest at the root. A project that exists and declares nothing is still the quiet empty answer.
- **Where the raises go.** N0 catches ValueError on all three paths and halts, and HALT alerts; provisioning turns ValueError into `ProvisioningError` naming the worktree.

### coverage_report.py (2 ledger rows: both compliant, pinned)

- **Unchanged, by design.** No TOTAL row (137) and a table that leaves out the target (143) are each a reading in the state ABSENT, with no percentage and a message naming what was sought and what the report held. That is the module's contract (#2637). N5 stops on it, and N4c returns it as an error that its router sends to HALT. The new tests pin the contract.

### audit.py, the testing workflow's (3 ledger rows: 2 fixed, 1 left for the verify_phases batch)

- **A missing audit directory raises (121).** `next_file_number` raises FileNotFoundError naming it, after an ERROR line. It answered 1, as if the directory were empty. Every caller checks or creates the directory first.
- **A lost audit event raises (280).** `log_workflow_execution` raises `WorkflowAuditError` naming the workflow, the event, the issue, the log and the cause, after an ERROR line, when the log's directory cannot be made or the line cannot be appended. It logged a WARNING and went on. The run ends through its entry point's handler, which alerts.
- **No coverage table still reads 0.0 (320).** `nodes/verify_phases.py`, another batch's file, compares and records the value as a number, so None would raise there. The fix needs that file first; a strict xfail records the open site. N5 already catches the absence with `coverage_report.read_coverage` before it decides a route.

### path_validator.py (3 ledger rows: 2 fixed, 1 compliant and pinned)

- **Every failed context file is said (164, 177).** A rejection, or a read that fails, is an ERROR line naming the file and the cause. The read handler names OSError and UnicodeDecodeError where it caught every exception.
- **No partial context.** When any file fails, no content comes back, only the errors. The one caller, `tools/run_implement_from_lld.py`, already refuses to start on any error, and its handler alerts.
- **Kept (65).** A file that cannot be statted is a rejection with its reason.

### symbol_validator.py (3 ledger rows: 3 fixed)

- **A check that cannot run raises.** A module of the target's own that cannot be read or parsed (71, 152), and a test source that does not parse (137), raise `SymbolCheckError`, a ValueError, naming the file and the cause after an ERROR line. They returned None or an empty list, the same answer as "every import resolves".
- **Not the repository's own is still quiet.** An import from the standard library or a third-party package is not this check's to make.
- **Where the raise goes.** N4c (`nodes/augment_tests.py`) does not catch it, so the run ends through the entry point's handler, which alerts. Catching it at N4c's two calls and returning it as `error_message` would end the run at HALT instead.

### knowledge/patterns.py (2 ledger rows: 2 fixed)

- **The knowledge base is read or refused.** A missing types.yaml (24) raises FileNotFoundError naming it. One that cannot be read, does not parse, or holds no `test_types` mapping (30) raises `KnowledgeBaseError`, a ValueError. Each comes after an ERROR line.
- **The stand-in is deleted.** Both failures fell back, silently, to a shorter inline copy of the definitions that differed from the file. It existed only for those failures.
- **Where the raise goes.** N0 and N1 read the knowledge base outside any handler, so a broken install ends the run at the first node, through the entry point's handler, which alerts.

### templates/runbook.py (3 ledger rows: 3 fixed)

- **No invented sections.** An LLD with no prerequisites (172), no procedure (200) or no verification steps (210) raises ValueError naming the feature, the issue and every missing section, after an ERROR line and before anything is written. The template wrote invented ones in their place, and the runbook read as written from the LLD.
- **The caller still swallows it.** N8 (`nodes/document.py`) catches every exception from the runbook and prints "SKIPPED" on stdout. That handler is its own ledger row, `document.py:308`, in another batch.
- **A defect that row's fix will expose.** The section patterns allow one digit before a heading, so "## 10. Verification" and "## 2.2 Dependencies" are not found. On such an LLD the runbook now raises where it used to be invented.

### templates/wiki_page.py (2 ledger rows: 2 fixed)

- **No placeholder overview (120).** An LLD with no overview raises ValueError naming the feature, the issue and the headings searched, after an ERROR line and before anything is written.
- **A missing sidebar is said (169).** `update_wiki_sidebar` raises FileNotFoundError naming `_Sidebar.md`, after an ERROR line. It returned False, the same answer as "already linked", and N8 ignored it. False now means only "already linked".
- **The caller still swallows both.** N8 catches every exception from the wiki step and prints "SKIPPED" on stdout: ledger rows `document.py:289` and `document.py:292`, in another batch.

### templates/cp_docs.py (2 ledger rows: 2 fixed)

- **No invented commands (137, 159).** An LLD that shows no command raises ValueError naming the tool, the issue and what was searched, after an ERROR line and before anything is written. The CLI document carried an invented reference row and usage block, neither of them the tool's.
- **The caller still swallows it.** N8 catches every exception from the c/p docs and prints "SKIPPED": ledger row `document.py:338`, in another batch. The CLI document is written first, so no prompt document is written without it.


---

# 3585 - Implementation Report: loud failure in the testing workflow, batch A

## 1. Metadata

| Field | Value |
|-------|-------|
| **Issue** | #3585 (step 5, the #3581 sweep); module issue #3810 for `checkpoints.py` |
| **LLD** | None: the work order is #3585, and each site's prescription is its row in `docs/audits/0908-loud-failure-sweep-ledger.md` |
| **Test Report** | `docs/reports/3585/test-report.md` |
| **Implementer** | Claude Opus 5.5 via Claude Code |
| **Date** | 2026-10-31 |
| **Branch** | `3585-testing-verify` |

## 2. Summary

Batch A brings four modules of the testing workflow under ADR 0236 and standard 0034: every failure is loud, logged with details, stops what depends on it, and alerts the operator. Each module is one commit. The ledger's line numbers are from commit `79e18ad1`.

### 2.1 `assemblyzero/workflows/testing/checkpoints.py` (#3810, 14 rows fixed)

`commit_checkpoint`, `record_measurement` and `read_measurement` used to be best-effort: every git failure printed "(non-fatal)" to stdout and returned False or None, which callers read as "nothing to commit" or "no measurement". Each failure now writes one ERROR line to stderr, logs it, and raises `CheckpointError` naming the worktree or commit, the git command, its exit code and git's stderr. Only exit 1 of `git diff --cached --quiet` reads as staged, and only git's "no note found" (exit 1, nothing on stdout) reads as an unmeasured commit. A note is parsed field by field, so a corrupt note and numbers that do not convert are both live, named failures. The three `# fail-open:` tags are gone.

The module alerts no one itself; the caller that can stop does. N5 now notes its measurement through `_note_measurement` in `verify_phases.py`, which turns `CheckpointError` into N5's halt; `route_after_green` sends it to HALT, which alerts. The halt site is the new gate `impl.measurement_not_noted`, and the impl halt-row ratchet rises from 44 to 45.

### 2.2 `assemblyzero/workflows/testing/nodes/verify_phases.py` (33 rows fixed, 18 compliant rows pinned)

Every step N3 and N5 depend on raises `PhaseStepError` after an ERROR line: pytest that times out, cannot start or lacks pytest-cov for a coverage run; a red marker, test file, spec suite or audit directory that cannot be read or written; a snapshot, restore, dropping removal or visual sample that fails; a failed `git status`; a coverage target nothing names (the hard-coded default is gone) or that lies outside the repository; a runner that crashed or exited non-zero with no failure; an unknown coverage_type; a passing leg with no coverage figure; a critical skipped test. The two entry points turn it into one registered halt, gate `impl.phase_step_failed` (impl ratchet 46). A run with no framework, or naming an unknown one, halts through `FrameworkLegError`; a full suite whose exit contradicts its parse halts at the gate. A state with no `audit_dir` still writes no trail (only a direct call omits it); a named directory that is gone halts.

### 2.3 `assemblyzero/workflows/testing/nodes/cleanup_helpers.py` (4 fixed, 2 compliant)

A failed `git worktree list` raises `CalledProcessError`; only git's not-found message for this branch reads as already deleted; an unreadable lineage artifact or an unparsable coverage figure raises `LineageReadError`.

### 2.4 `assemblyzero/workflows/testing/nodes/cleanup.py` (N9, 8 fixed)

Every N9 failure writes an ERROR line and raises `CleanupError`, because N9's edge to END is unconditional; N9 reads the declared keys (`coverage_achieved`, `coverage_target`, `workflow_status`) and refuses when one, or `repo_root`, is absent; `route_after_document` raises when N8 leaves no issue_number. The graph changes that would let N8 and N9 route to HALT instead belong to `graph.py`.

## 3. Files Created

| File | Description |
|------|-------------|
| `tests/unit/test_checkpoints_loud_failure.py` | One test per ledger site, the kept behaviours, and N5's halt on a note it cannot write |
| `tests/unit/test_verify_phases_loud_failure.py` | One test per site, kept behaviours, and the 18 compliant rows (69 tests) |
| `tests/unit/test_cleanup_helpers_loud_failure.py` | One test per site and the two compliant rows (10 tests) |
| `tests/unit/test_cleanup_loud_failure.py` | One test per site and the kept behaviours (12 tests) |

## 4. Files Modified

| File | Description |
|------|-------------|
| `assemblyzero/workflows/testing/checkpoints.py` | `CheckpointError`; every git failure raises after an ERROR line; field parser for the note |
| `assemblyzero/workflows/testing/nodes/verify_phases.py` | `_note_measurement`: a note N5 cannot write is N5's halt |
| `assemblyzero/core/gate_registry.py` | Gate `impl.measurement_not_noted` |
| `tests/fixtures/gate_registry_baseline.json` | impl halt rows 44 to 45 |
| `tests/unit/conftest.py` | Autouse stand-in for the name N5 calls through (`verify_phases.record_measurement`); N5's unit tests measure fake runs in plain directories |
| `tests/unit/test_tdd_checkpoints.py`, `tests/unit/test_impl_resume_prefers_best_measured.py`, `tests/unit/test_impl_lands_through_driver.py` | Tests that asserted the retired best-effort behaviour now assert the raise |

## 5. Deviations from the ledger

None for `checkpoints.py`. Two defects found and not fixed (not ledger sites): `record_measurement` still returns False for a path that is not a directory, and `orchestrator/stages.py::_best_measured_attempt` reads every grave as unmeasured when `target_repo` is "".

## 6. Compliance with standard 0034

| Failure path | Loud | Logged | Stops | Alerts |
|---|---|---|---|---|
| A checkpoint commit fails (any git step, timeout, missing worktree) | ERROR line on stderr | `logger.error` and the exception message: worktree, command, exit code, stderr | `CheckpointError` raised | By the caller: the standalone finish's entry-point handler; the graph's checkpoint wrapper is batch C's row `graph.py:128` |
| N5's measurement note cannot be written | ERROR line on stderr | as above, plus the note | N5 returns `error_message`, routed to HALT | HALT alerts |
| A measurement note cannot be read or is corrupt | ERROR line on stderr | commit, repository, note text | `CheckpointError` raised out of the impl stage | The orchestrator entry point's handler |
