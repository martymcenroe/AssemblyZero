# Test Report: #4199

`tests/unit/test_model_call_ledger.py`, a Popen double answering as `agy --output-format json` would, the ledger in the test's `tmp_path`:

- T1: a successful agy reply writes one line with every field set and agy's tokens (2766 in, 41 out); the argv carries `--output-format json`.
- T2: a non-`SUCCESS` status (its tokens kept), a non-zero exit and a timeout each write one line, `failed` or `timeout`.
- T3: an `invoke()` that fails once and then succeeds writes two lines, `failed` then `ok`.
- T4: plain-text output still succeeds, with no tokens; a JSON model answer outside agy's envelope is plain text; text that opens like JSON and does not parse raises and is recorded as `failed`.
- T5: a Claude provider call writes one line with its tokens (fresh, cache-read and cache-written input summed); an Anthropic failure is `anthropic-api`, `failed`; a timeout class is `timeout`; the Gemini and mock providers write none.
- T6: under pytest with no `MODEL_CALL_LEDGER` nothing is written; outside it the ledger is `~/.claude/logs/model-calls.jsonl`; a worktree resolves to its repository in Ubuntu and Windows spelling.
- T7: agy that could not start writes nothing.
- ADR 0236: a line that cannot be written calls `alert_operator`.

The real ledger was checked absent after the runs.

## Gates and suites

- `tests/unit/test_fail_open_audit.py` and `tests/unit/test_loud_failure_check.py` pass with the new files tracked: the baseline's only key changes are the three agy handlers renamed to `_agy_once`, and the new code adds no fail-open site.
- With `test_gemini_client.py`, `test_agy_wsl_transport.py` and `test_gemini_call_bounds.py` (#4195's real-process timeout test included): 158 passed.
- Full suite on the final tree: 35 failed, 11699 passed, 82 skipped, 4 errors. Every failure and every error also fails on `main`: 26 recorded on an untouched `main` worktree for #4195 earlier today, and 14 more (the cascade-rule, `test_issue_161`, `test_mine_verdict_patterns` and `test_open_questions_loop` tests) plus the 4 `TestFixtureSamples` setup errors, each run on `main` at `58b72ca2` this afternoon and failing there too.
- `ruff check` is clean on the new files and on every changed line; the six findings it reports in `gemini_client.py` are on import and assignment lines `main` already has.
