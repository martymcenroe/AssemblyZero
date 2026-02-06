# Issue #19: Audit Reorganization Plan

**Issue:** [#19 - chore: Review and rearrange audit classes/tiers](https://github.com/martymcenroe/AssemblyZero/issues/19)
**Created:** 2026-02-05
**Status:** COMPLETED - 2026-02-05

---

## Executive Summary

The audit index (0800) has grown organically and requires cleanup. Investigation reveals:
- **35 actual files** exist (vs. 33 claimed in index)
- **Numbering collision** at 0837 (two different audits)
- **Phantom audits** referenced but don't exist (082x range)
- **Category boundaries** unclear and inconsistent
- **Ultimate tier** underspecified

This plan proposes a coherent reorganization with clear category definitions.

---

## Current State Analysis

### Actual File Inventory (35 files)

**Core Range (0801-0817): 17 files**
| Number | Name | Focus |
|--------|------|-------|
| 0801 | Security | OWASP, ASVS |
| 0802 | Privacy | GDPR, data handling |
| 0803 | Code Quality | CI/linting |
| 0804 | Accessibility | WCAG |
| 0805 | License Compliance | OSS licenses |
| 0806 | Bias & Fairness | AI fairness |
| 0807 | Explainability | XAI |
| 0808 | AI Safety | LLM, NIST AI RMF |
| 0809 | Agentic AI Governance | OWASP Agentic |
| 0810 | AI Management System | ISO 42001 |
| 0811 | AI Incident Post-Mortem | Failure analysis |
| 0812 | AI Supply Chain | AIBOM |
| 0813 | Claude Capabilities | Model features |
| 0814 | Horizon Scanning | Threat monitoring |
| 0815 | Permission Friction | Approval overhead |
| 0816 | Permission Permissiveness | Access control |
| 0817 | AssemblyZero Self-Audit | Framework health |

**Extended Range (0832-0840): 10 files** *(includes collision)*
| Number | Name | Focus |
|--------|------|-------|
| 0832 | Cost Optimization | Token efficiency |
| 0833 | Gitignore Encryption | git-crypt review |
| 0834 | Worktree Hygiene | Branch cleanup |
| 0835 | Structure Compliance | Directory conventions |
| 0836 | Gitignore Consistency | Ignore patterns |
| 0837 | README Compliance | Template adherence |
| **0837** | **Code Quality Procedure** | **COLLISION** |
| 0838 | Broken References | Link validation |
| 0839 | Wiki Alignment | Wiki/code sync |
| 0840 | Cross-Project Harvest | Pattern extraction |

**Documentation Health (0841-0847): 7 files** *(all stubs)*
| Number | Name | Status |
|--------|------|--------|
| 0841 | Open Issues Currency | Stub |
| 0842 | Reports Completeness | Stub |
| 0843 | LLD-to-Code Alignment | Stub |
| 0844 | File Inventory Drift | Stub |
| 0845 | Terminology Consistency | Stub |
| 0846 | Architecture Drift | Stub |
| 0847 | Implementation Completeness | Stub |

**Meta (0899): 1 file**
| Number | Name | Purpose |
|--------|------|---------|
| 0899 | Meta-Audit | Audit governance |

### Phantom Audits (Referenced in Index, Don't Exist)

The following appear in the index's Model Recommendations (§11), By Topic (§10.2), and other sections but have no corresponding files:

| Number | Claimed Name | Evidence |
|--------|--------------|----------|
| 0818 | AI Management System | In §11.2, §7 |
| 0819 | AI Supply Chain | In §11.2, §6.1, §7 |
| 0820 | Explainability | In §11.2 - **was unleashed audit, moved to separate repo** |
| 0821 | Agentic AI Governance | In §4.2, §6.1, §7, §9.2, §11 |
| 0822 | Bias & Fairness | In §6.1, §7, §11 |
| 0823 | AI Incident Post-Mortem | In §7, §10.2, §11 |
| 0824 | Permission Friction | In §5.1, §10.2, §11 |
| 0825 | AI Safety | In §11 - **History says "split from 0809"** |
| 0826 | Cross-Browser Testing | In History |
| 0827 | Infrastructure Integration | In §7, §11 |
| 0828 | Build Artifact Freshness | In §11 |
| 0829 | Lambda Failure Remediation | In §10.2, §11 |
| 0830 | Architecture Freshness | In History |
| 0831 | Web Assets | In §10.2, §11 |
| 0898 | Horizon Scanning | In §6.2, §7, §9.1 |

**Root Cause:** The index was updated to *plan* these audits but the files were never created. Some (like 0820) were created then moved to other repos without cleanup.

### Category Problems

**Problem 1: Core Range (0801-0817) Mixes Unrelated Concerns**
- Security/Privacy (0801-0802)
- Code Quality/Accessibility (0803-0804)
- License (0805)
- AI Governance (0806-0812)
- Claude-specific (0813-0817)

**Problem 2: Extended Range is a Catch-All**
- Cost (0832)
- Security (0833)
- Git hygiene (0834, 0836)
- Documentation (0835, 0837, 0838, 0839)
- Cross-project (0840)

**Problem 3: Stub Files vs. Implemented Files Not Distinguished**
- Documentation Health (0841-0847) are all stubs but mixed with real audits

---

## Proposed Reorganization

### Option A: Thematic Categories (Recommended)

Reorganize by *what the audit verifies*, not by number range:

| Category | Audits | Principle |
|----------|--------|-----------|
| **Security & Privacy** | 0801, 0802, 0805, 0833 | External threats, compliance, legal |
| **Code Quality** | 0803, 0804, 0847 | Code correctness, standards |
| **AI Governance** | 0806-0812 | AI-specific risks and compliance |
| **AssemblyZero Operations** | 0813-0817, 0832, 0834 | This framework's health |
| **Documentation Health** | 0835-0846 (minus stubs) | Docs/code alignment |
| **Meta** | 0899 | Audit system governance |

### Option B: Frequency-Based Tiers

Reorganize by *how often they run*:

| Tier | Frequency | Audits |
|------|-----------|--------|
| **Continuous** | Per-PR, on-change | 0803 |
| **Weekly** | Hygiene checks | 0816, 0834, 0838, 0841-0844 |
| **Monthly** | Governance checks | 0809, 0815, 0817, 0832, 0835, 0839-0840, 0846 |
| **Quarterly** | Deep audits | 0801, 0802, 0805-0808, 0810, 0812, 0814, 0899 |
| **On-Demand** | Incident/event | 0811, 0845 |
| **Ultimate** | Expensive/rare | 0833 (+ candidates) |

### Option C: Minimal Cleanup (Conservative)

Keep current categories, just fix problems:
1. Resolve 0837 collision
2. Remove phantom audit references
3. Update counts
4. Define --ultimate criteria

---

## Specific Actions Required

### Phase 1: Immediate Fixes (No Category Change)

1. **Resolve 0837 Collision**
   - Rename `0837-audit-code-quality-procedure.md` → `0848-audit-code-quality-procedure.md`
   - Update any references

2. **Remove Phantom Audit References**
   - Delete references to 0818-0831, 0898 from index
   - Clean up Model Recommendations table
   - Clean up By Topic table
   - Clean up Frequency Matrix
   - Clean up Standards Coverage Map
   - Clean up Dependencies section

3. **Update Counts**
   - Index claims 33 audits, actually 35 (34 unique + 1 collision)
   - After collision fix: 35 unique audits

4. **Mark Stubs Clearly**
   - Add `**[STUB]**` prefix to 0841-0847 in Quick Links
   - Or move to separate "Planned Audits" section

### Phase 2: Category Reorganization

**If Option A (Thematic):**
- Rewrite §4 (Audit Categories) with new groupings
- Update §3 (Overview) counts per category
- Update §10 (Quick Links) organization

**If Option B (Frequency):**
- Rewrite §4 around frequency tiers
- Consolidate §5 (Frequency Matrix) into §4
- Simplify §3 to show tier counts

**If Option C (Minimal):**
- Phase 1 only, no category changes

### Phase 3: Ultimate Tier Definition

Current: Only 0833 (Gitignore Encryption) is ultimate tier.

**Proposed Ultimate Tier Criteria:**
- Cost > $1 per run (Opus-heavy, multiple files)
- Requires human judgment/approval
- Run frequency < monthly
- External tool dependencies

**Candidate Ultimate Audits:**
| Audit | Rationale |
|-------|-----------|
| 0833 | Already ultimate - git-crypt review |
| 0801 | Security - requires careful Opus analysis |
| 0802 | Privacy - GDPR complexity |
| 0810 | ISO 42001 - comprehensive framework |

---

## Questions for User

Before finalizing this plan, I need decisions on:

### Q1: Category Approach
Which option?
- **A) Thematic** - Group by what's being verified
- **B) Frequency** - Group by how often it runs
- **C) Minimal** - Just fix collisions and phantoms

### Q2: Phantom Audit Disposition
For the 15 phantom audits referenced but never created:
- **Delete** - Remove all references, they were aspirational
- **Stub** - Create stub files for future implementation
- **Audit** - Research each to determine if it was ever useful

### Q3: Ultimate Tier Expansion
Beyond 0833, should other expensive audits become ultimate tier?
- **Yes** - Add 0801, 0802, 0810 to ultimate
- **No** - Keep only 0833, others run on schedule
- **Selective** - You tell me which ones

### Q4: Stub Audits (0841-0847)
The Documentation Health audits are all stubs. Should we:
- **Keep** - Leave as stubs for future implementation
- **Delete** - Remove until someone implements them
- **Consolidate** - Merge into fewer, actually-implemented audits

### Q5: Implementation Approach
Given budget constraints:
- **Document only** - Update the index, commit changes, no actual audit runs
- **Validate minimally** - Run a few cheap audits (Haiku) to verify fixes
- **Full validation** - Run /audit suite after changes (expensive)

---

## Estimated Work

| Phase | Effort | Cost |
|-------|--------|------|
| Phase 1 (Fixes) | 30 min | ~$0.50 (editing only) |
| Phase 2 (Reorg) | 1-2 hours | ~$2-5 (depending on option) |
| Phase 3 (Ultimate) | 15 min | ~$0.25 |
| Validation | Variable | $0 (doc only) to $50+ (full audit) |

---

## Appendix: File Count Reconciliation

```
Index claims: 33 audits
Actual files: 35 files

Breakdown:
- Core (0801-0817): 17 files
- Extended (0832-0840): 10 files (includes 0837 collision, so 9 unique numbers)
- Documentation Health (0841-0847): 7 files (all stubs)
- Meta (0899): 1 file

Total unique: 34 (after resolving collision)
```

---

## References

- [Issue #19](https://github.com/martymcenroe/AssemblyZero/issues/19) - This task
- [Issue #18](https://github.com/martymcenroe/AssemblyZero/issues/18) - Ultimate tier origin (git-crypt ideas)
- [0800-audit-index.md](../audits/0800-audit-index.md) - Current index
- [Commit 708a5b7](https://github.com/martymcenroe/AssemblyZero/commit/708a5b7) - Unleashed migration (removed 0820)
