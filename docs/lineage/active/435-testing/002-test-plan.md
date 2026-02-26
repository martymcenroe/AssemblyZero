# Extracted Test Plan

## Scenarios

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_gemini_review()` | Fixture `sample_lld_with_review.md` content (contains `### Gemini Review` heading) | `True`

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_gemini_review()` | Fixture `sample_lld_no_review.md` content (ends with `*No reviews yet.*`) | `False`

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_gemini_review()` | `""` | `False`

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_gemini_review()` | `"# 400 - Example\n\n## Appendix: Review Log\n\n### Gemini Revi"` (truncated marker) | `False`

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_gemini_review()` | Fixture with_review content + `"\n\n### Gemini Review\n\n | Field | Value | ..."` appended | `True`

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `embed_review_evidence()` | String containing `"APPROVED"`, `"Gemini"`, `"2026-02-25T10:00:00Z"`

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `embed_review_evidence()` | Result of T060 + same evidence dict | Verdict count equals T060 verdict count (no duplication)

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `embed_review_evidence()` | `ValueError`/`KeyError`/`TypeError` raised, OR returns original content unchanged

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `embed_review_evidence()` | `""` + valid evidence dict | `ValueError`/`TypeError` raised, OR returns string containing verdict

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `embed_review_evidence()` | Output contains `"## 1. Context & Goal"` and `"## 2. Proposed Changes"`

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `embed_review_evidence()` | Output contains `"Gemini"`, `"APPROVED"`, `"2026-02-25T10:00:00Z"`, `"gemini-2.5-pro"`, `"Design is sound"`

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_lld_tracking()` | `Path("tests/fixtures/lld_tracking/sample_tracking.json")` | Dict with key `"100"`, entry `{"issue_id": 100, "status": "approved", ...}`

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_lld_tracking()` | `tmp_path / "does_not_exist.json"` | `FileNotFoundError` raised OR `{}`

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_lld_tracking()` | `Path("tests/fixtures/lld_tracking/sample_tracking_corrupt.json")` | `json.JSONDecodeError` raised OR `{}`

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_lld_tracking()` | `tmp_path / "empty.json"` (0 bytes) | `{}` OR `json.JSONDecodeError`

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_lld_tracking()` | `Path("tests/fixtures/lld_tracking/sample_tracking.json")` | Dict with keys `{"100", "200", "300"}`

### test_t170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `update_lld_status()` | File with 3 entries, `issue_id=100, status="rejected"` | File re-read: entry 100 has `status="rejected"`, `lld_path` unchanged

### test_t180
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `update_lld_status()` | File with 3 entries (100, 200, 300), `issue_id=999, status="draft"` | File re-read: new entry 999 with `status="draft"`, keys 100/200/300 still present

### test_t190
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `update_lld_status()` | Non-existent file path, `issue_id=500, status="draft"` | File created, re-read: entry 500 with `status="draft"`

### test_t200
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `update_lld_status()` | File with 3 entries, `issue_id=200, status="reviewed", gemini_reviewed=True, review_verdict="APPROVED", review_timestamp="2026-02-25T12:00:00Z"` | Entry 200 has all kwargs merg

### test_t210
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `update_lld_status()` | File with 3 entries, `issue_id=100, status="invalid_value"` | `ValueError` raised OR graceful handling (entry stored)

### test_t220
- Type: unit
- Requirement: 
- Mock needed: False
- Description: N/A (meta-test) | `Path(__file__)` introspection + `inspect.getmembers()` | File in `tests/unit/`, name `test_lld_tracking.py`, ≥5 `Test*` classes

