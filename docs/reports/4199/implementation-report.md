# Implementation Report: #4199

## Problem

AssemblyZero could not count its model calls. `GeminiClient` wrote nothing when a call succeeded, the providers' `calls.jsonl` records were written only on armed runs, and agy was never asked for the one output form that reports tokens.

## Change

- `assemblyzero/core/model_call_ledger.py` (new): `record()` appends one JSON line per model call to `~/.claude/logs/model-calls.jsonl` on its side of the machine, or to the file `MODEL_CALL_LEDGER` names. Under pytest with no `MODEL_CALL_LEDGER` it writes nothing. Each line: `ts`, `side`, `program`, `library`, `repo` (a worktree resolves to its repository through its `.git` file), `cwd`, `transport`, `model`, `tokens_in`, `tokens_out`, `usage`, `wall_s`, `outcome`, `error`. A line that cannot be written calls `alert_operator` (ADR 0236): the failure is loud and reaches the operator, and the call's own result stands, since nothing depends on the line. The issue's R5 said a failed write is swallowed; ADR 0236 and both failure gates rule that out, so the write alerts instead (recorded on #4199).
- `assemblyzero/core/gemini_client.py`: the one agy process moved from `_invoke_via_stdin` into `_agy_once`, unchanged except as below; `_invoke_via_stdin` now times it and writes its ledger line when a process started, on a returned failure and on a raised one alike (the raised one is re-raised). agy is asked for `--output-format json`. `_agy_json_reply` recognises agy's `{"status", "response", "usage"}` reply: a status other than `SUCCESS` is a failure, the response text is the answer, and the usage goes on the line. Text that does not open with `{`, and a parsed object that is not agy's envelope, take the plain-text path exactly as before; text that opens like JSON and does not parse raises. Every retry of `invoke()` is its own process and its own line.
- `tests/fixtures/fail_open_baseline.json`: regenerated. Its only key changes are the three agy handlers renamed from `_invoke_via_stdin` to `_agy_once`; `findings_total` is unchanged, because the new code adds no fail-open site.
- `assemblyzero/core/llm_provider.py`: `log_llm_call` ends with `_ledger_line`, which writes one line for a `claude` (transport `claude`) or `anthropic` (transport `anthropic-api`) call, with its tokens; `timeout` when the failure class names one. The Gemini provider writes none there, because GeminiClient writes its lines per process, and the mock provider calls no model.
- `tests/unit/test_agy_wsl_transport.py`: the pinned WSL argv now ends with `--output-format json`.

The #4195 process-group change is untouched: `start_new_session` and the timeout's `kill_process_tree` sit in `_agy_once` as they were.
