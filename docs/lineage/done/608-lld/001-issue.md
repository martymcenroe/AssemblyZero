---
repo: martymcenroe/AssemblyZero
issue: 608
url: https://github.com/martymcenroe/AssemblyZero/issues/608
fetched: 2026-03-06T05:14:22.592620Z
---

# Issue #608: chore: Align Section Numbers between LLD and Implementation Spec Templates

## Objective
Standardize section numbering between the **LLD Template** and the **Implementation Spec Template (Standard 0701)** to prevent LLM cognitive drift and mechanical parsing failures.

## Problem
Currently, there is a collision in how testing/verification is indexed:
- **LLD Template:** Uses `## 10. Verification & Testing`.
- **Implementation Spec:** Uses `## 9. Test Mapping`.

When an agent generates an Implementation Spec, it uses the approved LLD as context. The presence of "Section 10" in the LLD frequently causes the agent to ignore the Spec template and output "Section 10" for the Spec as well. This trips the mechanical validator, which strictly expects "Section 9" for specs.

## Proposed Solution
Align both templates to use the same section number for testing-related content.
- **Recommendation:** Standardize on **Section 10** for both, as the LLD is the "parent" document and already uses this index.
- Update `docs/standards/0701-implementation-spec-template.md` to use `## 10. Test Mapping`.
- Update the parser logic in `assemblyzero/workflows/testing/nodes/load_lld.py` to canonicalize on Section 10.

## Acceptance Criteria
- [ ] Implementation Spec Template (0701) updated to Section 10.
- [ ] Mechanical parsers updated to expect Section 10 for both LLDs and Specs.
- [ ] LLD Generator skills updated to reflect the new unified indexing.

## Related
- #600 (Triggering implementation)
- #606 (Systemic assembly solution)
