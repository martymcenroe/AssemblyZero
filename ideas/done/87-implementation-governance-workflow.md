# Governance Workflow: Implementation & TDD Enforcement

**Context:** We have firmly established the "Governance-as-Code" pattern with the Issue and LLD workflows. Now we face the most critical challenge: the **Implementation Phase**. This is where LLMs historically fail by hallucinating test results, deleting the wrong files, or writing code that ignores project standards.

## Problem

1. **The "Trust Me" Trap:** Claude/LLMs often claim "I ran the tests and they passed," when they simply imagined a passing result.
2. **Infinite Loops:** Without a strict "Arbiter," an agent can get stuck in a loop of writing broken code, seeing an error, and rewriting the same broken code until the token limit is hit.
3. **Context Amnesia:** The coder doesn't know about `agentos/core/audit.py` or our logging standards unless manually told, leading to duplicate utility functions.
4. **Dangerous Cleanup:** Agents executing `git worktree remove` or `rm -rf` as tool calls are unsafe; these must be privileged **Nodes** in the graph.

## Goal

Create `tools/run_implementation_workflow.py` that enforces a **Test-Driven Development (TDD)** cycle and supports **Context Injection** to ground the LLM in reality.

**Core Philosophy:** The Graph is the Arbiter. The LLM submits code; the Graph runs `pytest`. If `pytest` fails, the Graph rejects the submission.

## Proposed Architecture

### 1. The State Graph (`agentos/workflows/implementation/graph.py`)

* **Input:** `issue_id`, `lld_path` (Approved Design), `context_files` (List[str]).
* **Nodes:**
* **N0_ContextLoader:** Reads `lld_path` + `context_files`. Builds the "Master Prompt".
* **N1_Scaffold:** Creates **ONLY** the test files (`tests/test_feature.py`) based on the LLD.
* **N2_TestGate_Fail:** Runs `pytest`. **MUST FAIL**. (Verifies tests are testing new functionality).
* **N3_Coder:** Writes/Edits implementation code (`src/feature.py`) to satisfy the tests.
* **N4_TestGate_Pass:** Runs `pytest`. **MUST PASS**.
* *Routing:* If Fail -> Return to `N3_Coder` (Max 3 retries).
* *Routing:* If Pass -> Proceed to `N5`.


* **N5_Lint_Audit:** Runs static analysis / security checks.
* **N6_Human_Review:** Final human check in VS Code.
* **N7_Safe_Merge:** Automated commit, squash (optional), and safe worktree cleanup.



### 2. State Management (`agentos/workflows/implementation/state.py`)

```python
class ImplementationState(TypedDict):
    issue_id: int
    lld_content: str
    context_content: str      # Injected architecture/standards
    test_output: str          # Real stdout/stderr from pytest
    test_exit_code: int       # 0 = Pass, 1 = Fail
    retry_count: int          # To prevent infinite loops
    changed_files: List[str]  # Tracked for cleanup

```

### 3. The TDD Arbiter Logic

We do not ask the LLM "Did the tests pass?" We run `subprocess.run(['pytest', ...])` in a Python function.

* **The Loop:**
```python
def route_after_test(state):
    if state['test_exit_code'] == 0:
        return "N5_Lint_Audit"
    if state['retry_count'] > 3:
        return "N6_Human_Review" # "I'm stuck, human help me"
    return "N3_Coder" # Try again with error logs

```



### 4. The CLI Runner (`tools/run_implementation_workflow.py`)

* **Usage:**
```bash
python tools/run_implementation_workflow.py \
  --issue 42 \
  --lld docs/LLDs/active/42-feature.md \
  --context docs/standards/0002-coding.md agentos/core/audit.py

```


* **Behavior:**
* Injects the LLD and Context Files into `N1` and `N3`.
* Manages the Git Worktree isolation (setup/teardown) safely outside the LLM's control.



## Success Criteria

* [ ] **Test-First Enforcement:** The workflow *requires* a failing test before implementation code is accepted.
* [ ] **Context Awareness:** The agent uses existing utilities (e.g., `GovernanceAuditLog`) because `agentos/core/audit.py` was passed via `--context`.
* [ ] **Reality Check:** The workflow loops back automatically when real `pytest` execution fails.
* [ ] **Safety:** Cleanup (worktree removal) happens only after successful merge/commit.