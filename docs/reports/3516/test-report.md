# Test Report: agy tool-execution posture (#3516)

## New tests

`tests/unit/test_agy_sandbox_args.py`:

| Test | What it pins |
|---|---|
| `test_the_safety_args_are_the_sandbox_flag` | `AGY_SAFETY_ARGS == ["--sandbox"]` |
| `test_the_pty_path_passes_sandbox` | the short-prompt PTY argv starts `agy --sandbox`, with the flag before `-p`; `winpty` is stubbed so the test runs on Linux CI |
| `test_the_stdin_path_passes_sandbox` | the oversize-prompt stdin argv starts `agy --sandbox` |

All three fail on the code before this change, which was checked by stashing `gemini_client.py` and rerunning.

## Updated test

`test_gemini_client.py::TestInvokeViaStdin::test_oversize_prompt_routes_to_stdin_path` now expects `argv[1:4] == ["--sandbox", "--model", "gemini-3.1-pro-high"]`.

## Run

```
pytest tests/unit/test_agy_sandbox_args.py tests/unit/test_gemini_call_bounds.py
       tests/unit/test_gemini_client.py tests/unit/test_gemini_client_capacity.py
       tests/unit/test_stage_watchdog.py
78 passed
```

`tools/audit_fail_open.py --check`: PASS, with no baseline change.

## Live evidence (not a unit test)

Three live `agy` calls through `GeminiClient._invoke_via_cli` form the experiment in ADR 0233, plus two latency calls. The latency calls were a pure-text "pong": 7.7 s with `--sandbox` and 8.4 s without. They show the flag costs nothing when no tool is attempted.
