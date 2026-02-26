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
- REQ-T030: load_config()
- REQ-T040: load_config()
- REQ-T050: get_default_config_path()
- REQ-T060: count_issues_in_period()
- REQ-T070: detect_workflows_used()
- REQ-T080: count_lineage_artifacts()
- REQ-T090: count_gemini_verdicts()
- REQ-T100: collect_repo_metrics()
- REQ-T110: count_lineage_artifacts()
- REQ-T120: aggregate_metrics()
- REQ-T130: aggregate_metrics()
- REQ-T140: aggregate_metrics()
- REQ-T150: compute_approval_rate()
- REQ-T170: load_cached_metrics()
- REQ-T180: load_cached_metrics()
- REQ-T190: invalidate_cache()
- REQ-T200: invalidate_cache()
- REQ-T210: format_json_snapshot()
- REQ-T220: format_markdown_table()
- REQ-T230: write_snapshot()
- REQ-T250: validate_repo_name()
- REQ-T260: collect_repo_metrics()
- REQ-T270: collect_repo_metrics()
- REQ-T280: main()
- REQ-T290: main()
- REQ-T300: count_issues_in_period()
- REQ-T310: detect_workflows_used()

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
- **Description:** Tests Function | File | Input | Expected Output
- **Mock needed:** False
- **Assertions:** 

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** `load_config()` | `test_metrics_config.py` | `tracked_repos_valid.json` fixture | Config with 3 repos, `cache_ttl_minutes=60`
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `load_config()` | `test_metrics_config.py` | Non-existent path | `ConfigError` with path in message
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `load_config()` | `test_metrics_config.py` | `tracked_repos_malformed.json` fixture | `ConfigError("Failed to parse...")`
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `load_config()` | `test_metrics_config.py` | `tracked_repos_empty.json` fixture | `ConfigError("repos list cannot be empty")`
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `get_default_config_path()` | `test_metrics_config.py` | No args | Path ending in `.assemblyzero/tracked_repos.json`
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `count_issues_in_period()` | `test_metrics_collector.py` | Mock repo: 4 created, 2 closed, 2 open | `(4, 2, 2)`
- **Mock needed:** True
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_workflows_used()` | `test_metrics_collector.py` | Mock issues with `workflow:requirements` x2, `workflow:tdd` x2 | `{"requirements": 2, "tdd": 2}`
- **Mock needed:** True
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `count_lineage_artifacts()` | `test_metrics_collector.py` | Mock 2 active + 3 done dirs | `5`
- **Mock needed:** True
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `count_gemini_verdicts()` | `test_metrics_collector.py` | Mock 4 verdict files: 3 APPROVE, 1 BLOCK | `(4, 3, 1)`
- **Mock needed:** True
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `collect_repo_metrics()` | `test_metrics_collector.py` | Mock `UnknownObjectException` | `CollectionError` with repo name
- **Mock needed:** True
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `count_lineage_artifacts()` | `test_metrics_collector.py` | Mock 404 on both dirs | `0`
- **Mock needed:** True
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `aggregate_metrics()` | `test_metrics_aggregator.py` | 3 RepoMetrics | Sums: (87, 72, 25, 40, 35), rate=0.857
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `aggregate_metrics()` | `test_metrics_aggregator.py` | Empty list | All zeros, empty per_repo
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `aggregate_metrics()` | `test_metrics_aggregator.py` | 1 RepoMetrics | Identity with single repo
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** `compute_approval_rate()` | `test_metrics_aggregator.py` | `(0, 0)` | `0.0`
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** `save_cached_metrics()` + `load_cached_metrics()` | `test_metrics_cache.py` | Save then load within TTL | Identical metrics dict
- **Mock needed:** False
- **Assertions:** 

### test_t170
- **Type:** unit
- **Requirement:** 
- **Description:** `load_cached_metrics()` | `test_metrics_cache.py` | TTL=0, sleep 0.1s | `None`
- **Mock needed:** False
- **Assertions:** 

### test_t180
- **Type:** unit
- **Requirement:** 
- **Description:** `load_cached_metrics()` | `test_metrics_cache.py` | Corrupt JSON file | `None`
- **Mock needed:** False
- **Assertions:** 

### test_t190
- **Type:** unit
- **Requirement:** 
- **Description:** `invalidate_cache()` | `test_metrics_cache.py` | 3 cached, invalidate 1 | 2 remain, 1 is None
- **Mock needed:** False
- **Assertions:** 

### test_t200
- **Type:** unit
- **Requirement:** 
- **Description:** `invalidate_cache()` | `test_metrics_cache.py` | 3 cached, invalidate all (`None`) | All 3 return None
- **Mock needed:** False
- **Assertions:** 

### test_t210
- **Type:** unit
- **Requirement:** 
- **Description:** `format_json_snapshot()` | `test_metrics_formatters.py` | AggregatedMetrics fixture | Valid JSON with all required keys
- **Mock needed:** False
- **Assertions:** 

### test_t220
- **Type:** unit
- **Requirement:** 
- **Description:** `format_markdown_table()` | `test_metrics_formatters.py` | AggregatedMetrics fixture | Markdown with ` | Repo | ` table, repo names, `85.7%`
- **Mock needed:** False
- **Assertions:** 

### test_t230
- **Type:** unit
- **Requirement:** 
- **Description:** `write_snapshot()` | `test_metrics_formatters.py` | AggregatedMetrics + tmp_path | File at `cross-project-{date}.json` with valid JSON
- **Mock needed:** False
- **Assertions:** 

### test_t240
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_repo_metrics()` + `create_repo_metrics()` | `test_metrics_models.py` | `issues_created=-1` | `ValueError("issues_created must be non-negative, got -1")`
- **Mock needed:** False
- **Assertions:** 

### test_t250
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_repo_name()` | `test_metrics_config.py` | `"martymcenroe/AssemblyZero"` valid, `"'; DROP TABLE--"` invalid | `True` / `False`
- **Mock needed:** False
- **Assertions:** 

### test_t260
- **Type:** unit
- **Requirement:** 
- **Description:** `collect_repo_metrics()` | `test_metrics_collector.py` | Mock with token `"ghp_real_token"` | `Github("ghp_real_token")` called
- **Mock needed:** True
- **Assertions:** 

### test_t270
- **Type:** unit
- **Requirement:** 
- **Description:** `collect_repo_metrics()` | `test_metrics_collector.py` | Empty token `""` | `Github()` called without args
- **Mock needed:** False
- **Assertions:** 

### test_t280
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | `test_metrics_cli.py` | 3 repos config, 1 unreachable | Exit code `1`
- **Mock needed:** False
- **Assertions:** 

### test_t290
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | `test_metrics_cli.py` | 3 repos config, all unreachable | Exit code `2`
- **Mock needed:** False
- **Assertions:** 

### test_t300
- **Type:** unit
- **Requirement:** 
- **Description:** `count_issues_in_period()` | `test_metrics_collector.py` | Correct filtering: 1 created, 1 closed
- **Mock needed:** False
- **Assertions:** 

### test_t310
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_workflows_used()` | `test_metrics_collector.py` | No workflow labels, LLD filenames present | Dict populated via heuristic
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | File | Input | Expected Output |
|---------|---------------|------|-------|-----------------|
| T010 | `load_config()` | `test_metrics_config.py` | `tracked_repos_valid.json` fixture | Config with 3 repos, `cache_ttl_minutes=60` |
| T020 | `load_config()` | `test_metrics_config.py` | Non-existent path | `ConfigError` with path in message |
| T030 | `load_config()` | `test_metrics_config.py` | `tracked_repos_malformed.json` fixture | `ConfigError("Failed to parse...")` |
| T040 | `load_config()` | `test_metrics_config.py` | `tracked_repos_empty.json` fixture | `ConfigError("repos list cannot be empty")` |
| T050 | `get_default_config_path()` | `test_metrics_config.py` | No args | Path ending in `.assemblyzero/tracked_repos.json` |
| T060 | `count_issues_in_period()` | `test_metrics_collector.py` | Mock repo: 4 created, 2 closed, 2 open | `(4, 2, 2)` |
| T070 | `detect_workflows_used()` | `test_metrics_collector.py` | Mock issues with `workflow:requirements` x2, `workflow:tdd` x2 | `{"requirements": 2, "tdd": 2}` |
| T080 | `count_lineage_artifacts()` | `test_metrics_collector.py` | Mock 2 active + 3 done dirs | `5` |
| T090 | `count_gemini_verdicts()` | `test_metrics_collector.py` | Mock 4 verdict files: 3 APPROVE, 1 BLOCK | `(4, 3, 1)` |
| T100 | `collect_repo_metrics()` | `test_metrics_collector.py` | Mock `UnknownObjectException` | `CollectionError` with repo name |
| T110 | `count_lineage_artifacts()` | `test_metrics_collector.py` | Mock 404 on both dirs | `0` |
| T120 | `aggregate_metrics()` | `test_metrics_aggregator.py` | 3 RepoMetrics | Sums: (87, 72, 25, 40, 35), rate=0.857 |
| T130 | `aggregate_metrics()` | `test_metrics_aggregator.py` | Empty list | All zeros, empty per_repo |
| T140 | `aggregate_metrics()` | `test_metrics_aggregator.py` | 1 RepoMetrics | Identity with single repo |
| T150 | `compute_approval_rate()` | `test_metrics_aggregator.py` | `(0, 0)` | `0.0` |
| T160 | `save_cached_metrics()` + `load_cached_metrics()` | `test_metrics_cache.py` | Save then load within TTL | Identical metrics dict |
| T170 | `load_cached_metrics()` | `test_metrics_cache.py` | TTL=0, sleep 0.1s | `None` |
| T180 | `load_cached_metrics()` | `test_metrics_cache.py` | Corrupt JSON file | `None` |
| T190 | `invalidate_cache()` | `test_metrics_cache.py` | 3 cached, invalidate 1 | 2 remain, 1 is None |
| T200 | `invalidate_cache()` | `test_metrics_cache.py` | 3 cached, invalidate all (`None`) | All 3 return None |
| T210 | `format_json_snapshot()` | `test_metrics_formatters.py` | AggregatedMetrics fixture | Valid JSON with all required keys |
| T220 | `format_markdown_table()` | `test_metrics_formatters.py` | AggregatedMetrics fixture | Markdown with `| Repo |` table, repo names, `85.7%` |
| T230 | `write_snapshot()` | `test_metrics_formatters.py` | AggregatedMetrics + tmp_path | File at `cross-project-{date}.json` with valid JSON |
| T240 | `validate_repo_metrics()` + `create_repo_metrics()` | `test_metrics_models.py` | `issues_created=-1` | `ValueError("issues_created must be non-negative, got -1")` |
| T250 | `validate_repo_name()` | `test_metrics_config.py` | `"martymcenroe/AssemblyZero"` valid, `"'; DROP TABLE--"` invalid | `True` / `False` |
| T260 | `collect_repo_metrics()` | `test_metrics_collector.py` | Mock with token `"ghp_real_token"` | `Github("ghp_real_token")` called |
| T270 | `collect_repo_metrics()` | `test_metrics_collector.py` | Empty token `""` | `Github()` called without args |
| T280 | `main()` | `test_metrics_cli.py` | 3 repos config, 1 unreachable | Exit code `1` |
| T290 | `main()` | `test_metrics_cli.py` | 3 repos config, all unreachable | Exit code `2` |
| T300 | `count_issues_in_period()` | `test_metrics_collector.py` | 7-day period, 2 issues | Correct filtering: 1 created, 1 closed |
| T310 | `detect_workflows_used()` | `test_metrics_collector.py` | No workflow labels, LLD filenames present | Dict populated via heuristic |
