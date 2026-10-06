# Test report: #3697, #3698, #3699, #3700

## Changed tests

- `tests/unit/test_model_scorecard.py::TestPricingTable::test_no_pricing_key_is_forbidden` (new): asserts no key of `MODEL_PRICING` is on `config.FORBIDDEN_MODELS`.
- `TestPricingTable::test_every_gemini_key_is_an_id_the_provider_sends` (new): every Gemini key in `MODEL_PRICING` is a value of `GeminiProvider.MODEL_MAP`. It runs in this direction because the map still carries dead and forbidden ids (#3710).
- `TestPricingTable::test_fixture_model_is_priced` (new): `FIXTURE_MODEL` is priced.
- `TestPricingTable::test_gemini_client_accepts_fixture_model` (new): constructs a real `GeminiClient` with the fixture id, with only the agy lookup patched out, so the test follows any check the constructor gains.
- `TestPricingTable::test_gemini_on_subscription_costs_nothing` (new): the fixture id costs 0.0 for a million tokens each way.
- `FIXTURE_MODEL` is `config.REVIEWER_MODEL`, the id the pipeline sends to the reviewer seat, in place of the forbidden `gemini-3-pro-preview`. `TestParseReviewLogs::test_basic_parsing` uses it.
- `TestEstimateCost::test_known_model` and `test_small_token_count`: check the cost arithmetic on `claude:sonnet` ($3.00/$15.00 per million), since a zero-priced row cannot test the formula.

## Runs, 2026-10-06

- `tests/unit/test_model_scorecard.py`: 27 passed.
- Full `tests/unit` suite through `tools/test-gate.py`: 10764 passed, 68 skipped, 7 deselected, 6 xfailed in 8m 37s.
- Acceptance greps from #3697 and #3698: `gemini-retry` and `gemini (-p|--model)` under `.claude` and `tools`, and `gemini-rotate` under `tools`, all print nothing.
- `ruff check .`: 2775 findings on this branch and 2775 on `main`. The three changed Python files carry 23 on both, the same findings. The import block this change extended in `test_model_scorecard.py` was already flagged unsorted (I001) on `main`.
