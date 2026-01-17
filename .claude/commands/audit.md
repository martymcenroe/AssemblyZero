---
description: Full 08xx audit suite with project-specific extensions
argument-hint: "[--help] [--deep] [--ultimate] [NNNN] [NNNN] ..."
---

# Full Audit Suite

**If `$ARGUMENTS` contains `--help`:** Display the Help section below and STOP. Do not execute any audits.

---

## Help

Usage: `/audit [--help] [--deep] [--ultimate] [NNNN] [NNNN] ...`

| Argument | Description |
|----------|-------------|
| `--help` | Show this help message and exit |
| `--deep` | Enable web search for external research (CVEs, GDPR, etc.) |
| `--ultimate` | Include expensive/rare audits (e.g., 0833 Gitignore Encryption) |
| `NNNN` | Run specific audit(s) by number (e.g., `0809`, `0810`) |
| (none) | Run ALL standard audits in sequence (excludes ultimate tier) |

**Examples:**
- `/audit --help` - show this help
- `/audit` - run full suite (standard mode, excludes ultimate)
- `/audit --deep` - run full suite with web research
- `/audit --ultimate` - run full suite INCLUDING expensive audits
- `/audit 0809` - run just security audit
- `/audit 0809 0810 0811` - run security, privacy, accessibility
- `/audit --deep 0809` - run security audit with CVE lookups
- `/audit 0833` - run gitignore encryption review (ultimate tier)

**Output:** Results saved to `docs/audit-results/YYYY-MM-DD.md`

---

## Execution

Execute all 08xx audits in sequence per the project's audit index.

**Audit Index Location:** `docs/audits/` directory

This is **explicit approval** to execute all audits autonomously.

## Arguments

| Arg | Effect |
|-----|--------|
| (none) | Run ALL standard audits - excludes ultimate tier |
| `--deep` | Run ALL standard audits with web search for external research |
| `--ultimate` | Run ALL audits INCLUDING ultimate tier (expensive/rare audits) |
| `NNNN` | Run SINGLE audit by number (e.g., `0801`, `0809`, `0833`) |
| `NNNN NNNN ...` | Run MULTIPLE audits by number (space-separated) |
| `--deep NNNN ...` | Run specified audit(s) with web search |
| `--ultimate --deep` | Run ALL audits including ultimate tier with web search |

## Deep Mode

**Deep mode enables WebSearch/WebFetch for external research:**
- Security: OWASP updates, CVEs, vulnerabilities
- Privacy: GDPR/CCPA guidance
- License: Package license lookups, SPDX compatibility
- Capabilities: Anthropic changelog, Claude Code releases
- AI Governance: ISO/IEC 42001 updates, OWASP Agentic Top 10
- Horizon Scanning: Framework discovery (**REQUIRES deep**)

## Ultimate Mode

**Ultimate mode includes expensive or rarely-needed audits:**
- 0833: Gitignore Encryption Review (scans all .gitignore entries, recommends encrypt vs ignore)

These audits are excluded from standard runs because:
- They may take longer to execute
- They require human judgment for many findings
- They're typically run once per project setup, not routinely

**Direct invocation always works:** `/audit 0833` runs the specific audit regardless of tier.

## Rules

- Use absolute paths and `git -C` patterns (no cd && chaining)
- Use `--repo {{GITHUB_REPO}}` for all gh commands (skip if no repo)
- **Evidence over inference:** Grep code/config, don't trust doc claims
- **Do NOT auto-fix issues** - report findings for orchestrator triage
  - **Exception:** Remediation audits (like Lambda Failure Remediation) MAY fix issues on worktrees
- Report findings with severity: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`
- In standard mode: Skip audits that require external access
- In deep mode: Use WebSearch tool for external research

---

## Core Audit Sequence (AgentOS Generic)

These audits apply to ALL projects using AgentOS:

### 0801 - Open Issues Currency
**Purpose:** Identify issues that are actually complete, deprecated, or stale.
**Check:** For each open issue, verify it's truly in progress. Flag:
- Issues with no activity in 30+ days
- Issues that appear complete based on merged PRs
- Issues superseded by other work

### 0802 - Reports Completeness
**Purpose:** Ensure all closed issues have required reports.
**Check:** For each closed issue, verify `docs/reports/{IssueID}/` exists with implementation and test reports.

### 0803 - Code Quality Audit
**Purpose:** Manual quality checks beyond linting.
**Check:** SOLID principles, cyclomatic complexity, test coverage gaps, documentation completeness.

### 0804 - File Inventory Drift
**Purpose:** Detect files not in inventory, or inventory entries for deleted files.
**Check:** Compare actual files against `docs/0003-file-inventory.md`.

### 0805 - Terminology Consistency
**Purpose:** Ensure consistent naming across docs and code.
**Check:** Grep for deprecated terms, verify modern alternatives used.

### 0806 - Architecture Audit
**Purpose:** Detect drift between architecture docs and actual codebase.
**Check:** Verify components exist, verify code is documented, check ADRs are accurate.

### 0807 - AgentOS Health Check
**Purpose:** Verify the documentation system itself is healthy.
**Check:** Doc formatting, cross-references, templates match practice.

### 0808 - Permission Permissiveness
**Purpose:** Ensure agent permissions are maximally permissive within safety bounds.
**Check:** Verify deny list contains only truly dangerous commands, identify friction patterns.

### 0809 - Security Audit
**Purpose:** Comprehensive security audit.
**Check:** OWASP Top 10 (2021), OWASP LLM Top 10 (2025), OWASP Agentic Security (2026).
**Deep mode:** CVE searches, vulnerability lookups.

### 0810 - Privacy Audit
**Purpose:** Verify data protection compliance.
**Check:** Data collection inventory, storage duration, consent mechanisms, deletion capability.
**Deep mode:** GDPR/CCPA guidance lookups.

### 0811 - Accessibility Audit
**Purpose:** WCAG 2.1 compliance.
**Check:** Keyboard navigation, screen reader compatibility, color contrast, focus indicators.

### 0812 - Performance Audit
**Purpose:** Ensure acceptable performance.
**Check:** Load times, cold starts, memory usage, cost per request.

### 0813 - Code Quality Deep Dive
**Purpose:** Extended code quality analysis.
**Check:** SOLID principles, complexity metrics, test coverage.

### 0814 - License Compliance
**Purpose:** Ensure compatible licenses.
**Check:** Verify all dependencies use compatible licenses (MIT, Apache-2.0, BSD, ISC).
**Deep mode:** Package license lookups.

### 0815 - Claude Capabilities
**Purpose:** Track new Claude Code features.
**Standard mode:** SKIP (requires web search)
**Deep mode:** ENABLED - Check Anthropic changelog, new features.

### 0816 - Permission Permissiveness
**Purpose:** Detailed permission friction analysis.
**Check:** Read settings.local.json, identify friction patterns.

### 0817 - Documentation Alignment
**Purpose:** Ensure documentation reflects reality.
**Check:** README, Wiki, and docs align with current state.

### 0818 - AI Management System (ISO/IEC 42001)
**Purpose:** AI governance per ISO/IEC 42001:2023.
**Check:**
1. AI system inventory (models, agents, classifiers)
2. Risk classification per system
3. Development lifecycle documentation
4. Data management practices
**Deep mode:** WebSearch for ISO 42001 updates.

### 0819 - AI Supply Chain
**Purpose:** Model provenance, dependency security, AIBOM.
**Check:**
1. Model source verification (provider, version)
2. Model version pinning
3. Dependency vulnerability scan
4. Training data source integrity (if applicable)
**Deep mode:** WebSearch for model security advisories, AIBOM standards.

### 0820 - Explainability (XAI)
**Purpose:** Ensure AI outputs are understandable and traceable.
**Check:**
1. AI disclosure to users
2. Reasoning/rationale included in outputs
3. Decision traceability
4. Uncertainty markers present
**Deep mode:** WebSearch for EU AI Act transparency requirements, XAI frameworks.

### 0821 - Agentic AI Governance
**Purpose:** OWASP Agentic Top 10 compliance for AI agents.
**Check:**
1. AA01 Agent Goal Hijacking - Boundary enforcement
2. AA05 Tool Misuse - Permission deny lists
3. AA06 Excessive Autonomy - Human approval gates
4. AA07 Trust Boundary Violations - Isolation mechanisms
**Deep mode:** WebSearch for OWASP Agentic Top 10 updates.

### 0822 - Bias & Fairness
**Purpose:** Ensure fair, unbiased AI outputs.
**Check:**
1. Cultural/linguistic bias in outputs
2. Source data bias
3. Output consistency testing
4. Demographic fairness (if applicable)

### 0823 - AI Incident Post-Mortem
**Purpose:** Structured process for AI failure analysis.
**Check:**
1. Review any open/recent AI-related issues
2. Verify incident classification process exists
3. Check lessons learned captured
4. Review response time SLAs

### 0832 - Cross-Project Harvest
**Purpose:** Discover patterns in child projects worth promoting to AgentOS.
**Tool:** `poetry run python tools/agentos-harvest.py`
**Check:** Commands, tools, templates, permissions that appeared in multiple projects.

### 0833 - Gitignore Encryption Review (Ultimate Tier)
**Purpose:** Review .gitignore entries and recommend encrypt vs ignore.
**Standard mode:** SKIP (ultimate tier only)
**Ultimate mode:** ENABLED - Scan all .gitignore patterns.
**Check:** For each gitignored path, categorize as:
- ENCRYPT: Sensitive data that should travel with repo (use git-crypt)
- IGNORE: Build artifacts, caches, truly local files (keep in .gitignore)
- REVIEW: Unknown pattern, needs human decision

### 0898 - Horizon Scanning
**Purpose:** Discover emerging AI governance frameworks and threats.
**Standard mode:** SKIP (requires web search)
**Deep mode:** ENABLED - Framework discovery.

### 0899 - Meta-Audit
**Purpose:** Audit the audit suite itself.
**Check:** All 08xx procedures indexed, no stale procedures, appropriate triggers.

---

## Project-Specific Audits

Projects may define additional audits in their `docs/audits/` directory using the **10xxx numbering scheme** (project-specific implementations).

**Example:** Aletheia has `10809-audit-security.md` extending the generic `0809` framework.

To include project-specific audits:
1. Check if `docs/audits/` exists in project
2. Read audit index for project-specific procedures
3. Execute those in addition to generic suite

---

## Output Format

After audit(s) complete, produce a summary table:

```markdown
## Audit Results - YYYY-MM-DD

| Audit | Status | Findings |
|-------|--------|----------|
| 0801 Open Issues | PASS/FAIL | N issues need attention |
| 0802 Reports | PASS/FAIL | N missing reports |
| ... | ... | ... |

### Critical Findings
1. [CRITICAL] Description...

### High Priority Findings
1. [HIGH] Description...

### Recommendations
1. ...
```

Save findings to `docs/audit-results/YYYY-MM-DD.md` (create directory if needed).
