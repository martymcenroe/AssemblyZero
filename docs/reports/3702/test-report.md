# Test report: #3702, #3703, #3710

## New and changed tests

- `tests/unit/test_gemini_prompt_templates.py` (new, #3702): every template under `.claude/templates/gemini-prompts/` names no `FORBIDDEN_MODELS` id and no `gemini-model-check`, and the template directory is not empty.
- `tests/unit/test_project_json_example.py` (new, #3703): `.claude/project.json.example` parses as JSON, and names neither the Gemini CLI, the deleted wrapper, nor any `FORBIDDEN_MODELS` id.
- `tests/unit/test_llm_provider.py::TestGeminiProvider` (#3710):
  - `test_flash_aliases_are_refused`, which replaces `test_valid_model_flash` and `test_valid_model_3_flash_preview`: `flash`, `2.5-flash` and `3.1-flash-preview` raise "Unknown Gemini model".
  - `test_legacy_pro_aliases_resolve_to_living_id`: `2.5-pro` and `pro` resolve to `gemini-3.1-pro-high`.
  - `test_every_map_value_is_an_id_agy_serves`: every `MODEL_MAP` value is in `config.AGY_GEMINI_MODELS`.
  - `test_no_map_value_is_forbidden`: no `MODEL_MAP` value is on `FORBIDDEN_MODELS`.
- `tests/unit/test_model_scorecard.py::TestPricingTable::test_every_id_the_provider_sends_is_priced` (new): every `MODEL_MAP` value has a price. #3710 noted that this check became possible once the map carried only living ids.

## Runs, 2026-10-06

- The directly affected files (`test_llm_provider`, `test_model_scorecard`, both new files, `test_adversarial_gemini`, `test_seats`, `test_requirements_cli`, `test_requirements_config`, `test_requirements_state`): 387 passed.
- Full `tests/unit` suite through `tools/test-gate.py`: 10780 passed, 68 skipped, 7 deselected, 6 xfailed in 11m 12s.
- `poetry run python -m json.tool .claude/project.json.example`: exit 0.
- `ruff check` on the five changed Python files: 31 findings on this branch and 31 on `main`. The two new test files: no findings.
