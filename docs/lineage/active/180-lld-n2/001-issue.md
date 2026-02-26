---
repo: martymcenroe/AgentOS
issue: 180
url: https://github.com/martymcenroe/AgentOS/issues/180
fetched: 2026-02-04T06:29:57.329738Z
---

# Issue #180: feat: N9 Cleanup Node - Worktree removal, lineage archival, and learning summary

## Summary

The implementation workflow (N0-N8) ends at N8_document but leaves cleanup tasks undone:
- Worktree remains after PR is merged
- Lineage stays in `active/` forever
- No distilled summary for learning agents

## Current State

```
N7_finalize → N8_document → END
                              ↓
                    Worktree orphaned
                    Lineage stuck in active/
                    64+ artifact files with no summary
```

## Proposed: N9_cleanup Node

```
N8_document → N9_cleanup → END
                  ↓
            1. Remove worktree (if PR merged)
            2. Move lineage active/ → done/
            3. Generate learning summary
```

## Requirements

### 1. Worktree Removal (Post-Merge)

After successful PR merge:
```python
def cleanup_worktree(state):
    worktree_path = state.get("worktree_path")
    if worktree_path and is_pr_merged(state):
        # git worktree remove {path}
        # git branch -d {branch}
        # Log cleanup
```

**Safety:** Only remove if PR is confirmed merged. If PR still open, log and skip.

### 2. Lineage Archival

Move from `docs/lineage/active/{issue}-testing/` to `docs/lineage/done/`:
```python
def archive_lineage(state):
    issue_number = state.get("issue_number")
    active_dir = repo_root / "docs" / "lineage" / "active" / f"{issue_number}-testing"
    done_dir = repo_root / "docs" / "lineage" / "done" / f"{issue_number}-testing"
    if active_dir.exists():
        shutil.move(active_dir, done_dir)
```

### 3. Learning Summary Generation (for Learning Agent)

The lineage contains 64+ files per implementation run:
- `001-lld.md` through `064-failed-response-full.md`
- Prompts, responses, test scaffolds, phase outputs, implementation files

**A learning agent needs a distilled summary, not raw artifacts.**

Generate `{issue}-learning-summary.md`:

```markdown
# Learning Summary: Issue #{issue}

## Outcome
- **Result:** SUCCESS/FAILURE
- **Coverage:** 98% (target: 90%)
- **Iterations:** 5
- **Stall detected:** Yes, at iteration 3 (88% → 88%)

## What Worked
- Initial test scenarios 010-090 from LLD
- Implementation approach for archive_file_to_done()

## What Didn't Work
- Missing test scenarios for finalize() success path
- Original LLD test plan only tested failure cases

## Coverage Gap Analysis
| Iteration | Coverage | Missing Lines | Root Cause |
|-----------|----------|---------------|------------|
| 1 | 85% | 287-301, 218 | finalize() success path untested |
| 2 | 85% | 287-301, 218 | Same - no new scenarios |
| 3 | 88% | 287-301 | Added E2E test, still missing success path |

## Key Artifacts
- `005-test-scaffold.py` - Initial test file
- `008-implementation-response.md` - First working implementation
- `052-green-phase.txt` - Final passing tests

## Recommendations for Similar Issues
1. Always test both success and failure branches of conditional logic
2. Check that wrapper functions are tested, not just low-level helpers
3. If coverage stalls, analyze missing lines directly (not just scenarios)
```

### 4. Learning Agent Integration (Future)

The learning summaries feed into a learning agent that:
1. Reads past summaries from `docs/lineage/done/*/learning-summary.md`
2. Identifies patterns in what causes stalls
3. Improves LLD test plan generation based on past failures
4. Suggests test scenarios that were historically missing

This connects to Issue #177 (coverage-driven test planning) - the learning agent can proactively suggest scenarios based on historical gaps.

## Implementation

### New Node: `agentos/workflows/testing/nodes/cleanup.py`

```python
def cleanup(state: TestingWorkflowState) -> dict[str, Any]:
    """N9: Post-implementation cleanup.
    
    1. Check if PR is merged
    2. Remove worktree if merged
    3. Archive lineage to done/
    4. Generate learning summary
    """
    ...
```

### Graph Update: `agentos/workflows/testing/graph.py`

```python
# Add N9
workflow.add_node("N9_cleanup", cleanup)

# N8 → N9 (new edge)
workflow.add_conditional_edges(
    "N8_document",
    route_after_document,
    {
        "N9_cleanup": "N9_cleanup",
        "end": END,
    },
)

# N9 → END
workflow.add_edge("N9_cleanup", END)
```

### State Additions

```python
class TestingWorkflowState(TypedDict, total=False):
    # ... existing fields ...
    pr_url: str  # For merge status check
    pr_merged: bool  # Set by N9 after checking
    learning_summary_path: str  # Generated summary location
```

## Acceptance Criteria

- [ ] N9 node added to workflow graph after N8
- [ ] Worktree removed only if PR confirmed merged
- [ ] Lineage moved from active/ to done/ on success
- [ ] Learning summary generated with outcome, gaps, recommendations
- [ ] Summary format documented for learning agent consumption
- [ ] Skip cleanup gracefully if PR not yet merged (log, don't fail)

## Dependencies

- #141 - Archive LLD/reports to done/ (handles LLD, this handles lineage)
- #177 - Coverage-driven test planning (consumes learning summaries)
- #139 - Rename workflows/testing/ to workflows/implementation/

## Out of Scope (Future)

- Learning agent that reads summaries (separate issue)
- Automatic LLD improvement based on patterns (separate issue)
- Cross-issue pattern detection (separate issue)

## Files to Create/Modify

| File | Change |
|------|--------|
| `agentos/workflows/testing/nodes/cleanup.py` | New - N9 implementation |
| `agentos/workflows/testing/nodes/__init__.py` | Export cleanup |
| `agentos/workflows/testing/graph.py` | Add N9 node and edges |
| `agentos/workflows/testing/state.py` | Add pr_url, pr_merged, learning_summary_path |

## Related Issues

- #141 - LLD/report archival (complementary, not duplicate)
- #94 - Lu-Tze general hygiene (runs separately, not in workflow)
- #100 - Lineage standardization during workflow
- #177 - Coverage-driven test planning (consumer of learning summaries)