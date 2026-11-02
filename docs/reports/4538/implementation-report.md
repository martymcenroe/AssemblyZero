# Implementation report: #4538

The transport failed any agy call whose answer mentioned `--agent`. `_agy_once` passed `stderr` and agy's whole stdout to `agent_warning`, and since #4199 that stdout is the one-line JSON envelope `{"conversation_id", "status", "response", "usage"}`, so the model's answer sat on the same line as everything agy wrote. The model-call ledger holds three calls failed this way, all changelog reviews: 2026-10-27 (162,709 input tokens), 2026-10-28 (111,770, `status SUCCESS`) and 2026-11-02 (122,965).

## What changed

- `assemblyzero/core/gemini_client.py`: new `agy_diagnostics(stderr, stdout_text, reply)` returns what agy itself wrote: stderr always; stdout only when it is not the JSON envelope; from the envelope, every field but `response`, as one JSON line. `_agy_once` hands that to `agent_warning` in place of both whole streams. `agent_warning` is unchanged.

## What did not change

A warning from agy still fails the call, on stderr, on plain-text stdout, or in any envelope field other than `response`. An unknown agent name was already caught another way: agy's headless run exits 1 with `unknown agent %q (available: %s)` (string from its binary), which the exit-status check fails.

No live agy call was made. The fixtures follow the envelopes the three failed calls left in the ledger, and the warning is agy's own string from its binary: `warning: ignoring --agent %q because we are resuming an existing conversation`.
