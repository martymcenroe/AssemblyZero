# Implementation Spec: Fix: Reduce Retry Prompt Context More Aggressively

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #642 |
| LLD | `docs/lld/active/642-reduce-retry-prompt-context.md` |
| Generated | 2026-03-07 |
| Status | DRAFT |

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
| 7 | `tests/unit/test_lld_section_extractor.py` | Add | Unit tests for section extraction |
| 8 | `tests/unit/test_retry_prompt_builder.py` | Add | Unit tests for retry prompt builder |

**Implementation Order Rationale:** Fixtures first (needed by tests), then the utility module (no internal deps), then the main module (depends on utility), then exports, then tests last (depend on everything).

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/workflows/implementation_spec/nodes/__init__.py`

**Relevant excerpt** (full file):

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

**What changes:** Add import block for `build_retry_prompt` from the new `retry_prompt_builder` module, appended after the last existing import block.

### 3.2 `assemblyzero/utils/__init__.py`

**Relevant excerpt** (full file):

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

**What changes:** Add import block for `extract_file_spec_section` and `ExtractedSection` from the new `lld_section_extractor` module, appended after the last existing import block.

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
    "lld_content": "# 642 - Fix: Reduce Retry Prompt Context\n\n## 2. Proposed Changes\n\n### 2.1 Files Changed\n\n| File | Change Type | Description |\n|------|-------------|-------------|\n| `assemblyzero/utils/lld_section_extractor.py` | Add | Utility module |\n| `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py` | Add | Core retry logic |\n\n## 3. Requirements\n\n1. Tier 1 must match current behavior...\n\n## Section for assemblyzero/utils/lld_section_extractor.py\n\nThis file implements `extract_file_spec_section()` which parses LLD markdown...\n\n## Section for assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py\n\nThis file implements `build_retry_prompt()` with tiered pruning...",
    "target_file": "assemblyzero/utils/lld_section_extractor.py",
    "error_message": "SyntaxError: unexpected indent at line 42 in lld_section_extractor.py",
    "retry_count": 2,
    "previous_attempt_snippet": "def extract_file_spec_section(lld_content: str, target_file: str) -> ExtractedSection | None:\n    sections = _split_lld_into_sections(lld_content)\n    scored = []\n    for heading, body in sections:\n        score = _score_section_for_file(body, target_file)\n         scored.append((score, heading, body))\n    if not scored:\n        return None\n    best = max(scored, key=lambda x: x[0])\n    if best[0] == 0.0:\n        return None\n    return ExtractedSection(\n        section_heading=best[1],\n        section_body=best[2],\n        match_confidence=best[0],\n    )",
    "completed_files": ["assemblyzero/utils/__init__.py", "tests/fixtures/retry_prompt/full_lld.md"]
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
    "prompt_text": "You are retrying the implementation of a file that failed in a previous attempt.\n\nRelevant specification section:\n\n## Section for assemblyzero/utils/lld_section_extractor.py\n\nThis file implements `extract_file_spec_section()` which parses LLD markdown...\n\nTarget file: assemblyzero/utils/lld_section_extractor.py\n\nError from previous attempt:\nSyntaxError: unexpected indent at line 42 in lld_section_extractor.py\n\nPrevious attempt (last 60 lines):\ndef extract_file_spec_section(lld_content: str, target_file: str) -> ExtractedSection | None:\n    sections = _split_lld_into_sections(lld_content)\n    ...",
    "tier": 2,
    "estimated_tokens": 487,
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
    "section_heading": "## Section for assemblyzero/utils/lld_section_extractor.py",
    "section_body": "## Section for assemblyzero/utils/lld_section_extractor.py\n\nThis file implements `extract_file_spec_section()` which parses LLD markdown and returns only the section(s) relevant to a target file.\n\n### Function Signatures\n\n```python\ndef extract_file_spec_section(lld_content: str, target_file: str) -> ExtractedSection | None:\n    ...\n```",
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
    lld_content="# 642 - Fix\n\n## 2. Proposed Changes\n\n### File: assemblyzero/utils/lld_section_extractor.py\n\nImplement extraction logic.\n\n### File: assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py\n\nImplement build_retry_prompt.\n",
    target_file="assemblyzero/utils/lld_section_extractor.py",
    error_message="IndentationError: unexpected indent at line 15",
    retry_count=2,
    previous_attempt_snippet="def extract_file_spec_section(lld_content: str) -> None:\n    pass\n",
    completed_files=["assemblyzero/utils/__init__.py"],
)
```

**Output Example (Tier 2):**

```python
{
    "prompt_text": "You are retrying the implementation of a file...\n\nRelevant specification section:\n\n### File: assemblyzero/utils/lld_section_extractor.py\n\nImplement extraction logic.\n\nTarget file: assemblyzero/utils/lld_section_extractor.py\n\nError from previous attempt:\nIndentationError: unexpected indent at line 15\n\nPrevious attempt (last 60 lines):\ndef extract_file_spec_section(lld_content: str) -> None:\n    pass\n",
    "tier": 2,
    "estimated_tokens": 127,
    "context_sections_included": ["relevant_file_spec_section", "error_message", "previous_attempt_snippet"],
}
```

**Output Example (Tier 1, retry_count=1):**

```python
{
    "prompt_text": "You are retrying the implementation of a file...\n\n## 2. Proposed Changes\n\n### File: assemblyzero/utils/lld_section_extractor.py\n\nImplement extraction logic.\n\n### File: assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py\n\nImplement build_retry_prompt.\n\nTarget file: assemblyzero/utils/lld_section_extractor.py\n\nError from previous attempt:\nIndentationError: unexpected indent at line 15\n",
    "tier": 1,
    "estimated_tokens": 203,
    "context_sections_included": ["full_lld", "error_message"],
}
```

**Edge Cases:**
- `retry_count=0` -> raises `ValueError("retry_count must be >= 1, got 0")`
- `retry_count < 0` -> raises `ValueError("retry_count must be >= 1, got -1")`
- `lld_content=""` -> raises `ValueError("lld_content must not be empty")`
- `target_file=""` -> raises `ValueError("target_file must not be empty")`
- `error_message=""` -> raises `ValueError("error_message must not be empty")`
- `retry_count=2` and `previous_attempt_snippet=None` -> raises `ValueError("Tier 2 requires previous_attempt_snippet")`
- `retry_count=2` and section extraction returns None -> falls back to tier 1, logs warning, returns `tier=1`

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
    lld_content="# 642\n\n## Section A\n\nContent about file_a.py\n\n## Section B\n\nContent about file_b.py\n",
    target_file="assemblyzero/utils/lld_section_extractor.py",
    error_message="NameError: name 'foo' is not defined",
    retry_count=1,
    previous_attempt_snippet=None,
    completed_files=["file_a.py"],
)
```

**Output Example:**

```python
"You are retrying the implementation of a file that failed in a previous attempt. Below is the full specification context.\n\n# 642\n\n## Section B\n\nContent about file_b.py\n\nTarget file: assemblyzero/utils/lld_section_extractor.py\n\nError from previous attempt:\nNameError: name 'foo' is not defined"
```

**Edge Cases:**
- `completed_files` is empty -> full LLD returned as-is (no stripping)
- `completed_files` contains all sections -> only non-section LLD preamble remains

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
    lld_content="# 642\n\n## Section for target.py\n\nTarget details here.\n\n## Section for other.py\n\nOther details.\n",
    target_file="target.py",
    error_message="TypeError: expected str",
    retry_count=2,
    previous_attempt_snippet="def foo():\n    return 42\n",
    completed_files=[],
)
```

**Output Example:**

```python
"You are retrying the implementation of a file that failed in a previous attempt. Below is only the relevant specification section for the target file.\n\nRelevant specification section:\n\n## Section for target.py\n\nTarget details here.\n\nTarget file: target.py\n\nError from previous attempt:\nTypeError: expected str\n\nPrevious attempt (last 60 lines):\ndef foo():\n    return 42\n"
```

**Edge Cases:**
- `previous_attempt_snippet=None` -> raises `ValueError("Tier 2 requires previous_attempt_snippet")`
- Section extraction returns None -> calls `_build_tier1_prompt(ctx)` and logs warning

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
snippet = "\n".join(f"line {i}" for i in range(200))  # 200 lines
max_lines = 60
```

**Output Example (truncation needed):**

```python
"...\nline 140\nline 141\nline 142\n...line 199"  # last 60 lines, prefixed with "..."
```

**Input Example (no truncation):**

```python
snippet = "line 1\nline 2\nline 3"
max_lines = 60
```

**Output Example (no truncation):**

```python
"line 1\nline 2\nline 3"  # unchanged
```

**Edge Cases:**
- Empty string -> returns empty string
- Exactly `max_lines` lines -> returns unchanged
- `max_lines=0` -> returns `"..."`

### 5.5 `_estimate_tokens()`

**File:** `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py`

**Signature:**

```python
def _estimate_tokens(text: str) -> int:
    """Estimate token count of text using tiktoken cl100k_base encoding."""
    ...
```

**Input Example:**

```python
text = "Hello, world! This is a test string."
```

**Output Example:**

```python
9  # approximate, depends on encoding
```

**Edge Cases:**
- Empty string -> returns `0`
- tiktoken encoding fails -> returns `-1` (wrapped in try/except)

### 5.6 `extract_file_spec_section()`

**File:** `assemblyzero/utils/lld_section_extractor.py`

**Signature:**

```python
def extract_file_spec_section(lld_content: str, target_file: str) -> ExtractedSection | None:
    """Parse LLD markdown and extract the section most relevant to target_file."""
    ...
```

**Input Example (exact match):**

```python
lld_content = "# My LLD\n\n## Overview\n\nGeneral info.\n\n## File: assemblyzero/utils/lld_section_extractor.py\n\nThis module does extraction.\n\n## File: assemblyzero/nodes/builder.py\n\nThis module builds prompts.\n"
target_file = "assemblyzero/utils/lld_section_extractor.py"
```

**Output Example (exact match):**

```python
{
    "section_heading": "## File: assemblyzero/utils/lld_section_extractor.py",
    "section_body": "## File: assemblyzero/utils/lld_section_extractor.py\n\nThis module does extraction.\n",
    "match_confidence": 1.0,
}
```

**Input Example (stem match):**

```python
lld_content = "# My LLD\n\n## Overview\n\n## Extraction Module\n\nThe lld_section_extractor handles parsing.\n\n## Builder Module\n\nThe builder handles prompts.\n"
target_file = "assemblyzero/utils/lld_section_extractor.py"
```

**Output Example (stem match):**

```python
{
    "section_heading": "## Extraction Module",
    "section_body": "## Extraction Module\n\nThe lld_section_extractor handles parsing.\n",
    "match_confidence": 0.6,
}
```

**Input Example (no match):**

```python
lld_content = "# My LLD\n\n## Overview\n\nGeneral info.\n\n## Other Topic\n\nNothing relevant.\n"
target_file = "assemblyzero/utils/lld_section_extractor.py"
```

**Output Example (no match):**

```python
None
```

**Edge Cases:**
- `lld_content=""` -> raises `ValueError("lld_content must not be empty")`
- `target_file=""` -> returns `None` (no file to match against)
- LLD with no `##` headings -> returns `None` (no sections to split)

### 5.7 `_split_lld_into_sections()`

**File:** `assemblyzero/utils/lld_section_extractor.py`

**Signature:**

```python
def _split_lld_into_sections(lld_content: str) -> list[tuple[str, str]]:
    """Split LLD markdown into (heading, body) tuples at ## and ### boundaries."""
    ...
```

**Input Example:**

```python
lld_content = "# Title\n\nPreamble.\n\n## Section One\n\nBody one.\n\n### Subsection\n\nSub body.\n\n## Section Two\n\nBody two.\n"
```

**Output Example:**

```python
[
    ("## Section One", "## Section One\n\nBody one.\n\n### Subsection\n\nSub body.\n"),
    ("### Subsection", "### Subsection\n\nSub body.\n"),
    ("## Section Two", "## Section Two\n\nBody two.\n"),
]
```

**Edge Cases:**
- No `##` or `###` headings -> returns empty list
- Consecutive headings with no body -> each gets just heading + empty body

### 5.8 `_score_section_for_file()`

**File:** `assemblyzero/utils/lld_section_extractor.py`

**Signature:**

```python
def _score_section_for_file(section_text: str, target_file: str) -> float:
    """Score how relevant a section is to target_file."""
    ...
```

**Input Example (exact path):**

```python
section_text = "## File: assemblyzero/utils/lld_section_extractor.py\n\nDetails here."
target_file = "assemblyzero/utils/lld_section_extractor.py"
```

**Output Example:** `1.0`

**Input Example (stem match):**

```python
section_text = "## Extraction Module\n\nThe lld_section_extractor handles parsing."
target_file = "assemblyzero/utils/lld_section_extractor.py"
```

**Output Example:** `0.6`

**Input Example (directory match):**

```python
section_text = "## Utils Overview\n\nThe assemblyzero/utils/ package contains utilities."
target_file = "assemblyzero/utils/lld_section_extractor.py"
```

**Output Example:** `0.3`

**Input Example (no match):**

```python
section_text = "## Overview\n\nGeneral project description."
target_file = "assemblyzero/utils/lld_section_extractor.py"
```

**Output Example:** `0.0`

## 6. Change Instructions

### 6.1 `tests/fixtures/retry_prompt/full_lld.md` (Add)

**Complete file contents:**

```markdown
# 999 - Sample Full LLD for Testing

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

1. Alpha service must handle concurrent requests.
2. Beta service must validate all inputs.
3. Gamma model must support new field types.
4. Delta helper must be pure functions only.
5. Epsilon flow must integrate with existing workflow graph.

## Section for assemblyzero/services/alpha_service.py

This section describes the Alpha service implementation in detail.

The Alpha service handles concurrent request processing with a thread pool.
It exposes a `process()` method that accepts a request dict and returns
a response dict. Error handling follows the standard pattern: return an
`error_message` field in the response.

### Function Signatures

```python
def process(request: dict[str, Any]) -> dict[str, Any]:
    """Process a single request."""
    ...

def validate_request(request: dict[str, Any]) -> bool:
    """Validate request structure."""
    ...
```

### Data Structures

The request format:
```json
{
    "action": "compute",
    "payload": {"x": 1, "y": 2},
    "timeout_ms": 5000
}
```

Additional implementation notes for Alpha service that add to the section length.
The service should use connection pooling and implement retry logic with
exponential backoff for downstream calls.

Performance requirements: p99 latency < 200ms, throughput > 1000 req/s.

## Section for assemblyzero/services/beta_service.py

This section describes the Beta service implementation.

Beta service provides input validation and transformation. It integrates
with the Alpha service for downstream processing. All inputs must be
validated against a JSON schema before forwarding.

### Function Signatures

```python
def validate_and_forward(input_data: dict) -> dict:
    """Validate input and forward to Alpha service."""
    ...

def get_schema(version: str) -> dict:
    """Load validation schema for given version."""
    ...
```

### Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `MAX_PAYLOAD_SIZE` | `1_048_576` | 1MB limit |
| `SCHEMA_CACHE_TTL` | `3600` | 1 hour cache |

## Section for assemblyzero/models/gamma_model.py

This section describes the Gamma model modifications.

The existing Gamma model needs to be extended with two new fields:
`metadata` (dict) and `tags` (list[str]). The migration strategy
is additive — no existing fields are removed or renamed.

### Current State

```python
class GammaModel(TypedDict):
    id: str
    name: str
    value: float
```

### Proposed Changes

Add metadata and tags fields with defaults.

```python
class GammaModel(TypedDict):
    id: str
    name: str
    value: float
    metadata: dict[str, Any]
    tags: list[str]
```

## Section for assemblyzero/utils/delta_helper.py

This section describes the Delta helper utility.

Delta helper provides pure utility functions for string manipulation
and data transformation used across multiple services.

### Function Signatures

```python
def normalize_key(key: str) -> str:
    """Normalize a dictionary key to snake_case."""
    ...

def merge_configs(base: dict, override: dict) -> dict:
    """Deep merge two configuration dictionaries."""
    ...
```

## Section for assemblyzero/workflows/epsilon_flow.py

This section describes the Epsilon workflow node.

Epsilon flow integrates with the existing LangGraph workflow as a new
processing node. It receives state from upstream nodes and produces
transformed state for downstream consumption.

### Function Signatures

```python
async def epsilon_node(state: EpsilonState) -> dict[str, Any]:
    """Process state in the Epsilon workflow node."""
    ...
```

### Integration Points

- Receives from: Delta helper (data transformation)
- Sends to: Finalization node (output assembly)

## 4. Alternatives Considered

Several alternatives were evaluated including monolithic processing,
microservice decomposition, and event-driven architecture. The current
approach balances simplicity with maintainability.

## 5. Security Considerations

All services must validate inputs. No PII is stored. API keys are
managed through the existing keyring integration.

## Padding Section Alpha

This section exists solely to increase the token count of this fixture
to simulate a realistic large LLD document. Real LLDs contain extensive
discussion of architecture decisions, code examples, data flow diagrams,
and detailed implementation notes that contribute to their substantial size.

The architecture follows a layered approach with clear separation of concerns.
Each layer communicates through well-defined interfaces. Error propagation
follows the standard pattern established in the codebase.

Additional context about deployment considerations, monitoring setup,
and operational runbooks that would appear in a comprehensive LLD document.

## Padding Section Beta

Further content to ensure the fixture is large enough to demonstrate
meaningful token reduction when tier 2 pruning is applied. This includes
discussion of edge cases, performance benchmarks, and integration testing
strategies.

The testing strategy employs a combination of unit tests, integration tests,
and end-to-end tests. Each layer has specific coverage requirements.
Mocking strategies follow the existing patterns in the test suite.

Load testing results show the system handles 10x expected traffic with
acceptable latency. Memory usage remains stable under sustained load.
CPU utilization peaks at 60% during maximum throughput testing.

## Padding Section Gamma

Even more content representing detailed technical discussion that would
appear in a real LLD. This covers database schema changes, API versioning
strategy, backward compatibility considerations, and rollback procedures.

Database migrations are managed through Alembic. Each migration is
reversible. Schema changes are tested against production data snapshots
before deployment.

API versioning follows semantic versioning principles. Breaking changes
require a major version bump. Deprecation notices are issued at least
two minor versions before removal.

## Padding Section Delta

Additional padding to reach a realistic token count. This section
discusses monitoring and observability, including metric collection,
alerting thresholds, and dashboard configurations.

Metrics are collected via Prometheus. Key metrics include request latency
(p50, p95, p99), error rate, throughput, and resource utilization.
Alerts fire when error rate exceeds 1% or p99 latency exceeds 500ms.

Dashboards are organized by service. Each dashboard shows real-time
metrics, historical trends, and SLO compliance. On-call engineers
have access to debugging dashboards with detailed request traces.

## Padding Section Epsilon

Final padding section to ensure sufficient document length. This covers
team coordination, code review guidelines, and deployment procedures.

Code reviews require at least one approval from a team member familiar
with the affected subsystem. Reviews focus on correctness, performance,
security, and adherence to coding standards.

Deployments follow a canary release pattern. Changes are first deployed
to a small percentage of traffic. If metrics remain healthy after a
30-minute bake period, the deployment proceeds to full rollout.
Automated rollback triggers if error rate exceeds the baseline by 2x.
```

### 6.2 `tests/fixtures/retry_prompt/minimal_lld.md` (Add)

**Complete file contents:**

```markdown
# 888 - Minimal LLD Fixture

## 1. Context

A minimal LLD with only one file section.

## Section for assemblyzero/utils/tiny_helper.py

This is the only file-specific section in this minimal LLD.

### Function Signatures

```python
def helper_func(x: int) -> int:
    """Double the input."""
    return x * 2
```

### Implementation Notes

Keep it simple. Pure function, no side effects.
```

### 6.3 `assemblyzero/utils/lld_section_extractor.py` (Add)

**Complete file contents:**

```python
"""LLD section extraction utility.

Issue #642: Fix: Reduce Retry Prompt Context More Aggressively

Parses LLD markdown and extracts the section(s) most relevant to a
given target file path. Used by the retry prompt builder to provide
focused context on tier 2 retries.
"""

from __future__ import annotations

import logging
import re
from pathlib import PurePosixPath
from typing import TypedDict

logger = logging.getLogger(__name__)


class ExtractedSection(TypedDict):
    """Result of extracting a single relevant section from an LLD."""

    section_heading: str
    section_body: str
    match_confidence: float


def extract_file_spec_section(
    lld_content: str, target_file: str
) -> ExtractedSection | None:
    """Parse LLD markdown and extract the section most relevant to target_file.

    Strategy:
      1. Split LLD into heading-delimited sections.
      2. Search each section for explicit mention of target_file (exact path match).
      3. If found, return that section with confidence=1.0.
      4. Fallback: search for the filename stem (without path) in section text;
         return best match with confidence < 1.0.
      5. If nothing matches, return None.

    Args:
        lld_content: Full LLD markdown string.
        target_file: Relative file path being targeted (e.g.,
            "assemblyzero/utils/lld_section_extractor.py").

    Returns:
        ExtractedSection if a relevant section is found, None otherwise.

    Raises:
        ValueError: If lld_content is empty.
    """
    if not lld_content or not lld_content.strip():
        raise ValueError("lld_content must not be empty")

    if not target_file or not target_file.strip():
        return None

    sections = _split_lld_into_sections(lld_content)
    if not sections:
        return None

    scored: list[tuple[float, str, str]] = []
    for heading, body in sections:
        score = _score_section_for_file(body, target_file)
        scored.append((score, heading, body))

    best = max(scored, key=lambda x: x[0])
    if best[0] == 0.0:
        return None

    return ExtractedSection(
        section_heading=best[1],
        section_body=best[2],
        match_confidence=best[0],
    )


def _split_lld_into_sections(
    lld_content: str,
) -> list[tuple[str, str]]:
    """Split LLD markdown into (heading, body) tuples at ## and ### boundaries.

    Args:
        lld_content: Full LLD markdown.

    Returns:
        List of (heading_text, full_section_text_including_heading) tuples.
        The heading_text is just the heading line; the full_section_text
        includes the heading and all content until the next heading of
        equal or higher level.
    """
    # Match lines starting with ## or ### (but not #### or deeper)
    heading_pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)

    matches = list(heading_pattern.finditer(lld_content))
    if not matches:
        return []

    sections: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        heading_line = match.group(0).strip()
        start = match.start()
        # Section extends to the start of the next heading match, or end of doc
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(lld_content)

        section_body = lld_content[start:end].rstrip() + "\n"
        sections.append((heading_line, section_body))

    return sections


def _score_section_for_file(section_text: str, target_file: str) -> float:
    """Score how relevant a section is to target_file.

    Scoring rules:
      - Exact path match in section text: 1.0
      - Filename stem match (basename without extension): 0.6
      - Directory name match (parent directory path): 0.3
      - No match: 0.0

    Args:
        section_text: Full text of an LLD section.
        target_file: Target file relative path.

    Returns:
        Float relevance score 0.0–1.0.
    """
    # Normalize path separators for consistent matching
    normalized_target = target_file.replace("\\", "/")

    # Exact path match (highest confidence)
    if normalized_target in section_text:
        return 1.0

    # Filename stem match (e.g., "lld_section_extractor" for
    # "assemblyzero/utils/lld_section_extractor.py")
    path = PurePosixPath(normalized_target)
    stem = path.stem  # filename without extension
    if stem and stem in section_text:
        return 0.6

    # Directory name match (e.g., "assemblyzero/utils" or just "utils")
    parent = str(path.parent)
    if parent and parent != "." and parent in section_text:
        return 0.3

    return 0.0
```

### 6.4 `assemblyzero/utils/__init__.py` (Modify)

**Change 1:** Add import block at end of file (after the `pattern_scanner` import block):

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

Issue #642: Fix: Reduce Retry Prompt Context More Aggressively

Implements build_retry_prompt() which applies tiered context pruning:
- Tier 1 (retry_count == 1): Full LLD minus completed files + error
- Tier 2 (retry_count >= 2): Relevant file spec section only + error
  + truncated previous attempt snippet

This reduces retry prompt size by 50-60% on retry 2+, cutting per-retry
API spend by $0.05-0.10.
"""

from __future__ import annotations

import logging
import re
from typing import TypedDict

import tiktoken

from assemblyzero.utils.lld_section_extractor import extract_file_spec_section

logger = logging.getLogger(__name__)

# Module-level constants
SNIPPET_MAX_LINES: int = 60
"""Maximum lines retained from previous attempt snippet (tail)."""

TIER_BOUNDARY: int = 2
"""retry_count >= this value triggers Tier 2 pruning."""

# Prompt template strings
_SYSTEM_PREAMBLE_TIER1: str = (
    "You are retrying the implementation of a file that failed in a previous "
    "attempt. Below is the full specification context."
)

_SYSTEM_PREAMBLE_TIER2: str = (
    "You are retrying the implementation of a file that failed in a previous "
    "attempt. Below is only the relevant specification section for the target file."
)

_SPEC_SECTION_HEADER: str = "\nRelevant specification section:\n"
_TARGET_FILE_HEADER: str = "\nTarget file: "
_ERROR_HEADER: str = "\n\nError from previous attempt:\n"
_PREVIOUS_ATTEMPT_HEADER: str = "\n\nPrevious attempt (last {max_lines} lines):\n"


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
    if not ctx["lld_content"] or not ctx["lld_content"].strip():
        raise ValueError("lld_content must not be empty")
    if not ctx["target_file"] or not ctx["target_file"].strip():
        raise ValueError("target_file must not be empty")
    if not ctx["error_message"] or not ctx["error_message"].strip():
        raise ValueError("error_message must not be empty")

    if ctx["retry_count"] < TIER_BOUNDARY:
        # Tier 1: full LLD
        tier = 1
        prompt_text = _build_tier1_prompt(ctx)
        sections_included = ["full_lld", "error_message"]
    else:
        # Tier 2: minimal context
        # Validate snippet requirement for tier 2
        if ctx["previous_attempt_snippet"] is None:
            raise ValueError("Tier 2 requires previous_attempt_snippet")

        prompt_text = _build_tier2_prompt(ctx)

        # Check if tier2 fell back to tier1 (indicated by preamble)
        if prompt_text.startswith(_SYSTEM_PREAMBLE_TIER1):
            tier = 1
            sections_included = ["full_lld", "error_message"]
        else:
            tier = 2
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
        "\n\n",
        lld,
        _TARGET_FILE_HEADER,
        ctx["target_file"],
        _ERROR_HEADER,
        ctx["error_message"],
    ]
    return "".join(parts)


def _build_tier2_prompt(ctx: RetryContext) -> str:
    """Assemble minimal retry prompt (Retry 2+).

    Includes only the relevant file spec section extracted from the LLD,
    the error message, and a truncated snippet of the previous attempt.

    Falls back to tier 1 if section extraction fails.

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

    attempt_header = _PREVIOUS_ATTEMPT_HEADER.format(
        max_lines=SNIPPET_MAX_LINES
    )

    parts = [
        _SYSTEM_PREAMBLE_TIER2,
        _SPEC_SECTION_HEADER,
        relevant_section["section_body"],
        _TARGET_FILE_HEADER,
        ctx["target_file"],
        _ERROR_HEADER,
        ctx["error_message"],
        attempt_header,
        truncated,
    ]
    return "".join(parts)


def _strip_completed_file_sections(
    lld_content: str, completed_files: list[str]
) -> str:
    """Remove sections from LLD that correspond to already-completed files.

    Uses a simple approach: for each completed file, find sections that
    mention the file path and remove them. If no sections are identified,
    the LLD is returned unchanged.

    Args:
        lld_content: Full LLD markdown text.
        completed_files: List of relative paths of completed files.

    Returns:
        LLD markdown with completed-file sections removed.
    """
    if not completed_files:
        return lld_content

    result = lld_content
    # Split into sections, remove those matching completed files, reassemble
    heading_pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
    matches = list(heading_pattern.finditer(lld_content))

    if not matches:
        return lld_content

    # Build list of (start, end) ranges for sections to remove
    ranges_to_remove: list[tuple[int, int]] = []
    for i, match in enumerate(matches):
        start = match.start()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(lld_content)

        section_text = lld_content[start:end]
        for completed_file in completed_files:
            normalized = completed_file.replace("\\", "/")
            if normalized in section_text:
                ranges_to_remove.append((start, end))
                break

    if not ranges_to_remove:
        return lld_content

    # Build result by including only non-removed ranges
    parts: list[str] = []
    prev_end = 0
    for rm_start, rm_end in sorted(ranges_to_remove):
        parts.append(lld_content[prev_end:rm_start])
        prev_end = rm_end
    parts.append(lld_content[prev_end:])

    result = "".join(parts)
    # Clean up excessive blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result


def _truncate_snippet(
    snippet: str, max_lines: int = SNIPPET_MAX_LINES
) -> str:
    """Truncate a previous-attempt snippet to at most max_lines lines.

    Keeps the final max_lines lines (tail) as they are most relevant
    to the failure point.

    Args:
        snippet: Raw previous attempt text.
        max_lines: Maximum number of lines to retain (default: SNIPPET_MAX_LINES).

    Returns:
        Truncated snippet string with a leading ellipsis if lines were dropped.
    """
    if not snippet:
        return snippet

    lines = snippet.splitlines()

    if len(lines) <= max_lines:
        return snippet

    if max_lines == 0:
        return "..."

    tail = lines[-max_lines:]
    return "...\n" + "\n".join(tail)


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
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        logger.warning("tiktoken encoding failed; returning -1")
        return -1
```

### 6.6 `assemblyzero/workflows/implementation_spec/nodes/__init__.py` (Modify)

**Change 1:** Add import block at end of file (after the `validate_completeness` import block):

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

Issue #642: Fix: Reduce Retry Prompt Context More Aggressively
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

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "retry_prompt"


@pytest.fixture()
def full_lld() -> str:
    """Load the full LLD fixture."""
    return (FIXTURES_DIR / "full_lld.md").read_text(encoding="utf-8")


@pytest.fixture()
def minimal_lld() -> str:
    """Load the minimal LLD fixture."""
    return (FIXTURES_DIR / "minimal_lld.md").read_text(encoding="utf-8")


class TestExtractFileSpecSection:
    """Tests for extract_file_spec_section() — T090, T100, T110, T120."""

    def test_exact_path_match_returns_confidence_1(self, full_lld: str) -> None:
        """T090: Exact path match returns confidence=1.0."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/services/alpha_service.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "alpha_service" in result["section_body"].lower()
        assert "assemblyzero/services/alpha_service.py" in result["section_body"]

    def test_exact_path_match_correct_section_heading(self, full_lld: str) -> None:
        """T090 extended: Correct heading returned for exact match."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/services/beta_service.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "beta_service" in result["section_heading"].lower() or \
               "beta_service" in result["section_body"].lower()

    def test_stem_match_returns_confidence_below_1(self) -> None:
        """T100: Stem match returns 0 < confidence < 1.0."""
        lld = (
            "# Test LLD\n\n"
            "## Module Overview\n\n"
            "The foobar_processor handles data.\n\n"
            "## Other Section\n\n"
            "Unrelated content.\n"
        )
        result = extract_file_spec_section(
            lld, "assemblyzero/utils/foobar_processor.py"
        )
        assert result is not None
        assert 0.0 < result["match_confidence"] < 1.0

    def test_no_match_returns_none(self) -> None:
        """T110: No match returns None."""
        lld = (
            "# Test LLD\n\n"
            "## Overview\n\n"
            "General content with no file references.\n\n"
            "## Architecture\n\n"
            "More general content.\n"
        )
        result = extract_file_spec_section(
            lld, "assemblyzero/nonexistent/module.py"
        )
        assert result is None

    def test_empty_lld_raises_valueerror(self) -> None:
        """T120: Empty lld_content raises ValueError."""
        with pytest.raises(ValueError, match="lld_content must not be empty"):
            extract_file_spec_section("", "assemblyzero/utils/foo.py")

    def test_whitespace_only_lld_raises_valueerror(self) -> None:
        """T120 extended: Whitespace-only lld_content raises ValueError."""
        with pytest.raises(ValueError, match="lld_content must not be empty"):
            extract_file_spec_section("   \n\t  ", "assemblyzero/utils/foo.py")

    def test_empty_target_file_returns_none(self) -> None:
        """Edge case: Empty target_file returns None."""
        result = extract_file_spec_section("# LLD\n\n## Section\n\nContent.\n", "")
        assert result is None

    def test_minimal_lld_exact_match(self, minimal_lld: str) -> None:
        """Minimal LLD with single section matches correctly."""
        result = extract_file_spec_section(
            minimal_lld, "assemblyzero/utils/tiny_helper.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "tiny_helper" in result["section_body"]

    def test_no_headings_returns_none(self) -> None:
        """LLD with no ## headings returns None."""
        lld = "# Title\n\nJust a title and paragraph. No subsections.\n"
        result = extract_file_spec_section(lld, "some/file.py")
        assert result is None


class TestSplitLldIntoSections:
    """Tests for _split_lld_into_sections()."""

    def test_basic_split(self) -> None:
        """Splits on ## headings correctly."""
        lld = "# Title\n\nPreamble.\n\n## Section One\n\nBody one.\n\n## Section Two\n\nBody two.\n"
        sections = _split_lld_into_sections(lld)
        assert len(sections) == 2
        assert sections[0][0] == "## Section One"
        assert "Body one." in sections[0][1]
        assert sections[1][0] == "## Section Two"
        assert "Body two." in sections[1][1]

    def test_includes_subsections(self) -> None:
        """### subsections are also captured."""
        lld = "# Title\n\n## Main\n\nBody.\n\n### Sub\n\nSub body.\n"
        sections = _split_lld_into_sections(lld)
        assert len(sections) == 2
        headings = [s[0] for s in sections]
        assert "## Main" in headings
        assert "### Sub" in headings

    def test_no_headings_returns_empty(self) -> None:
        """No ## or ### headings returns empty list."""
        lld = "# Only a top-level heading\n\nParagraph.\n"
        sections = _split_lld_into_sections(lld)
        assert sections == []

    def test_consecutive_headings(self) -> None:
        """Consecutive headings with no body are handled."""
        lld = "## H1\n## H2\n\nBody.\n"
        sections = _split_lld_into_sections(lld)
        assert len(sections) == 2
        assert sections[0][0] == "## H1"
        assert sections[1][0] == "## H2"


class TestScoreSectionForFile:
    """Tests for _score_section_for_file()."""

    def test_exact_path_match(self) -> None:
        """Exact path in section text scores 1.0."""
        section = "## File: assemblyzero/utils/foo.py\n\nDetails.\n"
        assert _score_section_for_file(section, "assemblyzero/utils/foo.py") == 1.0

    def test_stem_match(self) -> None:
        """Filename stem match scores 0.6."""
        section = "## Module\n\nThe foo_processor handles data.\n"
        assert _score_section_for_file(section, "assemblyzero/utils/foo_processor.py") == 0.6

    def test_directory_match(self) -> None:
        """Directory path match scores 0.3."""
        section = "## Utils Overview\n\nThe assemblyzero/utils/ package.\n"
        assert _score_section_for_file(section, "assemblyzero/utils/newfile.py") == 0.3

    def test_no_match(self) -> None:
        """No match scores 0.0."""
        section = "## Overview\n\nGeneral content.\n"
        assert _score_section_for_file(section, "assemblyzero/utils/foo.py") == 0.0

    def test_backslash_normalization(self) -> None:
        """Windows-style paths are normalized."""
        section = "## File\n\nContains assemblyzero/utils/foo.py\n"
        assert _score_section_for_file(section, "assemblyzero\\utils\\foo.py") == 1.0
```

### 6.8 `tests/unit/test_retry_prompt_builder.py` (Add)

**Complete file contents:**

```python
"""Unit tests for retry prompt builder.

Issue #642: Fix: Reduce Retry Prompt Context More Aggressively
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from assemblyzero.workflows.implementation_spec.nodes.retry_prompt_builder import (
    SNIPPET_MAX_LINES,
    PrunedRetryPrompt,
    RetryContext,
    _build_tier1_prompt,
    _build_tier2_prompt,
    _estimate_tokens,
    _truncate_snippet,
    build_retry_prompt,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "retry_prompt"


@pytest.fixture()
def full_lld() -> str:
    """Load the full LLD fixture."""
    return (FIXTURES_DIR / "full_lld.md").read_text(encoding="utf-8")


@pytest.fixture()
def minimal_lld() -> str:
    """Load the minimal LLD fixture."""
    return (FIXTURES_DIR / "minimal_lld.md").read_text(encoding="utf-8")


def _make_ctx(
    lld_content: str = "# LLD\n\n## Section for target.py\n\nTarget content.\n",
    target_file: str = "target.py",
    error_message: str = "SyntaxError: invalid syntax",
    retry_count: int = 1,
    previous_attempt_snippet: str | None = None,
    completed_files: list[str] | None = None,
) -> RetryContext:
    """Helper to create a RetryContext with defaults."""
    return RetryContext(
        lld_content=lld_content,
        target_file=target_file,
        error_message=error_message,
        retry_count=retry_count,
        previous_attempt_snippet=previous_attempt_snippet,
        completed_files=completed_files or [],
    )


class TestBuildRetryPromptTier1:
    """Tests for build_retry_prompt() tier 1 behavior — T010, T150."""

    def test_tier1_returns_full_lld(self, full_lld: str) -> None:
        """T010: retry_count=1 returns full LLD minus completed files."""
        ctx = _make_ctx(
            lld_content=full_lld,
            target_file="assemblyzero/services/alpha_service.py",
            retry_count=1,
        )
        result = build_retry_prompt(ctx)
        assert result["tier"] == 1
        # Full LLD content is present (spot check a section that is NOT the target)
        assert "beta_service" in result["prompt_text"].lower()
        assert "gamma_model" in result["prompt_text"].lower()
        assert result["estimated_tokens"] > 0

    def test_tier1_excludes_completed_files(self, full_lld: str) -> None:
        """T150: Completed files are excluded from tier 1 prompt."""
        ctx = _make_ctx(
            lld_content=full_lld,
            target_file="assemblyzero/services/alpha_service.py",
            retry_count=1,
            completed_files=["assemblyzero/services/beta_service.py"],
        )
        result = build_retry_prompt(ctx)
        assert result["tier"] == 1
        # The section specifically about beta_service should be removed
        # But alpha_service content should remain
        assert "assemblyzero/services/alpha_service.py" in result["prompt_text"]
        # beta_service.py path should not appear in a section heading/body
        # (it may appear in the files table, which is harder to strip,
        # so we check that the dedicated section body is gone)
        assert "Beta service provides input validation" not in result["prompt_text"]

    def test_tier1_contains_error_message(self) -> None:
        """T010 extended: Error message appears in prompt."""
        ctx = _make_ctx(retry_count=1, error_message="NameError: x not defined")
        result = build_retry_prompt(ctx)
        assert "NameError: x not defined" in result["prompt_text"]

    def test_tier1_contains_target_file(self) -> None:
        """T010 extended: Target file appears in prompt."""
        ctx = _make_ctx(retry_count=1, target_file="my/file.py")
        result = build_retry_prompt(ctx)
        assert "my/file.py" in result["prompt_text"]

    def test_tier1_context_sections_included(self) -> None:
        """T010 extended: context_sections_included lists full_lld."""
        ctx = _make_ctx(retry_count=1)
        result = build_retry_prompt(ctx)
        assert "full_lld" in result["context_sections_included"]
        assert "error_message" in result["context_sections_included"]


class TestBuildRetryPromptTier2:
    """Tests for build_retry_prompt() tier 2 behavior — T020, T030."""

    def test_tier2_returns_section_only(self, full_lld: str) -> None:
        """T020: retry_count=2 returns section-only prompt."""
        ctx = _make_ctx(
            lld_content=full_lld,
            target_file="assemblyzero/services/alpha_service.py",
            retry_count=2,
            previous_attempt_snippet="def process():\n    pass\n",
        )
        result = build_retry_prompt(ctx)
        assert result["tier"] == 2
        # Should contain the alpha_service section
        assert "Alpha service" in result["prompt_text"]
        # Should NOT contain other sections' distinctive content
        assert "Padding Section Gamma" not in result["prompt_text"]
        assert "Epsilon workflow" not in result["prompt_text"]
        # Should contain error and snippet
        assert "SyntaxError" in result["prompt_text"]
        assert "def process():" in result["prompt_text"]

    def test_tier2_token_reduction_at_least_50_percent(self, full_lld: str) -> None:
        """T030: Tier 2 token count ≤50% of tier 1 for same context."""
        base_ctx = _make_ctx(
            lld_content=full_lld,
            target_file="assemblyzero/services/alpha_service.py",
            error_message="SyntaxError: invalid syntax at line 10",
            previous_attempt_snippet="def process():\n    pass\n",
        )
        # Build tier 1
        tier1_ctx = {**base_ctx, "retry_count": 1}
        tier1_result = build_retry_prompt(RetryContext(**tier1_ctx))  # type: ignore[arg-type]

        # Build tier 2
        tier2_ctx = {**base_ctx, "retry_count": 2}
        tier2_result = build_retry_prompt(RetryContext(**tier2_ctx))  # type: ignore[arg-type]

        assert tier1_result["tier"] == 1
        assert tier2_result["tier"] == 2
        assert tier1_result["estimated_tokens"] > 0
        assert tier2_result["estimated_tokens"] > 0
        ratio = tier2_result["estimated_tokens"] / tier1_result["estimated_tokens"]
        assert ratio <= 0.50, (
            f"Tier 2 tokens ({tier2_result['estimated_tokens']}) is "
            f"{ratio:.1%} of tier 1 ({tier1_result['estimated_tokens']}); "
            f"expected ≤50%"
        )

    def test_tier2_context_sections_included(self, full_lld: str) -> None:
        """T020 extended: context_sections_included lists section + error + snippet."""
        ctx = _make_ctx(
            lld_content=full_lld,
            target_file="assemblyzero/services/alpha_service.py",
            retry_count=2,
            previous_attempt_snippet="code\n",
        )
        result = build_retry_prompt(ctx)
        assert "relevant_file_spec_section" in result["context_sections_included"]
        assert "error_message" in result["context_sections_included"]
        assert "previous_attempt_snippet" in result["context_sections_included"]

    def test_tier2_retry_count_3_also_works(self, full_lld: str) -> None:
        """T020 extended: retry_count=3 also triggers tier 2."""
        ctx = _make_ctx(
            lld_content=full_lld,
            target_file="assemblyzero/services/alpha_service.py",
            retry_count=3,
            previous_attempt_snippet="code\n",
        )
        result = build_retry_prompt(ctx)
        assert result["tier"] == 2


class TestBuildRetryPromptFallback:
    """Tests for tier 2 fallback behavior — T040."""

    def test_fallback_when_section_not_found(self) -> None:
        """T040: Falls back to tier 1 when section extraction returns None."""
        lld = "# LLD\n\n## Overview\n\nNo file-specific content here.\n\n## Design\n\nGeneral design.\n"
        ctx = _make_ctx(
            lld_content=lld,
            target_file="assemblyzero/completely/unrelated/file.py",
            retry_count=2,
            previous_attempt_snippet="some code\n",
        )
        result = build_retry_prompt(ctx)
        # Should fall back to tier 1
        assert result["tier"] == 1
        # Full LLD should be in prompt
        assert "General design" in result["prompt_text"]

    def test_fallback_emits_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """T040: Fallback emits a warning log."""
        lld = "# LLD\n\n## Overview\n\nGeneral content.\n"
        ctx = _make_ctx(
            lld_content=lld,
            target_file="assemblyzero/nonexistent.py",
            retry_count=2,
            previous_attempt_snippet="code\n",
        )
        with caplog.at_level(logging.WARNING):
            result = build_retry_prompt(ctx)
        assert result["tier"] == 1
        assert "falling back to tier 1" in caplog.text.lower()


class TestBuildRetryPromptValidation:
    """Tests for input validation — T050, T060."""

    def test_retry_count_zero_raises_valueerror(self) -> None:
        """T050: retry_count=0 raises ValueError."""
        ctx = _make_ctx(retry_count=0)
        with pytest.raises(ValueError, match="retry_count must be >= 1"):
            build_retry_prompt(ctx)

    def test_retry_count_negative_raises_valueerror(self) -> None:
        """T050 extended: retry_count=-1 raises ValueError."""
        ctx = _make_ctx(retry_count=-1)
        with pytest.raises(ValueError, match="retry_count must be >= 1"):
            build_retry_prompt(ctx)

    def test_empty_lld_raises_valueerror(self) -> None:
        """Validation: empty lld_content raises ValueError."""
        ctx = _make_ctx(lld_content="")
        with pytest.raises(ValueError, match="lld_content must not be empty"):
            build_retry_prompt(ctx)

    def test_empty_target_file_raises_valueerror(self) -> None:
        """Validation: empty target_file raises ValueError."""
        ctx = _make_ctx(target_file="")
        with pytest.raises(ValueError, match="target_file must not be empty"):
            build_retry_prompt(ctx)

    def test_empty_error_message_raises_valueerror(self) -> None:
        """Validation: empty error_message raises ValueError."""
        ctx = _make_ctx(error_message="")
        with pytest.raises(ValueError, match="error_message must not be empty"):
            build_retry_prompt(ctx)

    def test_tier2_snippet_none_raises_valueerror(self) -> None:
        """T060: retry_count=2 with snippet=None raises ValueError."""
        ctx = _make_ctx(retry_count=2, previous_attempt_snippet=None)
        with pytest.raises(ValueError, match="Tier 2 requires previous_attempt_snippet"):
            build_retry_prompt(ctx)


class TestTruncateSnippet:
    """Tests for _truncate_snippet() — T070, T080."""

    def test_truncates_to_max_lines(self) -> None:
        """T070: Snippet longer than max_lines is truncated to tail."""
        snippet = "\n".join(f"line {i}" for i in range(200))
        result = _truncate_snippet(snippet, max_lines=60)
        lines = result.splitlines()
        # Should be max_lines + 1 (the "..." line)
        assert len(lines) <= 61  # 60 content lines + "..."
        assert lines[0] == "..."
        assert "line 199" in result
        assert "line 140" in result

    def test_short_snippet_unchanged(self) -> None:
        """T080: Snippet shorter than max_lines returned unchanged."""
        snippet = "line 1\nline 2\nline 3"
        result = _truncate_snippet(snippet, max_lines=60)
        assert result == snippet

    def test_exact_max_lines_unchanged(self) -> None:
        """T080 extended: Snippet of exactly max_lines returned unchanged."""
        snippet = "\n".join(f"line {i}" for i in range(60))
        result = _truncate_snippet(snippet, max_lines=60)
        assert result == snippet

    def test_empty_snippet(self) -> None:
        """Edge case: empty snippet returns empty string."""
        assert _truncate_snippet("") == ""

    def test_max_lines_zero(self) -> None:
        """Edge case: max_lines=0 returns just ellipsis."""
        result = _truncate_snippet("line 1\nline 2", max_lines=0)
        assert result == "..."

    def test_default_max_lines_is_snippet_max_lines(self) -> None:
        """Default max_lines matches module constant."""
        snippet = "\n".join(f"line {i}" for i in range(200))
        result = _truncate_snippet(snippet)
        lines = result.splitlines()
        # "..." + SNIPPET_MAX_LINES content lines
        assert len(lines) == SNIPPET_MAX_LINES + 1


class TestEstimateTokens:
    """Tests for _estimate_tokens() — T130, T140."""

    def test_positive_for_nonempty_string(self) -> None:
        """T130: Non-empty string returns positive int."""
        result = _estimate_tokens("Hello, world! This is a test.")
        assert isinstance(result, int)
        assert result > 0

    def test_zero_for_empty_string(self) -> None:
        """T140: Empty string returns 0."""
        assert _estimate_tokens("") == 0

    def test_returns_int(self) -> None:
        """Token count is always an integer."""
        result = _estimate_tokens("The quick brown fox jumps over the lazy dog.")
        assert isinstance(result, int)

    def test_longer_text_more_tokens(self) -> None:
        """Longer text produces more tokens."""
        short = _estimate_tokens("hello")
        long = _estimate_tokens("hello " * 100)
        assert long > short

    def test_encoding_failure_returns_negative_one(self) -> None:
        """tiktoken failure returns -1."""
        with patch("assemblyzero.workflows.implementation_spec.nodes.retry_prompt_builder.tiktoken") as mock_tiktoken:
            mock_tiktoken.get_encoding.side_effect = RuntimeError("encoding failed")
            result = _estimate_tokens("test text")
            assert result == -1


class TestBuildTier1Prompt:
    """Tests for _build_tier1_prompt() directly."""

    def test_includes_full_lld(self) -> None:
        """Tier 1 includes full LLD content."""
        ctx = _make_ctx(
            lld_content="# Full LLD\n\n## Section A\n\nContent A.\n\n## Section B\n\nContent B.\n",
            retry_count=1,
        )
        result = _build_tier1_prompt(ctx)
        assert "Content A" in result
        assert "Content B" in result

    def test_strips_completed_file_sections(self) -> None:
        """Tier 1 strips sections for completed files."""
        lld = (
            "# LLD\n\n"
            "## Section for done.py\n\n"
            "Content about assemblyzero/done.py that should be removed.\n\n"
            "## Section for target.py\n\n"
            "Content about target.py.\n"
        )
        ctx = _make_ctx(
            lld_content=lld,
            target_file="target.py",
            completed_files=["assemblyzero/done.py"],
            retry_count=1,
        )
        result = _build_tier1_prompt(ctx)
        assert "Content about assemblyzero/done.py" not in result
        assert "Content about target.py" in result


class TestBuildTier2Prompt:
    """Tests for _build_tier2_prompt() directly."""

    def test_includes_relevant_section_only(self) -> None:
        """Tier 2 includes only the matched section."""
        lld = (
            "# LLD\n\n"
            "## Section for assemblyzero/utils/target.py\n\n"
            "Target section content.\n\n"
            "## Section for other.py\n\n"
            "Other section content.\n"
        )
        ctx = _make_ctx(
            lld_content=lld,
            target_file="assemblyzero/utils/target.py",
            retry_count=2,
            previous_attempt_snippet="old code\n",
        )
        result = _build_tier2_prompt(ctx)
        assert "Target section content" in result
        assert "Other section content" not in result

    def test_includes_error_and_snippet(self) -> None:
        """Tier 2 includes error message and previous attempt snippet."""
        ctx = _make_ctx(
            lld_content="# LLD\n\n## Section for target.py\n\nContent.\n",
            target_file="target.py",
            error_message="TypeError: bad type",
            retry_count=2,
            previous_attempt_snippet="def bad_func():\n    return None\n",
        )
        result = _build_tier2_prompt(ctx)
        assert "TypeError: bad type" in result
        assert "def bad_func():" in result

    def test_snippet_none_raises_valueerror(self) -> None:
        """Tier 2 with None snippet raises ValueError."""
        ctx = _make_ctx(retry_count=2, previous_attempt_snippet=None)
        with pytest.raises(ValueError, match="Tier 2 requires previous_attempt_snippet"):
            _build_tier2_prompt(ctx)

    def test_falls_back_to_tier1_when_no_section(self) -> None:
        """Falls back to tier 1 prompt when section not found."""
        lld = "# LLD\n\n## Overview\n\nGeneral content.\n"
        ctx = _make_ctx(
            lld_content=lld,
            target_file="assemblyzero/nonexistent.py",
            retry_count=2,
            previous_attempt_snippet="code\n",
        )
        result = _build_tier2_prompt(ctx)
        # Should use tier 1 preamble as fallback indicator
        assert "full specification context" in result
```

## 7. Pattern References

### 7.1 Node Module Structure

**File:** `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py` (lines 1-50)

```python
"""Implementation Spec generation node.

Issue #304: Implementation Readiness Review Workflow (LLD -> Implementation Spec)

Node N2: Generate the Implementation Spec draft using Claude.
"""

from __future__ import annotations

import logging
from typing import Any

# ... imports ...

logger = logging.getLogger(__name__)
```

**Relevance:** Follow the same module structure: docstring with issue reference, `from __future__ import annotations`, logging setup, typed imports. The `retry_prompt_builder.py` module follows this exact pattern.

### 7.2 Utils Module Structure

**File:** `assemblyzero/utils/codebase_reader.py` (lines 1-50)

```python
"""Codebase reading utilities for AssemblyZero.

... docstring ...
"""

from __future__ import annotations

# ... imports and TypedDict definitions ...
```

**Relevance:** The `lld_section_extractor.py` utility follows the same pattern as existing utils: module docstring, `from __future__ import annotations`, TypedDict definitions near top, public functions first, private helpers after.

### 7.3 `__init__.py` Export Pattern

**File:** `assemblyzero/utils/__init__.py` (lines 1-30)

```python
"""Utility modules for AssemblyZero."""

from assemblyzero.utils.codebase_reader import (
    FileReadResult,
    is_sensitive_file,
    parse_project_metadata,
    read_file_with_budget,
    read_files_within_budget,
)
```

**Relevance:** New exports follow the same pattern: `from assemblyzero.utils.new_module import (ClassName, function_name,)`. Alphabetical grouping by module.

### 7.4 Test Structure Pattern

**File:** `tests/unit/test_retry_prompt_builder.py` follows the pattern seen across the test suite:

- `pytest.fixture` for shared data
- Class-based test grouping by feature
- Test IDs in docstrings (e.g., "T010: ...")
- `pytest.raises` for error cases
- `caplog` for log assertions

**Relevance:** Maintaining consistency with existing test conventions in the project.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | All new files |
| `import logging` | stdlib | `retry_prompt_builder.py`, `lld_section_extractor.py` |
| `import re` | stdlib | `retry_prompt_builder.py`, `lld_section_extractor.py` |
| `from pathlib import PurePosixPath` | stdlib | `lld_section_extractor.py` |
| `from typing import TypedDict` | stdlib | `retry_prompt_builder.py`, `lld_section_extractor.py` |
| `import tiktoken` | pyproject.toml (existing) | `retry_prompt_builder.py` |
| `from assemblyzero.utils.lld_section_extractor import extract_file_spec_section` | internal (new) | `retry_prompt_builder.py` |
| `import pytest` | dev dependency | test files |
| `from unittest.mock import patch` | stdlib | `test_retry_prompt_builder.py` |
| `from pathlib import Path` | stdlib | test files |

**New Dependencies:** None. `tiktoken` is already in `pyproject.toml`.

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

## 11. Implementation Notes

### 11.1 Error Handling Convention

All validation errors raise `ValueError` with a descriptive message. The `_estimate_tokens()` function is the exception — it catches all exceptions from tiktoken and returns `-1`, because token estimation is non-critical (used for logging/observability only). The fallback from tier 2 to tier 1 logs a `WARNING` and never raises.

### 11.2 Logging Convention

Use `logging.getLogger(__name__)` in each new module. Log at `WARNING` level for fallback events (tier 2 -> tier 1). No `print()` statements. This follows the pattern in existing utility modules (e.g., `codebase_reader.py`).

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `SNIPPET_MAX_LINES` | `60` | Generous tail window capturing failure context without excessive size |
| `TIER_BOUNDARY` | `2` | `retry_count >= 2` triggers tier 2; matches LLD specification |
| `_SYSTEM_PREAMBLE_TIER1` | String | Tier 1 system instruction for the retry prompt |
| `_SYSTEM_PREAMBLE_TIER2` | String | Tier 2 system instruction for the retry prompt |
| `_SPEC_SECTION_HEADER` | String | Markdown header before the extracted spec section |
| `_TARGET_FILE_HEADER` | String | Label before the target file path |
| `_ERROR_HEADER` | String | Label before the error message |
| `_PREVIOUS_ATTEMPT_HEADER` | Format string | Label before the truncated snippet (uses `{max_lines}`) |

### 11.4 Fixture Design Rationale

The `full_lld.md` fixture is designed to be large enough that removing all non-relevant sections produces a >50% token reduction. It includes:
- 5 distinct file-specific sections with explicit paths
- 5 "padding" sections with general content (simulates LLD verbosity)
- A preamble, requirements section, and alternatives section

The `minimal_lld.md` fixture has exactly one file-specific section, ensuring clean single-match testing.

### 11.5 Type Annotation Notes

Both modules use `from __future__ import annotations` to enable `str | None` syntax on Python 3.10+. All function parameters and return types are annotated. TypedDict classes use explicit field annotations. The `list[str]` and `dict[str, Any]` generic forms are used (not `List`, `Dict`).

For mypy strict compliance:
- No `Any` type is used anywhere (not needed for these modules)
- All private helper functions have full annotations
- Return types are always explicit (no inference reliance)

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
| Iterations | 0 |
| Finalized | — |