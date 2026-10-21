# Test Report: Gemini ids agy offers, and runbook 0935 after Auto Review (#4178, #4189)

## New tests

`tests/unit/test_agy_catalog.py` reads `tests/fixtures/agy_models.txt`, the recorded `agy models` output, and takes the first tab-separated field of each model line as the catalog.

- `test_every_allowed_id_is_in_the_catalog` (#4178 AC1): `AGY_GEMINI_MODELS` minus the catalog is empty. Under the old set it fails: the fixture contains no `3.1-pro` id (`grep -c` counts 0), and the old set held only `gemini-3.1-pro-high` and `gemini-3.1-pro-low`.
- `test_every_map_value_is_in_the_catalog`: the same for every `MODEL_MAP` value.
- `test_flash_resolves_by_name[low|medium|high]` (#4178 AC2): `GeminiProvider("3.8-flash-<tier>")` resolves to `gemini-3.8-flash-<tier>` and is not refused.
- `test_default_ids_are_in_the_review_tier`: `REVIEWER_MODEL`, the preflight probe and `GeminiProvider()` default to Argon.
- `test_no_review_alias_resolves_to_flash`: only an alias containing "flash" reaches a Flash id.
- `test_adversarial_seat_resolves_to_argon`, `test_adversarial_seat_still_refuses_flash`, `test_adversarial_reply_check_accepts_argon[...]`, `test_adversarial_reply_check_refuses_flash`: the adversarial gate keeps its Flash refusal and accepts Argon replies.

`tests/unit/test_merge_instructions.py`:

- `test_runbook_mentions_auto_review_only_as_retired` (#4189 test 1): every line of 0935 naming Auto Review also carries one of "retired", "skipped", "Earlier versions", "#3663".
- `test_runbook_tree_has_the_no_review_branch` (#4189 test 2): the decision tree's fenced block contains `REVIEW_REQUIRED` and "No Review At All".
- `gh pr close` and `gh pr reopen` added to the forbidden command forms, so no `bash` block in 0935 or `CLAUDE.md` can teach them again.

## Changed tests

Five tests pinned `gemini-3.1-pro-high`, or "pro" in the resolved id, and now pin Argon: `test_adversarial_gemini.py`, `test_agy_both_seats.py`, `test_model_record.py`, `test_preflight_transport.py`, `test_seats.py`. `test_llm_provider.py`'s alias assertions moved the same way.

## Full local suite (WSL)

```
poetry run pytest tests/unit -q
11189 passed, 66 skipped, 7 deselected, 6 xfailed
```

The first full run had 7 failures: the five pinned tests above, and `test_cascade_detector.py::TestDetectionLatency::test_typical_input_latency` and `test_max_input_latency`. The latency pair passed alone on `main` and on this branch, and in the second full run.

## Lint

Ruff counts unchanged against `main` across the changed Python files: 56 before, 56 after. `tests/unit/test_agy_catalog.py` is clean.

## Live calls

On 2026-10-21 at about 6:10 PM Central, one call per id went through this branch's `GeminiClient` and agy, as the pipeline makes it, with a one-word prompt:

```
3.1-pro gemini-4-argon-high success 'Blue'
3.8-flash-low gemini-3.8-flash-low success 'Blue'
```

A full review run on Argon is left to the next pipeline run.
