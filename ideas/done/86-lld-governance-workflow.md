# Governance Workflow: LLD Creation & Review

**Context:** We have successfully implemented the Issue Creation Workflow (#62) using LangGraph. We now need to extend this "Governance-as-Code" approach to the next stage of the software lifecycle: Low Level Design (LLD).

## Problem

We have individual nodes for designing LLDs (`agentos/nodes/designer.py`) and reviewing them (`agentos/nodes/governance.py`), but they are currently disconnected.

* There is no orchestrator to pass data between them.
* There is no enforcement of the "Design -> Human Edit -> Governance Review" loop.
* We rely on manual script execution, which makes the process brittle and hard to audit.

## Goal

Create a new LangGraph workflow (`tools/run_lld_workflow.py`) that strictly enforces the LLD creation process:

1. **Draft:** Fetch a GitHub Issue and draft an LLD.
2. **Human Gate:** Pause for human refinement in VS Code.
3. **Governance Gate:** Auto-review via Gemini 3 Pro.
4. **Loop:** Force revision if Governance rejects the design.

## Proposed Architecture

### 1. The State Graph

Create `agentos/workflows/lld/graph.py`.

* **Input:** `issue_id` (Integer)
* **Nodes:**
* `N0_design`: Fetches issue content + invokes `designer.py`.
* `N1_human_edit`: Pauses workflow to allow manual edits to the generated markdown.
* `N2_review`: Invokes `governance.py` to audit the LLD against `docs/skills/0702c-LLD-Review-Prompt.md`.


* **Edges:**
* `N0` -> `N1`
* `N1` -> `N2`
* `N2` -> **Conditional**:
* If `APPROVED`: End workflow.
* If `BLOCK`: Route back to `N1` (Human Edit).





### 2. State Management

Create `agentos/workflows/lld/state.py`.

* **Attributes:**
* `issue_id`: int
* `lld_draft_path`: str (Path to the active draft file)
* `lld_content`: str
* `governance_verdict`: str (APPROVED/BLOCK)
* `governance_critique`: str
* `iteration_count`: int



### 3. The CLI Runner

Create `tools/run_lld_workflow.py`.

* **Usage:** `python tools/run_lld_workflow.py --issue 42`
* **Behavior:**
* Initializes the graph with the issue ID.
* Uses `SqliteSaver` for checkpointing (critical for the human pause).
* Handles the loop: Draft -> Edit -> Review -> Success/Retry.



## Success Criteria

* The workflow refuses to finish until Gemini returns `[x] **APPROVED**`.
* The user can edit the LLD draft in VS Code between the "Draft" and "Review" steps.
* The final approved LLD is present in `docs/LLDs/active/` (or similar).
* Existing nodes (`designer.py`, `governance.py`) are reused, not rewritten.