# Implementation Plan: Issue #86 (LLD Governance Workflow)

## Phase 0: Setup (Pre-Implementation)

### 0.1 Create Worktree
```bash
git worktree add ../AssemblyZero-86 -b 86-lld-governance-workflow
git -C ../AssemblyZero-86 push -u origin HEAD
poetry install --directory ../AssemblyZero-86
```

### 0.2 Verify Dependencies
- Confirm `assemblyzero/nodes/designer.py` exists and is functional
- Confirm `assemblyzero/nodes/governance.py` exists and is functional
- Confirm LLD template exists at `docs/templates/0102-feature-lld-template.md`

---

## Phase 1: Core Infrastructure (Foundation)

### 1.1 State Schema
**File:** `assemblyzero/workflows/lld/state.py`

Create `LLDWorkflowState` TypedDict and enums exactly as specified in LLD Section 2.3.

**Test:** Unit test that state can be instantiated and type-checked.

### 1.2 Audit Trail Module
**File:** `assemblyzero/workflows/lld/audit.py`

Port pattern from `assemblyzero/workflows/issue/audit.py`:
- `get_repo_root()`
- `create_audit_dir()` → `docs/audit/active/{issue_number}-lld/`
- `save_audit_file()` with sequential numbering
- `next_file_number()`

**Test:** Unit test audit file creation and numbering.

### 1.3 Package Init
**File:** `assemblyzero/workflows/lld/__init__.py`

Export public interface.

---

## Phase 2: Nodes (Core Logic)

### 2.1 Fetch Issue Node (N0)
**File:** `assemblyzero/workflows/lld/nodes.py`

```python
def fetch_issue(state: LLDWorkflowState) -> dict:
    # 1. Validate issue_number
    # 2. Call: gh issue view {issue_number} --json title,body
    # 3. Assemble context_content from context_files
    # 4. Validate context paths (security check per LLD Section 7)
    # 5. Create audit_dir
    # 6. Save 001-issue.md to audit trail
```

**Test:**
- Mock `gh` CLI, verify issue parsing
- Test path validation rejects paths outside project root
- Test missing issue returns error

### 2.2 Design Node (N1)
**File:** `assemblyzero/workflows/lld/nodes.py`

```python
def design(state: LLDWorkflowState) -> dict:
    # 1. Load LLD template
    # 2. Build prompt: issue + context + template
    # 3. Call designer.py (import, not copy)
    # 4. Save draft to audit trail
    # 5. If not auto mode: open in VS Code
```

**Test:**
- Mock designer.py, verify prompt construction
- Verify audit file created
- Verify VS Code skipped in auto mode

### 2.3 Human Edit Node (N2)
**File:** `assemblyzero/workflows/lld/nodes.py`

```python
def human_edit(state: LLDWorkflowState) -> dict:
    # 1. Display iteration count
    # 2. If verdict exists: display critique
    # 3. If auto mode: auto-select Send
    # 4. Else: prompt [S]end / [R]evise / [M]anual
    # 5. Read LLD from disk (may have been edited)
    # 6. Set next_node for routing
```

**Test:**
- Mock input, verify routing logic
- Verify auto mode bypasses prompt

### 2.4 Review Node (N3)
**File:** `assemblyzero/workflows/lld/nodes.py`

```python
def review(state: LLDWorkflowState) -> dict:
    # 1. Call governance.py (import, not copy)
    # 2. Parse verdict: APPROVED / REVISE / DISCUSS
    # 3. Save verdict to audit trail
    # 4. Check iteration count vs max (5)
    # 5. Set next_node for routing
```

**Test:**
- Mock governance.py with APPROVED response
- Mock governance.py with REVISE response
- Verify max iteration enforcement

### 2.5 Finalize Node (N4)
**File:** `assemblyzero/workflows/lld/nodes.py`

```python
def finalize(state: LLDWorkflowState) -> dict:
    # 1. Copy LLD to docs/LLDs/active/LLD-{issue_number}.md
    # 2. Log success
    # 3. Set final_lld_path
```

**Test:**
- Verify file created in correct location
- Verify content matches draft

---

## Phase 3: Graph Assembly

### 3.1 Routing Functions
**File:** `assemblyzero/workflows/lld/graph.py`

- `route_after_human_edit()` → N3_review | N1_design | END
- `route_after_review()` → N4_finalize | N2_human_edit | END
- `check_error()` → continue | END

**Test:** Unit test each routing function with mock states.

### 3.2 StateGraph Definition
**File:** `assemblyzero/workflows/lld/graph.py`

```python
def build_lld_workflow() -> StateGraph:
    # N0 → N1 → N2 → N3 → N4 → END
    #            ↑    ↓
    #            +----+ (revision loop)
```

**Test:** Verify graph compiles without errors.

---

## Phase 4: Mock Mode Infrastructure

### 4.1 Test Fixtures
**Directory:** `tests/fixtures/lld_workflow/`

| File | Content |
|------|---------|
| `issue_42.json` | `{"number": 42, "title": "Test Feature", "body": "## Requirements\n..."}` |
| `designer_output.md` | Valid LLD following template |
| `governance_approved.json` | `{"verdict": "APPROVED", "critique": ""}` |
| `governance_rejected.json` | `{"verdict": "REVISE", "critique": "Missing error handling"}` |

### 4.2 Mock Module
**File:** `assemblyzero/workflows/lld/mock.py`

```python
def mock_fetch_issue(state): ...  # Load from fixture
def mock_design(state): ...       # Load from fixture
def mock_review(state): ...       # Load from fixture (configurable)
```

**Test:** Verify mock functions return expected data.

---

## Phase 5: CLI Runner

### 5.1 Argument Parsing
**File:** `tools/run_lld_workflow.py`

```python
parser.add_argument("--issue", type=int, required=True)
parser.add_argument("--context", action="append", default=[])
parser.add_argument("--auto", action="store_true")
parser.add_argument("--mock", action="store_true")
parser.add_argument("--resume", action="store_true")
parser.add_argument("--max-iterations", type=int, default=5)
```

### 5.2 Workflow Execution
```python
def main():
    # 1. Parse args
    # 2. Build workflow (real or mock)
    # 3. Create/load checkpoint
    # 4. Stream events
    # 5. Return exit code
```

**Test:** CLI help text, argument validation.

---

## Phase 6: Aggressive End-to-End Testing

### 6.1 Mock Mode E2E Tests

| Test | Scenario | Verification |
|------|----------|--------------|
| `test_e2e_happy_path_mock` | --issue 42 --mock | LLD created, exit 0 |
| `test_e2e_single_rejection_mock` | First REVISE, then APPROVE | iteration_count == 2 |
| `test_e2e_max_iterations_mock` | Always REVISE | Exit with guidance message |
| `test_e2e_resume_mock` | Kill at N2, resume | Continues from checkpoint |

### 6.2 Integration Tests (Real APIs, Isolated)

| Test | Scenario | Verification |
|------|----------|--------------|
| `test_integration_fetch_real_issue` | Fetch existing issue from repo | issue_body populated |
| `test_integration_designer_generates_lld` | Real designer call | Valid markdown returned |
| `test_integration_governance_reviews` | Real governance call | Verdict parsed correctly |

### 6.3 Manual E2E Test (One-Time Verification)

```bash
# Create test issue
gh issue create --title "Test LLD Workflow" --body "## Requirements\nTest feature"

# Run workflow
python tools/run_lld_workflow.py --issue {NEW_ISSUE_NUMBER}

# Verify:
# 1. VS Code opens with draft
# 2. Edit draft, save, close
# 3. Gemini review executes
# 4. If rejected, loop works
# 5. Final LLD in docs/LLDs/active/
```

### 6.4 Stress Tests

| Test | Scenario |
|------|----------|
| `test_large_context_files` | --context with 50KB file |
| `test_many_context_files` | --context repeated 10 times |
| `test_rapid_resume` | Start/stop/resume 5 times |

---

## Phase 7: Documentation & Reports

### 7.1 Implementation Report
**File:** `docs/reports/active/86-implementation-report.md`

### 7.2 Test Report
**File:** `docs/reports/active/86-test-report.md`

With mandatory Warnings Summary section.

### 7.3 Tool Documentation
Update `tools/README.md` with new tool.

---

## Execution Order (Dependency-Aware)

```
Phase 0 ──► Phase 1.1 ──► Phase 1.2 ──► Phase 1.3
                │
                ▼
            Phase 2.1 ──► Phase 2.2 ──► Phase 2.3 ──► Phase 2.4 ──► Phase 2.5
                                                            │
                                                            ▼
                                                        Phase 3
                                                            │
                ┌───────────────────────────────────────────┘
                ▼
            Phase 4 ──► Phase 5 ──► Phase 6 ──► Phase 7
```

---

## Test Commands Summary

```bash
# Unit tests only (fast, no API)
poetry run pytest tests/test_lld_workflow.py -v -m "not integration"

# Mock E2E tests (no API)
poetry run pytest tests/test_lld_workflow.py -v -m "mock"

# Integration tests (uses real APIs)
poetry run pytest tests/test_lld_workflow.py -v -m "integration"

# All tests with coverage
poetry run pytest tests/test_lld_workflow.py -v --cov=assemblyzero/workflows/lld

# Manual E2E
python tools/run_lld_workflow.py --issue 42 --mock  # Dry run
python tools/run_lld_workflow.py --issue {REAL}     # Real run
```

---

## Risk Mitigations During Implementation

| Risk | Mitigation |
|------|------------|
| Designer.py interface changes | Read current signature before implementing N1 |
| Governance.py interface changes | Read current signature before implementing N3 |
| Checkpoint format incompatibility | Use same SqliteSaver pattern as issue workflow |
| VS Code not blocking on Windows | Test `code --wait` behavior early |

---

## Definition of Done (Implementation Gate)

- [ ] All Phase 1-5 files created
- [ ] All unit tests pass
- [ ] All mock E2E tests pass
- [ ] Manual E2E test completed successfully
- [ ] Implementation report written
- [ ] Test report written with warnings summary
- [ ] PR created and ready for review
