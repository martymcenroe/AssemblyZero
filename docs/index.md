# AgentOS Documentation Index

**Version:** 1.0
**Last Updated:** 2026-01-13

---

## Quick Links

| Need to... | Go to |
|------------|-------|
| Set up a new project | [0901-new-project-setup.md](runbooks/0901-new-project-setup.md) |
| Look up a command | [0600-command-reference.md](skills/0600-command-reference.md) |
| Create a new runbook | [0109-runbook-template.md](templates/0109-runbook-template.md) |
| Understand core rules | [CLAUDE.md](../CLAUDE.md) |

---

## Directory Structure

```
AgentOS/
├── CLAUDE.md                    # Core rules (inherited by all projects)
├── docs/
│   ├── index.md                 # This file
│   ├── skills/                  # 06xx - Command/skill documentation
│   ├── runbooks/                # 09xx - Operational procedures
│   └── templates/               # 01xx - Document templates
├── tools/                       # Python utilities
│   ├── agentos-generate.py      # Config generator
│   ├── agentos-permissions.py   # Permission manager
│   └── ...
├── .claude/
│   ├── commands/                # Canonical skill implementations
│   ├── templates/               # Config templates (with {{VAR}})
│   └── project.json.example     # Example project config
└── logs/                        # Runtime logs (zugzwang, etc.)
```

---

## Numbering Convention

AgentOS follows a 4-digit document numbering system:

| Range | Category | Directory | Description |
|-------|----------|-----------|-------------|
| 00xx | Standards | standards/ | Core protocols, coding standards |
| 01xx | Templates | templates/ | Document templates |
| 02xx | ADRs | adrs/ | Architecture Decision Records |
| 06xx | Skills | skills/ | Command documentation |
| 08xx | Audits | audits/ | Audit frameworks |
| 09xx | Runbooks | runbooks/ | Operational procedures |

**Sub-numbering:** Within a range, letters denote related sub-documents:
- 0001-architecture.md (main)
- 0001a-context-view.md (sub-topic)
- 0001b-container-view.md (sub-topic)

---

## Document Catalog

### Skills (06xx)

| Number | Title | Description |
|--------|-------|-------------|
| [0600](skills/0600-command-reference.md) | Command Reference | All 8 AgentOS commands documented |

### Runbooks (09xx)

| Number | Title | Description |
|--------|-------|-------------|
| [0901](runbooks/0901-new-project-setup.md) | New Project Setup | Initialize a project with AgentOS |

### Templates (01xx)

| Number | Title | Description |
|--------|-------|-------------|
| [0109](templates/0109-runbook-template.md) | Runbook Template | Template for operational procedures |

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
| tools/agentos-generate.py | Generate configs from templates |
| tools/agentos-permissions.py | Manage permission settings |

---

## Inheritance Model

```
AgentOS/CLAUDE.md           -> Core rules (bash safety, gates, worktree)
    | inherited by
~/.claude/commands/         -> User-level skills (available everywhere)
    | available to
Project/CLAUDE.md           -> Project-specific rules
    | with
Project/.claude/            -> Generated from AgentOS templates
```

---

## Future Documents (Planned)

| Number | Title | Category |
|--------|-------|----------|
| 0000 | System Guide | Standards |
| 0001 | Architecture | Standards |
| 0002 | Coding Standards | Standards |
| 0201 | Privacy-First Permissions | ADR |
| 0207 | Worktree Isolation | ADR |
| 0800 | Audit Index | Audits |
| 0900 | Runbook Index | Runbooks |

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-13 | Initial structure with skills, runbooks, templates |
