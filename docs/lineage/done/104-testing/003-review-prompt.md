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

# Test Plan for Issue #104

## Requirements to Cover

- REQ-1: CLI scans verdicts from all repos listed in project-registry.json
- REQ-2: CLI accepts --root or --registry to locate project-registry.json
- REQ-3: Verdicts are stored in SQLite with deduplication via content hash
- REQ-4: Blocking issues are extracted and categorized by tier (1/2/3)
- REQ-5: Pattern frequency statistics are available via --stats
- REQ-6: Recommendations map to specific template sections in 0102
- REQ-7: --recommend shows preview without modification (dry-run default)
- REQ-8: --auto applies changes with .bak backup created first
- REQ-9: Database location is `.agentos/verdicts.db` within project root (git-ignored, worktree-scoped)
- REQ-10: Tool handles missing repos gracefully (warn, continue)
- REQ-11: All file writes are atomic (tmp file + rename)
- REQ-12: Verbose logging (-v/-vv) enables debugging of parsing errors
- REQ-13: Path traversal attacks are prevented via resolve() + is_relative_to() validation on both verdict paths AND template paths
- REQ-14: Symlink loops cannot cause infinite recursion (follow_symlinks=False)
- REQ-15: Parser version tracking enables re-parsing when parser logic improves
- REQ-C: **Simplicity:** Similar components collapsed (per 0006 §8.1)
- REQ-C: **No touching:** All elements have visual separation (per 0006 §8.2)
- REQ-C: **No hidden lines:** All arrows fully visible (per 0006 §8.3)
- REQ-C: **Readable:** Labels not truncated, flow direction clear
- REQ-C: **Auto-inspected:** Agent rendered via mermaid.ink and viewed (per 0006 §8.5)
- REQ-C: Implementation complete and linted
- REQ-C: Code comments reference this LLD
- REQ-C: All modules created per 2.1 Files Changed
- REQ-C: Logging configuration supports -v/-vv verbosity levels
- REQ-C: Path validation uses `Path.resolve()` and `is_relative_to()` for traversal prevention on both verdict paths and template paths
- REQ-C: Scanner uses `follow_symlinks=False` to prevent infinite recursion
- REQ-C: PARSER_VERSION constant defined and stored in database
- REQ-C: All SQL queries use parameterized queries exclusively (no string interpolation)
- REQ-C: Database stored in project-local `.agentos/` directory
- REQ-C: All test scenarios pass
- REQ-C: Test coverage meets threshold (>80%)
- REQ-C: Integration test with real verdicts passes
- REQ-C: tests/conftest.py handles temporary database creation/teardown
- REQ-C: LLD updated with any deviations
- REQ-C: Implementation Report (0103) completed
- REQ-C: CLI help text is comprehensive (--help)
- REQ-C: Code review completed
- REQ-C: Gemini governance review passed
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
- **Description:** Parse LLD verdict | Auto | Sample LLD verdict markdown | VerdictRecord with correct fields | All fields populated, type='lld'
- **Mock needed:** False
- **Assertions:** 

### test_020
- **Type:** unit
- **Requirement:** 
- **Description:** Parse Issue verdict | Auto | Sample Issue verdict markdown | VerdictRecord with correct fields | All fields populated, type='issue'
- **Mock needed:** False
- **Assertions:** 

### test_030
- **Type:** unit
- **Requirement:** 
- **Description:** Extract blocking issues | Auto | Verdict with Tier 1/2/3 issues | List of BlockingIssue | Correct tier, category, description
- **Mock needed:** False
- **Assertions:** 

### test_040
- **Type:** unit
- **Requirement:** 
- **Description:** Content hash change detection | Auto | Same file, modified file | needs_update=False, True | Correct boolean return
- **Mock needed:** False
- **Assertions:** 

### test_050
- **Type:** unit
- **Requirement:** 
- **Description:** Pattern normalization | Auto | Various descriptions | Normalized patterns | Consistent output for similar inputs
- **Mock needed:** False
- **Assertions:** 

### test_060
- **Type:** unit
- **Requirement:** 
- **Description:** Category mapping | Auto | All categories | Correct template sections | Matches CATEGORY_TO_SECTION
- **Mock needed:** False
- **Assertions:** 

### test_070
- **Type:** unit
- **Requirement:** 
- **Description:** Template section parsing | Auto | 0102 template | Dict of 11 sections | All sections extracted
- **Mock needed:** False
- **Assertions:** 

### test_080
- **Type:** unit
- **Requirement:** 
- **Description:** Recommendation generation | Auto | Pattern stats with high counts | Recommendations list | Type, section, content populated
- **Mock needed:** False
- **Assertions:** 

### test_090
- **Type:** unit
- **Requirement:** 
- **Description:** Atomic write with backup | Auto | Template path + content | .bak created, content written | Both files exist, content correct
- **Mock needed:** False
- **Assertions:** 

### test_100
- **Type:** unit
- **Requirement:** 
- **Description:** Multi-repo discovery | Auto | Mock project-registry.json | List of repo paths | All repos found
- **Mock needed:** True
- **Assertions:** 

### test_110
- **Type:** unit
- **Requirement:** 
- **Description:** Missing repo handling | Auto | Registry with nonexistent repo | Warning logged, continue | No crash, other repos scanned
- **Mock needed:** False
- **Assertions:** 

### test_120
- **Type:** unit
- **Requirement:** 
- **Description:** Database migration | Auto | Old schema DB | Updated schema | New columns exist
- **Mock needed:** True
- **Assertions:** 

### test_130
- **Type:** unit
- **Requirement:** 
- **Description:** Dry-run mode (default) | Auto | Preview only, no file changes | Template unchanged
- **Mock needed:** False
- **Assertions:** 

### test_140
- **Type:** unit
- **Requirement:** 
- **Description:** Stats output formatting | Auto | Database with verdicts | Formatted statistics | Readable output
- **Mock needed:** True
- **Assertions:** 

### test_150
- **Type:** unit
- **Requirement:** 
- **Description:** Auto | Registry found at /path/to/dir/project-registry.json | Correct path resolution
- **Mock needed:** False
- **Assertions:** 

### test_160
- **Type:** unit
- **Requirement:** 
- **Description:** Auto | Registry found at explicit path
- **Mock needed:** False
- **Assertions:** 

### test_170
- **Type:** unit
- **Requirement:** 
- **Description:** Auto | DB with existing verdicts | All verdicts re-parsed | Hash check bypassed
- **Mock needed:** False
- **Assertions:** 

### test_180
- **Type:** unit
- **Requirement:** 
- **Description:** Verbose logging (-v) | Auto | Filename logged at DEBUG | Parsing error includes filename
- **Mock needed:** False
- **Assertions:** 

### test_190
- **Type:** unit
- **Requirement:** 
- **Description:** Path traversal prevention (verdict) | Auto | Verdict path with ../../../etc/passwd | Path rejected, error logged | is_relative_to() check fails
- **Mock needed:** False
- **Assertions:** 

### test_195
- **Type:** unit
- **Requirement:** 
- **Description:** Path traversal prevention (template) | Auto | Path rejected, error logged | validate_template_path() fails
- **Mock needed:** False
- **Assertions:** 

### test_200
- **Type:** unit
- **Requirement:** 
- **Description:** Parser version upgrade re-parse | Auto | DB with old parser_version | Verdict re-parsed despite unchanged content | needs_update returns True when parser_version outdated
- **Mock needed:** False
- **Assertions:** 

### test_210
- **Type:** unit
- **Requirement:** 
- **Description:** Symlink loop handling | Auto | Directory with recursive symlink | Scanner completes without hanging | No infinite recursion, warning logged
- **Mock needed:** False
- **Assertions:** 

### test_220
- **Type:** unit
- **Requirement:** 
- **Description:** Database directory creation | Auto | .agentos/ does not exist | Directory created, DB initialized | No error, DB file exists
- **Mock needed:** True
- **Assertions:** 

## Original Test Plan Section

*Ref: [0005-testing-strategy-and-protocols.md](0005-testing-strategy-and-protocols.md)*

**Testing Philosophy:** Strive for 100% automated test coverage. Manual tests are a last resort for scenarios that genuinely cannot be automated (e.g., visual inspection, hardware interaction). Every scenario marked "Manual" requires justification.

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Parse LLD verdict | Auto | Sample LLD verdict markdown | VerdictRecord with correct fields | All fields populated, type='lld' |
| 020 | Parse Issue verdict | Auto | Sample Issue verdict markdown | VerdictRecord with correct fields | All fields populated, type='issue' |
| 030 | Extract blocking issues | Auto | Verdict with Tier 1/2/3 issues | List of BlockingIssue | Correct tier, category, description |
| 040 | Content hash change detection | Auto | Same file, modified file | needs_update=False, True | Correct boolean return |
| 050 | Pattern normalization | Auto | Various descriptions | Normalized patterns | Consistent output for similar inputs |
| 060 | Category mapping | Auto | All categories | Correct template sections | Matches CATEGORY_TO_SECTION |
| 070 | Template section parsing | Auto | 0102 template | Dict of 11 sections | All sections extracted |
| 080 | Recommendation generation | Auto | Pattern stats with high counts | Recommendations list | Type, section, content populated |
| 090 | Atomic write with backup | Auto | Template path + content | .bak created, content written | Both files exist, content correct |
| 100 | Multi-repo discovery | Auto | Mock project-registry.json | List of repo paths | All repos found |
| 110 | Missing repo handling | Auto | Registry with nonexistent repo | Warning logged, continue | No crash, other repos scanned |
| 120 | Database migration | Auto | Old schema DB | Updated schema | New columns exist |
| 130 | Dry-run mode (default) | Auto | --recommend without --auto | Preview only, no file changes | Template unchanged |
| 140 | Stats output formatting | Auto | Database with verdicts | Formatted statistics | Readable output |
| 150 | --root argument resolution | Auto | --root /path/to/dir | Registry found at /path/to/dir/project-registry.json | Correct path resolution |
| 160 | --registry argument override | Auto | --registry /custom/path.json | Registry found at explicit path | --registry overrides --root |
| 170 | --force-rescan flag | Auto | DB with existing verdicts | All verdicts re-parsed | Hash check bypassed |
| 180 | Verbose logging (-v) | Auto | --scan -v with unparseable file | Filename logged at DEBUG | Parsing error includes filename |
| 190 | Path traversal prevention (verdict) | Auto | Verdict path with ../../../etc/passwd | Path rejected, error logged | is_relative_to() check fails |
| 195 | Path traversal prevention (template) | Auto | --template ../../../etc/hosts | Path rejected, error logged | validate_template_path() fails |
| 200 | Parser version upgrade re-parse | Auto | DB with old parser_version | Verdict re-parsed despite unchanged content | needs_update returns True when parser_version outdated |
| 210 | Symlink loop handling | Auto | Directory with recursive symlink | Scanner completes without hanging | No infinite recursion, warning logged |
| 220 | Database directory creation | Auto | .agentos/ does not exist | Directory created, DB initialized | No error, DB file exists |

*Note: Use 3-digit IDs with gaps of 10 (010, 020, 030...) to allow insertions.*

**Type values:**
- `Auto` - Fully automated, runs in CI (pytest, playwright, etc.)
- `Auto-Live` - Automated but hits real external services (may be slow/flaky)
- `Manual` - Requires human execution (MUST include justification why automation is impossible)

### 10.2 Test Commands

```bash
# Run all automated tests
poetry run pytest tests/test_verdict_analyzer.py -v

# Run only fast/mocked tests (exclude live)
poetry run pytest tests/test_verdict_analyzer.py -v -m "not live"

# Run live integration tests (actual repo scanning)
poetry run pytest tests/test_verdict_analyzer.py -v -m live
```

### 10.3 Manual Tests (Only If Unavoidable)

**N/A - All scenarios automated.**

*Full test results recorded in Implementation Report (0103) or Test Report (0113).*
