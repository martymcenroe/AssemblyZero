# Extracted Test Plan

## Scenarios

### test_id
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Tests Function | File | Input | Expected Output

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `run_spelunking()` | `test_engine.py` | doc with "5 tools", 3 actual tools | DriftReport with MISMATCH, drift_score < 100

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `run_spelunking()` | `test_engine.py` | empty doc, empty repo | DriftReport(total_claims=0, drift_score=100.0)

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `run_spelunking()` | `test_engine.py` | 2 checkpoints, matching repo | DriftReport with 2 MATCH results

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_file_count_claims()` | `test_extractors.py` | "11 tools in tools/" | Claim(type=FILE_COUNT, expected="11")

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_file_reference_claims()` | `test_extractors.py` | "`tools/death.py`" | Claim(type=FILE_EXISTS, expected="tools/death.py")

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_technical_claims()` | `test_extractors.py` | "not vector embeddings" | Claim(type=TECHNICAL_FACT)

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_timestamp_claims()` | `test_extractors.py` | "Last Updated: 2026-01-15" | Claim(type=TIMESTAMP, expected="2026-01-15")

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_claims_from_markdown()` | `test_extractors.py` | "# Hello\nJust greeting" | `[]`

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `verify_file_count()` | `test_verifiers.py` | dir with 5 .py, expected=5 | VerificationResult(status=MATCH)

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `verify_file_count()` | `test_verifiers.py` | dir with 8 .py, expected=5 | VerificationResult(status=MISMATCH, actual="8")

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `verify_file_exists()` | `test_verifiers.py` | existing tmp file | VerificationResult(status=MATCH)

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `verify_file_exists()` | `test_verifiers.py` | nonexistent path | VerificationResult(status=MISMATCH)

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `verify_no_contradiction()` | `test_verifiers.py` | "chromadb" absent | VerificationResult(status=MATCH)

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `verify_no_contradiction()` | `test_verifiers.py` | "chromadb" present | VerificationResult(status=MISMATCH)

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `verify_unique_prefix()` | `test_verifiers.py` | 3 unique ADR files | VerificationResult(status=MATCH)

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `verify_unique_prefix()` | `test_verifiers.py` | 2 files with "0204-" | VerificationResult(status=MISMATCH)

### test_t170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `verify_timestamp_freshness()` | `test_verifiers.py` | today - 5 days | VerificationResult(status=MATCH)

### test_t180
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `verify_timestamp_freshness()` | `test_verifiers.py` | today - 45 days | VerificationResult(status=STALE)

### test_t190
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `verify_file_exists()` | `test_verifiers.py` | "../../etc/passwd" | VerificationResult(status=ERROR)

### test_t200
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `probe_inventory_drift()` | `test_probes.py` | inventory says 5, actual 8 | ProbeResult(passed=False)

### test_t210
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `probe_inventory_drift()` | `test_probes.py` | inventory says 3, actual 3 | ProbeResult(passed=True)

### test_t220
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `probe_dead_references()` | `test_probes.py` | doc refs ghost.py | ProbeResult(passed=False)

### test_t230
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `probe_dead_references()` | `test_probes.py` | doc refs existing file | ProbeResult(passed=True)

### test_t240
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `probe_adr_collision()` | `test_probes.py` | 0204-a.md, 0204-b.md | ProbeResult(passed=False)

### test_t250
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `probe_adr_collision()` | `test_probes.py` | unique prefixes | ProbeResult(passed=True)

### test_t260
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `probe_stale_timestamps()` | `test_probes.py` | date 45 days old | ProbeResult(passed=False)

### test_t270
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `probe_stale_timestamps()` | `test_probes.py` | date 5 days old | ProbeResult(passed=True)

### test_t275
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `probe_stale_timestamps()` | `test_probes.py` | stale + missing timestamp docs | ProbeResult(passed=False, 2+ findings)

### test_t280
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `probe_readme_claims()` | `test_probes.py` | "not chromadb" + import chromadb | ProbeResult(passed=False)

### test_t290
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `probe_readme_claims()` | `test_probes.py` | "not quantum" + no quantum code | ProbeResult(passed=True)

### test_t300
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `probe_persona_status()` | `test_probes.py` | 2 of 5 missing status | ProbeResult(passed=False)

### test_t310
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `DriftReport.drift_score` | `test_report.py` | 8 MATCH + 2 MISMATCH | drift_score == 80.0

### test_t320
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `generate_drift_report()` | `test_report.py` | DriftReport with mixed | Valid Markdown with tables

### test_t325
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `generate_drift_report()` | `test_report.py` | DriftReport, format="json" | Valid JSON with all fields

### test_t327
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `generate_drift_report()` | `test_report.py` | format="xml" | Raises ValueError

### test_t330
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `generate_probe_summary()` | `test_report.py` | 3 ProbeResults | Markdown table with [PASS]/[FAIL]

### test_t335
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `generate_probe_summary()` | `test_report.py` | 6 ProbeResults | Totals row with counts

### test_t340
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `run_all_probes()` | `test_engine.py` | empty tmp_path | 6 results, no crashes

### test_t350
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `DriftReport.drift_score` | `test_report.py` | 5 MATCH + 3 UNVERIFIABLE | drift_score == 100.0

### test_t360
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `test_T360_no_external_imports()` | `test_dependencies.py` | Scans spelunking/*.py + probe files on disk | No assertion errors (pass) or AssertionError listing third-party imports (fail)

### test_t365
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `test_T365_pyproject_unchanged()` | `test_dependencies.py` | pyproject.toml | No new suspicious dependencies

