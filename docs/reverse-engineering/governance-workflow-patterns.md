# Governance Workflow Patterns

**Created:** 2026-02-01
**Purpose:** Extract reusable patterns from existing governance workflows for building Stage 3 (Testing Workflow)
**Source Workflows:** Issue Workflow (#62), LLD Workflow (#86)

---

## Table of Contents

1. [State Schema Patterns](#state-schema-patterns)
2. [Node Interface Patterns](#node-interface-patterns)
3. [Human Gate Patterns](#human-gate-patterns)
4. [Iteration/Retry Patterns](#iterationretry-patterns)
5. [External Tool Integration](#external-tool-integration)
6. [Error Handling Patterns](#error-handling-patterns)
7. [Checkpointing and Resume](#checkpointing-and-resume)
8. [Audit Trail Patterns](#audit-trail-patterns)

---

## State Schema Patterns

### TypedDict with total=False

Both workflows use `TypedDict` with `total=False` to allow optional fields:

```python
from typing import Literal, TypedDict

class LLDWorkflowState(TypedDict, total=False):
    # Input
    issue_number: int
    context_files: list[str]
    repo_root: str

    # Workflow tracking
    audit_dir: str
    file_counter: int
    iteration_count: int
    max_iterations: int

    # Current artifacts
    lld_content: str
    lld_draft_path: str

    # Routing
    next_node: str

    # Error handling
    error_message: str

    # Mode flags
    auto_mode: bool
    mock_mode: bool
```

### Key State Categories

1. **Input Fields:** Data provided at workflow start
2. **Tracking Counters:** `file_counter`, `iteration_count`, `*_count`
3. **Current Artifacts:** Paths and content of latest versions
4. **Routing:** `next_node` string for conditional edges
5. **Error Handling:** `error_message` for graceful failures
6. **Mode Flags:** `auto_mode`, `mock_mode` for testing

### Counter Preservation Pattern

Counters must be explicitly preserved through state transitions:

```python
def human_edit(state: LLDWorkflowState) -> dict:
    return {
        "iteration_count": iteration,
        "next_node": "N3_review",
        # Preserve counters through transitions
        "draft_count": state.get("draft_count", 0),
        "verdict_count": state.get("verdict_count", 0),
        "file_counter": state.get("file_counter", 0),
    }
```

**Why:** LangGraph merges returned dict into state; unmentioned keys are lost.

---

## Node Interface Patterns

### Standard Node Signature

```python
def node_name(state: WorkflowState) -> dict:
    """Node docstring.

    Args:
        state: Current workflow state.

    Returns:
        State updates (merged into existing state).
    """
    # 1. Extract needed values from state
    value = state.get("key", default)

    # 2. Check for mock mode
    if state.get("mock_mode"):
        return _mock_node_name(state)

    # 3. Do work
    result = do_something(value)

    # 4. Return state updates
    return {
        "new_key": result,
        "error_message": "",  # Clear on success
    }
```

### Node Naming Convention

- **N0:** Load/fetch input data
- **N1-N(n-2):** Processing nodes
- **N(n-1):** Human gate (if applicable)
- **N(n):** Finalize/save output

### Guard Pattern (Pre/Post Validation)

```python
def review(state: LLDWorkflowState) -> dict:
    # --------------------------------------------------------------------------
    # GUARD: Pre-LLM content validation
    # --------------------------------------------------------------------------
    lld_content = state.get("lld_content", "")

    if not lld_content or not lld_content.strip():
        print("    [GUARD] BLOCKED: Draft is empty")
        return {"error_message": "GUARD: Draft is empty"}

    if len(lld_content) > 100000:
        print(f"    [GUARD] BLOCKED: Draft too large ({len(lld_content)} chars)")
        return {"error_message": f"GUARD: Draft too large"}
    # --------------------------------------------------------------------------

    # ... continue with node logic
```

---

## Human Gate Patterns

### VS Code Wait Pattern

```python
def open_vscode_and_wait(file_path: str) -> tuple[bool, str]:
    """Open VS Code with --wait flag for blocking user interaction."""
    import subprocess

    try:
        result = subprocess.run(
            ["code", "--wait", file_path],
            capture_output=True,
            text=True,
            timeout=86400,  # 24 hours
        )
        if result.returncode != 0:
            return False, f"VS Code exited with code {result.returncode}"
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "VS Code wait timed out"
    except FileNotFoundError:
        return False, "'code' command not found"
```

### Human Decision Enum

```python
from enum import Enum

class HumanDecision(str, Enum):
    """User choices at human gate node."""
    SEND = "S"      # Send to Gemini review
    REVISE = "R"    # Return for revision
    MANUAL = "M"    # Exit for manual handling
```

### Interactive Prompt Pattern

```python
def human_edit(state: LLDWorkflowState) -> dict:
    # Check auto mode first
    if state.get("auto_mode"):
        return {"next_node": "N3_review", ...}

    # Show options
    print("\n    [S] Send to Gemini review")
    print("    [R] Revise with feedback")
    print("    [M] Manual exit")

    while True:
        try:
            choice = input("\n    Choice: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            choice = "M"

        if choice == "S":
            return {"next_node": "N3_review", ...}
        elif choice == "R":
            feedback = input("    Enter feedback: ").strip()
            return {"next_node": "N1_design", "user_feedback": feedback, ...}
        elif choice == "M":
            return {"next_node": "END", "error_message": "MANUAL: User chose exit"}
        else:
            print("    Invalid choice.")
```

### Auto Mode Bypass

```python
if state.get("auto_mode"):
    gemini_critique = state.get("gemini_critique", "")

    if gemini_critique:
        # Previous review was BLOCKED - revise automatically
        return {
            "next_node": "N1_design",
            "user_feedback": f"Gemini review feedback:\n{gemini_critique}",
        }
    else:
        # First iteration - send to review
        return {"next_node": "N3_review"}
```

---

## Iteration/Retry Patterns

### Max Iterations Guard

```python
DEFAULT_MAX_ITERATIONS = 20

def review(state: LLDWorkflowState) -> dict:
    iteration = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", DEFAULT_MAX_ITERATIONS)

    # ... do review ...

    # Check max iterations
    if lld_status != "APPROVED" and iteration >= max_iterations:
        return {
            "lld_status": lld_status,
            "error_message": f"MAX_ITERATIONS_REACHED:{max_iterations}",
            "next_node": "END",
        }
```

### Conditional Edge Routing

```python
def route_after_review(state) -> Literal["N4_finalize", "N2_human_edit", "end"]:
    """Route based on state['next_node'] set by review node."""
    next_node = state.get("next_node", "")
    error = state.get("error_message", "")

    if error:
        return "end"

    if next_node == "N4_finalize":
        return "N4_finalize"
    elif next_node == "N2_human_edit":
        return "N2_human_edit"
    else:
        return "end"
```

### Graph Edge Definition

```python
workflow.add_conditional_edges(
    "N3_review",
    route_after_review,
    {
        "N4_finalize": "N4_finalize",
        "N2_human_edit": "N2_human_edit",
        "end": END,
    },
)
```

### Cumulative Feedback Pattern

```python
def _collect_previous_verdicts(audit_dir: Path) -> str:
    """Collect all previous verdicts for cumulative context."""
    verdict_files = sorted(audit_dir.glob("*-verdict.md"))

    if not verdict_files:
        return ""

    sections = []
    for verdict_file in verdict_files:
        content = verdict_file.read_text(encoding="utf-8").strip()
        if content:
            sections.append(f"### Review {file_num}:\n{content}")

    return "## PREVIOUS FEEDBACK (DO NOT REGRESS)\n\n" + "\n\n".join(sections)
```

---

## External Tool Integration

### Claude Headless Pattern

```python
def call_claude_headless(prompt: str, system_prompt: str | None = None) -> str:
    """Call Claude via subprocess in headless mode."""
    cmd = ["claude", "-p", "--output-format", "json", "--tools", ""]

    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    if result.returncode != 0:
        raise RuntimeError(f"Claude failed: {result.stderr}")

    response = json.loads(result.stdout)
    return response.get("result", "")
```

### Gemini Client Pattern

```python
from agentos.core.gemini_client import GeminiClient
from agentos.core.config import GOVERNANCE_MODEL

client = GeminiClient(model=GOVERNANCE_MODEL)
result = client.invoke(
    system_instruction="You are reviewing...",
    content=f"{review_prompt}\n\n{draft_content}",
)

if result.success:
    verdict_content = result.response
else:
    error_msg = f"Gemini error: {result.error_message}"
```

### GitHub CLI Pattern

```python
def fetch_issue(issue_number: int, repo_root: str | None = None) -> dict:
    """Fetch issue via gh CLI with cross-repo support."""
    result = subprocess.run(
        ["gh", "issue", "view", str(issue_number), "--json", "title,body"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        cwd=repo_root,  # Cross-repo support
    )

    if result.returncode != 0:
        return {"error": result.stderr.strip()}

    return json.loads(result.stdout)
```

### Pytest Execution Pattern

```python
def run_pytest(test_files: list[str], coverage_target: int = 90) -> dict:
    """Run pytest with coverage."""
    cmd = [
        "pytest",
        *test_files,
        f"--cov=agentos",
        f"--cov-fail-under={coverage_target}",
        "--tb=short",
        "-v",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
    )

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "passed": result.returncode == 0,
    }
```

---

## Error Handling Patterns

### Error Message Prefixes

```python
# Used for routing decisions
"GUARD: ..."               # Pre/post validation failure
"MANUAL: ..."              # User chose manual exit
"MAX_ITERATIONS_REACHED:"  # Hit iteration limit
"TIMEOUT: ..."             # External tool timeout
"API_ERROR: ..."           # External API failure
```

### Error Routing

```python
def route_after_node(state) -> Literal["next", "end"]:
    error = state.get("error_message", "")

    if error:
        if "MANUAL" in error:
            return "end"  # Clean exit
        if "GUARD" in error:
            return "end"  # Validation failure
        if "MAX_ITERATIONS" in error:
            return "end"  # Limit reached
        return "end"  # Unknown error

    return "next"
```

### Graceful Degradation

```python
def node_with_fallback(state):
    try:
        result = primary_operation()
    except TimeoutError:
        print("    [WARN] Primary operation timed out, using fallback")
        result = fallback_operation()
    except Exception as e:
        return {"error_message": f"Unexpected error: {e}"}

    return {"result": result}
```

---

## Checkpointing and Resume

### SqliteSaver Setup

```python
from langgraph.checkpoint.sqlite import SqliteSaver
from pathlib import Path

db_path = Path.home() / ".agentos" / "testing_workflow.db"
db_path.parent.mkdir(parents=True, exist_ok=True)

with SqliteSaver.from_conn_string(str(db_path)) as memory:
    app = workflow.compile(checkpointer=memory)
```

### Thread ID for Resume

```python
config = {
    "configurable": {"thread_id": f"{issue_number}-testing"},
    "recursion_limit": 25,
}

# Resume uses same thread_id
for event in app.stream(initial_state, config):
    process_event(event)
```

### Resume Detection

```python
def check_for_resume(issue_number: int, db_path: Path) -> bool:
    """Check if there's an existing checkpoint to resume."""
    if not db_path.exists():
        return False

    with SqliteSaver.from_conn_string(str(db_path)) as memory:
        thread_id = f"{issue_number}-testing"
        checkpoint = memory.get({"configurable": {"thread_id": thread_id}})
        return checkpoint is not None
```

---

## Audit Trail Patterns

### Sequential File Numbering

```python
def next_file_number(audit_dir: Path) -> int:
    """Get next sequential file number (001, 002, ...)."""
    if not audit_dir.exists():
        return 1

    max_num = 0
    for f in audit_dir.iterdir():
        if f.is_file():
            match = re.match(r"^(\d{3})-", f.name)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)

    return max_num + 1
```

### Save Audit File

```python
def save_audit_file(
    audit_dir: Path,
    number: int,
    suffix: str,
    content: str,
) -> Path:
    """Save file with NNN-suffix format."""
    filename = f"{number:03d}-{suffix}"
    file_path = audit_dir / filename
    file_path.write_text(content, encoding="utf-8")
    return file_path
```

### Audit Directory Structure

```
docs/lineage/active/{issue}-testing/
├── 001-lld.md              # Loaded LLD
├── 002-test-plan.md        # Extracted test plan
├── 003-review-prompt.md    # Prompt sent to Gemini
├── 004-verdict.md          # Gemini review verdict
├── 005-test-scaffold.py    # Generated test stubs
├── 006-red-phase.txt       # Pytest output (all fail)
├── 007-implementation.py   # Claude-generated code
├── 008-green-phase.txt     # Pytest output (all pass)
├── 009-e2e-results.txt     # E2E test output
└── 010-approved.json       # Final metadata
```

### Workflow Audit Logging

```python
def log_workflow_execution(
    target_repo: Path,
    issue_number: int,
    workflow_type: str,
    event: str,
    details: dict | None = None,
) -> None:
    """Log to docs/lineage/workflow-audit.jsonl."""
    log_file = target_repo / "docs/lineage/workflow-audit.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workflow_type": workflow_type,
        "issue_number": issue_number,
        "event": event,
    }
    if details:
        entry["details"] = details

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
```

---

## Pattern Checklist for New Workflows

When building a new workflow, ensure you have:

- [ ] TypedDict state with `total=False`
- [ ] Input, tracking, artifacts, routing, error sections in state
- [ ] Guard validation before external calls
- [ ] Mock mode support in each node
- [ ] Counter preservation in state returns
- [ ] Human gate with auto_mode bypass
- [ ] Max iterations check
- [ ] Conditional edge routing functions
- [ ] Cumulative feedback collection
- [ ] Cross-repo support via `repo_root`
- [ ] Sequential audit file numbering
- [ ] Workflow audit logging
- [ ] Checkpoint with SqliteSaver
- [ ] Resume detection by thread_id
