# Implementation Spec: #642 — Retry Context Pruning

## 1. Overview

Implement tiered context pruning in `build_retry_prompt()` so that the first retry sends the full LLD while retry 2+ sends only the relevant LLD file spec section, the error message, and a truncated previous-attempt snippet. This reduces retry prompt size by 50–60% and cuts per-retry API spend by $0.05–0.10.

**Objective:** Two-tier context pruning for retry prompts — full LLD on retry 1, minimal context on retry 2+.

**Success Criteria:** Tier 2 prompt token count ≤50% of Tier 1 for an 80K-token LLD; graceful fallback to Tier 1 when section extraction fails; ≥95% test coverage on new modules.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `tests/fixtures/retry_prompt/full_lld.md` | Add | Large sample LLD fixture (~400 lines, 5+ sections with file paths) |
| 2 | `tests/fixtures/retry_prompt/minimal_lld.md` | Add | Small LLD fixture with single file spec section |
| 3 | `assemblyzero/utils/lld_section_extractor.py` | Add | Utility to extract file-relevant sections from LLD markdown |
| 4 | `assemblyzero/utils/__init__.py` | Modify | Export `extract_file_spec_section` |
| 5 | `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py` | Add | Core module with `build_retry_prompt()` and tiered pruning logic |
| 6 | `assemblyzero/workflows/implementation_spec/nodes/__init__.py` | Modify | Export `build_retry_prompt` |
| 7 | `assemblyzero/workflows/implementation_spec/state.py` | Modify | Add `retry_count: int` (default 0) and `previous_attempt_snippet: str | None` (default None) to workflow state TypedDict |
| 8 | `assemblyzero/workflows/implementation_spec/nodes/generate_code.py` | Modify | Update call site to construct `RetryContext` from workflow state and pass to `build_retry_prompt()` |
| 9 | `tests/unit/test_lld_section_extractor.py` | Add | Unit tests for section extraction |
| 10 | `tests/unit/test_retry_prompt_builder.py` | Add | Unit tests for retry prompt builder including integration with workflow state |

**Implementation Order Rationale:** Fixtures first (needed by tests), then the utility module (no internal deps), then the main prompt builder module (depends on utility), then exports, then workflow state update (no code deps on new modules), then call site integration (depends on state + prompt builder), then tests last (depend on everything).

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/workflows/implementation_spec/nodes/__init__.py`

[UNCHANGED]

### 3.2 `assemblyzero/utils/__init__.py`

[UNCHANGED]

## 4. Data Structures

### 4.1 RetryContext

[UNCHANGED]

### 4.2 PrunedRetryPrompt

[UNCHANGED]

### 4.3 ExtractedSection

[UNCHANGED]

## 5. Function Specifications

### 5.1 `build_retry_prompt()`

[UNCHANGED]

### 5.2 `_build_tier1_prompt()`

[UNCHANGED]

### 5.3 `_build_tier2_prompt()`

[UNCHANGED]

### 5.4 `_truncate_snippet()`

[UNCHANGED]

### 5.5 `_estimate_tokens()`

[UNCHANGED]

### 5.6 `extract_file_spec_section()`

[UNCHANGED]

### 5.7 `_split_lld_into_sections()`

[UNCHANGED]

### 5.8 `_score_section_for_file()`

[UNCHANGED]

## 6. Change Instructions

### 6.1 `tests/fixtures/retry_prompt/full_lld.md` (Add)

## 1. Context & Goal

This is a sample LLD used for testing retry prompt context pruning.
It contains multiple file-specific sections to verify that section extraction
correctly identifies the relevant section for a given target file.

General project context that spans multiple paragraphs to simulate
a realistic LLD preamble with substantial content that contributes
to overall token count.

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod
tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam,
quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/services/alpha_service.py` | Add | Alpha service implementation |
| `assemblyzero/services/beta_service.py` | Add | Beta service implementation |
| `assemblyzero/models/gamma_model.py` | Modify | Gamma model updates |
| `assemblyzero/utils/delta_helper.py` | Add | Delta helper utility |
| `assemblyzero/workflows/epsilon_flow.py` | Add | Epsilon workflow node |

## 3. Requirements

[UNCHANGED]

## Section for assemblyzero/services/alpha_service.py

### Function Signatures

[UNCHANGED]

### Data Structures

[UNCHANGED]

## Section for assemblyzero/services/beta_service.py

### Function Signatures

[UNCHANGED]

### Constants

[UNCHANGED]

## Section for assemblyzero/models/gamma_model.py

### Current State

[UNCHANGED]

### Proposed Changes

[UNCHANGED]

## Section for assemblyzero/utils/delta_helper.py

### Function Signatures

[UNCHANGED]

## Section for assemblyzero/workflows/epsilon_flow.py

### Function Signatures

[UNCHANGED]

### Integration Points

[UNCHANGED]

## 4. Alternatives Considered

[UNCHANGED]

## 5. Security Considerations

[UNCHANGED]

## Padding Section Alpha

[UNCHANGED]

## Padding Section Beta

[UNCHANGED]

## Padding Section Gamma

[UNCHANGED]

## Padding Section Delta

[UNCHANGED]

## Padding Section Epsilon

[UNCHANGED]

### 6.2 `tests/fixtures/retry_prompt/minimal_lld.md` (Add)

## 1. Context

[UNCHANGED]

## Section for assemblyzero/utils/tiny_helper.py

### Function Signatures

[UNCHANGED]

### Implementation Notes

[UNCHANGED]

### 6.3 `assemblyzero/utils/lld_section_extractor.py` (Add)

[UNCHANGED]

### 6.4 `assemblyzero/utils/__init__.py` (Modify)

[UNCHANGED]

### 6.5 `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py` (Add)

[UNCHANGED]

### 6.6 `assemblyzero/workflows/implementation_spec/nodes/__init__.py` (Modify)

[UNCHANGED]

### 6.7 `tests/unit/test_lld_section_extractor.py` (Add)

[UNCHANGED]

### 6.8 `tests/unit/test_retry_prompt_builder.py` (Add)

[UNCHANGED]

## 7. Pattern References

### 7.1 Node Module Structure

[UNCHANGED]

### 7.2 Utils Module Structure

[UNCHANGED]

### 7.3 `__init__.py` Export Pattern

[UNCHANGED]

### 7.4 Test Structure Pattern

[UNCHANGED]

## 8. Dependencies & Imports

[UNCHANGED]

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `build_retry_prompt()` | `RetryContext(retry_count=1, lld=full_lld, target="alpha_service.py", error="SyntaxError")` | `PrunedRetryPrompt(tier=1)`, prompt contains "beta_service", "gamma_model" |
| T020 | `build_retry_prompt()` | `RetryContext(retry_count=2, lld=full_lld, target="alpha_service.py", snippet="code")` | `PrunedRetryPrompt(tier=2)`, prompt lacks "Padding Section Gamma" |
| T030 | `build_retry_prompt()` | Same ctx for tier 1 and tier 2 | `tier2.estimated_tokens <= 0.50 * tier1.estimated_tokens` |
| T040 | `build_retry_prompt()` | LLD with no mention of target; `retry_count=2` | `tier=1` (fallback); warning logged |
| T050 | `build_retry_prompt()` | `retry_count=0` | `ValueError("retry_count must be >= 1")` |
| T060 | `build_retry_prompt()` | `retry_count=2, snippet=None` | `ValueError("Tier 2 requires previous_attempt_snippet")` |
| T070 | `_truncate_snippet()` | 200-line snippet, `max_lines=60` | Output ≤61 lines; starts with "..."; contains "line 199" |
| T080 | `_truncate_snippet()` | 3-line snippet, `max_lines=60` | Output unchanged |
| T090 | `extract_file_spec_section()` | full_lld, target="assemblyzero/services/alpha_service.py" | `confidence=1.0`, body contains "Alpha service" |
| T100 | `extract_file_spec_section()` | LLD with stem only, target with full path | `0.0 < confidence < 1.0` |
| T110 | `extract_file_spec_section()` | LLD with no match | `None` |
| T120 | `extract_file_spec_section()` | `lld_content=""` | `ValueError("lld_content must not be empty")` |
| T130 | `_estimate_tokens()` | `"Hello, world!"` | `int > 0` |
| T140 | `_estimate_tokens()` | `""` | `0` |
| T150 | `build_retry_prompt()` | `completed_files=["beta_service.py"], retry_count=1` | "Beta service provides" not in prompt |
| T160 | mypy strict | `retry_prompt_builder.py` | Exit code 0 |
| T170 | mypy strict | `lld_section_extractor.py` | Exit code 0 |
| T180 | pytest-cov | `retry_prompt_builder` module | ≥95% line coverage |
| T190 | pytest-cov | `lld_section_extractor` module | ≥95% line coverage |
| T200 | pyproject.toml diff | Before/after | No new runtime deps |
| T210 | Workflow state definition | Import `ImplementationSpecState` from `assemblyzero/workflows/implementation_spec/state.py`; inspect annotations | `retry_count: int` field present; default value is `0`. `previous_attempt_snippet: str \| None` field present; default value is `None`. |
| T220 | Workflow call site integration | Construct `ImplementationSpecState` with `retry_count=2, previous_attempt_snippet="err at line 5"`; invoke the call site function that builds the retry prompt | Returned `RetryContext["retry_count"]` equals `2`; `RetryContext["previous_attempt_snippet"]` equals `"err at line 5"`. Verifies the call site in `generate_code.py` correctly maps state fields to `RetryContext`. |

## 11. Implementation Notes

### 11.1 Error Handling Convention

[UNCHANGED]

### 11.2 Logging Convention

[UNCHANGED]

### 11.3 Constants

[UNCHANGED]

### 11.4 Fixture Design Rationale

[UNCHANGED]

### 11.5 Type Annotation Notes

[UNCHANGED]

## Completeness Checklist

[UNCHANGED]

## Review Log

[UNCHANGED]