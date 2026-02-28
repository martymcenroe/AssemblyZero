# Governance Pipeline Vision

**Created:** 2026-02-01
**Status:** Draft
**Related Issues:** #77, #87, #101, #102

---

## Executive Summary

The AssemblyZero Governance Pipeline is a four-stage workflow system that transforms ideas into production-ready code through AI-assisted design, human oversight, and automated testing. Each stage is a LangGraph workflow that enforces quality gates before progressing.

---

## The Four Stages

```
STAGE 1: IDEATION     Brief → Issue     (issue workflow - COMPLETE)
STAGE 2: DESIGN       Issue → LLD       (LLD workflow - COMPLETE)
STAGE 3: BUILD        LLD → Code        (testing workflow - THIS PLAN)
STAGE 4: LEARN        Feedback Loop     (#77 - FUTURE)
```

### Stage 1: Ideation (Brief → Issue)

**Workflow:** `assemblyzero/workflows/issue/`
**Status:** Complete and Production

Transforms rough ideas captured in markdown briefs into well-structured GitHub issues:
- Claude drafts the issue from the brief
- Gemini reviews for clarity, completeness, and actionability
- Human approves or requests revisions
- Filed to GitHub when approved

**Key Artifact:** GitHub Issue with labels, acceptance criteria

### Stage 2: Design (Issue → LLD)

**Workflow:** `assemblyzero/workflows/lld/`
**Status:** Complete and Production

Transforms GitHub issues into Low-Level Design documents:
- Claude generates LLD from issue requirements
- Gemini reviews for technical soundness and completeness
- Human reviews and edits
- LLD saved to `docs/lld/active/` when approved

**Key Artifact:** LLD markdown with review evidence

### Stage 3: Build (LLD → Code)

**Workflow:** `assemblyzero/workflows/testing/` (THIS IMPLEMENTATION)
**Status:** In Development

Transforms approved LLDs into tested, production-ready code:
1. Load LLD and extract test plan from Section 10
2. Gemini reviews test plan for coverage and validity
3. Scaffold executable test stubs (TDD red phase)
4. Verify all tests fail (no pre-existing implementation)
5. Claude generates implementation to pass tests
6. Verify all tests pass with coverage target
7. E2E validation in sandbox environment
8. Generate test report

**Key Artifacts:** Test files, implementation code, test report

### Stage 4: Learn (Feedback Loop)

**Workflow:** Future (#77)
**Status:** Not Started

Closes the loop by learning from completed work:
- Analyze what worked and what didn't
- Update prompt templates based on common feedback
- Identify patterns in Gemini rejections
- Feed lessons back into Stages 1-3

---

## Stage Handoffs

### Stage 1 → Stage 2

**Trigger:** Issue filed to GitHub
**Handoff Data:**
- `issue_number`: GitHub issue ID
- Issue title and body accessible via `gh issue view`

**How to Start Stage 2:**
```bash
python tools/run_lld_workflow.py --issue <issue_number>
```

### Stage 2 → Stage 3

**Trigger:** LLD approved and saved to `docs/lld/active/LLD-{N}.md`
**Handoff Data:**
- `issue_number`: Links to both LLD and original issue
- LLD content with test plan in Section 10

**How to Start Stage 3:**
```bash
python tools/run_implement_from_lld.py --issue <issue_number>
```

### Stage 3 → Stage 4

**Trigger:** Code merged and test report generated
**Handoff Data:**
- Test report: `docs/reports/active/{issue}-test-report.md`
- Implementation report: `docs/reports/active/{issue}-implementation-report.md`
- Audit trail in `docs/lineage/active/{issue}-testing/`

---

## Architecture Patterns

### Shared Patterns Across All Stages

1. **TypedDict State:** Each workflow uses a TypedDict for state
2. **Sequential Audit Trail:** Files numbered NNN-artifact.md
3. **Human Gates:** VS Code opens for review before proceeding
4. **Gemini Governance:** Independent LLM reviews Claude's work
5. **Mode Flags:** `auto_mode` and `mock_mode` for testing
6. **Cross-Repo Support:** `repo_root` parameter in state
7. **Checkpoint/Resume:** SqliteSaver for crash recovery

### Stage-Specific Patterns

| Pattern | Stage 1 | Stage 2 | Stage 3 |
|---------|---------|---------|---------|
| Input | Brief file | GitHub issue | LLD file |
| Output | GitHub issue | LLD file | Code + tests |
| LLM for drafting | Claude | Claude | Claude |
| LLM for review | Gemini | Gemini | Gemini |
| Human gates | 2 (draft, verdict) | 1 (edit) | 1 (test plan) |
| Nodes | 7 (N0-N6) | 5 (N0-N4) | 8 (N0-N7) |

---

## Future: Unified Mega-Workflow

Currently, each stage is invoked separately. Future vision:

```bash
# Today: Run each stage manually
python tools/run_issue_workflow.py --brief my-idea.md
# Wait, review, approve...
python tools/run_lld_workflow.py --issue 42
# Wait, review, approve...
python tools/run_implement_from_lld.py --issue 42

# Future: Single command
python tools/run_governance_pipeline.py --brief my-idea.md
# Orchestrator handles all stages with appropriate human gates
```

### Considerations for Unification

1. **Human Gate Aggregation:** How many reviews is too many?
2. **Failure Modes:** What happens if Stage 2 is approved but Stage 3 fails?
3. **Checkpoint Granularity:** One checkpoint per stage or per node?
4. **Parallel Execution:** Can Stage 4 learn while Stage 3 builds?

---

## Naming Conventions

### Workflow Directories

```
assemblyzero/workflows/
├── issue/      # Stage 1: Brief → Issue
├── lld/        # Stage 2: Issue → LLD
└── testing/    # Stage 3: LLD → Code (this implementation)
```

### CLI Tools

```
tools/
├── run_issue_workflow.py      # Stage 1
├── run_lld_workflow.py        # Stage 2
└── run_implement_from_lld.py    # Stage 3
```

### Audit Directories

```
docs/lineage/active/
├── {slug}/            # Stage 1 audit trail
├── {issue}-lld/       # Stage 2 audit trail
└── {issue}-testing/   # Stage 3 audit trail
```

### Reports

```
docs/reports/active/
├── {issue}-implementation-report.md
└── {issue}-test-report.md
```

---

## Related Issues

| Issue | Stage | Description |
|-------|-------|-------------|
| #62 | 1 | Issue creation workflow |
| #86 | 2 | LLD governance workflow |
| #101 | 3 | Test plan reviewer |
| #102 | 3 | TDD initialization |
| #87 | 3 | Implementation workflow (autonomous coding) |
| #77 | 4 | Lessons learned feedback loop |

---

## Implementation Priority

1. **Now:** Stage 3 (testing workflow) - This plan
2. **Soon:** Integration with #87 for N4 (implement_code)
3. **Later:** Stage 4 (#77) for continuous improvement
4. **Future:** Unified mega-workflow
