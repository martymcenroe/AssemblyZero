# Brief: Gemini Credential Quota Display

**Status:** Active
**Created:** 2026-02-02
**Updated:** 2026-02-28
**Effort:** Low
**Priority:** Low
**Tracking Issue:** None

---

## Problem

The credential pool has 4 credentials (1 OAuth + 3 API keys). When a workflow fails with a quota error, diagnosing which credential is exhausted and when it resets requires manual API calls or guesswork. The rotation system tracks exhaustion events but doesn't expose quota health in a human-readable way.

## What Already Exists

- **`tools/gemini-test-credentials-v2.py`** — tests credentials using the `google.genai` SDK. Validates that each credential can make a successful API call. This is the right foundation to enhance.
- **`tools/gemini-rotate.py`** — automatic credential rotation. Tracks quota exhaustion in `~/.assemblyzero/gemini-rotation-state.json`. Has a `--status` subcommand showing current rotation state.
- **`~/.assemblyzero/gemini-credentials.json`** — credential configuration file (4 credentials).
- **`~/.assemblyzero/gemini-rotation-state.json`** — rotation state including exhaustion timestamps and capacity tracking.

## The Gap

- `gemini-test-credentials-v2.py` tests if credentials *work* but not how much quota *remains*
- `gemini-rotate.py --status` shows rotation state (which credential is active, which are exhausted) but not quota numbers
- No single command answers: "How much quota do I have left across all credentials, and when do exhausted ones reset?"

## Proposed Solution

Enhance `gemini-test-credentials-v2.py` to add a `--status` mode that combines:

1. **Credential health** — existing test (can it make an API call?)
2. **Rotation state** — read from `gemini-rotation-state.json` (which are exhausted, when did exhaustion occur)
3. **Quota estimate** — based on exhaustion timestamps and known reset windows (Gemini free tier resets daily at midnight PT)

### Output Example

```
Credential Status (2026-02-28 14:30 UTC)
─────────────────────────────────────────
  oauth-main     OK healthy    last exhausted: never
  apikey-1       OK healthy    last exhausted: 2026-02-27 08:15
  apikey-2       XX exhausted  since: 2026-02-28 13:45 (resets ~midnight PT)
  apikey-3       OK healthy    last exhausted: 2026-02-28 02:00
─────────────────────────────────────────
  Pool: 3/4 available
```

### Retirement of v1

After enhancing v2, retire `gemini-test-credentials.py` (v1) — it uses the older SDK and duplicates functionality.

## Integration Points

- **`gemini-rotate.py`** — reads the same rotation state file; no changes needed to rotation logic
- **Watch** (`city-watch-regression-guardian.md`) — future: credential health could be a pre-flight check before starting expensive workflows

## Acceptance Criteria

- [ ] `--status` mode displays health and exhaustion state for all credentials
- [ ] Reads rotation state from `gemini-rotation-state.json` (no extra API calls for exhausted credentials)
- [ ] Shows estimated reset time for exhausted credentials
- [ ] Pool summary (N/M available)
- [ ] v1 script (`gemini-test-credentials.py`) removed after v2 enhancement

## Dependencies & Cross-References

- **`gemini-rotate.py`** — rotation state file is the data source
- **`gemini-test-credentials-v2.py`** — the file being enhanced
