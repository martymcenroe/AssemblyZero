# 0834 - Worktree Hygiene Audit

## Purpose

Detect stale, orphaned, or problematic git worktrees that indicate abandoned work or cleanup failures. Catches:
- Worktrees with uncommitted changes (work in progress left behind)
- Worktrees with no unique commits (created but never used)
- Worktrees where the tracking branch no longer exists
- Orphaned worktree directories (worktree removed but directory remains)
- Worktrees older than expected session lifetime

## Trigger

- Weekly (part of standard cleanup)
- During `/cleanup --full`
- After PR merges (to verify worktree was cleaned up)
- During full audit suite (`/audit`)

## Philosophy

> "A worktree should either be actively worked on or deleted."

Stale worktrees with uncommitted changes represent lost work. Worktrees with no unique commits represent false starts. Both indicate process failures that should be surfaced.

---

## Procedure

### Step 1: List All Worktrees

```bash
# Get all worktrees for the repository
git worktree list

# Expected output format:
# /path/to/main-repo      abc1234 [main]
# /path/to/repo-123       def5678 [123-feature-name]
```

### Step 2: Check Each Worktree for Uncommitted Changes

For each worktree (excluding main):

```bash
# Check for uncommitted changes
git -C /path/to/worktree status --porcelain

# If output is non-empty, worktree has uncommitted changes
```

**Finding:** Uncommitted changes in worktree = **HIGH** severity. Work may be lost.

### Step 3: Check Each Worktree for Unique Commits

Compare worktree branch to the base branch:

```bash
# Check how many commits worktree has that main doesn't
git -C /path/to/worktree rev-list --count main..HEAD

# If count is 0, worktree has no unique commits (stale/abandoned)
```

**Finding:** Zero unique commits = **MEDIUM** severity. Worktree was never used.

### Step 4: Check Worktree Age

```bash
# Get creation time of worktree directory
stat -c %Y /path/to/worktree 2>/dev/null || stat -f %m /path/to/worktree

# Compare to current time
# If older than 7 days, flag as potentially stale
```

**Finding:** Worktree older than 7 days = **LOW** severity. May be abandoned.

### Step 5: Check for Orphaned Worktree Directories

Sometimes `git worktree remove` fails or worktrees are deleted manually:

```bash
# List directories that look like worktrees but aren't tracked
ls -d /path/to/projects/{{REPO_NAME}}-* 2>/dev/null | while read dir; do
  if [ -d "$dir/.git" ]; then
    # Check if git worktree list includes this directory
    if ! git worktree list | grep -q "^$dir "; then
      echo "ORPHAN: $dir"
    fi
  fi
done
```

**Finding:** Orphaned worktree directory = **MEDIUM** severity. Cleanup failed.

### Step 6: Check for Missing Remote Branches

Verify the tracking branch still exists on remote:

```bash
# For each worktree, get its tracking branch
git -C /path/to/worktree branch -vv --list | grep '\*' | grep -oP '\[origin/[^\]]+\]'

# Check if that branch exists on remote
git ls-remote --heads origin | grep "branch-name"
```

**Finding:** Worktree tracking deleted remote branch = **MEDIUM** severity. PR was merged but worktree wasn't cleaned up.

---

## Remediation Actions

| Finding | Severity | Action |
|---------|----------|--------|
| Uncommitted changes | HIGH | **INVESTIGATE before removing.** May contain important work. |
| No unique commits | MEDIUM | Safe to remove: `git worktree remove /path/to/worktree` |
| Older than 7 days | LOW | Review and decide: commit changes or remove |
| Orphaned directory | MEDIUM | Manual removal: `rm -rf /path/to/orphan` |
| Missing remote branch | MEDIUM | Cleanup: `git worktree remove /path/to/worktree` |

### Safe Removal Command

```bash
# Remove worktree and delete branch (if safe)
git worktree remove /path/to/worktree
git branch -d branch-name  # -d = safe delete (fails if unmerged)
```

### When `git worktree remove` Refuses

`git worktree remove --force` and `git branch -D` are **banned** fleet-wide
(see `Projects/CLAUDE.md` banned-commands table). Resolve via gentler
means:

```bash
# 1. Cleans admin metadata for dead refs; often unblocks the next remove.
git worktree prune

# 2. Retry the plain remove.
git worktree remove /path/to/worktree
```

If `branch -d` refuses on a squash-merge orphan (different SHA from
the squash commit on main), use the ADR-0217 `git replace --graft`
recipe — never `branch -D`. If the branch still refuses to delete, it
has unmerged work: investigate, do not force.

---

## Auto-Fix Capability

This audit does NOT auto-fix worktrees with uncommitted changes. It DOES auto-report:

| Finding | Auto-Fix | Reason |
|---------|----------|--------|
| Uncommitted changes | NO | May contain valuable work |
| No unique commits | REPORT | Safe but needs confirmation |
| Orphaned directory | NO | May have uncommitted work |
| Missing remote branch | REPORT | Safe but needs confirmation |

**Rationale:** Worktrees with uncommitted changes may contain hours of work. Auto-deletion would be catastrophic.

---

## Output Format

```markdown
## Worktree Hygiene Audit - {DATE}

### Summary
- Active worktrees: N
- Healthy: N
- Issues found: N

### Worktree Status

| Worktree | Branch | Uncommitted | Unique Commits | Age | Remote | Status |
|----------|--------|-------------|----------------|-----|--------|--------|
| /Project-123 | 123-feature | YES (3 files) | 0 | 5 days | EXISTS | STALE |
| /Project-456 | 456-bugfix | NO | 3 | 1 day | EXISTS | HEALTHY |
| /Project-789 | 789-old | NO | 2 | 30 days | DELETED | CLEANUP |

### Issues Found

#### HIGH - Uncommitted Changes
1. `/Project-123` has uncommitted changes:
   - `src/file1.js` (modified)
   - `src/file2.js` (modified)
   - `tests/new.test.js` (untracked)

   **Action Required:** Review changes. Commit or discard.

#### MEDIUM - Stale Worktrees
1. `/Project-123` has 0 unique commits (created but never used)

   **Action:** Safe to remove after verifying no uncommitted changes

#### MEDIUM - Missing Remote
1. `/Project-789` tracks `origin/789-old` but branch no longer exists

   **Action:** PR likely merged. Safe to remove.

### Recommendations
1. Review uncommitted changes in `/Project-123`
2. Remove stale worktree: `git worktree remove /path/to/Project-123`
3. Cleanup merged PR worktree: `git worktree remove /path/to/Project-789`
```

---

## Integration with Cleanup

This audit should be integrated into the cleanup skill:

- `/cleanup --quick`: Skip worktree audit (too slow)
- `/cleanup`: Run worktree audit, REPORT issues
- `/cleanup --full`: Run worktree audit, PROMPT for removal of safe worktrees

---

## Common Patterns

| Pattern | Cause | Prevention |
|---------|-------|------------|
| Uncommitted changes in merged PR worktree | Dev committed from main, forgot worktree | Use `merge_pr.py` script |
| Worktree with 0 commits | Started work, switched to different issue | Cleanup after context switches |
| Orphaned directory | Manual `rm -rf` instead of `git worktree remove` | Always use git worktree commands |
| Very old worktrees | Long-running feature, forgot about branch | Weekly audit |

---

## Audit Record

| Date | Auditor | Findings | Issues |
|------|---------|----------|--------|
| | | | |

---

## History

| Date | Change |
|------|--------|
| 2026-01-18 | Created (from Aletheia audit finding: stale Aletheia-331 worktree with uncommitted changes). |

