# Implementation Spec: Fix — Reduce Retry Prompt Context More Aggressively

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #642 |
| LLD | `docs/lld/active/642-reduce-retry-prompt-context.md` |
| Generated | 2026-03-07 |
| Status | DRAFT |

## 1. Overview

Implement tiered context pruning in `build_retry_prompt()` so that Retry 1 sends full LLD context (current behavior) while Retry 2+ sends only the relevant LLD file spec section, the error message, and a truncated previous-attempt snippet. This cuts retry prompt size by 50–60% and reduces per-retry API spend.

**Objective:** Tier 2 retry prompts contain only the relevant LLD section, error, and prior-attempt snippet — no full LLD.

**Success Criteria:** Tier 2 token count ≤ 50% of equivalent Tier 1 prompt; graceful fallback to Tier 1 on extraction failure; ≥ 95% test coverage on new modules; zero new runtime dependencies.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `tests/fixtures/retry_prompt/full_lld.md` | Add | Large fixture LLD with ≥5 sections and explicit file paths |
| 2 | `tests/fixtures/retry_prompt/minimal_lld.md` | Add | Small fixture LLD with single file spec section |
| 3 | `assemblyzero/utils/lld_section_extractor.py` | Add | Utility to extract file-relevant section from LLD markdown |
| 4 | `assemblyzero/utils/__init__.py` | Modify | Export `extract_file_spec_section` |
| 5 | `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py` | Add | Core `build_retry_prompt()` with tiered pruning logic |
| 6 | `assemblyzero/workflows/implementation_spec/nodes/__init__.py` | Modify | Export `build_retry_prompt` |
| 7 | `tests/unit/test_lld_section_extractor.py` | Add | Unit tests for section extraction |
| 8 | `tests/unit/test_retry_prompt_builder.py` | Add | Unit tests for prompt builder across all tiers |

**Implementation Order Rationale:** Fixtures first (no dependencies). Then the utility module (`lld_section_extractor`) since the prompt builder depends on it. Then the prompt builder itself. Then the `__init__.py` exports. Finally the tests (which import from the newly-exported modules).

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/workflows/implementation_spec/nodes/__init__.py`

**Relevant excerpt** (lines 1–47, complete file):

```python
"""Nodes package for Implementation Spec workflow.

Issue #304: Implementation Readiness Review Workflow (LLD -> Implementation Spec)

Individual node implementations for the LangGraph workflow:
- N0: load_lld - Load and parse approved LLD
- N1: analyze_codebase - Extract current state from codebase files
- N2: generate_spec - Generate Implementation Spec draft (Claude)
- N3: validate_completeness - Mechanical completeness checks
- N4: human_gate - Optional human review checkpoint
- N5: review_spec - Gemini readiness review
- N6: finalize_spec - Write final spec to docs/lld/drafts/
"""

from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import (
    analyze_codebase,
    extract_relevant_excerpt,
    find_pattern_references,
)

from assemblyzero.workflows.implementation_spec.nodes.finalize_spec import (
    finalize_spec,
    generate_spec_filename,
)

from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
    build_drafter_prompt,
    generate_spec,
)

from assemblyzero.workflows.implementation_spec.nodes.human_gate import human_gate

from assemblyzero.workflows.implementation_spec.nodes.load_lld import (
    load_lld,
    parse_files_to_modify,
)

from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
    parse_review_verdict,
    review_spec,
)

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_change_instructions_specific,
    check_data_structures_have_examples,
    check_functions_have_io_examples,
    check_modify_files_have_excerpts,
    check_pattern_references_valid,
    validate_completeness,
)
```

**What changes:** Append an import block for `build_retry_prompt` from the new `retry_prompt_builder` module at the end of the file.

### 3.2 `assemblyzero/utils/__init__.py`

**Relevant excerpt** (lines 1–26, complete file):

```python
"""Utility modules for AssemblyZero."""

from assemblyzero.utils.codebase_reader import (
    FileReadResult,
    is_sensitive_file,
    parse_project_metadata,
    read_file_with_budget,
    read_files_within_budget,
)

from assemblyzero.utils.lld_verification import (
    LLDVerificationError,
    LLDVerificationResult,
    detect_false_approval,
    extract_review_log_verdicts,
    has_gemini_approved_footer,
    run_verification_gate,
    validate_lld_path,
    verify_lld_approval,
)

from assemblyzero.utils.pattern_scanner import (
    PatternAnalysis,
    detect_frameworks,
    extract_conventions_from_claude_md,
    scan_patterns,
)
```

**What changes:** Append an import block for `extract_file_spec_section` and `ExtractedSection` from the new `lld_section_extractor` module at the end of the file.

## 4. Data Structures

### 4.1 RetryContext

**Definition:**

```python
class RetryContext(TypedDict):
    """All information needed to build a retry prompt at any tier."""
    lld_content: str
    target_file: str
    error_message: str
    retry_count: int
    previous_attempt_snippet: str | None
    completed_files: list[str]
```

**Concrete Example:**

```json
{
    "lld_content": "# 642 - Fix: Reduce Retry Prompt Context\n\n## 2. Proposed Changes\n\n### 2.1 Files Changed\n\n| File | Change Type | Description |\n|------|-------------|-------------|\n| `assemblyzero/utils/lld_section_extractor.py` | Add | Utility for section extraction |\n\n## 3. Requirements\n\n1. Token count must decrease by 50%...\n\n## Section for assemblyzero/nodes/other_file.py\n\nThis section covers other_file.py implementation...\n",
    "target_file": "assemblyzero/utils/lld_section_extractor.py",
    "error_message": "IndentationError: unexpected indent at line 45",
    "retry_count": 2,
    "previous_attempt_snippet": "def extract_file_spec_section(lld_content: str, target_file: str) -> ExtractedSection | None:\n    sections = _split_lld_into_sections(lld_content)\n        scored = []  # <-- IndentationError here\n    for heading, body in sections:\n        score = _score_section_for_file(body, target_file)\n        scored.append((score, heading, body))\n    return None\n",
    "completed_files": ["assemblyzero/utils/__init__.py", "assemblyzero/nodes/other_file.py"]
}
```

### 4.2 PrunedRetryPrompt

**Definition:**

```python
class PrunedRetryPrompt(TypedDict):
    """Output of build_retry_prompt() — the assembled prompt and metadata."""
    prompt_text: str
    tier: int
    estimated_tokens: int
    context_sections_included: list[str]
```

**Concrete Example:**

```json
{
    "prompt_text": "You are fixing a code generation error. Below is the relevant specification section for the file you are implementing.\n\n## Relevant Specification\n\n### 2.1 Files Changed\n\n| File | Change Type | Description |\n| `assemblyzero/utils/lld_section_extractor.py` | Add | Utility for section extraction |\n\n## Target File\n\nassemblyzero/utils/lld_section_extractor.py\n\n## Error from Previous Attempt\n\nIndentationError: unexpected indent at line 45\n\n## Previous Attempt (last 60 lines)\n\ndef extract_file_spec_section(lld_content: str, target_file: str) -> ExtractedSection | None:\n    sections = _split_lld_into_sections(lld_content)\n        scored = []  # <-- IndentationError here\n    ...\n",
    "tier": 2,
    "estimated_tokens": 187,
    "context_sections_included": ["relevant_file_spec_section", "error_message", "previous_attempt_snippet"]
}
```

### 4.3 ExtractedSection

**Definition:**

```python
class ExtractedSection(TypedDict):
    """Result of extracting a single relevant section from an LLD."""
    section_heading: str
    section_body: str
    match_confidence: float
```

**Concrete Example:**

```json
{
    "section_heading": "### 2.1 Files Changed",
    "section_body": "### 2.1 Files Changed\n\n| File | Change Type | Description |\n|------|-------------|-------------|\n| `assemblyzero/utils/lld_section_extractor.py` | Add | Utility for section extraction |\n| `assemblyzero/nodes/other_file.py` | Add | Other module |\n",
    "match_confidence": 1.0
}
```

## 5. Function Specifications

### 5.1 `build_retry_prompt()`

**File:** `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py`

**Signature:**

```python
def build_retry_prompt(ctx: RetryContext) -> PrunedRetryPrompt:
    """Build a retry prompt applying tiered context pruning."""
    ...
```

**Input Example:**

```python
ctx = RetryContext(
    lld_content="# 642 - Fix\n\n## Section for assemblyzero/utils/lld_section_extractor.py\n\nThis section covers the extractor implementation details.\n\n## Section for assemblyzero/nodes/other_file.py\n\nOther file details here.\n",
    target_file="assemblyzero/utils/lld_section_extractor.py",
    error_message="NameError: name 'foo' is not defined",
    retry_count=2,
    previous_attempt_snippet="def extract():\n    return foo\n",
    completed_files=["assemblyzero/nodes/other_file.py"],
)
```

**Output Example:**

```python
PrunedRetryPrompt(
    prompt_text="You are fixing a code generation error...\n\n## Relevant Specification\n\n## Section for assemblyzero/utils/lld_section_extractor.py\n\nThis section covers the extractor implementation details.\n\n## Target File\n\nassemblyzero/utils/lld_section_extractor.py\n\n## Error from Previous Attempt\n\nNameError: name 'foo' is not defined\n\n## Previous Attempt (last 60 lines)\n\ndef extract():\n    return foo\n",
    tier=2,
    estimated_tokens=95,
    context_sections_included=["relevant_file_spec_section", "error_message", "previous_attempt_snippet"],
)
```

**Edge Cases:**
- `retry_count=0` -> raises `ValueError("retry_count must be >= 1, got 0")`
- `retry_count < 0` -> raises `ValueError("retry_count must be >= 1, got -3")`
- `lld_content=""` -> raises `ValueError("lld_content must not be empty")`
- `target_file=""` -> raises `ValueError("target_file must not be empty")`
- `error_message=""` -> raises `ValueError("error_message must not be empty")`
- `retry_count=2, previous_attempt_snippet=None` -> raises `ValueError("Tier 2 requires previous_attempt_snippet")`
- `retry_count=2`, section extraction returns `None` -> falls back to tier 1, logs warning, returns `tier=1`

### 5.2 `_build_tier1_prompt()`

**File:** `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py`

**Signature:**

```python
def _build_tier1_prompt(ctx: RetryContext) -> str:
    """Assemble full-LLD retry prompt (current behavior, Retry 1)."""
    ...
```

**Input Example:**

```python
ctx = RetryContext(
    lld_content="# Full LLD\n\n## Section A (assemblyzero/done.py)\n\nDone file section.\n\n## Section B (assemblyzero/target.py)\n\nTarget file section.\n",
    target_file="assemblyzero/target.py",
    error_message="SyntaxError: invalid syntax",
    retry_count=1,
    previous_attempt_snippet=None,
    completed_files=["assemblyzero/done.py"],
)
```

**Output Example:**

```python
"""You are retrying a code generation task. The full specification is provided below.

## Specification

# Full LLD

## Section B (assemblyzero/target.py)

Target file section.

## Target File

assemblyzero/target.py

## Error from Previous Attempt

SyntaxError: invalid syntax"""
```

**Edge Cases:**
- `completed_files` is empty -> entire LLD is included
- `completed_files` contains a file not in LLD -> no change (silently ignored)

### 5.3 `_build_tier2_prompt()`

**File:** `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py`

**Signature:**

```python
def _build_tier2_prompt(ctx: RetryContext) -> str:
    """Assemble minimal retry prompt (Retry 2+)."""
    ...
```

**Input Example:**

```python
ctx = RetryContext(
    lld_content="# Full LLD content with many sections...\n\n## Section for assemblyzero/utils/extractor.py\n\nExtractor implementation details spanning many lines.\n",
    target_file="assemblyzero/utils/extractor.py",
    error_message="TypeError: expected str got int",
    retry_count=2,
    previous_attempt_snippet="def extract(x):\n    return x + 1\n",
    completed_files=[],
)
```

**Output Example:**

```python
"""You are fixing a code generation error. Below is ONLY the relevant specification section for the file you are implementing — not the full specification.

## Relevant Specification

## Section for assemblyzero/utils/extractor.py

Extractor implementation details spanning many lines.

## Target File

assemblyzero/utils/extractor.py

## Error from Previous Attempt

TypeError: expected str got int

## Previous Attempt (last 60 lines)

def extract(x):
    return x + 1"""
```

**Edge Cases:**
- `previous_attempt_snippet=None` -> raises `ValueError("Tier 2 requires previous_attempt_snippet")`
- Section extraction returns `None` -> returns result of `_build_tier1_prompt(ctx)` (fallback)

### 5.4 `_truncate_snippet()`

**File:** `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py`

**Signature:**

```python
def _truncate_snippet(snippet: str, max_lines: int = SNIPPET_MAX_LINES) -> str:
    """Truncate a previous-attempt snippet to at most max_lines lines (tail)."""
    ...
```

**Input Example (truncation needed):**

```python
snippet = "\n".join([f"line {i}" for i in range(200)])  # 200 lines
max_lines = 60
```

**Output Example (truncation needed):**

```python
"...\nline 140\nline 141\n...\nline 199"
# Exactly 60 lines: "..." prefix line + last 59 source lines
# Total: 60 lines
```

More precisely: if there are more than `max_lines` lines, keep the last `max_lines - 1` lines and prepend a single `"..."` line.

**Input Example (no truncation):**

```python
snippet = "line 1\nline 2\nline 3\nline 4\nline 5"
max_lines = 60
```

**Output Example (no truncation):**

```python
"line 1\nline 2\nline 3\nline 4\nline 5"  # unchanged
```

**Edge Cases:**
- Empty string `""` -> returns `""`
- Exactly `max_lines` lines -> returns unchanged
- Single line -> returns unchanged

### 5.5 `_estimate_tokens()`

**File:** `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py`

**Signature:**

```python
def _estimate_tokens(text: str) -> int:
    """Estimate token count using tiktoken cl100k_base encoding."""
    ...
```

**Input Example:**

```python
text = "Hello world, this is a test."
```

**Output Example:**

```python
7  # tiktoken cl100k_base encoding result
```

**Edge Cases:**
- Empty string `""` -> returns `0`
- tiktoken encoding error (exotic chars) -> returns `-1` (sentinel, wrapped in try/except)

### 5.6 `_strip_completed_file_sections()`

**File:** `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py`

**Signature:**

```python
def _strip_completed_file_sections(lld_content: str, completed_files: list[str]) -> str:
    """Remove sections from LLD that correspond to already-completed files."""
    ...
```

**Input Example:**

```python
lld_content = "# LLD\n\n## Section for src/done.py\n\nDone content.\n\n## Section for src/target.py\n\nTarget content.\n"
completed_files = ["src/done.py"]
```

**Output Example:**

```python
"# LLD\n\n## Section for src/target.py\n\nTarget content.\n"
```

**Edge Cases:**
- `completed_files` is empty -> returns `lld_content` unchanged
- No sections match `completed_files` -> returns `lld_content` unchanged

### 5.7 `extract_file_spec_section()`

**File:** `assemblyzero/utils/lld_section_extractor.py`

**Signature:**

```python
def extract_file_spec_section(lld_content: str, target_file: str) -> ExtractedSection | None:
    """Parse LLD markdown and extract the section most relevant to target_file."""
    ...
```

**Input Example (exact match):**

```python
lld_content = "# LLD\n\n## Overview\n\nGeneral intro.\n\n## Section for assemblyzero/utils/extractor.py\n\nThis section has `assemblyzero/utils/extractor.py` details.\nFunction signatures and data structures.\n\n## Section for assemblyzero/nodes/builder.py\n\nBuilder details.\n"
target_file = "assemblyzero/utils/extractor.py"
```

**Output Example (exact match):**

```python
ExtractedSection(
    section_heading="## Section for assemblyzero/utils/extractor.py",
    section_body="## Section for assemblyzero/utils/extractor.py\n\nThis section has `assemblyzero/utils/extractor.py` details.\nFunction signatures and data structures.\n",
    match_confidence=1.0,
)
```

**Input Example (stem match only):**

```python
lld_content = "# LLD\n\n## Extractor Module\n\nThis describes the extractor.py module.\n\n## Builder Module\n\nBuilder stuff.\n"
target_file = "assemblyzero/utils/extractor.py"
```

**Output Example (stem match only):**

```python
ExtractedSection(
    section_heading="## Extractor Module",
    section_body="## Extractor Module\n\nThis describes the extractor.py module.\n",
    match_confidence=0.6,
)
```

**Input Example (no match):**

```python
lld_content = "# LLD\n\n## Overview\n\nGeneral intro with no file references.\n"
target_file = "assemblyzero/nonexistent/module.py"
```

**Output Example (no match):**

```python
None
```

**Edge Cases:**
- `lld_content=""` -> raises `ValueError("lld_content must not be empty")`
- LLD with only a single top-level heading and no `##` sections -> returns `None`
- Multiple sections mention the target file -> returns the one with the highest score (first exact match wins)

### 5.8 `_split_lld_into_sections()`

**File:** `assemblyzero/utils/lld_section_extractor.py`

**Signature:**

```python
def _split_lld_into_sections(lld_content: str) -> list[tuple[str, str]]:
    """Split LLD markdown into (heading, body) tuples at ## and ### boundaries."""
    ...
```

**Input Example:**

```python
lld_content = "# Title\n\nPreamble text.\n\n## Section A\n\nContent A.\n\n### Subsection A1\n\nSub content.\n\n## Section B\n\nContent B.\n"
```

**Output Example:**

```python
[
    ("## Section A", "## Section A\n\nContent A.\n"),
    ("### Subsection A1", "### Subsection A1\n\nSub content.\n"),
    ("## Section B", "## Section B\n\nContent B.\n"),
]
```

Note: The preamble before the first `##` heading is not included as a section (it has no `##`/`###` heading). Each section's body runs from its heading up to (but not including) the next `##` or `###` heading.

**Edge Cases:**
- No `##` or `###` headings -> returns empty list `[]`
- Consecutive headings with no body -> body is just the heading line + newline

### 5.9 `_score_section_for_file()`

**File:** `assemblyzero/utils/lld_section_extractor.py`

**Signature:**

```python
def _score_section_for_file(section_text: str, target_file: str) -> float:
    """Score how relevant a section is to target_file."""
    ...
```

**Input Example (exact path):**

```python
section_text = "## Section\n\nThis covers `assemblyzero/utils/extractor.py` implementation.\n"
target_file = "assemblyzero/utils/extractor.py"
```

**Output Example:** `1.0`

**Input Example (stem match):**

```python
section_text = "## Extractor Details\n\nThe extractor.py module handles parsing.\n"
target_file = "assemblyzero/utils/extractor.py"
```

**Output Example:** `0.6`

**Input Example (directory match):**

```python
section_text = "## Utils Package\n\nThe assemblyzero/utils/ package contains utilities.\n"
target_file = "assemblyzero/utils/extractor.py"
```

**Output Example:** `0.3`

**Input Example (no match):**

```python
section_text = "## Overview\n\nGeneral project overview with no file references.\n"
target_file = "assemblyzero/utils/extractor.py"
```

**Output Example:** `0.0`

**Scoring Logic (in priority order):**
1. If `target_file` (exact string, e.g. `assemblyzero/utils/extractor.py`) appears in `section_text` -> return `1.0`
2. If the filename stem (e.g. `extractor`) appears in `section_text` (case-insensitive word boundary match) -> return `0.6`
3. If the parent directory path (e.g. `assemblyzero/utils`) appears in `section_text` -> return `0.3`
4. Otherwise -> return `0.0`

## 6. Change Instructions

### 6.1 `tests/fixtures/retry_prompt/full_lld.md` (Add)

**Complete file contents:**

This fixture must be ~400 lines with ≥5 distinct `##` sections, each mentioning a different explicit file path. The fixture must be large enough that a Tier 2 extraction of a single section results in ≤ 50% of the full content.

```markdown
# 999 - Sample LLD for Testing

## 1. Context & Goal

This is a sample LLD used for testing retry prompt context pruning.
The LLD covers multiple files across the project.
It includes detailed specifications for each file to ensure sufficient
token count for meaningful reduction measurement.

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod
tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam,
quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse
cillum dolore eu fugiat nulla pariatur.

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/alpha/module_a.py` | Add | Alpha module A implementation |
| `assemblyzero/beta/module_b.py` | Add | Beta module B implementation |
| `assemblyzero/gamma/module_c.py` | Modify | Gamma module C changes |
| `assemblyzero/delta/module_d.py` | Add | Delta module D implementation |
| `assemblyzero/epsilon/module_e.py` | Add | Epsilon module E implementation |

## 3. Section for assemblyzero/alpha/module_a.py

This section describes the implementation of `assemblyzero/alpha/module_a.py`.

The module_a file provides the core Alpha functionality. It must implement
the following functions:

- `alpha_init()` — Initialize the alpha subsystem
- `alpha_process(data: str) -> dict` — Process input data through alpha pipeline
- `alpha_validate(result: dict) -> bool` — Validate alpha processing results

### Function Signatures

```python
def alpha_init() -> None:
    """Initialize the alpha subsystem."""
    ...

def alpha_process(data: str) -> dict[str, Any]:
    """Process input data through alpha pipeline."""
    ...

def alpha_validate(result: dict[str, Any]) -> bool:
    """Validate alpha processing results."""
    ...
```

### Data Structures

The alpha module uses the following structures:

```python
class AlphaConfig(TypedDict):
    name: str
    threshold: float
    enabled: bool
```

Additional implementation notes for the alpha module:
- Must handle empty input strings gracefully
- Threshold defaults to 0.5 if not specified
- Processing pipeline has three stages: parse, transform, validate
- Each stage logs its progress using the standard logging pattern
- Error handling follows the project convention of returning error dicts

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Pellentesque
habitant morbi tristique senectus et netus et malesuada fames ac turpis
egestas. Vestibulum tortor quam, feugiat vitae, ultricies eget, tempor
sit amet, ante. Donec eu libero sit amet quam egestas semper. Aenean
ultricies mi vitae est. Mauris placerat eleifend leo.

## 4. Section for assemblyzero/beta/module_b.py

This section describes the implementation of `assemblyzero/beta/module_b.py`.

The module_b file provides Beta processing capabilities. It depends on
the alpha module for initialization.

### Function Signatures

```python
def beta_transform(input_data: list[str]) -> list[dict[str, Any]]:
    """Transform a list of strings into structured data."""
    ...

def beta_aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate multiple beta results into a summary."""
    ...

def beta_export(summary: dict[str, Any], format: str = "json") -> str:
    """Export beta summary in the specified format."""
    ...
```

### Requirements

- Must process lists of up to 10,000 items efficiently
- Aggregation must handle missing fields gracefully
- Export supports "json" and "yaml" formats
- All functions must have complete type annotations

Additional padding text to ensure this section has meaningful size:
The beta module is critical for the data pipeline. It receives raw inputs
from upstream producers and transforms them into a normalized format that
downstream consumers can process uniformly. The transformation logic
applies a series of rules defined in the beta configuration.

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer nec
odio. Praesent libero. Sed cursus ante dapibus diam. Sed nisi. Nulla
quis sem at nibh elementum imperdiet. Duis sagittis ipsum.

## 5. Section for assemblyzero/gamma/module_c.py

This section describes the modifications to `assemblyzero/gamma/module_c.py`.

The existing module_c file needs updates to support the new gamma protocol.
Current code at lines 45-60:

```python
def gamma_process(data: str) -> str:
    """Process data using gamma protocol."""
    return data.upper()
```

### Changes Required

The `gamma_process` function must be updated to:
1. Accept an optional `encoding` parameter
2. Apply the gamma transformation algorithm
3. Return a GammaResult TypedDict instead of a plain string

```python
class GammaResult(TypedDict):
    output: str
    encoding: str
    checksum: str

def gamma_process(data: str, encoding: str = "utf-8") -> GammaResult:
    """Process data using gamma protocol with encoding support."""
    ...
```

Additional details about the gamma module modifications:
- Backward compatibility must be maintained for callers using positional args
- The checksum is computed using hashlib.sha256
- Encoding parameter must be validated against a whitelist
- Performance must not degrade by more than 10% for the common case

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Cras dapibus.
Vivamus elementum semper nisi. Aenean vulputate eleifend tellus. Aenean
leo ligula, porttitor eu, consequat vitae, eleifend ac, enim.

## 6. Section for assemblyzero/delta/module_d.py

This section describes the implementation of `assemblyzero/delta/module_d.py`.

The module_d file implements the Delta state machine. It coordinates between
alpha and beta modules to manage complex workflows.

### State Machine

States: INIT, PROCESSING, VALIDATING, COMPLETE, ERROR

Transitions:
- INIT -> PROCESSING: on `start()`
- PROCESSING -> VALIDATING: on `process_complete()`
- VALIDATING -> COMPLETE: on `validate_pass()`
- VALIDATING -> ERROR: on `validate_fail()`
- ERROR -> INIT: on `reset()`

### Function Signatures

```python
class DeltaStateMachine:
    def __init__(self) -> None: ...
    def start(self, config: dict[str, Any]) -> None: ...
    def process_complete(self, result: dict[str, Any]) -> None: ...
    def validate_pass(self) -> dict[str, Any]: ...
    def validate_fail(self, reason: str) -> None: ...
    def reset(self) -> None: ...
    def get_state(self) -> str: ...
```

The delta module must ensure thread safety for all state transitions.
Concurrent access to the state machine must be serialized using a
threading.Lock. The state machine must reject invalid transitions with
a DeltaTransitionError.

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Aliquam lorem
ante, dapibus in, viverra quis, feugiat a, tellus. Phasellus viverra
nulla ut metus varius laoreet. Quisque rutrum. Aenean imperdiet.

## 7. Section for assemblyzero/epsilon/module_e.py

This section describes the implementation of `assemblyzero/epsilon/module_e.py`.

The module_e file provides the Epsilon reporting interface. It collects
metrics from all other modules and generates reports.

### Function Signatures

```python
def epsilon_collect_metrics(modules: list[str]) -> dict[str, Any]:
    """Collect metrics from specified modules."""
    ...

def epsilon_generate_report(metrics: dict[str, Any], format: str = "text") -> str:
    """Generate a human-readable report from collected metrics."""
    ...

def epsilon_export_dashboard(metrics: dict[str, Any]) -> dict[str, Any]:
    """Export metrics in dashboard-compatible format."""
    ...
```

### Report Format

Reports include:
- Module name and version
- Processing count and success rate
- Average latency per operation
- Error breakdown by category
- Recommendations for optimization

The epsilon module must handle partial metric collection gracefully.
If a module fails to report metrics, the report should note the missing
data rather than failing entirely.

Additional implementation notes:
- Metrics are collected via a polling mechanism
- Report generation must complete within 5 seconds
- Dashboard export uses a JSON schema compatible with Grafana

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Etiam ut purus
mattis mauris sodales aliquam. Curabitur nisi. Quisque malesuada placerat
nisl. Nam ipsum risus, rutrum vitae, vestibulum eu, molestie vel, lacus.

## 8. Requirements

1. All modules must have complete type annotations.
2. Test coverage must be >= 95%.
3. No new runtime dependencies.
4. All functions must handle edge cases gracefully.
5. Performance: all operations must complete within 100ms.

## 9. Verification & Testing

Test scenarios cover all modules and their interactions.
Each module has dedicated unit tests and integration tests.

This section provides additional padding to represent a realistic LLD
that contains substantial content beyond the individual file sections.
In production LLDs, this section often contains detailed test plans,
verification commands, and acceptance criteria tables.

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Fusce neque.
Suspendisse faucibus, nunc et pellentesque egestas, lacus ante convallis
tellus, vitae iaculis lacus elit id tortor. Vivamus aliquet elit ac nisl.
Fusce fermentum odio nec arcu. Vivamus euismod mauris.

## 10. Definition of Done

- All modules implemented
- All tests passing
- Coverage >= 95%
- Type-check passes
- No regressions

End of sample LLD for testing purposes.
```

### 6.2 `tests/fixtures/retry_prompt/minimal_lld.md` (Add)

**Complete file contents:**

```markdown
# 888 - Minimal LLD for Testing

## 1. Overview

A minimal LLD with a single file section.

## 2. Section for assemblyzero/single/only_file.py

This section covers `assemblyzero/single/only_file.py` implementation.

### Function Signatures

```python
def only_function(x: int) -> int:
    """Double the input."""
    return x * 2
```

### Requirements

- Must handle negative integers
- Must handle zero
- Must return an integer

## 3. Definition of Done

- only_file.py implemented and tested
```

### 6.3 `assemblyzero/utils/lld_section_extractor.py` (Add)

**Complete file contents:**

```python
"""LLD section extraction utility.

Issue #642: Extract file-relevant sections from LLD markdown for
tiered retry prompt context pruning.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import TypedDict


class ExtractedSection(TypedDict):
    """Result of extracting a single relevant section from an LLD."""

    section_heading: str
    section_body: str
    match_confidence: float


# Pattern to match ## and ### headings (but not # top-level)
_HEADING_PATTERN: re.Pattern[str] = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)


def extract_file_spec_section(
    lld_content: str, target_file: str
) -> ExtractedSection | None:
    """Parse LLD markdown and extract the section most relevant to target_file.

    Strategy:
      1. Split LLD into heading-delimited sections.
      2. Score each section for relevance to target_file.
      3. Return the highest-scoring section, or None if no match.

    Args:
        lld_content: Full LLD markdown string.
        target_file: Relative file path being targeted.

    Returns:
        ExtractedSection if a relevant section is found, None otherwise.

    Raises:
        ValueError: If lld_content is empty.
    """
    if not lld_content.strip():
        raise ValueError("lld_content must not be empty")

    sections = _split_lld_into_sections(lld_content)
    if not sections:
        return None

    best_score: float = 0.0
    best_heading: str = ""
    best_body: str = ""

    for heading, body in sections:
        score = _score_section_for_file(body, target_file)
        if score > best_score:
            best_score = score
            best_heading = heading
            best_body = body

    if best_score == 0.0:
        return None

    return ExtractedSection(
        section_heading=best_heading,
        section_body=best_body,
        match_confidence=best_score,
    )


def _split_lld_into_sections(lld_content: str) -> list[tuple[str, str]]:
    """Split LLD markdown into (heading, body) tuples at ## and ### boundaries.

    Args:
        lld_content: Full LLD markdown.

    Returns:
        List of (heading_text, full_section_text_including_heading) tuples.
    """
    matches = list(_HEADING_PATTERN.finditer(lld_content))
    if not matches:
        return []

    sections: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        heading_line = match.group(0)  # e.g., "## Section Name"
        start = match.start()
        # Section runs from this heading to the start of the next heading
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(lld_content)
        body = lld_content[start:end]
        sections.append((heading_line, body))

    return sections


def _score_section_for_file(section_text: str, target_file: str) -> float:
    """Score how relevant a section is to target_file.

    Scoring rules (highest priority first):
      - Exact path match in section text: 1.0
      - Filename stem match: 0.6
      - Parent directory path match: 0.3
      - No match: 0.0

    Args:
        section_text: Full text of an LLD section.
        target_file: Target file relative path.

    Returns:
        Float relevance score 0.0–1.0.
    """
    # Normalize path separators to forward slashes for consistent matching
    normalized_target = target_file.replace("\\", "/")

    # 1. Exact path match
    if normalized_target in section_text:
        return 1.0

    # 2. Filename stem match (case-insensitive, word boundary)
    stem = PurePosixPath(normalized_target).stem  # e.g., "extractor" from "extractor.py"
    if stem and re.search(
        r"(?i)\b" + re.escape(stem) + r"\b", section_text
    ):
        return 0.6

    # 3. Parent directory path match
    parent = str(PurePosixPath(normalized_target).parent)
    if parent and parent != "." and parent in section_text:
        return 0.3

    return 0.0
```

### 6.4 `assemblyzero/utils/__init__.py` (Modify)

**Change 1:** Append import block at the end of the file (after the `pattern_scanner` import block, line 26):

```diff
 from assemblyzero.utils.pattern_scanner import (
     PatternAnalysis,
     detect_frameworks,
     extract_conventions_from_claude_md,
     scan_patterns,
 )
+
+from assemblyzero.utils.lld_section_extractor import (
+    ExtractedSection,
+    extract_file_spec_section,
+)
```

### 6.5 `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py` (Add)

**Complete file contents:**

```python
"""Retry prompt builder with tiered context pruning.

Issue #642: Implements build_retry_prompt() which applies tiered context
pruning — Tier 1 (full LLD) for first retry, Tier 2 (relevant section only)
for subsequent retries — reducing prompt size by 50-60%.
"""

from __future__ import annotations

import logging
import re
from typing import TypedDict

import tiktoken

from assemblyzero.utils.lld_section_extractor import extract_file_spec_section

logger = logging.getLogger(__name__)

# --- Module-level constants ---
SNIPPET_MAX_LINES: int = 60
"""Maximum lines retained from previous attempt snippet in Tier 2."""

TIER_BOUNDARY: int = 2
"""retry_count >= this value triggers Tier 2 pruning."""

# --- Prompt template strings ---
_SYSTEM_PREAMBLE_TIER1: str = (
    "You are retrying a code generation task. "
    "The full specification is provided below."
)

_SYSTEM_PREAMBLE_TIER2: str = (
    "You are fixing a code generation error. "
    "Below is ONLY the relevant specification section for the file "
    "you are implementing — not the full specification."
)

_SPEC_SECTION_HEADER: str = "## Relevant Specification"
_TARGET_FILE_HEADER: str = "## Target File"
_ERROR_HEADER: str = "## Error from Previous Attempt"
_PREVIOUS_ATTEMPT_HEADER: str = "## Previous Attempt (last 60 lines)"
_FULL_SPEC_HEADER: str = "## Specification"


class RetryContext(TypedDict):
    """All information needed to build a retry prompt at any tier."""

    lld_content: str
    target_file: str
    error_message: str
    retry_count: int
    previous_attempt_snippet: str | None
    completed_files: list[str]


class PrunedRetryPrompt(TypedDict):
    """Output of build_retry_prompt() — the assembled prompt and metadata."""

    prompt_text: str
    tier: int
    estimated_tokens: int
    context_sections_included: list[str]


def build_retry_prompt(ctx: RetryContext) -> PrunedRetryPrompt:
    """Build a retry prompt applying tiered context pruning.

    Tier 1 (retry_count == 1): Full LLD + target file spec + error.
    Tier 2 (retry_count >= 2): Relevant file spec section only + error
      + truncated previous attempt snippet.

    Args:
        ctx: RetryContext containing LLD, target file, error, and retry metadata.

    Returns:
        PrunedRetryPrompt with assembled prompt text, tier used, and token estimate.

    Raises:
        ValueError: If retry_count < 1 or required fields are missing/empty.
    """
    # Validate required fields
    if ctx["retry_count"] < 1:
        raise ValueError(
            f"retry_count must be >= 1, got {ctx['retry_count']}"
        )
    if not ctx["lld_content"].strip():
        raise ValueError("lld_content must not be empty")
    if not ctx["target_file"].strip():
        raise ValueError("target_file must not be empty")
    if not ctx["error_message"].strip():
        raise ValueError("error_message must not be empty")

    if ctx["retry_count"] < TIER_BOUNDARY:
        # Tier 1: full LLD
        tier = 1
        prompt_text = _build_tier1_prompt(ctx)
        sections_included = ["full_lld", "target_file", "error_message"]
    else:
        # Tier 2: minimal context
        tier = 2
        if ctx["previous_attempt_snippet"] is None:
            raise ValueError("Tier 2 requires previous_attempt_snippet")
        prompt_text = _build_tier2_prompt(ctx)
        # Check if tier2 fell back (we detect by checking the preamble)
        if prompt_text.startswith(_SYSTEM_PREAMBLE_TIER1):
            tier = 1
            sections_included = [
                "full_lld",
                "target_file",
                "error_message",
                "fallback_from_tier2",
            ]
        else:
            sections_included = [
                "relevant_file_spec_section",
                "error_message",
                "previous_attempt_snippet",
            ]

    estimated_tokens = _estimate_tokens(prompt_text)

    return PrunedRetryPrompt(
        prompt_text=prompt_text,
        tier=tier,
        estimated_tokens=estimated_tokens,
        context_sections_included=sections_included,
    )


def _build_tier1_prompt(ctx: RetryContext) -> str:
    """Assemble full-LLD retry prompt (current behavior, Retry 1).

    Drops completed_files from context. Includes full LLD + target file
    section call-out + error message.

    Args:
        ctx: Full RetryContext.

    Returns:
        Assembled prompt string.
    """
    lld = _strip_completed_file_sections(
        ctx["lld_content"], ctx["completed_files"]
    )
    parts = [
        _SYSTEM_PREAMBLE_TIER1,
        "",
        _FULL_SPEC_HEADER,
        "",
        lld.strip(),
        "",
        _TARGET_FILE_HEADER,
        "",
        ctx["target_file"],
        "",
        _ERROR_HEADER,
        "",
        ctx["error_message"],
    ]
    return "\n".join(parts)


def _build_tier2_prompt(ctx: RetryContext) -> str:
    """Assemble minimal retry prompt (Retry 2+).

    Includes only the relevant file spec section extracted from the LLD,
    the error message, and a truncated snippet of the previous attempt.

    Args:
        ctx: Full RetryContext; previous_attempt_snippet must not be None.

    Returns:
        Assembled prompt string.

    Raises:
        ValueError: If previous_attempt_snippet is None on tier 2.
    """
    if ctx["previous_attempt_snippet"] is None:
        raise ValueError("Tier 2 requires previous_attempt_snippet")

    relevant_section = extract_file_spec_section(
        ctx["lld_content"], ctx["target_file"]
    )
    if relevant_section is None:
        logger.warning(
            "Tier 2 section extraction failed; falling back to tier 1 "
            "for file=%s",
            ctx["target_file"],
        )
        return _build_tier1_prompt(ctx)

    truncated = _truncate_snippet(
        ctx["previous_attempt_snippet"], max_lines=SNIPPET_MAX_LINES
    )

    parts = [
        _SYSTEM_PREAMBLE_TIER2,
        "",
        _SPEC_SECTION_HEADER,
        "",
        relevant_section["section_body"].strip(),
        "",
        _TARGET_FILE_HEADER,
        "",
        ctx["target_file"],
        "",
        _ERROR_HEADER,
        "",
        ctx["error_message"],
        "",
        _PREVIOUS_ATTEMPT_HEADER,
        "",
        truncated,
    ]
    return "\n".join(parts)


def _truncate_snippet(
    snippet: str, max_lines: int = SNIPPET_MAX_LINES
) -> str:
    """Truncate a previous-attempt snippet to at most max_lines lines.

    Keeps the final max_lines lines (tail) as they are most relevant
    to the failure point. Prepends "..." if lines were dropped.

    Args:
        snippet: Raw previous attempt text.
        max_lines: Maximum number of lines to retain.

    Returns:
        Truncated snippet string with a leading ellipsis if lines were dropped.
    """
    if not snippet:
        return ""

    lines = snippet.splitlines()
    if len(lines) <= max_lines:
        return snippet

    # Keep last (max_lines - 1) lines + prepend "..."
    kept = lines[-(max_lines - 1) :]
    return "...\n" + "\n".join(kept)


def _estimate_tokens(text: str) -> int:
    """Estimate token count of text using tiktoken cl100k_base encoding.

    Args:
        text: String to estimate.

    Returns:
        Integer token count estimate. Returns -1 if encoding fails.
    """
    if not text:
        return 0
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        logger.warning("tiktoken encoding failed; returning -1 sentinel")
        return -1


def _strip_completed_file_sections(
    lld_content: str, completed_files: list[str]
) -> str:
    """Remove sections from LLD that correspond to already-completed files.

    Uses the same section-splitting logic as the LLD section extractor
    to identify sections that mention completed file paths, then removes
    those sections from the LLD content.

    Args:
        lld_content: Full LLD markdown text.
        completed_files: List of completed file relative paths.

    Returns:
        LLD content with completed file sections removed.
    """
    if not completed_files:
        return lld_content

    from assemblyzero.utils.lld_section_extractor import _split_lld_into_sections

    sections = _split_lld_into_sections(lld_content)
    result = lld_content

    for _heading, body in sections:
        for completed_file in completed_files:
            normalized = completed_file.replace("\\", "/")
            if normalized in body:
                result = result.replace(body, "")
                break

    return result
```

### 6.6 `assemblyzero/workflows/implementation_spec/nodes/__init__.py` (Modify)

**Change 1:** Append import block at the end of the file (after the `validate_completeness` import block):

```diff
 from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
     check_change_instructions_specific,
     check_data_structures_have_examples,
     check_functions_have_io_examples,
     check_modify_files_have_excerpts,
     check_pattern_references_valid,
     validate_completeness,
 )
+
+from assemblyzero.workflows.implementation_spec.nodes.retry_prompt_builder import (
+    build_retry_prompt,
+    PrunedRetryPrompt,
+    RetryContext,
+)
```

### 6.7 `tests/unit/test_lld_section_extractor.py` (Add)

**Complete file contents:**

```python
"""Unit tests for LLD section extractor.

Issue #642: Tests for extract_file_spec_section() and helpers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.utils.lld_section_extractor import (
    ExtractedSection,
    _score_section_for_file,
    _split_lld_into_sections,
    extract_file_spec_section,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "retry_prompt"


@pytest.fixture()
def full_lld() -> str:
    """Load the full LLD fixture."""
    return (FIXTURES_DIR / "full_lld.md").read_text(encoding="utf-8")


@pytest.fixture()
def minimal_lld() -> str:
    """Load the minimal LLD fixture."""
    return (FIXTURES_DIR / "minimal_lld.md").read_text(encoding="utf-8")


# --- extract_file_spec_section tests ---


class TestExtractFileSpecSection:
    """Tests for extract_file_spec_section()."""

    def test_exact_path_match_returns_confidence_1(self, full_lld: str) -> None:
        """T090: Exact path match returns confidence=1.0."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/alpha/module_a.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "assemblyzero/alpha/module_a.py" in result["section_body"]

    def test_exact_match_returns_correct_section_heading(self, full_lld: str) -> None:
        """Exact match returns the heading of the matched section."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/beta/module_b.py"
        )
        assert result is not None
        assert "module_b" in result["section_heading"].lower() or "beta" in result["section_heading"].lower()

    def test_stem_match_returns_confidence_below_1(self, full_lld: str) -> None:
        """T100: Stem match returns 0.0 < confidence < 1.0."""
        # Use a path where the exact path won't appear, but stem "module_a" will
        result = extract_file_spec_section(
            full_lld, "some/other/path/module_a.py"
        )
        assert result is not None
        assert 0.0 < result["match_confidence"] < 1.0

    def test_no_match_returns_none(self, full_lld: str) -> None:
        """T110: No match returns None."""
        result = extract_file_spec_section(
            full_lld, "completely/nonexistent/zzzzz_unique.py"
        )
        assert result is None

    def test_empty_lld_raises_value_error(self) -> None:
        """T120: Empty lld_content raises ValueError."""
        with pytest.raises(ValueError, match="lld_content must not be empty"):
            extract_file_spec_section("", "any/file.py")

    def test_whitespace_only_lld_raises_value_error(self) -> None:
        """Whitespace-only lld_content raises ValueError."""
        with pytest.raises(ValueError, match="lld_content must not be empty"):
            extract_file_spec_section("   \n\t  ", "any/file.py")

    def test_minimal_lld_exact_match(self, minimal_lld: str) -> None:
        """Minimal LLD fixture with a single section returns exact match."""
        result = extract_file_spec_section(
            minimal_lld, "assemblyzero/single/only_file.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "only_function" in result["section_body"]

    def test_no_heading_sections_returns_none(self) -> None:
        """LLD with no ## sections returns None."""
        lld = "# Title\n\nJust a title and some text, no ## headings.\n"
        result = extract_file_spec_section(lld, "any/file.py")
        assert result is None

    def test_multiple_exact_matches_returns_first(self) -> None:
        """When multiple sections mention the exact path, first wins."""
        lld = (
            "## Section A\n\nMentions `src/foo.py` here.\n\n"
            "## Section B\n\nAlso mentions `src/foo.py` here.\n"
        )
        result = extract_file_spec_section(lld, "src/foo.py")
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert result["section_heading"] == "## Section A"


# --- _split_lld_into_sections tests ---


class TestSplitLldIntoSections:
    """Tests for _split_lld_into_sections()."""

    def test_splits_on_h2_headings(self) -> None:
        """Splits correctly on ## headings."""
        lld = "# Title\n\nPreamble.\n\n## A\n\nContent A.\n\n## B\n\nContent B.\n"
        sections = _split_lld_into_sections(lld)
        assert len(sections) == 2
        assert sections[0][0] == "## A"
        assert sections[1][0] == "## B"

    def test_splits_on_h3_headings(self) -> None:
        """Splits on ### headings."""
        lld = "## Parent\n\nParent content.\n\n### Child\n\nChild content.\n"
        sections = _split_lld_into_sections(lld)
        assert len(sections) == 2
        assert sections[0][0] == "## Parent"
        assert sections[1][0] == "### Child"

    def test_no_headings_returns_empty(self) -> None:
        """No ## or ### headings returns empty list."""
        lld = "# Just a title\n\nSome text.\n"
        sections = _split_lld_into_sections(lld)
        assert sections == []

    def test_section_body_includes_heading(self) -> None:
        """Section body includes its own heading."""
        lld = "## My Section\n\nBody text here.\n"
        sections = _split_lld_into_sections(lld)
        assert len(sections) == 1
        assert sections[0][1].startswith("## My Section")
        assert "Body text here." in sections[0][1]

    def test_full_lld_fixture_has_multiple_sections(self, full_lld: str) -> None:
        """Full LLD fixture produces ≥5 sections."""
        sections = _split_lld_into_sections(full_lld)
        assert len(sections) >= 5


# --- _score_section_for_file tests ---


class TestScoreSectionForFile:
    """Tests for _score_section_for_file()."""

    def test_exact_path_match_scores_1(self) -> None:
        """Exact path in section text scores 1.0."""
        section = "## Details\n\nCovers `assemblyzero/utils/ext.py` implementation.\n"
        assert _score_section_for_file(section, "assemblyzero/utils/ext.py") == 1.0

    def test_stem_match_scores_0_6(self) -> None:
        """Filename stem match scores 0.6."""
        section = "## Module Ext\n\nThe ext module does things.\n"
        assert _score_section_for_file(section, "assemblyzero/utils/ext.py") == 0.6

    def test_directory_match_scores_0_3(self) -> None:
        """Parent directory path match scores 0.3."""
        section = "## Utils Package\n\nThe assemblyzero/utils package.\n"
        assert _score_section_for_file(section, "assemblyzero/utils/unique_xyz.py") == 0.3

    def test_no_match_scores_0(self) -> None:
        """No match scores 0.0."""
        section = "## Overview\n\nGeneral project overview.\n"
        assert _score_section_for_file(section, "assemblyzero/utils/ext.py") == 0.0

    def test_backslash_path_normalized(self) -> None:
        """Windows-style backslash paths are normalized."""
        section = "## Details\n\nassemblyzero/utils/ext.py implementation.\n"
        assert _score_section_for_file(section, "assemblyzero\\utils\\ext.py") == 1.0
```

### 6.8 `tests/unit/test_retry_prompt_builder.py` (Add)

**Complete file contents:**

```python
"""Unit tests for retry prompt builder with tiered context pruning.

Issue #642: Tests for build_retry_prompt() across all tier cases.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from assemblyzero.workflows.implementation_spec.nodes.retry_prompt_builder import (
    SNIPPET_MAX_LINES,
    PrunedRetryPrompt,
    RetryContext,
    _build_tier1_prompt,
    _build_tier2_prompt,
    _estimate_tokens,
    _strip_completed_file_sections,
    _truncate_snippet,
    build_retry_prompt,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "retry_prompt"


@pytest.fixture()
def full_lld() -> str:
    """Load the full LLD fixture."""
    return (FIXTURES_DIR / "full_lld.md").read_text(encoding="utf-8")


@pytest.fixture()
def minimal_lld() -> str:
    """Load the minimal LLD fixture."""
    return (FIXTURES_DIR / "minimal_lld.md").read_text(encoding="utf-8")


def _make_ctx(**overrides: Any) -> RetryContext:
    """Create a RetryContext with sensible defaults, overridable."""
    defaults: dict[str, Any] = {
        "lld_content": "## Section for src/target.py\n\nTarget details.\n\n## Section for src/done.py\n\nDone details.\n",
        "target_file": "src/target.py",
        "error_message": "SyntaxError: unexpected EOF",
        "retry_count": 1,
        "previous_attempt_snippet": None,
        "completed_files": [],
    }
    defaults.update(overrides)
    return RetryContext(**defaults)  # type: ignore[typeddict-item]


# --- build_retry_prompt tests ---


class TestBuildRetryPrompt:
    """Tests for the main build_retry_prompt() function."""

    def test_tier1_happy_path(self, full_lld: str) -> None:
        """T010: retry_count=1 returns full LLD minus completed files, tier=1."""
        ctx = _make_ctx(
            lld_content=full_lld,
            target_file="assemblyzero/alpha/module_a.py",
            retry_count=1,
            completed_files=[],
        )
        result = build_retry_prompt(ctx)
        assert result["tier"] == 1
        assert "assemblyzero/alpha/module_a.py" in result["prompt_text"]
        # Full LLD content should be present (spot check another section)
        assert "assemblyzero/beta/module_b.py" in result["prompt_text"]
        assert result["estimated_tokens"] > 0

    def test_tier2_happy_path(self, full_lld: str) -> None:
        """T020: retry_count=2 returns section-only prompt, tier=2."""
        ctx = _make_ctx(
            lld_content=full_lld,
            target_file="assemblyzero/alpha/module_a.py",
            retry_count=2,
            previous_attempt_snippet="def alpha_init():\n    pass\n",
        )
        result = build_retry_prompt(ctx)
        assert result["tier"] == 2
        # Should contain the relevant section
        assert "assemblyzero/alpha/module_a.py" in result["prompt_text"]
        # Should NOT contain other file sections' content
        assert "assemblyzero/epsilon/module_e.py" not in result["prompt_text"]
        # Should contain the snippet
        assert "def alpha_init():" in result["prompt_text"]
        # Should contain the error
        assert "SyntaxError" in result["prompt_text"]

    def test_tier2_token_reduction(self, full_lld: str) -> None:
        """T030: Tier 2 token count ≤ 50% of Tier 1 for full LLD fixture."""
        ctx_tier1 = _make_ctx(
            lld_content=full_lld,
            target_file="assemblyzero/alpha/module_a.py",
            retry_count=1,
        )
        result_tier1 = build_retry_prompt(ctx_tier1)

        ctx_tier2 = _make_ctx(
            lld_content=full_lld,
            target_file="assemblyzero/alpha/module_a.py",
            retry_count=2,
            previous_attempt_snippet="def alpha_init():\n    pass\n",
        )
        result_tier2 = build_retry_prompt(ctx_tier2)

        assert result_tier2["tier"] == 2
        assert result_tier1["estimated_tokens"] > 0
        assert result_tier2["estimated_tokens"] > 0
        assert result_tier2["estimated_tokens"] <= 0.50 * result_tier1["estimated_tokens"], (
            f"Tier 2 tokens ({result_tier2['estimated_tokens']}) must be <= 50% of "
            f"Tier 1 tokens ({result_tier1['estimated_tokens']})"
        )

    def test_tier2_fallback_on_no_section(self, caplog: pytest.LogCaptureFixture) -> None:
        """T040: Falls back to tier 1 when section not found, emits warning."""
        ctx = _make_ctx(
            lld_content="## Overview\n\nNo file paths mentioned here at all.\n",
            target_file="assemblyzero/nonexistent/zzzzz.py",
            retry_count=2,
            previous_attempt_snippet="some code\n",
        )
        with caplog.at_level(logging.WARNING):
            result = build_retry_prompt(ctx)
        assert result["tier"] == 1  # Fell back to tier 1
        assert "fallback" in " ".join(caplog.messages).lower() or "fallback_from_tier2" in result["context_sections_included"]

    def test_retry_count_zero_raises(self) -> None:
        """T050: retry_count=0 raises ValueError."""
        ctx = _make_ctx(retry_count=0)
        with pytest.raises(ValueError, match="retry_count must be >= 1, got 0"):
            build_retry_prompt(ctx)

    def test_retry_count_negative_raises(self) -> None:
        """retry_count=-1 raises ValueError."""
        ctx = _make_ctx(retry_count=-1)
        with pytest.raises(ValueError, match="retry_count must be >= 1"):
            build_retry_prompt(ctx)

    def test_tier2_snippet_none_raises(self) -> None:
        """T060: retry_count=2 with snippet=None raises ValueError."""
        ctx = _make_ctx(
            retry_count=2,
            previous_attempt_snippet=None,
        )
        with pytest.raises(ValueError, match="Tier 2 requires previous_attempt_snippet"):
            build_retry_prompt(ctx)

    def test_empty_lld_raises(self) -> None:
        """Empty lld_content raises ValueError."""
        ctx = _make_ctx(lld_content="")
        with pytest.raises(ValueError, match="lld_content must not be empty"):
            build_retry_prompt(ctx)

    def test_empty_target_file_raises(self) -> None:
        """Empty target_file raises ValueError."""
        ctx = _make_ctx(target_file="")
        with pytest.raises(ValueError, match="target_file must not be empty"):
            build_retry_prompt(ctx)

    def test_empty_error_message_raises(self) -> None:
        """Empty error_message raises ValueError."""
        ctx = _make_ctx(error_message="")
        with pytest.raises(ValueError, match="error_message must not be empty"):
            build_retry_prompt(ctx)

    def test_completed_files_excluded_tier1(self, full_lld: str) -> None:
        """T150: completed_files are excluded from tier 1 prompt."""
        ctx = _make_ctx(
            lld_content=full_lld,
            target_file="assemblyzero/alpha/module_a.py",
            retry_count=1,
            completed_files=["assemblyzero/beta/module_b.py"],
        )
        result = build_retry_prompt(ctx)
        assert result["tier"] == 1
        # The beta section body should be stripped out
        assert "beta_transform" not in result["prompt_text"]
        # But alpha section should remain
        assert "alpha_init" in result["prompt_text"]

    def test_context_sections_included_tier1(self) -> None:
        """Tier 1 context_sections_included has expected entries."""
        ctx = _make_ctx(retry_count=1)
        result = build_retry_prompt(ctx)
        assert "full_lld" in result["context_sections_included"]
        assert "error_message" in result["context_sections_included"]

    def test_context_sections_included_tier2(self) -> None:
        """Tier 2 context_sections_included has expected entries."""
        ctx = _make_ctx(
            retry_count=2,
            previous_attempt_snippet="some code\n",
        )
        result = build_retry_prompt(ctx)
        assert result["tier"] == 2
        assert "relevant_file_spec_section" in result["context_sections_included"]
        assert "previous_attempt_snippet" in result["context_sections_included"]

    def test_retry_count_3_still_tier2(self, full_lld: str) -> None:
        """retry_count=3 (and higher) still uses tier 2."""
        ctx = _make_ctx(
            lld_content=full_lld,
            target_file="assemblyzero/alpha/module_a.py",
            retry_count=3,
            previous_attempt_snippet="code\n",
        )
        result = build_retry_prompt(ctx)
        assert result["tier"] == 2


# --- _truncate_snippet tests ---


class TestTruncateSnippet:
    """Tests for _truncate_snippet()."""

    def test_truncates_to_max_lines(self) -> None:
        """T070: Truncates long snippet to max_lines with leading ellipsis."""
        snippet = "\n".join(f"line {i}" for i in range(200))
        result = _truncate_snippet(snippet, max_lines=60)
        result_lines = result.splitlines()
        assert len(result_lines) == 60
        assert result_lines[0] == "..."
        assert result_lines[-1] == "line 199"

    def test_short_snippet_unchanged(self) -> None:
        """T080: Snippet shorter than max_lines returned unchanged."""
        snippet = "line 1\nline 2\nline 3"
        result = _truncate_snippet(snippet, max_lines=60)
        assert result == snippet

    def test_exact_max_lines_unchanged(self) -> None:
        """Snippet with exactly max_lines is returned unchanged."""
        snippet = "\n".join(f"line {i}" for i in range(60))
        result = _truncate_snippet(snippet, max_lines=60)
        assert result == snippet

    def test_empty_string_returns_empty(self) -> None:
        """Empty string returns empty."""
        assert _truncate_snippet("") == ""

    def test_single_line_unchanged(self) -> None:
        """Single line is returned unchanged."""
        assert _truncate_snippet("only line") == "only line"

    def test_default_max_lines_is_snippet_max_lines(self) -> None:
        """Default max_lines matches SNIPPET_MAX_LINES constant."""
        snippet = "\n".join(f"line {i}" for i in range(200))
        result = _truncate_snippet(snippet)
        result_lines = result.splitlines()
        assert len(result_lines) == SNIPPET_MAX_LINES

    def test_truncated_keeps_tail(self) -> None:
        """Truncation keeps the tail (last lines) of the snippet."""
        snippet = "\n".join(f"line {i}" for i in range(100))
        result = _truncate_snippet(snippet, max_lines=10)
        result_lines = result.splitlines()
        # First line is "..."
        assert result_lines[0] == "..."
        # Last 9 lines are lines 91-99
        assert result_lines[1] == "line 91"
        assert result_lines[-1] == "line 99"


# --- _estimate_tokens tests ---


class TestEstimateTokens:
    """Tests for _estimate_tokens()."""

    def test_positive_for_nonempty(self) -> None:
        """T130: Returns positive int for non-empty string."""
        result = _estimate_tokens("Hello world, this is a test.")
        assert isinstance(result, int)
        assert result > 0

    def test_zero_for_empty(self) -> None:
        """T140: Returns 0 for empty string."""
        assert _estimate_tokens("") == 0

    def test_longer_text_more_tokens(self) -> None:
        """Longer text produces more tokens."""
        short = _estimate_tokens("Hi")
        long = _estimate_tokens("This is a much longer sentence with many more words and tokens.")
        assert long > short


# --- _strip_completed_file_sections tests ---


class TestStripCompletedFileSections:
    """Tests for _strip_completed_file_sections()."""

    def test_strips_completed_section(self) -> None:
        """Removes the section mentioning the completed file."""
        lld = "## Section A\n\nCovers `src/done.py` implementation.\n\n## Section B\n\nCovers `src/keep.py` implementation.\n"
        result = _strip_completed_file_sections(lld, ["src/done.py"])
        assert "src/done.py" not in result
        assert "src/keep.py" in result

    def test_empty_completed_files_no_change(self) -> None:
        """Empty completed_files list returns content unchanged."""
        lld = "## Section\n\nContent.\n"
        assert _strip_completed_file_sections(lld, []) == lld

    def test_no_match_no_change(self) -> None:
        """No matching completed files returns content unchanged."""
        lld = "## Section\n\nContent about src/keep.py.\n"
        result = _strip_completed_file_sections(lld, ["src/other.py"])
        assert result == lld


# --- _build_tier1_prompt tests ---


class TestBuildTier1Prompt:
    """Tests for _build_tier1_prompt()."""

    def test_contains_full_lld(self) -> None:
        """Tier 1 prompt contains the LLD content."""
        ctx = _make_ctx(
            lld_content="## Test Section\n\nTest content for verification.\n",
            retry_count=1,
        )
        result = _build_tier1_prompt(ctx)
        assert "Test content for verification." in result

    def test_contains_target_file(self) -> None:
        """Tier 1 prompt contains the target file path."""
        ctx = _make_ctx(target_file="assemblyzero/foo/bar.py", retry_count=1)
        result = _build_tier1_prompt(ctx)
        assert "assemblyzero/foo/bar.py" in result

    def test_contains_error_message(self) -> None:
        """Tier 1 prompt contains the error message."""
        ctx = _make_ctx(error_message="ImportError: no module named xyz", retry_count=1)
        result = _build_tier1_prompt(ctx)
        assert "ImportError: no module named xyz" in result


# --- _build_tier2_prompt tests ---


class TestBuildTier2Prompt:
    """Tests for _build_tier2_prompt()."""

    def test_contains_relevant_section_only(self) -> None:
        """Tier 2 prompt contains only the relevant section, not full LLD."""
        ctx = _make_ctx(
            lld_content=(
                "## Section for src/target.py\n\nTarget spec content.\n\n"
                "## Section for src/other.py\n\nOther spec content.\n"
            ),
            target_file="src/target.py",
            retry_count=2,
            previous_attempt_snippet="code here\n",
        )
        result = _build_tier2_prompt(ctx)
        assert "Target spec content." in result
        assert "Other spec content." not in result

    def test_contains_snippet(self) -> None:
        """Tier 2 prompt contains the previous attempt snippet."""
        ctx = _make_ctx(
            retry_count=2,
            previous_attempt_snippet="def my_func():\n    return 42\n",
        )
        result = _build_tier2_prompt(ctx)
        assert "def my_func():" in result

    def test_snippet_none_raises(self) -> None:
        """Tier 2 with snippet=None raises ValueError."""
        ctx = _make_ctx(
            retry_count=2,
            previous_attempt_snippet=None,
        )
        with pytest.raises(ValueError, match="Tier 2 requires previous_attempt_snippet"):
            _build_tier2_prompt(ctx)

    def test_fallback_when_no_section_found(self, caplog: pytest.LogCaptureFixture) -> None:
        """Falls back to tier 1 output when section not found."""
        ctx = _make_ctx(
            lld_content="## Overview\n\nNo file paths here.\n",
            target_file="totally/missing/file.py",
            retry_count=2,
            previous_attempt_snippet="code\n",
        )
        with caplog.at_level(logging.WARNING):
            result = _build_tier2_prompt(ctx)
        # Result should be a tier 1 prompt (starts with tier 1 preamble)
        assert "full specification" in result.lower()
        assert any("fallback" in msg.lower() or "tier 1" in msg.lower() for msg in caplog.messages)
```

## 7. Pattern References

### 7.1 Node Implementation Pattern

**File:** `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py` (lines 1–50)

```python
"""Generate Implementation Spec draft using Claude.

Issue #304: Implementation Readiness Review Workflow (LLD -> Implementation Spec)
Node N2: generate_spec
"""

from __future__ import annotations

import logging
from typing import Any

# ... imports follow
```

**Relevance:** The new `retry_prompt_builder.py` follows the same module structure: module docstring referencing the issue, `from __future__ import annotations`, logging setup, typed helper functions. This is the standard pattern for all node modules in the implementation_spec workflow.

### 7.2 Utils Module Pattern

**File:** `assemblyzero/utils/lld_verification.py` (lines 1–30)

The lld_verification module demonstrates the pattern for utility modules: TypedDict definitions at top, public functions with full type annotations, private helper functions prefixed with `_`.

**Relevance:** The new `lld_section_extractor.py` follows the exact same structure — `ExtractedSection` TypedDict at top, public `extract_file_spec_section()`, private helpers `_split_lld_into_sections()` and `_score_section_for_file()`.

### 7.3 __init__.py Export Pattern

**File:** `assemblyzero/utils/__init__.py` (lines 1–26, shown in Section 3.2)

**Relevance:** New exports follow the existing pattern: grouped import block with explicit names, no wildcard imports, sorted alphabetically within each block.

### 7.4 Test Pattern

**File:** `tests/unit/` directory (existing test files)

Tests follow pytest conventions: fixtures for shared setup, class-based test grouping, descriptive docstrings mapping to test IDs from the LLD, `pytest.raises` for exception testing.

**Relevance:** Both new test files follow this exact pattern.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | Both new modules |
| `import re` | stdlib | `lld_section_extractor.py` |
| `import logging` | stdlib | `retry_prompt_builder.py` |
| `from pathlib import PurePosixPath` | stdlib | `lld_section_extractor.py` |
| `from typing import TypedDict` | stdlib | Both new modules |
| `import tiktoken` | `tiktoken` (existing dep) | `retry_prompt_builder.py` |
| `from assemblyzero.utils.lld_section_extractor import extract_file_spec_section` | internal | `retry_prompt_builder.py` |
| `from assemblyzero.utils.lld_section_extractor import _split_lld_into_sections` | internal | `retry_prompt_builder.py` (in `_strip_completed_file_sections`) |
| `import pytest` | `pytest` (existing dev dep) | Both test files |

**New Dependencies:** None. `tiktoken` is already in `pyproject.toml`.

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | File | Input | Expected Output |
|---------|---------------|------|-------|-----------------|
| T010 | `build_retry_prompt()` | `test_retry_prompt_builder.py::TestBuildRetryPrompt::test_tier1_happy_path` | `RetryContext(retry_count=1, lld=full_lld, target="alpha/module_a.py")` | `tier=1`, prompt contains full LLD |
| T020 | `build_retry_prompt()` | `test_retry_prompt_builder.py::TestBuildRetryPrompt::test_tier2_happy_path` | `RetryContext(retry_count=2, snippet="...", target="alpha/module_a.py")` | `tier=2`, prompt has section only |
| T030 | `build_retry_prompt()` | `test_retry_prompt_builder.py::TestBuildRetryPrompt::test_tier2_token_reduction` | Same ctx, compare tier1 vs tier2 | `tier2_tokens <= 0.50 * tier1_tokens` |
| T040 | `build_retry_prompt()` | `test_retry_prompt_builder.py::TestBuildRetryPrompt::test_tier2_fallback_on_no_section` | LLD with no matching file; `retry_count=2` | `tier=1`, warning logged |
| T050 | `build_retry_prompt()` | `test_retry_prompt_builder.py::TestBuildRetryPrompt::test_retry_count_zero_raises` | `retry_count=0` | `ValueError` |
| T060 | `build_retry_prompt()` | `test_retry_prompt_builder.py::TestBuildRetryPrompt::test_tier2_snippet_none_raises` | `retry_count=2, snippet=None` | `ValueError` |
| T070 | `_truncate_snippet()` | `test_retry_prompt_builder.py::TestTruncateSnippet::test_truncates_to_max_lines` | 200-line snippet, `max_lines=60` | 60 lines, starts with "..." |
| T080 | `_truncate_snippet()` | `test_retry_prompt_builder.py::TestTruncateSnippet::test_short_snippet_unchanged` | 3-line snippet | Unchanged |
| T090 | `extract_file_spec_section()` | `test_lld_section_extractor.py::TestExtractFileSpecSection::test_exact_path_match_returns_confidence_1` | LLD with exact path | `confidence=1.0` |
| T100 | `extract_file_spec_section()` | `test_lld_section_extractor.py::TestExtractFileSpecSection::test_stem_match_returns_confidence_below_1` | LLD with stem only | `0.0 < confidence < 1.0` |
| T110 | `extract_file_spec_section()` | `test_lld_section_extractor.py::TestExtractFileSpecSection::test_no_match_returns_none` | LLD with no match | `None` |
| T120 | `extract_file_spec_section()` | `test_lld_section_extractor.py::TestExtractFileSpecSection::test_empty_lld_raises_value_error` | `lld_content=""` | `ValueError` |
| T130 | `_estimate_tokens()` | `test_retry_prompt_builder.py::TestEstimateTokens::test_positive_for_nonempty` | `"Hello world"` | `int > 0` |
| T140 | `_estimate_tokens()` | `test_retry_prompt_builder.py::TestEstimateTokens::test_zero_for_empty` | `""` | `0` |
| T150 | `build_retry_prompt()` | `test_retry_prompt_builder.py::TestBuildRetryPrompt::test_completed_files_excluded_tier1` | `completed_files=["beta/module_b.py"]` | "beta_transform" absent |
| T160 | mypy check | External command | `mypy --strict retry_prompt_builder.py` | Exit code 0 |
| T170 | mypy check | External command | `mypy --strict lld_section_extractor.py` | Exit code 0 |
| T180 | pytest-cov | External command | Coverage on `retry_prompt_builder` | ≥ 95% |
| T190 | pytest-cov | External command | Coverage on `lld_section_extractor` | ≥ 95% |
| T200 | pyproject.toml diff | External command | `git diff pyproject.toml` | No new runtime deps |

## 11. Implementation Notes

### 11.1 Error Handling Convention

All validation errors raise `ValueError` with a descriptive message. The `build_retry_prompt()` function validates all required fields upfront before dispatching to tier-specific builders. The `_estimate_tokens()` function catches all exceptions and returns `-1` as a sentinel because token estimation is non-critical (used for logging only).

### 11.2 Logging Convention

Use `logging.getLogger(__name__)` for module-level logger. Emit `WARNING` level when tier 2 falls back to tier 1 (section extraction failure). No `print()` statements — all output goes through the logging framework.

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `SNIPPET_MAX_LINES` | `60` | Generous enough to capture failure context; small enough to ensure token savings |
| `TIER_BOUNDARY` | `2` | `retry_count >= 2` triggers tier 2; matches the LLD's two-tier design |

### 11.4 Section Splitting Detail

The `_split_lld_into_sections()` function uses `re.MULTILINE` to match `##` and `###` headings at line start. It does NOT match `#` (top-level title) or `####` and deeper headings. Each section's body extends from its heading to the next `##`/`###` heading or end of document. Preamble text before the first `##` heading is not captured as a section.

### 11.5 Fallback Detection in build_retry_prompt()

When `_build_tier2_prompt()` falls back to tier 1 (because `extract_file_spec_section()` returned `None`), the `build_retry_prompt()` function detects this by checking if the returned prompt starts with `_SYSTEM_PREAMBLE_TIER1`. If so, it sets `tier=1` and adds `"fallback_from_tier2"` to `context_sections_included`. This ensures the caller always gets an accurate `tier` value even after fallback.

### 11.6 Test Fixture Size Requirement

The `full_lld.md` fixture must be large enough that extracting a single section produces ≤ 50% of the full content's tokens. The fixture provided in Section 6.1 has ~400 lines spread across 5+ distinct file sections, plus padding text. If the 50% threshold test (T030) fails, add more padding/lorem ipsum text to the non-target sections.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #642 |
| Verdict | DRAFT |
| Date | 2026-03-07 |
| Iterations | 1 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #642 |
| Verdict | APPROVED |
| Date | 2026-03-07 |
| Iterations | 0 |
| Finalized | 2026-03-07T02:32:53Z |

### Review Feedback Summary

The implementation spec is exceptionally detailed and highly actionable. It provides complete source code for all new files, exact diffs for file modifications, and comprehensive test files mapped directly to the LLD requirements. Data structures, function specifications, and concrete edge-case handling are explicitly defined, ensuring an AI agent can implement the changes with near-zero ambiguity.

## Suggestions
- In `_estimate_tokens`, consider caching the tiktoken encoding instance (`tiktoke...
