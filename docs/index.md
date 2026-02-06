# AssemblyZero Documentation Index

**Version:** 3.0
**Last Updated:** 2026-01-21

---

## Primary Documentation: GitHub Wiki

📖 **[AssemblyZero Wiki](https://github.com/martymcenroe/AssemblyZero/wiki)** - Main documentation portal for enterprise users

### Key Wiki Pages

| Page | Audience | Description |
|------|----------|-------------|
| [Home](https://github.com/martymcenroe/AssemblyZero/wiki) | Everyone | Overview and architecture diagram |
| [Multi-Agent Orchestration](https://github.com/martymcenroe/AssemblyZero/wiki/Multi-Agent-Orchestration) | Architects | Core architecture - 12+ concurrent agents |
| [LangGraph Evolution](https://github.com/martymcenroe/AssemblyZero/wiki/LangGraph-Evolution) | Tech Leaders | Roadmap to enterprise state machines |
| [Measuring Productivity](https://github.com/martymcenroe/AssemblyZero/wiki/Measuring-Productivity) | VPs/Leadership | KPIs, metrics, dashboards |
| [Gemini Verification](https://github.com/martymcenroe/AssemblyZero/wiki/Gemini-Verification) | Architects | Multi-model review architecture |
| [Governance Gates](https://github.com/martymcenroe/AssemblyZero/wiki/Governance-Gates) | Security Teams | LLD, implementation, report gates |
| [Permission Friction](https://github.com/martymcenroe/AssemblyZero/wiki/Permission-Friction) | Developers | Adoption optimization |
| [Security & Compliance](https://github.com/martymcenroe/AssemblyZero/wiki/Security-Compliance) | Security Teams | OWASP, GDPR, AI Safety |
| [Quick Start](https://github.com/martymcenroe/AssemblyZero/wiki/Quick-Start) | Developers | 5-minute setup guide |

---

## Quick Links (Local Docs)

| Need to... | Go to |
|------------|-------|
| Set up a new project | [0901-new-project-setup.md](runbooks/0901-new-project-setup.md) |
| Look up a command | [0600-command-index.md](skills/0600-command-index.md) |
| Create a new runbook | [0109-runbook-template.md](templates/0109-runbook-template.md) |
| Document a new tool | [0008-documentation-convention.md](standards/0008-documentation-convention.md) |
| Understand core rules | [CLAUDE.md](../CLAUDE.md) |

---

## Directory Structure

```
AssemblyZero/
├── CLAUDE.md                    # Core rules (inherited by all projects)
├── docs/
│   ├── index.md                 # This file
│   ├── skills/                  # 06xx - Command/skill documentation
│   ├── runbooks/                # 09xx - Operational procedures
│   └── templates/               # 01xx - Document templates
├── tools/                       # Python utilities
│   ├── assemblyzero-generate.py      # Config generator
│   ├── assemblyzero-permissions.py   # Permission manager
│   └── ...
├── .claude/
│   ├── commands/                # Canonical skill implementations
│   ├── templates/               # Config templates (with {{VAR}})
│   └── project.json.example     # Example project config
└── logs/                        # Runtime logs (zugzwang, etc.)
```

---

## Numbering Convention

### Parent-Child Scheme (AssemblyZero ↔ Projects)

AssemblyZero uses **4-digit numbers** for generic/shared frameworks.
Projects use **5-digit numbers** (prefix `1` + AssemblyZero number) for implementations.

| Scope | Digits | Range | Example |
|-------|--------|-------|---------|
| **AssemblyZero (Generic)** | 4 | 0000-9999 | `0809-agentic-ai-governance.md` |
| **Projects (Specific)** | 5 | 10000-19999 | `10809-agentic-ai-governance.md` |

**The `1` prefix means "project-specific implementation of":**
- AssemblyZero `0809` = Generic audit framework for agentic AI governance
- Aletheia `10809` = Aletheia's implementation of that audit
- Talos `10809` = Talos's implementation of that audit

**Future commands enabled:**
- `compare 0809 10809` - Compare generic to project-specific
- `promote 10809` - Extract common patterns from all projects' 10809, move to AssemblyZero 0809

### AssemblyZero Categories (4-digit)

| Range | Category | Directory | Description |
|-------|----------|-----------|-------------|
| 00xx | Standards | standards/ | Core protocols, coding standards |
| 01xx | Templates | templates/ | Document templates |
| 02xx | ADRs | adrs/ | Architecture Decision Records |
| 06xx | Skills | skills/ | Command documentation |
| 08xx | Audits | audits/ | Audit frameworks |
| 09xx | Runbooks | runbooks/ | Operational procedures |

### Project Categories (5-digit)

| Range | Category | Directory | Description |
|-------|----------|-----------|-------------|
| 100xx | Standards | standards/ | Project-specific standards |
| 101xx | Templates | templates/ | Project-specific templates |
| 102xx | ADRs | adrs/ | Project-specific ADRs |
| 106xx | Skills | skills/ | Project-specific skills |
| 108xx | Audits | audits/ | Project-specific audit reports |
| 109xx | Runbooks | runbooks/ | Project-specific runbooks |
| 10001 | Architecture | architecture/ | C4 diagrams (project-specific) |

**Sub-numbering:** Within a range, letters denote related sub-documents:
- 0001-architecture.md (main) → 10001-architecture.md (project)
- 0001a-context-view.md (sub-topic) → 10001a-context-view.md (project)

---

## Document Catalog

### Standards (00xx)

| Number | Title | Description |
|--------|-------|-------------|
| [0001](standards/0001-orchestration-protocol.md) | Orchestration Protocol | Multi-agent coordination |
| [0002](standards/0002-coding-standards.md) | Coding Standards | Code style and practices |
| [0003](standards/0003-agent-prohibited-actions.md) | Agent Prohibited Actions | What agents must NOT do |
| [0004](standards/0004-mermaid-diagrams.md) | Mermaid Diagrams | Diagram standards |
| [0005](standards/0005-session-closeout-protocol.md) | Session Closeout | End-of-session procedures |
| [0006](standards/0006-standard-labels.md) | Standard Labels | GitHub labels convention |
| [0007](standards/0007-testing-strategy.md) | Testing Strategy | Test-first philosophy |
| [0008](standards/0008-documentation-convention.md) | Documentation Convention | c/p pattern for CLI vs Prompt docs |

### Templates (01xx)

| Number | Title | Description |
|--------|-------|-------------|
| [0100](templates/0100-template-guide.md) | Template Guide | How to use templates |
| [0101](templates/0101-issue-template.md) | Issue Template | GitHub issue format |
| [0102](templates/0102-feature-lld-template.md) | Feature LLD | Low-level design template |
| [0103](templates/0103-implementation-report-template.md) | Implementation Report | Post-impl documentation |
| [0104](templates/0104-adr-template.md) | ADR Template | Architecture decisions |
| [0105](templates/0105-implementation-plan-template.md) | Implementation Plan | Pre-impl planning |
| [0106](templates/0106-lld-pre-impl-review.md) | LLD Pre-Impl Review | Review checklist |
| [0107](templates/0107-test-script-template.md) | Test Script | Test case format |
| [0108](templates/0108-test-report-template.md) | Test Report | Test results format |
| [0109](templates/0109-runbook-template.md) | Runbook Template | Operational procedures |

### ADRs (02xx)

| Number | Title | Description |
|--------|-------|-------------|
| [0201](adrs/0201-adversarial-audit-philosophy.md) | Adversarial Audit Philosophy | Security mindset |
| [0202](adrs/0202-claude-staging-pattern.md) | Claude Staging Pattern | Safe deployment |
| [0203](adrs/0203-git-worktree-isolation.md) | Git Worktree Isolation | Multi-agent safety |
| [0204](adrs/0204-single-identity-orchestration.md) | Single Identity Orchestration | Agent identity |
| [0205](adrs/0205-test-first-philosophy.md) | Test-First Philosophy | Quality approach |
| [0206](adrs/0206-bidirectional-sync-architecture.md) | Bidirectional Sync Architecture | Cross-project propagation |

### Skills (06xx)

| Number | Title | Description |
|--------|-------|-------------|
| [0600](skills/0600-command-reference.md) | Command Reference | All 8 AssemblyZero commands |
| [0601](skills/0601-gemini-dual-review.md) | Gemini Dual Review | AI-to-AI review |
| [0602](skills/0602-gemini-lld-review.md) | Gemini LLD Review | Design review |
| [0604](skills/0604-gemini-retry.md) | Gemini Retry | Exponential backoff for Gemini |
| [0699](skills/0699-skill-instructions-index.md) | Skill Index | All skills listed |

### Audits (08xx)

| Number | Title | Description |
|--------|-------|-------------|
| [0800](audits/0800-audit-index.md) | Audit Index | Master audit list |
| [0801](audits/0801-security-audit.md) | Security Audit | OWASP-based security |
| [0802](audits/0802-privacy-audit.md) | Privacy Audit | IAPP privacy framework |
| [0803](audits/0803-code-quality-audit.md) | Code Quality | Maintainability check |
| [0804](audits/0804-accessibility-audit.md) | Accessibility | WCAG compliance |
| [0805](audits/0805-license-compliance.md) | License Compliance | OSS license check |
| [0806](audits/0806-bias-fairness.md) | Bias & Fairness | AI fairness audit |
| [0807](audits/0807-explainability.md) | Explainability | AI transparency |
| [0808](audits/0808-ai-safety-audit.md) | AI Safety | Safety measures |
| [0809](audits/0809-agentic-ai-governance.md) | Agentic AI Governance | Agent oversight |
| [0810](audits/0810-ai-management-system.md) | AI Management System | ISO 42001 alignment |
| [0811](audits/0811-ai-incident-post-mortem.md) | AI Incident Post-Mortem | Failure analysis |
| [0812](audits/0812-ai-supply-chain.md) | AI Supply Chain | Dependency audit |
| [0813](audits/0813-claude-capabilities.md) | Claude Capabilities | Model features |
| [0814](audits/0814-horizon-scanning-protocol.md) | Horizon Scanning | Threat monitoring |
| [0815](audits/0815-permission-friction.md) | Permission Friction | Approval overhead |
| [0816](audits/0816-permission-permissiveness.md) | Permission Permissiveness | Access control |
| [0817](audits/0817-assemblyzero-audit.md) | AssemblyZero Audit | Self-audit framework |
| [0832](audits/0832-audit-cost-optimization.md) | Cost Optimization | Skill/tool token efficiency |
| [0899](audits/0899-meta-audit.md) | Meta Audit | Audit the audits |

### Runbooks (09xx)

| Number | Title | Description |
|--------|-------|-------------|
| [0900](runbooks/0900-runbook-index.md) | Runbook Index | All runbooks listed |
| [0901](runbooks/0901-new-project-setup.md) | New Project Setup | Initialize with AssemblyZero |
| [0902](runbooks/0902-nightly-assemblyzero-audit.md) | Nightly AssemblyZero Audit | Scheduled audit run |

---

## Commands Quick Reference

| Command | Alias | Purpose |
|---------|-------|---------|
| /cleanup | /closeout, /goodbye | Session cleanup |
| /code-review | | Multi-agent PR review |
| /commit-push-pr | | Git workflow automation |
| /friction | | Permission friction analysis |
| /onboard | | Agent project onboarding |
| /sync-permissions | | Permission cleanup |
| /test-gaps | | Test coverage analysis |
| /zugzwang | /zz | Real-time friction logging |

See [0600-command-reference.md](skills/0600-command-reference.md) for full details.

---

## Key Files

| File | Purpose |
|------|---------|
| CLAUDE.md | Core rules inherited by all projects |
| .claude/project.json.example | Template for project configuration |
| tools/assemblyzero-generate.py | Generate configs from templates |
| tools/assemblyzero-permissions.py | Manage permission settings |
| tools/gemini-retry.py | Gemini CLI wrapper with exponential backoff |
| tools/claude-usage-scraper.py | Usage quota extraction via TUI automation |

---

## Inheritance Model

```
AssemblyZero/CLAUDE.md           -> Core rules (bash safety, gates, worktree)
    | inherited by
~/.claude/commands/         -> User-level skills (available everywhere)
    | available to
Project/CLAUDE.md           -> Project-specific rules
    | with
Project/.claude/            -> Generated from AssemblyZero templates
```

---

## Bidirectional Sync Model

See [ADR 0206](adrs/0206-bidirectional-sync-architecture.md) for full details.

```
                    ┌─────────────┐
                    │   AssemblyZero   │
                    │  (Generic)  │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐      ┌─────▼─────┐     ┌─────▼─────┐
    │ Aletheia│      │   Talos   │     │maintenance│
    │(10xxx)  │      │  (10xxx)  │     │  (10xxx)  │
    └────┬────┘      └─────┬─────┘     └─────┬─────┘
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                     ┌─────▼─────┐
                     │  Harvest  │
                     │  Promote  │
                     └───────────┘
```

### Sync Directions

| Direction | Trigger | Tool |
|-----------|---------|------|
| **AssemblyZero → Projects** | Manual, post-commit | `assemblyzero-generate.py` |
| **Project → AssemblyZero** | Agent explicit call | `/promote` command |
| **All Projects → AssemblyZero** | `/cleanup --full` | `assemblyzero-harvest.py` |

### Registered Projects

See `.claude/project-registry.json` for current list.

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-13 | Initial structure with skills, runbooks, templates |
| 2.0 | 2026-01-13 | Full document catalog after numbering audit (47 docs) |
| 2.1 | 2026-01-13 | Added parent-child numbering scheme (4-digit AssemblyZero, 5-digit projects) |
| 2.2 | 2026-01-13 | ADR 0206: Bidirectional sync architecture, project registry created |
| 2.3 | 2026-01-14 | Added 0008 Documentation Convention (c/p pattern) |
| 2.4 | 2026-01-14 | Added 0603 Unleashed, 0604 Gemini Retry, updated Key Files |
