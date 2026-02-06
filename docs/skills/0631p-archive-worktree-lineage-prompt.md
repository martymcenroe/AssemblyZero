# archive-worktree-lineage - Prompt Usage

**File:** `docs/skills/0631p-archive-worktree-lineage-prompt.md`
**CLI Guide:** [0631c-archive-worktree-lineage-cli.md](0631c-archive-worktree-lineage-cli.md)
**Version:** 2026-02-03
**Issue:** #189

---

## Quick Reference

This is a CLI tool, not a slash command. Use it as part of post-merge cleanup.

```
# After merging a PR, run:
python tools/archive_worktree_lineage.py --worktree ../AssemblyZero-{ID} --issue {ID}
```

---

## When Claude Should Use This

Claude should run this tool automatically as part of post-merge cleanup when:

1. A PR has just been merged
2. There's a worktree to clean up
3. The worktree may contain lineage data

---

## Integration with Post-Merge Cleanup

When the user says "merge the PR" and Claude merges it, the post-merge cleanup should include:

```python
# Step 1: Archive lineage (NEW - Issue #189)
python tools/archive_worktree_lineage.py --worktree ../AssemblyZero-{ID} --issue {ID}

# Step 2: Remove worktree
git worktree remove ../AssemblyZero-{ID}

# Step 3: Delete local branch
git branch -d {ID}-desc

# Step 4: Pull merged changes
git pull
```

---

## Example Conversation

**User:** merge the PR

**Claude:**
```
PR merged. Executing post-merge cleanup:

**Bash Check:** `python tools/archive_worktree_lineage.py --worktree ../AssemblyZero-155 --issue 155`
**Scan:** No &&, no |, no ;, no cd at start → CLEAN
**Friction Risk:** LOW
**Action:** Execute

[runs archive tool]

**Bash Check:** `git worktree remove ../AssemblyZero-155`
**Scan:** No &&, no |, no ;, no cd at start → CLEAN
**Friction Risk:** LOW
**Action:** Execute

[removes worktree]

Done. PR merged and cleanup complete.
- ✅ Lineage archived to docs/lineage/archived/155-*/
- ✅ Worktree removed
- ✅ Branch deleted
- ✅ Main updated
```

---

## What Gets Preserved

The tool preserves iteration history that helps with:

- **Workflow analysis:** How many drafts/reviews before approval?
- **Pattern mining:** Common failure modes in reviews
- **Improvement measurement:** Are iterations decreasing over time?

---

## Manual vs Automatic

| Scenario | Recommendation |
|----------|----------------|
| Standard PR merge | Claude runs automatically |
| Need to inspect first | Use `--no-commit` flag |
| No lineage exists | Tool handles gracefully |
| Want to skip entirely | Just don't run the tool |

---

## Related Documentation

- CLI details: [0631c-archive-worktree-lineage-cli.md](0631c-archive-worktree-lineage-cli.md)
- CLAUDE.md: POST-MERGE CLEANUP section
- Tool source: `tools/archive_worktree_lineage.py`
