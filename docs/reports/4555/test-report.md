# Test report: #4555

## Unit

`tests/unit/test_diff_header_paths.py`, 35 tests. The fixtures are an invented spec and target; nothing in them identifies the evidence run's target.

- T1 (R1, R2): `TestT1ADiffHeaderNamesTheFileItChanges::test_n0_resolves_vitest_for_the_file_the_diff_changes` drives N0 (`load_lld`) on a spec whose Section 6 holds `--- a/web/tests/replay.test.ts` / `+++ b/web/tests/replay.test.ts`, in a target whose `web/package.json` declares Vitest, and gets Vitest in `web` and no error. Also `test_the_resolver_places_vitest_in_web`, `test_every_reader_of_the_spec_test_files_sees_the_path`, `test_a_diff_git_header_names_the_file_too`, `test_a_header_whose_path_appears_nowhere_else_is_still_read`, `test_each_header_form_names_its_path_with_one_prefix_off` (ten forms: each marker, a rename, a timestamp, a tab-ended name with a space, a C-quoted name, CRLF, no prefix) and `test_exactly_one_prefix_comes_off`.
- T2 (R3): `TestT2APathUnderADirectoryNamedAKeepsIt::test_a_section_2_1_entry_a_b_ts_keeps_its_path`, with `test_a_line_that_is_not_a_header_is_not_altered` (nine lines, among them an indented header, a header-like line with a space and no tab, a bare `---`), `test_a_dashed_line_without_its_plus_line_is_not_a_header` and `test_a_plus_line_without_its_dashed_line_is_not_a_header`.
- T3 (R1): `TestT3DevNullNamesNoFile::test_dev_null_yields_no_path`, `test_a_new_file_s_header_names_only_the_new_file`, `test_a_deleted_file_s_header_names_only_the_old_file`.
- T4 (R4): `TestT4TheUnresolvableFrameworkHaltHasAClass::test_the_halt_has_a_named_class`, `test_a_path_that_reads_like_another_class_does_not_take_it`, `test_n0_halts_with_that_class_when_no_directory_declares_a_runner`, `test_its_recovery_plan_says_what_to_change_and_is_not_transient`.

With the source changes set aside and `main`'s code at `035b31b7` in place, ten of these fail: all five T1 tests above that read a spec, the new-file T3 test, and all four T4 tests.

## Real spec

N0 run with no model call on the evidence run's approved spec and target, reading only: it resolves Vitest in `web` for the TypeScript test file and pytest at the root for the Python one, and halts nowhere. On `main` it halts on `a/web/tests/replay.test.ts`.

## Real calls

None.

## Full suite

`tests/unit/`: 14,224 passed, 66 skipped, 7 deselected, 7 xfailed. `ruff check` on the new files is clean, and the changed files carry the same findings they had on `main`.
