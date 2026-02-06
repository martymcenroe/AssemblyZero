# RAG Injection: Knowledge Management (The Historian)

**Context:** We are implementing a local vector store for "The Librarian" (#DN-002) to enforce architectural consistency. However, `AssemblyZero` is rapidly accumulating completed work in `docs/audit/done/` and `docs/LLDs/done/`. As the project scales, "Institutional Amnesia" becomes a risk—we might solve the same problem twice because we forgot we solved it two months ago.

## Problem

**The "Reinventing the Wheel" Failure Mode:**
When a user starts a new Issue Workflow for "Optimize Docker build," the agent proceeds as if this is a novel problem. It does not know that:

* We already optimized the Dockerfile in Issue #12.
* We explicitly rejected a multi-stage build in Issue #25 due to CI compatibility.

Result: Wasted API costs, duplicate code, and re-litigating settled decisions.

## Goal

Implement an **Automated History Check Node ("The Historian")** at the very start of the Issue Workflow.

1. **Index:** Expand the vector store to include `docs/audit/done/` (past work) and `docs/LLDs/done/` (past designs).
2. **Detect:** Before drafting a new issue, query the store for semantically similar past work.
3. **Warn:** If a high-similarity match is found, pause the workflow and ask the user if they want to proceed, abort, or reference the past work.

## Proposed Architecture

### 1. Vector Infrastructure Expansion

Modify `tools/rebuild_knowledge_base.py` (from the Librarian brief) to also scan:

* `docs/audit/done/*/001-issue.md` (The original problem statements)
* `docs/LLDs/done/*.md` (The approved solutions)

*Note: These should be tagged with metadata `type: history` to distinguish them from `type: standard`.*

### 2. The Historian Node (`assemblyzero/nodes/historian.py`)

A new node for the `issue_workflow` graph.

* **Input:** `brief_content`
* **Process:**
1. Embed the brief.
2. Query Vector Store for `k=3` nearest neighbors where `type == history`.
3. **Threshold Check:** If the top score is > 0.85 (High Similarity), trigger a "Duplicate Alert".
4. If score is 0.5 - 0.85 (Related Context), append the summary to the `brief_content` as "Related Past Work".


* **Output:** `history_check_result` (Clear / Warning).

### 3. Workflow Integration

Modify `assemblyzero/workflows/issue/graph.py`:

**Current:**
`Load Brief -> Sandbox -> Draft -> ...`

**New:**
`Load Brief -> [The Historian] -> (Conditional Gate) -> Sandbox -> Draft -> ...`

**The Gate Logic:**

* **No Match:** Proceed automatically.
* **Match Found:** Pause workflow (using the `human_node` pattern). Show the user the matching Issue # and Title.
* *Option A:* Abort (It's a duplicate).
* *Option B:* Link (Add as context and proceed).
* *Option C:* Ignore (Proceed anyway).



## Success Criteria

* [ ] The `rebuild_knowledge_base.py` script indexes `docs/audit/done/` without error.
* [ ] Creating a brief "Fix the logging bug" triggers a warning if "Issue #57: Distributed Logging Fix" exists in `done/`.
* [ ] The user can choose to "Link" past work, which injects that issue's summary into the new Draft prompt.
* [ ] Zero false positives blocking the workflow (low similarity matches should be silent context, not blockers).