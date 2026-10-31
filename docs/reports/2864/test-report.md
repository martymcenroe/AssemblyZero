# Test Report: remove the paid Anthropic API path (#2864, #2950)

Run with no `ANTHROPIC_API_KEY` in the environment (`env -u ANTHROPIC_API_KEY`) and with the `anthropic` and `langchain-anthropic` packages uninstalled from the virtualenv.

## The absence is tested: `tests/unit/test_no_api_key_path.py` (extended, 22 tests)

The existing guard for the Gemini key path was extended rather than duplicated, since the property is the same. From the AST and the TOML, never a pattern:

- no module under `assemblyzero/` or `tools/` imports `anthropic` or `langchain_anthropic`;
- none reads `ANTHROPIC_API_KEY` through `os.environ[...]`, `os.environ.get`, `os.getenv` or `environ.get`;
- none compares a code string against `ANTHROPIC_API_KEY`, or starts one with it, which is what a `.env` loader does (docstrings and bare strings are not code strings);
- `pyproject.toml` and, new, `poetry.lock` name neither package.

`test_the_guard_catches_each_shape` gained nine shapes (the SDK import forms, the three environment reads, a loader comparison and a loader prefix test), and `test_the_guard_passes_clean_code` gained comment, docstring and look-alike-import cases.

## Behaviour tests

- `tests/unit/test_llm_provider.py::TestGetProvider`: `claude:opus` is exactly `ClaudeCLIProvider`; `anthropic:haiku` raises `ValueError` "Unknown provider 'anthropic'"; the unknown-provider message lists `claude, gemini, mock, scripted`.
- `tests/unit/test_llm_provider_loud_failure.py::test_2864_a_usage_limit_stops_the_call_and_says_to_wait`: a CLI exit with "usage limit" returns a failed, non-retryable result, records the exhaustion, and prints `ERROR [LLM] [CAPACITY] ...` to stderr.
- `tests/unit/test_claude_spend_lock_refusal.py::test_t2_an_anthropic_api_seat_override_is_refused`: an `anthropic:` seat is a `ProfileError`, with the lock on and off. Its allow-list of spend sites no longer holds the two SDK entries.
- `tests/unit/test_model_record.py::test_no_fallback_field_is_recorded`.
- `tests/unit/test_testing_workflow.py::test_call_claude_headless_has_no_sdk_fallback` replaces the test that injected a fake `anthropic` module: with the CLI missing the call returns an error and nothing answers.

## Deleted with the code they tested

- `tests/unit/test_document_assembler.py` (the `workflows/lld` node), `test_prompt_caching.py` (AnthropicProvider cache directives), `test_errors_loud_failure.py` (the `retry-after` read in the SDK classifier).
- Classes: `TestLoadAnthropicApiKey`, `TestAnthropicProvider`, `TestFallbackProvider`, `TestCircuitBreaker`, `TestNonRetryableCircuitBreaker`, `TestAPIPolicy` (in `test_llm_provider.py`); `TestFallbackProviderJsonSchema` and two single tests (`test_llm_provider_json_schema.py`); `TestTheApiProviderFailsLoudly` and `TestTheFallbackIsLoud` (`test_llm_provider_loud_failure.py`); `TestClassifyAnthropicError` (`test_errors.py`); `TestCircuitBreakerPersistence` (`test_retry.py`); the SDK-layer tests of `test_529_hardening.py`; the parser test T120 of `test_llm_instrumentation.py`.
- Repointed, not deleted: `test_model_call_ledger.py` (a failed `claude` call now stands where `anthropic` stood), `test_adversarial_node.py` (the message it mimics), `test_gate_registry.py` and `test_node_modules_supply_nodes.py` (the `assembly_node` exemption).

## Audits

- `tools/audit_loud_failure.py --check`: PASS, 118 sites, all in the baseline; `tests/unit/test_loud_failure_check.py` passes with `BASELINE_CEILING` unchanged at 118 (no entry for the deleted code was in that baseline).
- `tools/audit_fail_open.py --check --strict`: PASS, 310 files, 10137 sites, no new fail-open; the baseline lost two sites (215 findings to 213).

## Tiers (2026-10-31)

- `poetry run pytest tests/unit -q --tb=short -p no:cacheprovider`: `13139 passed, 66 skipped, 7 deselected, 7 xfailed, 26 warnings in 1263.96s (0:21:03)`. No `FAIL:` line from the session guards; the tree held only the intended changes afterwards.
- `ASSEMBLYZERO_MOCK_MODE=1 poetry run python tools/test-gate.py tests/ -q --tb=short -m integration`: `64 passed, 7 skipped, 13771 deselected, 26 warnings in 108.56s`.
- `ASSEMBLYZERO_MOCK_MODE=1 poetry run python tools/test-gate.py tests/ -q --tb=short -m e2e`: `19 passed, 13823 deselected, 26 warnings in 128.26s`.
- `ruff check --select F,E9` on the changed Python files: three findings, all in lines this change did not touch (`test_llm_instrumentation.py` lines 208 and 252, `run_requirements_workflow.py` line 1176).
