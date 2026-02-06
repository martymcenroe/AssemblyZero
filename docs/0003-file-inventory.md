# AssemblyZero - File Inventory & Status Map

**Document:** 0003
**Version:** 1.2
**Last Updated:** 2026-01-21

## 1. Status Taxonomy

| Status | Meaning |
|--------|---------|
| **Stable** | Verified, documented, production-ready |
| **Beta** | Functional but lacks full test coverage or documentation |
| **In-Progress** | Active development; expect instability |
| **Placeholder** | Skeleton or empty file; do not run |
| **Legacy** | Deprecated/archived (reference only) |

---

## 2. Documentation Inventory

### Standards (00xx) - 9 files

| File | Status | Description |
|------|--------|-------------|
| `0001-orchestration-protocol.md` | Stable | Multi-agent coordination rules |
| `0002-coding-standards.md` | Stable | Code style and practices |
| `0003-agent-prohibited-actions.md` | Stable | Forbidden agent actions |
| `0004-mermaid-diagrams.md` | Stable | Diagram conventions |
| `0005-session-closeout-protocol.md` | Stable | End-of-session procedures |
| `0006-standard-labels.md` | Stable | GitHub labels |
| `0007-testing-strategy.md` | Stable | Test-first philosophy |
| `0008-documentation-convention.md` | Stable | c/p pattern for CLI vs Prompt docs |
| `0009-canonical-project-structure.md` | Stable | Standard project layout |

### Templates (01xx) - 10 files

| File | Status | Description |
|------|--------|-------------|
| `0100-template-guide.md` | Stable | How to use templates |
| `0101-issue-template.md` | Stable | GitHub issue format |
| `0102-feature-lld-template.md` | Stable | Low-level design |
| `0103-implementation-report-template.md` | Stable | Post-impl docs |
| `0104-adr-template.md` | Stable | ADR format |
| `0105-implementation-plan-template.md` | Stable | Pre-impl planning |
| `0106-lld-pre-impl-review.md` | Stable | Review checklist |
| `0107-test-script-template.md` | Stable | Test case format |
| `0108-test-report-template.md` | Stable | Test results format |
| `0109-runbook-template.md` | Stable | Operational procedures |

### ADRs (02xx) - 6 files

| File | Status | Description |
|------|--------|-------------|
| `0201-adversarial-audit-philosophy.md` | Stable | Security mindset |
| `0202-claude-staging-pattern.md` | Stable | Safe deployment |
| `0203-git-worktree-isolation.md` | Stable | Multi-agent safety |
| `0204-single-identity-orchestration.md` | Stable | Agent identity |
| `0205-test-first-philosophy.md` | Stable | Quality approach |
| `0206-bidirectional-sync-architecture.md` | Stable | Cross-project propagation |

### Skills (06xx) - 30 files

Skill documentation uses the c/p convention (CLI + Prompt pairs).

| File | Status | Description |
|------|--------|-------------|
| `0600-command-index.md` | Stable | All commands documented |
| `0601-gemini-dual-review.md` | Stable | AI-to-AI review |
| `0602-gemini-lld-review.md` | Stable | Design review |
| `0604-gemini-retry.md` | Stable | Exponential backoff for Gemini |
| `0699-skill-instructions-index.md` | Stable | Skill index |
| `0620c-sync-permissions-cli.md` | Stable | CLI: Permission sync |
| `0620p-sync-permissions-prompt.md` | Stable | Prompt: Permission sync |
| `0621c-cleanup-cli.md` | Stable | CLI: Session cleanup |
| `0621p-cleanup-prompt.md` | Stable | Prompt: Session cleanup |
| `0622c-onboard-cli.md` | Stable | CLI: Agent onboarding |
| `0622p-onboard-prompt.md` | Stable | Prompt: Agent onboarding |
| `0623c-friction-cli.md` | Stable | CLI: Permission friction |
| `0623p-friction-prompt.md` | Stable | Prompt: Permission friction |
| `0624c-zugzwang-cli.md` | Stable | CLI: Friction logger |
| `0624p-zugzwang-prompt.md` | Stable | Prompt: Friction logger |
| `0625c-code-review-cli.md` | Stable | CLI: Code review |
| `0625p-code-review-prompt.md` | Stable | Prompt: Code review |
| `0625c-gemini-retry-cli.md` | Stable | CLI: Gemini retry |
| `0625p-gemini-retry-prompt.md` | Stable | Prompt: Gemini retry |
| `0626c-commit-push-pr-cli.md` | Stable | CLI: Git workflow |
| `0626p-commit-push-pr-prompt.md` | Stable | Prompt: Git workflow |
| `0626c-gemini-rotate-cli.md` | Stable | CLI: Gemini rotation |
| `0626p-gemini-rotate-prompt.md` | Stable | Prompt: Gemini rotation |
| `0627c-test-gaps-cli.md` | Stable | CLI: Test gap analysis |
| `0627p-test-gaps-prompt.md` | Stable | Prompt: Test gap analysis |
| `0627c-assemblyzero-harvest-cli.md` | Stable | CLI: Pattern harvester |
| `0627p-assemblyzero-harvest-prompt.md` | Stable | Prompt: Pattern harvester |
| `0628c-Manual-Issue-Review-Prompt.md` | Stable | Manual issue review |
| `0629c-Manual-LLD-Review-Prompt.md` | Stable | Manual LLD review |
| `0630c-Manual-Implementation-Review-Prompt.md` | Stable | Manual implementation review |

### Audits (08xx) - 34 files

| File | Status | Description |
|------|--------|-------------|
| `0800-audit-index.md` | Stable | Master audit list |
| `0801-security-audit.md` | Stable | OWASP security |
| `0802-privacy-audit.md` | Stable | IAPP privacy |
| `0803-code-quality-audit.md` | Stable | Maintainability |
| `0804-accessibility-audit.md` | Stable | WCAG compliance |
| `0805-license-compliance.md` | Stable | OSS licenses |
| `0806-bias-fairness.md` | Stable | AI fairness |
| `0807-explainability.md` | Stable | AI transparency |
| `0808-ai-safety-audit.md` | Stable | Safety measures |
| `0809-agentic-ai-governance.md` | Stable | Agent oversight |
| `0810-ai-management-system.md` | Stable | ISO 42001 |
| `0811-ai-incident-post-mortem.md` | Stable | Failure analysis |
| `0812-ai-supply-chain.md` | Stable | Dependencies |
| `0813-claude-capabilities.md` | Stable | Model features |
| `0814-horizon-scanning-protocol.md` | Stable | Threat monitoring |
| `0815-permission-friction.md` | Stable | Approval overhead |
| `0816-permission-permissiveness.md` | Stable | Access control |
| `0817-assemblyzero-audit.md` | Stable | Self-audit |
| `0817-audit-wiki-alignment.md` | Stable | Wiki sync |
| `0832-cross-project-harvest.md` | Stable | Pattern harvesting |
| `0832-audit-cost-optimization.md` | Stable | Token efficiency |
| `0833-audit-gitignore-encryption.md` | Stable | Encrypt vs ignore |
| `0834-audit-worktree-hygiene.md` | Stable | Worktree cleanup |
| `0835-audit-structure-compliance.md` | Stable | Project structure |
| `0836-audit-gitignore-consistency.md` | Stable | Gitignore patterns |
| `0837-audit-readme-compliance.md` | Stable | README standards |
| `0838-audit-broken-references.md` | Stable | Cross-reference validation |
| `0899-meta-audit.md` | Stable | Audit the audits |

### Runbooks (09xx) - 5 files

| File | Status | Description |
|------|--------|-------------|
| `0900-runbook-index.md` | Stable | All runbooks |
| `0901-new-project-setup.md` | Stable | Project init |
| `0902-nightly-assemblyzero-audit.md` | Stable | Scheduled audit |
| `0903-windows-scheduled-tasks.md` | Stable | Windows Task Scheduler |
| `0905-gemini-credentials.md` | Stable | Gemini credential management |

---

## 3. Tools Inventory (12 files)

### Core Tools

| File | Status | Description |
|------|--------|-------------|
| `tools/assemblyzero-generate.py` | Stable | Config generator from templates |
| `tools/assemblyzero-permissions.py` | Stable | Permission manager (sync, clean, merge-up) |
| `tools/assemblyzero_config.py` | Stable | Config loader for path parameterization |
| `tools/assemblyzero_credentials.py` | Stable | Credential management utilities |
| `tools/assemblyzero-harvest.py` | Beta | Pattern harvester for permission discovery |

### Gemini Integration

| File | Status | Description |
|------|--------|-------------|
| `tools/gemini-retry.py` | Stable | Exponential backoff for MODEL_CAPACITY_EXHAUSTED |
| `tools/gemini-rotate.py` | Stable | Credential rotation for quota management |
| `tools/gemini-test-credentials.py` | Stable | Credential validation tool |

### Utilities

| File | Status | Description |
|------|--------|-------------|
| `tools/zugzwang.py` | Stable | Permission friction logger |
| `tools/append_session_log.py` | Stable | Session tracking |
| `tools/update-doc-refs.py` | Beta | Documentation reference updater |
| `tools/claude-usage-scraper.py` | Stable | Quota visibility via TUI scraping |

---

## 4. Configuration Inventory

| File | Status | Description |
|------|--------|-------------|
| `CLAUDE.md` | Stable | Core agent rules |
| `.claude/project.json.example` | Stable | Project config template |
| `.claude/commands/*.md` | Stable | 9 skill definitions (see below) |
| `.claude/templates/*.template` | Stable | Config templates |

### Skills/Commands (9 files)

| File | Status | Description |
|------|--------|-------------|
| `.claude/commands/audit.md` | Stable | Full audit suite |
| `.claude/commands/cleanup.md` | Stable | Session cleanup |
| `.claude/commands/code-review.md` | Stable | Parallel code review |
| `.claude/commands/commit-push-pr.md` | Stable | Git workflow |
| `.claude/commands/friction.md` | Stable | Permission friction analysis |
| `.claude/commands/onboard.md` | Stable | Agent onboarding |
| `.claude/commands/promote.md` | Stable | Pattern promotion to AssemblyZero |
| `.claude/commands/test-gaps.md` | Stable | Test gap mining |
| `.claude/commands/zugzwang.md` | Stable | Real-time friction logger |

---

## 5. Summary Statistics

| Category | Count | Status |
|----------|-------|--------|
| Standards | 9 | All stable |
| Templates | 10 | All stable |
| ADRs | 6 | All stable |
| Skills | 30 | All stable |
| Audits | 34 | 28 stable, 6 stubs |
| Runbooks | 5 | All stable |
| Tools | 12 | 10 stable, 2 beta |
| Commands | 9 | All stable |
| **Total Docs** | **94** | |
| **Total Tools** | **12** | |

---

## 6. Maintenance Notes

- Review this inventory during `/cleanup --full`
- Update when adding new files
- Run numbering audit if files added without numbers

---

*Last audit: 2026-01-21*
