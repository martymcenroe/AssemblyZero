# Issue #147: feat: Implementation Completeness Gate (anti-stub detection)

# Implementation Completeness Gate - Anti-Laziness System

## Problem Statement

Claude produces stub implementations that pass tests because the tests themselves are stubs. The current pipeline has no gate that catches:
- `pass`, `...`, `NotImplementedError` in function bodies
- `assert True`, `assert x is not None` weak tests
- CLI flags defined in argparse but never used
- Mock-everything tests that verify mocks, not behavior

## Solution: Two-Layer Completeness Gate

A new **N4b_completeness_gate** node inserted between N4 (implement_code) and N5 (verify_green) that performs:

1. **Static Analysis** (fast, local, deterministic) - Catches obvious patterns
2. **Gemini Semantic Review** (if static passes) - Catches subtle incompleteness

If BLOCKED, loops back to N4_implement_code with feedback.

---

## Architecture

```
Current:  N4_implement_code â†’ N5_verify_green
Proposed: N4_implement_code â†’ N4b_completeness_gate â†’ N5_verify_green
                                      â†“ (BLOCK)
                              N4_implement_code (loop)
```

---

## Files to Create

### 1. Static Analyzer Module
**Path:** `agentos/workflows/testing/completeness/__init__.py`
**Path:** `agentos/workflows/testing/completeness/static_analyzer.py`

Detects patterns via regex and AST:

| Category | Pattern | Severity |
|----------|---------|----------|
| Stub body | `pass` alone | BLOCK |
| Stub body | `...` alone | BLOCK |
| Stub body | `raise NotImplementedError` | BLOCK |
| Weak test | `assert True` | BLOCK |
| Weak test | `assert x is not None` (alone) | BLOCK |
| Skip abuse | `pytest.skip()` without reason | BLOCK |
| Mock abuse | Function returns only `Mock()` | WARN |

### 2. Completeness Gate Node
**Path:** `agentos/workflows/testing/nodes/completeness_gate.py`

```python
def completeness_gate(state: TestingWorkflowState) -> dict[str, Any]:
    """N4b: Verify implementation is complete and real."""
    # Layer 1: Static analysis
    static_result = analyze_implementation(impl_files, test_files)
    if static_result["verdict"] == "BLOCK":
        return {"completeness_verdict": "BLOCK", ...}

    # Layer 2: Gemini semantic review
    gemini_verdict = call_gemini_review(state, static_result)
    return {"completeness_verdict": gemini_verdict, ...}
```

### 3. Gemini Prompt
**Path:** `docs/skills/0707c-Completeness-Review-Prompt.md`

Tier 1 BLOCKING checks:
- Empty function bodies (stub detection)
- Tautological assertions (assert True)
- Skip abuse (pytest.skip without reason)
- Mock-everything tests
- Feature completeness vs LLD

---

## Files to Modify

### 1. Workflow Graph
**Path:** `agentos/workflows/testing/graph.py`

Add node and routing:
```python
workflow.add_node("N4b_completeness_gate", completeness_gate)

workflow.add_conditional_edges(
    "N4_implement_code",
    route_after_implement,
    {"N4b_completeness_gate": "N4b_completeness_gate", "end": END}
)

workflow.add_conditional_edges(
    "N4b_completeness_gate",
    route_after_completeness_gate,
    {"N5_verify_green": "N5_verify_green", "N4_implement_code": "N4_implement_code", "end": END}
)
```

### 2. Workflow State
**Path:** `agentos/workflows/testing/state.py`

Add fields:
```python
completeness_check_passed: bool
completeness_static_issues: list[dict]
completeness_verdict: Literal["PASS", "WARN", "BLOCK"]
```

### 3. Node Exports
**Path:** `agentos/workflows/testing/nodes/__init__.py`

Add export:
```python
from agentos.workflows.testing.nodes.completeness_gate import completeness_gate
```

### 4. Enhance Existing Prompt
**Path:** `docs/skills/0703c-Implementation-Review-Prompt.md`

Promote Test Integrity from Tier 2 to Tier 1 BLOCKING:
- Test Reality: Tests must exercise real code, not just mocks
- Stub Detection: Reject implementations with only pass/...
- Weak Assertions: Reject assert True patterns

---

## Routing Logic

```python
def route_after_completeness_gate(state) -> Literal["N5_verify_green", "N4_implement_code", "end"]:
    verdict = state.get("completeness_verdict", "")
    iteration = state.get("iteration_count", 0)
    max_iter = state.get("max_iterations", 10)

    if verdict == "BLOCK":
        if iteration >= max_iter:
            return "end"  # Give up
        return "N4_implement_code"  # Try again

    return "N5_verify_green"  # Proceed
```

---

## Verification Plan

1. **Unit tests for static analyzer:**
   - Test each pattern detection
   - Test AST-based empty function detection
   - Test combined analysis

2. **Integration test for completeness gate:**
   - Mock mode should pass
   - File with `pass` should BLOCK
   - File with `assert True` should BLOCK
   - Clean file should PASS

3. **E2E test:**
   - Run workflow with intentionally stubbed implementation
   - Verify it loops back and eventually fails or fixes

4. **Manual verification:**
   ```bash
   poetry run python tools/run_requirements_workflow.py \
     --type lld --issue 142 --gates none --mock
   ```

---

## Related Issues

- #142, #143, #144, #145, #146

---

## Summary

| Component | Purpose |
|-----------|---------|
| `static_analyzer.py` | Fast pattern detection (regex + AST) |
| `completeness_gate.py` | N4b node combining static + Gemini |
| `0707c-*.md` | Gemini prompt for semantic review |
| `graph.py` changes | Insert N4b between N4 and N5 |
| `0703c-*.md` changes | Promote Test Integrity to Tier 1 |

This creates a bulletproof gate that catches lazy implementations before they can pass fake tests.