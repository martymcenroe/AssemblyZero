# ADR-0210: Discworld Persona Convention

**Status:** Accepted
**Date:** 2026-03-01
**Issue:** #114

## 1. Context

AssemblyZero names its autonomous agents and workflows after Terry Pratchett's Discworld characters. This began organically — Vimes for regression testing (deep suspicion), the Librarian for documentation retrieval ("Oook") — and has grown into a consistent system. With 12 personas now in use, we need to formalize the convention so future agents follow the same principles.

## 2. Decision

Every workflow or agent subsystem in AssemblyZero **should** be mapped to a Discworld character when:

1. The subsystem has a distinct operational philosophy (not just a utility function)
2. A Discworld character's personality maps naturally to that philosophy
3. The mapping aids developer intuition about what the subsystem does

### Naming Rules

- **Persona names are canonical identifiers.** "The Librarian" is the RAG retrieval node. "Lu-Tze" is the janitor. Use these names in documentation, commit messages, and issue titles.
- **Source material matters.** Each persona entry must cite the Discworld book(s) that define the character. This grounds the mapping in Pratchett's writing, not vague associations.
- **One persona per domain.** No two personas should overlap in function. If a new workflow overlaps with an existing persona's domain, extend the existing persona rather than creating a new one.
- **Quotes are required.** Every persona must have at least one representative quote from the books. This anchors the philosophy.

### Persona-to-Workflow Mapping (Current)

| Persona | Domain | Workflow / Module | Issue |
|---------|--------|-------------------|-------|
| Om | Human orchestrator | (human-in-the-loop) | — |
| Moist von Lipwig | Pipeline orchestration | End-to-end pipeline | #305 |
| Lord Vetinari | Work visibility | GitHub Projects (planned) | — |
| Commander Vimes | Regression testing | (planned) | — |
| Captain Angua | External intelligence | Scout workflow | #93 |
| Brutha | Vector database / RAG | `assemblyzero/rag/` | #113 |
| The Librarian | Document retrieval | LibrarianNode | #88 |
| Hex | Codebase intelligence | Codebase retrieval | #92 |
| The Historian | Duplicate detection | Historian node | #91 |
| Lu-Tze | Repository hygiene | Janitor workflow | #94 |
| Lord Downey | Safe code deletion | (planned) | — |
| DEATH | Documentation reconciliation | (this issue) | #114 |

### When NOT to Create a Persona

- Pure utility scripts (e.g., `gemini-rotate.py`) don't need personas
- One-off tools that don't embody a philosophy
- Internal implementation details that users never interact with

## 3. Consequences

### Positive
- Developers can intuit workflow behavior from the persona name
- Documentation stays engaging and memorable
- Consistent mental model across the entire system
- New contributors can understand system architecture through familiar archetypes

### Negative
- Requires Discworld familiarity (mitigated by wiki documentation with full character context)
- Naming can feel forced if the character doesn't fit — resist the urge to force-fit

## 4. References

- [Dramatis Personae wiki page](https://github.com/martymcenroe/AssemblyZero/wiki/Dramatis-Personae)
- [Terry Pratchett's Discworld](https://www.terrypratchettbooks.com/discworld/)
- [L-Space Web](https://www.lspace.org/)
