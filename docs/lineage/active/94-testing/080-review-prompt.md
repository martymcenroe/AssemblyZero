# Test Plan Review Prompt

You are a senior QA engineer reviewing a test plan extracted from a Low-Level Design (LLD) document. Your goal is to ensure the test plan provides adequate coverage and uses real, executable tests.

## Pre-Validated (Do NOT Re-Check)

**Issue #495:** The following have been confirmed by automated mechanical gates before this review. Do not re-check these — focus on semantic test quality instead.

- **Test plan section exists** with named scenarios: VERIFIED
- **Requirement coverage** ≥ 95%: VERIFIED
- **No vague assertions**: VERIFIED — no "verify it works" patterns detected
- **No human delegation**: VERIFIED — no "manual verification" keywords found

## Review Criteria

### 1. Test Type Appropriateness

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
## Test Type Review

| Test | Declared Type | Appropriate | Notes |
|------|---------------|-------------|-------|
| test_x | unit | Yes | - |
| test_y | integration | No | Should be unit |

## Edge Cases

- [ ] Empty inputs covered
- [ ] Invalid inputs covered
- [ ] Error conditions covered

## Semantic Issues

{Any issues found with test logic, mock strategy, or test design}

## Verdict

[x] **APPROVED** - Test plan is ready for implementation

OR

[x] **BLOCKED** - Test plan needs revision

## Required Changes (if BLOCKED)

1. [Specific, actionable change needed]
2. [Specific, actionable change needed]
```

## Important Notes

- Coverage, assertion quality, and human delegation are pre-validated — focus on semantic quality
- Provide specific, actionable feedback
- Reference specific tests and requirements by name


---

# Test Plan for Issue #94

## Requirements to Cover

- REQ-T010: build_initial_state()
- REQ-T020: probe_links()
- REQ-T030: probe_links()
- REQ-T040: probe_links()
- REQ-T050: probe_worktrees()
- REQ-T060: probe_worktrees()
- REQ-T070: probe_todo()
- REQ-T080: probe_todo()
- REQ-T090: probe_harvest()
- REQ-T100: run_probe_safe()
- REQ-T110: fix_broken_links()
- REQ-T120: fix_broken_links()
- REQ-T130: fix_stale_worktrees()
- REQ-T140: generate_commit_message()
- REQ-T150: LocalFileReporter.create_report()
- REQ-T160: LocalFileReporter.update_report()
- REQ-T170: LocalFileReporter.find_existing_report()
- REQ-T180: build_report_body()
- REQ-T190: route_after_sweep()
- REQ-T200: route_after_sweep()
- REQ-T210: route_after_sweep()
- REQ-T220: route_after_fix()
- REQ-T230: route_after_fix()
- REQ-T240: parse_args()
- REQ-T250: parse_args()
- REQ-T260: parse_args()
- REQ-T270: main()
- REQ-T280: main()
- REQ-T290: graph.invoke()
- REQ-T300: main()
- REQ-T310: graph.invoke()
- REQ-T320: graph.invoke()
- REQ-T330: graph.invoke()
- REQ-T340: main()
- REQ-T350: main()
- REQ-T360: GitHubReporter.__init__()
- REQ-T370: GitHubReporter.find_existing_report()
- REQ-T380: LocalFileReporter.create_report()

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

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** `build_initial_state()` | `parse_args(["--reporter", "local"])` | `JanitorState` with `scope=["links","worktrees","harvest","todo"]`, `reporter_type="local"`
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_links()` | mock repo with broken `./docs/old-guide.md` link | `ProbeResult(status="findings")` with `fixable=True` finding
- **Mock needed:** True
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_links()` | mock README with `https://example.com` only | `ProbeResult(status="ok")`, no findings
- **Mock needed:** True
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_links()` | mock repo with valid `./docs/guide.md` link | `ProbeResult(status="ok")`
- **Mock needed:** True
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_worktrees()` | mocked 15-day-old merged worktree | `ProbeResult(status="findings")` with `fixable=True`
- **Mock needed:** True
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_worktrees()` | mocked 1-day-old active worktree | `ProbeResult(status="ok")`
- **Mock needed:** True
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_todo()` | mocked TODO 45 days old | `ProbeResult(status="findings")` with `fixable=False`
- **Mock needed:** True
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_todo()` | mocked TODO added today | `ProbeResult(status="ok")`
- **Mock needed:** True
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_harvest()` | no harvest script in repo | `ProbeResult(status="findings")` with `harvest_missing` info
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `run_probe_safe()` | probe raises `RuntimeError` | `ProbeResult(status="error", error_message="RuntimeError: ...")`
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `fix_broken_links()` | finding + real file, `dry_run=False` | File updated, `FixAction(applied=True)`
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `fix_broken_links()` | finding + real file, `dry_run=True` | File unchanged, `FixAction(applied=False)`
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `fix_stale_worktrees()` | worktree finding, `dry_run=False` | `subprocess.run` called with `git worktree remove`
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `generate_commit_message()` | `"broken_link"`, `3` | `"chore: fix 3 broken markdown link(s) (ref #94)"`
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** `LocalFileReporter.create_report()` | title, body, severity | File created in `janitor-reports/`
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** `LocalFileReporter.update_report()` | existing path, new body | File overwritten
- **Mock needed:** False
- **Assertions:** 

### test_t170
- **Type:** unit
- **Requirement:** 
- **Description:** `LocalFileReporter.find_existing_report()` | report from today exists | Returns file path
- **Mock needed:** False
- **Assertions:** 

### test_t180
- **Type:** unit
- **Requirement:** 
- **Description:** `build_report_body()` | mixed findings + actions | Markdown with all sections
- **Mock needed:** False
- **Assertions:** 

### test_t190
- **Type:** unit
- **Requirement:** 
- **Description:** `route_after_sweep()` | `{"all_findings": []}` | `"__end__"`
- **Mock needed:** False
- **Assertions:** 

### test_t200
- **Type:** unit
- **Requirement:** 
- **Description:** `route_after_sweep()` | fixable finding + `auto_fix=True` | `"n1_fixer"`
- **Mock needed:** False
- **Assertions:** 

### test_t210
- **Type:** unit
- **Requirement:** 
- **Description:** `route_after_sweep()` | unfixable only | `"n2_reporter"`
- **Mock needed:** False
- **Assertions:** 

### test_t220
- **Type:** unit
- **Requirement:** 
- **Description:** `route_after_fix()` | `{"unfixable_findings": []}` | `"__end__"`
- **Mock needed:** False
- **Assertions:** 

### test_t230
- **Type:** unit
- **Requirement:** 
- **Description:** `route_after_fix()` | non-empty unfixable | `"n2_reporter"`
- **Mock needed:** False
- **Assertions:** 

### test_t240
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_args()` | `[]` | defaults: scope=all, auto_fix=True, etc.
- **Mock needed:** False
- **Assertions:** 

### test_t250
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_args()` | all flags | all values parsed correctly
- **Mock needed:** False
- **Assertions:** 

### test_t260
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_args()` | `["--scope", "invalid"]` | `SystemExit`
- **Mock needed:** False
- **Assertions:** 

### test_t270
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | mocked clean run | return `0`
- **Mock needed:** True
- **Assertions:** 

### test_t280
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | mocked unfixable findings | return `1`
- **Mock needed:** True
- **Assertions:** 

### test_t290
- **Type:** unit
- **Requirement:** 
- **Description:** `graph.invoke()` | integration with `LocalFileReporter` | report created, correct exit code
- **Mock needed:** False
- **Assertions:** 

### test_t300
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | mocked probes returning mixed | sweeper→fixer→reporter chain executes
- **Mock needed:** True
- **Assertions:** 

### test_t310
- **Type:** unit
- **Requirement:** 
- **Description:** `graph.invoke()` | `dry_run=True` with fixable | `FixAction(applied=False)`, file unchanged
- **Mock needed:** False
- **Assertions:** 

### test_t320
- **Type:** unit
- **Requirement:** 
- **Description:** `graph.invoke()` | broken link finding + real file | file updated, commit mocked
- **Mock needed:** True
- **Assertions:** 

### test_t330
- **Type:** unit
- **Requirement:** 
- **Description:** `graph.invoke()` | mixed findings | fix applied + report for unfixable
- **Mock needed:** False
- **Assertions:** 

### test_t340
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | `["--silent"]` + clean | no stdout
- **Mock needed:** False
- **Assertions:** 

### test_t350
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | not in git repo | return `2`
- **Mock needed:** False
- **Assertions:** 

### test_t360
- **Type:** unit
- **Requirement:** 
- **Description:** `GitHubReporter.__init__()` | `GITHUB_TOKEN` set, gh auth fails | reporter initializes successfully
- **Mock needed:** False
- **Assertions:** 

### test_t370
- **Type:** unit
- **Requirement:** 
- **Description:** `GitHubReporter.find_existing_report()` | existing issue found | returns URL, `update_report` would be called
- **Mock needed:** False
- **Assertions:** 

### test_t380
- **Type:** unit
- **Requirement:** 
- **Description:** `LocalFileReporter.create_report()` | standard inputs | file in `janitor-reports/`
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `build_initial_state()` | `parse_args(["--reporter", "local"])` | `JanitorState` with `scope=["links","worktrees","harvest","todo"]`, `reporter_type="local"` |
| T020 | `probe_links()` | mock repo with broken `./docs/old-guide.md` link | `ProbeResult(status="findings")` with `fixable=True` finding |
| T030 | `probe_links()` | mock README with `https://example.com` only | `ProbeResult(status="ok")`, no findings |
| T040 | `probe_links()` | mock repo with valid `./docs/guide.md` link | `ProbeResult(status="ok")` |
| T050 | `probe_worktrees()` | mocked 15-day-old merged worktree | `ProbeResult(status="findings")` with `fixable=True` |
| T060 | `probe_worktrees()` | mocked 1-day-old active worktree | `ProbeResult(status="ok")` |
| T070 | `probe_todo()` | mocked TODO 45 days old | `ProbeResult(status="findings")` with `fixable=False` |
| T080 | `probe_todo()` | mocked TODO added today | `ProbeResult(status="ok")` |
| T090 | `probe_harvest()` | no harvest script in repo | `ProbeResult(status="findings")` with `harvest_missing` info |
| T100 | `run_probe_safe()` | probe raises `RuntimeError` | `ProbeResult(status="error", error_message="RuntimeError: ...")` |
| T110 | `fix_broken_links()` | finding + real file, `dry_run=False` | File updated, `FixAction(applied=True)` |
| T120 | `fix_broken_links()` | finding + real file, `dry_run=True` | File unchanged, `FixAction(applied=False)` |
| T130 | `fix_stale_worktrees()` | worktree finding, `dry_run=False` | `subprocess.run` called with `git worktree remove` |
| T140 | `generate_commit_message()` | `"broken_link"`, `3` | `"chore: fix 3 broken markdown link(s) (ref #94)"` |
| T150 | `LocalFileReporter.create_report()` | title, body, severity | File created in `janitor-reports/` |
| T160 | `LocalFileReporter.update_report()` | existing path, new body | File overwritten |
| T170 | `LocalFileReporter.find_existing_report()` | report from today exists | Returns file path |
| T180 | `build_report_body()` | mixed findings + actions | Markdown with all sections |
| T190 | `route_after_sweep()` | `{"all_findings": []}` | `"__end__"` |
| T200 | `route_after_sweep()` | fixable finding + `auto_fix=True` | `"n1_fixer"` |
| T210 | `route_after_sweep()` | unfixable only | `"n2_reporter"` |
| T220 | `route_after_fix()` | `{"unfixable_findings": []}` | `"__end__"` |
| T230 | `route_after_fix()` | non-empty unfixable | `"n2_reporter"` |
| T240 | `parse_args()` | `[]` | defaults: scope=all, auto_fix=True, etc. |
| T250 | `parse_args()` | all flags | all values parsed correctly |
| T260 | `parse_args()` | `["--scope", "invalid"]` | `SystemExit` |
| T270 | `main()` | mocked clean run | return `0` |
| T280 | `main()` | mocked unfixable findings | return `1` |
| T290 | `graph.invoke()` | integration with `LocalFileReporter` | report created, correct exit code |
| T300 | `main()` | mocked probes returning mixed | sweeper→fixer→reporter chain executes |
| T310 | `graph.invoke()` | `dry_run=True` with fixable | `FixAction(applied=False)`, file unchanged |
| T320 | `graph.invoke()` | broken link finding + real file | file updated, commit mocked |
| T330 | `graph.invoke()` | mixed findings | fix applied + report for unfixable |
| T340 | `main()` | `["--silent"]` + clean | no stdout |
| T350 | `main()` | not in git repo | return `2` |
| T360 | `GitHubReporter.__init__()` | `GITHUB_TOKEN` set, gh auth fails | reporter initializes successfully |
| T370 | `GitHubReporter.find_existing_report()` | existing issue found | returns URL, `update_report` would be called |
| T380 | `LocalFileReporter.create_report()` | standard inputs | file in `janitor-reports/` |
