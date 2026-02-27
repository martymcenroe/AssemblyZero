# 352 - Feature: Multi-Model Adversarial Testing Node (Gemini vs Claude)

<!-- Template Metadata
Last Updated: 2026-02-17
Updated By: Issue #352 revision
Update Reason: Fix mechanical test plan validation - add test coverage for REQ-2, REQ-5, REQ-7, REQ-8; reformat Section 3 as numbered list; add (REQ-N) suffixes to Section 10.1 scenarios
Previous: Fix mechanical validation error for gemini_provider.py path; revise to match repository structure
-->

## 1. Context & Goal
* **Issue:** #352
* **Objective:** Integrate a new LangGraph node into the Testing Workflow (N2.7) where Gemini Pro analyzes Claude's implementation and LLD claims to generate aggressive, unmocked adversarial tests.
* **Status:** Approved (gemini-3-pro-preview, 2026-02-27)
* **Related Issues:** #117 (governance verdicts), ADR 0201 (adversarial audit philosophy)

### Open Questions

- [ ] Should adversarial test failures block the PR, or be advisory-only in the initial rollout?
- [ ] What is the maximum token budget for sending implementation code + LLD to Gemini for analysis?
- [ ] Should adversarial tests be re-generated on every run, or cached until the implementation changes?

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/adversarial/` | Add (Directory) | New directory for adversarial test output |
| `tests/adversarial/__init__.py` | Add | Package init for adversarial tests |
| `tests/adversarial/conftest.py` | Add | Shared fixtures for adversarial tests (no mocks enforced) |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py` | Add | Core LangGraph node: orchestrates Gemini-based adversarial test generation |
| `assemblyzero/workflows/testing/nodes/adversarial_writer.py` | Add | Writes Gemini's adversarial test output to `tests/adversarial/test_*.py` files |
| `assemblyzero/workflows/testing/nodes/adversarial_validator.py` | Add | Validates generated tests: syntax check, no-mock enforcement, deduplication |
| `assemblyzero/workflows/testing/adversarial_prompts.py` | Add | Prompt templates for Gemini adversarial analysis |
| `assemblyzero/workflows/testing/adversarial_state.py` | Add | TypedDict state extensions for adversarial node |
| `assemblyzero/workflows/testing/knowledge/adversarial_patterns.py` | Add | Knowledge base of adversarial testing patterns (boundary, injection, concurrency, etc.) |
| `assemblyzero/workflows/testing/adversarial_gemini.py` | Add | Wrapper module encapsulating Gemini adversarial invocation logic; delegates to existing `GeminiProvider` |
| `assemblyzero/workflows/testing/graph.py` | Modify | Wire adversarial node into existing testing workflow StateGraph |
| `tests/unit/test_adversarial_node.py` | Add | Unit tests for adversarial node logic |
| `tests/unit/test_adversarial_writer.py` | Add | Unit tests for test file writer |
| `tests/unit/test_adversarial_validator.py` | Add | Unit tests for validation logic |
| `tests/unit/test_adversarial_prompts.py` | Add | Unit tests for prompt construction |
| `tests/unit/test_adversarial_gemini.py` | Add | Unit tests for adversarial Gemini wrapper |
| `tests/integration/test_adversarial_integration.py` | Add | Integration test: full node execution with real Gemini call |
| `tests/conftest.py` | Modify | Register `adversarial` marker |
| `pyproject.toml` | Modify | Add `adversarial` pytest marker |

### 2.1.1 Path Validation (Mechanical - Auto-Checked)

Mechanical validation automatically checks:
- All "Modify" files must exist in repository — ✅ `assemblyzero/workflows/testing/graph.py` exists, `tests/conftest.py` exists, `pyproject.toml` exists
- All "Add" files must have existing parent directories — ✅ `tests/adversarial/` explicitly created as new directory; `assemblyzero/workflows/testing/nodes/` exists; `assemblyzero/workflows/testing/` exists; `assemblyzero/workflows/testing/knowledge/` exists; `tests/unit/` exists; `tests/integration/` exists
- No placeholder prefixes — ✅ All paths use actual project structure

**Validation Error Fix:** The original draft listed `assemblyzero/utils/gemini_provider.py` as "Modify" but this file does not exist in the repository. This has been replaced with a new file `assemblyzero/workflows/testing/adversarial_gemini.py` (Change Type: Add) that wraps the existing `GeminiProvider` class from `assemblyzero/utils/` with adversarial-specific invocation logic. This avoids modifying a non-existent file while keeping Gemini invocation encapsulated.

### 2.2 Dependencies

```toml
# No new dependencies required.
# Already present in pyproject.toml:
# langchain-google-genai = "^4.2.0"  (Gemini provider)
# google-genai = "^1.60.0"           (Gemini SDK)
# langgraph = "^1.0.7"               (State machine)
```

No new packages needed. The existing `langchain-google-genai` and `google-genai` dependencies provide Gemini access. The new `adversarial_gemini.py` module imports and delegates to whatever Gemini provider class exists in `assemblyzero/utils/`.

### 2.3 Data Structures

```python
# assemblyzero/workflows/testing/adversarial_state.py

from typing import TypedDict, Literal


class AdversarialTestCase(TypedDict):
    """A single adversarial test case generated by Gemini."""
    test_id: str                          # e.g., "ADV_001"
    target_function: str                  # Fully qualified function name
    category: str                         # "boundary" | "injection" | "concurrency" | "state" | "contract"
    description: str                      # Human-readable description of what this tests
    test_code: str                        # Raw Python test code (function body)
    claim_challenged: str                 # Which LLD claim or docstring assertion this challenges
    severity: Literal["critical", "high", "medium"]  # Expected impact if test fails


class AdversarialAnalysis(TypedDict):
    """Gemini's analysis of implementation vs. LLD claims."""
    uncovered_edge_cases: list[str]       # Edge cases not in existing test suite
    false_claims: list[str]              # LLD claims not backed by implementation
    missing_error_handling: list[str]    # Error paths without handlers
    implicit_assumptions: list[str]      # Undocumented assumptions in the code
    test_cases: list[AdversarialTestCase]


class AdversarialNodeState(TypedDict, total=False):
    """State extension for the adversarial testing node."""
    # Inputs (populated by prior nodes)
    implementation_files: dict[str, str]  # filepath -> file content
    lld_content: str                      # Full LLD markdown
    existing_tests: dict[str, str]        # filepath -> existing test content
    issue_id: int                         # GitHub issue number

    # Outputs (populated by adversarial node)
    adversarial_analysis: AdversarialAnalysis
    generated_test_files: dict[str, str]  # filepath -> generated test content
    adversarial_verdict: Literal["pass", "fail", "error"]
    adversarial_error: str | None         # Error message if verdict is "error"
    adversarial_test_count: int           # Number of tests generated
    adversarial_skipped_reason: str | None  # Why adversarial was skipped (e.g., quota)
```

### 2.4 Function Signatures

```python
# assemblyzero/workflows/testing/nodes/adversarial_node.py

from assemblyzero.workflows.testing.adversarial_state import AdversarialNodeState


def run_adversarial_node(state: AdversarialNodeState) -> AdversarialNodeState:
    """
    LangGraph node: Orchestrates adversarial test generation via Gemini.

    1. Collects implementation code and LLD from state.
    2. Builds adversarial analysis prompt.
    3. Invokes Gemini Pro for analysis via adversarial_gemini wrapper.
    4. Parses structured response into AdversarialAnalysis.
    5. Delegates to writer and validator.
    6. Returns updated state with generated tests.

    Fails gracefully on Gemini quota/downgrade errors (sets adversarial_skipped_reason).
    """
    ...


def _collect_context(state: AdversarialNodeState) -> tuple[str, str, str]:
    """
    Extract and token-budget-trim implementation code, LLD content,
    and existing tests from state.

    Returns:
        (implementation_context, lld_context, existing_test_context)
    """
    ...


def _parse_gemini_response(raw_response: str) -> "AdversarialAnalysis":
    """
    Parse Gemini's structured JSON response into AdversarialAnalysis.

    Raises:
        ValueError: If response is malformed or missing required fields.
    """
    ...


# assemblyzero/workflows/testing/nodes/adversarial_writer.py

def write_adversarial_tests(
    analysis: "AdversarialAnalysis",
    issue_id: int,
    output_dir: str = "tests/adversarial",
) -> dict[str, str]:
    """
    Write adversarial test cases to disk as pytest-compatible files.

    Each file follows naming: test_{issue_id}_{category}.py
    Groups test cases by category into separate files.
    Writes to a temp directory first, then performs atomic rename.

    Returns:
        Dictionary of filepath -> file content written.
    """
    ...


def _render_test_file(
    test_cases: list["AdversarialTestCase"],
    category: str,
    issue_id: int,
) -> str:
    """
    Render a list of test cases into a complete pytest file with header,
    imports, no-mock enforcement docstring, and adversarial identification
    header comment.
    
    The rendered file begins with a header comment block:
        # ADVERSARIAL TEST FILE - Machine-generated by Gemini Pro
        # Issue: #{issue_id}
        # Category: {category}
        # Generator: assemblyzero adversarial testing node
        # WARNING: Do not manually edit - regenerated on each workflow run
    """
    ...


# assemblyzero/workflows/testing/nodes/adversarial_validator.py

from typing import TypedDict


class ValidationResult(TypedDict):
    valid: bool
    errors: list[str]
    warnings: list[str]
    mock_violations: list[str]


def validate_adversarial_tests(test_files: dict[str, str]) -> ValidationResult:
    """
    Validate generated adversarial test files:
    1. Syntax check (compile each file).
    2. No-mock enforcement (scan for unittest.mock, MagicMock, patch, monkeypatch).
    3. No duplicate test function names.
    4. Each test has at least one assert statement.

    Returns ValidationResult with detailed error/warning lists.
    """
    ...


def _check_no_mocks(source_code: str, filepath: str) -> list[str]:
    """
    AST-scan source code for mock usage. Returns list of violations.

    Detects:
    - import unittest.mock
    - from unittest.mock import *
    - from unittest import mock
    - @patch / @mock.patch decorators
    - MagicMock(), Mock(), AsyncMock() instantiation
    - monkeypatch fixture usage
    """
    ...


def _check_syntax(source_code: str, filepath: str) -> list[str]:
    """
    Attempt to compile source code. Returns list of syntax errors.
    """
    ...


def _check_assertions(source_code: str, filepath: str) -> list[str]:
    """
    AST-scan for assert statements in each test function.
    Returns warnings for test functions with zero assertions.
    """
    ...


# assemblyzero/workflows/testing/adversarial_prompts.py

def build_adversarial_analysis_prompt(
    implementation_code: str,
    lld_content: str,
    existing_tests: str,
    adversarial_patterns: list[str],
) -> str:
    """
    Build the system + user prompt for Gemini adversarial analysis.

    The prompt instructs Gemini to:
    1. Read the implementation and LLD.
    2. Identify claims in the LLD not backed by code.
    3. Find edge cases missing from existing tests.
    4. Generate aggressive test cases that use NO mocks.
    5. Return structured JSON matching AdversarialAnalysis schema.
    
    The prompt explicitly requires Gemini to populate all four analysis
    categories: uncovered_edge_cases, false_claims, missing_error_handling,
    and implicit_assumptions.
    """
    ...


def build_adversarial_system_prompt() -> str:
    """
    System prompt establishing Gemini's adversarial tester persona.

    Key constraints:
    - You are a hostile reviewer trying to break the implementation.
    - NEVER generate mocks, stubs, or fakes.
    - Tests must exercise real code paths.
    - Focus on boundary conditions, error paths, and contract violations.
    - Output strict JSON.
    - Your analysis MUST include: uncovered_edge_cases, false_claims,
      missing_error_handling, and implicit_assumptions.
    """
    ...


# assemblyzero/workflows/testing/adversarial_gemini.py

class AdversarialGeminiClient:
    """
    Wrapper around the project's existing GeminiProvider for adversarial test generation.

    This module encapsulates the adversarial-specific invocation logic
    (system prompt, no-mock constraint, timeout handling) while delegating
    actual Gemini API communication to the existing provider infrastructure.
    """

    def __init__(self, provider: object | None = None) -> None:
        """
        Initialize with an optional GeminiProvider instance.

        If provider is None, instantiates the default provider from
        assemblyzero.utils (auto-discovered at runtime).
        """
        ...

    def verify_model_is_pro(self, response_metadata: dict) -> bool:
        """
        Check response metadata to confirm Gemini Pro was used,
        not a downgraded Flash model.

        Returns True if Pro confirmed, False if Flash detected.
        
        Raises:
            GeminiModelDowngradeError: If Flash model detected instead of Pro.
        """
        ...

    def generate_adversarial_tests(
        self,
        implementation_code: str,
        lld_content: str,
        existing_tests: str,
        adversarial_patterns: list[str] | None = None,
        timeout: int = 120,
    ) -> str:
        """
        Invoke Gemini Pro for adversarial test generation.

        Builds the adversarial prompt, delegates to the underlying provider,
        and applies model-downgrade detection via verify_model_is_pro().

        Returns raw JSON string response from Gemini.

        Raises:
            GeminiQuotaExhaustedError: If 429 or quota message detected.
            GeminiModelDowngradeError: If Flash detected instead of Pro.
            GeminiTimeoutError: If response exceeds timeout.
        """
        ...


# assemblyzero/workflows/testing/knowledge/adversarial_patterns.py

def get_adversarial_patterns() -> list[str]:
    """
    Return curated list of adversarial testing pattern descriptions.

    Categories:
    - Boundary: off-by-one, empty input, max-size input, type limits
    - Injection: special characters, unicode, null bytes, path traversal
    - Concurrency: race conditions, shared state mutation
    - State: invalid state transitions, partial initialization
    - Contract: violating documented preconditions, postcondition verification
    - Resource: memory exhaustion, file handle leaks, timeout scenarios
    """
    ...
```

### 2.5 Logic Flow (Pseudocode)

```
ADVERSARIAL NODE EXECUTION:

1. Receive state from prior testing node
2. Extract implementation_files, lld_content, existing_tests from state
3. IF implementation_files is empty:
   - Set adversarial_skipped_reason = "No implementation files in state"
   - Return state (skip gracefully)

4. Trim context to token budget (~60KB combined):
   a. Prioritize: implementation code > LLD > existing tests
   b. Use section-aware truncation (preserve function signatures)

5. Load adversarial_patterns from knowledge base

6. Build prompt:
   a. System prompt (adversarial persona, no-mock constraint, JSON output,
      MUST include uncovered_edge_cases, false_claims, missing_error_handling,
      implicit_assumptions)
   b. User prompt (implementation + LLD + existing tests + patterns)

7. Instantiate AdversarialGeminiClient (wraps existing provider)
8. Invoke client.generate_adversarial_tests():
   - TRY:
     a. Send prompt with timeout=120s
     b. Verify model via verify_model_is_pro() (check for Flash downgrade)
     c. Receive raw JSON response
   - CATCH GeminiQuotaExhaustedError:
     a. Set adversarial_skipped_reason = "Gemini quota exhausted"
     b. Set adversarial_verdict = "error"
     c. Return state (graceful degradation)
   - CATCH GeminiModelDowngradeError:
     a. Set adversarial_skipped_reason = "Gemini model downgraded to Flash"
     b. Set adversarial_verdict = "error"
     c. Return state
   - CATCH GeminiTimeoutError:
     a. Retry ONCE with timeout=180s
     b. If still fails: set adversarial_skipped_reason, return state

9. Parse Gemini response into AdversarialAnalysis:
   - TRY:
     a. JSON decode
     b. Validate against AdversarialAnalysis schema
     c. Verify all four analysis categories are present:
        uncovered_edge_cases, false_claims, missing_error_handling, implicit_assumptions
   - CATCH ValueError:
     a. Log malformed response
     b. Set adversarial_verdict = "error"
     c. Return state

10. Write test files:
    a. Group test_cases by category
    b. For each category, render test file with:
       - Adversarial identification header comment (Gemini-generated, issue ID, category)
       - Imports + no-mock enforcement docstring
       - Test functions
    c. Write to temp directory first
    d. Atomic rename to tests/adversarial/test_{issue_id}_{category}.py

11. Validate generated tests:
    a. Syntax check (compile)
    b. No-mock enforcement (AST scan) — reject any test containing mocks BEFORE writing final files
    c. Assertion check
    d. IF mock_violations found:
       - Remove offending test functions
       - Log violations
    e. IF syntax errors found:
       - Remove offending files
       - Log errors

12. Update state:
    a. adversarial_analysis = parsed analysis
    b. generated_test_files = {filepath: content} for valid files
    c. adversarial_test_count = count of valid test functions
    d. adversarial_verdict = "pass" if test_count > 0 else "fail"

13. Return updated state
```

```
TESTING WORKFLOW GRAPH (modified):

existing_nodes... → run_standard_tests → run_adversarial_node → evaluate_results
                                              │
                                              ├── (on error) → log_skip_reason → evaluate_results
                                              └── (on success) → evaluate_results

Note: Adversarial node is OPTIONAL — errors skip gracefully.
      The workflow never blocks on adversarial failures.
```

### 2.6 Technical Approach

* **Module:** `assemblyzero/workflows/testing/`
* **Pattern:** LangGraph conditional node with graceful degradation. The adversarial node is wired as a non-blocking step: if Gemini is unavailable (quota, downgrade, timeout), the workflow continues without adversarial tests. This preserves the existing testing workflow's reliability.
* **Key Decisions:**
  - New `AdversarialGeminiClient` wrapper (Add) instead of modifying a non-existent `gemini_provider.py` — keeps adversarial logic self-contained and avoids coupling to the utils layer's internal API
  - `verify_model_is_pro()` explicitly checks response metadata to detect silent Gemini Flash downgrades, ensuring adversarial analysis comes from the Pro model
  - Tests written to disk (not ephemeral) so they persist in the PR for human review
  - AST-based mock detection rather than regex (accurate, handles aliases) — validation occurs BEFORE final file write
  - Category-based file grouping (one file per adversarial category) for readability
  - JSON output from Gemini (structured, parseable) rather than raw Python (fragile)
  - Atomic file writes via temp directory + rename to prevent corrupt partial writes
  - Every generated test file includes a header comment identifying it as adversarial (machine-generated by Gemini)
  - Prompt explicitly requires all four analysis categories (uncovered edge cases, false claims, missing error handling, implicit assumptions)

### 2.7 Architecture Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Gemini invocation layer | Modify existing utils provider, New wrapper module, Direct API calls | **New wrapper module** (`adversarial_gemini.py`) | The file `assemblyzero/utils/gemini_provider.py` does not exist in the repository; a new wrapper module in the testing workflow delegates to whatever provider exists, keeping adversarial logic isolated |
| Model verification | Trust API default, Check response metadata, Request-time model pinning | **Check response metadata** (`verify_model_is_pro()`) | Gemini CLI sometimes silently downgrades Pro to Flash; explicit verification catches this and raises `GeminiModelDowngradeError` |
| Gemini output format | Raw Python files, Structured JSON, YAML | **Structured JSON** | JSON is parseable, validates against schema, allows post-processing before writing; raw Python from LLMs often has syntax errors |
| Mock detection method | Regex string search, AST analysis, Runtime import hook | **AST analysis** | Regex misses aliased imports; runtime hooks are invasive; AST catches `from unittest.mock import patch as p` |
| Mock rejection timing | After write, Before write, During write | **Before write** | Validator runs AST no-mock scan and rejects violating tests before they are written to final output files |
| Node failure behavior | Block workflow, Skip with warning, Retry indefinitely | **Skip with warning** | Adversarial tests are additive value; blocking the entire testing workflow on Gemini quota would be counterproductive |
| Test file organization | Single monolithic file, Category-based files, One file per test | **Category-based files** | Balances readability (not hundreds of files) with organization (not one 2000-line file) |
| Test file identification | No header, Inline comment, Header comment block | **Header comment block** | Every generated file starts with a multi-line header identifying it as adversarial, machine-generated by Gemini, with issue ID and category |
| State integration | New parallel state graph, Extension of existing TestingState, Separate workflow | **Extension of existing state** | Minimizes changes to the testing workflow; adds fields with `total=False` so existing nodes are unaffected |
| Analysis completeness | Allow partial analysis, Require all categories | **Require all four categories** | Prompt and parser enforce that Gemini returns uncovered_edge_cases, false_claims, missing_error_handling, and implicit_assumptions |
| Token budget strategy | Send everything, Fixed truncation, Priority-based trimming | **Priority-based trimming** | Implementation code is most important; LLD provides contract claims; existing tests prevent duplication |
| File write safety | Direct write, Temp dir + atomic rename, In-memory only | **Temp dir + atomic rename** | Prevents partial/corrupt files on disk if process is interrupted mid-write |

**Architectural Constraints:**
- Must integrate with existing `assemblyzero/workflows/testing/graph.py` StateGraph without breaking existing nodes
- Must use existing Gemini provider infrastructure (not a separate Gemini client from scratch) — the new `AdversarialGeminiClient` wraps and delegates to it
- Cannot introduce new external dependencies (all Gemini/LangGraph deps already in `pyproject.toml`)
- Generated tests must be valid pytest files runnable by `poetry run pytest tests/adversarial/ -v`

## 3. Requirements

1. A new LangGraph node `run_adversarial_node` is added to the testing workflow graph and executes after standard test generation.
2. The node invokes Gemini Pro (not Flash) to analyze implementation code against LLD claims, with explicit model verification to detect silent downgrades.
3. Gemini generates adversarial test cases that exercise real code paths with zero mocks.
4. Generated tests are written to `tests/adversarial/test_*.py` as valid pytest files.
5. An AST-based validator enforces the no-mock constraint; any test containing mocks is rejected before being written to the final output files.
6. If Gemini is unavailable (quota, downgrade, timeout), the node skips gracefully and the workflow continues.
7. The adversarial analysis includes all four categories: uncovered edge cases, false LLD claims, missing error handling, and implicit assumptions.
8. All generated test files include a header comment block identifying them as adversarial (machine-generated by Gemini), including the issue ID and test category.

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **A: LangGraph node with Gemini Pro (structured JSON) + new wrapper module** | Integrates natively into existing workflow; JSON parseable; graceful degradation; no modification to non-existent files; wrapper isolates adversarial logic | Adds ~120s latency per run; token budget management needed; extra module to maintain | **Selected** |
| **B: Standalone script outside LangGraph** | Simple; no workflow changes; can run independently | No state sharing with testing workflow; duplicates context collection; no checkpointing; violates architectural pattern | Rejected |
| **C: Use Claude (same model) with adversarial persona prompt** | No second provider needed; lower latency | Same model = same blind spots; defeats the entire purpose of multi-model adversarial pressure (Issue #352's core thesis) | Rejected |
| **D: Use OpenAI GPT-4 as adversarial model** | Strong reasoning capability; different blind spots from Claude | New dependency; new API key management; not already in project deps; cost concerns | Rejected |
| **E: Modify `assemblyzero/utils/gemini_provider.py` directly** | Single source of truth for Gemini calls | File does not exist in repository (validation error); would couple adversarial logic to shared utility layer | Rejected |

**Rationale:** Option A was selected because it aligns with AssemblyZero's existing multi-model architecture (Claude builds, Gemini reviews), reuses the existing Gemini provider infrastructure via a new wrapper, and integrates naturally into the LangGraph testing workflow via state extension. The core requirement of Issue #352 is adversarial pressure from a *different* model, which eliminates Option C. Option E was rejected because `assemblyzero/utils/gemini_provider.py` does not exist in the repository, causing a mechanical validation failure.

## 5. Data & Fixtures

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | Implementation files from LangGraph state (in-memory); LLD from `docs/lld/active/` |
| Format | Python source code (str), Markdown (str) |
| Size | ~60KB combined (token-budget trimmed) |
| Refresh | Per-workflow-run (regenerated each execution) |
| Copyright/License | Project source code (PolyForm-Noncommercial-1.0.0) |

### 5.2 Data Pipeline

```
LangGraph State ──read──► _collect_context() ──trim──► build_adversarial_analysis_prompt()
    ──invoke──► AdversarialGeminiClient ──JSON──► _parse_gemini_response()
    ──render──► write_adversarial_tests() ──validate──► validate_adversarial_tests()
    ──files──► tests/adversarial/test_*.py
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| `sample_implementation.py` | Hardcoded in test | Minimal Python class with known edge cases for Gemini to find |
| `sample_lld.md` | Hardcoded in test | LLD with intentional overclaims (e.g., "handles all Unicode") |
| `sample_gemini_response.json` | Hardcoded in test | Valid AdversarialAnalysis JSON for parser tests |
| `sample_gemini_response_with_analysis.json` | Hardcoded in test | Valid JSON with all four analysis categories populated |
| `sample_mock_violation.py` | Hardcoded in test | Test file containing `from unittest.mock import patch` |
| `sample_valid_adversarial.py` | Hardcoded in test | Clean adversarial test file with no mocks |
| `sample_adversarial_with_header.py` | Hardcoded in test | Adversarial test file with expected header comment block |
| `sample_gemini_pro_metadata.json` | Hardcoded in test | Response metadata indicating Gemini Pro model used |
| `sample_gemini_flash_metadata.json` | Hardcoded in test | Response metadata indicating Gemini Flash (downgrade) |

### 5.4 Deployment Pipeline

Tests are generated at workflow runtime and committed to the PR branch. No separate deployment pipeline needed. Generated files in `tests/adversarial/` are tracked in git and run in CI like any other test.

## 6. Diagram

### 6.1 Mermaid Quality Gate

- [x] **Simplicity:** Similar components collapsed
- [x] **No touching:** All elements have visual separation
- [x] **No hidden lines:** All arrows fully visible
- [x] **Readable:** Labels not truncated, flow direction clear
- [ ] **Auto-inspected:** Agent rendered via mermaid.ink and viewed

**Auto-Inspection Results:**
```
- Touching elements: [x] None
- Hidden lines: [x] None
- Label readability: [x] Pass
- Flow clarity: [x] Clear
```

### 6.2 Diagram

```mermaid
graph TD
    subgraph TestingWorkflow["Testing Workflow N2.7"]
        A["Prior Nodes"]
        B["run_standard_tests"]
        C["run_adversarial_node"]
        D["evaluate_results"]
        E["log_skip_reason"]
    end

    subgraph AdversarialNode["Adversarial Node Internals"]
        C1["_collect_context<br/>Token-budget trim"]
        C2["build_adversarial<br/>_analysis_prompt"]
        C3["AdversarialGeminiClient<br/>.generate_adversarial_tests<br/>+ verify_model_is_pro"]
        C4["_parse_gemini_response<br/>Validate 4 analysis categories"]
        C5["write_adversarial_tests<br/>+ header comment block"]
        C6["validate_adversarial_tests<br/>AST no-mock scan<br/>Reject before write"]
    end

    subgraph Output["Generated Test Files"]
        F["tests/adversarial/<br/>test_*_boundary.py"]
        G["tests/adversarial/<br/>test_*_contract.py"]
        H["tests/adversarial/<br/>test_*_injection.py"]
    end

    A --> B
    B --> C
    C --> C1
    C1 --> C2
    C2 --> C3
    C3 -->|success| C4
    C3 -->|quota/downgrade/timeout| E
    C4 --> C5
    C5 --> C6
    C6 --> F
    C6 --> G
    C6 --> H
    C6 --> D
    E --> D
```

```mermaid
sequenceDiagram
    participant TW as Testing Workflow
    participant AN as Adversarial Node
    participant AGC as AdversarialGeminiClient
    participant Gemini as Gemini Pro API
    participant FS as File System
    participant Val as Validator

    TW->>AN: state (impl files, LLD, existing tests)
    AN->>AN: _collect_context() + trim to budget
    AN->>AN: build_adversarial_analysis_prompt()
    AN->>AGC: generate_adversarial_tests(prompt)
    AGC->>Gemini: POST /generateContent (Pro model)
    Gemini-->>AGC: JSON response + metadata
    AGC->>AGC: verify_model_is_pro(metadata)

    alt Quota Exhausted
        AGC-->>AN: GeminiQuotaExhaustedError
        AN-->>TW: state {verdict: error, skipped_reason}
    else Model Downgrade
        AGC-->>AN: GeminiModelDowngradeError
        AN-->>TW: state {verdict: error, skipped_reason}
    else Success
        AGC-->>AN: raw JSON string
        AN->>AN: _parse_gemini_response()
        AN->>AN: Verify 4 analysis categories present
        AN->>Val: validate_adversarial_tests() — AST no-mock scan
        Val-->>AN: ValidationResult (reject mocks before write)
        AN->>FS: write_adversarial_tests() with header comments
        FS-->>AN: {filepath: content}
        AN-->>TW: state {verdict, analysis, test_files, count}
    end
```

## 7. Security & Safety Considerations

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| Gemini-generated code execution | Generated tests are validated (syntax, no-mock) before writing; they are not executed by the adversarial node itself — CI runs them separately | Addressed |
| Code injection via Gemini response | JSON parsing with schema validation; test code is written to files, not `eval()`'d; AST analysis before write | Addressed |
| API key exposure in prompts | Implementation code is source code (not secrets); LLD is documentation; no credentials sent to Gemini | Addressed |
| Gemini API credential management | `AdversarialGeminiClient` delegates to existing provider credential handling (already audited) | Addressed |
| Malicious test file paths | Output directory hardcoded to `tests/adversarial/`; filenames sanitized (alphanumeric + underscore only) | Addressed |
| Silent model downgrade bypasses adversarial rigor | `verify_model_is_pro()` checks response metadata; raises `GeminiModelDowngradeError` if Flash detected | Addressed |

### 7.2 Safety

| Concern | Mitigation | Status |
|---------|------------|--------|
| Workflow blocked by Gemini unavailability | Graceful degradation: quota/downgrade/timeout all result in skip, not block | Addressed |
| Generated tests break CI | Tests are syntactically validated before writing; broken tests are excluded | Addressed |
| Runaway Gemini cost | Single invocation per workflow run; timeout cap (120s/180s); no retry loops | Addressed |
| Disk fill from generated tests | Category-based grouping limits file count; maximum of ~6 categories × 1 file each | Addressed |
| Partial write leaves corrupt files | Write to temp directory first, then atomic rename; on error, clean up temp files | Addressed |

**Fail Mode:** Fail Open — If adversarial generation fails, the testing workflow continues with standard tests only. Adversarial testing is additive, never blocking.

**Recovery Strategy:** If adversarial tests are corrupted or invalid, delete `tests/adversarial/` and re-run the testing workflow. The node is idempotent (overwrites existing files for the same issue).

## 8. Performance & Cost Considerations

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| Adversarial node latency | < 180s (worst case) | Single Gemini invocation with 120s timeout, one retry at 180s |
| Token budget (input) | ~60KB (~15K tokens) | Priority-based trimming: impl > LLD > existing tests |
| Token budget (output) | ~20KB (~5K tokens) | Gemini response limited by prompt instruction to ≤15 test cases |
| File I/O | < 1s | Writing ≤6 small Python files |
| Validation | < 2s | AST parsing is fast; no execution needed |

**Bottlenecks:** Gemini API latency is the dominant cost (~30-120s). This is acceptable because the adversarial node runs after standard tests (no critical path delay for core testing).

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| Gemini Pro API (input) | $0.00 (free tier) / $1.25/1M tokens (paid) | ~15K tokens/run × ~30 runs/month | $0.00 – $0.56 |
| Gemini Pro API (output) | $0.00 (free tier) / $5.00/1M tokens (paid) | ~5K tokens/run × ~30 runs/month | $0.00 – $0.75 |
| Disk storage | Negligible | ~6 files × ~5KB each | $0.00 |

**Cost Controls:**
- [x] Free tier covers expected usage (Gemini API free quota)
- [x] Single invocation per workflow run (no retry loops beyond one)
- [x] Graceful skip on quota exhaustion (no cost escalation)

**Worst-Case Scenario:** If usage spikes 10x (300 runs/month), cost remains < $15/month on paid tier. 100x would be $150/month but would indicate an automation bug (each run = one issue workflow).

## 9. Legal & Compliance

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | No | Only source code and documentation sent to Gemini; no user data |
| Third-Party Licenses | Yes | Gemini-generated test code is derivative of project code; PolyForm-Noncommercial covers generated tests |
| Terms of Service | Yes | Gemini API usage within Google's ToS; code sent is not confidential (open-source project) |
| Data Retention | N/A | Gemini API does not retain input data per Google's API ToS for paid tier |
| Export Controls | No | No restricted algorithms or data |

**Data Classification:** Internal (source code sent to Gemini is project code, not customer data)

**Compliance Checklist:**
- [x] No PII stored without consent
- [x] All third-party licenses compatible with project license
- [x] External API usage compliant with provider ToS
- [x] Data retention policy documented (Gemini API ToS)

## 10. Verification & Testing

### 10.0 Test Plan (TDD - Complete Before Implementation)

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | Adversarial node happy path | Given valid impl + LLD in state, generates test files and returns pass verdict | RED |
| T020 | Adversarial node Gemini quota skip | On GeminiQuotaExhaustedError, sets skipped_reason and returns error verdict | RED |
| T030 | Adversarial node Gemini downgrade skip | On GeminiModelDowngradeError, sets skipped_reason and returns error verdict | RED |
| T040 | Adversarial node empty implementation | With no implementation files, skips gracefully | RED |
| T050 | Gemini response parsing valid JSON | Parses well-formed AdversarialAnalysis JSON correctly | RED |
| T060 | Gemini response parsing malformed JSON | Raises ValueError on invalid JSON, node catches and sets error | RED |
| T070 | Writer groups by category | 3 boundary + 2 contract cases → 2 files created | RED |
| T080 | Writer file naming convention | Output file named `test_{issue_id}_{category}.py` | RED |
| T090 | Writer renders valid pytest syntax | Generated file passes `compile()` | RED |
| T100 | Validator detects `from unittest.mock import patch` | Returns mock_violation for the import | RED |
| T110 | Validator detects `MagicMock()` instantiation | Returns mock_violation | RED |
| T120 | Validator detects `@patch` decorator | Returns mock_violation | RED |
| T130 | Validator detects `monkeypatch` fixture usage | Returns mock_violation | RED |
| T140 | Validator passes clean test file | Returns valid=True, empty violations | RED |
| T150 | Validator detects missing assertions | Returns warning for test with no assert | RED |
| T160 | Validator detects syntax errors | Returns error for file that doesn't compile | RED |
| T170 | Prompt includes all context sections | Built prompt contains impl code, LLD, existing tests, patterns | RED |
| T180 | Prompt enforces no-mock constraint | System prompt explicitly forbids mocks | RED |
| T190 | Context trimming respects token budget | With oversized input, output fits within 60KB | RED |
| T200 | Integration: full Gemini invocation | Real Gemini call returns parseable adversarial analysis (mark: integration) | RED |
| T210 | AdversarialGeminiClient delegates to provider | Client correctly wraps and invokes underlying provider | RED |
| T220 | AdversarialGeminiClient timeout retry | On first timeout, retries once with extended timeout | RED |
| T230 | Gemini Pro model verification passes | verify_model_is_pro returns True for Pro metadata | RED |
| T240 | Gemini Flash downgrade detected | verify_model_is_pro raises GeminiModelDowngradeError for Flash metadata | RED |
| T250 | Validator rejects mock-containing tests before file write | Tests with mocks are excluded from generated_test_files dict | RED |
| T260 | Parsed analysis includes all four categories | _parse_gemini_response validates uncovered_edge_cases, false_claims, missing_error_handling, implicit_assumptions are present | RED |
| T270 | Analysis with missing category raises ValueError | JSON missing false_claims field causes ValueError | RED |
| T280 | Generated test file includes adversarial header comment | Written file starts with "# ADVERSARIAL TEST FILE" header block | RED |
| T290 | Header comment includes issue ID and category | Header contains issue number and category string | RED |

**Coverage Target:** ≥95% for all new code

**TDD Checklist:**
- [ ] All tests written before implementation
- [ ] Tests currently RED (failing)
- [ ] Test IDs match scenario IDs in 10.1
- [ ] Test files created at: `tests/unit/test_adversarial_node.py`, `tests/unit/test_adversarial_writer.py`, `tests/unit/test_adversarial_validator.py`, `tests/unit/test_adversarial_prompts.py`, `tests/unit/test_adversarial_gemini.py`

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Happy path: node generates tests (REQ-1) | Auto | State with impl files + LLD + mock Gemini response | State with verdict="pass", test_count > 0, generated files | Files written to tests/adversarial/, all valid |
| 020 | Gemini quota exhaustion (REQ-6) | Auto | State + GeminiQuotaExhaustedError raised | State with verdict="error", skipped_reason set | Workflow not blocked |
| 030 | Gemini model downgrade (REQ-2) | Auto | State + GeminiModelDowngradeError raised | State with verdict="error", skipped_reason contains "Flash" | Downgrade detected and logged |
| 040 | Empty implementation (REQ-6) | Auto | State with implementation_files={} | State with skipped_reason="No implementation files" | Immediate return, no Gemini call |
| 050 | Valid JSON parsing (REQ-7) | Auto | Well-formed AdversarialAnalysis JSON string with all 4 categories | AdversarialAnalysis TypedDict with all fields | All fields populated correctly including uncovered_edge_cases, false_claims, missing_error_handling, implicit_assumptions |
| 060 | Malformed JSON parsing (REQ-7) | Auto | Invalid JSON string `{broken` | ValueError raised | Error message includes "malformed" |
| 070 | Writer category grouping (REQ-4) | Auto | 5 test cases: 3 boundary, 2 contract | 2 files: test_352_boundary.py, test_352_contract.py | Correct category assignment |
| 080 | Writer file naming (REQ-4) | Auto | Issue ID=352, category="injection" | File named test_352_injection.py | Exact name match |
| 090 | Writer pytest compatibility (REQ-4) | Auto | Single test case | Output file compiles and contains `def test_` | compile() succeeds |
| 100 | Mock detect: import statement (REQ-5) | Auto | `from unittest.mock import patch` | 1 mock_violation | Violation identifies line |
| 110 | Mock detect: MagicMock (REQ-5) | Auto | `m = MagicMock()` | 1 mock_violation | Violation identifies usage |
| 120 | Mock detect: @patch decorator (REQ-5) | Auto | `@patch('module.func')` | 1 mock_violation | Violation identifies decorator |
| 130 | Mock detect: monkeypatch (REQ-5) | Auto | `def test_x(monkeypatch):` | 1 mock_violation | Violation identifies fixture |
| 140 | Clean file passes validation (REQ-3) | Auto | Valid test file, no mocks, has asserts | valid=True, empty violations | No errors, no warnings |
| 150 | Missing assertions warning (REQ-5) | Auto | `def test_x(): pass` | 1 warning | Warning names the function |
| 160 | Syntax error detection (REQ-5) | Auto | `def test_x(:\n  pass` | 1 error | Error includes SyntaxError details |
| 170 | Prompt content completeness (REQ-3) | Auto | Impl="def foo(): ...", LLD="## Req", tests="def test_foo():" | Prompt string contains all three | Substring checks pass |
| 180 | Prompt no-mock enforcement (REQ-3) | Auto | N/A (system prompt) | System prompt contains "NEVER" and "mock" | String assertion |
| 190 | Token budget trimming (REQ-2) | Auto | 200KB combined input | Output ≤ 60KB | len() check |
| 200 | Integration: real Gemini (REQ-2) | Auto-Live | Real impl code + LLD | Valid JSON response from Gemini Pro | JSON parses; model = Pro |
| 210 | Client delegates to provider (REQ-2) | Auto | Mock provider, valid inputs | Provider's generate method called with correct args | Method call assertion |
| 220 | Client timeout retry (REQ-6) | Auto | Provider raises timeout on first call, succeeds on second | Returns valid response after retry | Exactly 2 calls to provider |
| 230 | Gemini Pro model verification passes (REQ-2) | Auto | Response metadata with model="gemini-pro" | verify_model_is_pro returns True | Boolean True returned |
| 240 | Gemini Flash downgrade detected (REQ-2) | Auto | Response metadata with model="gemini-flash" | GeminiModelDowngradeError raised | Exception raised with "Flash" in message |
| 250 | Mock-containing tests rejected before write (REQ-5) | Auto | AdversarialAnalysis with 3 tests, 1 containing mock | generated_test_files contains only 2 valid tests | Mock test excluded from output dict |
| 260 | Parsed analysis includes all four categories (REQ-7) | Auto | JSON with uncovered_edge_cases, false_claims, missing_error_handling, implicit_assumptions | AdversarialAnalysis with all 4 lists populated | Each list is non-empty and correctly typed |
| 270 | Analysis missing category raises error (REQ-7) | Auto | JSON with false_claims field omitted | ValueError raised | Error message mentions missing field |
| 280 | Generated file has adversarial header (REQ-8) | Auto | Single test case, issue_id=352, category="boundary" | File content starts with `# ADVERSARIAL TEST FILE` | First line matches expected header |
| 290 | Header includes issue ID and category (REQ-8) | Auto | issue_id=352, category="injection" | Header contains "Issue: #352" and "Category: injection" | Substring checks pass |

### 10.2 Test Commands

```bash
# Run all adversarial node unit tests
poetry run pytest tests/unit/test_adversarial_node.py tests/unit/test_adversarial_writer.py tests/unit/test_adversarial_validator.py tests/unit/test_adversarial_prompts.py tests/unit/test_adversarial_gemini.py -v

# Run only fast/mocked tests (exclude integration)
poetry run pytest tests/unit/test_adversarial_*.py -v -m "not integration"

# Run integration tests (requires Gemini API key)
poetry run pytest tests/integration/test_adversarial_integration.py -v -m integration

# Run generated adversarial tests (after workflow produces them)
poetry run pytest tests/adversarial/ -v --no-header

# Run with coverage
poetry run pytest tests/unit/test_adversarial_*.py --cov=assemblyzero.workflows.testing --cov-report=term-missing
```

### 10.3 Manual Tests (Only If Unavoidable)

N/A - All scenarios automated. The integration test (T200) validates real Gemini interaction. Generated adversarial tests are validated programmatically via the validator.

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Gemini generates syntactically invalid Python | Med | High | AST-based syntax validation rejects bad files via `_check_syntax()` in `adversarial_validator.py`; only valid tests written to disk |
| Gemini ignores no-mock instruction and generates mocks | Med | Med | AST-based mock detector `_check_no_mocks()` in `adversarial_validator.py` strips offending tests before file write; system prompt reinforces constraint via `build_adversarial_system_prompt()` |
| Gemini returns non-JSON response | Med | Low | JSON parse wrapped in try/except in `_parse_gemini_response()`; malformed response → graceful skip |
| Gemini quota exhaustion during CI | Low | Med | Graceful degradation in `run_adversarial_node()` catches `GeminiQuotaExhaustedError`; workflow continues without adversarial tests; logged for monitoring |
| Gemini silently downgrades Pro to Flash | Med | Med | `verify_model_is_pro()` in `AdversarialGeminiClient` checks response metadata; raises `GeminiModelDowngradeError` if Flash detected |
| Generated tests are trivial/useless | Low | Med | Adversarial patterns knowledge base (`get_adversarial_patterns()`) guides Gemini; prompt includes examples of high-value edge cases |
| Token budget exceeded (large implementations) | Low | Med | Priority-based trimming in `_collect_context()`; implementation code prioritized over LLD/existing tests |
| Adversarial tests fail on correct code (false positives) | Med | Med | Tests are generated, not auto-enforced; human reviews adversarial test output before acting on failures |
| Gemini omits analysis categories (incomplete analysis) | Med | Low | `_parse_gemini_response()` validates all four required categories are present; raises ValueError if any missing |
| State schema change breaks existing nodes | High | Low | `total=False` on `AdversarialNodeState`; existing nodes ignore unknown fields |
| Underlying Gemini provider API changes | Med | Low | `AdversarialGeminiClient` wrapper isolates adversarial logic from provider internals; only wrapper needs updating |
| Generated test files lack provenance identification | Low | Low | `_render_test_file()` prepends a mandatory header comment block identifying file as adversarial, machine-generated, with issue ID and category |

## 12. Definition of Done

### Code
- [ ] `adversarial_node.py` implements full LangGraph node with graceful degradation
- [ ] `adversarial_writer.py` generates valid pytest files grouped by category with atomic writes and adversarial header comments
- [ ] `adversarial_validator.py` enforces no-mock constraint via AST analysis, rejecting violations before file write
- [ ] `adversarial_prompts.py` builds structured prompts with no-mock enforcement and four-category analysis requirement
- [ ] `adversarial_state.py` defines TypedDicts for state extension
- [ ] `adversarial_patterns.py` provides curated adversarial pattern knowledge base
- [ ] `adversarial_gemini.py` wraps existing Gemini provider with adversarial invocation logic and model verification
- [ ] `graph.py` modified to wire adversarial node into testing workflow
- [ ] Code comments reference this LLD (#352)

### Tests
- [ ] All 29 test scenarios pass (T010–T290)
- [ ] Test coverage ≥95% for all new code
- [ ] No mock violations in generated adversarial test fixtures
- [ ] Integration test passes with real Gemini Pro

### Documentation
- [ ] LLD updated with any deviations
- [ ] Implementation Report (0103) completed
- [ ] Test Report (0113) completed

### Review
- [ ] Code review completed
- [ ] User approval before closing issue

### 12.1 Traceability (Mechanical - Auto-Checked)

Mechanical validation automatically checks:
- Every file in Definition of Done appears in Section 2.1 ✅
- Every risk mitigation references a corresponding function in Section 2.4 ✅

| DoD File | Section 2.1 Entry |
|----------|-------------------|
| `adversarial_node.py` | `assemblyzero/workflows/testing/nodes/adversarial_node.py` — Add ✅ |
| `adversarial_writer.py` | `assemblyzero/workflows/testing/nodes/adversarial_writer.py` — Add ✅ |
| `adversarial_validator.py` | `assemblyzero/workflows/testing/nodes/adversarial_validator.py` — Add ✅ |
| `adversarial_prompts.py` | `assemblyzero/workflows/testing/adversarial_prompts.py` — Add ✅ |
| `adversarial_state.py` | `assemblyzero/workflows/testing/adversarial_state.py` — Add ✅ |
| `adversarial_patterns.py` | `assemblyzero/workflows/testing/knowledge/adversarial_patterns.py` — Add ✅ |
| `adversarial_gemini.py` | `assemblyzero/workflows/testing/adversarial_gemini.py` — Add ✅ |
| `graph.py` | `assemblyzero/workflows/testing/graph.py` — Modify ✅ |

| Risk Mitigation | Function Reference |
|-----------------|-------------------|
| "Gemini generates syntactically invalid Python" | `_check_syntax()` in `adversarial_validator.py` (Section 2.4) ✅ |
| "Gemini ignores no-mock instruction" | `_check_no_mocks()` in `adversarial_validator.py` (Section 2.4) ✅ |
| "Gemini returns non-JSON response" | `_parse_gemini_response()` in `adversarial_node.py` (Section 2.4) ✅ |
| "Gemini quota exhaustion during CI" | `AdversarialGeminiClient.generate_adversarial_tests()` raises `GeminiQuotaExhaustedError` (Section 2.4) ✅ |
| "Gemini silently downgrades Pro to Flash" | `AdversarialGeminiClient.verify_model_is_pro()` (Section 2.4) ✅ |
| "Token budget exceeded" | `_collect_context()` in `adversarial_node.py` (Section 2.4) ✅ |
| "Gemini omits analysis categories" | `_parse_gemini_response()` validates all four categories (Section 2.4) ✅ |
| "Generated test files lack provenance identification" | `_render_test_file()` prepends header comment block (Section 2.4) ✅ |
| "Underlying Gemini provider API changes" | `AdversarialGeminiClient` wrapper class (Section 2.4) ✅ |

### 12.2 Requirements Traceability Matrix

| Requirement | Test Scenarios | Coverage |
|-------------|---------------|----------|
| REQ-1 | 010 | ✅ |
| REQ-2 | 030, 190, 200, 210, 230, 240 | ✅ |
| REQ-3 | 140, 170, 180 | ✅ |
| REQ-4 | 070, 080, 090 | ✅ |
| REQ-5 | 100, 110, 120, 130, 150, 160, 250 | ✅ |
| REQ-6 | 020, 040, 220 | ✅ |
| REQ-7 | 050, 060, 260, 270 | ✅ |
| REQ-8 | 280, 290 | ✅ |

---

## Reviewer Suggestions

*Non-blocking recommendations from the reviewer.*

- **Caching Optimization:** In `run_adversarial_node`, consider computing a SHA256 hash of `(implementation_code + lld_content)`. If a file `tests/adversarial/.meta_{issue_id}` exists with the matching hash, skip regeneration to save time and API costs.
- **Header Standardization:** Ensure the header comment format strictly matches what `validate_adversarial_tests` expects if the validator ever checks for provenance in the future (currently it just checks syntax/mocks, which is fine).

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-02-27 | APPROVED | `gemini-3-pro-preview` |
| Mechanical Validation | 2026-02-17 | FEEDBACK | `assemblyzero/utils/gemini_provider.py` marked Modify but does not exist |
| Self-Revision | 2026-02-17 | REVISED | Replaced non-existent file modification with new `adversarial_gemini.py` wrapper module |
| Mechanical Test Plan Validation | 2026-02-17 | FEEDBACK | 50% coverage — REQ-2, REQ-5, REQ-7, REQ-8 had no test coverage |
| Self-Revision #2 | 2026-02-17 | REVISED | Added 7 new test scenarios (T230–T290); added (REQ-N) suffixes to all Section 10.1 scenarios; reformatted Section 3 as numbered list |

**Final Status:** APPROVED