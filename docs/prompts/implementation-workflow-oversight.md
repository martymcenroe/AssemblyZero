# Implementation Workflow Oversight Prompt

**Purpose:** Guide an agent overseeing manual implementation of an LLD through the testing workflow.

---

## Context

You are overseeing the implementation of a feature from an approved LLD. The user (orchestrator) will provide the issue number. Your job is to:

1. Verify the LLD is ready
2. Create a worktree and implement the feature
3. Run appropriate tests
4. Handle issues as they arise
5. Create a PR when done

---

## Pre-Implementation Checklist

Before writing any code:

- [ ] **Read the LLD** at `docs/lld/active/LLD-{N}.md`
- [ ] **Verify LLD status** is APPROVED (check Review Log at bottom)
- [ ] **Confirm with user** that the LLD is final and won't be regenerated
- [ ] **Check for template/prompt changes** in the LLD's Files Changed - if the LLD modifies templates used to generate OTHER LLDs, flag this to the user as a bootstrapping concern

---

## Worktree Setup

**MANDATORY:** All code changes happen in a worktree.

```bash
git worktree add ../AssemblyZero-{IssueID} -b {IssueID}-short-description
git -C ../AssemblyZero-{IssueID} push -u origin HEAD
```

---

## Implementation Approach

### 1. Follow TDD from the LLD

The LLD Section 10.0 contains the test plan. Write tests FIRST:

```bash
# Create test file per LLD Section 10
# Tests should initially FAIL (RED phase)
poetry run pytest tests/unit/test_{module}.py -v
```

### 2. Implement Code

Follow LLD Sections 2.1-2.7 exactly:
- Files Changed (2.1)
- Data Structures (2.3)
- Function Signatures (2.4)
- Logic Flow (2.5)

### 3. Verify Tests Pass

```bash
# GREEN phase - tests should now pass
poetry run pytest tests/unit/test_{module}.py -v
```

---

## Testing Strategy

**DO:**
- Run new/modified test files (~seconds)
- Run related test files if changes affect them (~seconds)
- Run unit tests if quick: `pytest tests/unit/ -q` (~10 seconds)

**DO NOT:**
- Run full regression locally (that's CI's job)
- Set timeouts over 60 seconds for test commands
- Block waiting for long-running tests

**If tests take longer than expected:** Run in background, check results, move on. Don't sit waiting.

---

## When Issues Arise

**ALWAYS ask the user before:**
- Fixing bugs discovered during implementation (open issue or fix on spot?)
- Deviating from the LLD design
- Making changes to files not listed in the LLD
- Skipping any Definition of Done items

**Pattern:**
> "I found [issue]. Should I:
> 1. Fix it now as part of this PR, or
> 2. Open a separate issue to track it?"

---

## Definition of Done

Before creating PR, verify LLD Section 12:

- [ ] All code changes from Section 2.1 complete
- [ ] All tests from Section 10 pass
- [ ] Documentation updates (if any in Section 2.1)
- [ ] Code comments reference the issue number

---

## Creating the PR

```bash
git add [specific files]
git commit -m "feat: description (#IssueID)

[summary of changes]

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git push
gh pr create --title "..." --body "..."
```

**PR body should include:**
- Summary of changes
- Test plan with checkboxes
- `Closes #{IssueID}`

---

## Post-Merge Cleanup

After PR is merged:

```bash
git -C /path/to/main pull
git worktree remove ../AssemblyZero-{IssueID}
git branch -d {IssueID}-short-description
```

---

## Common Pitfalls

| Pitfall | Prevention |
|---------|------------|
| LLD changes mid-implementation | Confirm LLD is final before starting |
| Running full regression locally | Trust CI, run targeted tests only |
| Long blocking waits | Use short timeouts, check progress, move on |
| Fixing unrelated bugs inline | Ask user first - usually should be separate issue |
| Modifying templates that generate LLDs | Flag bootstrapping concern to user |
| Implementing from wrong LLD version | Always read fresh from `docs/lld/active/` |

---

## Gemini Reviews

**You do NOT call Gemini.** The orchestrator (user) handles all Gemini submissions.

If the LLD shows status other than APPROVED, stop and ask the user about it.
