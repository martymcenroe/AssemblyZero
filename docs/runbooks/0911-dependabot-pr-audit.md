# 0911 - Dependabot PR Audit

**Category:** Runbook / Security Maintenance
**Version:** 1.0
**Last Updated:** 2026-02-01

---

## Purpose

Safely merge Dependabot PRs with regression verification. Dependency updates are merged automatically when tests pass, with automatic rollback when problems occur.

**Key Principle:** Trust exit codes, not LLM interpretation of test output.

---

## Prerequisites

| Requirement | Check |
|-------------|-------|
| Clean working directory | `git status` shows no changes |
| On main branch | `git branch --show-current` |
| Poetry environment | `poetry run python --version` |
| GitHub CLI authenticated | `gh auth status` |

---

## Quick Reference

```bash
# List Dependabot PRs
gh pr list --author "app/dependabot" --json number,title

# List security alerts
gh api repos/OWNER/REPO/dependabot/alerts --jq '.[] | select(.state=="open")'

# Run tests with exit code capture
poetry run pytest; echo "EXIT_CODE=$?"
```

---

## Procedure

### Phase 1: Baseline

```bash
# 1.1 Ensure clean state
git checkout main
git pull origin main
git status  # Must be clean

# 1.2 Run baseline tests - CAPTURE EXIT CODE
poetry run pytest --tb=short -q
BASELINE_EXIT=$?
echo "BASELINE_EXIT=$BASELINE_EXIT"

# 1.3 Capture test count
poetry run pytest --collect-only -q 2>/dev/null | tail -1
```

**STOP if baseline fails (exit code != 0).** Fix existing issues first.

### Phase 2: Identify PRs

```bash
# 2.1 List Dependabot PRs
gh pr list --author "app/dependabot" --json number,title,headRefName

# 2.2 List security alerts (for context)
gh api repos/OWNER/REPO/dependabot/alerts \
  --jq '.[] | select(.state=="open") | "\(.number) | \(.security_advisory.severity) | \(.dependency.package.name)"'

# 2.3 Store PR numbers
DEPENDABOT_PRS=$(gh pr list --author "app/dependabot" --json number --jq '.[].number' | tr '\n' ' ')
echo "PRs to process: $DEPENDABOT_PRS"
```

**PASS immediately if no PRs exist.**

### Phase 3: Merge and Test

```bash
# 3.1 For each PR, merge and test
for PR in $DEPENDABOT_PRS; do
    echo "=== Processing PR #$PR ==="

    # Approve (for GitHub contribution credit) then merge
    gh pr review $PR --approve --body "Automated review: baseline tests pass, proceeding with merge."
    gh pr merge $PR --merge
    git pull origin main

    # Test - CAPTURE EXIT CODE
    poetry run pytest --tb=short -q
    POST_MERGE_EXIT=$?
    echo "POST_MERGE_EXIT=$POST_MERGE_EXIT"

    # If failed, revert immediately
    if [ $POST_MERGE_EXIT -ne 0 ]; then
        echo "REGRESSION DETECTED - Reverting PR #$PR"
        git revert HEAD --no-edit
        git push origin main

        # Comment on PR
        gh pr comment $PR --body "❌ Automated regression detected. Merge reverted. Manual investigation required."

        # Create issue
        gh issue create \
            --title "Dependabot PR #$PR causes regression" \
            --body "PR #$PR was merged but caused test failures. Reverted automatically." \
            --label "dependencies,regression,bug"
    else
        echo "PR #$PR merged successfully - tests pass"
    fi
done
```

### Phase 4: Verify Final State

```bash
# 4.1 Final test run
poetry run pytest --tb=short -q
FINAL_EXIT=$?

# 4.2 Compare with baseline
echo "Baseline exit: $BASELINE_EXIT"
echo "Final exit: $FINAL_EXIT"

# 4.3 Check remaining alerts
gh api repos/OWNER/REPO/dependabot/alerts \
  --jq '[.[] | select(.state=="open")] | length'
```

---

## Decision Tree

```
Baseline passes?
├── No → ABORT: Fix existing issues first
└── Yes → Any Dependabot PRs?
    ├── No → PASS: No action needed
    └── Yes → For each PR:
        ├── Merge and test
        ├── Tests pass? → Keep merged
        └── Tests fail? → Revert, comment, create issue
```

---

## Automation Status

**Current:** Manual procedure (this runbook)

**Planned:** LangGraph workflow (see brief: Issue #TBD)
- Programmatic exit code verification
- No LLM interpretation of "passed" / "failed"
- Structured state machine for rollback

---

## Integration

Run this audit:
- Before Security Audit (0809)
- Weekly as maintenance
- When Dependabot alerts accumulate

---

## Audit Record

| Date | Auditor | PRs Processed | Outcome | Issues Created |
|------|---------|---------------|---------|----------------|
| | | | | |

---

## References

- `.claude/templates/docs/dependabot-audit.md` - Original template
- `docs/audits/0812-ai-supply-chain.md` - Supply chain context
- GitHub Dependabot documentation

---

*Template source: AssemblyZero/.claude/templates/docs/dependabot-audit.md*
