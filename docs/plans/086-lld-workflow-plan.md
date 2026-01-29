# Plan: Write LLD for Issue #86 (LLD Creation & Governance Review Workflow)

## Objective

Write a Low-Level Design document for issue #86 that will pass Gemini review using the 0702c evaluation standard.

## Pre-Flight Gate Checklist (Must Pass)

Before submitting to Gemini, the LLD must have:
- [ ] GitHub Issue Link - `#86`
- [ ] Context/Scope Section - Section 1
- [ ] Proposed Changes Section - Section 2

## Tier 1 Checklist (Must Address)

### Cost
- [ ] Model tier selection justified (Claude for drafting, Gemini for review)
- [ ] Loop bounds defined (max 5 iterations)
- [ ] API call volume minimized (designer runs once, only review loops)
- [ ] Token budget defined

### Safety
- [ ] Worktree scope - All file operations scoped to project
- [ ] Destructive acts - None planned (creates files, doesn't delete)
- [ ] Permission friction - Document VS Code `--wait` behavior
- [ ] Fail-safe strategy - Fail closed with checkpoint preservation

### Security
- [ ] Secrets management - Uses existing env vars (GITHUB_TOKEN, GEMINI_API_KEY)
- [ ] Input validation - Issue number validated, file paths sanitized

### Legal
- [ ] Privacy - No PII handling, local processing only
- [ ] License compliance - All dependencies MIT/Apache compatible

## Tier 2 Checklist (Should Address)

### Architecture
- [ ] Design patterns - Follows issue workflow patterns
- [ ] Dependencies - Reuses designer.py, governance.py
- [ ] Mock mode - Fixture-based testing defined
- [ ] Interface correctness - Node signatures match LangGraph conventions

### Observability
- [ ] Logging strategy - State transitions logged
- [ ] LangSmith tracing - Optional, configurable

### Quality
- [ ] Test strategy - Unit + integration tests
- [ ] Willison protocol - Tests fail if implementation reverted
- [ ] Test fixtures - Mock issue, mock approvals/rejections

## LLD Sections to Complete

1. **Context & Goal** - Link to #86, objective, status
2. **Proposed Changes**
   - 2.1 Files Changed - All new files listed
   - 2.2 Dependencies - LangGraph, existing nodes
   - 2.3 Data Structures - LLDWorkflowState TypedDict
   - 2.4 Function Signatures - Node functions, routing functions
   - 2.5 Logic Flow - Pseudocode for workflow
   - 2.6 Technical Approach - LangGraph StateGraph pattern
3. **Requirements** - From issue acceptance criteria
4. **Alternatives Considered** - Why LangGraph vs simpler approach
5. **Data & Fixtures** - Mock data for testing
6. **Diagram** - Mermaid state diagram
7. **Security Considerations** - Secrets, input validation
8. **Performance Considerations** - API call budgets
9. **Risks & Mitigations** - API failures, checkpoint corruption
10. **Verification & Testing** - Test scenarios from issue
11. **Definition of Done** - Checklist from issue

## Key Design Decisions to Document

1. **Reuse existing nodes** - designer.py and governance.py imported, not copied
2. **Context injection** - Support `--context` flag per DN-001
3. **Mock mode** - Fixture-based testing for offline development
4. **Audit trail** - Same pattern as issue workflow
5. **Resume capability** - SQLite checkpointer, thread_id = issue number

## Output Location

`docs/LLDs/active/LLD-086-lld-governance-workflow.md`

## Self-Evaluation Before Gemini

After writing the LLD, verify:
1. All Pre-Flight Gate items present
2. All Tier 1 concerns explicitly addressed
3. All Tier 2 concerns addressed or justified
4. Mermaid diagram renders correctly
5. Test scenarios are automatable (Willison protocol)
