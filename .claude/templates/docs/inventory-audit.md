# File Inventory Drift Audit

## Purpose

Detect discrepancies between file inventory and the actual filesystem. Catches:
- Files that exist but aren't in inventory
- Inventory entries for deleted files
- Incorrect status or metadata

## Trigger

- Weekly (part of full cleanup)
- After any file creation, deletion, or move
- After major refactoring

## Procedure

### Step 1: Find Files Not in Inventory

```bash
# Python files
find src tests tools -name "*.py" -type f 2>/dev/null | while read f; do
  grep -q "$(basename $f)" docs/file-inventory.md || echo "NOT IN INVENTORY: $f"
done

# Shell scripts
find . -maxdepth 1 -name "*.sh" -type f 2>/dev/null | while read f; do
  grep -q "$(basename $f)" docs/file-inventory.md || echo "NOT IN INVENTORY: $f"
done

# Docs
find docs -name "*.md" -type f 2>/dev/null | while read f; do
  grep -q "$(basename $f)" docs/file-inventory.md || echo "NOT IN INVENTORY: $f"
done
```

### Step 2: Find Inventory Entries for Deleted Files

```bash
# Extract file paths from inventory and check existence
grep -oP '\| `[^`]+`' docs/file-inventory.md |
  sed 's/| `//;s/`//' |
  while read f; do
    [ ! -e "$f" ] && echo "DELETED: $f (still in inventory)"
  done
```

### Step 3: Check for Moved Files

Common moves to check:
- Root → src/ (main files)
- docs/ → docs/legacy/ (deprecated docs)
- tools/ restructuring

### Step 4: Verify Status Accuracy

For files marked **Stable**:
- Should have tests
- Should have documentation
- Should not have TODO/FIXME comments

For files marked **In-Progress**:
- Should have linked issue
- Should be actively worked on

### Step 5: Auto-Fix

When drift is detected:

1. **Missing files**: Add to inventory with:
   - Status: Stable (if tests exist) or Beta (otherwise)
   - Role: Inferred from location
   - Description: Inferred from filename

2. **Deleted files**: Remove entry from inventory

3. **Path changes**: Update paths

## Quick Commands

```bash
# Count files by location
echo "=== File counts ==="
echo "src/: $(find src -name '*.py' 2>/dev/null | wc -l)"
echo "tests/: $(find tests -name '*.py' 2>/dev/null | wc -l)"
echo "tools/: $(find tools -name '*.py' 2>/dev/null | wc -l)"
echo "docs/: $(find docs -name '*.md' 2>/dev/null | wc -l)"
```

## Output Format

```markdown
## File Inventory Audit - {DATE}

### Summary
- Files checked: {N}
- Not in inventory: {N}
- Deleted but listed: {N}
- Wrong path: {N}

### Additions Needed
| File | Suggested Status | Description |
|------|------------------|-------------|
| `tools/new_script.py` | Beta | New utility |

### Removals Needed
| Entry | Reason |
|-------|--------|
| `tests/test_old.py` | Deleted |

### Path Corrections
| Old Path | New Path |
|----------|----------|
| `main.py` | `src/main.py` |
```

---

*Template from: AssemblyZero/.claude/templates/docs/inventory-audit.md*
