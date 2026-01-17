# Implementation Report: Issue #5 - Permission Propagation Tool

**Issue:** [#5](https://github.com/martymcenroe/AgentOS/issues/5)
**Commit:** `5d76523`
**Date:** 2026-01-12
**Status:** Complete

---

## Summary

Implemented `agentos-permissions.py`, a tool that manages Claude Code permissions across master (user-level) and project-level settings files. The tool identifies and removes one-time "session vend" permissions while preserving reusable patterns, and can merge unique patterns from projects into the master configuration.

---

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `tools/agentos-permissions.py` | Created | Core permission management tool (798 lines) |
| `docs/skills/0620c-sync-permissions-cli.md` | Created | CLI documentation (c/p pattern) |
| `docs/skills/0620p-sync-permissions-prompt.md` | Created | Prompt documentation (c/p pattern) |
| `~/.claude/commands/sync-permissions.md` | Created | User-level skill wrapper |

---

## Design Decisions

### 1. Permission Classification

**Session Vends (one-time, removable):**
- Specific git commits with messages: `git commit -m "specific message"`
- PR creations with heredoc bodies
- Commands on worktrees: `git -C /path/Project-123 ...`
- Giant permissions (>300 chars) - usually embedded prompts
- Permissions with embedded content (newlines, markdown, code)

**Reusable Patterns (kept):**
- Wildcards: `Bash(git -C:*)`, `Bash(poetry:*)`
- Skills: `Skill(cleanup)`, `Skill(onboard)`
- Web tools: `WebFetch`, `WebSearch`
- File patterns: `Read(C:\Users\...\**)`

### 2. Protected Permissions

**Hard-coded protection:** `Bash(python:*)` and `Bash(python3:*)` are NEVER allowed in deny lists. The tool automatically removes these if found.

**Rationale:** Blocking Python execution would cripple AgentOS tools. This protection cannot be overridden.

### 3. Giant Permission Detection (`tools/agentos-permissions.py:150-162`)

Permissions over 300 characters are flagged as "giant" and removed. These are typically:
- Gemini prompts saved as permissions
- Commit messages with full bodies
- PR descriptions embedded in commands

### 4. Embedded Content Detection (`tools/agentos-permissions.py:164-181`)

Markers that indicate corrupted permissions:
- Actual newlines (`\n`)
- Markdown code blocks
- Python/JS function definitions
- Review markers (`[BLOCKING]`, `[HIGH]`)

### 5. Locked Steps for merge-up

**Critical Design:** The `--merge-up` mode always cleans all projects first before merging. This prevents garbage from propagating to master.

```
Step 1: Clean all projects (remove vends)
Step 2: Merge unique patterns to master
Step 3: Sync to Projects-level settings
```

---

## Operating Modes

| Mode | Description |
|------|-------------|
| `--audit` | Read-only analysis of permissions |
| `--clean` | Remove session vends (creates backup first) |
| `--quick-check` | Fast check for cleanup integration (exit 0/1) |
| `--merge-up` | Collect unique patterns from projects into master |
| `--restore` | Restore from backup |

---

## Architecture

```
User
  |
  v
agentos-permissions.py
  |
  +---> load_settings() → Parse JSON
  |
  +---> audit_project()
  |         |
  |         +---> is_session_vend() → Classify each permission
  |         +---> is_reusable_pattern()
  |         v
  |     Categorized: vends, reusable, unclear
  |
  +---> clean_project() [if --clean]
  |         |
  |         +---> Create backup
  |         +---> Remove vends from allow list
  |         +---> Remove protected from deny list
  |         v
  |     Save cleaned settings
  |
  +---> merge_up() [if --merge-up]
            |
            +---> Clean all projects (locked step)
            +---> Collect unique patterns
            +---> Merge to master
            +---> Sync to Projects level
```

---

## Key Implementation Details

### Session Vend Detection (`tools/agentos-permissions.py:183-261`)

Ordered checks:
1. Giant permission (>300 chars)
2. Embedded content (newlines, markdown)
3. Git commits with heredocs
4. Specific git commits with inline messages
5. PR creations with long bodies
6. Worktree commands (path contains issue ID)
7. One-time push with tracking
8. PR merge commands

### Reusable Pattern Detection (`tools/agentos-permissions.py:280-315`)

Patterns that are kept:
- Skills: `Skill(...)`
- Web tools: `WebFetch`, `WebSearch`
- File wildcards: `Read/Write/Edit(...**)`
- Bash wildcards: `Bash(...:*)`
- Environment variable prefixed wildcards

### JSON Validation (`tools/agentos-permissions.py:105-147`)

Paranoid validation before writing:
1. Serialize to JSON
2. Validate serialized content
3. Write to temp file
4. Validate written file
5. Atomic rename to final path

---

## Deviations from Original Issue Spec

### 1. `--sync` Mode → `--merge-up` with Locked Cleanup

**Original Spec:**
> `--sync` - Full sync with auto-promote (patterns in 3+ projects)

**What Was Implemented:**
`--merge-up` mode with a locked three-step sequence:
1. Clean all projects (remove session vends)
2. Merge unique patterns to master
3. Sync changes to Projects-level settings

**Rationale:**

The original `--sync` concept implied bidirectional synchronization. During implementation, we discovered this was dangerous: if a project has accumulated garbage (session vends, corrupted permissions), syncing would propagate that garbage to the master configuration.

The solution was **locked steps**: `--merge-up` ALWAYS cleans projects first, ensuring only clean, validated patterns reach master. This is not configurable because:

1. **Safety first** - Garbage propagation corrupts the entire permission ecosystem
2. **Atomic operation** - Users expect "merge up" to be a single safe operation
3. **No partial state** - If cleanup is optional, users could merge garbage by mistake

The locked step design means `--merge-up` is slower but always safe.

### 2. Auto-Promote Threshold Removed

**Original Spec:**
> `--sync` - Full sync with auto-promote (patterns in 3+ projects)

The original design proposed automatic promotion: patterns appearing in 3+ projects would be automatically added to master.

**What Was Implemented:**
Manual user-triggered promotion via `--merge-up`. Users explicitly run the command when they want to consolidate patterns.

**Rationale:**

Auto-promotion creates several problems:

1. **Hidden changes** - Automatic background promotion modifies master without explicit user action
2. **Threshold ambiguity** - "3+ projects" is arbitrary; different users have different project counts
3. **Permission creep** - Broad patterns could propagate from test/experimental projects
4. **Audit trail** - Hard to trace when/why a pattern appeared in master

The manual approach provides:
- **Explicit control** - User decides when to promote
- **Dry-run preview** - `--merge-up --dry-run` shows exactly what will change
- **Session awareness** - Users run it when cleaning up, not as a background process
- **Clear ownership** - The commit log shows when permissions were consolidated

This aligns with AgentOS's principle: **visible, auditable operations over magical automation**.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (file not found, invalid JSON) |
| 2 | Invalid arguments |

For `--quick-check`:
| Code | Meaning |
|------|---------|
| 0 | Permissions OK (≤5 vends) |
| 1 | Cleanup recommended (>5 vends) |
| 2 | Error |

---

## Subsequent Enhancements

The tool received several enhancements after initial implementation:

| Commit | Enhancement |
|--------|-------------|
| `02e2e70` | Added `--merge-up` mode |
| `3b38192` | Merge-up now cleans vends and dedupes |
| `357d6fe` | Added Python protection + locked steps |
| `950e9dd` | Enhanced vend detection + restructured docs |

---

## Related Documentation

- Test report: `docs/reports/5/test-report.md`
- Skill wrapper: `.claude/commands/sync-permissions.md`
- User-level skill: `~/.claude/commands/sync-permissions.md`
