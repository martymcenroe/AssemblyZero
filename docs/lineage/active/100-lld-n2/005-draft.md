# 100 - Feature: Lineage workflow integration: standardize design review artifacts

## 1. Context & Goal
* **Issue:** #100
* **Objective:** Standardize the storage of design review artifacts (briefs, drafts, verdicts) into a canonical `docs/lineage/` directory structure within the issue and LLD workflows.
* **Status:** Draft
* **Related Issues:** Standard 0009 (Commit 1d5132c), RCA-PDF (Commit 76a13fc)

### Open Questions
None - requirements are well-defined from issue.

## 2. Proposed Changes

### 2.1 Files Changed
| File | Action | Description |
|------|--------|-------------|
| `tools/issue-workflow.py` | Modify | Implement `LineageManager` class; integrate artifact saving (briefs, drafts, verdicts); handle archival to `done/`. |
| `tools/lld-workflow.py` | Modify | Update to accept an optional `--lineage-dir` argument; if present, save outputs there instead of temp locations. |
| `tools/new-repo-setup.py` | Modify | Add `docs/lineage/active` and `docs/lineage/done` to the scaffold directory list. |

### 2.2 Dependencies
* **Python Standard Library:** `pathlib`, `shutil`, `json`, `datetime`, `re` (slugification).
* **External:** None.

### 2.3 Data Structures

**LineageState (Class Attribute)**
```python
class LineageState(TypedDict):
    issue_id: str
    slug: str
    active_path: Path
    current_sequence: int
```

**FilingMetadata (JSON Schema)**
```json
{
  "issue_url": "https://github.com/...",
  "filed_at": "ISO-8601 Timestamp",
  "iterations": 3,
  "final_verdict": "APPROVED"
}
```

### 2.4 Function Signatures

**In `tools/issue-workflow.py` (New Helper Class):**

```python
class LineageManager:
    def __init__(self, issue_id: str, title: str, base_root: Path = Path("docs/lineage")):
        """
        Initializes the manager.
        1. Generates slug from title.
        2. Checks for existing folder in active/ or done/.
        3. Creates active/{id}-{slug} if not exists.
        """
        pass

    def _get_next_sequence(self) -> int:
        """
        Scans directory for files starting with {NNN}-.
        Returns max(found) + 1, or 1 if empty.
        """
        pass

    def save_artifact(self, tag: str, content: str, ext: str = "md") -> Path:
        """
        Generates filename: {NNN}-{tag}.{ext}
        Writes content to file.
        Returns path.
        """
        pass
    
    def save_filing_metadata(self, url: str, iterations: int) -> Path:
        """
        Saves {NNN}-filed.json with metadata.
        """
        pass

    def archive(self) -> Path:
        """
        Moves folder from docs/lineage/active/ to docs/lineage/done/.
        Returns new path.
        """
        pass
```

### 2.5 Logic Flow (Pseudocode)

**Updated Issue Workflow (`main` execution)**

```python
MAX_ITERATIONS = 5  # Safety bound

def main():
    # 1. Setup
    issue = get_user_input()
    lineage = LineageManager(issue.id, issue.title)
    
    # 2. Brief
    lineage.save_artifact("brief", issue.body)
    
    # 3. Design Loop
    iteration_count = 0
    approved = False
    
    while not approved and iteration_count < MAX_ITERATIONS:
        iteration_count += 1
        
        # Call LLD Generator (passing the lineage folder)
        # Note: We pass the directory so LLD tool can save directly if needed,
        # or we capture output and save here.
        lld_content = generate_lld(context) 
        lineage.save_artifact("draft", lld_content)
        
        # Review
        verdict = get_gemini_review(lld_content)
        lineage.save_artifact("verdict", verdict.full_text)
        
        if verdict.status == "APPROVED":
            approved = True
        else:
            # User Checkpoint to prevent runaway loop
            if not user_confirms_continue():
                print("Aborting workflow.")
                return

    # 4. Filing
    if approved:
        url = github.create_issue(lld_content)
        lineage.save_filing_metadata(url, iteration_count)
        lineage.archive()
        print(f"Filed and archived to docs/lineage/done/")
    else:
        print("Max iterations reached or rejected. Work remains in active/.")
```

### 2.6 Technical Approach
1.  **Path Management:** Use `pathlib` extensively to handle cross-platform path separators and directory existence checks.
2.  **State Recovery:** The `LineageManager` acts as a state machine. When initialized, it looks at the file system. If `docs/lineage/active/100-my-feature` exists and contains `003-verdict.md`, it knows the next file is `004`. This allows the workflow to be interrupted and resumed without losing history.
3.  **LLD Integration:** `tools/lld-workflow.py` will be modified to check for a `--lineage-dir` arg. If provided, it suppresses its default behavior (saving to `temp/` or `cwd`) and saves to the provided path.

## 3. Requirements
1.  **Directory Structure:** The system MUST maintain `docs/lineage/active/` for WIP and `docs/lineage/done/` for filed issues.
2.  **Naming Convention:** Issue folders MUST be named `{id}-{slug}` (e.g., `100-lineage-workflow`).
3.  **Sequential Artifacts:** Files MUST use a 3-digit zero-padded prefix incrementing for every file saved (`001`, `002`, ...).
4.  **Artifact Types:** The system MUST support saving `brief` (md), `draft` (md), `verdict` (md), and `filed` (json).
5.  **Iteration Safety:** The workflow MUST implement a `MAX_ITERATIONS` cap (default 5) and/or user confirmation steps between iterations to prevent infinite loops (Cost Control).
6.  **Archival:** Upon successful filing, the folder MUST be atomically moved to `done/`.
7.  **Resumability:** If the tool is restarted on an existing issue ID, it MUST append to the existing sequence rather than overwriting.

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **Git Branches** | Native version control. | Hard to review "history of thought" in a single view; creates repo pollution. | Rejected |
| **Single Markdown File** | Keeps everything in one place. | Becomes massive/unreadable; hard to parse specific drafts programmatically later. | Rejected |
| **Database (SQLite)** | structured, queryable. | Adds infrastructure dependency; overkill for simple text artifacts. | Rejected |
| **Sequential Files** | Easy to read chronologically; file system is the database; robust. | Requires manual sequence logic. | **Selected** |

## 5. Data & Fixtures

### 5.1 Data Sources
*   **User Input:** Issue ID, Title, Description.
*   **LLM:** Generated LLD text, Reviewer Verdicts.
*   **GitHub API:** URL of filed issue.

### 5.2 Data Pipeline
```ascii
[Input] -> LineageManager -> (Check/Create "active/100-feat")
           |
           +-> Save "001-brief.md"
           |
[Generator] -> Output -> LineageManager -> Save "002-draft.md"
           |
[Reviewer]  -> Output -> LineageManager -> Save "003-verdict.md"
           |
           +-> (If Approved) -> GitHub API -> URL
           |
           +-> Save "004-filed.json"
           |
           +-> Move folder to "done/100-feat"
```

### 5.3 Test Fixtures
| Fixture | Description |
|---------|-------------|
| `mock_fs` | Use `pyfakefs` or `tmp_path` (pytest) to simulate `docs/lineage` structure. |
| `mock_issue` | Object with `id=100`, `title="Test Feature"`. |

### 5.4 Deployment Pipeline
Development only. Scripts are checked into the repo.

## 6. Diagram

### 6.1 Mermaid Quality Gate
- [x] Syntax Valid
- [x] Flow Direction Clear
- [x] Nodes Labeled

### 6.2 Diagram
```mermaid
sequenceDiagram
    participant User
    participant Workflow
    participant LineageMgr
    participant FS as FileSystem

    User->>Workflow: Start(ID=100)
    Workflow->>LineageMgr: init(100)
    LineageMgr->>FS: mkdir active/100-title
    Workflow->>LineageMgr: save_artifact("brief")
    LineageMgr->>FS: write 001-brief.md
    
    loop Design Cycle (Max 5)
        Workflow->>LineageMgr: save_artifact("draft")
        LineageMgr->>FS: write NNN-draft.md
        
        Workflow->>LineageMgr: save_artifact("verdict")
        LineageMgr->>FS: write NNN-verdict.md
        
        alt Approved
            Workflow->>Workflow: Break Loop
        else Rejected
            Workflow->>User: Confirm Continue?
        end
    end
    
    alt Filed Successfully
        Workflow->>LineageMgr: save_filing_metadata()
        LineageMgr->>FS: write NNN-filed.json
        Workflow->>LineageMgr: archive()
        LineageMgr->>FS: mv active/100... done/100...
    end
```

## 7. Security Considerations
| Concern | Mitigation |
|---------|------------|
| **Directory Traversal** | Sanitize Issue ID and Title before creating paths. Ensure paths are relative to repo root. |
| **Data Loss** | `get_next_sequence` ensures we never overwrite existing numbers. `shutil.move` will be wrapped in try/except. |

## 8. Performance Considerations
| Metric | Budget |
|--------|--------|
| **File I/O** | < 100ms per operation. |
| **Startup Time** | < 1s to scan directory and determine sequence. |

## 9. Risks & Mitigations
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **Runaway Costs** | Infinite loop of draft/reject consumes API tokens. | Medium | **Critical:** Implemented `MAX_ITERATIONS` constant and User Confirmation checkpoints. |
| **Sequence Collision** | Two processes writing to same folder. | Low | Workflow is single-user local CLI. |
| **Filename Parsing** | User manually renames files, breaking sequence logic. | Low | Logic will default to `max(found)` or handle regex parse errors gracefully (ignore non-conforming files). |

## 10. Verification & Testing

### 10.1 Test Scenarios
| ID | Scenario | Type | Input | Output | Criteria |
|----|----------|------|-------|--------|----------|
| **T1** | Init New Lineage | Happy | ID: 100, Title: "Foo" | Dir `active/100-foo` | Directory created. |
| **T2** | Save Brief | Happy | Body: "Do X" | File `001-brief.md` | Content matches, sequence is 001. |
| **T3** | Sequence Logic | Logic | Folder has `001`..`005` | `save_artifact` | Creates `006-...md`. |
| **T4** | Archive | Happy | Workflow Complete | `done/100-foo` | `active` is empty, `done` contains all files. |
| **T5** | Max Iterations | Edge | Loop runs 6 times | Workflow Aborts | Loop terminates at 5. |

### 10.2 Test Commands
```bash
# Unit tests
pytest tests/tools/test_lineage.py

# Manual Verify
python tools/issue-workflow.py --id 999 --title "Lineage Test" --dry-run
# Check docs/lineage/active/999-lineage-test/ exists
```

### 10.3 Manual Tests (Only If Unavoidable)
N/A - All scenarios automated via unit tests and FS mocks.

## 11. Definition of Done

### Code
- [ ] `LineageManager` class implemented in `tools/issue-workflow.py`.
- [ ] `MAX_ITERATIONS` logic implemented.
- [ ] `lld-workflow.py` accepts `--lineage-dir`.
- [ ] `new-repo-setup.py` updated.

### Tests
- [ ] Unit tests for `LineageManager` (init, sequencing, archiving).
- [ ] Integration test for full loop (mocked LLM).

### Documentation
- [ ] `CONTRIBUTING.md` updated to explain the `docs/lineage` folder structure.

### Review
- [ ] Code review verifies cost controls (loop limits) are in place.

---

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-01-23 | **APPROVED** | Previous issue (unbounded loop) addressed via Section 2.5 and 9. |

**Final Status:** DRAFT - PENDING REVIEW