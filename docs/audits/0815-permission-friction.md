# 0824 - Audit: Permission Friction Analysis

## 1. Purpose

Systematically identify and eliminate permission friction from agent workflows. This audit mines session logs for patterns of commands that triggered user approval dialogs, categorizes them, and produces actionable remediation.

**Philosophy:** Every permission prompt is a workflow interruption. If we've approved a command once, we should never be asked again for equivalent commands.

**Relationship to 0808:** This audit is the **diagnostic complement** to 0808 (Permission Permissiveness). 0808 checks if permissions are correct; 0824 finds friction by analyzing actual session behavior.

---

## 2. Friction Categories

### 2.1 Missing Permission Patterns

Commands that should be in the allowlist but aren't.

**Indicators:**
- Agent asked for permission to run a routine command
- Same command type approved multiple times
- Commands matching existing patterns but with slight variations

### 2.2 MSYS Path Conversion (Windows-Specific)

Git Bash on Windows converts Unix-style paths starting with `/` to Windows paths (e.g., `/aws/lambda` becomes `C:/aws/lambda`).

**Indicators:**
- AWS CLI commands failing with path errors
- Commands containing `/aws/`, `/var/`, `/etc/` style paths
- Workarounds using `MSYS_NO_PATHCONV=1` prefix

**Known Affected Commands:**
- `aws logs tail /aws/lambda/...`
- `aws logs describe-log-groups --log-group-name-prefix /aws/...`
- `aws lambda get-function-configuration`
- Any AWS CLI command with ARN or path arguments

### 2.3 Pattern Matching Failures

Commands that don't match allowlist patterns due to structural issues.

**Indicators:**
- `cd /path && command` patterns (banned but still attempted)
- Relative vs absolute path mismatches
- Glob pattern depth issues (`*` vs `**`)

### 2.4 Environment Variable Prefixes

Commands prefixed with environment variables don't match base command patterns.

**Indicators:**
- `VAR=value command` not matching `Bash(command:*)`
- Need explicit `Bash(VAR=value command:*)` patterns

### 2.5 New Tool Introduction

New tools used during sessions that aren't in the allowlist.

**Indicators:**
- First-time use of a new CLI tool
- Upgraded tool versions with different invocation patterns

---

## 3. Audit Procedure

### 3.1 Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--sessions N` | Analyze last N sessions | 5 |
| `--since YYYY-MM-DD` | Analyze sessions since date | (none) |
| `--file PATH` | Analyze specific session log | (none) |

### 3.2 Step 1: Identify Session Logs

```bash
# List available session logs
ls -la /c/Users/mcwiz/Projects/Aletheia/docs/session-logs/
```

Select logs based on parameters or analyze most recent by default.

### 3.3 Step 2: Search for Friction Patterns

Search each session log for friction indicators:

```bash
# Permission-related mentions
grep -in "permission\|approval\|confirm\|allow" {session-log}

# MSYS path conversion mentions
grep -in "MSYS_NO_PATHCONV\|path conversion\|/aws/lambda" {session-log}

# Pattern matching issues
grep -in "cd &&\|doesn't match\|pattern match" {session-log}

# Command retry patterns
grep -in "retry\|again\|workaround" {session-log}
```

### 3.4 Step 3: Categorize Findings

For each friction instance found:

1. **Identify the command** that caused friction
2. **Categorize** using §2 categories
3. **Determine remediation** per §4

### 3.5 Step 4: Cross-Reference Settings

Read current permissions:

```bash
cat /c/Users/mcwiz/Projects/Aletheia/.claude/settings.local.json
```

Compare friction patterns against:
- Allow list entries
- Deny list entries
- Pattern structure (glob depth, prefixes)

### 3.6 Step 5: Generate Remediation Plan

Produce a remediation table (see §5 Output Format).

---

## 4. Remediation Procedures

### 4.1 Add to Allowlist

For missing permission patterns:

```json
"Bash(new-command:*)"
```

**Verify:** Command isn't in deny list, isn't destructive.

### 4.2 Fix MSYS Path Conversion

For Windows path conversion issues:

**Option A (Preferred):** Add MSYS-prefixed pattern
```json
"Bash(MSYS_NO_PATHCONV=1 aws:*)"
```

**Option B:** Add specific command patterns
```json
"Bash(MSYS_NO_PATHCONV=1 aws logs tail:*)",
"Bash(MSYS_NO_PATHCONV=1 aws lambda:*)"
```

**Update Agent Behavior:**
Add to CLAUDE.md Bash Command Rules:
```
- ✅ Prefix AWS CLI commands with `MSYS_NO_PATHCONV=1` on Windows
```

### 4.3 Fix Pattern Matching

For structural issues:

| Issue | Fix |
|-------|-----|
| `cd && command` | Use absolute paths, `git -C`, or tool-specific flags |
| `./tools/*` not matching subdirs | Change to `./tools/**:*` |
| Relative path mismatch | Use absolute paths |

### 4.4 Add Environment Variable Prefix

For env-prefixed commands:

```json
"Bash(ENV_VAR=value command:*)"
```

**Example:** `ESLINT_USE_FLAT_CONFIG=true npx eslint`

### 4.5 Update Command Patterns

For commands that can be restructured:

| Friction Pattern | Preferred Pattern |
|-----------------|-------------------|
| `cd /path && git status` | `git -C /path status` |
| `cd /path && poetry run` | `poetry -C /path run` |
| `cd /path && npm run` | Use absolute script path |

### 4.6 Auto-Fix (Default Behavior)

**This audit auto-fixes friction patterns rather than just reporting them.**

When friction is identified:

```markdown
Auto-fix procedure:
1. For missing permission patterns:
   - Read .claude/settings.local.json
   - Add pattern to "allow" array
   - Write updated file
   - Log: "Added 'Bash({pattern}:*)' to allowlist"

2. For MSYS path conversion issues:
   - Add MSYS-prefixed pattern to allowlist
   - Update CLAUDE.md Bash rules if pattern is new category
   - Log: "Added MSYS_NO_PATHCONV pattern for {command}"

3. For glob depth issues (./tools/* not matching subdirs):
   - Update pattern from `*` to `**`
   - Log: "Changed '{old}' to '{new}' for recursive matching"
```

**Auto-fix safety checks:**

| Check | Action if Fails |
|-------|-----------------|
| Command in deny list? | Skip auto-fix, log as unresolvable |
| Structural issue (&&, \|)? | Skip auto-fix, agent behavior issue |
| Security-sensitive path? | Skip auto-fix, flag for manual review |

**Cannot auto-fix (per §6.2):**
- Edits to `.claude/settings.local.json` itself (security feature)
- Pipe and chain operators (intentionally blocked)
- Novel destructive command patterns

---

## 5. Output Format

### 5.1 Friction Analysis Report

```markdown
## Permission Friction Analysis - YYYY-MM-DD

**Scope:** [N sessions / since DATE]
**Session Logs Analyzed:**
- docs/session-logs/YYYY-MM-DD.md

### Findings by Category

#### Missing Permission Patterns
| Command | Occurrences | Session(s) |
|---------|-------------|------------|
| `example-command` | 3 | 2026-01-05, 2026-01-06 |

#### MSYS Path Conversion
| Command | Issue | Session(s) |
|---------|-------|------------|
| `aws logs tail /aws/...` | Path converted to C:/ | 2026-01-05 |

#### Pattern Matching Failures
| Pattern Attempted | Why Failed | Session(s) |
|-------------------|-----------|------------|
| `cd /path && git` | Chaining blocked | 2026-01-04 |

### Remediation Plan

| Finding | Remediation | Priority |
|---------|-------------|----------|
| `aws` without MSYS prefix | Add `Bash(MSYS_NO_PATHCONV=1 aws:*)` | HIGH |
| Missing `tool-name` | Add `Bash(tool-name:*)` | MEDIUM |

### Immediate Actions
1. [List specific changes to settings.local.json]
2. [List updates to CLAUDE.md if needed]
```

---

## 6. Known Friction Patterns (Historical)

Patterns discovered and remediated, for reference:

### 6.1 Resolved

| Date | Pattern | Remediation | Commit |
|------|---------|-------------|--------|
| 2025-12-29 | `cd && poetry run` | Use absolute paths | a65d7fa |
| 2025-12-29 | 7 redundant permissions | Cleaned up | f9e5794 |
| 2026-01-05 | `./tools/*` not recursive | Changed to `./tools/**:*` | (session) |
| 2026-01-05 | `MSYS_NO_PATHCONV=1 aws logs tail` | Added specific pattern | (session) |

### 6.2 Unresolvable

| Pattern | Reason |
|---------|--------|
| `.claude/settings.local.json` edits | System-level protection (security feature) |
| Pipes (`\|`) and chains (`&&`) | Intentionally blocked per CLAUDE.md |

---

## 7. Audit Schedule

**Trigger:** Run after any session with noticeable friction (multiple approval prompts).

**Recommended:** Weekly review of session logs during /full-cleanup.

---

## 8. Audit Record

| Date | Auditor | Sessions Analyzed | Findings | Remediations Applied |
|------|---------|-------------------|----------|---------------------|
| | | | | |

---

## 9. References

- docs/0808-audit-permission-permissiveness.md - Permission policy audit
- .claude/settings.local.json - Permission implementation
- CLAUDE.md - Bash command rules
- docs/session-logs/ - Historical session data
