# Visibility Workflow: The Patrician (GitHub Project Stage Automation)

**Status:** Brief
**Priority:** High (enables project-wide visibility)
**Created:** 2026-02-02
**Persona:** Lord Vetinari (The Patrician of Ankh-Morpork)
**Inspiration:** Terry Pratchett's Discworld - City Watch series, *Going Postal*, *Making Money*

---

## Philosophy

> *"Down there are people who will follow any dragon, worship any god, ignore any iniquity. All out of a condition called 'not wanting to be noticed.'"*

Lord Havelock Vetinari doesn't control everything directly; he *organizes* it so the pieces work together. In his office, he maintains a wall map with little markers showing where everyone is. He sees patterns others miss. He moves pieces before problems arise.

**The Patrician's Core Principle:** "Don't tell me what stage you're in. I'll *observe* what stage you're in."

---

## The Wall Map

```
┌──────────┐    ┌─────────┐    ┌─────────────┐    ┌──────┐
│ Backlog  │ -> │  Ready  │ -> │ In Progress │ -> │ Done │
└──────────┘    └─────────┘    └─────────────┘    └──────┘
```

---

## Problem

The GitHub Projects "Stage" field must be manually updated as work progresses through the development lifecycle. This creates friction and leads to stale project boards that don't reflect actual work status.

Currently:
- Issues are created but Stage is not set
- LLDs get approved but Stage doesn't update to "Ready"
- Work starts (worktree created) but Stage doesn't update to "In Progress"
- PRs merge but Stage doesn't update to "Done"

The AssemblyZero workflows already know when these transitions happen but don't communicate them to GitHub Projects.

## Proposed Solution

Integrate `gh project item-edit` calls into existing AssemblyZero workflow nodes to automatically update the Stage field at key lifecycle events.

### Stage Transitions

| Event | Trigger Point | Stage Update |
|-------|---------------|--------------|
| Issue created | `run_issue_workflow.py` success | → **Backlog** |
| LLD approved | `run_lld_workflow.py` success | → **LLD Approved** |
| Work started | Worktree creation | → **Implementation** |
| PR merged | GitHub Action or post-merge hook | → **Done** |

### Simplified Stage Options

Based on user feedback, simplify from 5 stages to 4:

| Current | Proposed |
|---------|----------|
| Backlog | **Open** |
| LLD In Progress | (remove - LLD review is fast, 2-20 min) |
| LLD Approved | **Ready** |
| Implementation | **In Progress** |
| Done | **Done** |

## Technical Details

### Project Configuration

| Project | ID | Number | Stage Field ID |
|---------|-----|--------|----------------|
| Aletheia | `PVT_kwHOABGrz84BLIjk` | 1 | `PVTSSF_lAHOABGrz84BLIjkzg83eCY` |
| Infrastructure | `PVT_kwHOABGrz84BOCN9` | 2 | `PVTSSF_lAHOABGrz84BOCN9zg83eCU` |
| Talos | `PVT_kwHOABGrz84BOCN-` | 3 | `PVTSSF_lAHOABGrz84BOCN-zg83eDE` |
| Clio | `PVT_kwHOABGrz84BOCOA` | 4 | `PVTSSF_lAHOABGrz84BOCOAzg83eDw` |
| RCA-PDF | `PVT_kwHOABGrz84BOCPn` | 5 | `PVTSSF_lAHOABGrz84BOCPnzg83eD0` |

### Stage Option IDs (per project)

**Aletheia (#1):**
- Backlog: `4f25e338`
- LLD In Progress: `89a3f589`
- LLD Approved: `2188d81a`
- Implementation: `0e716135`
- Done: `61da0f9b`

**Infrastructure (#2):**
- Backlog: `ff185463`
- LLD In Progress: `295ae506`
- LLD Approved: `c86df025`
- Implementation: `8bbcaf54`
- Done: `d88bedfd`

**Talos (#3):**
- Backlog: `fbbefbac`
- LLD In Progress: `1aed4383`
- LLD Approved: `657cbd43`
- Implementation: `ecf7e95d`
- Done: `8be1efde`

**Clio (#4):**
- Backlog: `f3f4ec89`
- LLD In Progress: `5fa7e5e1`
- LLD Approved: `870ad056`
- Implementation: `a44c06ee`
- Done: `3f87106d`

**RCA-PDF (#5):**
- Backlog: `cb3c468e`
- LLD In Progress: `cba8401b`
- LLD Approved: `45ac3585`
- Implementation: `835238fe`
- Done: `cabd3ddc`

### Repo → Project Mapping

| Repository | GitHub Project |
|------------|----------------|
| `martymcenroe/Aletheia` | Aletheia (#1) |
| `martymcenroe/AssemblyZero` | Infrastructure (#2) |
| `martymcenroe/maintenance` | Infrastructure (#2) |
| `martymcenroe/unleashed` | Infrastructure (#2) |
| `martymcenroe/Talos` | Talos (#3) |
| `martymcenroe/Clio` | Clio (#4) |
| `martymcenroe/RCA-PDF-extraction-pipeline` | RCA-PDF (#5) |

### CLI Command Pattern

```bash
# Get item ID for an issue
gh project item-list <PROJECT_NUMBER> --owner @me --format json \
  --jq '.items[] | select(.content.number == <ISSUE_NUMBER>) | .id'

# Update Stage field
gh project item-edit \
  --project-id <PROJECT_ID> \
  --id <ITEM_ID> \
  --field-id <STAGE_FIELD_ID> \
  --single-select-option-id <OPTION_ID>
```

### Example: Set Issue #89 to "Implementation"

```bash
# 1. Get item ID
ITEM_ID=$(gh project item-list 2 --owner @me --format json \
  --jq '.items[] | select(.content.number == 89) | .id')

# 2. Update Stage
gh project item-edit \
  --project-id PVT_kwHOABGrz84BOCN9 \
  --id "$ITEM_ID" \
  --field-id PVTSSF_lAHOABGrz84BOCN9zg83eCU \
  --single-select-option-id 8bbcaf54
```

## Integration Points

### 1. Issue Workflow (`run_issue_workflow.py`)

**Location:** After successful issue creation (line ~380 where `issue_url` is set)

**Action:**
1. Detect which project the repo maps to
2. Find the item ID for the newly created issue
3. Set Stage to "Backlog" (or "Open" after simplification)

**Note:** Issue may need to be added to project first if not auto-added.

### 2. LLD Workflow (`run_lld_workflow.py`)

**Location:** After LLD approval (line ~625 where `final_lld_path` is set)

**Action:**
1. Detect which project the repo maps to
2. Find the item ID for the issue
3. Set Stage to "LLD Approved" (or "Ready" after simplification)

### 3. Worktree Creation

**Location:** New hook or integration in worktree creation scripts

**Trigger:** `git worktree add` for an issue branch

**Action:**
1. Parse issue number from branch name (e.g., `89-fix-resume-workflow` → #89)
2. Detect which project the repo maps to
3. Set Stage to "Implementation" (or "In Progress" after simplification)

### 4. PR Merge

**Option A: GitHub Action**
```yaml
on:
  pull_request:
    types: [closed]

jobs:
  update-stage:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - name: Update project stage
        run: |
          # Extract issue number from PR body or branch
          # Update Stage to Done
```

**Option B: Post-merge hook in AssemblyZero**
- Hook into the PR merge detection in existing workflows
- Call `gh project item-edit` to set Stage to "Done"

## Implementation Approach

### Phase 1: Core Utility

Create `tools/project_stage.py`:
- Function to detect repo → project mapping
- Function to get item ID for an issue
- Function to update Stage field
- Handle "issue not in project" gracefully (auto-add)

### Phase 2: Workflow Integration

1. Add Stage update to issue workflow success path
2. Add Stage update to LLD workflow success path
3. Create worktree hook for "In Progress" transition

### Phase 3: PR Merge Automation

Choose between:
- GitHub Action (runs in CI, needs secrets)
- AssemblyZero hook (runs locally, uses existing `gh` auth)

## Configuration

Store project/field mappings in `~/.assemblyzero/project-mappings.json`:

```json
{
  "repos": {
    "martymcenroe/AssemblyZero": {
      "project_id": "PVT_kwHOABGrz84BOCN9",
      "project_number": 2,
      "stage_field_id": "PVTSSF_lAHOABGrz84BOCN9zg83eCU",
      "stage_options": {
        "backlog": "ff185463",
        "lld_approved": "c86df025",
        "implementation": "8bbcaf54",
        "done": "d88bedfd"
      }
    }
  }
}
```

Or query dynamically via `gh` CLI (slower but always current).

## Acceptance Criteria

- [ ] When issue workflow completes successfully, issue Stage is set to "Backlog"
- [ ] When LLD workflow completes with approval, issue Stage is set to "LLD Approved"
- [ ] When worktree is created for an issue, Stage is set to "Implementation"
- [ ] When PR is merged, issue Stage is set to "Done"
- [ ] Stage updates work across all 5 projects (Aletheia, Infrastructure, Talos, Clio, RCA-PDF)
- [ ] Graceful handling when issue is not yet in project (auto-add or skip with warning)
- [ ] No workflow failures if GitHub Projects API is unavailable (warn and continue)

## Out of Scope

- Updating Stage when issue is closed without PR merge (manual)
- Handling multiple issues per PR
- Retroactive Stage updates for existing issues
- Simplifying Stage options (separate task - UI only)

## Dependencies

- GitHub CLI (`gh`) with `project` scope
- Existing AssemblyZero workflows (`run_issue_workflow.py`, `run_lld_workflow.py`)
- Per-repo `.claude/project.json` or global config

## Open Questions

1. Should we simplify Stage options before or after this automation?
2. Should "issue not in project" auto-add the issue, or just warn?
3. Should worktree creation hook be mandatory or opt-in?
4. GitHub Action vs local hook for PR merge - which is preferred?

## Output Example (The Morning Report)

```
======================================================================
            THE PATRICIAN'S MORNING REPORT
              'Information is power.'
======================================================================

Surveyed: 5 projects
Work items: 47

THE WALL MAP:
────────────────────────────────────────
  Backlog      │ ████████████ (12)
  Ready        │ █████ (5)
  In Progress  │ ████████ (8)
  Review       │ ███ (3)
  Done         │ ███████████████████ (19)

MOVEMENTS:
────────────────────────────────────────
  #104  │ Backlog      → Ready
  #107  │ In Progress  → Done
  #93   │ Review       → Done

  Total updates: 3

MATTERS REQUIRING ATTENTION:
────────────────────────────────────────
  ⚠ #88: Stale in In Progress (no activity 21 days)
  ⚠ #92: Has PR but no LLD

======================================================================
              'Don't let me detain you.'
======================================================================
```

---

## The Patrician's Rules

1. **Never trust self-reported status.** Observe the actual state.
2. **Flag anomalies, don't hide them.** Stale work is dangerous work.
3. **Move quietly.** Update the board; don't make a production of it.
4. **Information is power.** The report is the product.

---

## References

- [Workflow Personas](../wiki/Workflow-Personas.md) - Lord Vetinari entry
- GitHub Projects v2 API: https://docs.github.com/en/issues/planning-and-tracking-with-projects
- `gh project` CLI: https://cli.github.com/manual/gh_project
- AssemblyZero issue workflow: `tools/run_issue_workflow.py`
- AssemblyZero LLD workflow: `tools/run_lld_workflow.py`
- *Going Postal* by Terry Pratchett (Vetinari's management style)
- *Night Watch* by Terry Pratchett (The wall map)

---

*"Taxation, gentlemen, is very much like dairy farming. The task is to extract the maximum amount of milk with the minimum amount of moo."*

**The Patrician sees all. The Patrician knows all. Don't let him detain you.**
