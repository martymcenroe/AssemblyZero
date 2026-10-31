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

## Compliance

Every failure path above meets the four properties of standard 0034: it writes an ERROR line on stderr naming what failed and its subject, it stops what depends on it (a HALT route, or a raise the entry point owns), and it alerts the operator, through HALT, through the entry point's handler, or from the node when nothing stops.
