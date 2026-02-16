---
repo: martymcenroe/AgentOS
issue: 99
url: https://github.com/martymcenroe/AgentOS/issues/99
fetched: 2026-02-05T00:35:52.516268Z
---

# Issue #99: Schema-driven project structure: eliminate tool/standard drift

## Problem

`new-repo-setup.py` has **hardcoded** directory structure that duplicates what's documented in standard 0009. The tool even references the standard in its docstring but doesn't read from it:

```python
# Line 21-22:
"""
See: docs/standards/0009-canonical-project-structure.md
"""

# Lines 42-80: HARDCODED structure
DOCS_STRUCTURE = [
    "docs/adrs",
    "docs/standards",
    ...
]
```

This creates maintenance debt - two places to update when structure changes, inevitable drift.

## Solution

Create a JSON schema as the **single source of truth** for project structure. Both the standard documentation and the tool read from it.

```
docs/standards/0009-structure-schema.json   ← Canonical source
        │
        ├──→ 0009-canonical-project-structure.md  (references schema)
        │
        └──→ new-repo-setup.py (imports and uses schema)
```

## Schema Design

```json
{
  "version": "1.0",
  "directories": {
    "docs": {
      "required": true,
      "children": {
        "adrs": { "required": true, "description": "Architecture Decision Records" },
        "standards": { "required": true },
        "lineage": {
          "required": false,
          "children": {
            "active": { "required": true },
            "done": { "required": true }
          }
        }
      }
    },
    "tests": {
      "required": true,
      "children": {
        "unit": { "required": true },
        "integration": { "required": true }
      }
    }
  },
  "files": {
    "CLAUDE.md": { "required": true, "template": "claude-md.template" },
    "README.md": { "required": true }
  }
}
```

## Acceptance Criteria

- [ ] Create `docs/standards/0009-structure-schema.json`
- [ ] Update `new-repo-setup.py` to read structure from schema (remove hardcoded lists)
- [ ] Update `new-repo-setup.py --audit` to validate against schema
- [ ] Standard 0009 references the schema as authoritative source
- [ ] Schema includes `docs/lineage/` structure

## Scope

- **In scope:** Schema creation, tool refactor, standard update
- **Out of scope:** Generating markdown docs from schema (future enhancement)

## Labels

enhancement, dx, infrastructure