# Issue #91: The History Monks: Automated History Check for Issue Workflow

# The Historian: Automated History Check for Issue Workflow

## User Story
As an AgentOS user starting a new issue,
I want the system to automatically check for similar past work,
So that I don't waste time solving problems we've already solved or re-litigating settled decisions.

## Objective
Implement an automated history check node ("The Historian") that queries past completed work before drafting new issues, preventing duplicate effort and preserving institutional knowledge.

## UX Flow

### Scenario 1: No Similar Past Work (Happy Path)
1. User runs issue workflow with a new brief
2. System embeds the brief and queries the vector store for similar history
3. No matches found above threshold (< 0.5 similarity)
4. Workflow proceeds automatically to sandbox/draft phase
5. Result: User experiences no interruption

### Scenario 2: High Similarity Match Found (Duplicate Alert)
1. User runs issue workflow with brief "Optimize Docker build times"
2. System finds "Issue #12: Docker Build Optimization" with 0.91 similarity
3. Workflow pauses with warning: "⚠️ Similar past work detected"
4. User sees: Issue #12 title, summary, and similarity score
5. User chooses option:
   - **Abort**: Workflow terminates ("This appears to be a duplicate")
   - **Link**: Past work summary injected into brief as context, workflow continues
   - **Ignore**: Workflow continues without modification
6. Result: User makes informed decision about proceeding

### Scenario 3: Related Context Found (Silent Enhancement)
1. User runs issue workflow with brief "Add structured logging to API"
2. System finds "Issue #57: Distributed Logging Fix" with 0.67 similarity
3. Related work summary automatically appended to brief as "Related Past Work" section
4. Workflow proceeds automatically (no pause)
5. Result: Agent has historical context without user interruption

### Scenario 4: Rejected Decision in History
1. User runs issue workflow with brief "Implement multi-stage Docker builds"
2. System finds "Issue #25: Docker Build Strategy" noting multi-stage was rejected
3. High similarity triggers pause with context showing the rejection reason
4. User can proceed with knowledge of why this was previously rejected
5. Result: Prevents re-litigating settled architectural decisions

### Scenario 5: Technical Failure (Fail Open)
1. User runs issue workflow with a new brief
2. System attempts to embed brief but encounters error (API timeout, vector store corruption, file lock)
3. System logs error: "⚠️ Historian check failed: {error_type}. Proceeding without history check."
4. Workflow proceeds automatically to sandbox/draft phase
5. Result: User is not blocked; error is logged for debugging

### Scenario 6: Empty or Sparse Vector Store
1. User runs issue workflow with a new brief
2. Vector store is empty or contains fewer than 3 documents
3. System handles gracefully: returns available results (0-2) or empty set
4. Workflow proceeds automatically to sandbox/draft phase
5. Result: User is not blocked; system operates correctly with limited history

## Requirements

### Vector Infrastructure
1. Expand `rebuild_knowledge_base.py` to index `docs/audit/done/*/001-issue.md`
2. Expand indexing to include `docs/LLDs/done/*.md`
3. Tag indexed history documents with metadata `type: history`
4. Distinguish from existing `type: standard` documents (architectural standards)
5. Extract and store issue number, title, and summary as retrievable metadata
6. **Metadata Extraction Strategy**: Extract `issue_id` from YAML frontmatter if present; fall back to parsing filename pattern `{IssueID}-*.md` for audit files; skip metadata extraction for files without parseable identifiers (log warning)

### Historian Node
1. Create `agentos/nodes/historian.py` implementing the history check
2. Accept `brief_content` as input state
3. Embed brief content using same **local embedding model** as Librarian (SentenceTransformers)
4. Query vector store with filter `type == history`, retrieve `k=3` results (or fewer if unavailable)
5. Apply threshold logic:
   - `>= 0.85`: High similarity → Duplicate Alert (pause workflow)
   - `>= 0.5 and < 0.85`: Related context → Silent enhancement (append to brief)
   - `< 0.5`: No match → Proceed unchanged
6. Output `history_check_result` with status and any matched documents
7. **Fail Open Strategy**: On any technical failure (embedding error, vector store unavailable, timeout, empty store), log the error and proceed to draft phase without blocking the workflow
8. **Empty State Handling**: If vector store is empty or has fewer than `k` documents, return available results without error

### Workflow Integration
1. Insert Historian node after "Load Brief" in `agentos/workflows/issue/graph.py`
2. Implement conditional gate based on `history_check_result`
3. Use `human_node` pattern for user interaction on Duplicate Alert
4. Support three user response options: Abort, Link, Ignore
5. Pass enriched brief (with linked context) to downstream nodes

### User Interface
1. Display matched issue number, title, and excerpt on Duplicate Alert
2. Show similarity score for transparency
3. Provide clear option labels with keyboard shortcuts
4. Log user's decision for analytics

## Technical Approach
- **Vector Store:** Extend existing Librarian infrastructure with history corpus and `type` metadata filtering
- **Embedding:** Reuse **local** embedding pipeline from `tools/rebuild_knowledge_base.py` (SentenceTransformers — no external API calls)
- **Node Pattern:** Follow existing LangGraph node conventions in `agentos/nodes/`
- **Conditional Routing:** Use LangGraph's conditional edge pattern for gate logic
- **Human Interaction:** Leverage `human_node` interrupt pattern already in codebase
- **Error Handling:** Implement try/catch with Fail Open behavior — log exceptions and proceed without history context
- **Metadata Extraction:** Use YAML frontmatter parser with filename-based fallback for issue ID extraction

## Security Considerations
- History documents are local project files, no external data exposure
- **Local embeddings only**: Uses SentenceTransformers locally; brief content is never transmitted to external services
- Vector store queries are read-only during workflow execution
- User retains full control via Abort/Link/Ignore decision
- No automatic actions taken on high-similarity matches without user consent

## Cost Considerations
- **No per-run API costs**: Embeddings are generated locally using SentenceTransformers
- One-time compute cost for initial indexing of history documents
- Minimal incremental cost for embedding new briefs at workflow start

## Files to Create/Modify
- `agentos/nodes/historian.py` — New node implementing history check logic with Fail Open error handling
- `tools/rebuild_knowledge_base.py` — Extend to index `done/` directories with history metadata
- `agentos/workflows/issue/graph.py` — Insert Historian node and conditional gate
- `agentos/workflows/issue/state.py` — Add `history_check_result` to workflow state
- `docs/wiki/architecture/historian.md` — Document the Historian subsystem

## Dependencies
- Issue #DN-002 (The Librarian) should be completed first to establish vector store infrastructure
- Requires `docs/audit/done/` and `docs/LLDs/done/` directory structure to exist
- **Prerequisite Check**: Verify `docs/LLDs/done/*.md` files include YAML frontmatter with `issue_id`; if not, implement filename-based fallback extraction

## Out of Scope (Future)
- **Cross-repository history search** — Querying other projects' history, deferred
- **Automatic issue linking in GitHub** — Creating formal issue references, future enhancement
- **History analytics dashboard** — Visualizing what topics we've covered, separate feature
- **Configurable thresholds** — Hardcoded for MVP, config file support later
- **Incremental indexing** — Full rebuild for now, delta updates in future
- **Configurable ignore list** — Allow users to exclude certain history items from matching

## Acceptance Criteria
- [ ] `rebuild_knowledge_base.py` indexes `docs/audit/done/*/001-issue.md` without error
- [ ] `rebuild_knowledge_base.py` indexes `docs/LLDs/done/*.md` without error
- [ ] Indexed history documents have `type: history` metadata
- [ ] Brief "Fix the logging bug" triggers warning when similar logging issue exists in `done/`
- [ ] User can select "Abort" to terminate workflow on duplicate detection
- [ ] User can select "Link" to inject past work summary into brief
- [ ] User can select "Ignore" to proceed without modification
- [ ] Similarity scores >= 0.5 and < 0.85 silently append context (no user prompt)
- [ ] Similarity scores < 0.5 proceed with no modification or interruption
- [ ] Similarity scores < 0.85 never trigger the 'Duplicate Alert' state (threshold boundary verified)
- [ ] Technical failures (embedding error, vector store unavailable, timeout) log warning and proceed without blocking
- [ ] System handles cases where vector store is empty or has < 3 documents without error

## Definition of Done

### Implementation
- [ ] Core Historian node implemented with threshold logic
- [ ] Fail Open error handling implemented with logging
- [ ] Empty/sparse vector store handling implemented
- [ ] Workflow graph updated with new node and conditional routing
- [ ] Knowledge base rebuild script extended for history indexing
- [ ] Metadata extraction implemented with YAML frontmatter + filename fallback
- [ ] Unit tests for historian node threshold behavior
- [ ] Unit tests with **mocked vector store** for isolated threshold logic testing
- [ ] Unit tests for threshold boundary conditions (0.49, 0.50, 0.51, 0.84, 0.85, 0.86)
- [ ] Unit tests for error conditions (TimeoutError, FileNotFoundError, ConnectionError)
- [ ] Integration test for full workflow with history check

### Tools
- [ ] Update `rebuild_knowledge_base.py` with `--include-history` flag
- [ ] Document rebuild command with history indexing

### Documentation
- [ ] Create `docs/wiki/architecture/historian.md`
- [ ] Update workflow documentation with Historian node
- [ ] Add ADR for history similarity thresholds (0.5/0.85)
- [ ] Add ADR for Fail Open error handling strategy
- [ ] Add new files to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created

### Verification
- [ ] Run 0809 Security Audit - PASS
- [ ] Run 0817 Wiki Alignment Audit - PASS

## Testing Notes

**To test Duplicate Alert flow:**
1. Ensure a completed issue exists in `docs/audit/done/` (e.g., "Docker optimization")
2. Run `rebuild_knowledge_base.py` to index history
3. Create a brief with very similar content to the completed issue
4. Start issue workflow and verify pause/warning appears
5. Test all three options: Abort, Link, Ignore

**To test Silent Context flow:**
1. Create a brief with moderately related content (target 0.6-0.7 similarity)
2. Verify workflow proceeds without pause
3. Check that "Related Past Work" section appears in enriched brief

**To test No Match flow:**
1. Create a brief for entirely novel work
2. Verify workflow proceeds without any modification or delay

**To test Fail Open behavior:**
1. Temporarily rename/corrupt the vector store index file
2. Run issue workflow with any brief
3. Verify warning is logged: "Historian check failed: {error}. Proceeding without history check."
4. Verify workflow proceeds to draft phase without blocking

**To test Empty Vector Store:**
1. Clear or use empty vector store
2. Run issue workflow with any brief
3. Verify no error occurs and workflow proceeds normally

**To force specific similarity scores for testing:**
- Use exact text from past issues for > 0.9
- Use related keywords/concepts for 0.5-0.85
- Use completely unrelated domain terms for < 0.5

**Unit test mocking strategy:**
- Mock `VectorStore.query()` to return controlled similarity scores
- Test threshold boundaries: 0.49, 0.50, 0.51, 0.84, 0.85, 0.86
- Test error conditions: raise `TimeoutError`, `FileNotFoundError`, `ConnectionError`
- Mock empty vector store responses (empty list, partial results)
- **CI/CD requirement**: All unit tests MUST use mocked vector store to avoid non-deterministic failures based on actual `done/` folder contents

## Labels
`feature`, `rag`, `workflow-core`, `governance`

## Effort Estimate
**Size: M (Medium)** — 3 Story Points

## Original Brief
# RAG Injection: Knowledge Management (The Historian)

**Context:** We are implementing a local vector store for "The Librarian" (#DN-002) to enforce architectural consistency. However, `AgentOS` is rapidly accumulating completed work in `docs/audit/done/` and `docs/LLDs/done/`. As the project scales, "Institutional Amnesia" becomes a risk—we might solve the same problem twice because we forgot we solved it two months ago.

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

### 2. The Historian Node (`agentos/nodes/historian.py`)

A new node for the `issue_workflow` graph.

* **Input:** `brief_content`
* **Process:**
1. Embed the brief.
2. Query Vector Store for `k=3` nearest neighbors where `type == history`.
3. **Threshold Check:** If the top score is > 0.85 (High Similarity), trigger a "Duplicate Alert".
4. If score is 0.5 - 0.85 (Related Context), append the summary to the `brief_content` as "Related Past Work".


* **Output:** `history_check_result` (Clear / Warning).

### 3. Workflow Integration

Modify `agentos/workflows/issue/graph.py`:

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