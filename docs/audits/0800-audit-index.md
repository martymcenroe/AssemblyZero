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
| Documentation Health | 7 | 6 | Docs-code alignment, inventory, terminology |
| Core Development | 18 | 4 | Code quality, security, privacy, accessibility, cost |
| AI Governance | 7 | 0 | AI-specific controls and compliance |
| Meta | 2 | 0 | Audit system governance |
| Ultimate | 1 | 0 | Expensive/rare audits (--ultimate only) |
| **Total** | **34** | **10** | |

### 3.2 Quick Reference

| Audit | One-Line Description | Auto-Fix |
|-------|----------------------|----------|
| 0801 | Open issues currency (stale/complete issues) | No |
| 0802 | Reports completeness (closed issues have reports) | **Yes** |
| 0803 | LLD-to-code alignment verification | No |
| 0804 | File inventory drift detection | **Yes** |
| 0805 | Terminology consistency (deprecated terms) | **Yes** |
| 0806 | Architecture drift (code vs docs) | **Yes** |
| 0807 | AgentOS health check (system self-audit) | **Yes** |
| 0808 | Permission problem mining (zugzwang violations, checkpoint tracking) | **Yes** |
| 0824 | Permission friction analysis (find missing allows) | **Yes** |
| 0809 | Application Security (OWASP, ASVS, extension) | No |
| 0825 | AI Safety (LLM, Agentic, NIST AI RMF) | No |
| 0810 | Privacy (GDPR-aware, data handling) | No |
| 0811 | Accessibility | No |
| 0812 | Performance | No |
| 0813 | Code Quality | CI |
| 0814 | License Compliance | No |
| 0817 | Wiki Alignment | No |
| 0815 | Claude Code workflow compliance | No |
| 0816 | Dependabot PR management | Semi |
| 0818 | AI Management System (ISO 42001) | No |
| 0819 | AI Supply Chain (OWASP LLM03, AIBOM) | No |
| 0820 | Explainability (XAI) | No |
| 0821 | Agentic AI Governance (OWASP Agentic) | No |
| 0822 | Bias & Fairness | No |
| 0823 | AI Incident Post-Mortem | No |
| 0826 | Cross-Browser Testing (Firefox/Chrome parity) | CI |
| 0827 | Infrastructure Integration (Lambda, DynamoDB, API Gateway) | No |
| 0828 | Build Artifact Freshness | **Yes** |
| 0829 | Lambda Failure Remediation (proactive fix or draft issue) | No |
| 0830 | Architecture Freshness (documentation completeness and currency) | **Yes** |
| 0831 | Web Assets (icons, buttons, responsive design, accessibility) | No |
| 0832 | Cost Optimization (model hints, context loading, spawn efficiency) | Partial |
| 0833 | Gitignore Encryption Review (encrypt vs ignore) | No (Ultimate) |
| 0898 | Horizon Scanning Protocol | No |
| 0899 | Meta-Audit (validation & execution) | No |

---

## 4. Audit Categories

### 4.0 Documentation Health Audits

Audits ensuring documentation stays aligned with code and complete.

| Number | Name | Frequency | Auto-Fix |
|--------|------|-----------|----------|
| 0801 | Open Issues Currency | Weekly | No |
| 0802 | Reports Completeness | Weekly | **Yes** |
| 0803 | LLD-to-Code Alignment | On change | No |
| 0804 | File Inventory Drift | Weekly | **Yes** |
| 0805 | Terminology Consistency | On rename | **Yes** |
| 0806 | Architecture Drift | Monthly | **Yes** |
| 0807 | AgentOS Health Check | Monthly | **Yes** |

### 4.1 Core Development Audits

Audits for code quality, security, and development practices.

| Number | Name | Frequency | Auto-Fix |
|--------|------|-----------|----------|
| 0808 | Permission Problem Mining | Weekly / On friction | **Yes** |
| 0824 | Permission Friction | On friction | **Yes** |
| 0809 | Security | Quarterly | No |
| 0810 | Privacy | Quarterly | No |
| 0811 | Accessibility | Monthly + on change | No |
| 0812 | Performance | Quarterly | No |
| 0813 | Code Quality | Per PR | CI |
| 0814 | License Compliance | Quarterly | No |
| 0817 | Wiki Alignment | Monthly + on change | No |
| 0815 | Claude Code Workflow | Monthly | No |
| 0816 | Dependabot PRs | Weekly | Semi |
| 0826 | Cross-Browser Testing | On extension changes | CI |
| 0827 | Infrastructure Integration | Quarterly | No |
| 0828 | Build Artifact Freshness | On deploy | **Yes** |
| 0829 | Lambda Failure Remediation | On-demand / cleanup --full | No |
| 0830 | Architecture Freshness | Monthly + on change | **Yes** |
| 0831 | Web Assets | On landing page change | No |
| 0832 | Cost Optimization | Monthly | Partial |

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
| 0818 | AI Management System | Quarterly | ISO/IEC 42001:2023 |
| 0819 | AI Supply Chain | Quarterly | OWASP LLM03:2025, SPDX 3.0 |
| 0820 | Explainability | Quarterly | XAI, EU AI Act Art. 13 |
| 0821 | Agentic AI Governance | Monthly | OWASP Agentic 2026 |
| 0822 | Bias & Fairness | Quarterly | ISO 24027, NIST |
| 0823 | AI Incident Post-Mortem | On incident | NIST AI RMF |
| 0825 | AI Safety | Quarterly | OWASP LLM 2025, NIST AI RMF |

### 4.3 Meta Audits

Audits that govern the audit system itself.

| Number | Name | Frequency | Purpose |
|--------|------|-----------|---------|
| 0898 | Horizon Scanning Protocol | Quarterly | Discover missing audits |
| 0899 | Meta-Audit | Quarterly | Validate audit execution |

---

## 5. Frequency Matrix

### 5.1 By Frequency

| Frequency | Audits |
|-----------|--------|
| **Per PR** | 0813 |
| **Monthly + on change** | 0811, 0817 |
| **Weekly** | 0816 |
| **Monthly** | 0815, 0821 |
| **Quarterly** | 0809, 0810, 0812, 0814, 0818, 0819, 0820, 0822, 0825, 0827, 0898, 0899 |
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

**Documentation Health (0801-0807)**
- [0801 - Open Issues Currency](0801-open-issues-audit.md)
- [0802 - Reports Completeness](0802-reports-completeness-audit.md) ✨
- [0803 - LLD-to-Code Alignment](0803-lld-code-audit.md)
- [0804 - File Inventory Drift](0804-inventory-audit.md) ✨
- [0805 - Terminology Consistency](0805-terminology-audit.md) ✨
- [0806 - Architecture Drift](0806-architecture-audit.md) ✨
- [0807 - AgentOS Health Check](0807-agentos-audit.md) ✨

**Core Development (0808-0831)**
- [0808 - Permission Permissiveness](0808-audit-permission-permissiveness.md) ✨
- [0824 - Permission Friction](0824-audit-permission-friction.md) ✨
- [0809 - Security](0809-audit-security.md)
- [0810 - Privacy](0810-audit-privacy.md)
- [0811 - Accessibility](0811-audit-accessibility.md)
- [0812 - Performance](0812-audit-performance.md)
- [0813 - Code Quality](0813-audit-code-quality.md)
- [0814 - License Compliance](0814-audit-license-compliance.md)
- [0817 - Wiki Alignment](0817-audit-wiki-alignment.md)
- [0815 - Claude Code Capabilities](0815-audit-claude-capabilities.md)
- [0816 - Dependabot PRs](0816-audit-dependabot-prs.md)
- [0826 - Cross-Browser Testing](0826-audit-cross-browser-testing.md)
- [0827 - Infrastructure Integration](0827-audit-infrastructure-integration.md)
- [0828 - Build Artifact Freshness](0828-audit-build-artifact-freshness.md) ✨
- [0829 - Lambda Failure Remediation](0829-audit-lambda-failure-remediation.md)
- [0830 - Architecture Freshness](0830-audit-architecture-freshness.md) ✨
- [0831 - Web Assets](0831-audit-web-assets.md)
- [0832 - Cost Optimization](0832-audit-cost-optimization.md) ✨

**Ultimate Tier (--ultimate only)**
- [0833 - Gitignore Encryption Review](0833-audit-gitignore-encryption.md) 🔒

**AI Governance (0818-0825)**
- [0818 - AI Management System](0818-audit-ai-management-system.md)
- [0819 - AI Supply Chain](0819-audit-ai-supply-chain.md)
- [0820 - Explainability](0820-audit-explainability.md)
- [0821 - Agentic AI Governance](0821-audit-agentic-ai-governance.md)
- [0822 - Bias & Fairness](0822-audit-bias-fairness.md)
- [0823 - AI Incident Post-Mortem](0823-audit-ai-incident-post-mortem.md)
- [0825 - AI Safety](0825-audit-ai-safety.md)

**Meta (0898-0899)**
- [0898 - Horizon Scanning Protocol](0898-horizon-scanning-protocol.md)
- [0899 - Meta-Audit](0899-meta-audit.md)

✨ = Auto-fix capability (audit automatically fixes findings rather than just reporting)
🔒 = Ultimate tier (only runs with `--ultimate` flag or direct invocation)

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
| **Haiku** | $ | 0808, 0812, 0814, 0816, 0817, 0819, 0827, 0899 | Simple checklist, metric aggregation, file parsing |
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
| 0898 Horizon Scanning | Sonnet | Framework research, moderate analysis |
| 0899 Meta-Audit | Haiku | Execution tracking, checklist validation |

### 11.3 Estimated Savings

By using appropriate models instead of Opus for all audits:
- **Haiku audits (8):** ~66% savings per audit
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
