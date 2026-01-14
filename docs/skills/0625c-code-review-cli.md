# /code-review - CLI Usage (Manual Steps)

**File:** `docs/skills/0625c-code-review-cli.md`
**Prompt Guide:** [0625p-code-review-prompt.md](0625p-code-review-prompt.md)
**Version:** 2026-01-14

---

## Overview

The `/code-review` skill is Claude-orchestrated with parallel agents. There's no standalone CLI tool, but you can perform manual reviews.

---

## Manual Review Steps

### Get PR Diff

```bash
# View PR changes
gh pr diff 123 --repo OWNER/REPO

# View PR files changed
gh pr view 123 --repo OWNER/REPO --json files

# View staged changes (no PR)
git diff --staged
```

### Review Checklist

#### Security (Critical)
- [ ] Input validation present?
- [ ] SQL/command injection risks?
- [ ] Auth/authz checks?
- [ ] Secrets in code?
- [ ] OWASP Top 10?

#### CLAUDE.md Compliance
- [ ] No `&&` in Bash commands?
- [ ] Absolute paths used?
- [ ] Worktree isolation respected?

#### Bug Detection
- [ ] Null/undefined handling?
- [ ] Race conditions?
- [ ] Edge cases covered?

#### Code Quality
- [ ] SOLID principles?
- [ ] DRY - no duplication?
- [ ] Complexity reasonable?

#### Test Coverage
- [ ] Tests exist for changes?
- [ ] Edge cases tested?
- [ ] Negative tests?

---

## When to Use Manual vs Prompt

| Scenario | Recommendation |
|----------|----------------|
| Quick sanity check | Manual |
| Comprehensive review | Use `/code-review` |
| Security-focused | Use `/code-review --focus security` |
| Multiple reviewers needed | Use `/code-review` (parallel agents) |
| Saving tokens | Manual |

---

## Related Files

- PR comments: `gh pr view 123 --comments`
- Skill definition: `~/.claude/commands/code-review.md`
