# 0905 - Runbook: Gemini Credentials (retired)

**Retired.** This runbook managed a pool of Gemini API keys: a credentials file, a rotation wrapper and a test script. All of that went with the move to the subscription (#1595, #1605), and the tools are deleted. There are no Gemini credentials to add, test, disable or rotate.

## What replaced it

The pipeline calls Gemini through the Antigravity CLI (`agy`), signed in to the subscription. `assemblyzero/core/gemini_client.py` is that transport, and ADR 0220 and ADR 0237 record the decisions.

Which model a role uses is set in `config/fleet-models.toml`. Runbook 0958 says how to change it.

## When a Gemini call fails

| Failure | What happens | What to do |
|---------|--------------|------------|
| Capacity (503, 529) | `GeminiClient` retries with backoff, within the call's time budget | Wait; if the run halts, rerun it later |
| Quota exhausted | The call fails and the run halts with a recovery plan | Wait for the subscription's limit to reset |
| Sign-in | The call fails and the run halts with a recovery plan | Check that `agy` is signed in to the subscription |

## History

| Date | Change |
|------|--------|
| 2026-01-20 | Initial runbook created |
| 2026-01-31 | Added API event log documentation |
| 2026-11-01 | Retired: the API-key rotation it described no longer exists (#4477) |
