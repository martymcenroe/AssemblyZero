# LLD Review: 1155-Fix: Mock-Heavy Tests Verify Mocks, Not Actual Behavior

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD proposes a robust shift towards a balanced test pyramid using pytest markers and contract tests. The concept is sound and addresses the issue of mock drift. However, there are missing architectural components regarding the scheduling of contract tests and critical safety guardrails for integration tests involving the `claude` CLI.

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation subject to Tier 2 fixes.

### Cost
- [ ] No issues found.

### Safety
- [ ] **Filesystem Isolation for CLI Tests:** The LLD involves integration tests for the `claude` CLI (Section 2.2). As an agentic CLI, it may perform file writes. The LLD must explicitly mandate the use of the `tmp_path` pytest fixture (or `tempfile`) for *all* integration tests involving file I/O to ensure no destructive acts occur in the actual worktree during testing. The current text "Use read-only operations where possible" is insufficient for an agent CLI; strict isolation is required.

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] **Missing CI Infrastructure:** Section 5.4 and 8.1 state that contract tests will "Run weekly". However, Section 2.1 (Files Changed) does not include a GitHub Actions workflow file (e.g., `.github/workflows/contract-tests.yml`) to implement this schedule. Please add this file to the implementation plan.
- [ ] **Configuration Ambiguity:** Section 2.1 lists "`pytest.ini` or `pyproject.toml`". Please specify exactly which configuration file acts as the source of truth for the project to prevent configuration fragmentation. Prefer `pyproject.toml` if already in use.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Unresolved Open Questions:** Section 1 contains open questions (e.g., "What external services..."). These appear to be answered in the body of the LLD (Claude CLI, GeminiClient). Please mark them as resolved or remove them to finalize the spec.
- [ ] **Test Coverage Specificity:** Section 3 Requirement 7 states "At least one integration test exists for each heavily-mocked module". Please explicitly list *which* modules are considered "heavily-mocked" in this context to ensure the definition of done is verifiable.

## Tier 3: SUGGESTIONS
- Consider adding a `make` target or `poe` task (if using poethepoet) for the contract generation command to make it easier for developers to refresh contracts locally.
- In Section 2.5, clarify if "Capture real service behavior" implies a record/replay mechanism (like VCR.py) or just a one-off capture script.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision