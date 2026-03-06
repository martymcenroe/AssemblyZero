# Implementation Spec: 0600 - AST-Based Import Sentinel

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #600 |
| LLD | `docs/lld/active/LLD-600.md` |
| Generated | 2026-03-05 |
| Status | APPROVED |

## 1. Overview
Catch missing imports early.

## 2. Files to Implement
| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/utils/ast_sentinel.py` | Add | AST logic |
| 2 | `tests/unit/test_ast_sentinel.py` | Add | Tests |
| 3 | `assemblyzero/workflows/requirements/nodes/validate_mechanical.py` | Modify | Integration |

## 3. Current State
### 3.1 `assemblyzero/workflows/requirements/nodes/validate_mechanical.py`
```python
def validate_mechanical(): pass
```

## 4. Data Structures
None.

## 5. Function Specifications
`analyze_file(path)`

## 6. Change Instructions
### 6.1 `assemblyzero/utils/ast_sentinel.py` (Add)
```python
import ast
import builtins
# ... implementation ...
```

## 7. Pattern References
None.

## 8. Dependencies & Imports
| Import | Source |
|--------|--------|
| `ast` | stdlib |

## 9. Test Mapping
| Test ID | Function | Expected |
|---------|----------|----------|
| T010 | `analyze_file` | Success |

## 10. Implementation Notes
None.
