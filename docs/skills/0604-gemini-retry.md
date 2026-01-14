# 0604 - Skill: Gemini Retry with Exponential Backoff

**Status:** Implemented
**Created:** 2026-01-14
**Related Issues:** #11

---

## Overview

This skill implements automatic retry with exponential backoff for Gemini CLI invocations. When `gemini-3-pro-preview` returns 429 (MODEL_CAPACITY_EXHAUSTED) errors, the system retries automatically until capacity frees up.

**Key Features:**
- Exponential backoff with jitter (avoids thundering herd)
- Distinguishes capacity vs quota errors
- Works unattended (while user sleeps/exercises)
- Full JSONL logging for debugging

---

## Problem Solved

Google's Gemini servers frequently return 429 errors with `MODEL_CAPACITY_EXHAUSTED` even when user quota is available. This happens during peak usage hours when server capacity is limited.

Before this skill:
```
gemini -p "Review this" --model gemini-3-pro-preview
# ERROR: 429 - No capacity available
# User must manually retry later
```

After this skill:
```
python tools/gemini-retry.py --prompt "Review this" --model gemini-3-pro-preview
# [GEMINI-RETRY] Attempt 1/20...
# [GEMINI-RETRY] Server capacity exhausted. Retrying in 30s...
# [GEMINI-RETRY] Attempt 2/20...
# [GEMINI-RETRY] Success on attempt 2 (model: gemini-3-pro-preview)
# <actual response>
```

---

## Error Classification

| Error Type | Retryable | Strategy |
|------------|-----------|----------|
| `MODEL_CAPACITY_EXHAUSTED` | Yes | Exponential backoff |
| `RESOURCE_EXHAUSTED` | Yes | Exponential backoff |
| `rateLimitExceeded` (per-minute) | Yes | Wait 60s fixed |
| `QUOTA_EXHAUSTED` (daily) | No | Fail immediately |

---

## Backoff Algorithm

```
Initial delay: 30 seconds (configurable)
Max delay: 10 minutes (600 seconds)
Multiplier: 2x
Jitter: ±20%
Max retries: 20 (configurable)
```

**Retry Sequence (approximate):**
```
Attempt 1: immediate
Attempt 2: wait ~30s
Attempt 3: wait ~60s
Attempt 4: wait ~120s
Attempt 5: wait ~240s
Attempt 6: wait ~480s
Attempt 7+: wait ~600s (capped)
```

With 20 retries and 600s max delay, the script can retry for approximately 3 hours before giving up.

---

## Usage

### Command Line

```bash
# Simple prompt
python tools/gemini-retry.py --prompt "Review this code" --model gemini-3-pro-preview

# From file
python tools/gemini-retry.py --prompt-file /path/to/prompt.txt --model gemini-3-pro-preview

# With custom retry settings
GEMINI_RETRY_MAX=10 GEMINI_RETRY_BASE_DELAY=10 \
  python tools/gemini-retry.py --prompt "Hello" --model gemini-3-pro-preview
```

### Via gemini-model-check.sh

The `gemini-model-check.sh` script automatically uses `gemini-retry.py` if available:

```bash
./tools/gemini-model-check.sh "Review this LLD" gemini-3-pro-preview
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_RETRY_MAX` | 20 | Maximum retry attempts |
| `GEMINI_RETRY_BASE_DELAY` | 30 | Initial delay in seconds |
| `GEMINI_RETRY_MAX_DELAY` | 600 | Maximum delay cap in seconds |
| `GEMINI_RETRY_LOG_DIR` | `logs/` | Directory for JSONL logs |
| `GEMINI_RETRY_DEBUG` | (unset) | Enable debug output |

---

## Logging

All retry attempts are logged to `logs/gemini-retry-TIMESTAMP.jsonl`:

```jsonl
{"ts":"2026-01-14T07:30:00Z","event":"START","model":"gemini-3-pro-preview","max_retries":20}
{"ts":"2026-01-14T07:30:00Z","event":"ATTEMPT","attempt":1,"model":"gemini-3-pro-preview"}
{"ts":"2026-01-14T07:30:03Z","event":"ERROR","attempt":1,"error_type":"capacity","retryable":true}
{"ts":"2026-01-14T07:30:03Z","event":"RETRY_SCHEDULED","attempt":2,"delay_s":30.5}
{"ts":"2026-01-14T07:30:33Z","event":"ATTEMPT","attempt":2,"model":"gemini-3-pro-preview"}
{"ts":"2026-01-14T07:30:36Z","event":"SUCCESS","attempt":2,"model_used":"gemini-3-pro-preview"}
```

---

## Known Limitations

### Agentic Mode for Complex Prompts

When using complex prompts with `--output-format json`, Gemini CLI may enter agentic mode and return plain text instead of JSON. The script handles this gracefully by accepting plain text responses when exit code is 0.

### Model Validation

When Gemini returns plain text (agentic mode), we cannot validate which model was used. The `model_used` field will be `None` in these cases.

---

## Files

| File | Purpose |
|------|---------|
| `tools/gemini-retry.py` | Core retry logic with backoff |
| `.claude/tools/gemini-model-check.sh` | Shell wrapper (uses retry.py if available) |
| `logs/gemini-retry-*.jsonl` | Retry event logs |

---

## Testing

```bash
# Test with fast delays
GEMINI_RETRY_DEBUG=1 GEMINI_RETRY_MAX=3 GEMINI_RETRY_BASE_DELAY=5 \
  python tools/gemini-retry.py --prompt "Hello" --model gemini-3-pro-preview

# Monitor logs in real-time
tail -f logs/gemini-retry-*.jsonl
```

---

## Troubleshooting

### "Max retries exceeded"

The server capacity didn't free up within the retry window. Options:
1. Increase `GEMINI_RETRY_MAX` for longer retry window
2. Try again later when traffic is lower
3. Check Google Cloud status for outages

### "Daily quota exhausted"

User hit daily quota limit. Wait for quota reset (typically midnight PT).

### "Unknown error"

Check `logs/gemini-retry-*.jsonl` for raw error output. May need to add new error pattern to `classify_error()`.

---

## References

- Issue #11: Implementation tracking
- `docs/skills/0601-gemini-dual-review.md`: Gemini review workflow
- `docs/skills/0602-gemini-lld-review.md`: LLD review procedure
