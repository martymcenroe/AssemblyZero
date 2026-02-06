# AssemblyZero Command Index

**File:** `docs/skills/0600-command-index.md`
**Version:** 2026-01-14

---

## Overview

Each skill has two documentation files:
- **`c` (CLI)** - Manual steps to run without Claude, saves tokens
- **`p` (Prompt)** - How to use as `/skill` in Claude

---

## Command Reference

| Command | Description | CLI | Prompt |
|---------|-------------|-----|--------|
| `/sync-permissions` | Clean accumulated one-time permissions | [0620c](0620c-sync-permissions-cli.md) | [0620p](0620p-sync-permissions-prompt.md) |
| `/cleanup` | Session cleanup (quick/normal/full) | [0621c](0621c-cleanup-cli.md) | [0621p](0621p-cleanup-prompt.md) |
| `/onboard` | Agent project onboarding | [0622c](0622c-onboard-cli.md) | [0622p](0622p-onboard-prompt.md) |
| `/friction` | Analyze transcripts for permission friction | [0623c](0623c-friction-cli.md) | [0623p](0623p-friction-prompt.md) |
| `/zugzwang` | Real-time permission friction logger | [0624c](0624c-zugzwang-cli.md) | [0624p](0624p-zugzwang-prompt.md) |
| `/code-review` | Parallel multi-agent code review | [0625c](0625c-code-review-cli.md) | [0625p](0625p-code-review-prompt.md) |
| `/commit-push-pr` | Commit, push, and open a PR | [0626c](0626c-commit-push-pr-cli.md) | [0626p](0626p-commit-push-pr-prompt.md) |
| `/test-gaps` | Mine reports for testing gaps | [0627c](0627c-test-gaps-cli.md) | [0627p](0627p-test-gaps-prompt.md) |
| `/quote` | Memorialize Discworld quote to wiki | - | User-level skill |

---

## Quick Reference

### Session Lifecycle

| Phase | Command | Typical Usage |
|-------|---------|---------------|
| Start | `/onboard` | Load project context |
| Resume | `/onboard --refresh` | Reload rules after compact/resume |
| Work | `/zugzwang` | Log permission friction |
| End | `/cleanup` | Commit and close session |

### Maintenance

| Command | Frequency | Purpose |
|---------|-----------|---------|
| `/sync-permissions` | Weekly | Remove permission clutter |
| `/friction` | Weekly | Analyze permission patterns |
| `/test-gaps` | Weekly | Find testing debt |

### Git Workflow

| Command | Purpose |
|---------|---------|
| `/commit-push-pr` | Full commit → push → PR workflow |
| `/code-review` | Multi-agent PR review |

### Special

| Command | Purpose |
|---------|---------|
| `/quote` | Memorialize Discworld quote to Claude's World wiki |

---

## Aliases

| Alias | Resolves To |
|-------|-------------|
| `/closeout` | `/cleanup` |
| `/goodbye` | `/cleanup --quick` |
| `/zz` | `/zugzwang` |

---

## When to Use CLI vs Prompt

| Use CLI When | Use Prompt When |
|--------------|-----------------|
| Saving tokens | Need Claude's help |
| Routine tasks | Complex decisions |
| Quick checks | Want explanations |
| Running from terminal | Working in Claude session |

---

## File Locations

| Type | Location |
|------|----------|
| Canonical implementations | `AssemblyZero/.claude/commands/` |
| User-level stubs | `~/.claude/commands/` |
| CLI tools | `AssemblyZero/tools/` |
| This documentation | `AssemblyZero/docs/skills/` |

---

## Adding New Skills

New skills should:
1. Get a number in the 062x-069x range
2. Have both `c` (CLI) and `p` (Prompt) docs
3. Be added to this index
4. Be added to [0699-skill-instructions-index.md](0699-skill-instructions-index.md)
