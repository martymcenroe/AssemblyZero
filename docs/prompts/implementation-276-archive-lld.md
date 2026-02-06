# Implementation Prompt: Issue #276 - Archive LLD on Issue Close

**Purpose:** Guide an agent implementing the GitHub Action for LLD archival.

---

## Context

Issue #276 identifies that LLDs remain in `docs/lld/active/` when issues are closed outside the TDD workflow. The solution is a GitHub Action triggered on issue close.

**This is a no-LLD issue** - straightforward infrastructure work.

---

## Pre-Implementation Checklist

- [ ] Read issue #276 and the analysis comment
- [ ] Confirm the recommended approach (GitHub Action)
- [ ] Check if `.github/workflows/` directory exists

---

## Worktree Setup

**MANDATORY:** All code changes happen in a worktree.

```bash
git worktree add ../AssemblyZero-276 -b 276-archive-lld-action
git -C ../AssemblyZero-276 push -u origin HEAD
```

---

## Implementation

### 1. Create the GitHub Action

Create `.github/workflows/archive-lld.yml`:

```yaml
name: Archive LLD on Issue Close

on:
  issues:
    types: [closed]

jobs:
  archive:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Archive LLD if exists
        run: |
          ISSUE=${{ github.event.issue.number }}
          LLD="docs/lld/active/LLD-${ISSUE}.md"

          if [ -f "$LLD" ]; then
            mkdir -p docs/lld/done
            mv "$LLD" "docs/lld/done/"

            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            git add docs/lld/
            git commit -m "chore: archive LLD-${ISSUE} [skip ci]"
            git push
            echo "Archived LLD-${ISSUE}"
          else
            echo "No LLD found for issue ${ISSUE}"
          fi
```

### 2. Consider Edge Cases

Ask the user before handling these:

1. **Lineage files** - Should `docs/lineage/active/{issue}-*/` also be archived?
2. **Reports** - Should `docs/reports/active/{issue}-*.md` also be archived?
3. **Reopened issues** - Should there be an `issues: reopened` trigger to move back to active?

### 3. Test Locally (Optional)

Use `act` to test GitHub Actions locally:
```bash
act issues -e test-event.json
```

---

## Definition of Done

- [ ] `.github/workflows/archive-lld.yml` created
- [ ] Action triggers on `issues: closed`
- [ ] Archives LLD from `active/` to `done/`
- [ ] Commits with `[skip ci]` to prevent loops
- [ ] PR created with test plan

---

## Creating the PR

```bash
git add .github/workflows/archive-lld.yml
git commit -m "feat: add GitHub Action to archive LLDs on issue close (#276)

Automatically moves LLD-{N}.md from docs/lld/active/ to docs/lld/done/
when issue N is closed.

Closes #276

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git push
gh pr create --title "feat: archive LLDs on issue close (#276)" --body "$(cat <<'EOF'
## Summary

Adds a GitHub Action that automatically archives LLDs when issues are closed.

- Triggers on `issues: closed` event
- Moves `docs/lld/active/LLD-{N}.md` to `docs/lld/done/`
- Uses `[skip ci]` to prevent workflow loops

## Test Plan

- [ ] Close a test issue that has an LLD in `active/`
- [ ] Verify LLD is moved to `done/`
- [ ] Verify commit is created by github-actions[bot]
- [ ] Close an issue without an LLD - verify no error

Closes #276

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Post-Merge Cleanup

```bash
git checkout main
git pull
git worktree remove ../AssemblyZero-276
git branch -d 276-archive-lld-action
```
