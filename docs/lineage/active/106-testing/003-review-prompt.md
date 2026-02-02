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

# Test Plan for Issue #106

## Requirements to Cover

- REQ-1: `--parallel N` flag enables concurrent execution with N workers (default 3, max 10)
- REQ-2: Each workflow subprocess uses an isolated checkpoint database
- REQ-3: Issue numbers are sanitized to prevent path traversal attacks
- REQ-4: Console output is prefixed with workflow identifier, no partial line interleaving
- REQ-5: Credential exhaustion (all keys reserved) pauses all workflows gracefully
- REQ-6: HTTP 429 rate limits trigger per-key backoff without crashing workflows
- REQ-7: Ctrl+C triggers graceful shutdown with checkpoint persistence within 5 seconds
- REQ-8: Failed workflows do not affect other parallel workflows
- REQ-9: `--dry-run` flag lists pending items without executing
- REQ-10: Summary report displays status of all workflows at completion
- REQ-11: Per-workflow log files are created in `~/.agentos/logs/parallel/{timestamp}/`
- REQ-12: Performance: 6 items with `--parallel 3` completes in <50% of sequential time
- REQ-C: Should rate-limited keys be automatically retried after backoff, or should manual intervention be required?
- REQ-C: What is the maximum acceptable coordination overhead percentage for parallel execution?
- REQ-C: **Simplicity:** Similar components collapsed (per 0006 §8.1)
- REQ-C: **No touching:** All elements have visual separation (per 0006 §8.2)
- REQ-C: **No hidden lines:** All arrows fully visible (per 0006 §8.3)
- REQ-C: **Readable:** Labels not truncated, flow direction clear
- REQ-C: **Auto-inspected:** Agent rendered via mermaid.ink and viewed (per 0006 §8.5)
- REQ-C: Budget alerts: Not applicable (local execution)
- REQ-C: Rate limiting: Handled by CredentialCoordinator
- REQ-C: Fallback: Sequential execution if --parallel 1 or no credentials
- REQ-C: No PII stored without consent - N/A
- REQ-C: All third-party licenses compatible with project license - No new deps
- REQ-C: External API usage compliant with provider ToS - Unchanged pattern
- REQ-C: Data retention policy documented - Checkpoint cleanup defined
- REQ-C: `parallel_coordinator.py` implemented with full worker lifecycle management
- REQ-C: `credential_coordinator.py` implemented with reservation and rate-limit tracking
- REQ-C: `output_prefixer.py` implemented with line-buffered prefix injection
- REQ-C: `input_sanitizer.py` implemented with path traversal prevention
- REQ-C: `lld_workflow.py` updated with `--parallel` and `--dry-run` flags
- REQ-C: `issue_workflow.py` updated with `--parallel` and `--dry-run` flags
- REQ-C: `checkpoint_manager.py` updated to support `AGENTOS_WORKFLOW_DB` env var
- REQ-C: Code comments reference this LLD (#106)
- REQ-C: All 11 test scenarios pass
- REQ-C: Mock LLM provider fixtures created and working
- REQ-C: Integration test with 3+ mock workflows in parallel
- REQ-C: Rate-limit backoff behavior verified
- REQ-C: Test coverage ≥ 90% for new modules
- REQ-C: LLD updated with any deviations
- REQ-C: Implementation Report (0103) completed
- REQ-C: Test Report (0113) completed
- REQ-C: Wiki pages for lld-workflow and issue-workflow updated
- REQ-C: README.md updated with parallel execution examples
- REQ-C: ADR created for parallel execution architecture
- REQ-C: New files added to `docs/0003-file-inventory.md`
- REQ-C: Run 0809 Security Audit - PASS
- REQ-C: Run 0817 Wiki Alignment Audit - PASS
- REQ-C: Code review completed
- REQ-C: User approval before closing issue

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

### test_010
- **Type:** unit
- **Requirement:** 
- **Description:** Happy path: 3 LLDs processed in parallel | Auto | 3 mock LLDs, --parallel 3 | All complete, progress report shows 3/3 | Exit code 0, all DBs cleaned up
- **Mock needed:** True
- **Assertions:** 

### test_020
- **Type:** unit
- **Requirement:** 
- **Description:** Dry run lists without executing | Auto | 5 pending items, --dry-run | List of 5 items printed | No subprocess spawned, no DBs created
- **Mock needed:** False
- **Assertions:** 

### test_030
- **Type:** unit
- **Requirement:** 
- **Description:** Path traversal rejected | Auto | Issue number "../etc/passwd" | ValueError raised | Clear error message, no file access
- **Mock needed:** False
- **Assertions:** 

### test_040
- **Type:** unit
- **Requirement:** 
- **Description:** Credential exhaustion pauses workers | Auto | 5 items, 2 credentials, --parallel 5 | Workers pause, resume on release | Log shows "[COORDINATOR] Credential pool exhausted"
- **Mock needed:** False
- **Assertions:** 

### test_050
- **Type:** unit
- **Requirement:** 
- **Description:** HTTP 429 triggers backoff | Auto | AGENTOS_SIMULATE_429=true | Key marked rate-limited | Backoff applied, different key used or wait
- **Mock needed:** False
- **Assertions:** 

### test_060
- **Type:** unit
- **Requirement:** 
- **Description:** Single workflow failure isolated | Auto | 1 invalid spec among 3 | 2 succeed, 1 fails | Failed item in report, others complete
- **Mock needed:** False
- **Assertions:** 

### test_070
- **Type:** unit
- **Requirement:** 
- **Description:** Graceful shutdown on SIGINT | Auto | SIGINT during execution | Workers checkpoint and exit | All checkpoint DBs written within 5s
- **Mock needed:** False
- **Assertions:** 

### test_080
- **Type:** unit
- **Requirement:** 
- **Description:** Output prefix prevents interleaving | Auto | 3 parallel workflows | All lines prefixed correctly | No partial line mixing
- **Mock needed:** False
- **Assertions:** 

### test_090
- **Type:** unit
- **Requirement:** 
- **Description:** Performance benchmark | Auto-Live | 6 items, sequential vs --parallel 3 | Parallel < 50% sequential time | Timing comparison logged
- **Mock needed:** False
- **Assertions:** 

### test_100
- **Type:** unit
- **Requirement:** 
- **Description:** Max parallelism enforced | Auto | Capped to 10 | Warning logged, runs with 10
- **Mock needed:** False
- **Assertions:** 

### test_110
- **Type:** unit
- **Requirement:** 
- **Description:** Default parallelism applied | Auto | Uses 3 | Config shows max_parallelism=3
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

*Ref: [0005-testing-strategy-and-protocols.md](0005-testing-strategy-and-protocols.md)*

**Testing Philosophy:** Strive for 100% automated test coverage. Manual tests are a last resort for scenarios that genuinely cannot be automated (e.g., visual inspection, hardware interaction). Every scenario marked "Manual" requires justification.

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Happy path: 3 LLDs processed in parallel | Auto | 3 mock LLDs, --parallel 3 | All complete, progress report shows 3/3 | Exit code 0, all DBs cleaned up |
| 020 | Dry run lists without executing | Auto | 5 pending items, --dry-run | List of 5 items printed | No subprocess spawned, no DBs created |
| 030 | Path traversal rejected | Auto | Issue number "../etc/passwd" | ValueError raised | Clear error message, no file access |
| 040 | Credential exhaustion pauses workers | Auto | 5 items, 2 credentials, --parallel 5 | Workers pause, resume on release | Log shows "[COORDINATOR] Credential pool exhausted" |
| 050 | HTTP 429 triggers backoff | Auto | AGENTOS_SIMULATE_429=true | Key marked rate-limited | Backoff applied, different key used or wait |
| 060 | Single workflow failure isolated | Auto | 1 invalid spec among 3 | 2 succeed, 1 fails | Failed item in report, others complete |
| 070 | Graceful shutdown on SIGINT | Auto | SIGINT during execution | Workers checkpoint and exit | All checkpoint DBs written within 5s |
| 080 | Output prefix prevents interleaving | Auto | 3 parallel workflows | All lines prefixed correctly | No partial line mixing |
| 090 | Performance benchmark | Auto-Live | 6 items, sequential vs --parallel 3 | Parallel < 50% sequential time | Timing comparison logged |
| 100 | Max parallelism enforced | Auto | --parallel 15 | Capped to 10 | Warning logged, runs with 10 |
| 110 | Default parallelism applied | Auto | --parallel without N | Uses 3 | Config shows max_parallelism=3 |

*Note: Use 3-digit IDs with gaps of 10 (010, 020, 030...) to allow insertions.*

### 10.2 Test Commands

```bash
# Run all automated tests
poetry run pytest tests/test_parallel_coordinator.py tests/test_credential_coordinator.py -v

# Run only fast/mocked tests (exclude live)
poetry run pytest tests/ -v -m "not live" -k "parallel or credential"

# Run live integration tests (requires credentials)
poetry run pytest tests/ -v -m live -k "parallel"

# Run performance benchmark
poetry run pytest tests/test_parallel_coordinator.py -v -k "benchmark" --benchmark-only
```

### 10.3 Manual Tests (Only If Unavoidable)

**N/A - All scenarios automated.**
