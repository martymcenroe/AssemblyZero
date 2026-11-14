# Test report: #4274

## Changed tests

- `tests/unit/test_spec_short_files_changed_row_4274.py` (new, 8 tests):
  - T1: `TestTheNodeHalts::test_t1_a_two_cell_row_halts_n0_with_the_row_named`, parametrized over where the short row sits: `alone`, `last` and `first`.
  - The halt is loud: `TestTheNodeHalts::test_the_halt_is_loud_on_stderr`.
  - The parser: `TestTheParser::test_a_short_row_raises_naming_the_row_and_the_table`, `test_a_short_directory_row_raises_too` and `test_a_row_with_an_empty_description_cell_is_full`.
  - Unchanged behaviour: `TestTheParser::test_full_rows_parse_as_before`.

## Implementation runs, 2026-11-14

- The new file before the fix: `6 failed, 2 passed`.
- The new file with `test_spec_load_lld_loud_failure.py`, `test_load_lld.py`, `test_load_lld_v2.py`, `test_load_lld_loud_failure.py` and `tests/integration/test_lld_parsing_chain.py`, after the fix: `99 passed`.

## Full suite, 2026-11-14

Every tier ran in the worktree after the last edit, at 3:30 AM Central. Each exited 0.

- Unit tier, 3:59 AM Central: `= 14562 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 1119.35s (0:18:39) =`
- Integration tier, 3:42 AM Central: `=== 65 passed, 7 skipped, 15262 deselected, 34 warnings in 76.48s (0:01:16) ====`
- E2E tier, 3:42 AM Central: `========= 19 passed, 15315 deselected, 34 warnings in 80.49s (0:01:20) =========`
- Adversarial tier, 3:42 AM Central: `========= 1 skipped, 15333 deselected, 34 warnings in 63.97s (0:01:03) =========`. The tier's one test makes a live agy call and runs only with `AZ_LIVE_ADVERSARIAL_PROBE=1`.
- `tests/tools/`, 3:41 AM Central: `559 passed, 1 warning in 15.81s`

`tests/integration/test_lld_parsing_chain.py` carries no tier marker and sits outside `tests/unit/`, so none of the five tiers selects it. It was run alone, finishing at 3:42 AM Central: `14 passed, 1 warning in 2.74s`.

No nightly was run.
