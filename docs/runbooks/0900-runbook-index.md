# 0900 - Operational Runbooks Index

## Purpose

Quick reference for the orchestrator (Marty) on how to run tools, commands, agents, audits, and prompts. Runbooks are "how to run X" documents, distinct from audits (what to check) and standards (what rules to follow).

**Supersedes:** `0008-orchestrator-instructions.md` (deprecated)

## Runbook Categories

| Category | Description | Examples |
|----------|-------------|----------|
| **Audit Runbooks** | How to invoke audits (ultrathink, model selection) | 0901 |
| **Skill Runbooks** | How to use /cleanup, /onboard, /audit, etc. | (TBD) |
| **Agent Runbooks** | How to invoke custom agents | (TBD) |
| **Prompt Runbooks** | Standard prompts for common tasks | (TBD) |

## Runbook Index

| ID | Runbook | Trigger | Frequency | Model |
|----|---------|---------|-----------|-------|
| 0901 | [New Project Setup](0901-new-project-setup.md) | Manual | On new project | - |
| 0902 | [Nightly AgentOS Audit](0902-nightly-agentos-audit.md) | PowerShell | Nightly | Opus + ultrathink |
| 0903 | [Windows Scheduled Tasks](0903-windows-scheduled-tasks.md) | Reference | - | Sonnet |
| 0904 | [Issue Governance Workflow](0904-issue-governance-workflow.md) | Manual | Per issue | Claude + Gemini |
| 0905 | [Gemini Credentials](0905-gemini-credentials.md) | Manual | On credential issues | - |
| 0906 | [LLD Governance Workflow](0906-lld-governance-workflow.md) | Manual | Per LLD | Claude + Gemini |
| 0907 | [Unified Requirements Workflow](0907-unified-requirements-workflow.md) | Manual | Per issue/LLD | Pluggable |
| 0908 | [The Scout](0908-the-scout-external-intelligence-gathering-workflow.md) | Manual | Research | Sonnet |
| 0909 | [TDD Implementation Workflow](0909-tdd-implementation-workflow.md) | Manual | Per approved LLD | Claude + Gemini |
| 0910 | [Verdict Analyzer](0910-verdict-analyzer---template-improvement-from-gemini-verdicts.md) | Manual | Weekly/ad-hoc | - |

## Model Selection Guide

When running audits or tasks, use the appropriate model to balance cost and capability:

| Model | Cost | Use When |
|-------|------|----------|
| **Opus** | $$$ | Complex reasoning, architecture decisions, ultrathink mode |
| **Sonnet** | $$ | Standard development work, web research, documentation |
| **Haiku** | $ | Simple automation, metric aggregation, file inventory |

See `docs/0800-common-audits.md` for per-audit model recommendations.

## Ultrathink Mode

"Ultrathink" is the term we use to invoke extended thinking. This is done via PowerShell by the orchestrator and provides deeper analysis for complex audits.

**When to use ultrathink:**
- Nightly AgentOS self-audits
- Architecture reviews
- Conflict detection across documents
- Any task requiring multi-step reasoning

**Invocation:** See individual runbooks for specific commands.

## Related Documents

- `CLAUDE.md` - Agent operating procedures
- `docs/0000-GUIDE.md` - AgentOS overview and filing system
- `docs/0800-common-audits.md` - Audit index and procedures
- `docs/0008-orchestrator-instructions.md` - (Deprecated, see this index)
