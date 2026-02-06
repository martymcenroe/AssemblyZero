# Architecture Audit ("Drift Detector")

**Role:** Lead System Architect and Compliance Officer.
**Objective:** Perform "Drift Detection" audit. Compare the *theoretical* architecture (Documentation) against the *actual* implementation (Source Code).

## Phase 1: Context Loading (The Map)

1. **Read Core Architecture:**
   - `docs/0001-architecture.md` (Landing Page) and sub-documents
   - `docs/coding-standards.md` (The Rules)
   - `docs/adr-index.md` (The Decisions)

2. **Read Feature Definitions (LLDs):**
   - Scan all `docs/lld/**/*.md` files. These are the promises made.

## Phase 2: Code Inspection (The Territory)

Read critical paths to determine "As-Built" reality:
1. **Entry Points:** Main handlers, entry scripts
2. **Core Logic:** Business logic modules
3. **External Interfaces:** API definitions, manifests
4. **Infrastructure:** Deployment scripts, CI/CD

## Phase 3: The Gap Analysis

Compare **Code vs. Docs** by tier:

### Tier 1: Security & Correctness (Blocking)
- **Auth/AuthZ:** Are authentication gates enforced as documented?
- **Input Validation:** Does code validate inputs as promised?
- **Secrets:** Are API keys hardcoded that violate standards?

### Tier 2: Testing & Compliance (High Priority)
- **Test Coverage:** Do tests match feature promises?
- **Permissions:** Do actual permissions exceed documented scope?
- **Data Pipeline:** Does data flow match architecture docs?

### Tier 3: Maintainability (Suggestions)
- **Structure:** Has code evolved into patterns that contradict design?
- **Comments:** Do TODOs correspond to tracked issues?

---

## Phase 4: Auto-Fix

**This audit auto-fixes documentation drift rather than just reporting it.**

### Auto-Fixable Drift

| Drift Type | Detection | Auto-Fix |
|------------|-----------|----------|
| **Version numbers** | Compare actual vs documented | Update docs |
| **File paths** | Check if referenced files exist | Update paths |
| **Permission lists** | Compare actual vs documented | Update docs |

### Auto-Fix Procedure

```markdown
For each detected drift:
1. Verify the CODE is the source of truth (not a bug)
2. Update the DOCS to match the code
3. Log the change to audit output

For security/correctness drift (Tier 1):
1. Do NOT auto-fix - requires investigation
2. Flag as BLOCKING finding
3. Create GitHub issue for human review
```

### Cannot Auto-Fix

- Security vulnerabilities (needs investigation)
- Missing tests (needs implementation)
- Architectural regressions (needs design review)

---

## Output Format

```markdown
# As-Built Audit Report: {YYYY-MM-DD}

## Executive Summary
{Pass/Fail assessment of architectural drift}

## 🚨 Critical Drift (Tier 1)
* **[Security/Privacy]** {Description}: Doc says "X", but Code does "Y".
    * *Fix:* {Action required}

## ⚠️ Compliance & Testing Gaps (Tier 2)
* **[Permission Creep]** Actual permissions exceed documented scope.
* **[Coverage Gap]** Feature implemented but no corresponding test.

## 📉 Technical Debt (Tier 3)
* **[Documentation Stale]** LLD refers to renamed function.
* **[Code Rot]** Module exists but not in inventory.

## Recommended Actions
1. {Step 1}
2. {Step 2}
```

---

*Template from: AssemblyZero/.claude/templates/docs/architecture-audit.md*
