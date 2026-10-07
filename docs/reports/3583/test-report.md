# Test Report: the rest of the API-key path removed (#3583, ADR 0237)

## Tests added

`tests/unit/test_no_api_key_path.py`, the guard ADR 0237 defines. It is built on `ast`, and uses no pattern matching:

- `test_no_module_imports_a_key_sdk_or_reads_a_key` checks every tracked module under `assemblyzero/` and `tools/`. It fails on:
  - an import of `google.genai`, `google.generativeai`, `google.api_core` or `langchain_google_genai`, including `from google import genai`;
  - a read of `GEMINI_API_KEY` or `GOOGLE_API_KEY`, through `os.environ[...]`, `os.environ.get`, `pop` or `setdefault`, `os.getenv`, or a bare `environ` or `getenv`.

  It reads files as `utf-8-sig`, because one module (`assemblyzero/core/llm_provider.py`) starts with a byte-order mark that `ast.parse` rejects.
- `test_no_key_sdk_is_a_dependency`: `pyproject.toml` names none of `google-genai`, `google-generativeai`, `langchain-google-genai`, `google-auth` or `google-api-core`.
- T1: `test_the_guard_catches_each_shape` (nine fixtures) and `test_the_guard_passes_clean_code`.

## Tests changed

`tests/unit/test_gemini_client.py::TestErrorClassification` now drives the live path: `classify_agy_error`, then `GeminiClient._error_type_from_classified`. The removed `_classify_error` is gone from it.
- Quota, capacity and auth are each covered by three messages.
- `test_a_key_error_is_not_an_agy_classification` asserts that `API_KEY_INVALID` now falls to `UNKNOWN`, which fails closed.

## Runs, 2026-10-07

- `tests/unit/test_no_api_key_path.py`: 12 passed.
- `test_no_api_key_path.py`, `test_gemini_client.py`, `test_adversarial_gemini.py` and `test_llm_provider.py`: 218 passed before the BOM fix; the guard's tree check then passed too.
- Full `tests/unit` tier, with the machine quiet: 10881 passed before main moved; after rebasing onto `c8bde904`, 10896 passed, 66 skipped, 7 deselected, 6 xfailed in 8m 40s.
- T2: `poetry show google-auth` in this branch's environment after `poetry remove google-auth`: `Package google-auth not found`. `poetry check --lock`: `All set!`.
- `tools/audit_fail_open.py --check --strict`: PASS. The baseline was regenerated because the dead code removed took seven sites with it (9542 down to 9535 on the rebased tree); its frozen sites are unchanged at 438, the number `main` already held. `tools/audit_halt_sites.py --check`: PASS.
- `tests/unit/test_land_2283_guard.py`, `test_no_api_key_path.py` and `test_no_spelled_projects_root.py`: 32 passed after the `land_2283` text fix.
