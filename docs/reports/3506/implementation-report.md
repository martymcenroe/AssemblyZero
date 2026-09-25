# Implementation Report — The Gemini preflight runs only when Gemini is configured, and checks agy (#3506)

Backfilled 2026-09-25 after the merge, from PR #3540 (merge `2963678b`) and its body (#3559). No report was written at the time; nothing was re-run for the backfill, and every claim below is the PR's own.

Parent: #3502.

## What was wrong

N1 (`requirements/nodes/generate_draft.py`) and the spec drafter (`implementation_spec/nodes/generate_spec.py`) both called `check_gemini_available()` unconditionally, and that reads `~/.assemblyzero/gemini-credentials.json`. A run launched with the then-standalone defaults, `--drafter claude:sonnet --reviewer claude:opus`, halted with `[PREFLIGHT] Gemini unavailable` on any machine without the file, although no Gemini call was going to happen. Where the file existed, the check said nothing about the transport: since ADR 0220 Gemini is reached through `agy`, and the file's presence does not show whether `agy` is installed, logged in, or answering.

## What changed

- `preflight.preflight_for_specs(*specs)` returns `None` unless some node's spec is `gemini:*`.
- When a node is Gemini, `preflight.check_gemini_transport()` checks that `GeminiClient._find_agy_cli()` resolves and that one minimal call through `GeminiClient.invoke` returns a non-empty answer, sent exactly as a review is sent. Each failure is reported as `transport: <which step>: <why>`. The probe runs once per process.
- The halt message head stays `[PREFLIGHT] Gemini unavailable`, the head the gate registry rows `lld.preflight` and `spec.preflight` emit.
- `tests/unit/conftest.py` stubs `check_gemini_transport` and resets the memo, so no unit test makes the real `agy` probe call.

This PR introduced #3541 (the probe built `GeminiClient()` with the Claude default model), fixed the same evening by PR #3542.

## Files

`assemblyzero/core/preflight.py`, `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py`, `assemblyzero/workflows/requirements/nodes/generate_draft.py`, `tests/unit/conftest.py`, `tests/unit/test_preflight_transport.py`.
