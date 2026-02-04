# 199 - Feature: Schema-driven project structure: eliminate tool/standard drift

## 1. Context & Goal
* **Issue:** #99
* **Objective:** Replace hardcoded directory lists in `new-repo-setup.py` with a dynamic system that reads from a canonical JSON schema file, ensuring alignment between documentation and tooling.
* **Status:** Draft
* **Related Issues:** Standard 0009 (Canonical Project Structure)

### Open Questions
None - requirements and schema structure are well-defined in the issue.

## 2. Proposed Changes

### 2.1 Files Changed
| File | Action | Description |
| :--- | :--- | :--- |
| `docs/standards/0009-structure-schema.json` | **Create** | The new single source of truth defining the project structure. |
| `new-repo-setup.py` | **Modify** | Remove `DOCS_STRUCTURE` constants; add JSON loading and recursive creation/auditing logic. |
| `docs/standards/0009-canonical-project-structure.md` | **Modify** | Update text to reference the JSON file as the authoritative source. |

### 2.2 Dependencies
*   **Built-in:** `json`, `pathlib`, `typing`
*   **External:** None.

### 2.3 Data Structures

```python
from typing import TypedDict, Dict, Optional, Union

class FileNode(TypedDict):
    required: bool
    template: Optional[str]
    description: Optional[str]

class DirectoryNode(TypedDict):
    required: bool
    description: Optional[str]
    children: 'Dict[str, DirectoryNode]' # Recursive definition

class ProjectSchema(TypedDict):
    version: str
    directories: Dict[str, DirectoryNode]
    files: Dict[str, FileNode]
```

### 2.4 Function Signatures

```python
def load_schema(schema_path: str = "docs/standards/0009-structure-schema.json") -> Dict:
    """
    Loads and validates the JSON schema file.
    Raises FileNotFoundError or json.JSONDecodeError on failure.
    """
    pass

def create_structure(base_path: Path, schema: Dict, dry_run: bool = False) -> None:
    """
    Orchestrates the creation of directories and files based on schema.
    Delegates to _create_recursive for directories.
    """
    pass

def _create_recursive(current_path: Path, structure: Dict) -> None:
    """
    Recursively traverses the 'children' dictionary to create directories.
    """
    pass

def audit_structure(base_path: Path, schema: Dict) -> List[str]:
    """
    Traverses the schema and checks if required directories/files exist.
    Returns a list of missing paths (empty list if compliant).
    """
    pass
```

### 2.5 Logic Flow (Pseudocode)

**Main Execution:**
```text
1. Define SCHEMA_PATH = "docs/standards/0009-structure-schema.json"
2. Load JSON from SCHEMA_PATH into 'schema_data'
3. IF mode is CREATE:
    a. Call create_structure(root, schema_data)
    b. Iterate 'directories':
        i. Create directory
        ii. Recurse into 'children'
    c. Iterate 'files':
        i. Create empty file or apply template if missing
4. IF mode is AUDIT:
    a. Call audit_structure(root, schema_data)
    b. Return list of violations
    c. Print pass/fail
```

**Recursive Creation (_create_recursive):**
```text
Input: path, node_data
1. If node_data['required'] is True OR path doesn't exist:
    a. os.makedirs(path, exist_ok=True)
2. If 'children' in node_data:
    a. For child_name, child_data in children:
        b. next_path = path / child_name
        c. CALL _create_recursive(next_path, child_data)
```

### 2.6 Technical Approach
*   **Design Pattern:** Configuration-driven Logic. The logic remains static; the behavior is determined entirely by the external JSON resource.
*   **Recursion:** Since the directory structure is a tree, recursive functions are the most robust way to handle arbitrary depth (e.g., `docs/lineage/active`).
*   **Validation:** The script will fail fast if the schema JSON is malformed, preventing partial repo setup.

## 3. Requirements
1.  **Schema Source:** The system MUST read from `docs/standards/0009-structure-schema.json`.
2.  **Directory Creation:** The system MUST create nested directories defined in the schema's `directories` key.
3.  **File Stubbing:** The system MUST create files defined in the schema's `files` key if they do not exist.
4.  **Audit Capability:** The system MUST be able to report missing required directories and files when run with `--audit`.
5.  **Backward Compatibility:** The script MUST continue to function using standard library modules only (no `pip install` required for setup).

## 4. Alternatives Considered

| Alternative | Pros | Cons | Decision |
| :--- | :--- | :--- | :--- |
| **YAML Schema** | Easier for humans to read. | Requires `PyYAML` (pip install) which complicates setup scripts. | **Rejected** (Stick to stdlib `json`) |
| **Python Dict in Shared Module** | Full programmatic control. | Documentation cannot easily "read" a Python file to display structure. | **Rejected** |
| **JSON Schema** | Native stdlib support; Language agnostic; Validatable. | Strictly hierarchical, comments not supported natively. | **Selected** |

## 5. Data & Fixtures

### 5.1 Data Sources
| Source | Type | Attributes |
| :--- | :--- | :--- |
| `0009-structure-schema.json` | JSON | `version`, `directories` (nested), `files` |

### 5.2 Data Pipeline
```text
+-------------------+       +---------------------+       +-------------------+
| JSON Schema File  | ----> | new-repo-setup.py | ----> | File System (OS)  |
+-------------------+       +---------------------+       +-------------------+
```

### 5.3 Test Fixtures
*   **`tests/fixtures/valid_schema.json`**: A minimal valid schema with 1 directory and 1 file.
*   **`tests/fixtures/invalid_schema.json`**: Malformed JSON content.

### 5.4 Deployment Pipeline
*   **Development Only:** This tool is used during the initialization of the repository or during CI checks (Linting/Auditing).

## 6. Diagram

### 6.1 Mermaid Quality Gate
- [x] Diagram type: Flowchart
- [x] Nodes valid
- [x] Connections valid

### 6.2 Diagram
```mermaid
flowchart TD
    A[Start new-repo-setup.py] --> B{Load JSON Schema};
    B -- Success --> C{Check Mode};
    B -- Error --> Z[Exit with Error];
    
    C -- --audit --> D[Traverse File System];
    D --> E{Match Schema?};
    E -- Yes --> F[Print OK];
    E -- No --> G[Print Missing Paths];
    
    C -- (default) --> H[Iterate Directories];
    H --> I[os.makedirs recursive];
    I --> J[Iterate Files];
    J --> K[Touch files];
    K --> L[Done];
```

## 7. Security Considerations
| Concern | Mitigation |
| :--- | :--- |
| **Path Traversal** | The schema should be trusted (it is in the repo), but the script will validate that paths do not contain `..` or absolute paths pointing outside the repo root. |
| **Malicious JSON** | Use `json.load` which is generally safe from execution exploits, unlike pickle. |

## 8. Performance Considerations
| Metric | Budget | Notes |
| :--- | :--- | :--- |
| **Execution Time** | < 500ms | JSON parsing and FS stats are very fast. |
| **Memory Usage** | < 10MB | Schema is small text. |

## 9. Risks & Mitigations
| Risk | Impact | Likelihood | Mitigation |
| :--- | :--- | :--- | :--- |
| **Schema Syntax Error** | Tool fails completely. | Low | Add a pre-commit hook or test case that validates the JSON syntax. |
| **Structure Drift** | Docs and Code mismatch. | None | Solved by this design (Single Source of Truth). |

## 10. Verification & Testing

### 10.1 Test Scenarios
| ID | Scenario | Type | Input | Output | Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1 | Load Valid Schema | Unit | Valid JSON file | Dict object | Keys `directories`, `files` present. |
| T2 | Create Nested Dirs | Integ | Schema with `a/b/c` | FS State | Directory `a/b/c` exists. |
| T3 | Audit Missing Dir | Integ | Schema requires `x`; FS empty | List `['x']` | Function detects missing item. |
| T4 | Audit Compliance | Integ | Schema requires `x`; FS has `x` | Empty List | Function detects compliance. |
| T5 | Invalid JSON | Unit | `{ "version": ... ` (unclosed) | Raise Exception | Script handles parse error gracefully. |

### 10.2 Test Commands
```bash
# Run unit tests
python -m unittest tests/test_repo_setup.py

# Manual verification (Dry Run)
python new-repo-setup.py --audit
```

### 10.3 Manual Tests (Only If Unavoidable)
N/A - All scenarios automated via unittest using `tempfile.TemporaryDirectory`.

## 11. Definition of Done

### Code
- [ ] `docs/standards/0009-structure-schema.json` created with version 1.0 structure.
- [ ] `new-repo-setup.py` updated to import `json` and remove `DOCS_STRUCTURE`.
- [ ] Recursive creation logic implemented.
- [ ] Audit logic implemented.

### Tests
- [ ] Unit tests for schema loading.
- [ ] Integration tests for directory creation (using temp dirs).

### Documentation
- [ ] Standard 0009 updated to point to the JSON file.
- [ ] Script docstrings updated.

### Review
- [ ] PR reviewed by Tech Lead.
- [ ] Local run of `--audit` passes.

---

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| - | - | - | - |

**Final Status:** DRAFT - PENDING REVIEW