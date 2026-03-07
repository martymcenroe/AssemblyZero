File written to `tests/unit/test_implement_code_routing.py`. All 16 test scenarios from the LLD are covered:

- **T010–T080**: `select_model_for_file()` routing rules (init.py, conftest.py, test scaffold, line count boundaries, deeply nested paths, unknown size)
- **T090–T100**: `call_claude_for_file()` signature inspection (model param exists, default is None)
- **T110**: `generate_file_with_retry()` integration (routing called, model passed through)
- **T120–T140**: Edge cases (negative line count, 1-line file, 51-line file)
- **Logging tests**: All 4 routing reasons verified via caplog
- **Constants sanity check**: `SMALL_FILE_LINE_THRESHOLD == 50`

What do you want to work on next?
