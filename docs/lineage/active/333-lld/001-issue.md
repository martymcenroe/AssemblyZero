---
repo: martymcenroe/AssemblyZero
issue: 333
url: https://github.com/martymcenroe/AssemblyZero/issues/333
fetched: 2026-02-26T04:12:22.356127Z
---

# Issue #333: feat: Cross-project metrics aggregation for AssemblyZero usage tracking

## Problem

AssemblyZero is used by multiple repositories (AssemblyZero itself, RCA-PDF, potentially dispatch). Currently, we only track metrics for the AssemblyZero repo. We need visibility into how AssemblyZero workflows are being used across all projects.

## Requirements

### Functional Requirements
- [ ] Aggregate issue velocity (opened/closed) across configured repos
- [ ] Track which workflows are used per repo (requirements, implementation, TDD)
- [ ] Track Gemini review outcomes per repo
- [ ] Generate combined metrics dashboard

### Non-Functional Requirements
- [ ] Minimal API calls (cache/batch where possible)
- [ ] Support for private repos (authenticated)
- [ ] Configurable repo list

## Proposed Solution

1. **Config file**: `~/.assemblyzero/tracked_repos.json`
   ```json
   {
     "repos": [
       "martymcenroe/AssemblyZero",
       "martymcenroe/RCA-PDF",
       "martymcenroe/dispatch"
     ]
   }
   ```

2. **Metrics collector**: `tools/collect-cross-project-metrics.py`
   - Fetches issue data from all configured repos
   - Aggregates into unified metrics
   - Outputs to `docs/metrics/cross-project-{date}.json`

3. **Wiki integration**: Update Metrics page with cross-project data

## Data Points to Track

| Metric | Description |
|--------|-------------|
| Issues created | Total across all repos |
| Issues closed | Total across all repos |
| LLDs generated | Count of lineage folders |
| Gemini reviews | Count of verdict files |
| Workflows run | By workflow type |

## Related

- Wiki: [Metrics](https://github.com/martymcenroe/AssemblyZero/wiki/Metrics)
- The RCA-PDF project uses AssemblyZero for its governance workflow