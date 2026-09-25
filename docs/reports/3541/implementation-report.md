# Implementation Report — The transport preflight probes with a Gemini model, not the Claude default (#3541)

Backfilled 2026-09-25 after the merge, from PR #3542 (merge `a39e29b2`) and its body (#3559). No report was written at the time; nothing was re-run for the backfill, and every claim below is the PR's own.

Parent: #3502. A regression from #3506 (PR #3540), shipped the same day.

## What was wrong

`preflight.check_gemini_transport()` built `GeminiClient()` with no model. The client's default is `config.REVIEWER_MODEL`, `claude-opus-4-6`, and the constructor rejects it: `ValueError: Model 'claude-opus-4-6' is not a valid Gemini model`. The check reports every exception as a failed transport, so from `2963678b` any run with a Gemini node halted at N1 or at the spec drafter with `[PREFLIGHT] Gemini unavailable: transport: the probe call raised ValueError`. It was live for about 50 minutes; no run was started in that window.

## What changed

- `preflight_for_specs` probes with the model the run is configured to use: `gemini_model_for(*specs)` maps the first `gemini:<name>` spec through `GeminiProvider.MODEL_MAP`, the same mapping `get_provider` uses.
- `check_gemini_transport(client=None, model=DEFAULT_PROBE_MODEL)` builds `GeminiClient(model=model)`; `DEFAULT_PROBE_MODEL` is `gemini-3.1-pro-high`, never `REVIEWER_MODEL`.

## Files

`assemblyzero/core/preflight.py`, `tests/unit/test_preflight_transport.py`.
