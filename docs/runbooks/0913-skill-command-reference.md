# 0913 - Skill Command Reference

## Purpose

Quick reference for the orchestrator (Marty) on all available `/skill` commands. This is the runbook version - for detailed CLI/prompt documentation, see `docs/skills/`.

---

## Command Quick Reference

| Command | Description | When to Use |
|---------|-------------|-------------|
| `/onboard` | Load project context | Start of session |
| `/onboard --refresh` | Reload rules after compaction | After context resume |
| `/cleanup` | Session cleanup | End of session |
| `/cleanup --quick` | Quick cleanup (alias: `/goodbye`) | Fast exit |
| `/commit-push-pr` | Full git workflow | Ready to submit code |
| `/code-review` | Multi-agent PR review | Before merge |
| `/sync-permissions` | Clean permission clutter | Weekly maintenance |
| `/friction` | Analyze permission patterns | Weekly analysis |
| `/zugzwang` | Real-time permission logger | During active work |
| `/test-gaps` | Find testing debt | Weekly or post-implementation |
| `/audit` | Run 08xx audit suite | Scheduled or ad-hoc |
| `/quote` | Memorialize Discworld quote | After significant milestone |

---

## Session Lifecycle

```
Start Session:
  /onboard              → Load project context

During Work:
  /zugzwang             → Log permission friction (optional)
  /quote                → Memorialize a Discworld quote (optional)

Ready to Submit:
  /commit-push-pr       → Commit, push, create PR
  /code-review          → Get multi-agent review

End Session:
  /cleanup              → Full cleanup
  /cleanup --quick      → Fast exit (alias: /goodbye)
```

---

## Maintenance Commands

| Command | Frequency | Purpose |
|---------|-----------|---------|
| `/sync-permissions` | Weekly | Remove accumulated one-time permissions |
| `/friction` | Weekly | Analyze session transcripts for friction patterns |
| `/test-gaps` | Weekly | Mine reports for untested code paths |
| `/audit` | Nightly/weekly | Run compliance and quality audits |

---

## Special Commands

### `/quote` - Discworld Quote Memorialization

Auto-detects the most recent Discworld quote from conversation and memorializes it to `wiki/Claudes-World.md`.

**When appropriate:**
- Significant task completed
- Brilliant non-code discussion concludes
- Moment calls for philosophical perspective

**Not appropriate:**
- During active coding/debugging
- Routine operations
- When busy with urgent work

**Quote types:**
- **In-character**: Claude speaking as Discworld persona (Vetinari, Vimes, DEATH)
- **Direct**: Actual Pratchett quotes with book attribution

---

## Aliases

| Alias | Resolves To |
|-------|-------------|
| `/closeout` | `/cleanup` |
| `/goodbye` | `/cleanup --quick` |
| `/zz` | `/zugzwang` |

---

## Detailed Documentation

For CLI steps (manual execution) and prompt details, see:
- **Index**: `docs/skills/0600-command-index.md`
- **Full docs**: `docs/skills/06XXc-*-cli.md` and `docs/skills/06XXp-*-prompt.md`

---

## Related Runbooks

| Runbook | Relevance |
|---------|-----------|
| [0904 Issue Governance](0904-issue-governance-workflow.md) | Uses `/commit-push-pr` |
| [0906 LLD Governance](0906-lld-governance-workflow.md) | Uses `/code-review` |
| [0902 Nightly Audit](0902-nightly-assemblyzero-audit.md) | Uses `/audit` |
