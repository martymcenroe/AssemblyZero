# 0912 - GitHub Projects

## Overview

GitHub Projects v2 is used to track work across all repositories. Projects are user-level (not repo-level), allowing cross-repo visibility and planning.

## Project Structure

| # | Project | Repos | URL |
|---|---------|-------|-----|
| 1 | Aletheia | Aletheia | [projects/1](https://github.com/users/martymcenroe/projects/1) |
| 2 | Infrastructure | AssemblyZero, maintenance, unleashed | [projects/2](https://github.com/users/martymcenroe/projects/2) |
| 3 | Talos | Talos | [projects/3](https://github.com/users/martymcenroe/projects/3) |
| 4 | Clio | Clio | [projects/4](https://github.com/users/martymcenroe/projects/4) |
| 5 | RCA-PDF | RCA-PDF-extraction-pipeline | [projects/5](https://github.com/users/martymcenroe/projects/5) |

## Stage Workflow

Issues progress through these stages:

```
┌──────────┐    ┌──────────────┐    ┌────────────────┐    ┌──────┐
│ Backlog  │ -> │ LLD Approved │ -> │ Implementation │ -> │ Done │
└──────────┘    └──────────────┘    └────────────────┘    └──────┘
     │                 │                    │                 │
     │                 │                    │                 │
  Issue created    LLD reviewed       Worktree created   PR merged
                   & approved         work started
```

| Stage | Meaning | Entry Trigger |
|-------|---------|---------------|
| **Backlog** | Issue exists, needs LLD | Issue created via workflow |
| **LLD Approved** | Design reviewed, ready to build | LLD workflow completes with approval |
| **Implementation** | Active development | Worktree created for issue |
| **Done** | Complete | PR merged |

## CLI Reference

### Authentication

GitHub Projects requires the `project` scope:

```bash
# Add project scope to gh auth
gh auth refresh -s project
```

### List Projects

```bash
# List all your projects
gh project list --owner @me

# Output:
# 5  RCA-PDF         open  PVT_kwHOABGrz84BOCPn
# 4  Clio            open  PVT_kwHOABGrz84BOCOA
# ...
```

### View Project

```bash
# View project details
gh project view 2 --owner @me

# Open in browser
gh project view 2 --owner @me --web
```

### List Items in Project

```bash
# List all items
gh project item-list 2 --owner @me

# List with JSON output
gh project item-list 2 --owner @me --format json

# Count items
gh project item-list 2 --owner @me --format json --jq '.items | length'

# Find specific issue
gh project item-list 2 --owner @me --format json \
  --jq '.items[] | select(.content.number == 89)'
```

### Add Issue to Project

```bash
# Add by issue URL
gh project item-add 2 --owner @me --url https://github.com/martymcenroe/AssemblyZero/issues/89

# Add multiple issues (loop)
for url in URL1 URL2 URL3; do
  gh project item-add 2 --owner @me --url "$url"
done
```

### Update Item Field (Stage)

```bash
# Get item ID first
ITEM_ID=$(gh project item-list 2 --owner @me --format json \
  --jq '.items[] | select(.content.number == 89) | .id')

# Update Stage field
gh project item-edit \
  --project-id PVT_kwHOABGrz84BOCN9 \
  --id "$ITEM_ID" \
  --field-id PVTSSF_lAHOABGrz84BOCN9zg83eCU \
  --single-select-option-id 8bbcaf54  # Implementation
```

### Archive Item

```bash
# Archive (hide from default view)
gh project item-archive 2 --owner @me --id PVTI_xxx

# Unarchive
gh project item-archive 2 --owner @me --id PVTI_xxx --undo
```

### List Fields

```bash
# Show all fields in a project
gh project field-list 2 --owner @me

# Get Stage field options
gh project field-list 2 --owner @me --format json \
  --jq '.fields[] | select(.name == "Stage")'
```

### Create Field

```bash
# Create single-select field
gh project field-create 2 --owner @me \
  --name "Priority" \
  --data-type "SINGLE_SELECT" \
  --single-select-options "P0,P1,P2,P3"
```

## Project IDs Reference

### Project IDs

| Project | Number | ID |
|---------|--------|-----|
| Aletheia | 1 | `PVT_kwHOABGrz84BLIjk` |
| Infrastructure | 2 | `PVT_kwHOABGrz84BOCN9` |
| Talos | 3 | `PVT_kwHOABGrz84BOCN-` |
| Clio | 4 | `PVT_kwHOABGrz84BOCOA` |
| RCA-PDF | 5 | `PVT_kwHOABGrz84BOCPn` |

### Stage Field IDs

| Project | Stage Field ID |
|---------|----------------|
| Aletheia | `PVTSSF_lAHOABGrz84BLIjkzg83eCY` |
| Infrastructure | `PVTSSF_lAHOABGrz84BOCN9zg83eCU` |
| Talos | `PVTSSF_lAHOABGrz84BOCN-zg83eDE` |
| Clio | `PVTSSF_lAHOABGrz84BOCOAzg83eDw` |
| RCA-PDF | `PVTSSF_lAHOABGrz84BOCPnzg83eD0` |

### Stage Option IDs

**Infrastructure (#2):**
| Stage | Option ID |
|-------|-----------|
| Backlog | `ff185463` |
| LLD In Progress | `295ae506` |
| LLD Approved | `c86df025` |
| Implementation | `8bbcaf54` |
| Done | `d88bedfd` |

**Aletheia (#1):**
| Stage | Option ID |
|-------|-----------|
| Backlog | `4f25e338` |
| LLD In Progress | `89a3f589` |
| LLD Approved | `2188d81a` |
| Implementation | `0e716135` |
| Done | `61da0f9b` |

**Talos (#3):**
| Stage | Option ID |
|-------|-----------|
| Backlog | `fbbefbac` |
| LLD In Progress | `1aed4383` |
| LLD Approved | `657cbd43` |
| Implementation | `ecf7e95d` |
| Done | `8be1efde` |

**Clio (#4):**
| Stage | Option ID |
|-------|-----------|
| Backlog | `f3f4ec89` |
| LLD In Progress | `5fa7e5e1` |
| LLD Approved | `870ad056` |
| Implementation | `a44c06ee` |
| Done | `3f87106d` |

**RCA-PDF (#5):**
| Stage | Option ID |
|-------|-----------|
| Backlog | `cb3c468e` |
| LLD In Progress | `cba8401b` |
| LLD Approved | `45ac3585` |
| Implementation | `835238fe` |
| Done | `cabd3ddc` |

## Views (Kanban Board)

Views are configured in the GitHub web UI only (not via CLI).

### Creating a Kanban View

1. Open project in browser: `gh project view <N> --owner @me --web`
2. Click **+ New view** (top left)
3. Select **Board**
4. Click gear icon (top right of view)
5. Set **Columns by** → **Stage**
6. Rename view to "Kanban"

### Filtering Views

In the view settings (gear icon):
- **Filter** - e.g., `label:priority:high` or `repo:martymcenroe/AssemblyZero`
- **Group by** - Stage, Assignee, Label, etc.
- **Sort by** - Created, Updated, custom fields

## Labels for Sprints

Use labels on issues for simple sprint tracking:

```bash
# Create sprint labels
gh label create "sprint-1" --repo martymcenroe/AssemblyZero --color "1d76db"
gh label create "sprint-2" --repo martymcenroe/AssemblyZero --color "1d76db"

# Add label to issue
gh issue edit 89 --repo martymcenroe/AssemblyZero --add-label "sprint-1"
```

Then filter your board view by label to see only current sprint items.

## Common Workflows

### Add All Open Issues from a Repo to Project

```bash
# Get all open issue URLs and add to project
gh issue list --repo martymcenroe/AssemblyZero --state open --json url --jq '.[].url' | \
  while read url; do
    gh project item-add 2 --owner @me --url "$url"
  done
```

### Move Issue to "In Progress"

```bash
# Set Stage to Implementation for issue #89 in Infrastructure
ITEM_ID=$(gh project item-list 2 --owner @me --format json \
  --jq '.items[] | select(.content.number == 89) | .id')

gh project item-edit \
  --project-id PVT_kwHOABGrz84BOCN9 \
  --id "$ITEM_ID" \
  --field-id PVTSSF_lAHOABGrz84BOCN9zg83eCU \
  --single-select-option-id 8bbcaf54
```

### Archive All Closed Issues

```bash
# Find and archive closed issues (requires checking issue state)
gh project item-list 2 --owner @me --format json \
  --jq '.items[] | select(.content.state == "CLOSED") | .id' | \
  while read id; do
    gh project item-archive 2 --owner @me --id "$id"
  done
```

## Automation

Stage updates can be automated by integrating with AssemblyZero workflows.

See: `ideas/active/github-project-stage-automation.md`

Planned automation:
- Issue workflow success → Stage = Backlog
- LLD workflow approval → Stage = LLD Approved
- Worktree creation → Stage = Implementation
- PR merge → Stage = Done

## Troubleshooting

### "Token missing required scopes"

```bash
gh auth refresh -s project
```

### Issue not appearing in project

Issue must be explicitly added to project:
```bash
gh project item-add <PROJECT_NUM> --owner @me --url <ISSUE_URL>
```

### Can't find item ID

```bash
# List all items with details
gh project item-list <N> --owner @me --format json --jq '.items[] | {id: .id, number: .content.number, title: .title}'
```

### Stage field not updating

Verify you have correct IDs:
1. Project ID (not number)
2. Item ID (not issue number)
3. Field ID
4. Option ID

All four must match the specific project.

## Related

- [GitHub Projects Documentation](https://docs.github.com/en/issues/planning-and-tracking-with-projects)
- [gh project CLI Manual](https://cli.github.com/manual/gh_project)
- Brief: `ideas/active/github-project-stage-automation.md`
