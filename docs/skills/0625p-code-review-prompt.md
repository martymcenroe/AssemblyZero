# /code-review - Prompt Usage

**File:** `docs/skills/0625p-code-review-prompt.md`
**CLI Guide:** [0625c-code-review-cli.md](0625c-code-review-cli.md)
**Version:** 2026-01-14

---

## Quick Reference

```
/code-review 123              # Review PR #123
/code-review --files src/     # Review specific files
/code-review 123 --focus security    # Security-only
/code-review 123 --focus quality     # Quality-only
/code-review --help           # Show help
```

---

## When to Use This Skill

| Scenario | Use Skill? |
|----------|------------|
| PR review needed | **Skill** - comprehensive |
| Quick sanity check | **CLI** - manual |
| Security audit | **Skill --focus security** |
| Multiple perspectives | **Skill** - 5 parallel agents |
| Saving tokens | **CLI** |

---

## What It Does

Runs 5 parallel review agents:

| Agent | Model | Focus |
|-------|-------|-------|
| Security Reviewer | Opus | Injection, auth, data exposure |
| CLAUDE.md Compliance | Sonnet | AssemblyZero rule violations |
| Bug Detector | Sonnet | Null handling, race conditions |
| Code Quality | Sonnet | SOLID, DRY, complexity |
| Test Coverage | Sonnet | Missing tests, coverage gaps |

---

## Arguments

| Argument | Description |
|----------|-------------|
| `PR#` | Review specific pull request |
| `--files path` | Review specific files |
| `--focus security` | Security agents only |
| `--focus quality` | Quality agents only |
| `--focus all` | All agents (default) |

---

## Focus Modes

### --focus security
Runs only Agent 1 (Security Reviewer - Opus)

### --focus quality
Runs only Agents 4-5 (Code Quality, Test Coverage)

### --focus all (default)
Runs all 5 agents in parallel

---

## Confidence Filtering

| Confidence | Action |
|------------|--------|
| >= 0.8 | Include in report |
| 0.5 - 0.8 | Include with "Verify manually" |
| < 0.5 | Exclude (too uncertain) |

---

## Example Session

```
User: /code-review 123

Claude: Running parallel code review on PR #123...

[Spawns 5 agents]

# Code Review: PR #123 - Add user authentication

## Summary
Generally solid implementation with one security concern.

## Security Findings
### CRITICAL
- [ ] Password stored in plain text (confidence: 0.95)
  - File: src/auth.py:45
  - Recommendation: Use bcrypt hashing

## CLAUDE.md Compliance
- [ ] Line 78: Uses && in Bash command

## Potential Bugs
- [ ] Null check missing for user.email (confidence: 0.82)

## Code Quality
- No issues found

## Test Coverage
- [ ] Missing test for invalid password case

## Recommendations
1. [CRITICAL] Hash passwords before storage
2. [HIGH] Add null check for user.email
3. [MEDIUM] Add negative test cases
```

---

## Output Format

```markdown
# Code Review: [PR Title or Files]

## Summary
[1-2 sentence assessment]

## Security Findings
### CRITICAL / HIGH / MEDIUM
- [ ] Finding (confidence: X.X)

## CLAUDE.md Compliance
- [ ] Violation description

## Potential Bugs
- [ ] Bug description (confidence: X.X)

## Code Quality
- [ ] Issue description

## Test Coverage
- [ ] Missing coverage

## Recommendations
1. [Priority] Action item
```

---

## Source of Truth

**Skill definition:** `~/.claude/commands/code-review.md`
