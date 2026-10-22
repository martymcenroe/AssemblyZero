# Test Report: adversarial review runs on 3.8 Flash (#4192)

## Tests in `tests/unit/test_adversarial_gemini.py`

- `test_the_default_seat_runs_on_flash` (T1): `resolve_adversarial_model()` under the default profile returns `gemini-3.8-flash-high`. It replaces `test_the_default_seat_is_refused_while_agy_offers_no_pro`, which #4178 added to assert the refusal.
- `test_allowed_flash_passes[...]` (T2): `verify_model_is_pro` returns `True` for `gemini-3.8-flash-high` and `gemini-3.8-flash-low`.
- `test_the_request_and_reply_checks_agree`: the id the request check returns passes the reply check.
- `test_argon_is_refused_before_any_request[...]` and `test_a_forbidden_reply_is_refused[...]` (T3): both ends refuse `gemini-4-argon-high`. The reply check also refuses a retired id on the list, `gemini-3-pro-preview-0514`; `test_pro_preview_variant` now uses `gemini-3.1-pro-preview-0514`, which is not on it.
- `test_the_default_provider_comes_from_get_provider_with_the_gemini_spec` and `test_the_spec_sent_is_the_alias_that_was_checked` (T4) are back to their form before #4178: the client builds with the real model check, no stub.

The Flash replies in the older tests (`gemini-2.0-flash-001`, `gemini-2.0-flash-exp`) are still refused, now because `FORBIDDEN_MODELS` lists `gemini-2.0-flash`.

`test_adversarial_gemini.py`, `test_adversarial_node.py`, `test_adversarial_review_halts.py` and `test_agy_catalog.py` together: 136 passed.

## Live call

On 2026-10-21 just before 6:55 PM Central, `AdversarialGeminiClient()` on the default seat made one call through agy with a one-word prompt. The probe refused to run unless the seat resolved to 3.8 Flash.

```
requested gemini-3.8-flash-high | reply model gemini-3.8-flash-high | reply check True | 'Blue'
```

## Full local suite (WSL)

```
poetry run pytest tests/unit -q
2 failed, 11195 passed, 66 skipped, 7 deselected, 6 xfailed
```

The two failures are `test_cascade_detector.py::TestDetectionLatency::test_typical_input_latency` and `test_max_input_latency`, the wall-clock timing tests tracked in #4190. This branch does not touch the cascade detector. Run alone straight after, they failed again; the machine's one-minute load average was 17.5 at 7:05 PM Central. On unchanged `main`, under the same load, `test_max_input_latency` failed too.
