---
repo: martymcenroe/AssemblyZero
issue: 607
url: https://github.com/martymcenroe/AssemblyZero/issues/607
fetched: 2026-03-06T07:44:57.859227Z
---

# Issue #607: feat: Mechanical Document Assembly Node

## Objective
Transition from LLM-generated documents to Code-assembled documents to eliminate "Section Number Drift" and ensure 100% template compliance.

## Problem
Currently, we ask LLMs to generate entire Markdown documents (LLDs, Specs) from a template. LLMs frequently drift from these templates, using the wrong section numbers (e.g., Section 10 vs 9) or omitting mandatory sections. This causes mechanical validation failures and wastes tokens on retries.

## Proposed Solution: Mechanical Assembly Node
1. **Structural Ownership:** The LangGraph node (Python code) owns the Markdown headers and structure.
2. **Section-by-Section Generation:** The node iterates through the required sections.
3. **Targeted Prompts:** For each section, the LLM is given a specific prompt: "Provide the content for Section 2.5: Logic Flow based on the provided issue."
4. **Assembly:** The code concatenates the headers and LLM-generated content into the final file.

## Benefits
- **Physical Compliance:** Section numbers are hardcoded in the assembly logic and cannot drift.
- **Granular Quality Gates:** Validate and retry individual sections rather than the entire document.
- **Token Efficiency:** Only send/receive the context relevant to the specific section being built.

## Acceptance Criteria
- [ ] New LangGraph node pattern for "Assembled Documents".
- [ ] Prototype implementation for the LLD workflow.
- [ ] No manual section numbering required from the drafter LLM.

## Related
- #600 (Triggering failure)
- Standard 0010 (Golden Schema)
