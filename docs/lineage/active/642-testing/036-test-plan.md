# Extracted Test Plan

## Scenarios

### test_id
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Test Description | Expected Behavior | Status

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_retry_prompt` retry_count=1 returns full LLD minus completed files | Prompt contains full LLD text; tier=1 | RED

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_retry_prompt` retry_count=2 returns section-only prompt | Prompt does NOT contain full LLD; contains only relevant section; tier=2 | RED

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Tier 2 prompt is ≤50% tokens of tier 1 prompt for same context | `estimated_tokens` in tier 2 ≤ 0.50 × tier 1 for full_lld.md fixture | RED

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Tier 2 fallback when section not found | Falls back to tier 1 behavior; emits warning | RED

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_retry_prompt` raises ValueError when retry_count < 1 | ValueError raised | RED

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_retry_prompt` raises ValueError when retry_count=2 and snippet is None | ValueError raised | RED

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_truncate_snippet` truncates to max_lines | Output has ≤max_lines lines; leading ellipsis present | RED

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_truncate_snippet` returns unchanged when input ≤max_lines | Output equals input exactly | RED

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_file_spec_section` exact path match returns confidence=1.0 | confidence == 1.0; correct section body returned | RED

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_file_spec_section` stem match returns confidence<1.0 | 0.0 < confidence < 1.0 | RED

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_file_spec_section` no match returns None | Returns None | RED

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_file_spec_section` raises ValueError on empty lld_content | ValueError raised | RED

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_estimate_tokens` returns positive int for non-empty string | Result > 0 | RED

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_estimate_tokens` returns 0 or handles empty string gracefully | No exception; returns 0 | RED

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_retry_prompt` completed_files excluded from tier 1 prompt | Excluded file names absent from prompt text | RED

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: All functions in retry_prompt_builder have complete type annotations | mypy reports zero errors on the module | RED

### test_t170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: All functions in lld_section_extractor have complete type annotations | mypy reports zero errors on the module | RED

### test_t180
- Type: unit
- Requirement: 
- Mock needed: False
- Description: pytest-cov reports ≥95% line coverage for retry_prompt_builder | Coverage report shows ≥95% | RED

### test_t190
- Type: unit
- Requirement: 
- Mock needed: False
- Description: pytest-cov reports ≥95% line coverage for lld_section_extractor | Coverage report shows ≥95% | RED

### test_t200
- Type: unit
- Requirement: 
- Mock needed: False
- Description: No new entries added to pyproject.toml dependencies section | pyproject.toml diff contains no new runtime dependency lines | RED

### test_t210
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Workflow state TypedDict includes retry_count integer field defaulting to 0 | Field present in state definition; default value is 0 | RED

### test_t220
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Workflow call site passes retry_count to build_retry_prompt | Integration test verifies retry_count flows from state into RetryContext | RED

### test_010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Happy path tier 1 (REQ-1) | Auto | `RetryContext(retry_count=1, lld=full_lld, ...)` | `PrunedRetryPrompt(tier=1)` | tier==1; prompt contains LLD text

### test_020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Happy path tier 2 (REQ-2) | Auto | `RetryContext(retry_count=2, lld=full_lld, snippet="...", ...)` | `PrunedRetryPrompt(tier=2)` | tier==2; prompt lacks bulk of LLD; contains relevant section, error, 

### test_030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Token reduction ≥50% (REQ-3) | Auto | Same context; compare tier 1 vs tier 2 token estimates | tier2.estimated_tokens ≤ 0.5 × tier1.estimated_tokens | Numeric assertion passes

### test_040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Fallback on no section (REQ-4) | Auto | LLD with no mention of target_file; retry_count=2 | tier==1 fallback; warning logged | tier==1; no exception

### test_050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Invalid retry_count=0 (REQ-1) | Auto | `RetryContext(retry_count=0, ...)` | `ValueError` | Exception raised with descriptive message

### test_060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Tier 2, snippet None (REQ-2) | Auto | `RetryContext(retry_count=2, previous_attempt_snippet=None, ...)` | `ValueError` | Exception raised

### test_070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Snippet longer than max_lines (REQ-5) | Auto | snippet with 200 lines | Truncated to SNIPPET_MAX_LINES; starts with "..." | len(output.splitlines()) ≤ SNIPPET_MAX_LINES

### test_080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Snippet shorter than max_lines (REQ-5) | Auto | snippet with 5 lines | Unchanged | output == input

### test_090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Section extraction exact match (REQ-7) | Auto | LLD containing `assemblyzero/foo/bar.py`; target=`assemblyzero/foo/bar.py` | confidence==1.0 | Assertion passes

### test_100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Section extraction stem match (REQ-7) | Auto | LLD containing `bar.py` but not full path; target=`assemblyzero/foo/bar.py` | 0.0 < confidence < 1.0 | Assertion passes

### test_110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Section extraction no match (REQ-7) | Auto | LLD with no mention of target file or stem | None | Returns None

### test_120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Empty LLD raises ValueError (REQ-7) | Auto | `lld_content=""` | `ValueError` | Exception raised

### test_130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Token estimate positive (REQ-3) | Auto | `"Hello world"` | int > 0 | Assertion passes

### test_140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Token estimate empty string (REQ-3) | Auto | `""` | 0 or no exception | No crash; result ≥ 0

### test_150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Completed files excluded tier 1 (REQ-1) | Auto | `completed_files=["assemblyzero/done.py"]`; retry_count=1 | `"done.py"` not in prompt_text | String search passes

### test_160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Type annotations complete — retry_prompt_builder (REQ-6) | Auto | Run `mypy assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py --strict` | Exit code 0; zero errors reported | myp

### test_170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Type annotations complete — lld_section_extractor (REQ-6) | Auto | Run `mypy assemblyzero/utils/lld_section_extractor.py --strict` | Exit code 0; zero errors reported | mypy passes with no errors

### test_180
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Coverage ≥95% retry_prompt_builder (REQ-8) | Auto | Run pytest-cov on retry_prompt_builder module | Coverage report line% ≥ 95 | pytest-cov assertion passes

### test_190
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Coverage ≥95% lld_section_extractor (REQ-8) | Auto | Run pytest-cov on lld_section_extractor module | Coverage report line% ≥ 95 | pytest-cov assertion passes

### test_200
- Type: unit
- Requirement: 
- Mock needed: False
- Description: No new runtime dependencies added (REQ-9) | Auto | Read `pyproject.toml` dependencies section before and after; diff | Diff is empty (no new lines in `[project.dependencies]`) | Automated diff asserti

### test_210
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Workflow state includes retry_count field (REQ-10) | Auto | Inspect workflow state TypedDict definition; verify field presence and default | `retry_count: int` present with default `0` | AST/import as

### test_220
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Workflow call site passes retry_count and previous_attempt_snippet (REQ-10) | Auto | Unit test that constructs a minimal workflow state with retry_count=2 and invokes the call site wrapper; assert Ret

