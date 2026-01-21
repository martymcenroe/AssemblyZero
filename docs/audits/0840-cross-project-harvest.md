# 0832 - Cross-Project Harvest Audit

**Category:** Documentation Health / Multi-Agent
**Frequency:** Monthly or during `/cleanup --full`
**Auto-fix:** No (generates report for human review)
**Model Recommendation:** Haiku (pattern matching, file parsing)

---

## 1. Purpose

Scan all registered child projects to discover patterns that should potentially be promoted to AgentOS. This audit implements the "harvest" layer of the bidirectional sync architecture (ADR 0206).

**Goals:**
1. Detect **convergent evolution** - patterns that independently appeared in multiple projects
2. Find **promotion candidates** - valuable patterns trapped in single projects
3. Identify **permission accumulation** - permissions that should be in AgentOS base set
4. Flag **CLAUDE.md duplication** - content that duplicates AgentOS

---

## 2. What Gets Scanned

| Category | What We Look For | Priority Logic |
|----------|------------------|----------------|
| **Commands** | `.claude/commands/*.md` not in AgentOS | HIGH - commands are high value |
| **Tools** | `.claude/tools/*` not in AgentOS | HIGH if generic, MEDIUM if project-specific |
| **Templates** | Custom directories in `.claude/` | MEDIUM - may be project-specific |
| **Permissions** | `settings.local.json` allow patterns | HIGH if convergent, LOW otherwise |
| **CLAUDE.md** | Duplicate content with AgentOS | LOW - cleanup task |

**Convergent Evolution Boost:** Any pattern found in 2+ projects automatically becomes HIGH priority.

---

## 3. Running the Audit

### 3.1 Command

```bash
# Scan all registered projects
poetry run --directory /c/Users/mcwiz/Projects/AgentOS \
    python /c/Users/mcwiz/Projects/AgentOS/tools/agentos-harvest.py

# Scan specific project only
poetry run --directory /c/Users/mcwiz/Projects/AgentOS \
    python /c/Users/mcwiz/Projects/AgentOS/tools/agentos-harvest.py --project Talos

# Output as JSON
poetry run --directory /c/Users/mcwiz/Projects/AgentOS \
    python /c/Users/mcwiz/Projects/AgentOS/tools/agentos-harvest.py --format json

# Save report to file
poetry run --directory /c/Users/mcwiz/Projects/AgentOS \
    python /c/Users/mcwiz/Projects/AgentOS/tools/agentos-harvest.py --output harvest-report.md
```

### 3.2 Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No promotion candidates found (all projects aligned) |
| 1 | Promotion candidates found (review report) |
| 2+ | Error (registry missing, project not found, etc.) |

### 3.3 Integration with /cleanup --full

The harvest audit should run during `/cleanup --full`:

```markdown
## Cross-Project Harvest (0818)
- [ ] Run: `poetry run python tools/agentos-harvest.py`
- [ ] Review HIGH priority candidates
- [ ] Create GitHub issues for patterns worth promoting
- [ ] Or use `/promote` command for immediate promotion
```

---

## 4. Understanding the Report

### 4.1 Report Sections

**Summary Table:** Overview of candidates by category and priority.

**High Priority:** Patterns strongly recommended for promotion. Includes:
- Any pattern found in 2+ projects (convergent)
- Commands (always high value)
- Generic tools (no project-specific references)

**Medium Priority:** Worth considering but may need evaluation:
- Tools with some project-specific references
- Template directories

**Low Priority:** Review later:
- Individual permission patterns (unless convergent)
- CLAUDE.md duplication warnings

### 4.2 Convergent Evolution Marker

Patterns marked with **[CONVERGENT]** appeared in multiple projects independently. This is strong signal that the pattern is valuable and should be in AgentOS.

Example:
```markdown
### tools: `gemini-model-check.sh` **[CONVERGENT]**
- **Project:** Talos
- **Path:** `C:\...\Talos\.claude\tools\gemini-model-check.sh`
- **Reason:** Tool exists in Talos but not in AgentOS [CONVERGENT: found in Talos, maintenance]
```

---

## 5. Acting on Findings

### 5.1 For Commands (HIGH)

Commands are always worth promoting if they solve a general problem.

**Action:** Use `/promote` or manually:
1. Copy command to AgentOS `.claude/commands/`
2. Generalize: Replace project-specific references with `{{VAR}}`
3. Test in AgentOS context
4. Run `agentos-generate.py` to propagate

### 5.2 For Tools (HIGH/MEDIUM)

Tools need evaluation for genericity.

**If HIGH (generic):**
1. Copy to AgentOS `.claude/tools/`
2. Add `{{PROJECT_NAME}}` placeholders
3. Update tool documentation

**If MEDIUM (project-specific):**
1. Evaluate if the core logic is generic
2. Extract generic parts to AgentOS
3. Leave project-specific wrapper in project

### 5.3 For Templates/Prompts (MEDIUM)

Template directories like `gemini-prompts/` may contain reusable patterns.

**Action:**
1. Review contents for genericity
2. If generic, create AgentOS template directory
3. Add to `.claude/templates/` with `{{VAR}}` substitution

### 5.4 For Permissions (HIGH if convergent, LOW otherwise)

Convergent permissions should be added to AgentOS base set.

**Action:**
1. Add to AgentOS `.claude/settings.local.json`
2. Run `/sync-permissions` to propagate
3. Or wait for next `agentos-generate.py` run

### 5.5 For CLAUDE.md Duplication (LOW)

Indicates project CLAUDE.md has content that belongs in AgentOS.

**Action:**
1. Review duplicated content
2. Ensure it's in AgentOS CLAUDE.md
3. Remove from project CLAUDE.md
4. Add reference: "See AgentOS CLAUDE.md for [topic]"

---

## 6. Project Registry

The harvest reads from `.claude/project-registry.json`:

```json
{
  "children": [
    {
      "name": "Aletheia",
      "path": "C:\\Users\\mcwiz\\Projects\\Aletheia",
      "github": "martymcenroe/Aletheia",
      "status": "active"
    }
  ]
}
```

**Adding a New Project:**
1. Edit `.claude/project-registry.json`
2. Add entry with `status: "active"`
3. Run harvest to check alignment

**Excluding a Project:**
Set `status: "inactive"` to skip during harvest.

---

## 7. Audit Record

| Date | Auditor | Projects | Candidates | Actions Taken |
|------|---------|----------|------------|---------------|
| 2026-01-13 | Claude Opus 4.5 | Aletheia, Talos, maintenance | 158 (21 HIGH) | Initial run, report generated |

---

## 8. Related Documents

- [ADR 0206 - Bidirectional Sync Architecture](../adrs/0206-bidirectional-sync-architecture.md)
- [0817 - AgentOS Audit](0817-agentos-audit.md) - Self-audit for AgentOS health
- [0816 - Permission Permissiveness](0816-permission-permissiveness.md) - Permission management

---

## 9. Tool Location

**Script:** `AgentOS/tools/agentos-harvest.py`

**Dependencies:** Python 3.10+, standard library only (no external packages)

**Output formats:** Markdown (default), JSON (`--format json`)
