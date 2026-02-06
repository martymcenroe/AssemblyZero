# Dependabot PR Audit

## 1. Purpose

Automated process to safely merge pending Dependabot PRs with regression verification. This audit ensures dependency updates don't break the build while minimizing manual intervention.

**Key Principle:** Dependency updates are merged automatically when safe, with automatic rollback and issue creation when problems occur.

---

## 2. Trigger Conditions

| Trigger | Context |
|---------|---------|
| **Pre-Security Audit** | MUST run before Security Audit |
| **Weekly** | Part of regular maintenance |
| **On Demand** | When Dependabot PRs accumulate or security concern arises |

---

## 3. Procedure

### Phase 1: Baseline

```bash
# 1.1 Ensure clean working directory
cd {{PROJECT_ROOT}}
git checkout main
git pull origin main
git status  # Must be clean

# 1.2 Run full regression test (baseline)
# Adjust test command for your project
poetry run pytest --tb=short 2>&1 | tee /tmp/baseline-test.log
# OR: npm test 2>&1 | tee /tmp/baseline-test.log

BASELINE_EXIT=$?
```

**Stop Condition:** If baseline tests fail, abort audit and fix existing issues first.

### Phase 2: Identify Dependabot PRs

```bash
# 2.1 List all open Dependabot PRs
gh pr list --repo {{GITHUB_REPO}} --author "app/dependabot" --json number,title,headRefName \
  --jq '.[] | "\(.number) | \(.title) | \(.headRefName)"'

# 2.2 Store PR numbers for processing
DEPENDABOT_PRS=$(gh pr list --repo {{GITHUB_REPO}} --author "app/dependabot" --json number --jq '.[].number' | tr '\n' ' ')
echo "Dependabot PRs to process: $DEPENDABOT_PRS"
```

**Stop Condition:** If no Dependabot PRs, audit passes immediately.

### Phase 3: Batch Merge Attempt

```bash
# 3.1 Merge all Dependabot PRs
for PR in $DEPENDABOT_PRS; do
    echo "Merging PR #$PR..."
    gh pr merge $PR --repo {{GITHUB_REPO}} --merge --auto
done

# 3.2 Wait for merges to complete
sleep 10
git pull origin main

# 3.3 Run full regression test (post-merge)
poetry run pytest --tb=short 2>&1 | tee /tmp/postmerge-test.log
# OR: npm test 2>&1 | tee /tmp/postmerge-test.log
```

### Phase 4: Compare Results

Compare baseline vs post-merge test counts. If identical, audit passes.

If regression detected, proceed to Phase 5.

### Phase 5: Rollback and Isolate

```bash
# 5.1 Revert all Dependabot merges
REVERT_TO=$(git log --oneline | grep -v "dependabot\|Bump" | head -1 | cut -d' ' -f1)
git revert --no-commit HEAD...$REVERT_TO
git commit -m "chore: revert Dependabot batch merge due to regression"
git push origin main
```

### Phase 6: One-by-One Merge

Merge each PR individually, testing after each:

```bash
for PR in $DEPENDABOT_PRS; do
    echo "=== Testing PR #$PR in isolation ==="

    # Merge single PR
    gh pr merge $PR --repo {{GITHUB_REPO}} --merge
    git pull origin main

    # Run regression test
    poetry run pytest --tb=short

    # If regression, revert and create issue
    if [ REGRESSION ]; then
        git revert HEAD --no-edit
        git push origin main

        gh pr comment $PR --repo {{GITHUB_REPO}} --body "Automated regression detected. Merge reverted."

        gh issue create --repo {{GITHUB_REPO}} \
            --title "Dependabot PR #$PR causes regression" \
            --body "Details..." \
            --label "dependencies,regression"
    fi
done
```

---

## 4. Decision Tree

```
Baseline passes?
├── No → ABORT: Fix existing issues
└── Yes → Any Dependabot PRs?
    ├── No → PASS: No action needed
    └── Yes → Merge ALL, test again
        ├── Results identical? → PASS: All merged
        └── Regression? → Revert, merge one-by-one
            ├── PR passes → Keep merged
            └── PR fails → Revert, comment, create issue
```

---

## 5. Integration

This audit is a **prerequisite** for Security Audit. Run before vulnerability analysis to ensure clean dependency baseline.

---

*Template from: AssemblyZero/.claude/templates/docs/dependabot-audit.md*
