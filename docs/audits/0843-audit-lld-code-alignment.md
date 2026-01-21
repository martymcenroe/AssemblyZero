# 0843 - LLD-to-Code Alignment Audit

**Status:** STUB - Implementation pending
**Category:** Documentation Health
**Frequency:** On change (post-implementation)
**Auto-Fix:** No (requires human judgment)

---

## Purpose

Verify that Low-Level Design documents match actual implementation. LLDs are promises; code is reality. This audit catches the drift.

---

## Checks

### 1. Interface Drift

Compare LLD-specified interfaces to actual code:

| LLD Specifies | Code Has | Status |
|---------------|----------|--------|
| `def process(input: str) -> Result` | `def process(input: str, timeout: int = 30) -> Result` | DRIFT - new param |
| Class `UserManager` | Class `UserService` | DRIFT - renamed |
| Module `auth/` | Module `authentication/` | DRIFT - restructured |

**Suggested implementation:**
- Parse LLD for function signatures, class names, module paths
- Use AST parsing to extract actual signatures from code
- Diff and flag mismatches

### 2. Data Model Drift

LLDs often specify data structures. Compare to actual:
- Field names and types
- Relationships (1:1, 1:N, N:N)
- Constraints (nullable, unique, indexed)

### 3. Sequence Diagram Drift

If LLD includes sequence diagrams:
- Extract actor/component names
- Verify those components exist in code
- Check call order matches actual flow

### 4. Missing Implementation

LLD describes feature X, but:
- No code exists for X
- Code exists but is commented out
- Code exists but throws `NotImplementedError`

### 5. Scope Creep Detection

Code implements features NOT in LLD:
- Could indicate undocumented changes
- Could indicate LLD wasn't updated
- Either way, documentation debt

---

## Complexity Considerations

This is one of the harder audits to automate because:
1. LLDs use natural language, code uses syntax
2. Intent vs implementation gap
3. Acceptable drift vs problematic drift

**Suggested approach:**
- Start with simple pattern matching (class names, function names)
- Graduate to semantic comparison using LLM
- Human review for edge cases

---

## Suggestions for Future Implementation

1. **LLD Versioning**: Track LLD versions alongside code versions. "This code was built from LLD v1.2"

2. **Bidirectional Updates**: When code changes, flag if LLD needs update. When LLD changes, flag if code needs update.

3. **Gemini-Assisted Comparison**: Feed LLD + code to Gemini, ask "does this implementation match this design?"

4. **Coverage Metrics**: What % of LLD is implemented? What % of code is documented in LLD?

5. **Decision Record Linkage**: When implementation deviates from LLD, require an ADR explaining why.

---

## Audit Record

| Date | Auditor | Findings | Issues Created |
|------|---------|----------|----------------|
| - | - | STUB - Not yet implemented | - |

---

## Related

- [0102 - Feature LLD Template](../templates/0102-feature-lld-template.md)
- [0842 - Reports Completeness](0842-audit-reports-completeness.md)
