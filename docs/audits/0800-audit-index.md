# 0800 - Audit Index

## 1. Purpose

Master index of all AgentOS audits. Provides navigation, categorization, and quick reference for the audit suite.

---

## 2. Audit Philosophy

> "Don't trust metadata—verify reality."

Audits exist because:
1. **Docs drift from code** - Architecture changes, docs don't update
2. **Issues drift from reality** - Issues marked open are actually complete (or vice versa)
3. **Process steps get skipped** - Reports not created, inventory not updated
4. **Terminology evolves** - Old names persist in forgotten corners
5. **The system itself decays** - Cross-references break, templates diverge

### 2.1 Evidence over Inference (CRITICAL)

**Do not assume compliance based on file names or documentation claims. Grep the code/config for the specific setting.**

| Bad Practice | Good Practice |
|--------------|---------------|
| "0810 says in-memory only" | `grep put_item src/lambda_function.py` |
| "CLAUDE.md says eval is forbidden" | `grep eval .claude/settings.local.json` |
| "Package says MIT license" | Compare LICENSE, package.json, pyproject.toml |

**The code is the truth. The docs are a claim about the truth.**

### 2.2 N/A Verification Policy (MANDATORY)

**"N/A" is not a free pass.** Items marked Not Applicable require verification each audit:

| Wrong | Right |
|-------|-------|
| "Data Poisoning: N/A (no fine-tuning)" | "Data Poisoning: ⬜ VERIFY no fine-tuning → ✅ VERIFIED: No training jobs, no custom models" |
| Check box without evidence | Grep/inspect to prove claim still true |

**Every N/A claim requires:**
1. **Architectural verification** - Confirm the reason still holds (check code/config)
2. **Documentation** - Note in audit record: "Verified [item] N/A: [evidence]"
3. **Re-evaluation** - If architecture changed, audit the item fully

**Rationale:** Architecture evolves. What was N/A last quarter (e.g., "no fine-tuning") may not be N/A now. Blind N/A checkboxes become security debt.

### 2.3 Fix-First Mandate (NON-NEGOTIABLE)

> "An audit that finds the same error twice is a broken audit."

**Audits MUST fix errors, not just document them.**

| Wrong | Right |
|-------|-------|
| "Finding: stale artifact. Noted as exception." | "Finding: stale artifact. Auto-fixed via `build_release.py`." |
| "Finding: missing permission. Added to issues." | "Finding: missing permission. Auto-added to `settings.local.json`." |
| "npm audit found 3 vulns. Documented." | "npm audit found 3 vulns. Ran `npm audit fix`. Now 0." |

**Fix-First Hierarchy:**

1. **Auto-fix immediately** - If the fix is mechanical (add entry, update file, run command), do it
2. **Auto-fix with rebuild** - If fix requires a build/test cycle, run it (e.g., `build_release.py`)
3. **Create GitHub issue** - Only if fix requires human judgment, design discussion, or code changes
4. **Exception** - Only if fix is impossible (external dependency, third-party bug)

**The goal:** The next audit run should find ZERO of the same errors.

**Audit Record Requirement:**

```markdown
### Auto-Fixed
- [x] Rebuilt stale Chrome artifact
- [x] Added `Bash(new-tool:*)` to allowlist

### Requires Human Decision
- [ ] Version bump: 1.0 → 1.1? (needs product decision)

### Exceptions (Truly Unfixable)
- [ ] Claude Code permission bug #17637 (upstream)
```

---

## 3. Audit Suite Overview

### 3.1 At a Glance

| Category | Count | Auto-Fix | Focus |
|----------|-------|----------|-------|
| Core Audits (0801-0817) | 17 | 3 | Security, privacy, AI governance, permissions |
| Extended Audits (0832-0840) | 9 | 1 | Cost, structure, hygiene, references |
| Documentation Health (0841-0847) | 7 | 4 | Docs-code alignment, completeness |
| Meta (0899) | 1 | 0 | Audit system governance |
| **Total** | **33** | **8** | |

*Note: Documentation Health audits (0841-0846) are stub files pending implementation.*

### 3.2 Quick Reference

**Existing Audits (with files):**

| Audit | One-Line Description | Auto-Fix |
|-------|----------------------|----------|
| 0801 | Security (OWASP, ASVS) | No |
| 0802 | Privacy (GDPR-aware, data handling) | No |
| 0803 | Code Quality | CI |
| 0804 | Accessibility (WCAG) | No |
| 0805 | License Compliance | No |
| 0806 | Bias & Fairness | No |
| 0807 | Explainability (XAI) | No |
| 0808 | AI Safety (LLM, NIST AI RMF) | No |
| 0809 | Agentic AI Governance (OWASP Agentic) | No |
| 0810 | AI Management System (ISO 42001) | No |
| 0811 | AI Incident Post-Mortem | No |
| 0812 | AI Supply Chain (OWASP LLM03, AIBOM) | No |
| 0813 | Claude Code Capabilities | No |
| 0814 | Horizon Scanning Protocol | No |
| 0815 | Permission Friction | **Yes** |
| 0816 | Permission Permissiveness | **Yes** |
| 0817 | AgentOS Self-Audit | **Yes** |
| 0832 | Cost Optimization | Partial |
| 0833 | Gitignore Encryption Review | No (Ultimate) |
| 0834 | Worktree Hygiene | No |
| 0835 | Structure Compliance | No |
| 0836 | Gitignore Consistency | No |
| 0837 | README Compliance | No |
| 0838 | Broken References | No |
| 0839 | Wiki Alignment | No |
| 0840 | Cross-Project Harvest | No |
| 0899 | Meta-Audit | No |

**Documentation Health Audits (new stubs):**

| Audit | One-Line Description | Auto-Fix |
|-------|----------------------|----------|
| 0841 | Open Issues Currency (stale/complete issues) | No |
| 0842 | Reports Completeness (closed issues have reports) | **Yes** |
| 0843 | LLD-to-Code Alignment | No |
| 0844 | File Inventory Drift | **Yes** |
| 0845 | Terminology Consistency | **Yes** |
| 0846 | Architecture Drift (code vs docs) | **Yes** |
| 0847 | Implementation Completeness (stubs, fake tests) | No |

---

## 4. Audit Categories

### 4.0 Documentation Health Audits (0841-0847)

Audits ensuring documentation stays aligned with code and complete.

| Number | Name | Frequency | Auto-Fix |
|--------|------|-----------|----------|
| 0841 | Open Issues Currency | Weekly | No |
| 0842 | Reports Completeness | Weekly | **Yes** |
| 0843 | LLD-to-Code Alignment | On change | No |
| 0844 | File Inventory Drift | Weekly | **Yes** |
| 0845 | Terminology Consistency | On rename | **Yes** |
| 0846 | Architecture Drift | Monthly | **Yes** |
| 0847 | Implementation Completeness | On new repo / Monthly | No |
| 0817 | AgentOS Self-Audit | Monthly | **Yes** |

### 4.1 Core Development Audits

Audits for code quality, security, and development practices.

| Number | Name | Frequency | Auto-Fix |
|--------|------|-----------|----------|
| 0801 | Security (OWASP) | Quarterly | No |
| 0802 | Privacy (GDPR) | Quarterly | No |
| 0803 | Code Quality | Per PR | CI |
| 0804 | Accessibility (WCAG) | Monthly + on change | No |
| 0805 | License Compliance | Quarterly | No |
| 0815 | Permission Friction | On friction | **Yes** |
| 0816 | Permission Permissiveness | Weekly / On friction | **Yes** |
| 0832 | Cost Optimization | Monthly | Partial |
| 0834 | Worktree Hygiene | Weekly + on cleanup | No |
| 0835 | Structure Compliance | Monthly | No |
| 0836 | Gitignore Consistency | On change | No |
| 0837 | README Compliance | On change | No |
| 0838 | Broken References | Weekly | No |
| 0839 | Wiki Alignment | Monthly + on change | No |
| 0840 | Cross-Project Harvest | Monthly | No |

### 4.1.1 Ultimate Tier Audits

Expensive or rarely-needed audits that only run on explicit request.

| Number | Name | Trigger | Auto-Fix |
|--------|------|---------|----------|
| 0833 | Gitignore Encryption Review | `--ultimate` or direct | No |

**Trigger conditions:**
- `/audit 0833` - Direct invocation
- `/audit --ultimate` - Runs all standard + ultimate audits

**NOT triggered by:**
- `/audit` (standard)
- `/audit --full` (all standard, no ultimate)

### 4.2 AI Governance Audits

Audits specific to AI system governance, compliance, and responsible AI.

| Number | Name | Frequency | Framework |
|--------|------|-----------|-----------|
| 0806 | Bias & Fairness | Quarterly | ISO 24027, NIST |
| 0807 | Explainability | Quarterly | XAI, EU AI Act Art. 13 |
| 0808 | AI Safety | Quarterly | OWASP LLM 2025, NIST AI RMF |
| 0809 | Agentic AI Governance | Monthly | OWASP Agentic 2026 |
| 0810 | AI Management System | Quarterly | ISO/IEC 42001:2023 |
| 0811 | AI Incident Post-Mortem | On incident | NIST AI RMF |
| 0812 | AI Supply Chain | Quarterly | OWASP LLM03:2025, SPDX 3.0 |
| 0814 | Horizon Scanning | Quarterly | Threat monitoring |

### 4.3 Meta Audits

Audits that govern the audit system itself.

| Number | Name | Frequency | Purpose |
|--------|------|-----------|---------|
| 0899 | Meta-Audit | Quarterly | Validate audit execution |

---

## 5. Frequency Matrix

### 5.1 By Frequency

| Frequency | Audits |
|-----------|--------|
| **Per PR** | 0803 |
| **Monthly + on change** | 0804, 0817, 0839 |
| **Weekly** | 0816, 0834, 0838, 0841, 0842, 0844 |
| **Monthly** | 0809, 0815, 0832, 0835, 0840, 0846 |
| **Quarterly** | 0801, 0802, 0805, 0806, 0807, 0808, 0810, 0812, 0814, 0899 |
| **On incident** | 0811 |
| **On Event** | 0808 (mining), 0824 (friction analysis), 0823 (incident), 0829 (lambda failures) |

### 5.2 Calendar View

| Month | Week 1 | Week 2 | Week 3 | Week 4 |
|-------|--------|--------|--------|--------|
| **Jan** | 0816, 0815 | 0816 | 0816, 0809, 0810 | 0816, 0898, 0899 |
| **Feb** | 0816, 0815, 0821 | 0816 | 0816 | 0816 |
| **Mar** | 0816, 0815 | 0816, 0821 | 0816 | 0816, 0818, 0819, 0820, 0822 |
| **Apr** | 0816, 0815 | 0816 | 0816, 0821, 0809, 0810 | 0816, 0898, 0899 |
| ... | | | | |

---

## 6. Standards Coverage Map

### 6.1 By Standard

| Standard | Primary Audit | Supporting Audits |
|----------|---------------|-------------------|
| **OWASP LLM Top 10 (2025)** | 0809 | 0819, 0821 |
| **OWASP Agentic Top 10 (2026)** | 0821 | 0808, 0815 |
| **ISO/IEC 42001:2023** | 0818 | 0809, 0810, 0822 |
| **EU AI Act** | 0820 | 0809, 0810, 0818 |
| **NIST AI RMF** | 0818 | 0823 |
| **ASVS 4.0.3** | 0809 §4 | |
| **CWE Top 25** | 0809 §2 | |
| **SPDX 3.0 AI Profile** | 0819 | |

### 6.2 Coverage Gaps

See **0898 Horizon Scanning Protocol** for ongoing gap discovery.

---

## 7. Audit Dependencies

### 7.1 Dependency Graph

```
0899 Meta-Audit
  └── validates all 08xx audits

0898 Horizon Scanning
  └── discovers gaps for all 08xx

0821 Agentic AI Governance
  ├── depends on: 0808, 0815
  └── informs: 0823

0819 AI Supply Chain
  └── depends on: 0816

0809 Security
  └── informs: 0821, 0823

0823 AI Incident Post-Mortem
  └── triggers: 0809, 0821, 0822 (as needed)
```

### 7.2 Run Order (when running multiple)

1. Code quality audit first (0813)
2. Dependency audit (0816)
3. Security/Privacy (0809, 0810)
4. AI Governance (0818-0822)
5. Agent audits (0808, 0815, 0821)
6. Meta audits last (0898, 0899)

---

## 8. Record-Keeping Requirements (MANDATORY)

### 8.1 Auditor Identity

**Every audit record entry MUST include auditor identity.** No anonymous audits.

| Field | Requirement | Example |
|-------|-------------|---------|
| **Auditor** | Model name + version | "Claude Opus 4.5", "Gemini 3.0 Pro" |
| **Date** | ISO 8601 format | 2026-01-10 |
| **Findings** | Explicit PASS/FAIL with issue refs | "PASS", "FAIL: See #234" |

**Accountability Rule:** The auditor recorded in the audit record MUST match the git commit author. If Claude runs the audit, the commit must be by Claude. This creates traceability.

### 8.2 Audit Record Format

Standard format for all audits:

```markdown
| Date | Auditor | Findings Summary | Issues Created |
|------|---------|------------------|----------------|
| YYYY-MM-DD | [Model Name] | [PASS/FAIL summary] | #NNN, #NNN |
```

**Forbidden entries:**
- ❌ Empty auditor field
- ❌ "TBD" or "TODO" as auditor
- ❌ Generic "Agent" without model name
- ❌ Findings without PASS/FAIL classification

### 8.3 Audit Failure → GitHub Issue (MANDATORY)

**Every audit failure MUST create a GitHub issue.** No internal-only findings.

| Finding | Action | Issue Label |
|---------|--------|-------------|
| **FAIL** | Create issue immediately | `audit`, `high-priority` |
| **WARN** | Create issue | `audit`, `low-priority` |
| **PASS** | No issue needed | - |

**Audit Record Entry Format for Failures:**

```markdown
| Date | Auditor | Findings Summary | Issues Created |
|------|---------|------------------|----------------|
| 2026-01-10 | Claude Opus 4.5 | FAIL: XSS in overlay | #NNN |
```

**Forbidden:**
- ❌ `FAIL` without issue reference
- ❌ `FAIL: See internal notes`
- ❌ Findings buried in prose without issue

**Rationale:** GitHub issues are visible, trackable, and cannot be quietly dismissed. Internal audit records can be edited or forgotten.

---

## 9. Audit Ownership

### 9.1 By Role

| Role | Audits Owned |
|------|--------------|
| **Developer** | All (solo project) |
| **CI/CD** | 0813 |
| **Dependabot** | 0816 (triggers) |

### 9.2 Accountability

| Audit | Accountable | Responsible | Consulted |
|-------|-------------|-------------|-----------|
| 0809 Security | Developer | Developer | - |
| 0821 Agentic | Developer | Claude Code | Developer |
| 0823 Incident | Developer | Developer | - |

---

## 10. Quick Links

### 10.1 By Number

**Core Audits (0801-0817)**
- [0801 - Security](0801-security-audit.md)
- [0802 - Privacy](0802-privacy-audit.md)
- [0803 - Code Quality](0803-code-quality-audit.md)
- [0804 - Accessibility](0804-accessibility-audit.md)
- [0805 - License Compliance](0805-license-compliance.md)
- [0806 - Bias & Fairness](0806-bias-fairness.md)
- [0807 - Explainability](0807-explainability.md)
- [0808 - AI Safety](0808-ai-safety-audit.md)
- [0809 - Agentic AI Governance](0809-agentic-ai-governance.md)
- [0810 - AI Management System](0810-ai-management-system.md)
- [0811 - AI Incident Post-Mortem](0811-ai-incident-post-mortem.md)
- [0812 - AI Supply Chain](0812-ai-supply-chain.md)
- [0813 - Claude Capabilities](0813-claude-capabilities.md)
- [0814 - Horizon Scanning](0814-horizon-scanning-protocol.md)
- [0815 - Permission Friction](0815-permission-friction.md) ✨
- [0816 - Permission Permissiveness](0816-permission-permissiveness.md) ✨
- [0817 - AgentOS Self-Audit](0817-agentos-audit.md) ✨

**Extended Audits (0832-0840)**
- [0832 - Cost Optimization](0832-audit-cost-optimization.md) ✨
- [0833 - Gitignore Encryption Review](0833-audit-gitignore-encryption.md) 🔒
- [0834 - Worktree Hygiene](0834-audit-worktree-hygiene.md)
- [0835 - Structure Compliance](0835-audit-structure-compliance.md)
- [0836 - Gitignore Consistency](0836-audit-gitignore-consistency.md)
- [0837 - README Compliance](0837-audit-readme-compliance.md)
- [0838 - Broken References](0838-audit-broken-references.md)
- [0839 - Wiki Alignment](0839-audit-wiki-alignment.md)
- [0840 - Cross-Project Harvest](0840-cross-project-harvest.md)

**Documentation Health (0841-0846) - STUBS**
- [0841 - Open Issues Currency](0841-audit-open-issues.md) 📝
- [0842 - Reports Completeness](0842-audit-reports-completeness.md) ✨📝
- [0843 - LLD-to-Code Alignment](0843-audit-lld-code-alignment.md) 📝
- [0844 - File Inventory Drift](0844-audit-file-inventory.md) ✨📝
- [0845 - Terminology Consistency](0845-audit-terminology.md) ✨📝
- [0846 - Architecture Drift](0846-audit-architecture-drift.md) ✨📝
- [0847 - Implementation Completeness](0847-audit-implementation-completeness.md) 🔨

**Meta (0899)**
- [0899 - Meta-Audit](0899-meta-audit.md)

✨ = Auto-fix capability
🔒 = Ultimate tier (only runs with `--ultimate` flag)
📝 = Stub file (implementation pending)
🔨 = Anti-laziness audit (forces thorough work)

### 10.2 By Topic

| Topic | Relevant Audits |
|-------|-----------------|
| Agent behavior | 0808, 0824, 0815, 0821 |
| AI safety | 0809, 0818, 0821, 0822 |
| Accessibility | 0811, 0831 |
| Code quality | 0813 |
| Compliance | 0818, 0820, 0898 |
| Dependencies | 0816, 0819 |
| Incidents | 0823 |
| Infrastructure | 0827, 0829 |
| License | 0814 |
| Performance | 0812 |
| Privacy | 0810 |
| Security | 0809, 0819 |
| Wiki/Docs | 0817 |

---

## 11. Model Recommendations

Cost optimization: use the cheapest model that can reliably execute each audit.

### 11.1 By Model Tier

| Model | Cost | Audits | Rationale |
|-------|------|--------|-----------|
| **Haiku** | $ | 0808, 0812, 0814, 0816, 0817, 0819, 0827, 0834, 0899 | Simple checklist, metric aggregation, file parsing |
| **Sonnet** | $$ | 0811, 0815, 0820, 0822, 0824, 0831, 0898 | Web research, framework analysis, moderate reasoning |
| **Opus** | $$$ | 0809, 0810, 0818, 0821, 0823, 0825, 0829 | Complex reasoning, security analysis, incident review, remediation |

### 11.2 Detailed Rationale

| Audit | Recommended | Why |
|-------|-------------|-----|
| 0808 Permission Problem Mining | Haiku | Transcript search, checkpoint tracking, pattern matching |
| 0809 Security | **Opus** | OWASP Top 10 requires nuanced security reasoning |
| 0810 Privacy | **Opus** | GDPR/privacy analysis requires contextual judgment |
| 0811 Accessibility | Sonnet | WCAG checklist with moderate reasoning |
| 0812 Performance | Haiku | Metric collection and threshold comparison |
| 0814 License Compliance | Haiku | SPDX string matching |
| 0815 Claude Code Capabilities | Sonnet | Web research for new features |
| 0816 Dependabot PRs | Haiku | GH API parsing, simple decisions |
| 0817 Wiki Alignment | Haiku | Text diff comparison |
| 0818 AI Management System | **Opus** | ISO 42001 requires comprehensive analysis |
| 0819 AI Supply Chain | Haiku | Dependency scanning, manifest parsing |
| 0820 Explainability | Sonnet | XAI evaluation with framework guidance |
| 0821 Agentic AI Governance | **Opus** | Complex agent behavior analysis |
| 0822 Bias & Fairness | Sonnet | Structured bias evaluation |
| 0823 AI Incident Post-Mortem | **Opus** | Root cause analysis requires deep reasoning |
| 0824 Permission Friction | Sonnet | Session log analysis, pattern recognition |
| 0825 AI Safety | **Opus** | LLM safety requires nuanced reasoning |
| 0827 Infrastructure Integration | Haiku | Config verification, AWS CLI parsing |
| 0828 Build Artifact Freshness | Haiku | Timestamp comparison, manifest parsing |
| 0829 Lambda Failure Remediation | **Opus** | Root cause analysis, code fixes, issue drafting |
| 0831 Web Assets | Sonnet | Visual design evaluation, responsive testing, accessibility |
| 0834 Worktree Hygiene | Haiku | Git command parsing, file status checks |
| 0898 Horizon Scanning | Sonnet | Framework research, moderate analysis |
| 0899 Meta-Audit | Haiku | Execution tracking, checklist validation |

### 11.3 Estimated Savings

By using appropriate models instead of Opus for all audits:
- **Haiku audits (9):** ~66% savings per audit
- **Sonnet audits (6):** ~25% savings per audit
- **Opus audits (6):** No change (required for complexity)

---

## 12. Getting Started

### 12.1 For New Contributors

1. Read this index to understand the audit landscape
2. Review 0815 for Claude Code workflow rules
3. Code quality audit (0813) runs automatically on PRs
4. Security (0809) and Privacy (0810) are the most comprehensive

### 12.2 For Audit Execution

1. Check 0899 for audit schedule and status
2. Run audit per its documented procedure
3. Record findings in audit's Audit Record section
4. Create GitHub issues for failures
5. Update 0899 with execution date

### 12.3 For Gap Discovery

1. Review 0898 Horizon Scanning Protocol
2. Check Framework Registry for updates
3. Triage new frameworks per 0898 §4
4. Propose new audits if gaps found

---

## 13. History

| Date | Change |
|------|--------|
| 2026-01-21 | **Major index reconciliation.** Fixed numbering collision: index described conceptual audits (0801-0807 Documentation Health) that conflicted with actual files (0801-security, 0802-privacy, etc.). Solution: Renumbered Documentation Health audits to 0841-0846 (stubs created). Fixed duplicates: 0817→0839 (wiki alignment), 0832→0840 (cross-project harvest). Updated all Quick Links to point to actual files. Total audits: 33 (27 implemented + 6 stubs). |
| 2026-01-16 | Created 0833 (Gitignore Encryption Review) for encrypt vs ignore recommendations. Added Ultimate tier for expensive/rare audits (--ultimate flag). Part of Issue #18 (git-crypt ideas folder). Total audits: 34. |
| 2026-01-12 | Added auto-fix capability to 9 audits (0802, 0804, 0805, 0806, 0807, 0808, 0824, 0828, 0830). Added Documentation Health category (0801-0807) to index. Total audits: 32. |
| 2026-01-11 | Renumbered 0827-audit-web-assets.md to 0831 (resolved duplicate with 0827-infrastructure-integration). Total audits: 25. |
| 2026-01-11 | Created 0830 (Architecture Freshness) for documentation completeness and currency. Part of Architectural Depth Model (#308). Total audits: 24. |
| 2026-01-10 | Created 0829 (Lambda Failure Remediation) for proactive CloudWatch error detection and fix-or-draft workflow. Total audits: 23. |
| 2026-01-10 | Created 0827 (Infrastructure Integration) for Lambda, DynamoDB, API Gateway verification. Total audits: 22. |
| 2026-01-09 | Created 0826 (Cross-Browser Testing) after Firefox incident. Enforces file parity and mock fidelity. Total audits: 21. |
| 2026-01-08 | Split 0809 per ADR 0213. Created 0825 (AI Safety) with LLM, Agentic, NIST AI RMF sections. 0809 now focused on app security. Total audits: 20. |
| 2026-01-08 | Index consistency audit. Fixed broken links (0811-0814, 0815, 0817). Corrected audit names/descriptions to match actual files. Added 0817 Wiki Alignment. Total audits: 19. |
| 2026-01-06 | Major update. Added AI Governance audits (0818-0823), split meta-audit into 0898 (horizon scanning) and 0899 (validation). Merged 0800-common-audits.md into this file (preserved Audit Philosophy section). Total audits: 17. |
| 2026-01-14 | Created 0832 (Cost Optimization) for skill/command token efficiency analysis. Total audits: 33. |
