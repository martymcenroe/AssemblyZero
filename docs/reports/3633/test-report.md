# Test report: #3633

## Changed tests

- `tests/unit/test_new_repo.py::TestMainLocalWorkflow::test_T260_local_creates_all_files`: asserts `GEMINI.md` is absent from a scaffolded repository.
- `tests/unit/test_new_repo.py::TestMainLocalWorkflow::test_T262_no_gemini_md_is_written_or_named`, replacing `test_T262_gemini_md_restates_no_universal_rules`, which read the file's text: asserts no `GEMINI.md` is written and that no generated file names one, so the inventory and README cannot promise a file that is not there.

## Runs, 2026-10-05

- `tests/unit/test_new_repo.py`: 131 passed.
- Full `tests/unit` suite: 10759 passed, 68 skipped, 6 xfailed, 7 deselected in 9m 21s.
- `ruff check tools/new_repo.py tests/unit/test_new_repo.py`: 38 findings, every one present on `main` before this change (the untouched copies report the same 38); none on a changed line.
