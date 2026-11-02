# Implementation report: #4521, #4522, #4523, #4525

Four defects that the first complete real implementation run showed in its own gates, on a private target, 2026-11-01. The run passed all fourteen steps, and its PR failed CI at once.

## #4525: the regression count

One failed lint test was reported as 11 regressions. The issue put the extra ten down to lines of the test's output. They were ruff's closing `Found 10 errors.`, quoted in the test's message: `parse_pytest_output` took each count from anywhere in the output, so that line set `errors` to 10 beside `failed` 1. Main still reproduces it exactly, `assert (1 + 10) == 1`.

`pytest_summary_counts` in `audit.py` reads pytest's closing line alone, in its `-v` and `-q` forms. `parse_pytest_output` and `PytestRunner.parse_results`, which had the same search, both use it. Output with no closing line, from a killed or interrupted run, counts nothing, and the full-suite gate's existing exit check then halts it as unreadable.

## #4523: the target's gates

R1. `JestRunner.run_lint` runs `npm run lint` when `package.json` declares a `lint` script, and `_verify_green_non_pytest` calls it once every test passes. A failure counts as one failure, as a failed typecheck does, and goes to N4 with the lint's output. At the cap the halt says the lint still fails. `BaseTestRunner.run_lint` returns None, so other runners are unchanged.

R2. A new step, N8.5 (`verify_final_suite`), runs the full-suite gate for every framework after N7.5 and N8 have written, and before N9 lands the run. A regression goes back to N4 through the route N5 uses, under the same cap, budget and repair grace. A file written after N5 that a failure outside it names, as a target's lint test names files, joins `files_to_modify` as a Modify. A failing adversarial test stays as written: handing it to N4 would let a run pass the review by editing it. At the cap, `_stop_after_final_suite` adds the late files the failures name to `_stop_after_green`'s message.

The atlas gains the step (`TOTAL_STEPS` 15), and the step budget gains the loop: nine super-steps an iteration. No halt site is added. The gate's lines name the node that runs it.

## #4521: the import check

An import the file already had is never refused. The base is `existing_content`, or the file on disk when N4 hands the validator none, as it does for an LLD "Add" the base already ships. It is read only when an import would otherwise be refused.

A new import that is neither stdlib, declared, internal nor planned is asked of the target's own environment with `_probe_target_env`, the spec stage's probe, and passes when it imports there. A name the repository or the plan owns is never passed that way, so `pkg.no_such_module` stays refused when `pkg` imports.

A reply that adds a dynamic import the file did not have is refused, naming the line and saying to write a plain import. That covers `importlib.import_module`, `sys.modules`, their `from` forms and `__import__`. A family the file already used, or one the spec names, is not refused.

## #4522: unrequested changes

`unrequested_changes.py` reads each Section 6 `diff` fence's hunks by file, and places each hunk in the base by its own context and removed lines, never by its line numbers. After each N4 pass, `_report_unrequested_changes` compares each Modify file with the run's base. A changed line outside every hunk, whose text is none of the hunks' own lines, is printed under the new advisory row `impl.unrequested_change` and logged as `unrequested_changes`.

`schema_keywords.py` holds the keyword sets of drafts 04, 06, 07, 2019-09 and 2020-12, written out in full. A reply that declares one of those drafts refuses a key that is not a keyword, in a position where only keywords belong. A key the base had, or one the spec quotes, stays.

## Ratchet and fail-open

No halt row was added, so the ratchet's counts are unchanged. Both new refusals sit inside `generate_file_with_retry`'s existing validate-and-retry loop. Every new handler fails closed. An environment that can't answer raises `CompletenessCannotCheck`. A base that doesn't parse stops the check on an ERROR line. The unrequested-change report raises `ChangedLinesError` on a base it can't read, as N5's coverage gate does on the same base.
