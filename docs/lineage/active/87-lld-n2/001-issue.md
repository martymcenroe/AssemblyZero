# Issue #87: Implementation Workflow: TDD Enforcement & Context-Aware Code Generation

# Implementation Workflow: TDD Enforcement & Context-Aware Code Generation

## User Story
As an **AgentOS developer**,
I want an **implementation workflow that enforces Test-Driven Development and injects architectural context**,
So that **LLM agents write code grounded in reality, use existing utilities, and cannot hallucinate test results**.

## Objective
Create a LangGraph-based implementation workflow that acts as an arbiterâ€”running real pytest commands, enforcing test-first development, and safely managing git operations outside of LLM control.

## Budget Estimate
- **Estimated tokens per run:** ~50k input tokens / ~4k output tokens
- **Max cost per feature implementation:** ~$0.50-$1.00 (depending on retry count)
- **Retry loop impact:** Each retry adds ~20k input tokens (test output injection)
- **Maximum tokens (3 retries + escalation):** ~130k input / ~16k output

## Context Size Guardrails
- **Individual file limit:** Reject files larger than 100KB
- **Total context limit:** Fail fast if total input context exceeds 200,000 tokens (model limit buffer)
- **Pre-flight validation:** Token count estimation performed before any API call
- **Error messaging:** Clear feedback on which file(s) exceeded limits

## Data Handling Policy
- **Code context transmission:** Code files provided via `--context` are transmitted to the configured Model Provider (e.g., Anthropic Claude)
- **Startup reminder:** CLI prints condensed data handling policy to console upon startup
- **User responsibility:** Ensure `--context` does not include files containing:
  - Personally Identifiable Information (PII)
  - Hardcoded secrets, API keys, or credentials
  - Proprietary code not licensed for LLM transmission
- **Local processing:** Pytest execution and git operations remain local; only code context and agent prompts are transmitted

## UX Flow

### Scenario 1: Happy Path - Successful TDD Cycle
1. Developer runs `python tools/run_implementation_workflow.py --issue 42 --lld docs/LLDs/active/42-feature.md --context docs/standards/0002-coding.md`
2. CLI prints data handling policy reminder to console
3. Workflow validates context file sizes (rejects if >100KB or total tokens exceed limit)
4. Workflow loads LLD and context files, builds master prompt
5. Agent scaffolds failing test files based on LLD spec
6. Workflow runs pytest â†’ confirms tests FAIL with **exit code 1** (Red phase - assertion failures)
7. Agent writes implementation code using injected context (knows about `GovernanceAuditLog`, etc.)
8. Workflow runs pytest â†’ tests PASS (Green phase)
9. Workflow runs lint/audit checks
10. Human reviews in VS Code via interactive prompt, approves or aborts
11. Workflow commits, merges, safely cleans up worktree
12. Result: Feature implemented with verified tests, no hallucination

### Scenario 2: Test Retry Loop (Agent Struggles)
1. Agent writes implementation code
2. Workflow runs pytest â†’ FAIL (exit code 1 - assertion failure)
3. Workflow injects actual pytest stderr/stdout into agent context
4. Agent rewrites code (retry 1)
5. Workflow runs pytest â†’ FAIL again (exit code 1)
6. Loop continues up to 3 retries
7. On retry 4: Workflow escalates to Human Review node with full error history
8. Result: Human intervenes before infinite loop burns tokens

### Scenario 3: Test-First Violation Detected
1. Agent attempts to write implementation before tests
2. N2_TestGate_Fail runs pytest â†’ tests PASS (nothing to test yet)
3. Workflow rejects: "Tests must fail before implementation. Write meaningful tests first."
4. Agent returns to N1_Scaffold
5. Result: TDD discipline enforced by graph structure

### Scenario 4: Context Injection Prevents Duplication
1. Developer passes `--context agentos/core/audit.py agentos/core/config.py`
2. Agent sees existing `GovernanceAuditLog` class in context
3. Agent imports and uses existing utility instead of recreating it
4. Result: No duplicate `AuditLogger` class, consistent codebase

### Scenario 5: Test Scaffold Has Syntax Error
1. Agent scaffolds test file with Python syntax error
2. N2_TestGate_Fail runs pytest â†’ exit code 4 (Usage Error / collection failure)
3. Workflow detects non-assertion failure: "Test file has syntax or collection error. Rescaffolding."
4. Agent returns to N1_Scaffold (not N3_Coder)
5. Result: Broken test files don't proceed to implementation phase

### Scenario 6: Context File Too Large
1. Developer passes `--context large_generated_file.py` (500KB file)
2. Workflow validates file size before loading
3. Workflow rejects: "Error: File 'large_generated_file.py' exceeds 100KB limit (500KB). Reduce file size or split context."
4. Result: Prevents token budget blowout before API call

### Scenario 7: Human Review - Abort Path
1. Workflow reaches N6_Human_Review after successful tests
2. Human reviews changes in VS Code
3. Human types "abort" at interactive prompt
4. Workflow triggers rollback: reverts uncommitted changes, preserves worktree for debugging
5. Result: Human can reject without committing broken code

## Requirements

### TDD Enforcement
1. Tests MUST be written before implementation code (Red-Green-Refactor)
2. N2_TestGate_Fail node MUST verify pytest fails with **exit code 1 specifically** (assertion failures only)
3. N2_TestGate_Fail MUST route back to N1_Scaffold if exit code is 2, 3, 4, or 5 (non-assertion failures indicate broken test scaffolding)
4. N4_TestGate_Pass node MUST verify pytest passes (exit code == 0)
5. Real subprocess executionâ€”never ask LLM "did tests pass?"
6. Maximum 3 retry attempts before human escalation
7. Pytest subprocess calls MUST include a 300-second (5 minute) timeout to prevent hanging tests from freezing the agent

### Pytest Exit Code Handling
1. **Exit Code 0:** Tests passed - proceed to next phase
2. **Exit Code 1:** Tests failed (assertion errors) - valid TDD "Red" state, proceed to implementation
3. **Exit Code 2:** Interrupted - escalate to human review
4. **Exit Code 3:** Internal error - escalate to human review
5. **Exit Code 4:** Usage/collection error (syntax errors, import failures) - retry N1_Scaffold
6. **Exit Code 5:** No tests collected - retry N1_Scaffold

### Context Injection
1. Accept `--context` flag with list of file paths
2. Load and concatenate context files into master prompt
3. Context persists through N1_Scaffold and N3_Coder nodes
4. Support both `.py` and `.md` files as context
5. **Reject individual files larger than 100KB** with clear error message
6. **Fail fast if total input context exceeds 200,000 tokens** before making API call

### Path Security
1. All paths provided via `--context` MUST be validated to resolve within the current working directory
2. Reject paths containing `../` traversal sequences
3. Reject absolute paths outside project root
4. Reject symbolic links pointing outside project root
5. Log rejected paths to `GovernanceAuditLog` with reason
6. Basic secret file rejection: Reject files matching patterns `*.env`, `.env*`, `*credentials*`, `*secret*`, `*.pem`, `*.key` (case-insensitive)

### State Management
1. Track `test_exit_code` from real pytest runs
2. Track `test_output` (stdout/stderr) for debugging
3. Track `retry_count` to prevent infinite loops
4. Track `changed_files` for safe cleanup
5. Track `scaffold_retry_count` separately for N1 retries (syntax/collection errors)
6. Track `human_decision` for review outcome (approve/abort)

### Safe Operations
1. Git worktree setup/teardown managed by Graph nodes, not LLM
2. `rm -rf` and `git worktree remove` are privileged Node operations only
3. Cleanup happens ONLY after successful merge/commit
4. Rollback capability if merge fails or human aborts

### Human Review Interaction
1. N6_Human_Review displays changed files and opens diff in VS Code
2. Interactive prompt: `"Review complete. Type 'approve' to commit or 'abort' to rollback: "`
3. On "approve": Proceed to N7_Safe_Merge
4. On "abort": Trigger rollback (revert uncommitted changes), exit with code 2
5. Timeout after 30 minutes of inactivity: Escalate with warning, preserve state

### CLI Interface
1. Required flags: `--issue`, `--lld`
2. Optional flags: `--context` (multiple files), `--max-retries` (default 3), `--dry-run`
3. Clear progress output showing current node
4. Exit codes: 0 (success), 1 (tests failed after retries), 2 (human intervention required/aborted)
5. Print data handling policy reminder on startup
6. `--dry-run` flag prints execution path without API calls (uses Mock LLM)

## Technical Approach

- **State Graph (`agentos/workflows/implementation/graph.py`):** LangGraph StateGraph with conditional routing based on pytest exit codes. Nodes are pure functions, routing is deterministic based on state.
- **State Schema (`agentos/workflows/implementation/state.py`):** TypedDict with `issue_id`, `lld_content`, `context_content`, `test_output`, `test_exit_code`, `retry_count`, `scaffold_retry_count`, `changed_files`, `human_decision`.
- **Test Arbiter:** Python `subprocess.run(['pytest', '-v', '--tb=short'], timeout=300)` captures real output. No LLM interpretation of pass/fail. Timeout prevents hanging tests. Exit code 1 specifically required for valid "Red" state.
- **Exit Code Router:** Dedicated routing function that maps pytest exit codes to appropriate next nodes (see Pytest Exit Code Handling requirements).
- **Context Loader:** Reads files after path validation and size checks, builds structured prompt with clear sections: `## LLD Specification`, `## Project Context`, `## Coding Standards`.
- **Context Size Validator:** Checks individual file sizes (<100KB) and estimates total token count before API call.
- **Path Validator:** Resolves all paths via `pathlib.Path.resolve()`, verifies they start with `cwd`, rejects traversal attempts. Includes basic secret file pattern matching.
- **Human Review Handler:** Uses `input()` for interactive approval/abort prompt with 30-minute timeout via signal handler.
- **CLI Runner (`tools/run_implementation_workflow.py`):** Argparse interface, initializes state, invokes graph, handles cleanup on interrupt. Prints data handling policy on startup.
- **Mock LLM Mode:** Environment variable `AGENTOS_MOCK_LLM=1` enables deterministic mock responses for testing graph routing logic without API calls. Static fixtures in `tests/fixtures/implementation/` provide canned responses for each node. Also activated by `--dry-run` flag.

## Security Considerations

- **Subprocess Isolation:** Pytest runs in subprocess with timeout, not eval'd code
- **Path Validation:** Context files must exist, be within project root, and not use `../` traversal. Implementation uses `pathlib.Path.resolve()` and validates `resolved_path.is_relative_to(project_root)`
- **Secret File Rejection:** Basic pattern matching rejects common secret file patterns (`.env`, `*.key`, etc.) before transmission
- **Context Size Limits:** Prevents token budget attacks via oversized files
- **Privileged Cleanup:** Only N7_Safe_Merge node can execute destructive git commands
- **No Shell=True:** All subprocess calls use explicit argument lists
- **Audit Trail:** All node transitions logged via `GovernanceAuditLog`
- **Symlink Protection:** Symbolic links are resolved before validation to prevent indirect traversal

## Files to Create/Modify

- `agentos/workflows/implementation/__init__.py` â€” Package init
- `agentos/workflows/implementation/graph.py` â€” Main StateGraph definition with all nodes
- `agentos/workflows/implementation/state.py` â€” ImplementationState TypedDict
- `agentos/workflows/implementation/nodes/context_loader.py` â€” N0 node implementation with path validation and size checks
- `agentos/workflows/implementation/nodes/scaffold.py` â€” N1 test scaffolding node
- `agentos/workflows/implementation/nodes/test_gates.py` â€” N2 (must fail with exit code 1) and N4 (must pass) nodes with timeout and exit code routing
- `agentos/workflows/implementation/nodes/coder.py` â€” N3 implementation writing node
- `agentos/workflows/implementation/nodes/lint_audit.py` â€” N5 static analysis node
- `agentos/workflows/implementation/nodes/human_review.py` â€” N6 interactive approval/abort with VS Code integration
- `agentos/workflows/implementation/nodes/safe_merge.py` â€” N7 privileged git operations
- `agentos/workflows/implementation/path_validator.py` â€” Centralized path security validation with secret file rejection
- `agentos/workflows/implementation/context_validator.py` â€” File size and token count validation
- `agentos/workflows/implementation/exit_code_router.py` â€” Pytest exit code to node routing logic
- `agentos/workflows/implementation/mock_llm.py` â€” Mock LLM responses for offline testing
- `tools/run_implementation_workflow.py` â€” CLI entry point with data policy display
- `tests/workflows/implementation/test_graph.py` â€” Graph routing tests (uses mock mode)
- `tests/workflows/implementation/test_nodes.py` â€” Individual node unit tests
- `tests/workflows/implementation/test_path_validator.py` â€” Path traversal security tests
- `tests/workflows/implementation/test_context_validator.py` â€” File size and token limit tests
- `tests/workflows/implementation/test_exit_code_router.py` â€” Exit code routing logic tests
- `tests/fixtures/implementation/` â€” Static fixtures for mock LLM mode

## Dependencies

- Issue #003 (LLD Workflow) should be completed first for `lld_path` integration
- Requires `langgraph` package (already in dependencies)
- Requires `pytest` available in environment

## Out of Scope (Future)

- **Parallel Test Execution** â€” pytest-xdist optimization deferred
- **Multi-Agent Review** â€” single agent implementation first
- **Auto-Refactor Node** â€” manual refactor in N3 for now
- **PR Creation** â€” separate workflow, this ends at local merge
- **Coverage Enforcement** â€” future enhancement to N5
- **Advanced Secret Scanning** â€” full AST-based secret detection deferred; basic pattern matching only for MVP
- **Gitignore-Aware Directory Context** â€” `--context` accepts files only; directory support with gitignore deferred

## Acceptance Criteria

- [ ] Running `python tools/run_implementation_workflow.py --issue 42 --lld path/to/lld.md` executes the full graph
- [ ] CLI prints data handling policy reminder on startup
- [ ] Tests are created BEFORE implementation code (N1 â†’ N2 order enforced)
- [ ] N2_TestGate_Fail accepts ONLY exit code 1 as valid "Red" state
- [ ] N2_TestGate_Fail routes to N1_Scaffold on exit codes 4 or 5 (syntax/collection errors)
- [ ] N2_TestGate_Fail routes to N6_Human_Review on exit codes 2 or 3 (interrupts/internal errors)
- [ ] N2_TestGate_Fail rejects if pytest passes (tests must fail first)
- [ ] N4_TestGate_Pass routes to N3_Coder on pytest failure (retry loop)
- [ ] Retry count increments and caps at 3 before human escalation
- [ ] `--context` files appear in agent prompts during N1 and N3
- [ ] Real pytest stdout/stderr captured in `state['test_output']`
- [ ] Worktree cleanup only executes after successful N7_Safe_Merge
- [ ] `GovernanceAuditLog` records all node transitions
- [ ] CLI exits with appropriate codes (0/1/2)
- [ ] Paths with `../` traversal are rejected with clear error message
- [ ] Files matching secret patterns (`.env`, `*.key`, etc.) are rejected
- [ ] Files larger than 100KB are rejected with clear error message
- [ ] Total context exceeding 200k tokens fails fast before API call
- [ ] Pytest subprocess times out after 300 seconds
- [ ] `AGENTOS_MOCK_LLM=1` enables offline graph testing
- [ ] `--dry-run` prints execution path without API calls
- [ ] N6_Human_Review accepts "approve" or "abort" input
- [ ] "abort" at human review triggers rollback and exits with code 2

## Definition of Done

### Implementation
- [ ] All nodes implemented and wired in graph
- [ ] Conditional routing logic tested (including all pytest exit codes)
- [ ] CLI argument parsing complete
- [ ] Error handling for missing files, invalid paths
- [ ] Path validation rejects traversal attempts
- [ ] Secret file pattern rejection implemented
- [ ] Context size validation implemented (100KB per file, 200k token total)
- [ ] Mock LLM mode functional for offline development
- [ ] Exit code router correctly maps all pytest exit codes
- [ ] Human review interactive prompt with approve/abort flow
- [ ] Data handling policy printed on CLI startup

### Tools
- [ ] `tools/run_implementation_workflow.py` documented with `--help`
- [ ] Example usage in tool docstring
- [ ] `--dry-run` flag documented

### Documentation
- [ ] Update `docs/wiki/workflows.md` with Implementation Workflow section
- [ ] Add architecture diagram showing node flow
- [ ] Document retry behavior and human escalation
- [ ] Document pytest exit code handling logic
- [ ] Document human review interaction (approve/abort)
- [ ] Add new files to `docs/0003-file-inventory.md`
- [ ] Document data transmission policy in wiki
- [ ] Document context size limits

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/004/implementation-report.md` created
- [ ] `docs/reports/004/test-report.md` created

### Verification
- [ ] Run 0809 Security Audit - PASS (subprocess handling, path validation)
- [ ] Run 0817 Wiki Alignment Audit - PASS

## Testing Notes

**To test the retry loop:**
```bash
# Create an LLD that specifies impossible requirements
# Watch agent fail 3 times then escalate
```

**To test context injection:**
```bash
# Pass --context with a file containing a utility class
# Verify agent imports it instead of recreating
grep "from agentos.core.audit import" generated_code.py
```

**To force N2 rejection (tests must fail first):**
```bash
# Manually create passing tests before running workflow
# N2 should reject with "Tests must fail before implementation"
```

**To verify real pytest execution:**
```bash
# Intentionally break a test assertion
# Verify state['test_output'] contains actual pytest traceback
```

**To test path validation security:**
```bash
# Attempt traversal attack
python tools/run_implementation_workflow.py --issue 42 --lld docs/lld.md --context ../../../etc/passwd
# Expected: "Error: Path '../../../etc/passwd' resolves outside project root"

# Attempt absolute path outside project
python tools/run_implementation_workflow.py --issue 42 --lld docs/lld.md --context /etc/passwd
# Expected: "Error: Absolute paths outside project root not allowed"
```

**To test secret file rejection:**
```bash
# Attempt to include .env file
python tools/run_implementation_workflow.py --issue 42 --lld docs/lld.md --context .env
# Expected: "Error: File '.env' matches secret file pattern and cannot be transmitted"

# Attempt to include key file
python tools/run_implementation_workflow.py --issue 42 --lld docs/lld.md --context config/server.key
# Expected: "Error: File 'server.key' matches secret file pattern and cannot be transmitted"
```

**To test context size limits:**
```bash
# Create oversized file
dd if=/dev/zero of=large_file.py bs=1024 count=150  # 150KB file
python tools/run_implementation_workflow.py --issue 42 --lld docs/lld.md --context large_file.py
# Expected: "Error: File 'large_file.py' exceeds 100KB limit (150KB)"

# Test total token limit (mock many files)
AGENTOS_MOCK_LLM=1 MOCK_TOKEN_COUNT=250000 python tools/run_implementation_workflow.py --issue 42 --lld docs/lld.md
# Expected: "Error: Total context (250k tokens) exceeds 200k token limit"
```

**To test mock LLM mode (offline development):**
```bash
# Run graph routing tests without API calls
AGENTOS_MOCK_LLM=1 pytest tests/workflows/implementation/test_graph.py -v

# Force specific mock responses to test error paths
AGENTOS_MOCK_LLM=1 MOCK_FORCE_FAIL=N3 python tools/run_implementation_workflow.py --issue 42 --lld docs/lld.md

# Use --dry-run flag
python tools/run_implementation_workflow.py --issue 42 --lld docs/lld.md --dry-run
# Expected: Prints execution path without API calls
```

**To test pytest timeout:**
```bash
# Create a test that hangs indefinitely
# Verify workflow times out after 300 seconds and escalates
```

**To test pytest exit code routing:**
```bash
# Test syntax error handling (exit code 4)
# Create test file with syntax error, verify routes to N1_Scaffold
AGENTOS_MOCK_LLM=1 MOCK_PYTEST_EXIT=4 pytest tests/workflows/implementation/test_exit_code_router.py -v

# Test no tests collected (exit code 5)
# Create empty test file, verify routes to N1_Scaffold
AGENTOS_MOCK_LLM=1 MOCK_PYTEST_EXIT=5 pytest tests/workflows/implementation/test_exit_code_router.py -v

# Test internal error (exit code 3)
# Verify routes to N6_Human_Review
AGENTOS_MOCK_LLM=1 MOCK_PYTEST_EXIT=3 pytest tests/workflows/implementation/test_exit_code_router.py -v
```

**To test human review interaction:**
```bash
# Run workflow to human review stage
python tools/run_implementation_workflow.py --issue 42 --lld docs/lld.md
# At prompt, type "approve" -> verify proceeds to merge
# At prompt, type "abort" -> verify rollback and exit code 2
```

## Labels
`workflow`, `core-infrastructure`, `python`

## Effort Estimate
**Large (L)** â€” Complex state management, subprocess handling, security validation, exit code routing, human interaction, and mock infrastructure