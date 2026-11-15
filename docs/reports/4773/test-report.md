# Test report: #4773

## New tests

Every test points the config path at a file under `tmp_path`, or patches HOME for a fresh copy of the module. None reads the real config.

| Test | Tests |
|---|---|
| T1 (R1) | `test_the_roots_come_from_the_setting_in_order_and_projects_is_the_first`, `test_the_windows_side_reads_its_own_pointer_and_spells_each_root`, `test_spell_root_gives_each_side_its_spelling`, `test_read_roots_setting_returns_the_roots_for_one_side`, `test_the_lazy_attributes_honour_the_patched_pointer_on_every_read` |
| T2 (R2) | `test_a_missing_root_stops_the_walk_and_is_named`, `test_a_missing_root_given_by_the_caller_stops_the_walk_too`, `test_locating_a_repository_with_a_root_missing_is_refused` |
| T3 (R4) | `test_a_name_under_two_roots_is_reported_and_left_out`, `test_locating_a_name_under_two_roots_raises_naming_both_copies`, `test_locating_a_name_under_one_root_gives_that_copy`, `test_locating_a_name_under_no_root_gives_the_first_roots_path` |
| T4 (R5) | `test_with_no_pointer_the_roots_are_the_checkouts_parent`, `test_a_walk_with_no_pointer_prints_one_line_saying_so` |
| T5 (R6) | `test_a_malformed_setting_stops_any_tool_naming_the_file_and_the_reason`, `test_a_pointer_to_a_missing_file_names_it`, `test_from_import_of_projects_raises_on_a_broken_pointer`, `test_a_broken_pointer_in_the_config_stops_any_tool_naming_the_config`, `test_importing_for_repo_root_reads_no_config_even_when_the_pointer_is_broken`, `test_the_pointer_reader_agrees_with_assemblyzero_config` |
| T6 (R7) | all of `tests/unit/test_set_projects_roots_file.py`, plus the pointer tests added to `tests/unit/test_assemblyzero_config_derived.py` |
| T7 (R1) | `test_with_no_pointer_nothing_outside_the_checkouts_parent_is_read`, `test_neither_the_module_nor_the_program_holds_a_settings_path`, `test_the_program_takes_the_settings_path_only_from_the_command_line` |

The tests were written first. They failed before the module and the program existed.

## Targeted run, 2026-11-14

The three new or extended files, with `test_set_new_repo_root.py` and `test_projects_root.py`: `138 passed, 1 warning in 162.05s (0:02:42)`.

## Not yet run

The full unit tier, and the other importers' test files, were not run before this wip commit.
