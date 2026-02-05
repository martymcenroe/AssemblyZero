---
repo: martymcenroe/AgentOS
issue: 312
url: https://github.com/martymcenroe/AgentOS/issues/312
fetched: 2026-02-05T03:25:58.516058Z
---

# Issue #312: Reduce false positive warnings in mechanical LLD validation for approach-style mitigations

## Problem

The mechanical validation in `agentos/workflows/requirements/nodes/validate_mechanical.py` produces false positive warnings when risk mitigations describe *approaches* rather than *function names*.

**Current behavior:** The `trace_mitigations_to_functions()` function (lines 509-549) extracts keywords from mitigation text and checks if any match function names from Section 2.4. It warns when no match is found.

**Example false positives from RCA-PDF-extraction-pipeline#6:**
```
MECHANICAL VALIDATION WARNINGS:
  - Risk mitigation has no matching function: 'O(n) transformation, tested with 500+ rows...'
  - Risk mitigation has no matching function: 'Use UTF-8 encoding explicitly...'
```

These mitigations are legitimate but don't reference functions - they describe algorithmic complexity and coding practices.

## Current Severity

**Trivial** - These are warnings (not errors), don't block the workflow, and the design is intentional ("warning only" per line 11). But they add noise to output.

## Proposed Solution

Make the validator smarter about when to warn:

1. **Only warn when mitigation contains explicit function syntax:**
   - Backticks: `` `function_name` ``
   - Parentheses: `function_name()`
   - Pattern: `in function_name`

2. **Skip "approach" mitigations** that describe practices:
   - Complexity claims: "O(n)", "O(1)"
   - Encoding: "UTF-8", "encoding"
   - Flags: "opt-in", "default unchanged"

## Acceptance Criteria

- [ ] Mitigations with explicit function references (backticks, `()`) still trigger warnings if function missing
- [ ] Mitigations describing approaches (complexity, encoding, practices) don't trigger false warnings
- [ ] Existing test coverage maintained

## Context

Discovered during first cross-repo test of requirements workflow from AgentOS to RCA-PDF-extraction-pipeline.