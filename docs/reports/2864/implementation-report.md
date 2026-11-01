# Implementation Report: remove the paid Anthropic API path (#2864, #2950)

The operator decided on 2026-09-05 that this fleet does not pay per token: when the weekly quota is exhausted the run waits for it to renew. The paid path is removed, not gated, so that no later edit can restore a spend path by flipping a default.

## What a run does now when the Claude CLI is rate-limited or fails

`get_provider("claude:...")` returns `ClaudeCLIProvider` and nothing else. A failed call returns a failed `LLMCallResult` and prints an ERROR line on stderr. A usage-limit failure is also not retried (`retryable` is false), is recorded in `assemblyzero/core/capacity.py` with the time the quota renews, and prints a `[CAPACITY]` line saying so. The caller routes the failure to HALT, which alerts the operator. No fallback provider runs and no HTTP request is made to any Anthropic endpoint.

## Removed

- `assemblyzero/core/llm_provider.py`: `AnthropicProvider`, `_load_anthropic_api_key`, `FallbackProvider` with its module-level breaker registry and `reset_circuit_breakers`, `set_api_policy`, `is_api_allowed`, the `anthropic` ledger transport. `_build_provider` returns `ClaudeCLIProvider` for `claude:`; `anthropic:` is an unknown provider and raises `ValueError`.
- `assemblyzero/core/errors.py`: `classify_anthropic_error` (the only importer of the SDK) and `_extract_retry_after` (its helper).
- `assemblyzero/nodes/anthropic_provider.py` (scope item 5; its own issue was a duplicate of #2864).
- `--allow-api` and the `set_api_policy` call from `check_requirements.py`, `run_audit.py`, `run_implement_from_lld.py` (only the `--allow-api` lines), `run_implementation_spec_workflow.py`, `run_janitor_workflow.py`, `run_requirements_workflow.py` and `run_scout_workflow.py`.
- `assemblyzero/core/model_record.py`: the `fallback` and `fallback_provider` fields of a call record. Nothing but the tests read them, and no transport can fall back.
- The `anthropic` and `langchain-anthropic` dependencies, by `poetry remove`. `poetry.lock` also loses `distro`, `docstring-parser` and `sniffio`, which only those two needed. Nothing else in the tree imports either package.
- #2950: the `assemblyzero/workflows/lld/` package, 4 files. Nothing reaches it: `run_lld_stage` runs `requirements.graph`, which imports nothing from it, and a search of `assemblyzero/`, `tools/` and `tests/` for `workflows.lld`, `assemble_document_node`, `LLDState` and `LLD_TEMPLATE` found only the package itself and `tests/unit/test_document_assembler.py`. Its node built `ChatAnthropic` directly on a retired model id. Its test and its two reachability-exemption entries (`test_gate_registry.py`, `test_node_modules_supply_nodes.py`) went with it.
- `tests/fixtures/llm_instrumentation/anthropic_api_response.json`, used only by the deleted parser test.

## Changed

- `assemblyzero/core/seats.py`: `check_spec` refuses a seat that names `anthropic:` with a `ProfileError` at profile load, lock or no lock. `ANTHROPIC_PROVIDERS` is now `{"claude"}`, and `_provider_class` and the model-map branch for the API are gone.
- `assemblyzero/telemetry/llm_call_record.py`: `ProviderName` drops `anthropic_api` and `fallback`.
- Comments and docstrings that described the fallback or the API gate, in `llm_provider.py`, `model_call_ledger.py`, `model_scorecard.py`, `claude_client.py` and the two review nodes.
- Docs: README, ADR 0208 (amended in place with the old rows struck through), standard 0021, `wiki/Cost-Management.md`, `wiki/Home.md`, `wiki/Metrics.md`.
- Baselines: `tests/fixtures/fail_open_baseline.json` drops `errors.py::_extract_retry_after` and `llm_provider.py::AnthropicProvider.invoke`. The loud-failure baseline held no entry for the deleted code (those sites were repaired in #3780 and #3774), so it and `BASELINE_CEILING` (118) are unchanged. In `docs/audits/0908-loud-failure-sweep-ledger.md` twelve rows for deleted code (eight in `llm_provider.py`, one in `errors.py`, two in `assembly_node.py`, one in `nodes/anthropic_provider.py`) now read `WON'T DO (#2864): the code is removed`.

## Kept, and why

- `ClaudeCLIProvider`, `GeminiProvider`, `MockProvider`, `ScriptedProvider`, `is_non_retryable_error` and `_is_capacity_message` (the CLI uses both).
- Labels, not paths: the `anthropic` provider string in the cost tracker, the retry tests and `BillingError(provider=...)` examples; the spend lock's "Anthropic model" wording and `anthropic_seats` (the CLI is an Anthropic model); the notional per-token prices for `claude:` models in `tools/model_scorecard.py`; the `@anthropic-ai/claude-code` install hint; `noreply@anthropic.com` in commit trailers.
- `ANTHROPIC_API_KEY` in `tests/e2e/conftest.py`, a list of key names the mock test removes from the environment: it reads nothing.
- `jiter` goes too. It was pinned directly, nothing under `assemblyzero/`, `tools/` or `tests/` imports it, and no package in `poetry.lock` depends on it once the SDK is gone.
- `docs/lld/active/LLD-774.md`, `LLD-775.md`, `wiki/LangGraph-Evolution.md` and `docs/adrs/0223-retire-rag-adopt-tiphys.md` describe the removed code as history and are left.

## Not done

`docs/lessons-learned.md`, `docs/lineage/`, `docs/reports/`, `docs/audits/` (apart from the ledger rows named above) and `docs/lld/done/` are records and were not touched.
