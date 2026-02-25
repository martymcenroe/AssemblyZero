# Test Plan Review Prompt

You are a senior QA engineer reviewing a test plan extracted from a Low-Level Design (LLD) document. Your goal is to ensure the test plan provides adequate coverage and uses real, executable tests.

## Pre-Flight Check

Before reviewing, verify these fundamentals:
- [ ] Test plan section exists and is not empty
- [ ] At least one test scenario is defined
- [ ] Test scenarios have names and descriptions

If any pre-flight check fails, immediately return BLOCKED with the specific issue.

## Review Criteria

### 1. Coverage Analysis (CRITICAL - 100% threshold per ADR 0207)

Calculate coverage by mapping test scenarios to requirements:

```
Coverage = (Requirements with tests / Total requirements) * 100
```

For each requirement, identify:
- Which test(s) cover it
- If no test covers it, flag as a gap

**BLOCKING if:** Coverage < 95%

### 2. Test Reality Check (CRITICAL)

Every test MUST be an executable automated test. Flag any test that:
- Delegates to "manual verification" or "human review"
- Says "verify by inspection" or "visual check"
- Has no clear assertions or expected outcomes
- Is vague like "test that it works"

**BLOCKING if:** Any test is not executable

### 3. No Human Delegation

Tests must NOT require human intervention. Flag any test that:
- Requires someone to "observe" behavior
- Needs "judgment" to determine pass/fail
- Says "ask the user" or "get feedback"

**BLOCKING if:** Any test delegates to humans

### 4. Test Type Appropriateness

Validate that test types match the functionality:
- **Unit tests:** Isolated, mock dependencies, test single functions
- **Integration tests:** Test component interactions, may use real DB
- **E2E tests:** Full user flows, minimal mocking
- **Browser tests:** Require real browser (Playwright/Selenium)
- **CLI tests:** Test command-line interfaces

**WARNING (not blocking) if:** Test types seem mismatched

### 5. Edge Cases

Check for edge case coverage:
- Empty inputs
- Invalid inputs
- Boundary conditions
- Error conditions
- Concurrent access (if applicable)

**WARNING (not blocking) if:** Edge cases seem missing

## Output Format

Provide your verdict in this exact format:

```markdown
## Pre-Flight Gate

- [x] PASSED / [ ] FAILED: Test plan exists
- [x] PASSED / [ ] FAILED: Scenarios defined
- [x] PASSED / [ ] FAILED: Scenarios have names

## Coverage Analysis

| Requirement | Test(s) | Status |
|-------------|---------|--------|
| REQ-1       | test_x  | Covered |
| REQ-2       | -       | GAP |

**Coverage: X/Y requirements (Z%)**

## Test Reality Check

| Test | Issue | Status |
|------|-------|--------|
| test_x | None | OK |
| test_y | "Manual check" | FAIL |

## Human Delegation Check

- [ ] PASSED: No human delegation found
- [ ] FAILED: [list tests that delegate to humans]

## Test Type Review

| Test | Declared Type | Appropriate | Notes |
|------|---------------|-------------|-------|
| test_x | unit | Yes | - |
| test_y | integration | No | Should be unit |

## Edge Cases

- [ ] Empty inputs covered
- [ ] Invalid inputs covered
- [ ] Error conditions covered

## Verdict

[x] **APPROVED** - Test plan is ready for implementation

OR

[x] **BLOCKED** - Test plan needs revision

## Required Changes (if BLOCKED)

1. [Specific, actionable change needed]
2. [Specific, actionable change needed]
```

## Important Notes

- Be strict on coverage (95% threshold)
- Be strict on test reality (no manual tests)
- Provide specific, actionable feedback
- Reference specific tests and requirements by name


---

# Test Plan for Issue #333

## Requirements to Cover

- REQ-T010: load_config()
- REQ-T020: load_config()
- REQ-T030: validate_config()
- REQ-T040: validate_config()
- REQ-T050: parse_repo_string()
- REQ-T060: _filter_issues_only()
- REQ-T070: fetch_repo_contents()
- REQ-T080: fetch_issues()
- REQ-T090: collect_issue_metrics()
- REQ-T100: collect_issue_metrics()
- REQ-T110: collect_workflow_metrics()
- REQ-T120: collect_workflow_metrics()
- REQ-T130: collect_gemini_metrics()
- REQ-T140: collect_gemini_metrics()
- REQ-T150: aggregate()
- REQ-T160: aggregate()
- REQ-T170: main()
- REQ-T180: main()
- REQ-T190: main()
- REQ-T200: write_metrics_output()
- REQ-T210: write_metrics_output()
- REQ-T220: format_summary_table()
- REQ-T230: get_rate_limit_remaining()
- REQ-T240: _get_cache_key()
- REQ-T250: _is_cache_valid()
- REQ-T260: _is_cache_valid()
- REQ-T270: parse_args()
- REQ-T280: main()
- REQ-T290: main()
- REQ-T300: write_metrics_output()
- REQ-T310: _resolve_token()
- REQ-T320: _resolve_token()
- REQ-T330: fetch_issues()
- REQ-T340: fetch_issues()

## Detected Test Types

- browser
- e2e
- integration
- mobile
- performance
- security
- terminal
- unit

## Required Tools

- appium
- bandit
- click.testing
- detox
- docker-compose
- locust
- pexpect
- playwright
- pytest
- pytest-benchmark
- safety
- selenium

## Mock Guidance

**Browser/UI Tests:** Real browser required, mock backend APIs for isolation
**End-to-End Tests:** Minimal mocking - test against real (sandboxed) systems
**Integration Tests:** Use test doubles for external services, real DB where possible
**Mobile App Tests:** Use emulators/simulators, mock backend services
**Performance Tests:** Test against representative data volumes
**Security Tests:** Never use real credentials, test edge cases thoroughly
**Terminal/CLI Tests:** Use CliRunner or capture stdout/stderr
**Unit Tests:** Mock external dependencies (APIs, DB, filesystem)

## Coverage Target

95%

## Test Scenarios

### test_id
- **Type:** unit
- **Requirement:** 
- **Description:** Tests Function | File | Input Summary | Expected Output
- **Mock needed:** False
- **Assertions:** 

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** `load_config()` | `test_metrics_config.py` | Explicit path to fixture | Valid config with 3 repos
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `load_config()` | `test_metrics_config.py` | Env var path | Config from env var
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_config()` | `test_metrics_config.py` | `{"repos": []}` | `ValueError`
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_config()` | `test_metrics_config.py` | `{"repos": ["invalid"]}` | `ValueError`
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_repo_string()` | `test_metrics_config.py` | `"martymcenroe/AssemblyZero"` | Correct `TrackedRepoConfig`
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `_filter_issues_only()` | `test_github_metrics_client.py` | 5 items (3 issues, 2 PRs) | 3 items
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `fetch_repo_contents()` | `test_github_metrics_client.py` | Mock 404 | `[]`
- **Mock needed:** True
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `fetch_issues()` | `test_github_metrics_client.py` | Mock 429 then 200 | Success after retry
- **Mock needed:** True
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `collect_issue_metrics()` | `test_metrics_aggregator.py` | 3 mock issues | Correct counts, avg=18.0
- **Mock needed:** True
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `collect_issue_metrics()` | `test_metrics_aggregator.py` | Empty list | All zeros, None avg
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `collect_workflow_metrics()` | `test_metrics_aggregator.py` | Issues with workflow labels | Label counts match
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `collect_workflow_metrics()` | `test_metrics_aggregator.py` | Mock content listing | lld_count=4, report_count=2
- **Mock needed:** True
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `collect_gemini_metrics()` | `test_metrics_aggregator.py` | Mock verdict files | approvals=3, blocks=2, rate=0.6
- **Mock needed:** True
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `collect_gemini_metrics()` | `test_metrics_aggregator.py` | Empty contents | All zeros, None rate
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** `aggregate()` | `test_metrics_aggregator.py` | 2 PerRepoMetrics | Correct summed totals
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** `aggregate()` | `test_metrics_aggregator.py` | 1 success, 1 failed | Failed listed, totals from success
- **Mock needed:** False
- **Assertions:** 

### test_t170
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | `test_collect_cross_project_metrics.py` | `dry_run=True` | Exit code 0, config printed
- **Mock needed:** False
- **Assertions:** 

### test_t180
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | `test_collect_cross_project_metrics.py` | 1 success, 1 exception | Exit code 1
- **Mock needed:** False
- **Assertions:** 

### test_t190
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | `test_collect_cross_project_metrics.py` | All exceptions | Exit code 2
- **Mock needed:** False
- **Assertions:** 

### test_t200
- **Type:** unit
- **Requirement:** 
- **Description:** `write_metrics_output()` | `test_collect_cross_project_metrics.py` | Valid metrics, tmp_path | Date-stamped file
- **Mock needed:** False
- **Assertions:** 

### test_t210
- **Type:** unit
- **Requirement:** 
- **Description:** `write_metrics_output()` | `test_collect_cross_project_metrics.py` | Valid metrics | `latest.json` exists
- **Mock needed:** False
- **Assertions:** 

### test_t220
- **Type:** unit
- **Requirement:** 
- **Description:** `format_summary_table()` | `test_collect_cross_project_metrics.py` | Table with repos + TOTALS
- **Mock needed:** False
- **Assertions:** 

### test_t230
- **Type:** unit
- **Requirement:** 
- **Description:** `get_rate_limit_remaining()` | `test_github_metrics_client.py` | Mock remaining=50 | `{"remaining": 50}`
- **Mock needed:** True
- **Assertions:** 

### test_t240
- **Type:** unit
- **Requirement:** 
- **Description:** `_get_cache_key()` | `test_github_metrics_client.py` | Same params twice | Equal keys
- **Mock needed:** False
- **Assertions:** 

### test_t250
- **Type:** unit
- **Requirement:** 
- **Description:** `_is_cache_valid()` | `test_github_metrics_client.py` | Fresh cache entry | `True`
- **Mock needed:** False
- **Assertions:** 

### test_t260
- **Type:** unit
- **Requirement:** 
- **Description:** `_is_cache_valid()` | `test_github_metrics_client.py` | Expired entry | `False`
- **Mock needed:** False
- **Assertions:** 

### test_t270
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_args()` | `test_collect_cross_project_metrics.py` | All flags | Correct namespace
- **Mock needed:** False
- **Assertions:** 

### test_t280
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | `test_collect_cross_project_metrics.py` | `verbose=True` | DEBUG logs emitted
- **Mock needed:** False
- **Assertions:** 

### test_t290
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | `test_collect_cross_project_metrics.py` | `lookback_days=7` | Config overridden
- **Mock needed:** False
- **Assertions:** 

### test_t300
- **Type:** unit
- **Requirement:** 
- **Description:** `write_metrics_output()` | `test_collect_cross_project_metrics.py` | Custom output_path | File at custom path
- **Mock needed:** False
- **Assertions:** 

### test_t310
- **Type:** unit
- **Requirement:** 
- **Description:** `_resolve_token()` | `test_github_metrics_client.py` | GITHUB_TOKEN env set | Token from env
- **Mock needed:** False
- **Assertions:** 

### test_t320
- **Type:** unit
- **Requirement:** 
- **Description:** `_resolve_token()` | `test_github_metrics_client.py` | GH_TOKEN fallback | Token from GH_TOKEN
- **Mock needed:** False
- **Assertions:** 

### test_t330
- **Type:** unit
- **Requirement:** 
- **Description:** `fetch_issues()` | `test_github_metrics_client.py` | Mock authenticated client | Issues returned
- **Mock needed:** True
- **Assertions:** 

### test_t340
- **Type:** unit
- **Requirement:** 
- **Description:** `fetch_issues()` | `test_github_metrics_client.py` | Mock 404 on private repo | `UnknownObjectException`
- **Mock needed:** True
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | File | Input Summary | Expected Output |
|---------|---------------|------|---------------|-----------------|
| T010 | `load_config()` | `test_metrics_config.py` | Explicit path to fixture | Valid config with 3 repos |
| T020 | `load_config()` | `test_metrics_config.py` | Env var path | Config from env var |
| T030 | `validate_config()` | `test_metrics_config.py` | `{"repos": []}` | `ValueError` |
| T040 | `validate_config()` | `test_metrics_config.py` | `{"repos": ["invalid"]}` | `ValueError` |
| T050 | `parse_repo_string()` | `test_metrics_config.py` | `"martymcenroe/AssemblyZero"` | Correct `TrackedRepoConfig` |
| T060 | `_filter_issues_only()` | `test_github_metrics_client.py` | 5 items (3 issues, 2 PRs) | 3 items |
| T070 | `fetch_repo_contents()` | `test_github_metrics_client.py` | Mock 404 | `[]` |
| T080 | `fetch_issues()` | `test_github_metrics_client.py` | Mock 429 then 200 | Success after retry |
| T090 | `collect_issue_metrics()` | `test_metrics_aggregator.py` | 3 mock issues | Correct counts, avg=18.0 |
| T100 | `collect_issue_metrics()` | `test_metrics_aggregator.py` | Empty list | All zeros, None avg |
| T110 | `collect_workflow_metrics()` | `test_metrics_aggregator.py` | Issues with workflow labels | Label counts match |
| T120 | `collect_workflow_metrics()` | `test_metrics_aggregator.py` | Mock content listing | lld_count=4, report_count=2 |
| T130 | `collect_gemini_metrics()` | `test_metrics_aggregator.py` | Mock verdict files | approvals=3, blocks=2, rate=0.6 |
| T140 | `collect_gemini_metrics()` | `test_metrics_aggregator.py` | Empty contents | All zeros, None rate |
| T150 | `aggregate()` | `test_metrics_aggregator.py` | 2 PerRepoMetrics | Correct summed totals |
| T160 | `aggregate()` | `test_metrics_aggregator.py` | 1 success, 1 failed | Failed listed, totals from success |
| T170 | `main()` | `test_collect_cross_project_metrics.py` | `dry_run=True` | Exit code 0, config printed |
| T180 | `main()` | `test_collect_cross_project_metrics.py` | 1 success, 1 exception | Exit code 1 |
| T190 | `main()` | `test_collect_cross_project_metrics.py` | All exceptions | Exit code 2 |
| T200 | `write_metrics_output()` | `test_collect_cross_project_metrics.py` | Valid metrics, tmp_path | Date-stamped file |
| T210 | `write_metrics_output()` | `test_collect_cross_project_metrics.py` | Valid metrics | `latest.json` exists |
| T220 | `format_summary_table()` | `test_collect_cross_project_metrics.py` | 2-repo metrics | Table with repos + TOTALS |
| T230 | `get_rate_limit_remaining()` | `test_github_metrics_client.py` | Mock remaining=50 | `{"remaining": 50}` |
| T240 | `_get_cache_key()` | `test_github_metrics_client.py` | Same params twice | Equal keys |
| T250 | `_is_cache_valid()` | `test_github_metrics_client.py` | Fresh cache entry | `True` |
| T260 | `_is_cache_valid()` | `test_github_metrics_client.py` | Expired entry | `False` |
| T270 | `parse_args()` | `test_collect_cross_project_metrics.py` | All flags | Correct namespace |
| T280 | `main()` | `test_collect_cross_project_metrics.py` | `verbose=True` | DEBUG logs emitted |
| T290 | `main()` | `test_collect_cross_project_metrics.py` | `lookback_days=7` | Config overridden |
| T300 | `write_metrics_output()` | `test_collect_cross_project_metrics.py` | Custom output_path | File at custom path |
| T310 | `_resolve_token()` | `test_github_metrics_client.py` | GITHUB_TOKEN env set | Token from env |
| T320 | `_resolve_token()` | `test_github_metrics_client.py` | GH_TOKEN fallback | Token from GH_TOKEN |
| T330 | `fetch_issues()` | `test_github_metrics_client.py` | Mock authenticated client | Issues returned |
| T340 | `fetch_issues()` | `test_github_metrics_client.py` | Mock 404 on private repo | `UnknownObjectException` |
