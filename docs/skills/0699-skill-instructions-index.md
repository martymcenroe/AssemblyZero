# 0600 - Skill Instructions Index

## Purpose

This document indexes all skill documentation in the `06xx` namespace.

**Convention:** Each skill has two documents:
- **`c` suffix** - CLI usage (manual steps, saves tokens)
- **`p` suffix** - Prompt usage (in Claude session)

---

## Master Index

**[0600-command-index.md](0600-command-index.md)** - Quick reference for all commands

---

## 060x: Review & Quality Skills

| File | Purpose | Status |
|:-----|:--------|:-------|
| [0601-gemini-lld-review.md](0601-gemini-lld-review.md) | LLD review procedure (Gemini) | Active |
| [0602-gemini-dual-review.md](0602-gemini-dual-review.md) | Claude-Gemini dual review | Planned |

---

## 062x: Maintenance Skills

| Command | CLI Doc | Prompt Doc | Status |
|:--------|:--------|:-----------|:-------|
| `/sync-permissions` | [0620c](0620c-sync-permissions-cli.md) | [0620p](0620p-sync-permissions-prompt.md) | Active |
| `/cleanup` | [0621c](0621c-cleanup-cli.md) | [0621p](0621p-cleanup-prompt.md) | Active |
| `/onboard` | [0622c](0622c-onboard-cli.md) | [0622p](0622p-onboard-prompt.md) | Active |
| `/friction` | [0623c](0623c-friction-cli.md) | [0623p](0623p-friction-prompt.md) | Active |
| `/code-review` | [0625c](0625c-code-review-cli.md) | [0625p](0625p-code-review-prompt.md) | Active |
| `/commit-push-pr` | [0626c](0626c-commit-push-pr-cli.md) | [0626p](0626p-commit-push-pr-prompt.md) | Active |
| `/test-gaps` | [0627c](0627c-test-gaps-cli.md) | [0627p](0627p-test-gaps-prompt.md) | Active |
| `/quote` | - | User-level (`~/.claude/commands/quote.md`) | Active |

---

## 061x: Audit Skills

| File | Purpose | Status |
|:-----|:--------|:-------|
| Reserved for audit execution procedures | | Future |

---

## Naming Convention

```
06XXc-skill-name-cli.md      # CLI usage (manual steps)
06XXp-skill-name-prompt.md   # Prompt usage (in Claude)
```

**Examples:**
- `0620c-sync-permissions-cli.md` - How to run permissions tool from terminal
- `0620p-sync-permissions-prompt.md` - How to use `/sync-permissions` in Claude

---

## Adding New Skills

1. Choose the next available number in appropriate range
2. Create both `c` and `p` docs
3. Add to this index
4. Add to [0600-command-index.md](0600-command-index.md)
5. Update `docs/0003-file-inventory.md`

---

## History

| Date | Change |
|------|--------|
| 2026-01-08 | Created. Moved 0109-gemini-lld-review-procedure.md to 0601. |
| 2026-01-09 | Added 0602-skill-gemini-dual-review.md. |
| 2026-01-14 | Restructured: Added c/p convention for CLI vs Prompt docs. |
| 2026-01-14 | Added 0620-0627 skill documentation (c/p pairs for all commands). |
| 2026-01-14 | Added --refresh option to /onboard (post-compact/resume rule reload). |
