# Test Report: Gemini ids agy offers, and runbook 0935 after Auto Review (#4178, #4189)

## New tests

`tests/unit/test_agy_catalog.py` reads `tests/fixtures/agy_models.txt`, the recorded `agy models` output, and takes the first tab-separated field of each model line as the catalog.

- `test_every_allowed_id_is_in_the_catalog` (#4178 AC1): `AGY_GEMINI_MODELS` minus the catalog is empty. Under the old set it fails: the fixture contains no `3.1-pro` id (`grep -c` counts 0), and the old set held only `gemini-3.1-pro-high` and `gemini-3.1-pro-low`.
- `test_every_map_value_is_in_the_catalog_and_allowed`: every `MODEL_MAP` value is in the catalog and passes `FORBIDDEN_MODELS`.
- `test_the_catalog_lists_argon`: the three Argon ids are in the recorded catalog, so the refusals below test something real.
- `test_argon_is_forbidden[...]`: each Argon id is caught by `FORBIDDEN_MODELS`, and is in neither `AGY_GEMINI_MODELS` nor the map.
- `test_the_client_refuses_argon[...]`: `GeminiClient(model=<argon id>)` raises before any call.
- `test_a_seat_naming_argon_is_refused[...]`: `check_spec` refuses `gemini:gemini-4-argon-high` and `gemini:4-argon`.
- `test_the_adversarial_reply_check_refuses_argon`: a reply naming Argon is not taken as Pro.
- `test_the_defaults_are_allowed_ids`: `REVIEWER_MODEL`, the preflight probe and `GeminiProvider()` default to 3.8 Flash.
- `test_flash_resolves_by_name[low|medium|high]` (#4178 AC2): `GeminiProvider("3.8-flash-<tier>")` resolves to `gemini-3.8-flash-<tier>` and is not refused.

`tests/unit/test_merge_instructions.py`:

- `test_runbook_mentions_auto_review_only_as_retired` (#4189 test 1): every line of 0935 naming Auto Review also carries one of "retired", "skipped", "Earlier versions", "#3663".
- `test_runbook_tree_has_the_no_review_branch` (#4189 test 2): the decision tree's fenced block contains `REVIEW_REQUIRED` and "No Review At All".
- `gh pr close` and `gh pr reopen` added to the forbidden command forms, so no `bash` block in 0935 or `CLAUDE.md` can teach them again.

## Changed tests

- `test_agy_both_seats.py`, `test_model_record.py`, `test_preflight_transport.py`, `test_seats.py` and `test_llm_provider.py` pinned `gemini-3.1-pro-high`, or "pro" in the resolved id, and now pin `gemini-3.8-flash-high`.
- `test_adversarial_gemini.py`: two tests asserted the default adversarial seat resolves to a permitted Pro id. They are replaced by `test_the_default_seat_is_refused_while_agy_offers_no_pro`, which asserts the seat refuses with `ForbiddenModelError` ("flash tier"). Two plumbing tests that build the client now stub the model check, since its refusal is tested on its own; they still assert which spec reaches `get_provider`.

## Full local suite (WSL)

The final code, as committed:

```
poetry run pytest tests/unit -q
1 failed, 11189 passed, 66 skipped, 7 deselected, 6 xfailed
```

The one failure is `test_cascade_detector.py::TestDetectionLatency::test_typical_input_latency`, a wall-clock timing test tracked in #4190. Run alone straight after, `test_cascade_detector.py` passed 53 of 53. It failed the same way in the first full run of the replaced Argon version, and passed in that version's second full run.

## Lint

Ruff counts unchanged against `main` across the changed Python files: 56 before, 56 after. `tests/unit/test_agy_catalog.py` is clean.

## Live calls

On 2026-10-21 at about 6:24 PM Central, one call went through this branch's `GeminiClient` and agy with the default alias, as the pipeline makes it, and a one-word prompt. The probe refused to run unless the alias resolved to 3.8 Flash.

```
3.1-pro gemini-3.8-flash-high success 'Blue'
```

The first version of this change made one Argon call, shortly after 6:10 PM, with the same one-word prompt. That version is replaced by this one and never merged.
