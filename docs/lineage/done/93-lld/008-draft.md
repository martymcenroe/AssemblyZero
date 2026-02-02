# 93 - Feature: The Scout: External Intelligence Gathering Workflow

## 1. Context & Goal
* **Issue:** #93
* **Objective:** Create a proactive research workflow that searches GitHub for best practices, analyzes top implementations, compares them against internal code, and produces an "Innovation Brief" to identify gaps.
* **Status:** Draft
* **Related Issues:** None - Foundational Feature.

### Open Questions
* **Tokenizer Compatibility:** The issue suggests `tiktoken` (OpenAI-based) for Gemini (Google-based) cost estimation.
    *   *Decision:* We will use `tiktoken` with the `cl100k_base` encoding as a local, high-speed approximation, applying a 10% safety buffer to the count to account for vocabulary differences before checking against the limit.
* **File System Safety:** How to ensure the tool doesn't read sensitive files outside the source tree or write reports to arbitrary locations?
    *   *Decision:* Implement strict path validation utilities (`security.validate_read_path`, `security.validate_write_path`) to enforce confinement to the project root and `ideas/active/` directory respectively.
* **Indirect Prompt Injection:** External READMEs are untrusted input and may contain instructions meant to hijack the LLM.
    *   *Decision:* Implement a `content_safety` module to sanitize external text and encase it in strict XML delimiters (`<external_context>`) within the prompt to enforce data/instruction separation.

## 2. Proposed Changes

### 2.1 Files Changed
| File Path | Description |
|-----------|-------------|
| `agentos/workflows/scout/__init__.py` | Package initialization. |
| `agentos/workflows/scout/graph.py` | Defines LangGraph nodes and edges. |
| `agentos/workflows/scout/nodes.py` | Implementation of Explorer, Extractor, Analyst, and Scribe logic with dynamic budget checks. |
| `agentos/workflows/scout/prompts.py` | Prompts for Gemini analysis with injection safeguards. |
| `agentos/workflows/scout/templates.py` | Markdown templates for Innovation Briefs. |
| `agentos/workflows/scout/budget.py` | **NEW**: Dynamic token tracking logic to enforce limits during execution. |
| `agentos/workflows/scout/security.py` | Path validation logic and file existence checks. |
| `agentos/workflows/scout/content_safety.py` | Utilities for truncating and sanitizing untrusted external text. |
| `tools/run_scout_workflow.py` | CLI entry point with argument parsing, offline mode, and overwrite protection. |
| `agentos/workflows/__init__.py` | Registration of the scout workflow. |
| `docs/0003-file-inventory.md` | Inventory update. |

### 2.2 Dependencies
* **PyGithub**: For GitHub Search and Content API interactions.
* **tiktoken**: For local, offline token estimation.
* **google-generativeai**: Existing dependency for LLM interactions.
* **langgraph**: Existing dependency for workflow orchestration.

### 2.3 Data Structures

**`agentos/workflows/scout/graph.py`**

```python
from typing import TypedDict, List, Optional

class ExternalRepo(TypedDict):
    name: str           # "owner/repo"
    url: str            # html_url
    stars: int
    description: str
    license_type: str   # e.g., "MIT", "Apache-2.0", "Unknown"
    readme_summary: str # Summarized content (truncated)
    code_snippets: str  # Relevant code content (truncated)

class ScoutState(TypedDict):
    topic: str
    internal_file_path: Optional[str]
    internal_code_content: Optional[str]
    min_stars: int
    max_tokens: int     # Budget limit
    current_token_usage: int # Running total
    found_repos: List[ExternalRepo]
    gap_analysis: Optional[str]
    final_brief: str
    errors: List[str]
    offline_mode: bool  # Flag for dev/testing
```

### 2.4 Function Signatures

**`agentos/workflows/scout/budget.py`**

```python
def check_and_update_budget(current_usage: int, new_text: str, limit: int) -> tuple[int, bool]:
    """
    Calculates token count of new_text using tiktoken.
    Returns (new_usage, is_within_limit).
    Applies 1.1x safety buffer factor internally.
    """
    pass

def truncate_to_fit(text: str, remaining_tokens: int) -> str:
    """
    Truncates text to fit within remaining_tokens budget.
    """
    pass
```

**`agentos/workflows/scout/security.py`**

```python
def validate_read_path(path: str, base_dir: str = ".") -> str:
    """
    Validates that 'path' exists and is strictly within 'base_dir'.
    Prevents path traversal.
    """
    pass

def get_safe_write_path(filename: str, output_dir: str = "ideas/active", overwrite: bool = False) -> str:
    """
    Validates 'filename' within 'output_dir'.
    If file exists and overwrite is False, appends timestamp to filename.
    Returns absolute safe path.
    """
    pass
```

**`agentos/workflows/scout/nodes.py`**

```python
def extractor_node(state: ScoutState) -> ScoutState:
    """
    Fetches content. 
    Enforces dynamic token budget: stops fetching or truncates content 
    if state['max_tokens'] is reached.
    If state['offline_mode'] is True, loads from fixtures.
    """
    pass
```

### 2.5 Logic Flow (Pseudocode)

**CLI (`tools/run_scout_workflow.py`)**

```python
def main():
    args = parse_arguments() # includes --offline, --force
    
    # 1. Path Safety & Content Loading
    internal_content = None
    if args.internal:
        try:
            safe_path = security.validate_read_path(args.internal)
            internal_content = read_file(safe_path)
        except ValueError as e:
            print_error(f"Security Error: {e}")
            return

    # 2. Pre-flight Token Estimation (Static Check)
    est_internal = budget.count_tokens(internal_content or "")
    if est_internal > args.max_tokens:
        print_error("Budget Exceeded by internal file alone.")
        return

    # 3. Privacy Confirmation
    if args.internal and not args.yes and not args.offline:
        warn_user_data_transmission(args.internal)
        if not get_user_confirmation():
            return

    # 4. Graph Execution
    state = {
        "topic": args.topic,
        "internal_code_content": internal_content,
        "max_tokens": args.max_tokens,
        "current_token_usage": est_internal, # Initial usage
        "offline_mode": args.offline,
        # ... other fields
    }
    
    final_state = workflow_graph.invoke(state)

    # 5. Output with Overwrite Protection
    if args.format == "json":
        print_json(final_state)
    else:
        base_filename = f"innovation-{slugify(args.topic)}.md"
        safe_out = security.get_safe_write_path(base_filename, overwrite=args.force)
        write_file(safe_out, final_state["final_brief"])
        print(f"Brief written to {safe_out}")
```

**Extractor Node Logic (Dynamic Budgeting)**

```python
def extractor_node(state):
    updated_repos = []
    current_usage = state['current_token_usage']
    
    repos_to_process = state['found_repos'][:3] # Top 3 only
    
    for repo in repos_to_process:
        # Check budget before fetch
        if current_usage >= state['max_tokens']:
            break # Stop processing if budget full
            
        # Fetch (Mock if offline)
        if state['offline_mode']:
            readme_raw = load_fixture("readme")
            license_raw = "MIT"
        else:
            readme_raw = github_api.get_readme(repo.url)
            license_raw = github_api.get_license(repo.url)
        
        # Sanitize
        clean_readme = content_safety.sanitize_external_content(readme_raw)
        
        # Calculate cost
        new_usage, fits = budget.check_and_update_budget(current_usage, clean_readme, state['max_tokens'])
        
        if not fits:
            # Truncate to fill remaining budget exactly
            remaining = state['max_tokens'] - current_usage
            clean_readme = budget.truncate_to_fit(clean_readme, remaining)
            current_usage = state['max_tokens']
            repo['readme_summary'] = clean_readme
            repo['license_type'] = license_raw
            updated_repos.append(repo)
            break # Budget full after this
        else:
            current_usage = new_usage
            repo['readme_summary'] = clean_readme
            repo['license_type'] = license_raw
            updated_repos.append(repo)
    
    return {
        "found_repos": updated_repos,
        "current_token_usage": current_usage
    }
```

### 2.6 Technical Approach
*   **Module Location:** `agentos/workflows/scout/`
*   **Design Pattern:** Chain of Responsibility (LangGraph).
*   **Budgeting Strategy:** Hybrid.
    *   **Static:** Pre-flight check in CLI to fail fast if internal file is huge.
    *   **Dynamic:** `budget.py` logic invoked inside `Extractor` node to cap external data accumulation in real-time.
*   **Offline Mode:** Uses dependency injection pattern (or simple conditionals) to swap API calls for local fixtures, enabling zero-cost development.
*   **Safety:**
    *   **File Isolation:** `security.py` strict boundaries.
    *   **Injection Defense:** XML fencing in prompts.

## 3. Requirements
1.  **Repository Search:** Retrieve repositories > 500 stars matching the topic via GitHub API (or fixtures in Offline mode).
2.  **License Capture:** Extract license SPDX identifier (e.g., "MIT") for every external repository.
3.  **Strict Path Validation:** Reject paths containing `..` or pointing outside the project root.
4.  **Overwrite Protection:** Do not overwrite existing briefs unless `--force` is used; otherwise append timestamp.
5.  **Offline Capability:** Support `--offline` flag to run workflow without network/cost using local data.
6.  **Dynamic Budget Enforcement:** Extractor node must stop or truncate content *during* execution if token limit is reached.
7.  **Injection Defense:** Treat all external content as untrusted; sanitizing and XML-fencing it in prompts.
8.  **Data Privacy:** Require interactive confirmation (or `--yes`) before sending internal code to LLM.

## 4. Alternatives Considered

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| **Static Budget Only** | Simple implementation. | Prone to overruns if external READMEs are huge. | **Dynamic + Static** - Safer, prevents API errors. |
| **Fail on Overwrite** | Prevents accidental data loss. | Annoying for iterative use. | **Timestamp Suffix** - Preserves history, user friendly. |
| **Mock Object Injection** | Cleanest testing architecture. | High complexity for simple CLI tool. | **Flag-based Logic (`if offline`)** - Sufficient for this scope. |

## 5. Data & Fixtures

### 5.1 Data Sources
| Source | Type | Attributes |
|--------|------|------------|
| **Internal Code** | File | Content, Path |
| **GitHub Search** | API | Repo Name, Stars, URL |
| **GitHub Content** | API | README.md (Truncated), LICENSE |

### 5.2 Data Pipeline
```ascii
[CLI Input] -> [Path Validator] -> [Static Token Check] -> [Confirmer]
                                         |
                                         v
[LangGraph] -> [Budget Manager] <-> [Extractor Node] <-> [GitHub API / Fixtures]
      |                                  |
      |                          (Stop if Budget Full)
      v
[Gap Analyst Node] -> [LLM (Gemini) / Mock]
      |
      v
[Scribe Node] -> [Overwrite Protector] -> [File System]
```

### 5.3 Test Fixtures
| Fixture | Description |
|---------|-------------|
| `tests/fixtures/scout/github_search_response.json` | Mocked search results for offline mode. |
| `tests/fixtures/scout/github_content_response.json` | Mocked README/License for offline mode. |
| `tests/fixtures/scout/malicious_readme.md` | README containing fake instructions (Prompt Injection test). |
| `tests/fixtures/golden-brief-summary.md` | Expected summary for similarity testing. |

### 5.4 Deployment Pipeline
*   **Development:** Use `--offline` for logic changes.
*   **Environment:** Requires `GITHUB_TOKEN` and `GOOGLE_API_KEY` for live runs.

## 6. Diagram

### 6.1 Mermaid Quality Gate
- [x] Diagram exists
- [x] Flows clearly defined
- [x] Includes Budget Loop
- [x] Includes Offline Logic

### 6.2 Diagram
```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Sec as Security/Budget
    participant Graph as LangGraph
    participant Extractor
    participant API as GitHub/Fixtures

    User->>CLI: run(--max-tokens 30k)
    CLI->>Sec: check_static_budget(internal_file)
    
    alt budget ok
        CLI->>Graph: invoke(state)
        Graph->>Extractor: extract_external_data()
        
        loop Each Repo
            Extractor->>Sec: check_remaining_budget(current_usage)
            
            alt has budget
                Extractor->>API: fetch_content()
                API-->>Extractor: content
                Extractor->>Sec: update_usage(content)
            else budget full
                Extractor-->>Graph: Stop Extraction
            end
        end
        
        Graph->>CLI: Final Brief
        CLI->>Sec: get_safe_write_path()
        CLI->>User: Write File
    end
```

## 7. Security Considerations

| Concern | Mitigation |
|---------|------------|
| **Path Traversal** | `security.validate_read_path` and `validate_write_path` ensure operations are confined to project root and `ideas/active/`. |
| **Indirect Prompt Injection** | External content is truncated and strictly enclosed in `<external_context>` XML tags within the prompt. |
| **Budget Overrun** | **Dynamic Budgeting:** Real-time token counting in `Extractor` node ensures hard stop before LLM call. |
| **Data Loss (Overwrite)** | Output filenames are timestamped if collision occurs. |
| **Internal Code Leakage** | Explicit user confirmation required. HTTPS encryption. |

## 8. Performance Considerations

| Metric | Budget | Strategy |
|--------|--------|----------|
| **Analysis Latency** | < 60s | Use Gemini 1.5 Flash. Offline mode skips LLM. |
| **Token Usage** | < 30k/run | Dynamic tracking halts data collection when limit is hit. |
| **API Rate Limits** | 5000/hr | Exponential backoff. |

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **Tokenizer Mismatch** | Estimate vs Actual variance. | Low | 10% safety buffer in `budget.py`. |
| **Offline Drift** | Fixtures diverge from API. | Medium | Periodic fixture refresh required. |
| **Partial Context** | Budget cuts off useful info. | Medium | Prioritize README header and Architecture sections before truncating. |

## 10. Verification & Testing

### 10.1 Test Scenarios
| ID | Scenario | Type | Input | Output | Criteria |
|----|----------|------|-------|--------|----------|
| T1 | Happy Path (Live) | Integ | `topic="async", internal="agentos/core.py"` | `.md` file | File created, contains License info. |
| T2 | Offline Mode | Unit | `--offline --topic "test"` | `.md` file | Uses fixture data, no API calls. |
| T3 | Dynamic Budget | Unit | `max_tokens=500` | Truncated State | Extractor stops after partial README read. |
| T4 | Overwrite Protect | Unit | Run twice on same topic | `file.md`, `file-timestamp.md` | Second run does not delete first file. |
| T5 | Prompt Injection | Integ | Malicious fixture | Safe Brief | Injection ignored by LLM. |

### 10.2 Test Commands
```bash
# Security & Budget Unit Tests
pytest tests/workflows/scout/test_security.py
pytest tests/workflows/scout/test_budget.py

# Offline Workflow Test
python tools/run_scout_workflow.py --topic "offline test" --offline --yes

# Overwrite Protection Test
touch "ideas/active/innovation-test.md"
python tools/run_scout_workflow.py --topic "test" --offline --yes
ls -l ideas/active/innovation-test*
```

### 10.3 Manual Tests (Only If Unavoidable)
| ID | Description |
|----|-------------|
| M1 | Run without `--yes` and manually decline confirmation. |

## 11. Definition of Done

### Code
- [ ] `agentos/workflows/scout/` package implemented.
- [ ] `budget.py` implemented with dynamic checks and safety buffer.
- [ ] `security.py` implemented with path validation and overwrite protection.
- [ ] CLI supports `--offline` and `--force`.

### Tests
- [ ] Unit tests for `budget.py` cover limits and truncation.
- [ ] Unit tests for `security.py` cover overwrite scenarios.
- [ ] Integration tests run in offline mode by default.

### Documentation
- [ ] `docs/0003-file-inventory.md` updated.
- [ ] Wiki updated with Scout usage and Offline mode instructions.

### Review
- [ ] Security Review passed.
- [ ] Code Review passed.

---

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| - | - | - | - |

**Final Status:** DRAFT - PENDING REVIEW