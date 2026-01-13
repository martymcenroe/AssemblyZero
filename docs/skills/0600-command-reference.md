# AgentOS Command Reference

Complete reference for all AgentOS skills (slash commands). Each command starts on a new page for easy printing.

**Location:** Canonical implementations live in `AgentOS/.claude/commands/`. User-level stubs in `~/.claude/commands/` delegate to the canonical versions.

**Version:** 2026-01-13

---

## Table of Contents

| Command | Description | Page |
|---------|-------------|------|
| `/cleanup` | Session cleanup with quick/normal/full modes | 2 |
| `/code-review` | Parallel multi-agent code review | 5 |
| `/commit-push-pr` | Commit, push, and open a PR | 9 |
| `/friction` | Analyze session transcripts for permission friction | 11 |
| `/onboard` | Agent onboarding (quick/full mode) | 15 |
| `/sync-permissions` | Clean accumulated one-time permissions | 17 |
| `/test-gaps` | Mine reports for testing gaps | 19 |
| `/zugzwang` | Real-time permission friction logger | 22 |

<div style="page-break-after: always;"></div>

# /cleanup

**Aliases:** `/closeout`, `/goodbye`

**Description:** Session cleanup with quick/normal/full modes

**Usage:** `/cleanup [--help] [--quick|--normal|--full] [--no-auto-delete]`

---

## Arguments

| Argument | Description |
|----------|-------------|
| `--help` | Show help message and exit |
| `--quick` | Minimal cleanup (~2 min) - appends session log, does NOT commit |
| `--normal` | Standard cleanup (~5 min) - typical session end (default) |
| `--full` | Comprehensive cleanup (~12 min) - after features, before breaks |
| `--no-auto-delete` | Skip automatic deletion of orphaned branches |

---

## Mode Comparison

| Check | Quick | Normal | Full |
|-------|:-----:|:------:|:----:|
| Git status | YES | YES | YES |
| Branch list | YES | YES | YES |
| Open PRs | YES | YES | YES |
| **Session log append** | YES | YES | YES |
| **Commit & push** | | YES | YES |
| Stash list | | YES | YES |
| Worktree list | | YES | YES |
| **Auto-delete orphans** | | YES | YES |
| Inventory audit | | | YES |

---

## Project Detection

Detects the current project from working directory:
- Extracts project name from path (e.g., `/c/Users/mcwiz/Projects/Aletheia` → `Aletheia`)
- Handles worktree paths (e.g., `Aletheia-123` → project is `Aletheia`)

**Known Projects:**

| Project | GitHub Repo |
|---------|-------------|
| Aletheia | martymcenroe/Aletheia |
| AgentOS | martymcenroe/AgentOS |
| Talos | martymcenroe/Talos |
| claude-code | anthropics/claude-code |
| maintenance | (none) |

---

## Session Log Format

Creates/appends to `docs/session-logs/{DATE}.md`:

```markdown
## Session: {SESSION_NAME}
- **Mode:** {MODE} cleanup
- **Model:** Claude Sonnet 4
- **Summary:** [brief description]
- **Next:** Per user direction
```

---

## Philosophy

**Quick mode:** Record what happened (session log), but don't commit. Changes accumulate until a normal/full cleanup commits them.

<div style="page-break-after: always;"></div>

# /code-review

**Description:** Parallel multi-agent code review (PR or staged changes)

**Usage:** `/code-review [PR#] [--files path1 path2...] [--focus security|quality|all]`

---

## Arguments

| Argument | Description |
|----------|-------------|
| `PR#` | Review a specific pull request (e.g., `123`) |
| `--files` | Review specific files instead of PR |
| `--focus security` | Run only security-focused agents |
| `--focus quality` | Run only code quality agents |
| `--focus all` | Run all agents (default) |

---

## Examples

```
/code-review 123              # Review PR #123 with all agents
/code-review --files src/main.py  # Review specific file
/code-review 123 --focus security # Security-only review of PR
```

---

## Architecture

**5 parallel agents with confidence-based filtering:**

| Agent | Model | Focus Area |
|-------|-------|------------|
| Security Reviewer | Opus | Injection, auth flaws, data exposure |
| CLAUDE.md Compliance | Sonnet | AgentOS rule violations |
| Bug Detector | Sonnet | Null handling, race conditions, edge cases |
| Code Quality | Sonnet | SOLID, DRY, complexity |
| Test Coverage | Sonnet | Missing tests, coverage gaps |

---

## Confidence Filtering

| Confidence | Action |
|------------|--------|
| >= 0.8 | Include in report (high confidence) |
| 0.5 - 0.8 | Include with caveat "Verify manually" |
| < 0.5 | Exclude from report (too uncertain) |

---

## Focus Modes

**--focus security:** Run only Agent 1 (Security Reviewer)

**--focus quality:** Run only Agents 4-5 (Code Quality, Test Coverage)

**--focus all (default):** Run all 5 agents in parallel

---

## Output Format

```markdown
# Code Review: [PR Title or Files]

## Summary
[1-2 sentence overall assessment]

## Security Findings
### CRITICAL
- [ ] Finding (confidence: X.X)

## CLAUDE.md Compliance
- [ ] Violation: ...

## Potential Bugs
- [ ] Bug: ... (confidence: X.X)

## Code Quality
- [ ] Issue: ...

## Test Coverage
- [ ] Missing: ...

## Recommendations
1. [Prioritized action items]
```

<div style="page-break-after: always;"></div>

# /commit-push-pr

**Description:** Commit, push, and open a PR

**Usage:** `/commit-push-pr [--title "..."] [--draft]`

---

## Arguments

| Argument | Description |
|----------|-------------|
| `--title` | Custom PR title |
| `--draft` | Create as draft PR |

---

## Workflow Steps

### Step 1: Create Branch (if on main)
If current branch is `main` or `master`, creates feature branch.

### Step 2: Stage Changes
```bash
git add .
```

### Step 3: Create Commit
Uses conventional commit format:
- Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
- Keeps first line under 72 characters
- Adds body if changes are complex
- Includes Co-Authored-By trailer

### Step 4: Push to Remote
```bash
git push -u origin HEAD
```

### Step 5: Create Pull Request
```bash
gh pr create --title "type: brief description" --body "..."
```

### Step 6: Report
Outputs PR URL and summary.

---

## Rules

- One command per Bash call (no `&&` or `|`)
- Use `git -C /path` if not in repo root
- Respect .gitignore
- Don't commit secrets or credentials
- Ask before force-pushing

---

## Notes

- Works in any git repository
- Detects GitHub repo automatically via `gh repo view`
- If not a GitHub repo, stops after push

<div style="page-break-after: always;"></div>

# /friction

**Description:** Analyze session transcripts for permission friction (15-30 min)

**Usage:** `/friction [--help] [--sessions N] [--since YYYY-MM-DD]`

---

## Arguments

| Argument | Description |
|----------|-------------|
| `--help` | Show help message and exit |
| `--sessions N` | Analyze last N session files (default: 3) |
| `--since YYYY-MM-DD` | Analyze sessions since date |

---

## Examples

```
/friction                     # Analyze last 3 session transcripts
/friction --sessions 5        # Analyze last 5 sessions
/friction --since 2026-01-05  # Analyze sessions since Jan 5
```

---

## What It Does

1. Searches Claude Code's verbatim session transcripts (NOT agent-written summaries)
2. Finds tool calls that resulted in errors or permission prompts
3. Categorizes findings (MISSING, MSYS, PATTERN, ENV_PREFIX, DENIED)
4. Generates remediation plan with specific settings.local.json changes

---

## Friction Categories

| Category | Description | Remediation |
|----------|-------------|-------------|
| **MISSING** | Command not in allowlist | Add `Bash(cmd:*)` to allow |
| **MSYS** | Windows path conversion | Add `MSYS_NO_PATHCONV=1` prefix |
| **PATTERN** | Command structure blocked | Change to allowed pattern |
| **ENV_PREFIX** | Env var prefix not allowed | Add `Bash(VAR=val cmd:*)` |
| **DENIED** | Intentionally blocked | Document why, no action needed |

---

## Permission-Safe Execution

This skill uses ONLY these tools (no permission prompts):

| Tool | Why Safe |
|------|----------|
| **Glob** | No path restrictions |
| **Grep** | No path restrictions, uses ripgrep |
| **Read** | System allows reading .claude paths |

---

## Output Format

```markdown
## Permission Friction Analysis - YYYY-MM-DD

**Project:** {PROJECT}
**Scope:** Analyzed N session transcripts from [date range]

### Findings Summary

| Category | Count | Priority |
|----------|-------|----------|
| MISSING | N | HIGH/MED/LOW |
| MSYS | N | ... |

### Remediation Actions

#### Add to settings.local.json allow list:
"Bash(new-pattern:*)",
```

---

## Relationship to /zugzwang

- `/zugzwang` = live capture during work
- `/friction` = forensic analysis after sessions

They are complementary.

<div style="page-break-after: always;"></div>

# /onboard

**Description:** Agent onboarding (quick/full mode)

**Usage:** `/onboard [--help] [--quick | --full]`

---

## Arguments

| Flag | Effect |
|------|--------|
| `--help` | Show help message and exit |
| `--quick` | Read digest only, report age (~$0.02, 30s) - for simple tasks |
| `--full` | Full onboarding (~$0.35, 2min) - for complex work (default) |

---

## Examples

```
/onboard --help   # Show help
/onboard --quick  # Quick onboard for status check
/onboard --full   # Full onboard for feature work
/onboard          # Same as --full
```

---

## Mode Comparison

| Mode | Cost | Time | Use Case |
|------|------|------|----------|
| `--quick` | ~$0.02 | ~30s | Simple tasks, status checks |
| `--full` | ~$0.35 | ~2min | Complex features, audits |

---

## Quick Mode

Reads only essential files:
1. `CLAUDE.md` in project root
2. `docs/0000-GUIDE.md` (if exists)
3. Most recent session log entry
4. Reports readiness

**Model hint:** Can use Haiku (~66% cost savings)

---

## Full Mode

### Step 1: Core Documentation (parallel reads)
- `CLAUDE.md` - Project rules
- `docs/0000-GUIDE.md` - System philosophy
- `docs/0001-*.md` - Architecture

### Step 2: Current State
- Check for sprint focus doc
- Read most recent session log (last 3 entries)
- Check open issues: `gh issue list --state open --limit 10`

### Step 3: Project-Specific Setup
- Run `tools/generate_onboard_digest.py` if exists
- Read `docs/0000b-ONBOARD-DIGEST.md` if exists

### Step 4: Acknowledge
Reports project name, current focus, priorities, and readiness.

---

## Fallback for Unknown Projects

If project lacks AgentOS documentation:
1. Read CLAUDE.md (if exists)
2. Read README.md
3. List top-level directories
4. Report: "Project {NAME} - minimal onboarding complete. No AgentOS docs found."

<div style="page-break-after: always;"></div>

# /sync-permissions

**Description:** Clean accumulated one-time permissions from settings

**Usage:** `/sync-permissions [--audit | --clean | --quick | --merge-up] [PROJECT]`

---

## Background

Every time you approve a permission prompt, that exact command gets saved:

```json
"Bash(git -C /c/Users/mcwiz/Projects/Aletheia commit -m \"docs: cleanup 2026-01-10\")"
```

These are useless clutter. The tool removes them while keeping useful patterns like `Bash(git -C:*)`.

---

## Usage Examples

```
/sync-permissions                      # Audit current project
/sync-permissions --audit Aletheia     # Audit specific project
/sync-permissions --clean              # Remove one-time permissions (dry-run first)
/sync-permissions --quick              # Fast check (for cleanup integration)
/sync-permissions --merge-up           # Pull unique patterns from all projects into master
```

---

## Modes

| Argument | Mode |
|----------|------|
| (none) or `--audit` | Read-only analysis |
| `--clean` | Remove one-time permissions |
| `--quick` | Fast check (exit 0=OK, 1=needs cleaning) |
| `--merge-up` | Collect unique patterns from projects into master |

---

## What Gets Removed vs Kept

**REMOVED (one-time clutter):**
- Specific git commits: `git commit -m "specific message"`
- Specific PR creations with bodies
- Specific push commands: `git push -u origin specific-branch`
- Commands on worktrees: `git -C /path/Aletheia-123 ...`

**KEPT (reusable patterns):**
- Wildcards: `Bash(git -C:*)`, `Bash(poetry:*)`
- Skills: `Skill(cleanup)`, `Skill(onboard)`
- Web tools: `WebFetch`, `WebSearch`
- File patterns: `Read(C:\Users\mcwiz\Projects\**)`

---

## Source of Truth

This skill calls: `AgentOS/tools/agentos-permissions.py`

**If the tool needs fixing, fix it in AgentOS - not locally.**

<div style="page-break-after: always;"></div>

# /test-gaps

**Description:** Mine reports for testing gaps and automation opportunities

**Usage:** `/test-gaps [--full] [--file path/to/report.md]`

---

## Arguments

| Argument | Description |
|----------|-------------|
| (none) | Quick scan - recent reports only |
| `--full` | Comprehensive scan - all reports |
| `--file` | Analyze specific report file |

---

## Gap Indicators

| Pattern | Category | Priority |
|---------|----------|----------|
| "manual testing" / "tested manually" | Automation opportunity | HIGH |
| "not tested" / "untested" / "skipped" | Known gap | CRITICAL |
| "deferred" / "future work" | Planned debt | MEDIUM |
| "edge case" + "not covered" | Missing coverage | HIGH |
| "happy path only" | Missing negative tests | HIGH |
| "works on my machine" | Environment-specific gap | MEDIUM |
| "hard to test" / "difficult to mock" | Architecture issue | LOW |
| "TODO" / "FIXME" in test code | Incomplete test | HIGH |

---

## Output Format

```markdown
# Test Gap Analysis

**Scan type:** [Quick/Full/Single file]
**Reports analyzed:** [count]
**Date:** [YYYY-MM-DD]

## Critical Gaps (No tests exist)

| File | Gap Description | Source | Effort |
|------|-----------------|--------|--------|
| `path/to/file.js` | [description] | Report #XXX | [Low/Med/High] |

## Automation Opportunities

| File | Current Testing | Automation Benefit | Source |
|------|-----------------|-------------------|--------|
| `path/to/file.js` | Manual login flow | Reduce regression time | Report #XXX |

## Recommended Actions

1. **[CRITICAL]** [First priority action]
2. **[HIGH]** [Second priority action]

## Issues to Create

- [ ] `test(unit): Add tests for [file]`
```

---

## Notes

- This skill is READ-ONLY - analyzes but does not modify files
- Creates issues only when user confirms
- Run periodically (weekly recommended) to prevent test debt

<div style="page-break-after: always;"></div>

# /zugzwang

**Aliases:** `/zz`

**Description:** Real-time permission friction logger - track every permission prompt

**Usage:** `/zugzwang [--help] [--tail N] [--clear] [--review] [--blast]`

---

## Arguments

| Argument | Description |
|----------|-------------|
| `--help` | Show help message and exit |
| `--tail N` | Show last N log entries (default: 10) |
| `--clear` | Clear the log file and start fresh |
| `--review` | Show full log with analysis, do NOT clear |
| `--blast` | Post to GitHub #17637, then clear log |

---

## Examples

```
/zugzwang          # Activate logger, show recent entries
/zz                # Same as /zugzwang
/zugzwang --tail 20    # Show last 20 entries
/zugzwang --clear      # Clear log file
/zugzwang --review     # Review all entries without clearing
/zugzwang --blast      # Post to GitHub and clear
```

---

## Log Location

`C:\Users\mcwiz\Projects\AgentOS\logs\zugzwang.log`

---

## Event Types

| Event | Description |
|-------|-------------|
| `PATTERN_RISKY` | Commands with `|`, `&&`, `;` before execution |
| `TOOL_BLOCKED` | Tool calls blocked by hooks/permissions |
| `TOOL_DENIED` | User denied permission prompts |
| `TOOL_APPROVED` | User approved permission prompts |

---

## Log Entry Format

```
TIMESTAMP | EVENT_TYPE | agent:MODEL | tool:TOOL | context:"DESCRIPTION" | status:STATUS
```

| Field | Values |
|-------|--------|
| TIMESTAMP | `yyyy-MM-ddTHH:mm:ss` |
| EVENT_TYPE | `PATTERN_RISKY`, `TOOL_BLOCKED`, `TOOL_DENIED`, `TOOL_APPROVED` |
| agent | `opus`, `sonnet`, `haiku` |
| tool | `Bash`, `Edit`, `Write`, `unknown` |
| status | `pre-execution`, `blocked`, `denied`, `confirmed` |

---

## Why "zugzwang"?

Chess term: a position where any move worsens your situation. Perfect metaphor for permission friction - you're stuck waiting for approval, unable to proceed.

---

## Relationship to /friction

- `/zugzwang` = live capture during work
- `/friction` = forensic analysis after sessions

They are complementary. Future enhancement: `/friction` could read zugzwang.log to correlate.

<div style="page-break-after: always;"></div>

# Appendix: Quick Reference

## All Commands Summary

| Command | Alias | Purpose | Time |
|---------|-------|---------|------|
| `/cleanup` | `/closeout`, `/goodbye` | Session cleanup | 2-12 min |
| `/code-review` | | Multi-agent code review | ~1 min |
| `/commit-push-pr` | | Git workflow automation | ~30 sec |
| `/friction` | | Permission friction analysis | 15-30 min |
| `/onboard` | | Agent project onboarding | 30s-2 min |
| `/sync-permissions` | | Permission cleanup | ~1 min |
| `/test-gaps` | | Test coverage analysis | 2-5 min |
| `/zugzwang` | `/zz` | Real-time friction logging | Continuous |

---

## File Locations

| Type | Location |
|------|----------|
| Canonical implementations | `AgentOS/.claude/commands/` |
| User-level stubs | `~/.claude/commands/` |
| Permission settings | `~/.claude/settings.local.json` |
| Project permissions | `<project>/.claude/settings.local.json` |
| Zugzwang log | `AgentOS/logs/zugzwang.log` |
| Session transcripts | `~/.claude/projects/C--Users-mcwiz-Projects-{PROJECT}/` |

---

## Common Workflows

**Starting a session:**
```
/onboard --quick    # Simple task
/onboard            # Complex work
```

**During work:**
```
/zugzwang           # Activate friction logging
```

**Ending a session:**
```
/cleanup --quick    # Just log, no commit
/cleanup            # Normal cleanup
/cleanup --full     # Comprehensive cleanup
```

**Periodic maintenance:**
```
/sync-permissions --clean     # Remove permission clutter
/friction --sessions 5        # Analyze recent friction
/test-gaps --full             # Find test debt
```
