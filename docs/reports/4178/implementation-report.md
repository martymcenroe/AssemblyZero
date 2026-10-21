# Implementation Report: Gemini ids agy offers, and runbook 0935 after Auto Review (#4178, #4189)

## #4178: the allowed Gemini ids

`agy models`, read 2026-10-21, lists `gemini-4-argon-{high,medium,low}` and `gemini-3.8-flash-{high,medium,low}` as its Gemini models. It lists no `gemini-3.1-pro` id. `config.AGY_GEMINI_MODELS` named only the two `gemini-3.1-pro` ids, and every `GeminiProvider.MODEL_MAP` alias resolved to one of them, so every Gemini call asked agy for a model it does not have.

The Pro-line aliases now resolve to Gemini 4 Argon, the only non-Flash Gemini agy lists. This is the same remap #1764 and #3710 made when earlier ids died. The run profiles keep their `gemini:3.1-pro` specs, so no review gate's choice of seat changed.

| File | Change |
|---|---|
| `assemblyzero/core/config.py` | `AGY_GEMINI_REVIEW_MODELS` (Argon) and `AGY_GEMINI_FLASH_MODELS` (3.8 Flash); `AGY_GEMINI_MODELS` is their union. `REVIEWER_MODEL` defaults to `gemini-4-argon-high`. |
| `assemblyzero/core/llm_provider.py` | Legacy Pro aliases resolve to `gemini-4-argon-high`, and `3.1-pro-low` to `gemini-4-argon-low`. New aliases `4-argon`, `4-argon-{high,medium,low}`, `3.8-flash-{high,medium,low}`. The "Flash is forbidden for governance" comment is removed; nothing traced it to the operator. |
| `assemblyzero/core/preflight.py` | The probe's default model is `gemini-4-argon-high`. |
| `assemblyzero/workflows/testing/adversarial_gemini.py` | `verify_model_is_pro` accepts the Argon ids, which do not contain "pro". The adversarial seat's own refusal of Flash is unchanged. |
| `assemblyzero/core/gemini_client.py` | A comment that named `gemini-3.1-pro-high` as the model now says the model is Gemini. |
| `tools/model_scorecard.py` | Prices the six catalog ids at zero (subscription). |
| `tests/fixtures/agy_models.txt` | The `agy models` output, as read. |

## #4189: runbook 0935

#3663 retired Auto Review; pr-sentinel posts `issue-reference` and approves as Cerberus in the same webhook request (`sentinel/src/webhook.js`, `sentinel/src/cerberus.js`). The runbook still described Auto Review as the approver.

| Section | Change |
|---|---|
| Purpose | The approval window is described as pr-sentinel's single request. |
| Step 3 | A rejected reference leaves the PR `blocked` and the driver at `poll_timeout`, with no Auto Review in the chain. |
| Step 4 | Rewritten: how pr-sentinel approves, the events it runs on, and that a failed approval goes only to the Worker's log. Auto Review is described as retired, and its `skipped` run as normal. |
| Step 6 | No close-and-reopen. pr-sentinel already runs on `edited`. |
| "No Review At All" (new) | The symptom row, how to read it, the one step that works (rerun the driver once), and what to report if that fails. It does not guess the cause. |
| Banned table | A body edit replaces close-and-reopen as the no-commit trigger; close-and-reopen gets its own row. |
| Decision tree | Close-and-reopen removed from every branch; a branch for the new symptom. |

Version 1.3, 2026-10-21.

## Not addressed here

- Two latency tests in `tests/unit/test_cascade_detector.py` failed once under the full suite and passed alone and in the next full run. That is tracked in #4190.
