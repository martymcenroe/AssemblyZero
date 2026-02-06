# Terminology Audit

## Purpose

Detect stale or inconsistent terminology after renaming. Catches:
- Old terms that should have been replaced
- Inconsistent naming across docs and code
- Glossary entries that are outdated

## Trigger

- After any major renaming (feature, component, concept)
- After architectural changes
- Weekly as part of maintenance

## Procedure

### Step 1: Identify Current Terminology

```bash
# Check glossary for canonical terms
cat docs/glossary.md

# List key terms from architecture doc
grep -E "^##|^\*\*" docs/0001-architecture.md
```

### Step 2: Search for Stale Terms

Known rename patterns to check:

| Old Term | New Term | Date Changed |
|----------|----------|--------------|
| Example Old | Example New | 2026-01-01 |

```bash
# Search for old terms
grep -ri "old_term" docs/ src/ tests/ --include="*.md" --include="*.py"

# Count occurrences
grep -ri "old_term" . --include="*.md" --include="*.py" | wc -l
```

### Step 3: Check for Inconsistency

```bash
# Find all variations of a term
grep -ri "term\|Term\|TERM" docs/ | head -20

# Check if naming is consistent
grep -c "camelCase" src/*.py
grep -c "snake_case" src/*.py
```

### Step 4: Update Stale References

For each stale term found:

```bash
# Bulk replace (dry run first)
grep -rl "old_term" docs/ | xargs -I{} echo "Would update: {}"

# Apply replacement
# Use sed or editor
```

### Step 5: Update Glossary

If terminology has changed:
1. Add new term to glossary
2. Mark old term as "See: {new term}" if still referenced
3. Update navigation/index docs

## Common Stale Terms

Check for these common patterns:

| Pattern | Why It's Stale |
|---------|----------------|
| TODO | Should be linked to issue |
| FIXME | Should be linked to issue |
| Old framework names | Architecture changed |
| Old service names | Renamed services |

## Output Format

```markdown
## Terminology Audit - {DATE}

### Summary
- Terms checked: {N}
- Stale occurrences found: {N}
- Files affected: {N}

### Stale Terms Found
| Term | Occurrences | Files |
|------|-------------|-------|
| old_term | 15 | 8 |

### Actions Taken
- Replaced "old_term" with "new_term" in {N} files
- Updated glossary with {N} new entries

### Remaining Issues
| Term | Location | Notes |
|------|----------|-------|
| legacy_term | README.md | Needs context review |
```

---

*Template from: AssemblyZero/.claude/templates/docs/terminology-audit.md*
