# Implementation report: #4512, #4513, #4514, #4515, #4516, #4517

Six defects from the first real TypeScript implementation run, on a private target, 2026-11-01. It wrote all seven files and halted at the green phase on one test line.

## #4512: the prompt hid the type

`type_declarations_for` in `edit_script_fix.py` reads the types a TypeScript compiler error names, walks the failing file's relative imports two levels, and adds each declaration to the fix prompt as read-only reference. A type declared in the failing file is already in the prompt, and a type found nowhere is said to be missing.

`build_code_edit_script_prompt` also lists the files the run may change and says a file off the list cannot change, so `NO-EDIT` can no longer point at one. Rule 5's wording stands, and the new section narrows it.

The bad line was not the model's. It is in the spec's own test body, and the run copied it. The repair still belongs here, because a line that is wrong for any reason needs the declaration to be fixed.

## #4513: the final newline

`extract_code_block` strips a reply, and N4 wrote the stripped text, so all seven modified files lost their final newline and the target's lint test failed. `final_newline_as_before` restores it at both write points, the main loop and the batch writer. A file that had no final newline keeps none.

## #4514: a spec's test bodies were unproven

Three completeness checks, each building the file exactly as the scaffolder will:

- `spec_tests_pass_target_lint` runs ruff on stdin with the target's own configuration, under the path the file will have, and names the test function each finding falls in, because the drafter may change only what a complaint names. It uses the ruff on PATH, since the target's environment does not exist at the spec stage.
- `spec_tests_start_js_tools_in_their_project` refuses a package manager started with no `cwd` on a target with no `package.json` at its root.
- `spec_tests_name_filters_can_match` refuses a test-name filter holding a bare regular-expression group. This requirement was added during the work: `-t "REQ-5 (row 080)"` matches no title, Vitest skips every test and exits 0, and eight of the real spec's twelve tests could not fail.

R3 as filed could not be built, because no mechanical rule tells a wrong test from wrong code. Every honest assertion failure is raised in the test file. The decidable part is built: when a revision changes no file and the failure names the spec's suite, the message says the spec may have to change.

A check that cannot emit the file fails, it does not defer to another check, because ADR 0236 withdrew the fail-open tag.

## #4515: an unchanged tree

R1 as filed would have added a new way to end a run, and the gate ratchet requires an operator ruling for that. None exists, and #2723 ruled that the iteration cap ends this loop. So it is an advisory, `impl.stagnation.nothing_changed`, printed at once and carried in the state as `nothing_changed`. The cap's halt quotes it, on both the pytest and the Vitest paths.

The cap's message now says when the typecheck stopped the run and no test ran, names the first compiler error, and no longer reports a test count. `TestRunResult` gained `typecheck_failed` and `failure_summary`.

## #4516: every framework runs

`verify_green_phase` collects each framework's stop and picks one route afterwards: a halt first, then a repair, then a coverage gap, with equal ranks in the frameworks' order. N4 and a halt hear from all of them. Vitest now gives a compact summary of its failed tests instead of the raw report, which carries every passing test as well. A single-framework run takes the same route as before.

## #4517: where a halt happened

The testing graph's nodes record `last_node`, and `_infer_stage` reads it first. Other workflows infer as before. A halt from the iteration cap is `iterations_exhausted`, classified first, because the message can quote a test failure whose words must not be read as the workflow's own.

## Left open

- #4510: why agy stays alive after answering.
- #4519: the spec's TypeScript test bodies are not checked before a run, because they refer to types the run has yet to write. One of them held the line behind #4512.
- The batch writer's newline and change tracking are exercised by no new test. It writes only Add files that do not yet exist.
