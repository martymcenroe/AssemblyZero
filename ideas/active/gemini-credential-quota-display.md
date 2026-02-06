# Brief: Gemini Credential Quota & Usage Display

## Problem

The current `gemini-test-credentials.py` script only tests whether credentials work. It doesn't show:
- Current quota usage (requests made today)
- Rate limits (requests per minute/day)
- Time until quota resets
- Available capacity
- Account tier (free/paid)

When managing multiple API keys for rotation, operators need visibility into quota health to:
1. Know which keys are near exhaustion before they fail
2. Plan when to add more keys
3. Debug rotation failures ("why did all keys fail?")

## Proposed Enhancement

Extend `gemini-test-credentials.py` to query and display quota/usage metadata from the Gemini API.

### New Output Format

```
============================================================
GEMINI CREDENTIAL TEST
Testing with model: gemini-2.0-flash
============================================================

Testing: oauth-primary [oauth] [ENABLED]
--------------------------------------------------
  PASS OK - Response: Hello to you.
  Quota: 1,432 / 1,500 requests today (95%)
  Rate Limit: 15 RPM, 1,500 RPD
  Resets: 2026-02-03 00:00 UTC (in 5h 23m)
  Tier: Free

Testing: api-key-1 (account@example.com) [api_key] [ENABLED]
--------------------------------------------------
  PASS OK - Response: Hello to you.
  Quota: 89 / 1,500 requests today (6%)
  Rate Limit: 15 RPM, 1,500 RPD
  Resets: 2026-02-03 00:00 UTC (in 5h 23m)
  Tier: Free

============================================================
SUMMARY
============================================================
Total credentials: 3
Working: 3
Working + Enabled: 3

QUOTA HEALTH:
  oauth-primary:  [##########] 95% - NEAR LIMIT
  api-key-1:      [#         ]  6% - healthy
  api-key-2:      [###       ] 28% - healthy

Next reset: 2026-02-03 00:00 UTC (in 5h 23m)
```

## Research Needed

1. **What quota info does `google.genai` SDK expose?**
   - Check `response` metadata after API calls
   - Look for `usage_metadata`, `quota_remaining`, headers
   - Check if there's a dedicated quota/limits endpoint

2. **What does Google Cloud Console API expose?**
   - Cloud Monitoring API for quota metrics
   - May require additional API enablement
   - May have latency (not real-time)

3. **What do the error messages contain?**
   - 429 errors often include `Retry-After` header
   - May include quota reset time in error body
   - Parse existing rotation state file for reset times

## Implementation Options

### Option A: Parse Response Metadata (Low effort)
- Check if `google.genai` responses include usage metadata
- Parse any headers or metadata returned
- Pros: No additional API calls
- Cons: May not expose quota limits

### Option B: Dedicated Quota Endpoint (Medium effort)
- Use Google Cloud APIs to query quota
- `cloudquotas.googleapis.com` or similar
- Pros: Accurate, real-time
- Cons: Requires additional API enablement, may not work for free-tier keys

### Option C: Track Usage Locally (Low effort)
- Count requests in `gemini-api.jsonl`
- Estimate based on known limits
- Pros: Works without API changes
- Cons: Only tracks our usage, not total account usage

### Option D: Hybrid Approach (Recommended)
- Parse reset times from rotation state file (already tracked)
- Count local usage from API log
- Display whatever metadata the SDK exposes
- Gracefully degrade if info not available

## Acceptance Criteria

1. Shows quota usage percentage for each credential
2. Shows time until quota resets
3. Shows rate limit info (RPM/RPD) if available
4. Visual indicator for credentials near limit (>80%)
5. Summary section with quota health overview
6. Graceful handling when quota info unavailable

## Files to Modify

| File | Change |
|------|--------|
| `tools/gemini-test-credentials.py` | Add quota display logic |
| `docs/runbooks/0905-gemini-credentials.md` | Update example output |

## Dependencies

- May require `google-cloud-quotas` package for full quota API access
- Current `google-genai` package may expose some metadata

## Related

- Issue #53 migrated to new `google.genai` SDK
- `~/.assemblyzero/gemini-rotation-state.json` tracks exhaustion times
- `~/.assemblyzero/gemini-api.jsonl` tracks all API events

## Next Steps

1. Research what `google.genai` SDK exposes in response metadata
2. Check Google Cloud Quotas API availability for free-tier keys
3. Prototype Option D (hybrid approach)
4. Create issue if pursuing this enhancement
