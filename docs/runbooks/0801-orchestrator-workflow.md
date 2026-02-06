# 0801 - Orchestrator Workflow Runbook

## Overview

This runbook describes how an **Orchestrator** (human operator) manages multiple AI agents across multiple projects using AssemblyZero. It covers the complete workflow from issue triage to PR merge, with emphasis on tracking LLD review status across projects.

**Target Audience:** Senior engineers or technical leads orchestrating AI agent development.

---

## The Problem

You have multiple projects with open issues. Some have LLDs, some don't. Some LLDs are reviewed, some aren't. Without a system, you lose track:

> "I have 15 issues in Talos, 6 in Clio, and 5 in Aletheia. Which ones can I actually start coding?"

AssemblyZero solves this with:
1. **Structured LLD/Report workflow** - Every issue follows the same gates
2. **Session-sharded audit logging** - Track Gemini reviews across all sessions
3. **Unified view tools** - See status at a glance

---

## Real-World Example: Your Current State

### Talos (15 open issues)
| Category | Count | LLD Status |
|----------|-------|------------|
| Core Epic (#97-105) | 9 | No LLDs - cannot start coding |
| Compliance (#63-66, #69) | 5 | No LLDs - cannot start coding |
| Safety (#96) | 1 | No LLD - cannot start coding |

**Action Required:** Create LLDs for priority issues before any agent can code.

### Clio (6 open issues)
| Category | Count | LLD Status |
|----------|-------|------------|
| Testing gaps (#2-4) | 3 | No LLDs needed (test tasks) |
| Asset fixes (#5, #11) | 2 | No LLDs needed (design tasks) |
| Feature (#1) | 1 | LLD completed and in `done/` |

**Action Required:** Testing tasks can proceed without LLDs. Feature #1 is complete.

### Aletheia (5 open issues)
| Category | Count | LLD Status |
|----------|-------|------------|
| Authentication (#341) | 1 | No LLD - high priority |
| Mobile/PWA (#330-333) | 4 | No LLDs - can be batched |

**Action Required:** Create LLD for #341 (security-critical). Batch #330-333 into single cross-platform LLD.

---

## Workflow: Issue to Merge

```
                    +-----------------+
                    |  GitHub Issue   |
                    +--------+--------+
                             |
                    +--------v--------+
                    |  Create LLD     |
                    |  (docs/LLDs/    |
                    |   active/)      |
                    +--------+--------+
                             |
              +--------------v--------------+
              |    LLD REVIEW GATE          |
              |    Submit to Gemini 3 Pro   |
              +--------------+--------------+
                             |
              +--------------v--------------+
              |  [APPROVED]  |  [BLOCKED]   |
              +------+-------+------+-------+
                     |              |
                     |              v
                     |       Fix issues,
                     |       resubmit
                     |
              +------v-------+
              |  Create      |
              |  Worktree    |
              +------+-------+
                     |
              +------v-------+
              |  Implement   |
              |  + Tests     |
              +------+-------+
                     |
              +------v-------+
              |  Generate    |
              |  Reports     |
              +------+-------+
                     |
         +-----------v-----------+
         | IMPLEMENTATION REVIEW |
         |  Submit to Gemini     |
         +-----------+-----------+
                     |
         +-----------v-----------+
         |  [APPROVED]  |[REVISE]|
         +------+-------+---+----+
                |           |
                v           v
           Create PR    Fix issues,
                        resubmit
                |
         +------v-------+
         |   Merge      |
         +------+-------+
                |
         +------v-------+
         |  Move LLD &  |
         |  Reports to  |
         |  done/       |
         +--------------+
```

---

## Step-by-Step: Creating an LLD

### 1. Start from Issue

```bash
# View issue details
gh issue view 98 --repo martymcenroe/Talos
```

### 2. Create LLD File

```bash
# Create LLD in active directory
touch docs/LLDs/active/98-schema-backend-crud.md
```

### 3. Use LLD Template (0102)

```markdown
# {IssueID} - Feature: {Title}

## 1. Context & Goal
* **Issue:** #{issue_id}
* **Objective:** {What this achieves}
* **Status:** Draft
* **Related Issues:** {Dependencies}

## 2. Proposed Changes

### 2.1 Files Changed
| File | Change Type | Description |
|------|-------------|-------------|

### 2.2 Dependencies
{New packages required}

### 2.3 Data Structures
{TypedDicts, classes, schemas}

### 2.4 Function Signatures
{Key function definitions}

### 2.5 Logic Flow (Pseudocode)
{Step-by-step implementation}

## 3. Requirements
{What must be true when done}

## 4. Alternatives Considered
| Option | Pros | Cons | Decision |
|--------|------|------|----------|

## 5. Security Considerations
| Concern | Mitigation | Status |

## 6. Verification & Testing
| ID | Scenario | Type | Expected |
|----|----------|------|----------|

## 7. Definition of Done
- [ ] {Checklist items}
```

### 4. Submit for Gemini Review

```bash
# Create prompt file
cat > /tmp/lld-review-prompt.txt << 'EOF'
REVIEW THE FOLLOWING LLD ONLY. DO NOT SEARCH FOR OTHER FILES.

[Paste full LLD content here]

END OF LLD. Respond with JSON only.
EOF

# Submit to Gemini
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python \
  /c/Users/mcwiz/Projects/AssemblyZero/tools/gemini-retry.py \
  --model gemini-3-pro-preview \
  --prompt-file /tmp/lld-review-prompt.txt
```

### 5. Handle Response

**If APPROVED:**
- Update LLD with review log entry
- Create worktree: `git worktree add ../Project-{IssueID} -b {IssueID}-short-desc`
- Push branch: `git push -u origin HEAD`
- Begin implementation

**If BLOCKED:**
- Address Tier 1 issues (blocking)
- Consider Tier 2 issues (recommended)
- Note Tier 3 suggestions for later
- Resubmit

---

## Tracking LLD Review Status

### Session-Sharded Audit Log (New in #57)

Every Gemini review is logged to `logs/active/{timestamp}_{session_id}.jsonl`:

```json
{
  "id": "uuid",
  "timestamp": "2026-01-24T18:30:45Z",
  "node": "review_lld",
  "issue_id": 98,
  "verdict": "APPROVED",
  "model_verified": "gemini-3-pro-preview",
  "credential_used": "credential-1",
  "duration_ms": 2345
}
```

### View Recent Reviews

```bash
# View last 10 audit entries
poetry run python tools/view_audit.py --tail 10

# Filter by project (future enhancement #52)
poetry run python tools/view_audit.py --issue 98
```

### Consolidation

Shards are automatically consolidated into `logs/governance_history.jsonl` via post-commit hook. This happens transparently - you don't need to do anything.

---

## Multi-Project Orchestration

### Morning Standup Routine

1. **Check all projects for open issues:**
```bash
gh issue list --repo martymcenroe/Talos --state open
gh issue list --repo martymcenroe/Clio --state open
gh issue list --repo martymcenroe/Aletheia --state open
```

2. **Check LLD coverage:**
```bash
ls docs/LLDs/active/    # Each project
ls docs/LLDs/done/      # Completed
```

3. **Check worktree status:**
```bash
git worktree list       # Each project
```

4. **Prioritize:**
   - Issues with approved LLDs can be assigned to agents
   - Issues without LLDs need LLD creation first
   - Security/compliance issues get priority

### Spawning Agents

Once an LLD is approved, spawn an agent:

```
"Implement issue #98 following the approved LLD at docs/LLDs/active/98-schema-backend-crud.md.
Create worktree, implement, run tests, generate reports, submit for implementation review."
```

The agent will:
1. Create worktree (isolated branch)
2. Implement per LLD
3. Run tests
4. Generate implementation-report.md and test-report.md
5. Submit to Gemini for implementation review
6. Create PR if approved

### Parallel Execution

With session-sharded logging, multiple agents can work simultaneously:

```
Agent A: Working on Talos #98 → logs/active/20260124T183045_a1b2c3d4.jsonl
Agent B: Working on Clio #2  → logs/active/20260124T183046_d4e5f6a7.jsonl
Agent C: Working on Aletheia #341 → logs/active/20260124T183047_b8c9d0e1.jsonl
```

No collisions. Each writes to its own shard. The orchestrator sees a unified view via `tail()`.

---

## Quick Reference

### Key Paths

| Path | Purpose |
|------|---------|
| `docs/LLDs/active/` | LLDs awaiting implementation |
| `docs/LLDs/done/` | Completed LLDs |
| `docs/reports/active/` | Reports awaiting merge |
| `docs/reports/done/` | Completed reports |
| `logs/active/` | Session shards (ephemeral) |
| `logs/governance_history.jsonl` | Consolidated audit log |

### Key Commands

| Command | Purpose |
|---------|---------|
| `gh issue list` | View open issues |
| `git worktree add` | Create isolated branch |
| `poetry run python tools/gemini-retry.py` | Submit Gemini review |
| `poetry run python tools/view_audit.py` | View audit log |

### Gate Checklist

Before coding:
- [ ] Issue exists in GitHub
- [ ] LLD created in `docs/LLDs/active/`
- [ ] LLD submitted to Gemini
- [ ] LLD APPROVED (not BLOCKED)
- [ ] Worktree created

Before PR:
- [ ] Tests pass
- [ ] implementation-report.md generated
- [ ] test-report.md generated
- [ ] Implementation review submitted to Gemini
- [ ] Implementation APPROVED

After merge:
- [ ] Worktree removed
- [ ] LLD moved to `docs/LLDs/done/`
- [ ] Reports moved to `docs/reports/done/`
- [ ] Local branch deleted

---

## Troubleshooting

### "Gemini quota exhausted"

The retry tool handles this automatically by rotating credentials. If all credentials exhausted:

1. Wait 24 hours for quota reset
2. Or add more credentials to `~/.assemblyzero/gemini-credentials.json`

### "Can't find LLD for issue X"

Check both locations:
```bash
ls docs/LLDs/active/*X*
ls docs/LLDs/done/*X*
```

If neither exists, create one.

### "Agent started coding without LLD review"

This is a protocol violation. Stop the agent:
1. Save current work
2. Create LLD from what was built
3. Submit for review
4. Resume only if approved

### "Multiple agents conflicting"

Ensure each agent:
- Has its own worktree
- Has unique session ID (automatic)
- Is working on different issues

Check worktrees: `git worktree list`

---

## Related Documentation

- [0102 - LLD Template](../standards/0102-feature-lld-template.md)
- [0701c - Issue Review Prompt](../skills/0701c-Issue-Review-Prompt.md)
- [0702c - LLD Review Prompt](../skills/0702c-LLD-Review-Prompt.md)
- [0703c - Implementation Review Prompt](../skills/0703c-Implementation-Review-Prompt.md)
