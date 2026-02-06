# RAG Injection: Implementation Context (The Smart Engineer)

**Context:** We have designed the "Librarian" (#DN-002) to inject architectural standards into LLDs, and "The Historian" to check for duplicate issues. Now we need to solve the **Engineering Context** problem.

## Problem

**The "Hallucinating Junior Engineer" Failure Mode:**
When the Coder Node (`N3_Coder`) implements a feature, it often:

1. **Reinvents Wheels:** Writes a new `log_to_file` function because it doesn't know `assemblyzero.core.audit` exists.
2. **Hallucinates Imports:** Guesses `from assemblyzero.utils import logger` (which doesn't exist) instead of the correct path.
3. **Ignores Patterns:** Uses `requests` directly instead of your `GeminiClient` wrapper, bypassing rotation and logging logic.

**Result:** The code fails "Lint/Audit" gates or requires heavy human refactoring.

## Goal

Implement a **Codebase Retrieval System** that gives the Coder Node access to the *actual* project utilities and patterns before it writes a single line of code.

1. **Index:** Expand `tools/rebuild_knowledge_base.py` to parse and chunk Python code (`.py` files).
2. **Retrieve:** Analyze the **LLD** (Low Level Design) to extract technical keywords (e.g., "Audit", "Gemini", "Config").
3. **Inject:** Fetch the actual function signatures/classes from the codebase and inject them into the Coder's system prompt.

## Proposed Architecture

### 1. Codebase Indexing (AST-Based)

Enhance `tools/rebuild_knowledge_base.py`.

* **Target:** Scan `assemblyzero/**/*.py` and `tools/**/*.py`.
* **Strategy:** Don't just chunk by lines. Use Python's `ast` module to chunk by **Class** and **Top-Level Function**.
* **Metadata:** Tag chunks with `type: code` and `module: assemblyzero.core.audit` (for example).

### 2. The "Tech Lead" Logic (in `run_implementation_workflow.py`)

Modify the prompt construction for `N3_Coder`.

* **Step A: Keyword Extraction**
* *Input:* The Approved LLD content.
* *Action:* Extract top 5 technical nouns (e.g., "GovernanceAuditLog", "GeminiClient", "SqliteSaver").


* **Step B: Retrieval**
* *Action:* Query the Vector Store (`collection='codebase'`) for these keywords.
* *Threshold:* High strictness (> 0.75) to avoid noise.


* **Step C: Context Injection**
* *Action:* Append the retrieved code snippets to the prompt under a new section:
```markdown
## Reference Codebase
Use these existing utilities. DO NOT reinvent them.

[Source: assemblyzero/core/audit.py]
class GovernanceAuditLog:
    def log(self, entry: dict): ...

```





### 3. Integration Point

This sits inside the **N3_Coder** node of the `Implementation Workflow` (from the previous brief). It runs *before* the prompt is sent to the LLM.

## Success Criteria

* [ ] The Vector Store contains chunks for `assemblyzero/core/audit.py` and `assemblyzero/core/gemini_client.py`.
* [ ] When an LLD mentions "logging", the Coder context automatically receives the `GovernanceAuditLog` class definition.
* [ ] The generated implementation uses `from assemblyzero.core.audit import GovernanceAuditLog` correctly on the first try.
* [ ] Zero `ImportError` failures caused by hallucinated module paths.