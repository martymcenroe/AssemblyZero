# 0838 - Broken Reference Audit

**Status:** Active
**Created:** 2026-01-20
**Purpose:** Find and fix broken file/path references after structural changes

---

## Overview

After renaming directories or migrating files, documentation and code may contain stale references. This audit identifies and fixes them.

**Common causes:**
- Directory renames (backend→src, test→tests, extension→extensions)
- Report migrations (per-issue subdirs → flat active/done)
- File relocations (RUNBOOK.md → docs/runbooks/)

---

## What to Scan

| File Type | Reference Patterns |
|-----------|-------------------|
| Markdown (*.md) | `[text](path)`, `` `path` ``, code blocks with paths |
| Python (*.py) | Import paths, string paths, comments |
| JavaScript (*.js) | Import/require paths, string paths |
| JSON (*.json) | Path values in config files |
| YAML (*.yaml) | Path values |

---

## Quick Audit (Single Repo)

### Step 1: Find potential path references

```bash
# Find markdown links that might be broken
grep -rn --include="*.md" -E '\]\([^)]+\)' /c/Users/mcwiz/Projects/{REPO}/ | grep -v node_modules | grep -v '.git'

# Find backtick paths
grep -rn --include="*.md" -E '`[^`]*(/|\\\\)[^`]*`' /c/Users/mcwiz/Projects/{REPO}/ | grep -v node_modules
```

### Step 2: Check for known stale patterns

```bash
# Old patterns that should no longer exist
grep -rn --include="*.md" -E '(backend/|/backend|test/[^s]|extension/[^s])' /c/Users/mcwiz/Projects/{REPO}/
grep -rn --include="*.md" 'docs/reports/[0-9]+/' /c/Users/mcwiz/Projects/{REPO}/
```

### Step 3: Validate markdown links exist

```bash
# Extract and test each link (manual review needed)
grep -ohP '\]\(\K[^)]+' /c/Users/mcwiz/Projects/{REPO}/**/*.md | sort -u
```

---

## Known Stale Patterns (Post-Migration)

| Old Pattern | New Pattern | Affected Repos |
|-------------|-------------|----------------|
| `backend/` | `src/` | Talos |
| `extension/` | `extensions/` | Clio |
| `test/` | `tests/` | Clio |
| `docs/reports/{issue}/` | `docs/reports/done/1{issue}-` | Aletheia, data-harvest |
| `RUNBOOK.md` (root) | `docs/runbooks/30001-*.md` | Clio |

---

## Full Audit Script

Run from AgentOS tools:

```bash
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/audit-broken-refs.py --repo {REPO_PATH}
```

### Script behavior:
1. Scan all .md, .py, .js, .json files
2. Extract path-like strings
3. Validate each path exists (relative to repo root)
4. Report broken references with line numbers
5. Suggest fixes based on known migrations

---

## Manual Fix Process

1. Run the audit to get list of broken refs
2. For each broken reference:
   - Determine if path moved or was deleted
   - Update reference to new path
   - Or remove reference if file no longer exists
3. Commit fixes: `fix: update stale path references`

---

## Automation (Future)

TODO: Create `audit-broken-refs.py` that:
- Parses markdown links `[text](path)`
- Parses code imports
- Validates paths exist
- Auto-fixes known patterns (--fix flag)
- Generates report of unfixable refs

---

## Post-Audit Checklist

- [ ] No references to `backend/` (should be `src/`)
- [ ] No references to `extension/` singular (should be `extensions/`)
- [ ] No references to `test/` singular (should be `tests/`)
- [ ] No references to `docs/reports/{number}/` (should be `docs/reports/done/1{number}-`)
- [ ] All markdown links resolve to existing files
- [ ] All documented paths in CLAUDE.md are valid
