# Maintenance Workflow: The Janitor (Entropy Demon)

**Context:** We have an extensive suite of hygiene audits (`083x`, `084x`) covering link checking, worktree cleanup, and structure compliance. Currently, these are static checklists that require a human (or an invoked agent) to "run" them. If we forget, the repository rots.

## Problem

**The "Broken Window" Failure Mode:**

* **Drift:** Documentation references files that were renamed last week (`tools/update-doc-refs.py` isn't run automatically).
* **Clutter:** `docs/temp/` and old git worktrees accumulate, confusing search tools.
* **Toil:** The user has to manually run `/audit 0834` or `/cleanup` to fix these.

## Goal

Create `tools/run_janitor_workflow.py`, a background maintenance agent that treats repository hygiene as a **Continuous State**, not a monthly task.

**Core Philosophy:**
The Janitor does not ask for permission to clean. It fixes what is mechanically broken and alerts on what is structurally unsound.

## Proposed Architecture

### 1. The State Graph (`assemblyzero/workflows/janitor/graph.py`)

* **Input:** `scope` (Default: "all"), `auto_fix` (Boolean: True).
* **Nodes:**
* **N0_Sweeper (The Sensor):**
* Runs a battery of "Probe Scripts" (returning JSON status):
* `probe_links`: Checks for broken internal markdown links.
* `probe_worktrees`: Lists stale/detached worktrees.
* `probe_harvest`: Runs `assemblyzero-harvest.py` to check for cross-project drift.
* `probe_todo`: Scans for `TODO` comments older than 30 days.




* **N1_Fixer (The Mechanic):**
* Input: Failed probes with `fixable: true`.
* Action:
* **Links:** Updates filenames in `docs/` if the target moved.
* **Worktrees:** Prunes dead trees.
* **Harvest:** Auto-promotes "High Confidence" patterns (e.g., standardized `.gitignore`).


* Output: Creates a PR or direct commit with the fixes.


* **N2_Reporter (The Town Crier):**
* Input: Failed probes with `fixable: false`.
* Action:
* Groups failures by category.
* Checks if an Issue already exists (deduplication).
* Files/Updates a **"Janitor Report"** Issue: *"Maintenance Alert: 3 Architectural Drifts Detected."*







### 2. State Management (`assemblyzero/workflows/janitor/state.py`)

```python
class JanitorState(TypedDict):
    probes_run: List[str]
    failures: List[Dict]      # {type: 'link_rot', target: '...', fixable: True}
    actions_taken: List[str]  # "Fixed link in README.md"
    report_issue_id: Optional[int]

```

### 3. The CLI Runner (`tools/run_janitor_workflow.py`)

* **Usage:**
```bash
# Scheduled via cron / Windows Task Scheduler
python tools/run_janitor_workflow.py --silent

```



## Success Criteria

* [ ] **Zero-Touch Link Fixing:** If I rename a file, the Janitor fixes the references in `README.md` overnight.
* [ ] **Clean Workspace:** `git worktree prune` is never run manually again.
* [ ] **Audit Obsolescence:** The following manual audits are archived and replaced by this workflow:
* `0834-audit-worktree-hygiene.md`
* `0838-audit-broken-references.md`
* `0840-cross-project-harvest.md`


* [ ] **Metric:** "Days since last broken link" > 30.

