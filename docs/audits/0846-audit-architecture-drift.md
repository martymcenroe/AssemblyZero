# 0846 - Architecture Drift Audit

**Status:** STUB - Implementation pending
**Category:** Documentation Health
**Frequency:** Monthly
**Auto-Fix:** Partial (can detect drift, fix requires human)

---

## Purpose

Detect when code structure diverges from documented architecture. Architecture docs describe intent; code represents reality. When they diverge, either the code is wrong or the docs are stale.

---

## Checks

### 1. Directory Structure Drift

Compare documented structure to actual:

```
Documented (in README.md):       Actual (from ls):
AgentOS/                         AgentOS/
├── tools/                       ├── tools/
├── docs/                        ├── docs/
├── .claude/                     ├── .claude/
└── tests/                       ├── tests/
                                 └── logs/          ← UNDOCUMENTED
```

### 2. Module Dependency Drift

If architecture specifies "X should not depend on Y":
- Parse imports in Python files
- Build dependency graph
- Flag violations

**Example violations:**
- `tools/` importing from `tests/`
- Circular imports
- Layer violations (UI importing directly from DB)

### 3. Component Existence Drift

Architecture diagrams reference components:
- Does `UserAuthenticator` exist?
- Is it in the documented location?
- Does it have the documented interface?

### 4. Data Flow Drift

If architecture specifies data flow:
```
User → API Gateway → Lambda → DynamoDB
```

Verify actual call patterns match (via code analysis or logs).

### 5. Technology Stack Drift

Documented: "Python 3.12, Poetry, pytest"
Actual: Check `pyproject.toml`, CI configs, actual runtime

Flag mismatches:
- Docs say SQLite, code uses PostgreSQL
- Docs say REST, code uses GraphQL

---

## Architecture Verification Levels

| Level | What We Check | Automation |
|-------|---------------|------------|
| **L1 - Structure** | Directories exist | Full |
| **L2 - Components** | Files/classes exist | Full |
| **L3 - Interfaces** | Signatures match | Partial |
| **L4 - Behavior** | Logic matches docs | Manual |
| **L5 - Intent** | Design rationale valid | Manual |

This audit focuses on L1-L3. L4-L5 require Gemini or human review.

---

## Architecture Document Locations

| Document | Purpose | Staleness Risk |
|----------|---------|----------------|
| `README.md` | High-level structure | Medium |
| `docs/index.md` | Documentation map | High |
| `CLAUDE.md` | Agent rules | Low (frequently touched) |
| ADRs | Design decisions | Low (immutable by design) |
| C4 diagrams | Visual architecture | High |

---

## Suggestions for Future Implementation

1. **Automated Diagram Generation**: Generate C4 diagrams from actual code, compare to documented diagrams.

2. **Import Graph Visualization**: Build and visualize actual dependency graph, overlay on documented architecture.

3. **Refactoring Detection**: Detect large-scale moves/renames that likely invalidate architecture docs.

4. **Architecture Fitness Functions**: Codify architectural constraints as tests that run in CI.

5. **Gemini Architecture Review**: Feed architecture docs + code structure to Gemini, ask "does this code follow this architecture?"

6. **Evolution Tracking**: When architecture intentionally changes, require ADR. Detect undocumented evolution.

7. **Dead Code Detection**: Code that exists but isn't referenced by documented flows may be vestigial.

---

## Audit Record

| Date | Auditor | Findings | Issues Created |
|------|---------|----------|----------------|
| - | - | STUB - Not yet implemented | - |

---

## Related

- [0843 - LLD-to-Code Alignment](0843-audit-lld-code-alignment.md)
- [0844 - File Inventory](0844-audit-file-inventory.md)
- [0206 - Bidirectional Sync Architecture](../adrs/0206-bidirectional-sync-architecture.md)
