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

# Test Plan for Issue #534

## Requirements to Cover

- REQ-T010: run_spelunking()
- REQ-T020: run_spelunking()
- REQ-T030: run_spelunking()
- REQ-T040: extract_file_count_claims()
- REQ-T050: extract_file_reference_claims()
- REQ-T060: extract_technical_claims()
- REQ-T070: extract_timestamp_claims()
- REQ-T080: extract_claims_from_markdown()
- REQ-T090: verify_file_count()
- REQ-T100: verify_file_count()
- REQ-T110: verify_file_exists()
- REQ-T120: verify_file_exists()
- REQ-T130: verify_no_contradiction()
- REQ-T140: verify_no_contradiction()
- REQ-T150: verify_unique_prefix()
- REQ-T160: verify_unique_prefix()
- REQ-T170: verify_timestamp_freshness()
- REQ-T180: verify_timestamp_freshness()
- REQ-T190: verify_file_exists()
- REQ-T200: probe_inventory_drift()
- REQ-T210: probe_inventory_drift()
- REQ-T220: probe_dead_references()
- REQ-T230: probe_dead_references()
- REQ-T240: probe_adr_collision()
- REQ-T250: probe_adr_collision()
- REQ-T260: probe_stale_timestamps()
- REQ-T270: probe_stale_timestamps()
- REQ-T275: probe_stale_timestamps()
- REQ-T280: probe_readme_claims()
- REQ-T290: probe_readme_claims()
- REQ-T300: probe_persona_status()
- REQ-T310: DriftReport.drift_score
- REQ-T320: generate_drift_report()
- REQ-T325: generate_drift_report()
- REQ-T327: generate_drift_report()
- REQ-T330: generate_probe_summary()
- REQ-T335: generate_probe_summary()
- REQ-T340: run_all_probes()
- REQ-T350: DriftReport.drift_score
- REQ-T360: test_T360_no_external_imports()
- REQ-T365: test_T365_pyproject_unchanged()

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
- **Description:** `run_spelunking()` | `test_engine.py` | doc with "5 tools", 3 actual tools | DriftReport with MISMATCH, drift_score < 100
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `run_spelunking()` | `test_engine.py` | empty doc, empty repo | DriftReport(total_claims=0, drift_score=100.0)
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `run_spelunking()` | `test_engine.py` | 2 checkpoints, matching repo | DriftReport with 2 MATCH results
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_file_count_claims()` | `test_extractors.py` | "11 tools in tools/" | Claim(type=FILE_COUNT, expected="11")
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_file_reference_claims()` | `test_extractors.py` | "`tools/death.py`" | Claim(type=FILE_EXISTS, expected="tools/death.py")
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_technical_claims()` | `test_extractors.py` | "not vector embeddings" | Claim(type=TECHNICAL_FACT)
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_timestamp_claims()` | `test_extractors.py` | "Last Updated: 2026-01-15" | Claim(type=TIMESTAMP, expected="2026-01-15")
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_claims_from_markdown()` | `test_extractors.py` | "# Hello\nJust greeting" | `[]`
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `verify_file_count()` | `test_verifiers.py` | dir with 5 .py, expected=5 | VerificationResult(status=MATCH)
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `verify_file_count()` | `test_verifiers.py` | dir with 8 .py, expected=5 | VerificationResult(status=MISMATCH, actual="8")
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `verify_file_exists()` | `test_verifiers.py` | existing tmp file | VerificationResult(status=MATCH)
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `verify_file_exists()` | `test_verifiers.py` | nonexistent path | VerificationResult(status=MISMATCH)
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `verify_no_contradiction()` | `test_verifiers.py` | "chromadb" absent | VerificationResult(status=MATCH)
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `verify_no_contradiction()` | `test_verifiers.py` | "chromadb" present | VerificationResult(status=MISMATCH)
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** `verify_unique_prefix()` | `test_verifiers.py` | 3 unique ADR files | VerificationResult(status=MATCH)
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** `verify_unique_prefix()` | `test_verifiers.py` | 2 files with "0204-" | VerificationResult(status=MISMATCH)
- **Mock needed:** False
- **Assertions:** 

### test_t170
- **Type:** unit
- **Requirement:** 
- **Description:** `verify_timestamp_freshness()` | `test_verifiers.py` | today - 5 days | VerificationResult(status=MATCH)
- **Mock needed:** False
- **Assertions:** 

### test_t180
- **Type:** unit
- **Requirement:** 
- **Description:** `verify_timestamp_freshness()` | `test_verifiers.py` | today - 45 days | VerificationResult(status=STALE)
- **Mock needed:** False
- **Assertions:** 

### test_t190
- **Type:** unit
- **Requirement:** 
- **Description:** `verify_file_exists()` | `test_verifiers.py` | "../../etc/passwd" | VerificationResult(status=ERROR)
- **Mock needed:** False
- **Assertions:** 

### test_t200
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_inventory_drift()` | `test_probes.py` | inventory says 5, actual 8 | ProbeResult(passed=False)
- **Mock needed:** False
- **Assertions:** 

### test_t210
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_inventory_drift()` | `test_probes.py` | inventory says 3, actual 3 | ProbeResult(passed=True)
- **Mock needed:** False
- **Assertions:** 

### test_t220
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_dead_references()` | `test_probes.py` | doc refs ghost.py | ProbeResult(passed=False)
- **Mock needed:** False
- **Assertions:** 

### test_t230
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_dead_references()` | `test_probes.py` | doc refs existing file | ProbeResult(passed=True)
- **Mock needed:** False
- **Assertions:** 

### test_t240
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_adr_collision()` | `test_probes.py` | 0204-a.md, 0204-b.md | ProbeResult(passed=False)
- **Mock needed:** False
- **Assertions:** 

### test_t250
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_adr_collision()` | `test_probes.py` | unique prefixes | ProbeResult(passed=True)
- **Mock needed:** False
- **Assertions:** 

### test_t260
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_stale_timestamps()` | `test_probes.py` | date 45 days old | ProbeResult(passed=False)
- **Mock needed:** False
- **Assertions:** 

### test_t270
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_stale_timestamps()` | `test_probes.py` | date 5 days old | ProbeResult(passed=True)
- **Mock needed:** False
- **Assertions:** 

### test_t275
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_stale_timestamps()` | `test_probes.py` | stale + missing timestamp docs | ProbeResult(passed=False, 2+ findings)
- **Mock needed:** False
- **Assertions:** 

### test_t280
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_readme_claims()` | `test_probes.py` | "not chromadb" + import chromadb | ProbeResult(passed=False)
- **Mock needed:** False
- **Assertions:** 

### test_t290
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_readme_claims()` | `test_probes.py` | "not quantum" + no quantum code | ProbeResult(passed=True)
- **Mock needed:** False
- **Assertions:** 

### test_t300
- **Type:** unit
- **Requirement:** 
- **Description:** `probe_persona_status()` | `test_probes.py` | 2 of 5 missing status | ProbeResult(passed=False)
- **Mock needed:** False
- **Assertions:** 

### test_t310
- **Type:** unit
- **Requirement:** 
- **Description:** `DriftReport.drift_score` | `test_report.py` | 8 MATCH + 2 MISMATCH | drift_score == 80.0
- **Mock needed:** False
- **Assertions:** 

### test_t320
- **Type:** unit
- **Requirement:** 
- **Description:** `generate_drift_report()` | `test_report.py` | DriftReport with mixed | Valid Markdown with tables
- **Mock needed:** False
- **Assertions:** 

### test_t325
- **Type:** unit
- **Requirement:** 
- **Description:** `generate_drift_report()` | `test_report.py` | DriftReport, format="json" | Valid JSON with all fields
- **Mock needed:** False
- **Assertions:** 

### test_t327
- **Type:** unit
- **Requirement:** 
- **Description:** `generate_drift_report()` | `test_report.py` | format="xml" | Raises ValueError
- **Mock needed:** False
- **Assertions:** 

### test_t330
- **Type:** unit
- **Requirement:** 
- **Description:** `generate_probe_summary()` | `test_report.py` | 3 ProbeResults | Markdown table with [PASS]/[FAIL]
- **Mock needed:** False
- **Assertions:** 

### test_t335
- **Type:** unit
- **Requirement:** 
- **Description:** `generate_probe_summary()` | `test_report.py` | 6 ProbeResults | Totals row with counts
- **Mock needed:** False
- **Assertions:** 

### test_t340
- **Type:** unit
- **Requirement:** 
- **Description:** `run_all_probes()` | `test_engine.py` | empty tmp_path | 6 results, no crashes
- **Mock needed:** False
- **Assertions:** 

### test_t350
- **Type:** unit
- **Requirement:** 
- **Description:** `DriftReport.drift_score` | `test_report.py` | 5 MATCH + 3 UNVERIFIABLE | drift_score == 100.0
- **Mock needed:** False
- **Assertions:** 

### test_t360
- **Type:** unit
- **Requirement:** 
- **Description:** `test_T360_no_external_imports()` | `test_dependencies.py` | Scans spelunking/*.py + probe files on disk | No assertion errors (pass) or AssertionError listing third-party imports (fail)
- **Mock needed:** True
- **Assertions:** 

### test_t365
- **Type:** unit
- **Requirement:** 
- **Description:** `test_T365_pyproject_unchanged()` | `test_dependencies.py` | pyproject.toml | No new suspicious dependencies
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | File | Input | Expected Output |
|---------|---------------|------|-------|-----------------|
| T010 | `run_spelunking()` | `test_engine.py` | doc with "5 tools", 3 actual tools | DriftReport with MISMATCH, drift_score < 100 |
| T020 | `run_spelunking()` | `test_engine.py` | empty doc, empty repo | DriftReport(total_claims=0, drift_score=100.0) |
| T030 | `run_spelunking()` | `test_engine.py` | 2 checkpoints, matching repo | DriftReport with 2 MATCH results |
| T040 | `extract_file_count_claims()` | `test_extractors.py` | "11 tools in tools/" | Claim(type=FILE_COUNT, expected="11") |
| T050 | `extract_file_reference_claims()` | `test_extractors.py` | "`tools/death.py`" | Claim(type=FILE_EXISTS, expected="tools/death.py") |
| T060 | `extract_technical_claims()` | `test_extractors.py` | "not vector embeddings" | Claim(type=TECHNICAL_FACT) |
| T070 | `extract_timestamp_claims()` | `test_extractors.py` | "Last Updated: 2026-01-15" | Claim(type=TIMESTAMP, expected="2026-01-15") |
| T080 | `extract_claims_from_markdown()` | `test_extractors.py` | "# Hello\nJust greeting" | `[]` |
| T090 | `verify_file_count()` | `test_verifiers.py` | dir with 5 .py, expected=5 | VerificationResult(status=MATCH) |
| T100 | `verify_file_count()` | `test_verifiers.py` | dir with 8 .py, expected=5 | VerificationResult(status=MISMATCH, actual="8") |
| T110 | `verify_file_exists()` | `test_verifiers.py` | existing tmp file | VerificationResult(status=MATCH) |
| T120 | `verify_file_exists()` | `test_verifiers.py` | nonexistent path | VerificationResult(status=MISMATCH) |
| T130 | `verify_no_contradiction()` | `test_verifiers.py` | "chromadb" absent | VerificationResult(status=MATCH) |
| T140 | `verify_no_contradiction()` | `test_verifiers.py` | "chromadb" present | VerificationResult(status=MISMATCH) |
| T150 | `verify_unique_prefix()` | `test_verifiers.py` | 3 unique ADR files | VerificationResult(status=MATCH) |
| T160 | `verify_unique_prefix()` | `test_verifiers.py` | 2 files with "0204-" | VerificationResult(status=MISMATCH) |
| T170 | `verify_timestamp_freshness()` | `test_verifiers.py` | today - 5 days | VerificationResult(status=MATCH) |
| T180 | `verify_timestamp_freshness()` | `test_verifiers.py` | today - 45 days | VerificationResult(status=STALE) |
| T190 | `verify_file_exists()` | `test_verifiers.py` | "../../etc/passwd" | VerificationResult(status=ERROR) |
| T200 | `probe_inventory_drift()` | `test_probes.py` | inventory says 5, actual 8 | ProbeResult(passed=False) |
| T210 | `probe_inventory_drift()` | `test_probes.py` | inventory says 3, actual 3 | ProbeResult(passed=True) |
| T220 | `probe_dead_references()` | `test_probes.py` | doc refs ghost.py | ProbeResult(passed=False) |
| T230 | `probe_dead_references()` | `test_probes.py` | doc refs existing file | ProbeResult(passed=True) |
| T240 | `probe_adr_collision()` | `test_probes.py` | 0204-a.md, 0204-b.md | ProbeResult(passed=False) |
| T250 | `probe_adr_collision()` | `test_probes.py` | unique prefixes | ProbeResult(passed=True) |
| T260 | `probe_stale_timestamps()` | `test_probes.py` | date 45 days old | ProbeResult(passed=False) |
| T270 | `probe_stale_timestamps()` | `test_probes.py` | date 5 days old | ProbeResult(passed=True) |
| T275 | `probe_stale_timestamps()` | `test_probes.py` | stale + missing timestamp docs | ProbeResult(passed=False, 2+ findings) |
| T280 | `probe_readme_claims()` | `test_probes.py` | "not chromadb" + import chromadb | ProbeResult(passed=False) |
| T290 | `probe_readme_claims()` | `test_probes.py` | "not quantum" + no quantum code | ProbeResult(passed=True) |
| T300 | `probe_persona_status()` | `test_probes.py` | 2 of 5 missing status | ProbeResult(passed=False) |
| T310 | `DriftReport.drift_score` | `test_report.py` | 8 MATCH + 2 MISMATCH | drift_score == 80.0 |
| T320 | `generate_drift_report()` | `test_report.py` | DriftReport with mixed | Valid Markdown with tables |
| T325 | `generate_drift_report()` | `test_report.py` | DriftReport, format="json" | Valid JSON with all fields |
| T327 | `generate_drift_report()` | `test_report.py` | format="xml" | Raises ValueError |
| T330 | `generate_probe_summary()` | `test_report.py` | 3 ProbeResults | Markdown table with [PASS]/[FAIL] |
| T335 | `generate_probe_summary()` | `test_report.py` | 6 ProbeResults | Totals row with counts |
| T340 | `run_all_probes()` | `test_engine.py` | empty tmp_path | 6 results, no crashes |
| T350 | `DriftReport.drift_score` | `test_report.py` | 5 MATCH + 3 UNVERIFIABLE | drift_score == 100.0 |
| T360 | `test_T360_no_external_imports()` | `test_dependencies.py` | Scans spelunking/*.py + probe files on disk | No assertion errors (pass) or AssertionError listing third-party imports (fail) |
| T365 | `test_T365_pyproject_unchanged()` | `test_dependencies.py` | pyproject.toml | No new suspicious dependencies |
