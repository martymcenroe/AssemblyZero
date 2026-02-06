# Brief: Dependabot PR Workflow Automation

**Status:** Brief
**Priority:** High (security maintenance)
**Created:** 2026-02-01

---

## Problem Statement

LLMs hallucinate about test results. When asked "did tests pass?", they may claim success based on output interpretation rather than exit codes. This is dangerous for security-related dependency updates.

Current state: Manual runbook (0911) requires human to run commands and verify exit codes.

---

## Proposed Solution

A LangGraph workflow that:
1. Runs tests via subprocess with exit code capture (not output parsing)
2. Makes merge/revert decisions based on integer comparison (exit_code == 0)
3. Maintains structured state for audit trail
4. Never asks an LLM "did this pass?"

---

## Key Design Principles

### 1. Exit Codes Are Truth

```python
# CORRECT - Programmatic verification
result = subprocess.run(["poetry", "run", "pytest"], capture_output=True)
passed = result.returncode == 0

# WRONG - LLM interpretation
# "The tests appear to have passed based on the output..."
```

### 2. Structured State Machine

```python
class DependabotWorkflowState(TypedDict):
    baseline_exit_code: int | None
    baseline_test_count: int | None
    prs_to_process: list[int]
    current_pr: int | None
    post_merge_exit_code: int | None
    merged_prs: list[int]
    reverted_prs: list[int]
    created_issues: list[int]
    phase: Literal["baseline", "identify", "merge", "verify", "complete"]
```

### 3. No LLM in Critical Path

The workflow should NOT use LLM for:
- Determining if tests passed
- Deciding whether to merge/revert
- Parsing test output for pass/fail

The workflow MAY use LLM for:
- Generating issue descriptions
- Summarizing what happened for the user
- Suggesting manual investigation steps

---

## Workflow Graph

```
N0_baseline
    ↓
    ├── exit_code != 0 → END (abort)
    └── exit_code == 0 → N1_identify_prs
                            ↓
                            ├── no PRs → END (pass)
                            └── has PRs → N2_merge_pr
                                            ↓
                                            N3_test_post_merge
                                            ↓
                                            ├── exit_code != 0 → N4_revert_pr → N2_merge_pr (next)
                                            └── exit_code == 0 → N2_merge_pr (next)
                                            ↓
                                        N5_final_verify
                                            ↓
                                        END
```

---

## Implementation Notes

### Test Count Verification (Optional)

Beyond exit codes, can verify test counts didn't decrease:

```python
def get_test_count() -> int:
    result = subprocess.run(
        ["poetry", "run", "pytest", "--collect-only", "-q"],
        capture_output=True, text=True
    )
    # Parse "X items" from last line
    match = re.search(r"(\d+) items?", result.stdout.split('\n')[-2])
    return int(match.group(1)) if match else 0
```

### GitHub CLI Integration

```python
def merge_pr(pr_number: int) -> bool:
    result = subprocess.run(
        ["gh", "pr", "merge", str(pr_number), "--merge"],
        capture_output=True
    )
    return result.returncode == 0

def revert_last_commit() -> bool:
    result = subprocess.run(
        ["git", "revert", "HEAD", "--no-edit"],
        capture_output=True
    )
    if result.returncode == 0:
        subprocess.run(["git", "push", "origin", "main"])
    return result.returncode == 0
```

### Audit Trail

Every state transition should be logged:

```python
{
    "timestamp": "2026-02-01T15:30:00Z",
    "phase": "merge",
    "pr": 66,
    "action": "merge_attempted",
    "exit_code": 0,
    "decision": "keep_merged"
}
```

---

## Acceptance Criteria

1. [ ] Workflow runs without human intervention
2. [ ] All pass/fail decisions based on exit codes only
3. [ ] Reverts happen automatically on regression
4. [ ] Issues created for failed PRs
5. [ ] Full audit trail in lineage folder
6. [ ] No LLM interpretation of test output in decision path

---

## Dependencies

- LangGraph StateGraph
- subprocess (Python stdlib)
- gh CLI
- poetry

---

## Estimated Complexity

Medium - Similar to TDD workflow but simpler (no LLM-generated code, just orchestration)

---

## References

- `docs/runbooks/0911-dependabot-pr-audit.md` - Manual procedure
- `assemblyzero/workflows/testing/` - Similar workflow pattern
- GitHub Dependabot API docs
