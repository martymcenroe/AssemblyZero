# feat: cache eviction policy

Synthetic fixture for the exact row-join mode (#2219). Every decision table
carries a leading ID column, and every row criterion opens with its ID, so the
checker can verify a bijection rather than a count.

## Requirements

- The cache shall evict entries in least-recently-used order.
- WHEN the cache exceeds its size limit the cache shall evict until it fits.
- WHILE a write to an entry is in flight the cache shall not evict that entry.
- IF an entry is pinned THEN the cache shall skip it during eviction.
- WHERE metrics are enabled the cache shall count every eviction.

Eviction depends on two independent conditions.

| ID | Entry pinned? | Cache over limit? | Entry after the sweep |
|---|---|---|---|
| E1 | no | no | retained |
| E2 | no | yes | evicted |
| E3 | yes | no | retained |
| E4 | yes | yes | retained, and the skip is counted |

## Acceptance Criteria

- [ ] Cache size is read from the configured limit at startup
- [ ] E1. Not pinned, not over limit: the entry is retained
- [ ] E2. Not pinned, over limit: the entry is evicted
- [ ] E3. Pinned, not over limit: the entry is retained
- [ ] E4. Pinned, over limit: the entry is retained, and the skip is counted
