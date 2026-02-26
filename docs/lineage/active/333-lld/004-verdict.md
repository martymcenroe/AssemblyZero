# LLD Review: 333 - Feature: Cross-Project Metrics Aggregation for AssemblyZero Usage Tracking

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
**PASSED**

The LLD contains all required structural elements:
- Issue Link: #333
- Context/Scope Section: Present
- Proposed Changes: Present

## Review Summary
This LLD is exceptionally well-structured and demonstrates a high degree of rigorous preparation. The architecture follows a clean separation of concerns (Collector -> Aggregator -> Formatter), and the caching strategy appropriately mitigates API cost/rate-limit risks. The Test Plan is comprehensive, achieving 100% coverage of requirements with specific, falsifiable scenarios. The mechanical validation performed prior to review has effectively ensured path correctness and dependency alignment.

## Open Questions Resolved
- [x] ~~Should the wiki page update be automated via PyGithub's wiki API, or should the tool output markdown that the user pastes manually?~~ **RESOLVED: Output Markdown files only.** Automation introduces unnecessary auth complexity for v1. Manual copy-paste or a separate CI step is sufficient.
- [x] ~~What is the desired retention period for historical cross-project metric snapshots?~~ **RESOLVED: Indefinite (Git-based).** JSON snapshots are small; keeping them in the repo (`docs/metrics/`) allows for historical trend analysis via git history without extra infrastructure.
- [x] ~~Should per-repo metrics be broken out in the combined output, or only aggregated totals?~~ **RESOLVED: Include per-repo breakdown.** Aggregates hide outliers. The `AggregatedMetrics` model in Section 2.3 already correctly includes `per_repo: list[RepoMetrics]`.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Load/validate tracked repos config | T010, T020, T030, T040, T050, T250 | ✓ Covered |
| 2 | Count issues (created, closed, open) in period | T060, T240, T300 | ✓ Covered |
| 3 | Detect workflow types (labels/heuristics) | T070, T310 | ✓ Covered |
| 4 | Count lineage artifacts (LLDs) | T080, T110 | ✓ Covered |
| 5 | Count Gemini review verdicts | T090 | ✓ Covered |
| 6 | Aggregate per-repo metrics | T120, T130, T140, T150 | ✓ Covered |
| 7 | Output JSON and Markdown | T210, T220, T230 | ✓ Covered |
| 8 | Cache API responses with TTL | T160, T170, T180, T190, T200 | ✓ Covered |
| 9 | Private repo support via token | T260, T270 | ✓ Covered |
| 10 | Graceful handling of unreachable repos | T100, T280, T290 | ✓ Covered |

**Coverage Calculation:** 10 requirements covered / 10 total = **100%**

**Verdict:** **PASS**

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation.

### Cost
- No issues found. API usage is bounded by the config list size and mitigated by the caching layer (REQ-8).

### Safety
- No issues found. The tool is read-only regarding GitHub data. File operations are scoped to the report output directory and the user's home directory for configuration/caching (standard CLI behavior).

### Security
- No issues found. Auth tokens are handled via environment variables (REQ-9) and not logged. Input validation for repo names prevents injection attacks (T250).

### Legal
- No issues found. No PII is collected; only aggregate counts.

## Tier 2: HIGH PRIORITY Issues
No high-priority issues found.

### Architecture
- **Path Structure:** Validated. The project uses a root-level package structure (`assemblyzero/`), and the LLD correctly adds `assemblyzero/metrics/`.
- **Design:** The ETL-style pipeline (Collector -> Aggregator -> Formatter) is appropriate for this reporting task.

### Observability
- **Logging:** Implicit in the CLI design (`--verbose` flag mentioned in Section 2.4). Ensure `logging` is configured to print to stderr so it doesn't corrupt stdout JSON output if piped.

### Quality
- **Test Plan:** Excellent. Scenarios are specific and cover edge cases (e.g., zero reviews, missing directories, expired cache).

## Tier 3: SUGGESTIONS
- **Logging Output:** Ensure that when running `tools/collect-cross-project-metrics.py`, logging messages go to `stderr` while the JSON output (if requested via stdout) goes to `stdout`. This allows piping the result to `jq` or other tools cleanly.
- **Cache Permission:** When creating `~/.assemblyzero/metrics_cache.json`, explicitly set file permissions to `0600` (read/write by owner only) since it may contain indirect info about private repos (though strictly speaking, it only contains counts).

## Questions for Orchestrator
1. None.

## Verdict
[x] **APPROVED** - Ready for implementation
[ ] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision