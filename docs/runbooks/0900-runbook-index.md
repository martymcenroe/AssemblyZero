# 0900 - Operational Runbooks Index

## Purpose

Quick reference for the user (Marty) on how to run tools, commands, agents, audits, and prompts. Runbooks are "how to run X" documents, distinct from audits (what to check) and standards (what rules to follow).

**Supersedes:** `0008-orchestrator-instructions.md` (deprecated)

## Runbook Categories

| Category | Description | Examples |
|----------|-------------|----------|
| **Audit Runbooks** | How to invoke audits (ultrathink, model selection) | 0901 |
| **Skill Runbooks** | How to use /cleanup, /onboard, /audit, etc. | 0913 |
| **Agent Runbooks** | How to invoke custom agents | (TBD) |
| **Prompt Runbooks** | Standard prompts for common tasks | (TBD) |

## Runbook Index

| ID | Runbook | Trigger | Frequency | Model |
|----|---------|---------|-----------|-------|
| 0901 | [New Project Setup](0901-new-project-setup.md) | Manual | On new project | - |
| 0902 | [Nightly AssemblyZero Audit](0902-nightly-assemblyzero-audit.md) | PowerShell | Nightly | Opus + ultrathink |
| 0903 | [Windows Scheduled Tasks](0903-windows-scheduled-tasks.md) | Reference | - | Sonnet |
| 0904 | [Issue Governance Workflow](0904-issue-governance-workflow.md) | Manual | Per issue | Claude + Gemini |
| 0905 | [Gemini Credentials](0905-gemini-credentials.md) | Manual | On credential issues | - |
| 0906 | [LLD Governance Workflow](0906-lld-governance-workflow.md) | Manual | Per LLD | Claude + Gemini |
| 0907 | [Unified Requirements Workflow](0907-unified-requirements-workflow.md) | Manual | Per issue/LLD | Pluggable |
| 0908 | [The Scout](0908-the-scout-external-intelligence-gathering-workflow.md) | Manual | Research | Sonnet |
| 0909 | [TDD Implementation Workflow](0909-tdd-implementation-workflow.md) | Manual | Per approved LLD | Claude + Gemini |
| 0910 | [Verdict Analyzer](0910-verdict-analyzer---template-improvement-from-gemini-verdicts.md) | Manual | Weekly/ad-hoc | - |
| 0911 | [Dependabot PR Audit](0911-dependabot-pr-audit.md) | Manual | On Dependabot PRs | Sonnet |
| 0912 | [GitHub Projects](0912-github-projects.md) | Reference | - | - |
| 0913 | [Skill Command Reference](0913-skill-command-reference.md) | Reference | - | - |
| 0914 | [Fix Implementation Workflow Archiving](0914-fix-implementation-workflow-should-archive-lld-and-reports-to-done--on-completion.md) | Manual | Post-merge | - |
| 0915 | [Backfill Audit Directories](0915-backfill-audit-directories.md) | Manual | One-time | - |
| 0916 | [Batch Workflow Runner](0916-batch-workflow-runner.md) | Manual | Unattended batch | Claude |
| 0917 | [Audit Skill Runbook](0917-audit-skill-runbook.md) | Manual | Per audit run | Varies |
| 0918 | [Heartbeat Lite Install Guide](0918-heartbeat-lite-install-guide.md) | Manual | One-time | - |
| 0919 | [No-LLD Workflow](0919-no-lld-workflow.md) | Manual | Per hotfix | - |
| 0920 | [Test Gate (Skipped Test Enforcement)](0920-implementation-spec-hard-gate-wrapper-for-skipped-test-enforcement-test-gatepy.md) | Manual | Per impl spec | - |
| 0921 | [Cross-Project Metrics Aggregation](0921-implementation-spec-cross-project-metrics-aggregation-for-assemblyzero-usage-tracking.md) | Manual | Weekly | - |
| 0922 | [N9 Cleanup Node](0922-implementation-spec-n9-cleanup-node---worktree-removal-lineage-archival-and-learning-summary.md) | Manual | Post-merge | - |
| 0923 | [Workflow Recovery and --resume](0923-workflow-recovery.md) | Manual | On interruption | - |
| 0925 | [Agent Token Setup](0925-agent-token-setup.md) | Manual | Quarterly (rotation) | - |
| 0926 | [Branch Protection Setup](0926-branch-protection-setup.md) | Manual | On new repo | - |
| 0927 | [AI CLI Tools Reference](0927-ai-cli-tools-reference.md) | Reference | - | All |

## Model Selection Guide

When running audits or tasks, use the appropriate model to balance cost and capability:

| Model | Cost | Use When |
|-------|------|----------|
| **Opus 4.6** | $$$ | Complex reasoning, architecture, patent review — use `/effort max` |
| **Sonnet 4.6** | $$ | Standard development work, web research, documentation |
| **Haiku 4.5** | $ | Simple automation, metric aggregation, file inventory |
| **Gemini 3.1 Pro** | Free tier | Budget research, large context analysis (1M tokens) |
| **GPT-5.4 (Codex)** | With ChatGPT sub | Security-sensitive execution (native sandbox) |

See `docs/0800-common-audits.md` for per-audit model recommendations.
See [0927](0927-ai-cli-tools-reference.md) for full tool comparison.

## Extended Thinking / Reasoning Effort

Each CLI tool has its own mechanism for increasing reasoning depth:

| Tool | Command | Max Setting |
|------|---------|-------------|
| **Claude Code** | `/effort max` | `max` (unconstrained thinking) |
| **Gemini CLI** | `thinkingLevel` in config | `high` (Deep Think) |
| **Codex CLI** | Reasoning effort setting | `xhigh` |

**Legacy:** "Ultrathink" was the old keyword-based system for Claude Code. It still works but `/effort` is the current mechanism.

**When to use max reasoning:**
- Nightly AssemblyZero self-audits
- Architecture reviews
- Patent claim analysis
- Conflict detection across documents
- Any task requiring multi-step reasoning

**Invocation:** See individual runbooks for specific commands.

## Related Documents

- `CLAUDE.md` - Agent operating procedures
- `docs/0000-GUIDE.md` - AssemblyZero overview and filing system
- `docs/0800-common-audits.md` - Audit index and procedures
- `docs/0008-orchestrator-instructions.md` - (Deprecated, see this index)
