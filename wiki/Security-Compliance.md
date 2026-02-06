# Security & Compliance

> What security teams need to approve AI coding assistant adoption

---

## Overview

Security teams block AI coding assistant adoption because:

1. **No governance** - AI generates code without review
2. **No audit trail** - Can't trace what AI did
3. **Security blind spots** - AI may introduce vulnerabilities
4. **Compliance gaps** - No evidence of controls

AssemblyZero addresses each concern with concrete mechanisms.

---

## Governance Framework

### Multi-Layer Review

```
┌─────────────────────────────────────────────────┐
│                 HUMAN REVIEW                     │
│         (Final approval before merge)            │
├─────────────────────────────────────────────────┤
│              GEMINI REVIEW GATE                  │
│  (AI reviews AI before human sees it)            │
├─────────────────────────────────────────────────┤
│              CLAUDE GENERATION                   │
│        (AI generates code/designs)               │
└─────────────────────────────────────────────────┘
```

Every AI-generated artifact passes through:
1. **Gemini verification** - Different model reviews for issues
2. **Human approval** - Final judgment before merge

### Enforced Gates

Three mandatory checkpoints:

| Gate | What's Reviewed | Evidence |
|------|-----------------|----------|
| LLD Review | Design document | Gemini verdict + reasoning |
| Implementation Review | Code + tests | Gemini verdict + reasoning |
| Report Generation | Auto-documentation | Audit trail |

Gates cannot be skipped (prompt-based now, state machine in roadmap).

---

## Security Audits

### OWASP Top 10 Coverage

AssemblyZero includes security audits for OWASP vulnerabilities:

| OWASP Category | Audit | Status |
|----------------|-------|--------|
| A01: Broken Access Control | Access control audit | ✓ |
| A02: Cryptographic Failures | Crypto audit | ✓ |
| A03: Injection | Injection audit | ✓ |
| A04: Insecure Design | Design review (LLD gate) | ✓ |
| A05: Security Misconfiguration | Config audit | ✓ |
| A06: Vulnerable Components | Dependency audit | ✓ |
| A07: Auth Failures | Auth audit | ✓ |
| A08: Software Integrity Failures | Integrity audit | ✓ |
| A09: Logging Failures | Logging audit | ✓ |
| A10: SSRF | SSRF audit | ✓ |

### Audit Philosophy

**Adversarial, not confirmatory.**

```
WRONG: "Check that code follows security best practices" ✗
RIGHT: "Find any injection vulnerabilities in this code" ✓
```

Audits are designed to find problems, not confirm compliance.

### Running Audits

```bash
# Run full security audit
/audit --type security

# Run specific OWASP audit
/audit --type owasp-injection

# Audit with auto-fix suggestions
/audit --type security --fix
```

---

## Privacy Compliance

### GDPR Considerations

| Requirement | AssemblyZero Control |
|-------------|-----------------|
| Data minimization | Agents access only necessary files |
| Purpose limitation | Session scoped to specific task |
| Storage limitation | Session data retention policies |
| Audit trail | Full session transcript logging |

### Data Handling

- **No PII in prompts** - Agents instructed to avoid PII
- **Local processing** - File reads are local, not sent upstream
- **Session isolation** - Each session is independent
- **Transcript retention** - Configurable retention period

---

## AI Safety (NIST AI RMF)

### Key Principles

| NIST Category | AssemblyZero Implementation |
|---------------|----------------------|
| **Validity** | Gemini verification of outputs |
| **Safety** | Destructive command blocks |
| **Security** | OWASP audits, secret detection |
| **Accountability** | Full audit trail |
| **Transparency** | Visible reasoning in transcripts |
| **Explainability** | Reports document decisions |
| **Privacy** | Data minimization, local processing |

### Destructive Command Protection

Certain commands are blocked regardless of context:

```
ALWAYS BLOCKED (catastrophic risk):
├── dd if=...          # Disk operations
├── mkfs               # Filesystem creation
├── shred              # Secure delete
└── format             # Format disk

PATH-SCOPED (allowed only in Projects):
├── rm, rm -r, rm -rf  # File deletion
├── git reset --hard   # Discard changes
└── git push --force   # Overwrite history
```

### Model Verification

Agents must use approved models:

| Model | Approved For |
|-------|--------------|
| claude-opus-4 | Complex reasoning, architecture |
| claude-sonnet-4 | General development tasks |
| gemini-3-pro | Review and verification |

**Silent downgrades are detected and rejected.**

---

## Audit Trail

### What's Logged

Every agent session creates:

```
Session: 2026-01-21-001
├── Transcript (full conversation)
├── Tool calls (all commands executed)
├── File changes (diffs)
├── Gemini reviews (verdicts + reasoning)
├── Reports (implementation, tests)
└── Metadata (timestamps, models used)
```

### Log Format

```jsonl
{"timestamp": "2026-01-21T14:32:00Z", "type": "tool_call", "tool": "Bash", "command": "git status"}
{"timestamp": "2026-01-21T14:32:01Z", "type": "tool_result", "output": "On branch feature..."}
{"timestamp": "2026-01-21T14:33:00Z", "type": "gemini_review", "verdict": "APPROVE", "model": "gemini-3-pro"}
```

### Retention

Default retention: 90 days
Configurable in: `~/.assemblyzero/config.json`

---

## Compliance Evidence

### For SOC 2

| Control | Evidence |
|---------|----------|
| Access Control | Single-user identity model |
| Change Management | PR workflow, Gemini gates |
| Audit Logging | Session transcripts |
| Risk Assessment | 34 audits covering major risks |

### For ISO 27001

| Control Area | Evidence |
|--------------|----------|
| A.12 Operations Security | Destructive command blocks |
| A.14 System Acquisition | Gemini verification gates |
| A.16 Incident Management | Audit logs for investigation |
| A.18 Compliance | OWASP, GDPR audits |

### For HIPAA (if applicable)

| Requirement | Evidence |
|-------------|----------|
| Access Controls | Single-user model, session isolation |
| Audit Controls | Full session logging |
| Integrity Controls | Gemini verification |
| Transmission Security | Local processing, no PII in prompts |

---

## 34 Audits Catalog

### By Category

| Category | Count | Examples |
|----------|-------|----------|
| Security (OWASP) | 10 | Injection, XSS, auth |
| Privacy (GDPR) | 6 | Data handling, consent |
| AI Safety (NIST) | 5 | Model verification, bias |
| Code Quality | 8 | Complexity, duplication |
| Documentation | 5 | Completeness, accuracy |

### Audit Index

Full catalog: `/audit --list`

```
Security Audits:
├── 0801-injection-audit
├── 0802-xss-audit
├── 0803-auth-audit
├── 0804-access-control-audit
├── 0805-crypto-audit
├── 0806-config-audit
├── 0807-dependency-audit
├── 0808-ssrf-audit
├── 0809-logging-audit
└── 0810-integrity-audit

Privacy Audits:
├── 0811-pii-detection
├── 0812-consent-audit
├── 0813-data-retention-audit
├── 0814-data-minimization-audit
├── 0815-cross-border-audit
└── 0816-dsar-readiness-audit

AI Safety Audits:
├── 0817-model-verification
├── 0818-bias-detection
├── 0819-hallucination-check
├── 0820-prompt-injection-audit
└── 0821-output-validation-audit
```

---

## For Security Team Reviews

### Approval Checklist

Before approving AI coding assistant adoption:

- [ ] Multi-model verification enabled (Claude + Gemini)
- [ ] All three gates enforced (LLD, Implementation, Report)
- [ ] OWASP audits passing (90%+ coverage)
- [ ] Destructive commands blocked outside Projects
- [ ] Session logging enabled
- [ ] Retention policy defined
- [ ] Model verification active (no silent downgrades)

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| AI introduces vulnerability | Medium | High | Gemini security review |
| Unauthorized code changes | Low | High | PR workflow required |
| Sensitive data exposure | Medium | High | PII detection audit |
| Silent model degradation | Low | Medium | Model verification |
| Audit trail gaps | Low | High | Session logging |

### Residual Risk

With AssemblyZero controls:
- **Reduced** but not eliminated risk of AI-introduced bugs
- **Mitigated** risk of security vulnerabilities
- **Maintained** audit trail for incident response
- **Preserved** human judgment for final approval

---

## Related Pages

- [Governance Gates](Governance-Gates) - Gate implementation details
- [Gemini Verification](Gemini-Verification) - Multi-model architecture
- [Measuring Productivity](Measuring-Productivity) - Audit metrics
- [Multi-Agent Orchestration](Multi-Agent-Orchestration) - Overall architecture
