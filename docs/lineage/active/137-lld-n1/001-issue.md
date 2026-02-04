# Issue #137: Integrate parallel execution module into workflow CLI tools

## Context

Issue #106 implemented the parallel execution infrastructure (`agentos/workflows/parallel/`), but the integration with existing workflow tools was not completed. The parallel module exists but is not usable.

## Current State

✅ Implemented in #106:
- `agentos/workflows/parallel/coordinator.py` - Worker pool, progress tracking, graceful shutdown
- `agentos/workflows/parallel/credential_coordinator.py` - Thread-safe credential reservation
- `agentos/workflows/parallel/output_prefixer.py` - Stdout/stderr workflow identification
- `agentos/workflows/parallel/input_sanitizer.py` - Path-safe identifier validation

❌ Not implemented:
- Integration with `tools/run_requirements_workflow.py`
- Integration with `tools/run_implement_from_lld.py`
- `--parallel` and `--dry-run` CLI flags

## User Story

As an orchestrator, I want to run multiple LLD generation or implementation workflows in parallel so that I can process a batch of issues faster.

## Acceptance Criteria

- [ ] `run_requirements_workflow.py` accepts `--parallel N` flag to process N issues concurrently
- [ ] `run_requirements_workflow.py` accepts `--dry-run` flag to list pending items without executing
- [ ] `run_implement_from_lld.py` accepts `--parallel N` flag to process N issues concurrently
- [ ] `run_implement_from_lld.py` accepts `--dry-run` flag to list pending items without executing
- [ ] Parallel execution uses the CredentialCoordinator for API key management
- [ ] Output is prefixed with workflow ID for clear identification
- [ ] Graceful shutdown on Ctrl+C

## Definition of Done

- [ ] All acceptance criteria met
- [ ] Unit tests for CLI argument parsing
- [ ] Integration test with `--dry-run` (no actual API calls)
- [ ] Documentation updated with parallel execution examples

## Related

- Depends on: #106 (completed)
- Blocked by: None