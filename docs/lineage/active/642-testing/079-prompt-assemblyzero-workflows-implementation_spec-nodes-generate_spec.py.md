# Implementation Request: assemblyzero/workflows/implementation_spec/nodes/generate_spec.py

## Task

Write the complete contents of `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py`.

Change type: Modify
Description: Update call site to construct `RetryContext` from workflow state and pass to `build_retry_prompt()`

## LLD Specification

# Implementation Spec: #642 — Retry Context Pruning

| Field | Value |
|-------|-------|
| Issue | #642 |
| LLD | `docs/lld/active/642-retry-prompt-context-pruning.md` |
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
| 7 | `assemblyzero/workflows/implementation_spec/state.py` | Modify | Add `retry_count: int` and `previous_attempt_snippet: str | None` to workflow state TypedDict |
| 8 | `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py` | Modify | Update call site to construct `RetryContext` from workflow state and pass to `build_retry_prompt()` |
| 9 | `tests/unit/test_lld_section_extractor.py` | Add | Unit tests for section extraction |
| 10 | `tests/unit/test_retry_prompt_builder.py` | Add | Unit tests for retry prompt builder including integration with workflow state |

**Implementation Order Rationale:** Fixtures first (needed by tests), then the utility module (no internal deps), then the main prompt builder module (depends on utility), then exports, then workflow state update (no code deps on new modules), then call site integration (depends on state + prompt builder), then tests last (depend on everything).

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

**What changes:** Append an import block for `build_retry_prompt` from the new `retry_prompt_builder` module.

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

**What changes:** Append an import block for `extract_file_spec_section` and `ExtractedSection` from the new `lld_section_extractor` module.

### 3.3 `assemblyzero/workflows/implementation_spec/state.py`

**Relevant excerpt** (expected TypedDict definition — lines near the top of the state class):

```python
class ImplementationSpecState(TypedDict, total=False):
    """State for the Implementation Spec workflow."""
    issue_number: int
    lld_path: str
    lld_content: str
    target_file: str
    error_message: str
    completed_files: list[str]
    # ... additional existing fields ...
```

**What changes:** Add two new fields: `retry_count: int` (default 0) and `previous_attempt_snippet: str | None` (default None). These are used by the retry prompt builder to determine which pruning tier to apply.

### 3.4 `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py`

**Relevant excerpt** (the section where retry prompts are constructed — expected pattern):

```python
# Expected call site pattern (exact location to be confirmed during implementation):
def generate_code(state: ImplementationSpecState) -> dict[str, Any]:
    """Generate code for a target file using LLD context."""
    # ... existing logic ...
    # On retry, a prompt is assembled from LLD + error info
    # This is where build_retry_prompt() will be called
    # ... existing prompt construction logic ...
```

**What changes:** Replace the existing inline retry prompt construction with a call to `build_retry_prompt()`, constructing a `RetryContext` from the workflow state fields (`retry_count`, `previous_attempt_snippet`, `lld_content`, `target_file`, `error_message`, `completed_files`).

## 4. Data Structures

### 4.1 RetryContext

**Definition:**

```python
# assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py

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
    "lld_content": "# 642 - Fix: Reduce Retry Prompt Context\n\n## 1. Context & Goal\n...\n\n## Section for assemblyzero/services/alpha_service.py\n\n### Function Signatures\n\ndef create_alpha(name: str) -> Alpha:\n    ...\n\n## Section for assemblyzero/services/beta_service.py\n\n...",
    "target_file": "assemblyzero/services/alpha_service.py",
    "error_message": "SyntaxError: unexpected indent at line 45",
    "retry_count": 2,
    "previous_attempt_snippet": "class AlphaService:\n    def __init__(self):\n        self.name = 'alpha'\n        \n    def create_alpha(name: str) -> Alpha:\n            return Alpha(name=name)  # <-- indentation error here",
    "completed_files": ["assemblyzero/services/beta_service.py", "assemblyzero/models/gamma_model.py"]
}
```

### 4.2 PrunedRetryPrompt

**Definition:**

```python
# assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py

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
    "prompt_text": "You are implementing a fix for a previous failed attempt.\n\n## Relevant Specification\n\n## Section for assemblyzero/services/alpha_service.py\n\n### Function Signatures\n\ndef create_alpha(name: str) -> Alpha:\n    ...\n\n## Target File\nassemblyzero/services/alpha_service.py\n\n## Error from Previous Attempt\nSyntaxError: unexpected indent at line 45\n\n## Previous Attempt (last 60 lines)\n...\nclass AlphaService:\n    def __init__(self):\n        self.name = 'alpha'\n\n    def create_alpha(name: str) -> Alpha:\n            return Alpha(name=name)",
    "tier": 2,
    "estimated_tokens": 187,
    "context_sections_included": ["Section for assemblyzero/services/alpha_service.py", "error_message", "previous_attempt_snippet (truncated)"]
}
```

### 4.3 ExtractedSection

**Definition:**

```python
# assemblyzero/utils/lld_section_extractor.py

class ExtractedSection(TypedDict):
    """Result of extracting a single relevant section from an LLD."""
    section_heading: str
    section_body: str
    match_confidence: float
```

**Concrete Example:**

```json
{
    "section_heading": "## Section for assemblyzero/services/alpha_service.py",
    "section_body": "## Section for assemblyzero/services/alpha_service.py\n\n### Function Signatures\n\ndef create_alpha(name: str) -> Alpha:\n    \"\"\"Create a new Alpha instance.\"\"\"\n    ...\n\n### Data Structures\n\nclass Alpha(TypedDict):\n    name: str\n    id: int\n    created_at: str\n",
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
    lld_content="# 642 - Fix\n\n## 1. Context\n...\n\n## Section for assemblyzero/services/alpha_service.py\n\nAlpha service creates Alpha instances...\n\n## Section for assemblyzero/services/beta_service.py\n\nBeta service provides...\n\n## Padding Section Alpha\n\nLorem ipsum...",
    target_file="assemblyzero/services/alpha_service.py",
    error_message="SyntaxError: unexpected indent at line 45",
    retry_count=2,
    previous_attempt_snippet="class AlphaService:\n    def __init__(self):\n        self.name = 'alpha'\n\n    def create_alpha(name: str) -> Alpha:\n            return Alpha(name=name)",
    completed_files=["assemblyzero/services/beta_service.py"],
)
```

**Output Example:**

```python
PrunedRetryPrompt(
    prompt_text="You are implementing a fix for a previous failed attempt...\n\n## Relevant Specification\n\n## Section for assemblyzero/services/alpha_service.py\n\nAlpha service creates Alpha instances...\n\n## Target File\nassemblyzero/services/alpha_service.py\n\n## Error from Previous Attempt\nSyntaxError: unexpected indent at line 45\n\n## Previous Attempt (last 60 lines)\nclass AlphaService:\n    def __init__(self):\n        self.name = 'alpha'\n\n    def create_alpha(name: str) -> Alpha:\n            return Alpha(name=name)",
    tier=2,
    estimated_tokens=142,
    context_sections_included=["Section for assemblyzero/services/alpha_service.py", "error_message", "previous_attempt_snippet (truncated)"],
)
```

**Edge Cases:**
- `retry_count=0` -> raises `ValueError("retry_count must be >= 1")`
- `retry_count=2, previous_attempt_snippet=None` -> raises `ValueError("Tier 2 requires previous_attempt_snippet")`
- `lld_content=""` -> raises `ValueError("lld_content must not be empty")`
- Section extraction returns `None` for `retry_count>=2` -> falls back to tier 1, logs warning

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
    lld_content="# Full LLD\n\n## Section for alpha_service.py\n\nAlpha details...\n\n## Section for beta_service.py\n\nBeta details...",
    target_file="assemblyzero/services/alpha_service.py",
    error_message="NameError: name 'foo' is not defined",
    retry_count=1,
    previous_attempt_snippet=None,
    completed_files=["assemblyzero/services/beta_service.py"],
)
```

**Output Example:**

```python
"You are retrying code generation for a file that previously failed.\n\n## Full LLD Context\n\n# Full LLD\n\n## Section for alpha_service.py\n\nAlpha details...\n\n## Target File\nassemblyzero/services/alpha_service.py\n\n## Error from Previous Attempt\nNameError: name 'foo' is not defined"
# Note: "beta_service.py" section is stripped because it's in completed_files
```

**Edge Cases:**
- `completed_files=[]` -> full LLD retained without stripping

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
    lld_content="# LLD\n\n## Section for alpha.py\n\nAlpha spec...\n\n## Padding\n\nLorem ipsum dolor sit amet...",
    target_file="assemblyzero/services/alpha.py",
    error_message="TypeError: expected str, got int",
    retry_count=3,
    previous_attempt_snippet="def alpha():\n    return 42  # should return str",
    completed_files=[],
)
```

**Output Example:**

```python
"You are implementing a fix for a previous failed attempt.\n\n## Relevant Specification\n\n## Section for alpha.py\n\nAlpha spec...\n\n## Target File\nassemblyzero/services/alpha.py\n\n## Error from Previous Attempt\nTypeError: expected str, got int\n\n## Previous Attempt (last 60 lines)\ndef alpha():\n    return 42  # should return str"
# Note: "Padding" section is NOT included
```

**Edge Cases:**
- `previous_attempt_snippet=None` -> raises `ValueError("Tier 2 requires previous_attempt_snippet")`
- Section extraction returns `None` -> calls `_build_tier1_prompt(ctx)` as fallback, logs warning

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
snippet = "\n".join(f"line {i}: some code here" for i in range(200))
max_lines = 60
```

**Output Example (truncation needed):**

```python
"...\nline 140: some code here\nline 141: some code here\n...\nline 199: some code here"
# Exactly 61 lines: 1 "..." prefix line + 60 content lines
```

**Input Example (no truncation):**

```python
snippet = "line 1\nline 2\nline 3"
max_lines = 60
```

**Output Example (no truncation):**

```python
"line 1\nline 2\nline 3"
# Returned unchanged
```

**Edge Cases:**
- Empty string -> returned unchanged (`""`)
- Exactly `max_lines` lines -> returned unchanged

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
text = "Hello, world! This is a test string."
```

**Output Example:**

```python
9  # approximate tiktoken cl100k_base count
```

**Edge Cases:**
- `""` -> returns `0`
- tiktoken encoding failure -> returns `-1` (sentinel; wrapped in try/except)

### 5.6 `extract_file_spec_section()`

**File:** `assemblyzero/utils/lld_section_extractor.py`

**Signature:**

```python
def extract_file_spec_section(lld_content: str, target_file: str) -> ExtractedSection | None:
    """Parse LLD markdown and extract the section(s) most relevant to target_file."""
    ...
```

**Input Example (exact match):**

```python
lld_content = "# LLD\n\n## 1. Context\n\nGeneral info...\n\n## Section for assemblyzero/services/alpha_service.py\n\nAlpha service creates Alpha instances.\n\n### Function Signatures\n\ndef create_alpha(name: str) -> Alpha: ...\n\n## Section for assemblyzero/services/beta_service.py\n\nBeta service provides connectivity.\n"
target_file = "assemblyzero/services/alpha_service.py"
```

**Output Example (exact match):**

```python
ExtractedSection(
    section_heading="## Section for assemblyzero/services/alpha_service.py",
    section_body="## Section for assemblyzero/services/alpha_service.py\n\nAlpha service creates Alpha instances.\n\n### Function Signatures\n\ndef create_alpha(name: str) -> Alpha: ...\n",
    match_confidence=1.0,
)
```

**Input Example (no match):**

```python
lld_content = "# LLD\n\n## 1. Context\n\nGeneral info only.\n"
target_file = "assemblyzero/services/nonexistent.py"
```

**Output Example (no match):**

```python
None
```

**Edge Cases:**
- `lld_content=""` -> raises `ValueError("lld_content must not be empty")`
- Stem-only match (e.g., LLD mentions `alpha_service.py` but not full path) -> returns `ExtractedSection` with `match_confidence=0.6`

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
lld_content = "# Title\n\nPreamble text.\n\n## Section A\n\nContent A.\n\n## Section B\n\nContent B.\n\n### Subsection B1\n\nContent B1.\n"
```

**Output Example:**

```python
[
    ("# Title", "# Title\n\nPreamble text.\n"),
    ("## Section A", "## Section A\n\nContent A.\n"),
    ("## Section B", "## Section B\n\nContent B.\n"),
    ("### Subsection B1", "### Subsection B1\n\nContent B1.\n"),
]
```

**Edge Cases:**
- No headings -> returns single tuple `("", lld_content)`
- Only `#` heading -> returns single section for whole document

### 5.8 `_score_section_for_file()`

**File:** `assemblyzero/utils/lld_section_extractor.py`

**Signature:**

```python
def _score_section_for_file(section_text: str, target_file: str) -> float:
    """Score how relevant a section is to target_file (0.0–1.0)."""
    ...
```

**Input Example (exact match):**

```python
section_text = "## Section for assemblyzero/services/alpha_service.py\n\nAlpha service details..."
target_file = "assemblyzero/services/alpha_service.py"
```

**Output Example (exact match):**

```python
1.0
```

**Input Example (stem match):**

```python
section_text = "## Alpha Service\n\nThis section describes alpha_service.py behavior..."
target_file = "assemblyzero/services/alpha_service.py"
```

**Output Example (stem match):**

```python
0.6
```

**Input Example (directory match):**

```python
section_text = "## Services Overview\n\nThe assemblyzero/services/ directory contains..."
target_file = "assemblyzero/services/alpha_service.py"
```

**Output Example (directory match):**

```python
0.3
```

**Input Example (no match):**

```python
section_text = "## Security Considerations\n\nNo sensitive data involved."
target_file = "assemblyzero/services/alpha_service.py"
```

**Output Example (no match):**

```python
0.0
```

## 6. Change Instructions

### 6.1 `tests/fixtures/retry_prompt/full_lld.md` (Add)

**Action:** Create new directory `tests/fixtures/retry_prompt/` and add `full_lld.md` with the following complete contents (~400 lines with 5+ file-specific sections and padding sections):

```markdown
# 999 - Sample LLD for Retry Prompt Testing

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

Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore
eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt
in culpa qui officia deserunt mollit anim id est laborum.

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

All services must implement the standard interface. Alpha service creates
Alpha instances with validated names. Beta service provides connectivity
to downstream systems. Gamma model receives new fields for tracking state.
Delta helper provides shared formatting utilities. Epsilon flow orchestrates
the end-to-end pipeline.

## Section for assemblyzero/services/alpha_service.py

### Function Signatures

```python
def create_alpha(name: str) -> Alpha:
    """Create a new Alpha instance with the given name."""
    ...

def validate_alpha_name(name: str) -> bool:
    """Return True if name meets Alpha naming constraints."""
    ...
```

### Data Structures

```python
class Alpha(TypedDict):
    name: str
    id: int
    created_at: str
```

Alpha service creates Alpha instances with validated names. The service
must enforce naming constraints before persisting. Error handling follows
the standard pattern: return error_message field on failure.

Additional implementation details for Alpha service spanning multiple
paragraphs to simulate realistic section length. The Alpha service
is the primary entry point for creating new tracked entities in the
system. It validates inputs, assigns unique IDs, and timestamps the
creation event.

## Section for assemblyzero/services/beta_service.py

### Function Signatures

```python
def connect_beta(host: str, port: int) -> BetaConnection:
    """Establish connection to a Beta downstream system."""
    ...

def disconnect_beta(conn: BetaConnection) -> None:
    """Gracefully close a Beta connection."""
    ...
```

### Constants

```python
BETA_TIMEOUT_SECONDS: int = 30
BETA_MAX_RETRIES: int = 3
```

Beta service provides connectivity and session management for
downstream Beta systems. It manages connection pooling and
automatic retry with exponential backoff.

## Section for assemblyzero/models/gamma_model.py

### Current State

```python
class GammaModel(TypedDict):
    id: int
    label: str
```

### Proposed Changes

Add `status` and `updated_at` fields to GammaModel:

```python
class GammaModel(TypedDict):
    id: int
    label: str
    status: str       # New: "active", "archived", "pending"
    updated_at: str   # New: ISO 8601 timestamp
```

The gamma model tracks entity lifecycle state. The new fields
enable querying by status and ordering by last update time.

## Section for assemblyzero/utils/delta_helper.py

### Function Signatures

```python
def format_timestamp(dt: datetime) -> str:
    """Format datetime as ISO 8601 string."""
    ...

def sanitize_label(label: str) -> str:
    """Remove non-alphanumeric characters from label."""
    ...
```

Delta helper provides shared formatting and sanitization utilities
used across multiple services. It has no external dependencies.

## Section for assemblyzero/workflows/epsilon_flow.py

### Function Signatures

```python
def run_epsilon_flow(state: EpsilonState) -> dict[str, Any]:
    """Execute the Epsilon end-to-end workflow."""
    ...

def validate_epsilon_inputs(state: EpsilonState) -> list[str]:
    """Return list of validation errors, empty if valid."""
    ...
```

### Integration Points

Epsilon flow calls Alpha service, Beta service, and Delta helper
in sequence. It reads GammaModel for state tracking. The flow
is designed to be idempotent and can be safely retried.

## 4. Alternatives Considered

Several alternative approaches were evaluated before settling on
the current design. Option A used a monolithic service but was
rejected due to complexity. Option B used microservices but was
rejected due to operational overhead. The chosen approach balances
modularity with operational simplicity.

## 5. Security Considerations

No sensitive data is processed by these services. All inputs
are validated before use. No external API keys or credentials
are stored in service code. Connections to downstream systems
use TLS.

## Padding Section Alpha

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam
euismod, nisi vel consectetur interdum, nisl nunc egestas nisi,
vitae tincidunt nisl nunc euismod nisi. Donec auctor, nisi vel
consectetur interdum, nisl nunc egestas nisi, vitae tincidunt
nisl nunc euismod nisi.

Sed ut perspiciatis unde omnis iste natus error sit voluptatem
accusantium doloremque laudantium, totam rem aperiam, eaque ipsa
quae ab illo inventore veritatis et quasi architecto beatae vitae
dicta sunt explicabo. Nemo enim ipsam voluptatem quia voluptas.

Curabitur at lacus ac velit ornare lobortis. Cras dapibus.
Vivamus elementum semper nisi. Aenean vulputate eleifend tellus.
Aenean leo ligula, porttitor eu, consequat vitae, eleifend ac, enim.

## Padding Section Beta

At vero eos et accusamus et iusto odio dignissimos ducimus qui
blanditiis praesentium voluptatum deleniti atque corrupti quos
dolores et quas molestias excepturi sint occaecati cupiditate
non provident, similique sunt in culpa qui officia deserunt
mollitia animi, id est laborum et dolorum fuga.

Et harum quidem rerum facilis est et expedita distinctio. Nam
libero tempore, cum soluta nobis est eligendi optio cumque nihil
impedit quo minus id quod maxime placeat facere possimus, omnis
voluptas assumenda est, omnis dolor repellendus.

## Padding Section Gamma

Temporibus autem quibusdam et aut officiis debitis aut rerum
necessitatibus saepe eveniet ut et voluptates repudiandae sint
et molestiae non recusandae. Itaque earum rerum hic tenetur a
sapiente delectus, ut aut reiciendis voluptatibus maiores alias
consequatur aut perferendis doloribus asperiores repellat.

Additional padding content to push total fixture size to approximately
400 lines, ensuring realistic token counts for tier 1 vs tier 2
comparison testing. This content should not match any target file
path and should be excluded from tier 2 prompts entirely.

## Padding Section Delta

Quis autem vel eum iure reprehenderit qui in ea voluptate velit
esse quam nihil molestiae consequatur, vel illum qui dolorem eum
fugiat quo voluptas nulla pariatur. Ut enim ad minima veniam,
quis nostrum exercitationem ullam corporis suscipit laboriosam.

More padding text to increase fixture size. This section contains
no file paths and should never be matched by the section extractor.
It exists purely to demonstrate that tier 2 pruning successfully
excludes irrelevant content from the retry prompt.

## Padding Section Epsilon

Sed ut perspiciatis unde omnis iste natus error sit voluptatem
accusantium doloremque laudantium, totam rem aperiam, eaque ipsa
quae ab illo inventore veritatis et quasi architecto beatae vitae
dicta sunt explicabo. Nemo enim ipsam voluptatem quia voluptas
sit aspernatur aut odit aut fugit.

Final padding section. Combined with all preceding sections, the
total fixture should be approximately 400 lines, which when
tokenized produces a significant token count difference between
tier 1 (full LLD) and tier 2 (single section only).
```

### 6.2 `tests/fixtures/retry_prompt/minimal_lld.md` (Add)

**Action:** Create `tests/fixtures/retry_prompt/minimal_lld.md` with the following complete contents:

```markdown
# 998 - Minimal LLD for Testing

## 1. Context

This is a minimal LLD fixture with only one file spec section.
It is used to test unambiguous section extraction.

## Section for assemblyzero/utils/tiny_helper.py

### Function Signatures

```python
def tiny_format(value: str) -> str:
    """Format a value using the tiny convention."""
    ...
```

### Implementation Notes

The tiny helper is a minimal utility with no external dependencies.
It follows the standard pattern of returning formatted strings.
Error handling: raises ValueError on empty input.
```

### 6.3 `assemblyzero/utils/lld_section_extractor.py` (Add)

**Action:** Create new file with the following complete contents:

```python
"""LLD section extractor utility.

Issue #642: Extract file-relevant sections from LLD markdown to support
tiered context pruning in retry prompts.
"""

from __future__ import annotations

import logging
import os
import re
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
      2. Score each section for relevance to target_file.
      3. Return the highest-scoring section if score > 0.0.
      4. Return None if no section matches.

    Args:
        lld_content: Full LLD markdown string.
        target_file: Relative file path (e.g., "assemblyzero/services/alpha_service.py").

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

    best_score = 0.0
    best_heading = ""
    best_body = ""

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
    # Match lines starting with ## or ### (but not #### or deeper)
    heading_pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
    matches = list(heading_pattern.finditer(lld_content))

    if not matches:
        return [("", lld_content)]

    sections: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(lld_content)
        heading_line = match.group(0).strip()
        section_text = lld_content[start:end]
        sections.append((heading_line, section_text))

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
    # Normalize path separators
    normalized_target = target_file.replace("\\", "/")

    # Exact path match
    if normalized_target in section_text:
        return 1.0

    # Filename stem match (e.g., "alpha_service" from "alpha_service.py")
    basename = os.path.basename(normalized_target)
    stem = os.path.splitext(basename)[0]
    if stem and stem in section_text:
        return 0.6

    # Directory name match (e.g., "assemblyzero/services" from path)
    parent_dir = os.path.dirname(normalized_target)
    if parent_dir and parent_dir in section_text:
        return 0.3

    return 0.0
```

### 6.4 `assemblyzero/utils/__init__.py` (Modify)

**Change:** Append import block after the existing `pattern_scanner` import block.

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

**Action:** Create new file with the following complete contents:

```python
"""Retry prompt builder with tiered context pruning.

Issue #642: Implement tiered context pruning in build_retry_prompt() so that
retry 1 sends the full LLD while retry 2+ sends only the relevant LLD file
spec section, the error message, and a truncated previous-attempt snippet.
"""

from __future__ import annotations

import logging
from typing import TypedDict

import tiktoken

from assemblyzero.utils.lld_section_extractor import extract_file_spec_section

logger = logging.getLogger(__name__)

# Module-level constants
SNIPPET_MAX_LINES: int = 60
"""Maximum lines retained from previous attempt snippet (tail)."""

TIER_BOUNDARY: int = 2
"""retry_count >= this value triggers Tier 2 pruning."""

# Prompt template fragments
_SYSTEM_PREAMBLE_TIER1: str = (
    "You are retrying code generation for a file that previously failed.\n"
    "Below is the full design specification and the error from the previous attempt.\n"
    "Generate a corrected implementation.\n"
)

_SYSTEM_PREAMBLE_TIER2: str = (
    "You are implementing a fix for a previous failed attempt.\n"
    "Below is only the relevant specification section for the target file,\n"
    "the error from the previous attempt, and the last portion of your\n"
    "previous output. Generate a corrected implementation.\n"
)

_SPEC_SECTION_HEADER: str = "\n## Relevant Specification\n\n"
_FULL_LLD_HEADER: str = "\n## Full LLD Context\n\n"
_TARGET_FILE_HEADER: str = "\n## Target File\n"
_ERROR_HEADER: str = "\n## Error from Previous Attempt\n"
_PREVIOUS_ATTEMPT_HEADER: str = "\n## Previous Attempt (last {n} lines)\n"


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
        ValueError: If retry_count < 1, lld_content is empty, target_file is empty,
            or error_message is empty.
    """
    if ctx["retry_count"] < 1:
        raise ValueError("retry_count must be >= 1")
    if not ctx["lld_content"].strip():
        raise ValueError("lld_content must not be empty")
    if not ctx["target_file"].strip():
        raise ValueError("target_file must not be empty")
    if not ctx["error_message"].strip():
        raise ValueError("error_message must not be empty")

    if ctx["retry_count"] < TIER_BOUNDARY:
        tier = 1
        prompt_text = _build_tier1_prompt(ctx)
        sections_included = ["full_lld (minus completed_files)", "error_message"]
    else:
        if ctx["previous_attempt_snippet"] is None:
            raise ValueError("Tier 2 requires previous_attempt_snippet")
        tier = 2
        prompt_text = _build_tier2_prompt(ctx)
        # Check if fallback occurred (tier2 falls back to tier1 on extraction failure)
        if _FULL_LLD_HEADER in prompt_text:
            tier = 1
            sections_included = [
                "full_lld (minus completed_files) [fallback]",
                "error_message",
            ]
        else:
            sections_included = [
                f"Section for {ctx['target_file']}",
                "error_message",
                "previous_attempt_snippet (truncated)",
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

    Strips sections for completed files. Includes full LLD + target file
    section call-out + error message.

    Args:
        ctx: Full RetryContext.

    Returns:
        Assembled prompt string.
    """
    lld = _strip_completed_sections(ctx["lld_content"], ctx["completed_files"])

    parts: list[str] = [
        _SYSTEM_PREAMBLE_TIER1,
        _FULL_LLD_HEADER,
        lld,
        _TARGET_FILE_HEADER,
        ctx["target_file"],
        _ERROR_HEADER,
        ctx["error_message"],
    ]
    return "".join(parts)


def _build_tier2_prompt(ctx: RetryContext) -> str:
    """Assemble minimal retry prompt (Retry 2+).

    Includes only the relevant file spec section, error, and truncated
    previous attempt snippet. Falls back to tier 1 if section extraction fails.

    Args:
        ctx: Full RetryContext; previous_attempt_snippet must not be None.

    Returns:
        Assembled prompt string.

    Raises:
        ValueError: If previous_attempt_snippet is None.
    """
    if ctx["previous_attempt_snippet"] is None:
        raise ValueError("Tier 2 requires previous_attempt_snippet")

    section = extract_file_spec_section(ctx["lld_content"], ctx["target_file"])
    if section is None:
        logger.warning(
            "Tier 2 section extraction failed; falling back to tier 1 for file=%s",
            ctx["target_file"],
        )
        return _build_tier1_prompt(ctx)

    truncated = _truncate_snippet(ctx["previous_attempt_snippet"])
    snippet_lines = len(truncated.splitlines())

    parts: list[str] = [
        _SYSTEM_PREAMBLE_TIER2,
        _SPEC_SECTION_HEADER,
        section["section_body"],
        _TARGET_FILE_HEADER,
        ctx["target_file"],
        _ERROR_HEADER,
        ctx["error_message"],
        _PREVIOUS_ATTEMPT_HEADER.format(n=snippet_lines),
        truncated,
    ]
    return "".join(parts)


def _truncate_snippet(snippet: str, max_lines: int = SNIPPET_MAX_LINES) -> str:
    """Truncate a previous-attempt snippet to at most max_lines lines.

    Keeps the final max_lines lines (tail) as they are most relevant
    to the failure point.

    Args:
        snippet: Raw previous attempt text.
        max_lines: Maximum number of lines to retain.

    Returns:
        Truncated snippet string with a leading "..." if lines were dropped.
    """
    lines = snippet.splitlines()
    if len(lines) <= max_lines:
        return snippet
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
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        logger.warning("tiktoken encoding failed; returning -1 sentinel")
        return -1


def _strip_completed_sections(lld_content: str, completed_files: list[str]) -> str:
    """Remove LLD sections that correspond to already-completed files.

    Args:
        lld_content: Full LLD markdown.
        completed_files: List of file paths already completed.

    Returns:
        LLD content with completed file sections removed.
    """
    if not completed_files:
        return lld_content

    from assemblyzero.utils.lld_section_extractor import _split_lld_into_sections

    sections = _split_lld_into_sections(lld_content)
    kept_parts: list[str] = []

    for _heading, body in sections:
        # Check if this section is about a completed file
        is_completed = False
        for completed in completed_files:
            normalized = completed.replace("\\", "/")
            if normalized in body:
                is_completed = True
                break
        if not is_completed:
            kept_parts.append(body)

    return "".join(kept_parts)
```

### 6.6 `assemblyzero/workflows/implementation_spec/nodes/__init__.py` (Modify)

**Change:** Append import block after the existing `validate_completeness` import block.

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
+)
```

### 6.7 `assemblyzero/workflows/implementation_spec/state.py` (Modify)

**Change:** Add two new fields to the `ImplementationSpecState` TypedDict. Locate the class definition and add the fields after the existing fields.

```diff
 class ImplementationSpecState(TypedDict, total=False):
     """State for the Implementation Spec workflow."""
     issue_number: int
     lld_path: str
     lld_content: str
     target_file: str
     error_message: str
     completed_files: list[str]
+    retry_count: int
+    previous_attempt_snippet: str | None
     # ... additional existing fields ...
```

**Note:** Because this TypedDict uses `total=False`, both fields are optional by default. The call site must default `retry_count` to `0` and `previous_attempt_snippet` to `None` when not present in state.

### 6.8 `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py` (Modify)

**Change:** Add import and update the retry prompt construction logic. The exact line numbers depend on the current file contents. Locate the section where retry prompts are assembled and replace inline construction with `build_retry_prompt()`.

**Add import at top of file:**

```diff
+from assemblyzero.workflows.implementation_spec.nodes.retry_prompt_builder import (
+    RetryContext,
+    build_retry_prompt,
+)
```

**Replace inline retry prompt construction** (locate the retry logic block):

```diff
-    # Existing inline prompt construction for retries
-    retry_prompt = f"... {lld_content} ... {error_message} ..."
+    # Build retry prompt with tiered context pruning (#642)
+    retry_ctx = RetryContext(
+        lld_content=state.get("lld_content", ""),
+        target_file=state.get("target_file", ""),
+        error_message=state.get("error_message", ""),
+        retry_count=state.get("retry_count", 0),
+        previous_attempt_snippet=state.get("previous_attempt_snippet", None),
+        completed_files=state.get("completed_files", []),
+    )
+    result = build_retry_prompt(retry_ctx)
+    retry_prompt = result["prompt_text"]
+    logger.info(
+        "Retry prompt built: tier=%d, tokens=%d, file=%s",
+        result["tier"],
+        result["estimated_tokens"],
+        state.get("target_file", ""),
+    )
```

### 6.9 `tests/unit/test_lld_section_extractor.py` (Add)

**Action:** Create new file with the following complete contents:

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
    """Tests for extract_file_spec_section()."""

    def test_exact_path_match_returns_confidence_1(self, full_lld: str) -> None:
        """T090: Exact path match yields confidence=1.0."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/services/alpha_service.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "Alpha service" in result["section_body"]
        assert "create_alpha" in result["section_body"]

    def test_stem_match_returns_lower_confidence(self, full_lld: str) -> None:
        """T100: Stem-only match yields 0.0 < confidence < 1.0."""
        # Construct a target path not literally in the LLD but whose stem is
        result = extract_file_spec_section(
            full_lld, "some/other/path/alpha_service.py"
        )
        assert result is not None
        assert 0.0 < result["match_confidence"] < 1.0

    def test_no_match_returns_none(self, full_lld: str) -> None:
        """T110: No match returns None."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/nonexistent/zzz_module.py"
        )
        assert result is None

    def test_empty_lld_raises_value_error(self) -> None:
        """T120: Empty lld_content raises ValueError."""
        with pytest.raises(ValueError, match="lld_content must not be empty"):
            extract_file_spec_section("", "assemblyzero/foo.py")

    def test_whitespace_only_lld_raises_value_error(self) -> None:
        """Edge case: whitespace-only lld_content raises ValueError."""
        with pytest.raises(ValueError, match="lld_content must not be empty"):
            extract_file_spec_section("   \n\t  ", "assemblyzero/foo.py")

    def test_minimal_lld_exact_match(self, minimal_lld: str) -> None:
        """Minimal LLD with single section returns exact match."""
        result = extract_file_spec_section(
            minimal_lld, "assemblyzero/utils/tiny_helper.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "tiny_format" in result["section_body"]


class TestSplitLldIntoSections:
    """Tests for _split_lld_into_sections()."""

    def test_splits_at_heading_boundaries(self) -> None:
        """Sections are split at ## and ### boundaries."""
        content = "# Title\n\nPreamble.\n\n## A\n\nBody A.\n\n## B\n\nBody B.\n"
        sections = _split_lld_into_sections(content)
        assert len(sections) == 3
        assert sections[0][0] == "# Title"
        assert sections[1][0] == "## A"
        assert sections[2][0] == "## B"

    def test_no_headings_returns_full_content(self) -> None:
        """Content without headings returns single section."""
        content = "Just some text\nwith no headings.\n"
        sections = _split_lld_into_sections(content)
        assert len(sections) == 1
        assert sections[0][0] == ""
        assert sections[0][1] == content


class TestScoreSectionForFile:
    """Tests for _score_section_for_file()."""

    def test_exact_path_scores_1(self) -> None:
        """Exact path in section scores 1.0."""
        section = "## Section for assemblyzero/services/alpha.py\n\nDetails."
        assert _score_section_for_file(section, "assemblyzero/services/alpha.py") == 1.0

    def test_stem_match_scores_0_6(self) -> None:
        """Filename stem match scores 0.6."""
        section = "## Alpha Module\n\nalpha details and alpha reference."
        assert _score_section_for_file(section, "some/path/alpha.py") == 0.6

    def test_directory_match_scores_0_3(self) -> None:
        """Directory path match scores 0.3."""
        section = "## Overview of assemblyzero/services/ directory.\n\nGeneral."
        assert (
            _score_section_for_file(
                section, "assemblyzero/services/nonexistent_file.py"
            )
            == 0.3
        )

    def test_no_match_scores_0(self) -> None:
        """No match scores 0.0."""
        section = "## Security Notes\n\nNothing relevant here."
        assert (
            _score_section_for_file(section, "assemblyzero/services/alpha.py") == 0.0
        )
```

### 6.10 `tests/unit/test_retry_prompt_builder.py` (Add)

**Action:** Create new file with the following complete contents:

```python
"""Unit tests for retry prompt builder.

Issue #642: Tests for build_retry_prompt() with tiered context pruning.
"""

from __future__ import annotations

import logging
from pathlib import Path

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
    full_lld: str,
    *,
    retry_count: int = 1,
    target_file: str = "assemblyzero/services/alpha_service.py",
    error_message: str = "SyntaxError: unexpected indent at line 45",
    previous_attempt_snippet: str | None = None,
    completed_files: list[str] | None = None,
) -> RetryContext:
    """Helper to construct a RetryContext with defaults."""
    return RetryContext(
        lld_content=full_lld,
        target_file=target_file,
        error_message=error_message,
        retry_count=retry_count,
        previous_attempt_snippet=previous_attempt_snippet,
        completed_files=completed_files or [],
    )


class TestBuildRetryPrompt:
    """Tests for build_retry_prompt()."""

    def test_tier1_returns_full_lld(self, full_lld: str) -> None:
        """T010: retry_count=1 returns tier 1 with full LLD content."""
        ctx = _make_ctx(full_lld, retry_count=1)
        result = build_retry_prompt(ctx)
        assert result["tier"] == 1
        # Tier 1 should contain content from multiple sections
        assert "beta_service" in result["prompt_text"].lower()
        assert "gamma_model" in result["prompt_text"].lower()

    def test_tier2_excludes_bulk_lld(self, full_lld: str) -> None:
        """T020: retry_count=2 returns tier 2 without padding sections."""
        ctx = _make_ctx(
            full_lld,
            retry_count=2,
            previous_attempt_snippet="def create_alpha():\n    pass",
        )
        result = build_retry_prompt(ctx)
        assert result["tier"] == 2
        assert "Padding Section Gamma" not in result["prompt_text"]
        assert "alpha_service" in result["prompt_text"].lower()

    def test_tier2_tokens_le_50pct_tier1(self, full_lld: str) -> None:
        """T030: Tier 2 estimated_tokens ≤ 50% of Tier 1."""
        ctx_t1 = _make_ctx(full_lld, retry_count=1)
        result_t1 = build_retry_prompt(ctx_t1)

        ctx_t2 = _make_ctx(
            full_lld,
            retry_count=2,
            previous_attempt_snippet="def create_alpha():\n    pass",
        )
        result_t2 = build_retry_prompt(ctx_t2)

        assert result_t2["estimated_tokens"] <= 0.50 * result_t1["estimated_tokens"]

    def test_tier2_fallback_when_no_section(self, full_lld: str) -> None:
        """T040: Falls back to tier 1 when target file not found in LLD."""
        ctx = _make_ctx(
            full_lld,
            retry_count=2,
            target_file="assemblyzero/nonexistent/zzz_module.py",
            previous_attempt_snippet="some code here",
        )
        result = build_retry_prompt(ctx)
        assert result["tier"] == 1  # Fallback

    def test_tier2_fallback_emits_warning(
        self, full_lld: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        """T040 (cont): Fallback emits a warning log."""
        ctx = _make_ctx(
            full_lld,
            retry_count=2,
            target_file="assemblyzero/nonexistent/zzz_module.py",
            previous_attempt_snippet="some code here",
        )
        with caplog.at_level(logging.WARNING):
            build_retry_prompt(ctx)
        assert "falling back to tier 1" in caplog.text.lower()

    def test_retry_count_zero_raises(self, full_lld: str) -> None:
        """T050: retry_count=0 raises ValueError."""
        ctx = _make_ctx(full_lld, retry_count=0)
        with pytest.raises(ValueError, match="retry_count must be >= 1"):
            build_retry_prompt(ctx)

    def test_tier2_snippet_none_raises(self, full_lld: str) -> None:
        """T060: retry_count=2 with snippet=None raises ValueError."""
        ctx = _make_ctx(
            full_lld, retry_count=2, previous_attempt_snippet=None
        )
        with pytest.raises(ValueError, match="Tier 2 requires previous_attempt_snippet"):
            build_retry_prompt(ctx)

    def test_completed_files_excluded_tier1(self, full_lld: str) -> None:
        """T150: Completed files are excluded from tier 1 prompt."""
        ctx = _make_ctx(
            full_lld,
            retry_count=1,
            completed_files=["assemblyzero/services/beta_service.py"],
        )
        result = build_retry_prompt(ctx)
        assert "Beta service provides" not in result["prompt_text"]


class TestTruncateSnippet:
    """Tests for _truncate_snippet()."""

    def test_long_snippet_truncated(self) -> None:
        """T070: 200-line snippet truncated to SNIPPET_MAX_LINES."""
        snippet = "\n".join(f"line {i}: some code here" for i in range(200))
        result = _truncate_snippet(snippet, max_lines=60)
        lines = result.splitlines()
        # 1 "..." line + 60 content lines = 61
        assert len(lines) <= 61
        assert lines[0] == "..."
        assert "line 199" in result

    def test_short_snippet_unchanged(self) -> None:
        """T080: 3-line snippet returned unchanged."""
        snippet = "line 1\nline 2\nline 3"
        result = _truncate_snippet(snippet, max_lines=60)
        assert result == snippet

    def test_empty_snippet_unchanged(self) -> None:
        """Edge case: empty snippet returned unchanged."""
        assert _truncate_snippet("", max_lines=60) == ""

    def test_exact_max_lines_unchanged(self) -> None:
        """Edge case: snippet with exactly max_lines lines is unchanged."""
        snippet = "\n".join(f"line {i}" for i in range(60))
        result = _truncate_snippet(snippet, max_lines=60)
        assert result == snippet


class TestEstimateTokens:
    """Tests for _estimate_tokens()."""

    def test_nonempty_string_positive(self) -> None:
        """T130: Non-empty string returns positive token count."""
        result = _estimate_tokens("Hello, world!")
        assert isinstance(result, int)
        assert result > 0

    def test_empty_string_zero(self) -> None:
        """T140: Empty string returns 0."""
        assert _estimate_tokens("") == 0

    def test_long_text_reasonable(self) -> None:
        """Sanity: long text token count is reasonable (not wildly off)."""
        text = "word " * 1000  # ~1000 words
        result = _estimate_tokens(text)
        assert 500 < result < 2000  # rough sanity bounds
```

## 7. Pattern References

### 7.1 Node Module Structure

**File:** `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py` (lines 1–30)

```python
"""Generate Implementation Spec draft using Claude.

Issue #304: Implementation Readiness Review Workflow (LLD -> Implementation Spec)
"""

from __future__ import annotations

import logging
from typing import Any

# ... imports ...

logger = logging.getLogger(__name__)


def build_drafter_prompt(...) -> str:
    """Build the prompt for spec generation."""
    ...


def generate_spec(state: ...) -> dict[str, Any]:
    """Generate spec from LLD content."""
    ...
```

**Relevance:** The new `retry_prompt_builder.py` follows the exact same module structure: module docstring with issue reference, `from __future__ import annotations`, logging setup, public function signatures, private helpers. This pattern ensures consistency across all node modules.

### 7.2 Utils Module Structure

**File:** `assemblyzero/utils/lld_verification.py` (lines 1–25)

```python
"""LLD verification utilities.

Issue #277: Verification gate for LLD approval status.
"""

from __future__ import annotations

import logging
from typing import TypedDict

logger = logging.getLogger(__name__)


class LLDVerificationResult(TypedDict):
    """Result of LLD verification."""
    is_approved: bool
    error_message: str
```

**Relevance:** The new `lld_section_extractor.py` follows the same pattern: TypedDict result class, module docstring with issue reference, `from __future__ import annotations`, logging setup. This ensures the new utility module is stylistically consistent.

### 7.3 `__init__.py` Export Pattern

**File:** `assemblyzero/utils/__init__.py` (lines 3–12)

```python
from assemblyzero.utils.codebase_reader import (
    FileReadResult,
    is_sensitive_file,
    parse_project_metadata,
    read_file_with_budget,
    read_files_within_budget,
)
```

**Relevance:** New exports for `extract_file_spec_section` and `ExtractedSection` follow the same multi-line import style with explicit named imports.

### 7.4 Test Structure Pattern

**File:** `tests/unit/test_lld_section_extractor.py` (to be created) follows the same pattern as existing test files.

**Reference File:** `tests/test_designer.py` (lines 1–20)

```python
"""Unit tests for designer module."""

from __future__ import annotations

import pytest

# ... test class with pytest fixtures and assertions ...
```

**Relevance:** All new test files use pytest, `from __future__ import annotations`, class-based test organization, and `@pytest.fixture` for shared data. This is the established testing convention.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | All new files |
| `import logging` | stdlib | `retry_prompt_builder.py`, `lld_section_extractor.py` |
| `import os` | stdlib | `lld_section_extractor.py` |
| `import re` | stdlib | `lld_section_extractor.py` |
| `from typing import TypedDict` | stdlib | `retry_prompt_builder.py`, `lld_section_extractor.py` |
| `import tiktoken` | pypi (already in pyproject.toml) | `retry_prompt_builder.py` |
| `from assemblyzero.utils.lld_section_extractor import extract_file_spec_section` | internal (new) | `retry_prompt_builder.py` |
| `from assemblyzero.utils.lld_section_extractor import _split_lld_into_sections` | internal (new) | `retry_prompt_builder.py` (in `_strip_completed_sections`) |
| `import pytest` | pypi (dev dep) | All test files |
| `from pathlib import Path` | stdlib | All test files |

**New Dependencies:** None. `tiktoken` is already present in `pyproject.toml`.

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
| T100 | `extract_file_spec_section()` | full_lld with stem-only path | `0.0 < confidence < 1.0` |
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
| T210 | Workflow state definition | Inspect `ImplementationSpecState` annotations | `retry_count: int` and `previous_attempt_snippet: str \| None` present |
| T220 | Workflow call site integration | Construct state with `retry_count=2, previous_attempt_snippet="err at line 5"` | `RetryContext` fields populated correctly from state |

## 11. Implementation Notes

### 11.1 Error Handling Convention

All public functions validate inputs eagerly and raise `ValueError` with descriptive messages for invalid arguments. Internal/private functions assume valid inputs (validation happens at the public boundary). The `_estimate_tokens()` function is an exception: it wraps tiktoken in try/except and returns `-1` sentinel on failure because token estimation is non-critical (logging only).

### 11.2 Logging Convention

Use `logging.getLogger(__name__)` at module level. Log at WARNING level for fallback conditions (section extraction failure). Log at INFO level for normal operations in the call site (tier used, token count). Do not log at DEBUG level in the new modules to avoid noise.

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `SNIPPET_MAX_LINES` | `60` | Generous tail window that captures failure context without bloating the prompt |
| `TIER_BOUNDARY` | `2` | `retry_count >= 2` triggers tier 2; aligns with LLD specification of "retry 2+" |

### 11.4 Fixture Design Rationale

The `full_lld.md` fixture is designed with:
- 5 distinct `## Section for <path>` headings to test exact-match extraction
- 5 padding sections with no file paths to test exclusion in tier 2
- A preamble and requirements section to simulate realistic LLD structure
- Total ~400 lines to produce meaningful token count differences between tiers

The `minimal_lld.md` fixture provides a minimal baseline with exactly one file-specific section for testing unambiguous extraction.

### 11.5 Type Annotation Notes

Both new modules use `from __future__ import annotations` for PEP 604 union syntax (`str | None`). All public and private functions have complete parameter and return type annotations. TypedDict classes use class-based syntax with per-field docstring comments.

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
| Iterations | 2 |
| Finalized | 2026-03-07T04:35:32Z |

### Review Feedback Summary

The implementation spec is exceptionally well-detailed and completely executable. It provides full source code for all new modules and comprehensive unit tests, alongside exact diffs for modifying existing files. Data structures, function signatures, edge cases, and architectural constraints are concretely defined, ensuring a high probability of first-try success for an AI agent.

## Suggestions
- In `retry_prompt_builder.py`, consider moving the local import of `_split_lld_into_sections` (curre...


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:

- `assemblyzero/models/gamma_model.py`
- `assemblyzero/services/alpha_service.py`
- `assemblyzero/services/beta_service.py`
- `assemblyzero/utils/delta_helper.py`
- `assemblyzero/workflows/epsilon_flow.py`

Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
tests/
  accessibility/
  adversarial/
  benchmark/
  compliance/
  contract/
  e2e/
  fixtures/
    death/
    issue_workflow/
    janitor/
      mock_repo/
    lld_tracking/
    metrics/
    mock_lineage/
    mock_repo/
      docs/
      src/
    rag/
    retry_prompt/
    scout/
    scraper/
    spelunking/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_death/
    test_gate/
    test_janitor/
    test_metrics/
    test_rag/
    test_spelunking/
  visual/
  __init__.py
  conftest.py
  test_assemblyzero_config.py
  test_audit.py
  test_audit_sharding.py
  test_credentials.py
  test_designer.py
  test_gemini_client.py
  test_gemini_credentials_v2.py
  test_integration_workflow.py
  ... and 13 more files
assemblyzero/
  core/
    validation/
  graphs/
  hooks/
  metrics/
  nodes/
  rag/
  spelunking/
  telemetry/
  utils/
  workflows/
    death/
    implementation_spec/
      nodes/
    issue/
      nodes/
    janitor/
      probes/
    lld/
      nodes/
    orchestrator/
    parallel/
    requirements/
      nodes/
      parsers/
    scout/
    testing/
      completeness/
      knowledge/
      nodes/
      runners/
      templates/
  __init__.py
  tracing.py
dashboard/
  src/
    client/
      components/
      pages/
  package.json
  tsconfig.client.json
  tsconfig.json
  tsconfig.worker.json
  wrangler.toml
data/
  hourglass/
  unleashed/
  handoff-log.md
```

Use these real paths — do NOT invent paths that don't exist.

## Existing File Contents

The file currently contains:

```python
"""N2: Generate Implementation Spec node for Implementation Spec Workflow.

Issue #304: Implementation Readiness Review Workflow (LLD -> Implementation Spec)

Uses the configured drafter LLM (Claude) to generate an Implementation Spec
from the approved LLD, codebase analysis results (current state snapshots
and pattern references), and the Implementation Spec template.

Supports revision mode when N3 (validate_completeness) or N5 (review_spec)
routes back with feedback. Revision prompts include cumulative feedback
history to prevent regression.

This node populates:
- spec_draft: Generated Implementation Spec markdown
- spec_path: Path where the draft was saved in the audit trail
- review_iteration: Incremented on revision cycles
- error_message: "" on success, error text on failure
"""

import logging
import re
from pathlib import Path
from typing import Any

from assemblyzero.core.llm_provider import get_cumulative_cost, get_provider
from assemblyzero.utils.cost_tracker import accumulate_node_cost, accumulate_node_tokens
from assemblyzero.core.section_utils import (
    build_targeted_prompt,
    extract_sections,
    identify_changed_sections,
)
from assemblyzero.workflows.requirements.audit import (
    get_repo_structure,
    load_template,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.implementation_spec.state import (
    ImplementationSpecState,
    PatternRef,
)
from assemblyzero.workflows.implementation_spec.nodes.retry_prompt_builder import (
    RetryContext,
    build_retry_prompt,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Template path relative to assemblyzero_root
SPEC_TEMPLATE_PATH = Path("docs/standards/0701-implementation-spec-template.md")

# Default drafter model spec
DEFAULT_DRAFTER = "claude:opus"

# Maximum characters for pattern reference excerpts in the prompt
MAX_PATTERN_EXCERPT_CHARS = 3_000

# Maximum characters for a single file snapshot in the prompt
MAX_SNAPSHOT_CHARS = 10_000

# Maximum total prompt content chars (to avoid token limits)
MAX_TOTAL_PROMPT_CHARS = 120_000


# =============================================================================
# System Prompt
# =============================================================================

DRAFTER_SYSTEM_PROMPT = """\
You are a technical architect creating an Implementation Specification.

An Implementation Spec bridges the gap between a Low-Level Design (LLD) and \
autonomous code implementation. It must contain enough concrete detail for an \
AI agent to implement the changes with >80% first-try success rate.

CRITICAL FORMATTING RULES:
- Start DIRECTLY with the document title (# heading)
- Do NOT include any preamble, explanation, or meta-commentary
- Output ONLY the raw markdown content
- First line MUST be the title starting with #

QUALITY REQUIREMENTS:
- Every "Modify" file MUST include a current state excerpt showing the code \
that will be changed
- Every data structure MUST have at least one concrete JSON/YAML example \
with realistic values (not just TypedDict definitions)
- Every function signature MUST have input/output examples with actual values
- Change instructions MUST be specific enough to generate diffs \
(line-level guidance, before/after snippets)
- Pattern references MUST include file:line locations pointing to real code

STRUCTURE:
Follow the provided template exactly. Include ALL sections. \
Do not skip or abbreviate any section."""


# =============================================================================
# Main Node
# =============================================================================


def generate_spec(state: ImplementationSpecState) -> dict[str, Any]:
    """N2: Generate Implementation Spec draft using Claude.

    Issue #304: Implementation Readiness Review Workflow

    Steps:
    1. Determine if this is an initial draft or revision
    2. Load Implementation Spec template from assemblyzero_root
    3. Build prompt with LLD content, codebase snapshots, and patterns
    4. Call configured drafter LLM
    5. Strip any preamble from response
    6. Save draft to audit trail
    7. Return state updates

    Args:
        state: Current workflow state. Requires:
            - lld_content: Raw LLD markdown (from N0)
            - current_state_snapshots: File excerpts (from N1)
            - pattern_references: Similar patterns (from N1)
            - assemblyzero_root: Path to AssemblyZero installation
            - repo_root: Target repository root path

    Returns:
        Dict with state field updates:
        - spec_draft: Generated Implementation Spec markdown
        - spec_path: Path where the draft was saved
        - review_iteration: Updated iteration count
        - error_message: "" on success, error text on failure
    """
    # Extract state
    assemblyzero_root = Path(state.get("assemblyzero_root", ""))
    repo_root = state.get("repo_root", "")
    mock_mode = state.get("config_mock_mode", False)
    issue_number = state.get("issue_number", 0)

    # Determine revision state
    review_iteration = state.get("review_iteration", 0)
    existing_draft = state.get("spec_draft", "")
    review_feedback = state.get("review_feedback", "")
    completeness_issues = state.get("completeness_issues", [])
    validation_passed = state.get("validation_passed", False)

    is_revision = bool(
        existing_draft and (review_feedback or completeness_issues)
    )

    # Issue #525: Resume from persisted draft if available (skip expensive LLM call)
    if not is_revision and not existing_draft:
        audit_dir_str = state.get("audit_dir", "")
        if audit_dir_str:
            audit_dir = Path(audit_dir_str)
            if audit_dir.exists():
                # Find most recent spec-draft in lineage
                drafts = sorted(audit_dir.glob("*-spec-draft.md"), reverse=True)
                if drafts:
                    recovered = drafts[0].read_text(encoding="utf-8")
                    if recovered.strip():
                        lines = len(recovered.splitlines())
                        print(f"\n[N2] Recovered existing draft from {drafts[0].name} ({lines} lines) — skipping LLM call")
                        return {
                            "spec_draft": recovered,
                            "spec_path": str(drafts[0]),
                            "review_iteration": review_iteration,
                            "completeness_issues": [],
                            "error_message": "",
                        }

    if is_revision:
        review_iteration += 1
        print(
            f"\n[N2] Generating Implementation Spec revision "
            f"(iteration {review_iteration})..."
        )
    else:
        print("\n[N2] Generating initial Implementation Spec draft...")

    # -------------------------------------------------------------------------
    # Load template
    # -------------------------------------------------------------------------
    try:
        template = load_template(SPEC_TEMPLATE_PATH, assemblyzero_root)
    except FileNotFoundError as e:
        print(f"    ERROR: Template not found: {e}")
        return {"error_message": str(e)}

    # -------------------------------------------------------------------------
    # Build prompt
    # Issue #642: Use build_retry_prompt() with tiered context pruning when
    # retry_count >= 1 in workflow state.
    # -------------------------------------------------------------------------
    retry_count = state.get("retry_count", 0)

    if retry_count >= 1:
        # Build retry prompt with tiered context pruning (#642)
        retry_ctx = RetryContext(
            lld_content=state.get("lld_content", ""),
            target_file=state.get("target_file", ""),
            error_message=state.get("error_message", ""),
            retry_count=retry_count,
            previous_attempt_snippet=state.get("previous_attempt_snippet", None),
            completed_files=state.get("completed_files", []),
        )
        result = build_retry_prompt(retry_ctx)
        prompt = result["prompt_text"]
        logger.info(
            "Retry prompt built: tier=%d, tokens=%d, file=%s",
            result["tier"],
            result["estimated_tokens"],
            state.get("target_file", ""),
        )
    else:
        prompt = build_drafter_prompt(
            lld_content=state.get("lld_content", ""),
            current_state=state.get("current_state_snapshots", {}),
            patterns=state.get("pattern_references", []),
            template=template,
            issue_number=issue_number,
            existing_draft=existing_draft if is_revision else "",
            review_feedback=review_feedback if is_revision else "",
            completeness_issues=completeness_issues if is_revision else [],
            repo_root=repo_root,
            files_to_modify=state.get("files_to_modify", []),
            project_context=state.get("project_context", ""),
            import_dependencies=state.get("import_dependencies", ""),
            repo_structure=state.get("repo_structure", ""),
        )

    # -------------------------------------------------------------------------
    # Issue #486: Pre-flight check — verify Gemini available before expensive Claude call
    # -------------------------------------------------------------------------
    if not mock_mode:
        from assemblyzero.core.preflight import check_gemini_available
        preflight = check_gemini_available()
        print(f"    [PREFLIGHT] Gemini: {preflight.available_credentials}/{preflight.total_credentials} credentials")
        if not preflight.passed:
            warnings_str = ", ".join(preflight.warnings)
            return {
                "error_message": f"[PREFLIGHT] Gemini unavailable: {warnings_str}",
                "previous_review_feedback": review_feedback,
            }

    # -------------------------------------------------------------------------
    # Get drafter provider
    # -------------------------------------------------------------------------
    if mock_mode:
        drafter_spec = "mock:draft"
    else:
        drafter_spec = state.get("config_drafter", DEFAULT_DRAFTER)

    try:
        drafter = get_provider(drafter_spec)
    except ValueError as e:
        print(f"    ERROR: Invalid drafter: {e}")
        return {"error_message": f"Invalid drafter: {e}"}

    print(f"    Drafter: {drafter_spec}")

    # -------------------------------------------------------------------------
    # Call drafter LLM
    # -------------------------------------------------------------------------
    cost_before = get_cumulative_cost()
    result = drafter.invoke(
        system_prompt=DRAFTER_SYSTEM_PROMPT,
        content=prompt,
        timeout_seconds=600,  # 10 min — impl specs are large
    )
    node_cost_usd = get_cumulative_cost() - cost_before

    if not result.success:
        print(f"    ERROR: {result.error_message}")
        return {"error_message": f"Drafter failed: {result.error_message}"}

    # Issue #476: Budget check
    cumulative = get_cumulative_cost()
    budget = state.get("cost_budget_usd", 0.0)
    if budget > 0 and cumulative > budget:
        msg = f"[BUDGET] ${cumulative:.2f} exceeds ${budget:.2f} budget. Halting."
        print(f"    {msg}")
        return {"error_message": msg}

    spec_content = result.response or ""

    # -------------------------------------------------------------------------
    # Strip preamble (safety: Claude sometimes adds text before the # heading)
    # -------------------------------------------------------------------------
    spec_content = _strip_preamble(spec_content)

    # -------------------------------------------------------------------------
    # Save to audit trail
    # -------------------------------------------------------------------------
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None

    spec_path = None
    if audit_dir and audit_dir.exists():
        file_num = next_file_number(audit_dir)
        spec_path = save_audit_file(
            audit_dir, file_num, "spec-draft.md", spec_content
        )

    # -------------------------------------------------------------------------
    # Report results
    # -------------------------------------------------------------------------
    draft_lines = len(spec_content.splitlines()) if spec_content else 0
    print(f"    Generated {draft_lines} lines")
    if spec_path:
        print(f"    Saved: {spec_path.name}")

    # Issue #511: Accumulate per-node cost
    node_costs = accumulate_node_cost(
        dict(state.get("node_costs", {})), "generate_spec", node_cost_usd,
    )
    node_tokens = accumulate_node_tokens(
        dict(state.get("node_tokens", {})),
        "generate_spec",
        result.input_tokens,
        result.output_tokens,
    )

    return {
        "spec_draft": spec_content,
        "spec_path": str(spec_path) if spec_path else "",
        "review_iteration": review_iteration,
        "completeness_issues": [],  # Clear after use
        "previous_review_feedback": review_feedback,  # Issue #486: Save for two-strike
        "previous_spec_draft": state.get("spec_draft", ""),  # Issue #491: Save for diff-aware review
        "review_feedback": "",  # Clear after use
        "error_message": "",
        "node_costs": node_costs,  # Issue #511
        "node_tokens": node_tokens,  # Issue #511
    }


# =============================================================================
# Prompt Building
# =============================================================================


def build_drafter_prompt(
    lld_content: str,
    current_state: dict[str, str],
    patterns: list[PatternRef],
    template: str = "",
    issue_number: int = 0,
    existing_draft: str = "",
    review_feedback: str = "",
    completeness_issues: list[str] | None = None,
    repo_root: str = "",
    files_to_modify: list | None = None,
    project_context: str = "",
    import_dependencies: str = "",
    repo_structure: str = "",
) -> str:
    """Build the prompt for Claude spec generation.

    Constructs either an initial draft prompt or a revision prompt
    depending on whether existing_draft and feedback are provided.

    The prompt includes:
    - Full LLD content
    - Project context (CLAUDE.md, README, metadata) — Issue #409
    - Current state snapshots for each file to be modified
    - Import dependencies between files — Issue #409
    - Pattern references with code excerpts
    - Implementation Spec template (if available)
    - Revision feedback (if revising)

    Args:
        lld_content: Raw LLD markdown content.
        current_state: Mapping of file_path -> code excerpt.
        patterns: List of PatternRef for similar implementation patterns.
        template: Implementation Spec template content.
        issue_number: GitHub issue number.
        existing_draft: Current spec draft (for revision mode).
        review_feedback: Feedback from Gemini review (for revision).
        completeness_issues: List of completeness check failures (for revision).
        repo_root: Target repository root path (for repo structure display).
        files_to_modify: List of FileToModify dicts from the LLD.
        project_context: CLAUDE.md/README/metadata context (Issue #409).
        import_dependencies: Cross-file import map (Issue #409).

    Returns:
        Complete prompt string for the drafter LLM.
    """
    if completeness_issues is None:
        completeness_issues = []
    if files_to_modify is None:
        files_to_modify = []

    is_revision = bool(existing_draft and (review_feedback or completeness_issues))

    if is_revision:
        return _build_revision_prompt(
            lld_content=lld_content,
            current_state=current_state,
            patterns=patterns,
            template=template,
            issue_number=issue_number,
            existing_draft=existing_draft,
            review_feedback=review_feedback,
            completeness_issues=completeness_issues,
            repo_root=repo_root,
            files_to_modify=files_to_modify,
            repo_structure=repo_structure,
        )
    else:
        return _build_initial_prompt(
            lld_content=lld_content,
            current_state=current_state,
            patterns=patterns,
            template=template,
            issue_number=issue_number,
            files_to_modify=files_to_modify,
            project_context=project_context,
            import_dependencies=import_dependencies,
        )


# =============================================================================
# Initial Prompt
# =============================================================================


def _build_initial_prompt(
    lld_content: str,
    current_state: dict[str, str],
    patterns: list[PatternRef],
    template: str,
    issue_number: int,
    files_to_modify: list,
    project_context: str = "",
    import_dependencies: str = "",
) -> str:
    """Build prompt for initial spec generation.

    Args:
        lld_content: Raw LLD markdown content.
        current_state: File path -> code excerpt mapping.
        patterns: Pattern references from codebase analysis.
        template: Implementation Spec template.
        issue_number: GitHub issue number.
        files_to_modify: List of FileToModify dicts.
        project_context: CLAUDE.md/README/metadata context (Issue #409).
        import_dependencies: Cross-file import map (Issue #409).

    Returns:
        Initial draft prompt string.
    """
    sections: list[str] = []

    sections.append(
        "IMPORTANT: Output ONLY the markdown content. "
        "Start with # title. No preamble."
    )

    # LLD content
    sections.append(f"## LLD Content (Issue #{issue_number})\n\n{lld_content}")

    # Project context (Issue #409 Gap 1)
    if project_context:
        sections.append(project_context)

    # Current state snapshots
    snapshot_section = _format_current_state_section(current_state, files_to_modify)
    if snapshot_section:
        sections.append(snapshot_section)

    # Import dependencies (Issue #409 Gap 3)
    if import_dependencies:
        sections.append(import_dependencies)

    # Pattern references
    pattern_section = _format_patterns_section(patterns)
    if pattern_section:
        sections.append(pattern_section)

    # Template
    if template:
        sections.append(f"## Implementation Spec Template (follow this structure)\n\n{template}")

    # Final instruction
    sections.append(
        "Create a complete Implementation Spec following the template structure.\n"
        "Ensure EVERY file listed in the LLD has concrete implementation guidance.\n"
        f"This spec is for Issue #{issue_number}.\n"
        "START YOUR RESPONSE WITH THE # HEADING. NO PREAMBLE."
    )

    prompt = "\n\n".join(sections)

    # Guard against excessively large prompts
    if len(prompt) > MAX_TOTAL_PROMPT_CHARS:
        prompt = _truncate_prompt(prompt)

    return prompt


# =============================================================================
# Revision Prompt
# =============================================================================


def _build_revision_prompt(
    lld_content: str,
    current_state: dict[str, str],
    patterns: list[PatternRef],
    template: str,
    issue_number: int,
    existing_draft: str,
    review_feedback: str,
    completeness_issues: list[str],
    repo_root: str,
    files_to_modify: list,
    repo_structure: str = "",
) -> str:
    """Build prompt for spec revision based on feedback.

    Args:
        lld_content: Raw LLD markdown content.
        current_state: File path -> code excerpt mapping.
        patterns: Pattern references from codebase analysis.
        template: Implementation Spec template.
        issue_number: GitHub issue number.
        existing_draft: Current spec draft to revise.
        review_feedback: Gemini review feedback.
        completeness_issues: Completeness check failures.
        repo_root: Target repo root (for structure display).
        files_to_modify: List of FileToModify dicts.

    Returns:
        Revision prompt string.
    """
    # Issue #489: Try section-level revision for focused changes
    if review_feedback and existing_draft:
        draft_sections = extract_sections(existing_draft)
        changed = identify_changed_sections(review_feedback, draft_sections)
        if changed:
            targeted = build_targeted_prompt(
                sections=draft_sections,
                changed_headings=changed,
                template=template,
                feedback=review_feedback,
            )
            if targeted:
                parts = [
                    "IMPORTANT: Output ONLY the markdown content. "
                    "Start with # title. No preamble.",
                    targeted,
                    f"## Original LLD (Issue #{issue_number})\n\n{lld_content}",
                    "CRITICAL REVISION INSTRUCTIONS:\n"
                    "1. Fix ALL issues from feedback\n"
                    "2. PRESERVE sections marked [UNCHANGED] exactly as-is\n"
                    "3. ONLY modify sections marked [REVISE]\n"
                    "4. Keep ALL template sections intact\n\n"
                    "START YOUR RESPONSE WITH THE # HEADING. NO PREAMBLE.",
                ]
                prompt = "\n\n".join(parts)
                if len(prompt) <= MAX_TOTAL_PROMPT_CHARS:
                    return prompt

    # Fallback: full revision prompt
    sections: list[str] = []

    sections.append(
        "IMPORTANT: Output ONLY the markdown content. "
        "Start with # title. No preamble."
    )

    # Completeness issues (highest priority — from N3 mechanical validation)
    if completeness_issues:
        issues_text = "## MECHANICAL COMPLETENESS ERRORS (MUST FIX FIRST)\n\n"
        issues_text += (
            "The following errors were found by automated completeness "
            "validation. These MUST be fixed before the spec can proceed:\n\n"
        )
        for issue in completeness_issues:
            issues_text += f"- **ERROR:** {issue}\n"

        # Show repo structure to help fix path-related issues
        # Issue #490: Use cached repo_structure, fallback to inline call
        if repo_root:
            repo_structure = repo_structure or get_repo_structure(repo_root)
            issues_text += "\n## ACTUAL REPOSITORY STRUCTURE\n\n"
            issues_text += (
                "**Use ONLY these existing directories** "
                "(or explicitly document new ones):\n\n"
            )
            issues_text += f"```\n{repo_structure}\n```\n"

        sections.append(issues_text)

    # Review feedback (from N5 Gemini review)
    if review_feedback:
        sections.append(
            "## Gemini Readiness Review Feedback\n\n"
            f"{review_feedback}"
        )

    # Current draft to revise
    sections.append(f"## Current Draft (to revise)\n\n{existing_draft}")

    # Current state snapshots (for reference during revision)
    snapshot_section = _format_current_state_section(current_state, files_to_modify)
    if snapshot_section:
        sections.append(snapshot_section)

    # Original LLD for reference
    sections.append(f"## Original LLD (Issue #{issue_number})\n\n{lld_content}")

    # Template
    if template:
        sections.append(
            f"## Implementation Spec Template (REQUIRED STRUCTURE)\n\n{template}"
        )

    # Revision instructions
    sections.append(
        "CRITICAL REVISION INSTRUCTIONS:\n"
        "1. Fix ALL mechanical completeness errors FIRST "
        "(missing excerpts, missing examples)\n"
        "2. Implement EVERY change requested by Gemini review feedback\n"
        "3. PRESERVE sections that weren't flagged\n"
        "4. ONLY modify sections that need changes\n"
        "5. Keep ALL template sections intact\n"
        "6. Ensure every Modify file has a current state excerpt\n"
        "7. Ensure every function has concrete input/output examples\n"
        "8. Ensure every data structure has a concrete JSON/YAML example\n\n"
        "Revise the draft to address ALL feedback above.\n"
        "START YOUR RESPONSE WITH THE # HEADING. NO PREAMBLE."
    )

    prompt = "\n\n".join(sections)

    # Guard against excessively large prompts
    if len(prompt) > MAX_TOTAL_PROMPT_CHARS:
        prompt = _truncate_prompt(prompt)

    return prompt


# =============================================================================
# Prompt Section Formatters
# =============================================================================


def _format_current_state_section(
    current_state: dict[str, str],
    files_to_modify: list,
) -> str:
    """Format current state snapshots into a prompt section.

    Args:
        current_state: File path -> code excerpt mapping.
        files_to_modify: List of FileToModify dicts for metadata.

    Returns:
        Formatted section string, or empty string if no snapshots.
    """
    if not current_state:
        return ""

    parts: list[str] = ["## Current State of Files to Modify\n"]

    # Build a lookup for change types
    change_types: dict[str, str] = {}
    descriptions: dict[str, str] = {}
    for f in files_to_modify:
        path = f.get("path", "") if isinstance(f, dict) else ""
        change_types[path] = f.get("change_type", "Modify") if isinstance(f, dict) else "Modify"
        descriptions[path] = f.get("description", "") if isinstance(f, dict) else ""

    for file_path, excerpt in current_state.items():
        change_type = change_types.get(file_path, "Modify")
        description = descriptions.get(file_path, "")

        # Truncate very large excerpts
        if len(excerpt) > MAX_SNAPSHOT_CHARS:
            excerpt = excerpt[:MAX_SNAPSHOT_CHARS] + "\n# ... (truncated)\n"

        header = f"### `{file_path}` ({change_type})"
        if description:
            header += f"\n*{description}*"

        parts.append(f"{header}\n\n```python\n{excerpt}\n```")

    return "\n\n".join(parts)


def _format_patterns_section(patterns: list[PatternRef]) -> str:
    """Format pattern references into a prompt section.

    Args:
        patterns: List of PatternRef dicts from codebase analysis.

    Returns:
        Formatted section string, or empty string if no patterns.
    """
    if not patterns:
        return ""

    parts: list[str] = [
        "## Similar Implementation Patterns\n\n"
        "Use these existing patterns as reference for consistent implementation style:"
    ]

    for ref in patterns:
        file_path = ref.get("file_path", "")
        start_line = ref.get("start_line", 0)
        end_line = ref.get("end_line", 0)
        pattern_type = ref.get("pattern_type", "")
        relevance = ref.get("relevance", "")

        parts.append(
            f"- **{pattern_type}** at `{file_path}:{start_line}-{end_line}`"
            f"\n  {relevance}"
        )

    return "\n".join(parts)


# =============================================================================
# Utility Functions
# =============================================================================


def _strip_preamble(content: str) -> str:
    """Strip any preamble text before the first # heading.

    Claude sometimes adds explanatory text before the actual spec content
    despite system prompt instructions. This strips it.

    Args:
        content: Raw LLM response content.

    Returns:
        Content starting from the first # heading.
    """
    if not content:
        return content

    match = re.search(r"^#\s+", content, re.MULTILINE)
    if match:
        heading_pos = match.start()
        if heading_pos > 0:
            stripped = content[:heading_pos].strip()
            if stripped:
                print(
                    f"    [WARN] Stripped {len(stripped)} chars of preamble "
                    f"before # heading"
                )
            return content[heading_pos:]

    return content


def _truncate_prompt(prompt: str) -> str:
    """Truncate prompt by dropping lowest-priority sections first.

    Issue #409 Gap 4: Instead of blunt 40%/30% string splitting that
    loses file excerpts mid-content, parse the prompt into ## sections
    and drop whole sections in priority order.

    Priority (highest = kept longest):
      Instructions/preamble, LLD, Template, Current Draft,
      Completeness Errors, File Excerpts, Import Dependencies,
      Patterns, Project Context

    Args:
        prompt: Full prompt content.

    Returns:
        Truncated prompt fitting within MAX_TOTAL_PROMPT_CHARS.
    """
    if len(prompt) <= MAX_TOTAL_PROMPT_CHARS:
        return prompt

    original_len = len(prompt)

    # Split into sections by ## headers
    sections = _split_into_sections(prompt)

    # Priority keywords: lower index = higher priority (kept longer).
    # Matching is case-insensitive substring on the ## header text.
    _priority_keywords = [
        "lld content",
        "implementation spec template",
        "current draft",
        "mechanical completeness",
        "current state",
        "gemini",
        "import dependencies",
        "similar implementation patterns",
        "project context",
    ]

    def _section_priority(section: dict) -> int:
        header = section["header"].lower()
        if not header:
            # Preamble / final instructions — highest priority
            return -1
        for i, keyword in enumerate(_priority_keywords):
            if keyword in header:
                return i
        # Unknown sections — drop before known ones
        return len(_priority_keywords)

    # Build a droppable list sorted by priority (lowest priority first)
    droppable = sorted(
        [s for s in sections if _section_priority(s) > 0],
        key=_section_priority,
        reverse=True,
    )

    total = sum(len(s["content"]) for s in sections)
    dropped: list[str] = []

    while total > MAX_TOTAL_PROMPT_CHARS and droppable:
        victim = droppable.pop(0)
        sections.remove(victim)
        total -= len(victim["content"])
        dropped.append(victim["header"] or "(unnamed)")

    if dropped:
        # Insert a notice where content was removed
        notice = (
            "\n\n<!-- CONTEXT TRIMMED: Dropped sections to fit budget: "
            + ", ".join(dropped)
            + " -->\n"
        )
        sections.append({"header": "", "content": notice, "order": 999})

    # Reassemble in original order
    sections.sort(key=lambda s: s["order"])
    result = "\n\n".join(s["content"] for s in sections)

    # Last resort: if still over budget, hard-truncate at limit
    if len(result) > MAX_TOTAL_PROMPT_CHARS:
        result = result[:MAX_TOTAL_PROMPT_CHARS]

    print(
        f"    [WARN] Prompt truncated from {original_len:,} to "
        f"{len(result):,} chars (dropped: {', '.join(dropped) if dropped else 'none'})"
    )

    return result


def _split_into_sections(prompt: str) -> list[dict]:
    """Split a prompt string into sections demarcated by ## headers.

    Each section is a dict with:
      - header: The ## header text (empty string for preamble/tail).
      - content: The full text including the header line.
      - order: Original position index for reassembly.

    Args:
        prompt: The full prompt string.

    Returns:
        List of section dicts in original order.
    """
    sections: list[dict] = []
    current_header = ""
    current_lines: list[str] = []

    for line in prompt.split("\n"):
        if line.startswith("## "):
            # Flush previous section
            if current_lines:
                sections.append({
                    "header": current_header,
                    "content": "\n".join(current_lines),
                    "order": len(sections),
                })
            current_header = line[3:].strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    # Flush last section
    if current_lines:
        sections.append({
            "header": current_header,
            "content": "\n".join(current_lines),
            "order": len(sections),
        })

    return sections
```

Modify this file according to the LLD specification.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_lld_section_extractor.py
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
    """Tests for extract_file_spec_section()."""

    def test_exact_path_match_returns_confidence_1(self, full_lld: str) -> None:
        """T090: Exact path match yields confidence=1.0."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/services/alpha_service.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "Alpha service" in result["section_body"]
        assert "create_alpha" in result["section_body"]

    def test_stem_match_returns_lower_confidence(self, full_lld: str) -> None:
        """T100: Stem-only match yields 0.0 < confidence < 1.0."""
        # Construct a target path not literally in the LLD but whose stem is
        result = extract_file_spec_section(
            full_lld, "some/other/path/alpha_service.py"
        )
        assert result is not None
        assert 0.0 < result["match_confidence"] < 1.0

    def test_no_match_returns_none(self, full_lld: str) -> None:
        """T110: No match returns None."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/nonexistent/zzz_module.py"
        )
        assert result is None

    def test_empty_lld_raises_value_error(self) -> None:
        """T120: Empty lld_content raises ValueError."""
        with pytest.raises(ValueError, match="lld_content must not be empty"):
            extract_file_spec_section("", "assemblyzero/foo.py")

    def test_whitespace_only_lld_raises_value_error(self) -> None:
        """Edge case: whitespace-only lld_content raises ValueError."""
        with pytest.raises(ValueError, match="lld_content must not be empty"):
            extract_file_spec_section("   \n\t  ", "assemblyzero/foo.py")

    def test_minimal_lld_exact_match(self, minimal_lld: str) -> None:
        """Minimal LLD with single section returns exact match."""
        result = extract_file_spec_section(
            minimal_lld, "assemblyzero/utils/tiny_helper.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "tiny_format" in result["section_body"]

    def test_returns_extracted_section_typed_dict(self, full_lld: str) -> None:
        """Result has all required TypedDict keys."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/services/alpha_service.py"
        )
        assert result is not None
        assert "section_heading" in result
        assert "section_body" in result
        assert "match_confidence" in result

    def test_section_body_includes_heading(self, full_lld: str) -> None:
        """Section body includes the heading line."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/services/alpha_service.py"
        )
        assert result is not None
        assert result["section_heading"] in result["section_body"]

    def test_returns_most_relevant_section(self, full_lld: str) -> None:
        """Returns the highest-scoring section, not an unrelated one."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/workflows/epsilon_flow.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "epsilon" in result["section_body"].lower()

    def test_exact_match_excludes_unrelated_sections(self, full_lld: str) -> None:
        """Exact match result does not contain padding sections."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/utils/delta_helper.py"
        )
        assert result is not None
        assert "Padding Section" not in result["section_body"]

    def test_beta_service_match(self, full_lld: str) -> None:
        """Beta service section extracted correctly."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/services/beta_service.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "connect_beta" in result["section_body"]

    def test_gamma_model_match(self, full_lld: str) -> None:
        """Gamma model section extracted correctly."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/models/gamma_model.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "GammaModel" in result["section_body"]


class TestSplitLldIntoSections:
    """Tests for _split_lld_into_sections()."""

    def test_splits_at_heading_boundaries(self) -> None:
        """Sections are split at ## and ### boundaries."""
        content = "# Title\n\nPreamble.\n\n## A\n\nBody A.\n\n## B\n\nBody B.\n"
        sections = _split_lld_into_sections(content)
        assert len(sections) == 3
        assert sections[0][0] == "# Title"
        assert sections[1][0] == "## A"
        assert sections[2][0] == "## B"

    def test_no_headings_returns_full_content(self) -> None:
        """Content without headings returns single section."""
        content = "Just some text\nwith no headings.\n"
        sections = _split_lld_into_sections(content)
        assert len(sections) == 1
        assert sections[0][0] == ""
        assert sections[0][1] == content

    def test_section_bodies_contain_headings(self) -> None:
        """Each section body includes its own heading."""
        content = "## Section A\n\nContent A.\n\n## Section B\n\nContent B.\n"
        sections = _split_lld_into_sections(content)
        assert "## Section A" in sections[0][1]
        assert "## Section B" in sections[1][1]

    def test_section_bodies_are_contiguous(self) -> None:
        """All section bodies together reconstruct the full document."""
        content = "# Title\n\nPreamble.\n\n## A\n\nBody A.\n\n## B\n\nBody B.\n"
        sections = _split_lld_into_sections(content)
        reconstructed = "".join(body for _, body in sections)
        assert reconstructed == content

    def test_handles_triple_hash_headings(self) -> None:
        """### headings are also split boundaries."""
        content = "## Parent\n\nParent body.\n\n### Child\n\nChild body.\n"
        sections = _split_lld_into_sections(content)
        assert len(sections) == 2
        assert sections[0][0] == "## Parent"
        assert sections[1][0] == "### Child"

    def test_single_heading_only(self) -> None:
        """Single # heading returns one section covering all content."""
        content = "# Only Title\n\nAll the content.\n"
        sections = _split_lld_into_sections(content)
        assert len(sections) == 1
        assert sections[0][0] == "# Only Title"
        assert sections[0][1] == content

    def test_full_lld_fixture_splits_correctly(self, full_lld: str) -> None:
        """Full LLD fixture produces multiple sections."""
        sections = _split_lld_into_sections(full_lld)
        assert len(sections) > 5

    def test_headings_matched_correctly(self) -> None:
        """Heading text is captured accurately."""
        content = "## Section for assemblyzero/services/alpha_service.py\n\nContent.\n"
        sections = _split_lld_into_sections(content)
        assert sections[0][0] == "## Section for assemblyzero/services/alpha_service.py"


class TestScoreSectionForFile:
    """Tests for _score_section_for_file()."""

    def test_exact_path_scores_1(self) -> None:
        """Exact path in section scores 1.0."""
        section = "## Section for assemblyzero/services/alpha.py\n\nDetails."
        assert _score_section_for_file(section, "assemblyzero/services/alpha.py") == 1.0

    def test_stem_match_scores_0_6(self) -> None:
        """Filename stem match scores 0.6."""
        section = "## Alpha Module\n\nalpha details and alpha reference."
        assert _score_section_for_file(section, "some/path/alpha.py") == 0.6

    def test_directory_match_scores_0_3(self) -> None:
        """Directory path match scores 0.3."""
        section = "## Overview of assemblyzero/services/ directory.\n\nGeneral."
        assert (
            _score_section_for_file(
                section, "assemblyzero/services/nonexistent_file.py"
            )
            == 0.3
        )

    def test_no_match_scores_0(self) -> None:
        """No match scores 0.0."""
        section = "## Security Notes\n\nNothing relevant here."
        assert (
            _score_section_for_file(section, "assemblyzero/services/alpha.py") == 0.0
        )

    def test_exact_match_beats_stem_match(self) -> None:
        """Exact path match (1.0) outscores stem match (0.6)."""
        exact_section = "## Section for assemblyzero/foo/bar.py\n\nContent."
        stem_section = "## Bar Module\n\nbar.py docs."
        exact_score = _score_section_for_file(exact_section, "assemblyzero/foo/bar.py")
        stem_score = _score_section_for_file(stem_section, "assemblyzero/foo/bar.py")
        assert exact_score > stem_score

    def test_stem_match_beats_directory_match(self) -> None:
        """Stem match (0.6) outscores directory match (0.3)."""
        stem_section = "## Alpha Module\n\nalpha_service referenced here."
        dir_section = "## Overview of assemblyzero/services/\n\nServices overview."
        stem_score = _score_section_for_file(
            stem_section, "assemblyzero/services/alpha_service.py"
        )
        dir_score = _score_section_for_file(
            dir_section, "assemblyzero/services/alpha_service.py"
        )
        assert stem_score > dir_score

    def test_backslash_path_normalized(self) -> None:
        """Windows-style backslash paths are normalized before scoring."""
        section = "## Section for assemblyzero/services/alpha.py\n\nDetails."
        # Target file with backslashes should still match
        score = _score_section_for_file(section, "assemblyzero\\services\\alpha.py")
        assert score == 1.0

    def test_empty_section_scores_0(self) -> None:
        """Empty section text scores 0.0."""
        assert _score_section_for_file("", "assemblyzero/services/alpha.py") == 0.0

    def test_padding_section_scores_0_for_file(self) -> None:
        """Padding sections with no file references score 0.0."""
        section = "## Padding Section Alpha\n\nLorem ipsum dolor sit amet."
        assert (
            _score_section_for_file(section, "assemblyzero/services/alpha_service.py")
            == 0.0
        )

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_retry_prompt_builder.py
"""Unit tests for retry prompt builder.

Issue #642: Tests for build_retry_prompt() with tiered context pruning.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
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
    full_lld: str,
    *,
    retry_count: int = 1,
    target_file: str = "assemblyzero/services/alpha_service.py",
    error_message: str = "SyntaxError: unexpected indent at line 45",
    previous_attempt_snippet: str | None = None,
    completed_files: list[str] | None = None,
) -> RetryContext:
    """Helper to construct a RetryContext with defaults."""
    return RetryContext(
        lld_content=full_lld,
        target_file=target_file,
        error_message=error_message,
        retry_count=retry_count,
        previous_attempt_snippet=previous_attempt_snippet,
        completed_files=completed_files or [],
    )


class TestBuildRetryPrompt:
    """Tests for build_retry_prompt()."""

    def test_tier1_returns_full_lld(self, full_lld: str) -> None:
        """T010: retry_count=1 returns tier 1 with full LLD content."""
        ctx = _make_ctx(full_lld, retry_count=1)
        result = build_retry_prompt(ctx)
        assert result["tier"] == 1
        # Tier 1 should contain content from multiple sections
        assert "beta_service" in result["prompt_text"].lower()
        assert "gamma_model" in result["prompt_text"].lower()

    def test_tier2_excludes_bulk_lld(self, full_lld: str) -> None:
        """T020: retry_count=2 returns tier 2 without padding sections."""
        ctx = _make_ctx(
            full_lld,
            retry_count=2,
            previous_attempt_snippet="def create_alpha():\n    pass",
        )
        result = build_retry_prompt(ctx)
        assert result["tier"] == 2
        assert "Padding Section Gamma" not in result["prompt_text"]
        assert "alpha_service" in result["prompt_text"].lower()

    def test_tier2_tokens_le_50pct_tier1(self, full_lld: str) -> None:
        """T030: Tier 2 estimated_tokens <= 50% of Tier 1."""
        ctx_t1 = _make_ctx(full_lld, retry_count=1)
        result_t1 = build_retry_prompt(ctx_t1)

        ctx_t2 = _make_ctx(
            full_lld,
            retry_count=2,
            previous_attempt_snippet="def create_alpha():\n    pass",
        )
        result_t2 = build_retry_prompt(ctx_t2)

        assert result_t2["estimated_tokens"] <= 0.50 * result_t1["estimated_tokens"]

    def test_tier2_fallback_when_no_section(self, full_lld: str) -> None:
        """T040: Falls back to tier 1 when target file not found in LLD."""
        ctx = _make_ctx(
            full_lld,
            retry_count=2,
            target_file="assemblyzero/nonexistent/zzz_module.py",
            previous_attempt_snippet="some code here",
        )
        result = build_retry_prompt(ctx)
        assert result["tier"] == 1  # Fallback

    def test_tier2_fallback_emits_warning(
        self, full_lld: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        """T040 (cont): Fallback emits a warning log."""
        ctx = _make_ctx(
            full_lld,
            retry_count=2,
            target_file="assemblyzero/nonexistent/zzz_module.py",
            previous_attempt_snippet="some code here",
        )
        with caplog.at_level(logging.WARNING):
            build_retry_prompt(ctx)
        assert "falling back to tier 1" in caplog.text.lower()

    def test_retry_count_zero_raises(self, full_lld: str) -> None:
        """T050: retry_count=0 raises ValueError."""
        ctx = _make_ctx(full_lld, retry_count=0)
        with pytest.raises(ValueError, match="retry_count must be >= 1"):
            build_retry_prompt(ctx)

    def test_tier2_snippet_none_raises(self, full_lld: str) -> None:
        """T060: retry_count=2 with snippet=None raises ValueError."""
        ctx = _make_ctx(full_lld, retry_count=2, previous_attempt_snippet=None)
        with pytest.raises(ValueError, match="Tier 2 requires previous_attempt_snippet"):
            build_retry_prompt(ctx)

    def test_completed_files_excluded_tier1(self, full_lld: str) -> None:
        """T150: Completed files are excluded from tier 1 prompt."""
        ctx = _make_ctx(
            full_lld,
            retry_count=1,
            completed_files=["assemblyzero/services/beta_service.py"],
        )
        result = build_retry_prompt(ctx)
        assert "Beta service provides" not in result["prompt_text"]

    def test_retry_count_negative_raises(self, full_lld: str) -> None:
        """retry_count < 0 raises ValueError."""
        ctx = _make_ctx(full_lld, retry_count=-1)
        with pytest.raises(ValueError, match="retry_count must be >= 1"):
            build_retry_prompt(ctx)

    def test_empty_lld_raises(self) -> None:
        """Empty lld_content raises ValueError."""
        ctx = RetryContext(
            lld_content="",
            target_file="assemblyzero/services/alpha_service.py",
            error_message="SyntaxError",
            retry_count=1,
            previous_attempt_snippet=None,
            completed_files=[],
        )
        with pytest.raises(ValueError, match="lld_content must not be empty"):
            build_retry_prompt(ctx)

    def test_tier1_prompt_contains_error(self, full_lld: str) -> None:
        """Tier 1 prompt contains the error message."""
        error = "NameError: name 'foo' is not defined"
        ctx = _make_ctx(full_lld, retry_count=1, error_message=error)
        result = build_retry_prompt(ctx)
        assert error in result["prompt_text"]

    def test_tier2_prompt_contains_error(self, full_lld: str) -> None:
        """Tier 2 prompt contains the error message."""
        error = "TypeError: expected str, got int"
        ctx = _make_ctx(
            full_lld,
            retry_count=2,
            error_message=error,
            previous_attempt_snippet="def foo():\n    return 42",
        )
        result = build_retry_prompt(ctx)
        assert error in result["prompt_text"]

    def test_tier2_prompt_contains_snippet(self, full_lld: str) -> None:
        """Tier 2 prompt contains the previous attempt snippet."""
        snippet = "def create_alpha():\n    return None  # wrong"
        ctx = _make_ctx(
            full_lld,
            retry_count=2,
            previous_attempt_snippet=snippet,
        )
        result = build_retry_prompt(ctx)
        assert "create_alpha" in result["prompt_text"]

    def test_result_has_all_required_keys(self, full_lld: str) -> None:
        """PrunedRetryPrompt has all required keys."""
        ctx = _make_ctx(full_lld, retry_count=1)
        result = build_retry_prompt(ctx)
        assert "prompt_text" in result
        assert "tier" in result
        assert "estimated_tokens" in result
        assert "context_sections_included" in result

    def test_estimated_tokens_positive(self, full_lld: str) -> None:
        """estimated_tokens is a positive integer."""
        ctx = _make_ctx(full_lld, retry_count=1)
        result = build_retry_prompt(ctx)
        assert isinstance(result["estimated_tokens"], int)
        assert result["estimated_tokens"] > 0

    def test_context_sections_included_nonempty(self, full_lld: str) -> None:
        """context_sections_included is a non-empty list."""
        ctx = _make_ctx(full_lld, retry_count=1)
        result = build_retry_prompt(ctx)
        assert isinstance(result["context_sections_included"], list)
        assert len(result["context_sections_included"]) > 0

    def test_tier3_also_uses_tier2(self, full_lld: str) -> None:
        """retry_count=3 (>= TIER_BOUNDARY) also returns tier 2."""
        ctx = _make_ctx(
            full_lld,
            retry_count=3,
            previous_attempt_snippet="def create_alpha():\n    pass",
        )
        result = build_retry_prompt(ctx)
        assert result["tier"] == 2

    def test_tier1_target_file_in_prompt(self, full_lld: str) -> None:
        """Tier 1 prompt contains the target file path."""
        target = "assemblyzero/services/alpha_service.py"
        ctx = _make_ctx(full_lld, retry_count=1, target_file=target)
        result = build_retry_prompt(ctx)
        assert target in result["prompt_text"]

    def test_tier2_target_file_in_prompt(self, full_lld: str) -> None:
        """Tier 2 prompt contains the target file path."""
        target = "assemblyzero/services/alpha_service.py"
        ctx = _make_ctx(
            full_lld,
            retry_count=2,
            target_file=target,
            previous_attempt_snippet="some code",
        )
        result = build_retry_prompt(ctx)
        assert target in result["prompt_text"]

    def test_completed_files_empty_tier1_keeps_all(self, full_lld: str) -> None:
        """Empty completed_files list preserves all LLD sections in tier 1."""
        ctx = _make_ctx(full_lld, retry_count=1, completed_files=[])
        result = build_retry_prompt(ctx)
        assert "beta_service" in result["prompt_text"].lower()
        assert "gamma_model" in result["prompt_text"].lower()

    def test_tier2_fallback_context_sections_label(
        self, full_lld: str
    ) -> None:
        """Fallback to tier 1 includes fallback label in context_sections_included."""
        ctx = _make_ctx(
            full_lld,
            retry_count=2,
            target_file="assemblyzero/nonexistent/zzz_module.py",
            previous_attempt_snippet="some code here",
        )
        result = build_retry_prompt(ctx)
        assert any("fallback" in s.lower() for s in result["context_sections_included"])


class TestBuildTier1Prompt:
    """Tests for _build_tier1_prompt()."""

    def test_contains_lld_content(self, full_lld: str) -> None:
        """Tier 1 prompt includes LLD content."""
        ctx = _make_ctx(full_lld, retry_count=1)
        prompt = _build_tier1_prompt(ctx)
        assert "alpha_service" in prompt.lower()

    def test_contains_error_message(self, full_lld: str) -> None:
        """Tier 1 prompt includes the error message."""
        error = "NameError: foo not defined"
        ctx = _make_ctx(full_lld, retry_count=1, error_message=error)
        prompt = _build_tier1_prompt(ctx)
        assert error in prompt

    def test_strips_completed_file_sections(self, full_lld: str) -> None:
        """Tier 1 prompt strips completed file sections."""
        ctx = _make_ctx(
            full_lld,
            retry_count=1,
            completed_files=["assemblyzero/services/beta_service.py"],
        )
        prompt = _build_tier1_prompt(ctx)
        assert "Beta service provides" not in prompt

    def test_no_completed_files_keeps_all(self, full_lld: str) -> None:
        """Empty completed_files list keeps all sections."""
        ctx = _make_ctx(full_lld, retry_count=1, completed_files=[])
        prompt = _build_tier1_prompt(ctx)
        assert "beta_service" in prompt.lower()

    def test_contains_target_file(self, full_lld: str) -> None:
        """Tier 1 prompt includes target file path."""
        target = "assemblyzero/services/alpha_service.py"
        ctx = _make_ctx(full_lld, retry_count=1, target_file=target)
        prompt = _build_tier1_prompt(ctx)
        assert target in prompt


class TestBuildTier2Prompt:
    """Tests for _build_tier2_prompt()."""

    def test_snippet_none_raises(self, full_lld: str) -> None:
        """Raises ValueError when snippet is None."""
        ctx = _make_ctx(full_lld, retry_count=2, previous_attempt_snippet=None)
        with pytest.raises(ValueError, match="Tier 2 requires previous_attempt_snippet"):
            _build_tier2_prompt(ctx)

    def test_contains_relevant_section(self, full_lld: str) -> None:
        """Tier 2 prompt contains the relevant file section."""
        ctx = _make_ctx(
            full_lld,
            retry_count=2,
            target_file="assemblyzero/services/alpha_service.py",
            previous_attempt_snippet="def create_alpha():\n    pass",
        )
        prompt = _build_tier2_prompt(ctx)
        assert "create_alpha" in prompt

    def test_excludes_padding_sections(self, full_lld: str) -> None:
        """Tier 2 prompt excludes padding sections."""
        ctx = _make_ctx(
            full_lld,
            retry_count=2,
            previous_attempt_snippet="some code",
        )
        prompt = _build_tier2_prompt(ctx)
        assert "Padding Section Gamma" not in prompt

    def test_contains_snippet(self, full_lld: str) -> None:
        """Tier 2 prompt contains the previous attempt snippet."""
        snippet = "def create_alpha():\n    return 'wrong'"
        ctx = _make_ctx(
            full_lld,
            retry_count=2,
            previous_attempt_snippet=snippet,
        )
        prompt = _build_tier2_prompt(ctx)
        assert "create_alpha" in prompt

    def test_contains_error(self, full_lld: str) -> None:
        """Tier 2 prompt contains the error message."""
        error = "TypeError: bad type"
        ctx = _make_ctx(
            full_lld,
            retry_count=2,
            error_message=error,
            previous_attempt_snippet="some code",
        )
        prompt = _build_tier2_prompt(ctx)
        assert error in prompt

    def test_fallback_when_no_section(
        self, full_lld: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Falls back to tier 1 when section extraction returns None."""
        ctx = _make_ctx(
            full_lld,
            retry_count=2,
            target_file="assemblyzero/nonexistent/zzz.py",
            previous_attempt_snippet="some code",
        )
        with caplog.at_level(logging.WARNING):
            prompt = _build_tier2_prompt(ctx)
        # Fallback uses tier 1 structure (full LLD header)
        assert "Full LLD Context" in prompt
        assert "falling back to tier 1" in caplog.text.lower()

    def test_long_snippet_is_truncated(self, full_lld: str) -> None:
        """Long snippet is truncated in tier 2 prompt."""
        long_snippet = "\n".join(f"line {i}: code" for i in range(200))
        ctx = _make_ctx(
            full_lld,
            retry_count=2,
            previous_attempt_snippet=long_snippet,
        )
        prompt = _build_tier2_prompt(ctx)
        # The truncated snippet should have the ellipsis prefix
        assert "..." in prompt


class TestTruncateSnippet:
    """Tests for _truncate_snippet()."""

    def test_long_snippet_truncated(self) -> None:
        """T070: 200-line snippet truncated to SNIPPET_MAX_LINES."""
        snippet = "\n".join(f"line {i}: some code here" for i in range(200))
        result = _truncate_snippet(snippet, max_lines=60)
        lines = result.splitlines()
        # 1 "..." line + 60 content lines = 61
        assert len(lines) <= 61
        assert lines[0] == "..."
        assert "line 199" in result

    def test_short_snippet_unchanged(self) -> None:
        """T080: 3-line snippet returned unchanged."""
        snippet = "line 1\nline 2\nline 3"
        result = _truncate_snippet(snippet, max_lines=60)
        assert result == snippet

    def test_empty_snippet_unchanged(self) -> None:
        """Edge case: empty snippet returned unchanged."""
        assert _truncate_snippet("", max_lines=60) == ""

    def test_exact_max_lines_unchanged(self) -> None:
        """Edge case: snippet with exactly max_lines lines is unchanged."""
        snippet = "\n".join(f"line {i}" for i in range(60))
        result = _truncate_snippet(snippet, max_lines=60)
        assert result == snippet

    def test_default_max_lines_is_constant(self) -> None:
        """Default max_lines uses SNIPPET_MAX_LINES constant."""
        long_snippet = "\n".join(f"line {i}" for i in range(SNIPPET_MAX_LINES + 10))
        result = _truncate_snippet(long_snippet)
        lines = result.splitlines()
        assert len(lines) <= SNIPPET_MAX_LINES + 1  # +1 for "..."
        assert lines[0] == "..."

    def test_truncation_keeps_tail(self) -> None:
        """Truncation keeps tail (most recent lines)."""
        snippet = "\n".join(f"line {i}" for i in range(100))
        result = _truncate_snippet(snippet, max_lines=10)
        # Last 10 lines should be present
        assert "line 99" in result
        assert "line 90" in result
        # Early lines should be absent
        assert "line 0\n" not in result

    def test_one_line_over_max_truncates(self) -> None:
        """One line over max triggers truncation with leading ellipsis."""
        snippet = "\n".join(f"line {i}" for i in range(61))
        result = _truncate_snippet(snippet, max_lines=60)
        lines = result.splitlines()
        assert lines[0] == "..."
        assert len(lines) == 61  # "..." + 60 lines


class TestEstimateTokens:
    """Tests for _estimate_tokens()."""

    def test_nonempty_string_positive(self) -> None:
        """T130: Non-empty string returns positive token count."""
        result = _estimate_tokens("Hello, world!")
        assert isinstance(result, int)
        assert result > 0

    def test_empty_string_zero(self) -> None:
        """T140: Empty string returns 0."""
        assert _estimate_tokens("") == 0

    def test_long_text_reasonable(self) -> None:
        """Sanity: long text token count is reasonable (not wildly off)."""
        text = "word " * 1000  # ~1000 words
        result = _estimate_tokens(text)
        assert 500 < result < 2000  # rough sanity bounds

    def test_returns_int(self) -> None:
        """Return type is always int."""
        result = _estimate_tokens("some text here")
        assert isinstance(result, int)

    def test_tiktoken_failure_returns_sentinel(self) -> None:
        """Returns -1 if tiktoken encoding fails."""
        with patch(
            "assemblyzero.workflows.implementation_spec.nodes.retry_prompt_builder.tiktoken.get_encoding",
            side_effect=Exception("tiktoken error"),
        ):
            result = _estimate_tokens("Hello world")
        assert result == -1

    def test_single_word(self) -> None:
        """Single word returns a small positive token count."""
        result = _estimate_tokens("hello")
        assert result >= 1

    def test_longer_text_more_tokens(self) -> None:
        """Longer text has more tokens than shorter text."""
        short_result = _estimate_tokens("Hello")
        long_result = _estimate_tokens("Hello world this is a longer sentence with more words")
        assert long_result > short_result


class TestWorkflowStateIntegration:
    """Tests for workflow state integration (T210, T220)."""

    def test_workflow_state_has_retry_count(self) -> None:
        """T210: ImplementationSpecState includes retry_count field."""
        from assemblyzero.workflows.implementation_spec.state import (
            ImplementationSpecState,
        )
        import typing

        hints = typing.get_type_hints(ImplementationSpecState)
        assert "retry_count" in hints

    def test_workflow_state_has_previous_attempt_snippet(self) -> None:
        """T210 (cont): ImplementationSpecState includes previous_attempt_snippet field."""
        from assemblyzero.workflows.implementation_spec.state import (
            ImplementationSpecState,
        )
        import typing

        hints = typing.get_type_hints(ImplementationSpecState)
        assert "previous_attempt_snippet" in hints

    def test_retry_count_flows_from_state(self, full_lld: str) -> None:
        """T220: retry_count from workflow state flows into RetryContext correctly."""
        # Simulate what generate_spec.py does: build RetryContext from state
        state = {
            "lld_content": full_lld,
            "target_file": "assemblyzero/services/alpha_service.py",
            "error_message": "SyntaxError: bad indent",
            "retry_count": 2,
            "previous_attempt_snippet": "def create_alpha():\n    pass",
            "completed_files": [],
        }

        retry_ctx = RetryContext(
            lld_content=state.get("lld_content", ""),
            target_file=state.get("target_file", ""),
            error_message=state.get("error_message", ""),
            retry_count=state.get("retry_count", 0),
            previous_attempt_snippet=state.get("previous_attempt_snippet", None),
            completed_files=state.get("completed_files", []),
        )

        assert retry_ctx["retry_count"] == 2
        assert retry_ctx["previous_attempt_snippet"] == "def create_alpha():\n    pass"
        assert retry_ctx["target_file"] == "assemblyzero/services/alpha_service.py"

    def test_state_defaults_produce_valid_tier1(self, full_lld: str) -> None:
        """State with retry_count=1 and no snippet produces valid tier 1 prompt."""
        state = {
            "lld_content": full_lld,
            "target_file": "assemblyzero/services/alpha_service.py",
            "error_message": "SyntaxError: bad indent",
            "retry_count": 1,
            "previous_attempt_snippet": None,
            "completed_files": [],
        }

        retry_ctx = RetryContext(
            lld_content=state.get("lld_content", ""),
            target_file=state.get("target_file", ""),
            error_message=state.get("error_message", ""),
            retry_count=state.get("retry_count", 0),
            previous_attempt_snippet=state.get("previous_attempt_snippet", None),
            completed_files=state.get("completed_files", []),
        )

        result = build_retry_prompt(retry_ctx)
        assert result["tier"] == 1
        assert result["estimated_tokens"] > 0


class TestTypeAnnotations:
    """Tests for type annotation completeness (T160, T170)."""

    def test_mypy_retry_prompt_builder(self) -> None:
        """T160: mypy reports zero errors on retry_prompt_builder module."""
        module_path = (
            Path(__file__).parent.parent.parent
            / "assemblyzero"
            / "workflows"
            / "implementation_spec"
            / "nodes"
            / "retry_prompt_builder.py"
        )
        result = subprocess.run(
            [sys.executable, "-m", "mypy", str(module_path), "--strict", "--ignore-missing-imports"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"mypy reported errors on retry_prompt_builder.py:\n{result.stdout}\n{result.stderr}"
        )

    def test_mypy_lld_section_extractor(self) -> None:
        """T170: mypy reports zero errors on lld_section_extractor module."""
        module_path = (
            Path(__file__).parent.parent.parent
            / "assemblyzero"
            / "utils"
            / "lld_section_extractor.py"
        )
        result = subprocess.run(
            [sys.executable, "-m", "mypy", str(module_path), "--strict", "--ignore-missing-imports"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"mypy reported errors on lld_section_extractor.py:\n{result.stdout}\n{result.stderr}"
        )


class TestNoDependencies:
    """Tests for no new runtime dependencies (T200)."""

    def test_no_new_runtime_deps(self) -> None:
        """T200: pyproject.toml has no new runtime dependencies added by this feature."""
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        content = pyproject_path.read_text(encoding="utf-8")
        # tiktoken should already be present (pre-existing dep per LLD)
        # Verify no new packages were added beyond what LLD specifies
        # This is validated by confirming tiktoken is present (pre-existing)
        # and no unexpected new packages were added
        assert "tiktoken" in content, "tiktoken should be a pre-existing dependency"


```

## Previous Attempt Failed — Fix These Specific Errors

The previous implementation failed these tests:

```
FAILED tests/unit/test_lld_section_extractor.py::TestExtractFileSpecSection::test_exact_path_match_returns_confidence_1
FAILED tests/unit/test_lld_section_extractor.py::TestExtractFileSpecSection::test_minimal_lld_exact_match
FAILED tests/unit/test_lld_section_extractor.py::TestExtractFileSpecSection::test_beta_service_match
FAILED tests/unit/test_lld_section_extractor.py::TestExtractFileSpecSection::test_gamma_model_match
FAILED tests/unit/test_retry_prompt_builder.py::TestBuildRetryPrompt::test_completed_files_excluded_tier1
FAILED tests/unit/test_retry_prompt_builder.py::TestBuildTier1Prompt::test_strips_completed_file_sections
6 failed, 77 passed, 2 warnings in 127.19s (0:02:07)
```

Read the error messages carefully and fix the root cause in your implementation.

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the Python code.

```python
# Your Python code here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the Python code in a single fenced code block
