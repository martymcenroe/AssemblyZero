# Audits Catalog

> 34 governance audits covering security, privacy, AI safety, and compliance

---

## Overview

AssemblyZero includes a comprehensive audit suite designed with an **adversarial philosophy**: audits exist to find violations, not confirm compliance.

| Category | Count | Focus |
|----------|-------|-------|
| Core Audits | 17 | Security, privacy, AI governance, permissions |
| Extended Audits | 9 | Cost, structure, hygiene, references |
| Documentation Health | 6 | Docs-code alignment |
| Meta | 1 | Audit system governance |
| **Total** | **34** | |

---

## Audit Philosophy

> "Don't trust metadata—verify reality."

### Evidence over Inference

Do not assume compliance based on file names or documentation claims. Grep the code/config for the specific setting.

| Bad Practice | Good Practice |
|--------------|---------------|
| "Docs say X is disabled" | `grep X src/config.py` |
| "README says MIT license" | Compare LICENSE, package.json, pyproject.toml |

**The code is the truth. The docs are a claim about the truth.**

### Fix-First Mandate

> "An audit that finds the same error twice is a broken audit."

Audits MUST fix errors, not just document them:

1. **Auto-fix immediately** - If the fix is mechanical, do it
2. **Auto-fix with rebuild** - If fix requires build/test cycle, run it
3. **Create GitHub issue** - Only if fix requires human judgment
4. **Exception** - Only if fix is impossible (external dependency)

---

## Quick Reference

### Security & Privacy

| Audit | Description | Auto-Fix |
|-------|-------------|----------|
| **0801** | Security (OWASP Top 10, ASVS) | No |
| **0802** | Privacy (GDPR-aware, data handling) | No |
| **0805** | License Compliance (OSS licenses) | No |

### AI Governance

| Audit | Description | Framework |
|-------|-------------|-----------|
| **0806** | Bias & Fairness | ISO 24027, NIST |
| **0807** | Explainability (XAI) | EU AI Act Art. 13 |
| **0808** | AI Safety | OWASP LLM 2025, NIST AI RMF |
| **0809** | Agentic AI Governance | OWASP Agentic 2026 |
| **0810** | AI Management System | ISO/IEC 42001:2023 |
| **0811** | AI Incident Post-Mortem | NIST AI RMF |
| **0812** | AI Supply Chain | OWASP LLM03:2025, SPDX 3.0 |

### Code Quality & Development

| Audit | Description | Auto-Fix |
|-------|-------------|----------|
| **0803** | Code Quality | CI |
| **0804** | Accessibility (WCAG) | No |
| **0813** | Claude Code Capabilities | No |
| **0814** | Horizon Scanning Protocol | No |

### Permission Management

| Audit | Description | Auto-Fix |
|-------|-------------|----------|
| **0815** | Permission Friction | **Yes** |
| **0816** | Permission Permissiveness | **Yes** |
| **0817** | AssemblyZero Self-Audit | **Yes** |

### Extended Audits

| Audit | Description | Auto-Fix |
|-------|-------------|----------|
| **0832** | Cost Optimization | Partial |
| **0833** | Gitignore Encryption Review | No |
| **0834** | Worktree Hygiene | No |
| **0835** | Structure Compliance | No |
| **0836** | Gitignore Consistency | No |
| **0837** | README Compliance | No |
| **0838** | Broken References | No |
| **0839** | Wiki Alignment | No |
| **0840** | Cross-Project Harvest | No |

### Documentation Health

| Audit | Description | Auto-Fix |
|-------|-------------|----------|
| **0841** | Open Issues Currency | No |
| **0842** | Reports Completeness | **Yes** |
| **0843** | LLD-to-Code Alignment | No |
| **0844** | File Inventory Drift | **Yes** |
| **0845** | Terminology Consistency | **Yes** |
| **0846** | Architecture Drift | **Yes** |

### Meta

| Audit | Description | Purpose |
|-------|-------------|---------|
| **0899** | Meta-Audit | Validate audit execution |

---

## Standards Coverage

| Standard | Primary Audit | Supporting |
|----------|---------------|------------|
| **OWASP LLM Top 10 (2025)** | 0808 | 0809 |
| **OWASP Agentic Top 10 (2026)** | 0809 | 0808, 0815 |
| **ISO/IEC 42001:2023** | 0810 | 0809, 0806 |
| **EU AI Act** | 0807 | 0809, 0810 |
| **NIST AI RMF** | 0810 | 0811 |
| **ASVS 4.0.3** | 0801 | |
| **GDPR** | 0802 | |
| **WCAG** | 0804 | |

---

## Frequency

| Frequency | Audits |
|-----------|--------|
| **Per PR** | 0803 |
| **Weekly** | 0815, 0816, 0834, 0838 |
| **Monthly** | 0809, 0817, 0832, 0839 |
| **Quarterly** | 0801, 0802, 0805, 0806, 0807, 0808, 0810, 0812, 0814, 0899 |
| **On incident** | 0811 |

---

## Running Audits

### Via Skill

```
/audit                    # Run standard audits
/audit --full             # Run all standard audits
/audit --ultimate         # Include expensive audits (0833)
/audit 0801               # Run specific audit
```

### Model Recommendations

| Model | Best For | Audits |
|-------|----------|--------|
| **Haiku** | Simple checklists, parsing | 0808, 0812, 0814, 0816, 0817, 0834, 0899 |
| **Sonnet** | Moderate reasoning, research | 0811, 0815, 0820, 0822, 0831, 0898 |
| **Opus** | Complex analysis, security | 0809, 0810, 0818, 0821, 0823, 0825 |

---

## Related Pages

- [Security & Compliance](Security-Compliance) - Security posture overview
- [Governance Gates](Governance-Gates) - LLD, implementation, report gates
- [Measuring Productivity](Measuring-Productivity) - Audit metrics
- [Tools Reference](Tools-Reference) - Tool documentation
