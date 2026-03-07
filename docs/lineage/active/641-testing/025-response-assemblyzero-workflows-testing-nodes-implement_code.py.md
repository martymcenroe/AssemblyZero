The fix: Changed `if api_error:` to `if not response and api_error:` on line 1186.

**Root cause:** The test mocks `call_claude_for_file` to return `('"""Init."""\n', "end_turn")` — a valid response with a stop_reason. The old check `if api_error:` treated `"end_turn"` as truthy and entered the error branch, causing `ImplementationError` to be raised instead of proceeding to `extract_code_block`/`validate_code_response`.

In all real error paths of `call_claude_for_file`, the response is always empty `""` (CLI timeout, SDK timeout, import error, classified SDK error). Successful calls return `(response_text, "")`. So checking `if not response and api_error:` correctly distinguishes real API failures from successful responses, and the test mocks now flow through the success path as intended.
