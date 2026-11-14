# Implementation report: #4274

## The defect

`parse_files_to_modify` in `assemblyzero/workflows/implementation_spec/nodes/load_lld.py` reads the LLD's Section 2.1 Files Changed table with a row pattern that needs three cells. A row with fewer cells than the header names no change type or no description for its file, and it was skipped without a word, or matched across the line break into the next row. N0 returned no error for a two-cell row.

## The fix

- The table pattern now captures the header row.
- `_count_cells` counts one row's cells: it drops the outer pipes and splits the rest on `|`, so `| a | b |` has two cells and `| a | b | |` three.
- Before any row is read, each body row with fewer cells than the header raises `ValueError`, naming the row's cell count, the header's, the header itself, and the row. N0's existing handler halts on it.

`_count_cells` first stripped the pipes with `startswith` and a slice, which `ruff` reported as two `FURB188` findings HEAD did not have. It now uses `removeprefix("|")` and `removesuffix("|")`, which strip the same single pipe at each end.

## Tests

In `tests/unit/test_spec_short_files_changed_row_4274.py` (new):

- `TestTheNodeHalts::test_t1_a_two_cell_row_halts_n0_with_the_row_named`, parametrized over where the short row sits (T1)
- `TestTheNodeHalts::test_the_halt_is_loud_on_stderr`
- `TestTheParser::test_a_short_row_raises_naming_the_row_and_the_table`
- `TestTheParser::test_a_short_directory_row_raises_too`
- `TestTheParser::test_a_row_with_an_empty_description_cell_is_full`
- `TestTheParser::test_full_rows_parse_as_before`

Before the fix: `6 failed, 2 passed`. The `[last]` case gave `AssertionError: N0 must return an error_message for a two-cell row`.

## The repository's own LLDs

A parse of the repository's 121 LLDs with the fix gave `{'parsed': 105, 'short_row': 0, 'other_error': 16}`, so no real LLD trips the check.

## The run

On Ubuntu, 2026-11-14, after the `removeprefix` change, the new file with `test_spec_load_lld_loud_failure.py`, `test_load_lld.py`, `test_load_lld_v2.py`, `test_load_lld_loud_failure.py` and `tests/integration/test_lld_parsing_chain.py`: `99 passed`.

`ruff check` on `load_lld.py` reports the one finding HEAD has (`I001`), none added. The new test file is clean.
