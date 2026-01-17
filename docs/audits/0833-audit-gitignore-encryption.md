# 0833 - Gitignore Encryption Audit

**File:** `docs/audits/0833-audit-gitignore-encryption.md`
**Status:** Active
**Frequency:** On-demand (--ultimate tier only)
**Auto-Fix:** No (recommendations only)
**Tier:** Ultimate

---

## 1. Purpose

Review all `.gitignore` entries and recommend whether each should be:
- **ENCRYPT** - Sensitive data that should travel with the repo (use git-crypt)
- **IGNORE** - Build artifacts, caches, truly local files (keep in .gitignore)
- **REVIEW** - Unknown pattern, needs human decision

**Why this audit exists:**

The default developer reflex is to .gitignore anything sensitive. But this creates a problem:
- Gitignored files don't travel with the repo
- No backup in version control
- Lost when switching machines or cloning fresh

For pre-issue ideation, patent concepts, and private notes, encryption is better than exclusion.

---

## 2. Audit Scope

### 2.1 What Gets Audited

| Source | Description |
|--------|-------------|
| `.gitignore` (root) | Project-level ignore patterns |
| `.gitignore` (subdirs) | Nested ignore patterns |
| `.git/info/exclude` | Local-only excludes |

### 2.2 What Gets Recommended

| Recommendation | Criteria | Examples |
|----------------|----------|----------|
| **ENCRYPT** | Contains sensitive data that should persist | `ideas/`, `notes/`, `drafts/`, `.env.local` |
| **IGNORE** | Build artifacts, caches, machine-specific | `node_modules/`, `__pycache__/`, `.DS_Store` |
| **REVIEW** | Unknown pattern, context-dependent | `local/`, `scratch/`, `temp/` |

---

## 3. Classification Signals

### 3.1 ENCRYPT Signals

Patterns that suggest encryption over gitignore:

```python
ENCRYPT_SIGNALS = [
    'ideas',
    'notes',
    'drafts',
    'private',
    'secrets',
    'credentials',
    'keys',
    '.env',
    'config.local',
    'personal',
    'todo',
    'journal',
]
```

### 3.2 IGNORE Signals

Patterns that are correctly gitignored:

```python
IGNORE_SIGNALS = [
    'node_modules',
    '__pycache__',
    '.pytest_cache',
    'dist',
    'build',
    '.next',
    'coverage',
    '*.pyc',
    '*.pyo',
    '.DS_Store',
    'Thumbs.db',
    '*.log',
    'tmp',
    'temp',
    '.venv',
    'venv',
    '.env',  # If it's a Python venv, not secrets
    '*.egg-info',
    '.mypy_cache',
    '.ruff_cache',
]
```

### 3.3 Context-Dependent

Some patterns need human review:

| Pattern | Could Be... |
|---------|-------------|
| `local/` | Local configs (ENCRYPT) or local builds (IGNORE) |
| `scratch/` | Scratch notes (ENCRYPT) or scratch builds (IGNORE) |
| `data/` | Sensitive data (ENCRYPT) or test fixtures (IGNORE) |
| `.env` | Secrets file (ENCRYPT) or Python venv (IGNORE) |

---

## 4. Audit Procedure

### 4.1 Automated Analysis

```bash
# Run the audit
python tools/audit-gitignore-encryption.py --project /path/to/project
```

### 4.2 Manual Review

For each REVIEW recommendation:
1. Inspect the actual contents of the ignored path
2. Ask: "Does this need to travel with the repo?"
3. Ask: "Would I lose important work if I cloned fresh?"
4. Decide: ENCRYPT or IGNORE

### 4.3 Taking Action

For patterns recommended as ENCRYPT:

1. Remove from `.gitignore`
2. Add to `.gitattributes` with git-crypt rules
3. Ensure git-crypt is initialized
4. Commit the change

---

## 5. Output Format

```markdown
## Gitignore Encryption Audit Results

**Project:** /path/to/project
**Date:** YYYY-MM-DD
**Auditor:** [Model Name]

### Summary

| Recommendation | Count |
|----------------|-------|
| ENCRYPT | 2 |
| IGNORE | 15 |
| REVIEW | 3 |

### Detailed Findings

| Pattern | Location | Recommendation | Reason |
|---------|----------|----------------|--------|
| `ideas/` | .gitignore | **ENCRYPT** | Contains sensitive ideation that should travel with repo |
| `node_modules/` | .gitignore | IGNORE | Build artifact, correctly gitignored |
| `local-notes/` | .gitignore | REVIEW | Unknown pattern, needs human decision |

### Recommended Actions

1. **ENCRYPT:** Move `ideas/` from .gitignore to git-crypt encryption
2. **REVIEW:** Inspect `local-notes/` to determine if it contains persistent data
```

---

## 6. Integration

### 6.1 Trigger Conditions

This audit runs ONLY when:
- Explicitly requested: `/audit 0833`
- Ultimate tier requested: `/audit --ultimate`

It does NOT run during:
- Standard audits: `/audit`
- Full audits: `/audit --full`

### 6.2 Why Ultimate Tier

- Requires inspecting potentially large directories
- Human judgment required for REVIEW items
- Not a routine check (run once per project setup, then occasionally)

---

## 7. Audit Record

| Date | Auditor | Project | Findings Summary |
|------|---------|---------|------------------|
| | | | |

---

## 8. Related

- [Issue #18](https://github.com/martymcenroe/AgentOS/issues/18) - Ideas folder with git-crypt encryption
- [LLD: Ideas Folder Encryption](../reports/18/lld-ideas-folder-encryption.md)
- [0800 - Audit Index](0800-audit-index.md) - Master audit list
