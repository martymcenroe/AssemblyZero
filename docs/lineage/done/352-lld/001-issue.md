---
repo: martymcenroe/AssemblyZero
issue: 352
url: https://github.com/martymcenroe/AssemblyZero/issues/352
fetched: 2026-02-27T07:51:48.024927Z
---

# Issue #352: feat: Multi-Model Adversarial Testing Node (Gemini vs Claude)

### Problem
Currently, the same model (Claude) that implements code also scaffolds the tests. There is no "adversarial pressure" from a competing model to find edge cases or expose false claims.

### Proposed Solution
Integrate a new node into the Testing Workflow (N2.7) where a separate LLM (Gemini Pro) analyzes the implementation and the LLD claims to write aggressive, unmocked adversarial tests.

### Requirements
- Integration into the LangGraph Testing Workflow.
- Use of a separate provider (Gemini) from the implementer (Claude).
- Generation of \`tests/adversarial/test_*.py\`.
- No mocks allowed in adversarial tests.