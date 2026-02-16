---
repo: martymcenroe/AssemblyZero
issue: 147
url: https://github.com/martymcenroe/AssemblyZero/issues/147
fetched: 2026-02-16T07:05:14.516987Z
---

# Issue #147: feat: Implementation Completeness Gate (anti-stub detection)

# Implementation Completeness Gate (Redesigned)

## Problem Statement

Claude produces implementations that pass tests because neither the tests nor the implementation are scrutinized for *semantic completeness*. The current pipeline has:
- **N2.5** (mechanical test validation) — catches stub *tests* (assert False, NotImplementedError, missing assertions)
- **N4** (implement_code) — validates *syntax* and minimum size
- **N5** (verify_green) — confirms tests pass + coverage target

**The gap:** Nothing verifies that the *implementation actually fulfills the LLD requirements*. A syntactically valid, test-passing implementation can still be incomplete.

### Actual Problems (from codebase scan, issues #149-#156, all now closed)

The original issue targeted `pass`/`...`/`assert True` — these turned out to be mostly false positives. The **real** problems found in production were:

| Problem | Example | Detection Method |
|---------|---------|-----------------|
| Argparse flags defined but never wired | `--select` parsed but never used | AST: trace `add_argument` to usage |
| Docstrings promising nonexistent behavior | "Retries with backoff" but no retry loop | Gemini semantic review |
| Mock-mode branches that silently fail | `if mock_mode: return None` | AST: empty/trivial conditional branches |
| Tests verifying existence, not behavior | `assert result is not None` as only check | AST: assertion quality analysis |

## Solution: Two-Layer Completeness Gate (N4b)

### Architecture

```
Current:  N4_implement_code → N5_verify_green
Proposed: N4_implement_code → N4b_completeness_gate → N5_verify_green
                                      ↓ (BLOCK)
                              N4_implement_code (loop)
```

### Layer 1: AST-Based Analysis (fast, deterministic)

Targets the **real** problems, not false-positive patterns:

| Check | What It Catches | Method |
|-------|----------------|--------|
| Dead CLI flags | `add_argument` with no corresponding usage | AST: trace argument names to function calls |
| Empty conditional branches | `if condition: pass` or `if condition: return None` | AST: branch body analysis |
| Docstring-only functions | Functions with docstring + `pass`/`return None` only | AST: function body depth |
| Trivial assertions | `assert x is not None` as the *sole* assertion in a test | AST: assertion quality scoring |
| Unused imports from implementation | Import statements with no usage in function bodies | AST: import-to-usage mapping |

**Deliberately excluded** (high false-positive rate):
- Bare `pass` statements (legitimate in exception handlers, abstract methods)
- `...` (used in prompt templates, type stubs)
- `assert True` (not actually found in codebase)

### Layer 2: Gemini Semantic Review (if Layer 1 passes)

**Orchestrator-controlled** per WORKFLOW.md — Claude prepares materials, orchestrator submits to Gemini.

Review prompt focus:
1. **LLD Requirement Mapping** — For each Section 3 requirement, does corresponding code exist? (Carried forward from #181)
2. **Behavioral Completeness** — Do functions do what their docstrings/names promise?
3. **Integration Completeness** — Are new functions actually called from the workflow/CLI entry points?

### Output: Verification Report (carried forward from #181)

The gate produces `docs/reports/active/{issue}-implementation-report.md` as a side effect:

```markdown
# Implementation Report: Issue #{issue}

## LLD Requirement Verification

| # | Requirement | Status | Evidence |
|---|-------------|--------|----------|
| 1 | Rate-limit backoff | ✅ Implemented | `coordinator.py:142` — exponential_backoff() |
| 2 | Retry on 429 | ✅ Implemented | `coordinator.py:158` — retry loop with 429 check |

## Completeness Analysis

| Check | Result | Details |
|-------|--------|---------|
| Dead CLI flags | ✅ PASS | 0 unused arguments |
| Empty branches | ✅ PASS | 0 trivial branches |
| Assertion quality | ⚠️ WARN | test_init.py:45 — sole assertion is `is not None` |

## Stub/TODO Detection

| File | Line | Pattern |
|------|------|---------|
| (none found) | | |
```

This populates the `implementation_report_path` state field (#181's gap).

## Files to Create

| File | Purpose |
|------|---------|
| `assemblyzero/workflows/testing/completeness/__init__.py` | Package |
| `assemblyzero/workflows/testing/completeness/ast_analyzer.py` | Layer 1 AST analysis |
| `assemblyzero/workflows/testing/completeness/report_generator.py` | Verification report output (from #181) |
| `assemblyzero/workflows/testing/nodes/completeness_gate.py` | N4b workflow node |
| `tests/test_completeness_gate.py` | Real tests (no mocks) |

## Files to Modify

| File | Change |
|------|--------|
| `assemblyzero/workflows/testing/graph.py` | Insert N4b between N4 and N5, add routing |
| `assemblyzero/workflows/testing/state.py` | Add `completeness_verdict`, `completeness_issues` fields |
| `assemblyzero/workflows/testing/nodes/__init__.py` | Export completeness_gate |

## Routing Logic

```python
def route_after_completeness_gate(state) -> Literal["N5_verify_green", "N4_implement_code", "end"]:
    verdict = state.get("completeness_verdict", "")
    iteration = state.get("iteration_count", 0)
    max_iter = state.get("max_iterations", 10)

    if verdict == "BLOCK":
        if iteration >= max_iter:
            return "end"  # Give up
        return "N4_implement_code"  # Try again with feedback

    return "N5_verify_green"  # Proceed
```

## Verification Plan

1. **Unit tests for AST analyzer** — feed it known-bad code samples, verify detection
2. **Integration test for completeness gate node** — run through workflow state machine
3. **Regression tests** — use the actual patterns from closed issues #149-#156 as test fixtures
4. **Manual E2E** — run workflow with intentionally incomplete implementation, verify block

## Subsumes

- **#181** (Implementation Report with LLD Requirement Verification) — closed as duplicate, report generation carried forward here

## Related Issues

- #335 — N2.5 mechanical test validation (architectural precedent for this gate)
- #225 — Skipped test enforcement (partial detection overlap on pytest.skip)
- #354 — Mutation testing (deep-frozen, Layer 3 verification for after this is proven)
- #149-#156 — Codebase scan findings (all closed, inform detection targets)