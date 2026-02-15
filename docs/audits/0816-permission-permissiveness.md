# 0808 - Audit: Permission Problem Mining

## 1. Purpose

Actively mine session data to find permission problems. This audit:
1. Searches verbatim logs for permission denial patterns
2. Searches for permission denial patterns
3. Proposes remediations for recurring patterns
4. Maintains a checkpoint to avoid re-processing old logs

**This is a MINING audit, not a configuration checklist.**

---

## 2. Data Sources

### 2.1 Verbatim Session Transcripts

**Location:** `~/.claude/projects/C--Users-mcwiz-Projects-Aletheia/*.jsonl`

**Format:** JSONL with user messages, assistant responses, tool calls

**Access:** Use Grep tool (allowed) or Read tool with Windows path format:
```
C:\Users\mcwiz\.claude\projects\C--Users-mcwiz-Projects-Aletheia\
```

### 2.2 Permission Denial Patterns

In JSONL, look for:
- Tool calls with `rejected` or `denied` status
- User messages containing "no" immediately after permission requests
- Error messages containing "not allowed" or "requires approval"

---

## 3. Checkpoint System

### 3.1 Checkpoint File

**Location:** `docs/audit-state/0808-checkpoint.json`

```json
{
  "last_run": "2026-01-10T09:45:00Z",
  "logs_processed": [
    "847f4555-c72c-476c-8bd1-ee661ef59a1a.jsonl",
    "8dd661da-eba1-405d-acc4-9e03d802f20f.jsonl"
  ],
  "findings": [
    {
      "date": "2026-01-10",
      "log_id": "847f4555",
      "pattern": "head -660 /c/Users/mcwiz/.claude/...",
      "status": "resolved",
      "resolution": "Added Read tool guidance to CLAUDE.md"
    }
  ]
}
```

### 3.2 Processing Logic

1. List all `.jsonl` files in transcript directory
2. Filter to only files NOT in `logs_processed`
3. Search new files for patterns
4. Update checkpoint after processing

---

## 4. Audit Procedure

### 4.1 Identify New Transcripts

**Step 1:** List all transcript files
```
Glob pattern: *.jsonl
Path: C:\Users\mcwiz\.claude\projects\C--Users-mcwiz-Projects-Aletheia
```

**Step 2:** Read checkpoint file
```
Read: docs/audit-state/0808-checkpoint.json
```

**Step 3:** Compare lists, identify unprocessed transcripts

### 4.2 Search for Permission Denials

Search for error patterns:
```
Grep pattern: "not allowed"
Grep pattern: "requires approval"
Grep pattern: "Permission denied"
```

### 4.3 Categorize Findings

| Category | Pattern | Remediation |
|----------|---------|-------------|
| Missing allowlist entry | `Bash(newcmd:*)` needed | Add to settings.local.json |
| Flag/path issue | `head -N /path` doesn't match | Add agent instructions |
| Structural issue | `cd && cmd` attempted | Reinforce CLAUDE.md rules |
| Model behavior | Agent ignores friction rules | Update spawning instructions |

### 4.4 Update Checkpoint

After processing:
1. Add processed transcript filenames to `logs_processed`
2. Add new findings with status "open"
3. Update `last_run` timestamp
4. Write updated checkpoint to file

---

## 5. Remediation Actions

### 5.1 For Missing Permissions

Add to `.claude/settings.local.json`:
```json
"Bash(command:*)"
```

**Verify:** Command isn't destructive, isn't in deny list.

### 5.2 For Pattern Matching Issues

Update CLAUDE.md friction prevention guidance:
- Add to "Friction Risk Assessment" table
- Update spawned agent instructions

### 5.3 For Structural Issues

Reinforce rules in spawned agent instructions:
- `&&`, `|`, `;` banned
- Use absolute paths
- Prefer Read/Grep/Glob over Bash

### 5.4 For Model Behavior Issues

If agent ignores friction rules despite instructions:
- Strengthen CLAUDE.md visibility requirements
- Consider hooks for enforcement

### 5.5 Auto-Fix (Default Behavior)

**This audit auto-fixes permission problems rather than just reporting them.**

When a pattern is identified as needing remediation:

```markdown
Auto-fix procedure:
1. For missing allowlist entries:
   - Read .claude/settings.local.json
   - Add pattern to "allow" array (alphabetically sorted)
   - Write updated file
   - Log: "Added 'Bash({pattern}:*)' to allowlist"

2. For friction risk patterns:
   - Read CLAUDE.md
   - Add row to "Friction Risk Assessment" table
   - Log: "Added '{pattern}' to friction risk table"

3. Update checkpoint:
   - Mark violation as "resolved"
   - Add resolution details
```

**Auto-fix safety checks:**

| Check | Action if Fails |
|-------|-----------------|
| Command in deny list? | Skip auto-fix, flag for manual review |
| Destructive pattern? (`rm -rf`, `git push -f`) | Skip auto-fix, flag for manual review |
| Overly broad? (`Bash(*:*)`) | Skip auto-fix, flag for manual review |
| Duplicate entry? | Skip (already exists) |

**Cannot auto-fix:**
- Structural issues (agent behavior requires CLAUDE.md revision by human)
- Novel command categories (need human judgment on safety)
- Model behavior issues (require investigation)

---

## 6. Output Format

```markdown
## Permission Problem Mining - YYYY-MM-DD

**Auditor:** [Model Name]
**Scope:** [N] new transcripts since last run

### Transcripts Processed
| Filename | Size | Age |
|----------|------|-----|
| `847f4555...jsonl` | 2.1MB | 3 days |
| `8dd661da...jsonl` | 5.4MB | 1 day |

### Zugzwang Violations Found

| Date | Transcript | Pattern | Status |
|------|------------|---------|--------|
| 2026-01-10 | 847f... | `head -660 /path` | OPEN |

### Permission Denials Found

| Command | Frequency | Proposed Fix |
|---------|-----------|--------------|
| `shellcheck script.sh` | 3 | Add `Bash(shellcheck:*)` |

### Actions Taken
1. Added `Bash(shellcheck:*)` to allowlist
2. Updated CLAUDE.md friction guidance

### Checkpoint Updated
- Transcripts processed: +2 (total: 45)
- Open violations: 1
- Resolved violations: 3
```

---

## 7. Audit Schedule

**Trigger:**
- Weekly during `/cleanup --full`
- After any session with noticeable friction
- On user request

**Frequency:** Weekly minimum

---

## 8. Audit Record

| Date | Auditor | Transcripts | Violations Found | Remediations |
|------|---------|-------------|------------------|--------------|
| | | | | |

---

## 9. Transcript Maintenance

### 9.1 Archival Policy

- **Active window:** 7 days
- **Archive location:** `~/.claude/projects/.../archive/YYYY-MM/`
- **Retention:** Forever (archives are permanent)
- **Archival trigger:** `/cleanup --full` or manual script run

### 9.2 Archival Script

```bash
poetry run python tools/archive_transcripts.py
```

The script:
1. Lists all `.jsonl` files in transcript directory
2. Identifies files older than 7 days (by modification time)
3. Creates archive subdirectory if needed (`archive/YYYY-MM/`)
4. Moves old files to archive
5. Reports count of archived files

### 9.3 Archive Structure

```
~/.claude/projects/C--Users-mcwiz-Projects-Aletheia/
├── *.jsonl                    # Active (last 7 days)
├── agent-*.jsonl              # Subagent files (not archived)
└── archive/
    ├── 2025-12/
    │   ├── abc123.jsonl
    │   └── def456.jsonl
    └── 2026-01/
        └── ghi789.jsonl
```

### 9.4 Mining Archives

When searching for permission violations:
- **Default:** Only search active transcripts (last 7 days)
- **--include-archives:** Also search archived transcripts

**Searching archives:**
```
Glob pattern: **/*.jsonl
Path: C:\Users\mcwiz\.claude\projects\C--Users-mcwiz-Projects-Aletheia\archive
```

---

## 10. References

- `docs/0824-audit-permission-friction.md` - Friction pattern analysis (complementary)
- `docs/0015-agent-prohibited-actions.md` - Policy document
- `.claude/settings.local.json` - Permission implementation
- `CLAUDE.md` - Workflow rules and friction prevention
- `tools/archive_transcripts.py` - Archival script
