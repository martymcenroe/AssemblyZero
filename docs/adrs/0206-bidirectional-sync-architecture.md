# 0206 - ADR: Bidirectional Sync Architecture

**Status:** Accepted
**Date:** 2026-01-13 (proposed) · 2026-10-01 (accepted; #3689)
**Categories:** Architecture, Infrastructure, Multi-Agent

> **Accepted retrospectively, because it shipped.** This sat at `Status: Proposed`
> for nearly nine months while the mechanism it proposes was built, maintained and
> wired in: `tools/assemblyzero-harvest.py` is the harvester,
> `assemblyzero/workflows/janitor/probes/harvest.py` runs it as a janitor probe and
> parses its output for cross-project drift, and `docs/0003-file-inventory.md` lists
> its CLI and prompt as `Stable`. A reader could not tell from this document whether
> the proposal had been adopted, rejected or forgotten, and its open questions read
> as live design work on a design that was already running. Section 11 records what
> was measured on 2026-10-01 instead of asking.

## 1. Context

AssemblyZero serves as the "upstream" repository providing generic frameworks (4-digit 0xxx docs) to child projects like Aletheia, Talos, and maintenance, which have project-specific implementations (5-digit 10xxx docs).

### Current State: Unidirectional Flow

```
AssemblyZero ──push──> Aletheia
         ──push──> Talos
         ──push──> maintenance
```

The current `assemblyzero-generate.py` tool pushes templates, commands, and permissions FROM AssemblyZero TO child projects. But there is **no mechanism** for:

1. **Process innovations** discovered in child projects to flow back to AssemblyZero
2. **Permissions** added by agents in child projects to propagate
3. **Commands** developed locally to be recognized as generic
4. **Conflict resolution** when multiple agents evolve process simultaneously

### The Problem: Trapped Knowledge

**Real-world example:** Claude Opus working in Talos developed a sophisticated Gemini review protocol:
- `gemini-model-check.sh` wrapper enforcing specific model versions
- Exit code verification (0=success, 2=quota, 3=downgrade)
- Stderr marker verification (`---GEMINI-MODEL-VERIFIED---`)

This knowledge is **trapped in Talos**. Aletheia agents don't benefit. If this is genuinely good process, it should live in AssemblyZero and propagate to all projects.

### Fundamental Tensions

| Tension | Description |
|---------|-------------|
| **Local Innovation vs. Global Consistency** | Agents need freedom to innovate in context, but good innovations should propagate |
| **Immediacy vs. Quality Control** | Want improvements available immediately, but untested changes could break other projects |
| **Autonomy vs. Coordination** | Each agent operates independently, but they share infrastructure |
| **Write Location** | Should agents update AssemblyZero directly, or their project, or both? |

## 2. Decision

**We will implement a hybrid bidirectional sync model with three propagation mechanisms:**

### 2.1 Layer 1: AssemblyZero → Projects (Push) — Existing

The current `assemblyzero-generate.py` continues to push:
- Templates with `{{VAR}}` substitution
- Generic commands
- Base permissions

**Trigger:** Manual invocation or post-commit hook in AssemblyZero.

### 2.2 Layer 2: Projects → AssemblyZero (Promote) — NEW

Agents can explicitly promote patterns to AssemblyZero via the `/promote` command:

```bash
/promote --file docs/standards/10002-coding-standards-local.md --section "Gemini Review Protocol"
```

**Process:**
1. Agent recognizes "this pattern should be global"
2. Invokes `/promote` with file and section
3. Tool extracts content, generalizes it (adds `{{VAR}}` placeholders)
4. Creates PR to AssemblyZero
5. Orchestrator reviews and merges
6. Next sync propagates to all projects

**Criteria for promotion-worthy patterns:**
- Solves a problem that exists across projects
- Not project-specific (no hardcoded paths, repos, etc.)
- Has been tested in at least one project context

### 2.3 Layer 3: Cross-Project Discovery (Harvest) — NEW

An AssemblyZero audit (`0010-cross-project-harvest.md`) proactively scans child projects:

```
AssemblyZero <──harvest──┬── Aletheia
                    ├── Talos
                    └── maintenance
```

**Detection patterns:**
1. **Convergent evolution:** Same pattern appears in multiple children independently
2. **Override detection:** Child has `-local.md` extension with content that doesn't exist in AssemblyZero parent
3. **Permission accumulation:** Child has permissions not in AssemblyZero base set
4. **Command divergence:** Child commands differ from AssemblyZero templates

**Output:** Report of promotion candidates for human review.

## 3. Technical Architecture

### 3.1 Project Registry

AssemblyZero must know about its children:

```json
// AssemblyZero/.claude/project-registry.json
{
  "children": [
    {
      "name": "Aletheia",
      "path": "C:\\Users\\mcwiz\\Projects\\Aletheia",
      "github": "martymcenroe/Aletheia",
      "lastSync": "2026-01-13T14:30:00Z",
      "lastHarvest": "2026-01-13T14:30:00Z"
    },
    {
      "name": "Talos",
      "path": "C:\\Users\\mcwiz\\Projects\\Talos",
      "github": "martymcenroe/Talos",
      "lastSync": "2026-01-10T09:00:00Z",
      "lastHarvest": null
    },
    {
      "name": "maintenance",
      "path": "C:\\Users\\mcwiz\\Projects\\maintenance",
      "github": "martymcenroe/maintenance",
      "lastSync": "2026-01-12T11:00:00Z",
      "lastHarvest": null
    }
  ]
}
```

### 3.2 Sync Directions

| Direction | Mechanism | Trigger | Tool |
|-----------|-----------|---------|------|
| AssemblyZero → Projects | Push | Manual, post-commit hook | `assemblyzero-generate.py` |
| Project → AssemblyZero | Promote | Agent explicit call | `/promote` command |
| All Projects → AssemblyZero | Harvest | `/cleanup --full`, scheduled | `assemblyzero-harvest.py` |

### 3.3 Permission Sync (Enhanced)

The existing `/sync-permissions` command is enhanced:

**Current behavior:** Removes one-time permissions accumulated in project

**New behavior:**
1. Remove one-time permissions (existing)
2. Detect permissions added to project that should be in AssemblyZero
3. Offer to promote permission patterns to AssemblyZero base set
4. Sync permissions across all registered projects

### 3.4 CLAUDE.md Inheritance (Enhanced)

**Current:** Projects read AssemblyZero CLAUDE.md first, then their own.

**Enhanced:**
1. Detect when project CLAUDE.md duplicates AssemblyZero content
2. Flag duplicates for removal during `/cleanup --full`
3. Ensure project CLAUDE.md only contains project-specific rules

### 3.5 Immediate Propagation

**Problem:** When AssemblyZero changes, how do all projects get updates immediately?

**Solution: Post-commit hook in AssemblyZero:**

```bash
#!/bin/bash
# AssemblyZero/.git/hooks/post-commit

REGISTRY="$GIT_DIR/../.claude/project-registry.json"
if [ -f "$REGISTRY" ]; then
  for project in $(jq -r '.children[].path' "$REGISTRY"); do
    poetry run python tools/assemblyzero-generate.py --project "$project" --quiet
  done
fi
```

This ensures changes to AssemblyZero templates/commands immediately propagate to all registered projects.

## 4. Alternatives Considered

### Option A: Push-Only (Current)
**Decision:** Rejected as insufficient
- Innovations trapped in child projects
- No feedback loop for process improvement

### Option B: Agent Direct-Write to AssemblyZero
**Decision:** Rejected as risky
- No review gate for untested changes
- Conflict potential when multiple agents write simultaneously
- May pollute AssemblyZero with project-specific content

### Option C: RFC-Only Pattern (Issues/PRs for all changes)
**Decision:** Rejected as too slow
- Adds friction to small improvements
- May discourage innovation
- Delays propagation unacceptably

### Option D: Hybrid (Selected)
**Decision:** Accepted
- Local innovation allowed (write to project docs)
- Explicit promotion path (agent-initiated PR to AssemblyZero)
- Proactive discovery (harvest audit finds patterns worth promoting)
- Quality gate preserved (human review before merge)

## 5. Conflict Resolution

When multiple agents evolve process simultaneously:

### 5.1 Conflict Types

| Type | Example | Resolution |
|------|---------|------------|
| **Additive** | Agent A adds rule X, Agent B adds rule Y | Auto-merge (no conflict) |
| **Modification** | Agent A changes rule, Agent B changes same rule | Flag for human review |
| **Deletion** | Agent removes rule | Always flag for human review |
| **Semantic** | Agents add contradictory rules | Flag for human review |

### 5.2 Resolution Protocol

1. **Additive changes:** Auto-merge via standard git
2. **Modifications to same section:** Create issue, assign to user
3. **Deletions:** Require explicit approval before propagation
4. **Semantic conflicts:** User decides canonical approach

### 5.3 Timestamp Precedence

For non-conflicting changes, most recent wins (git's default behavior). For conflicts, we do NOT use timestamp — human review required.

## 6. Where Should Agents Write?

### 6.1 Decision Matrix

| Content Type | Write To | Example |
|--------------|----------|---------|
| **Generic process** | AssemblyZero directly | Bash rules, worktree protocol |
| **Project-specific process** | Project docs | Gemini integration for Aletheia |
| **Unsure/experimental** | Project docs | Test locally, promote if valuable |
| **Permissions (generic)** | AssemblyZero base set | `Bash(npm install:*)` |
| **Permissions (project)** | Project settings | Project-specific tool paths |

### 6.2 The AssemblyZero-First Rule

**When an agent discovers a pattern that should be generic:**

1. **Recognize:** "This would help all projects"
2. **Write:** Add to AssemblyZero directly (if permitted) OR use `/promote`
3. **Never:** Add to project docs hoping it will "bubble up" magically

### 6.3 Project-Specific Detection

Patterns that indicate project-specific (don't promote):
- Contains hardcoded project name (Aletheia, Talos)
- References project-specific tools or paths
- Only makes sense in context of project's tech stack

## 7. Integration with Existing Workflows

### 7.1 `/cleanup --full` Integration

The full cleanup mode will include:

```markdown
## Cross-Project Sync Check
- [ ] Run harvest audit on registered projects
- [ ] Review promotion candidates
- [ ] Sync permissions (remove one-time, detect promotable)
- [ ] Check CLAUDE.md for duplicate content
```

### 7.2 New Audit: 0010-cross-project-harvest

| Field | Value |
|-------|-------|
| **Frequency** | Part of `/cleanup --full`, or monthly |
| **Auto-fix** | No (human review required) |
| **Model** | Sonnet (pattern recognition) |
| **Output** | Report of promotion candidates |

### 7.3 New Command: `/promote`

```markdown
# Usage
/promote --file <path> --section <name>
/promote --permission "<pattern>"
/promote --command <name>

# Examples
/promote --file docs/standards/10002-coding-standards-local.md --section "Gemini Review Protocol"
/promote --permission "Bash(npm audit fix:*)"
/promote --command cleanup
```

## 8. Migration Plan

### Phase 1: Infrastructure (Week 1)
- [ ] Create `project-registry.json` schema
- [ ] Register existing projects (Aletheia, Talos, maintenance)
- [ ] Add post-commit hook skeleton to AssemblyZero

### Phase 2: Harvest Tooling (Week 2)
- [ ] Implement `assemblyzero-harvest.py`
- [ ] Create 0010-cross-project-harvest.md audit
- [ ] Test on registered projects

### Phase 3: Promote Command (Week 3)
- [ ] Implement `/promote` command
- [ ] Add to `~/.claude/commands/`
- [ ] Document promotion workflow

### Phase 4: Integration (Week 4)
- [ ] Integrate harvest into `/cleanup --full`
- [ ] Enhance `/sync-permissions` for bidirectional flow
- [ ] Add CLAUDE.md duplicate detection

## 9. Security Risk Analysis

| Risk | Mitigation |
|------|------------|
| **Malicious content promotion** | Human review required before merge to AssemblyZero |
| **Permission escalation** | Promoted permissions reviewed before adding to base set |
| **Cross-project leakage** | Registry only includes user-approved projects |
| **Automated propagation failures** | Post-commit hook has error handling, logs failures |

## 10. Consequences

### Positive
- **Knowledge flows freely:** Innovations in any project benefit all projects
- **Reduced duplication:** Good patterns live in one place (AssemblyZero)
- **Faster iteration:** Agents can experiment locally, promote winners
- **Audit trail:** All promotions go through PR review

### Negative
- **New tooling required:** Harvest script, promote command, registry
- **Human review bottleneck:** Orchestrator must review promotions
- **Learning curve:** Agents must learn when to promote vs. keep local
- **Registry maintenance:** Must keep project list current

## 11. The four questions, answered

Measured 2026-10-01 (#3689). Three were answered by the implementation; one was
real and is tracked. **Nothing in this section is outstanding, and no row asks
anyone anything** — a decision record that holds a question is read again by every
later session as live design work, which is what these four did for nine months.

1. **Harvest automation: it already runs automatically, as a janitor probe.**
   `assemblyzero/workflows/janitor/probes/harvest.py` invokes
   `assemblyzero-harvest.py` and parses its output for cross-project drift. There is
   no scheduled GitHub Action and none is wanted: five workflows exist and none
   carries a `schedule` trigger, so the janitor is this repo's automation route
   rather than cron.
2. **AssemblyZero is not versioned, and that is consistent with how it is
   consumed.** `pyproject.toml` declares `0.1.0` and one tag exists. `CLAUDE.md`
   states that tools execute from `AssemblyZero/tools/` and are not copied locally,
   so nothing installs this as a package and a version number would have no
   consumer. Revisit only if something starts consuming it as a dependency.
3. **Cross-org use is not a current requirement.** No external consumer exists; the
   repo is consumed by path. A real external consumer would be a new ADR, not a
   question held open here against the possibility.
4. **Rollback is the one real gap, and it is tracked in #3690.** No rollback or
   revert path exists in the harvest or downstream-push tooling. Git history is the
   de facto procedure and is written down nowhere, which means it gets re-derived
   under pressure while the fleet is broken. #3690 covers writing the manual
   sequence down first, naming the child-side state a revert cannot reach, and
   deciding whether a tool is wanted.

## 12. References

- [0203-git-worktree-isolation.md](0203-git-worktree-isolation.md) - Isolation pattern
- [0204-single-identity-orchestration.md](0204-single-identity-orchestration.md) - Orchestrator role
- AssemblyZero CLAUDE.md § "Source of Truth" - Current unidirectional model
