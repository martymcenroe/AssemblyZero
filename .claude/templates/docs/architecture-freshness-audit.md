# Architecture Freshness Audit

## Purpose

Verify that architecture documentation is up-to-date with current implementation. Catches:
- Outdated diagrams
- Stale component descriptions
- Missing new components
- Deprecated components still documented

## Trigger

- Monthly (strategic review)
- After major architectural changes
- Before onboarding new team members

## Procedure

### Step 1: Inventory Current Components

```bash
# List actual components from source
ls -la src/
ls -la tools/
ls -la tests/

# Count files by type
find src -name "*.py" | wc -l
find src -name "*.js" | wc -l
```

### Step 2: Compare with Architecture Doc

Read architecture docs and check each documented component:

| Documented Component | Exists? | Path | Notes |
|---------------------|---------|------|-------|
| Component A | ✅ | src/component_a.py | Current |
| Component B | ❌ | - | Removed in v2 |
| Component C | ⚠️ | src/new_name.py | Renamed |

### Step 3: Check Diagram Accuracy

For each Mermaid diagram in architecture docs:
1. Extract node/edge definitions
2. Verify each node exists in codebase
3. Verify relationships are accurate

```bash
# Extract diagram definitions
grep -A 50 "```mermaid" docs/0001-architecture.md

# Check if referenced components exist
```

### Step 4: Check for Undocumented Components

```bash
# Find source files
find src -name "*.py" -type f

# Compare with documented components in architecture
grep -E "^\| " docs/0001-architecture.md
```

### Step 5: Update Stale Documentation

| Finding | Action |
|---------|--------|
| Component removed | Remove from architecture docs |
| Component renamed | Update references |
| Component added | Add to architecture docs |
| Diagram outdated | Regenerate diagram |
| Relationships changed | Update diagram edges |

## Checklist

- [ ] All documented components exist
- [ ] No undocumented components in src/
- [ ] Diagrams reflect current structure
- [ ] Deployment view matches infrastructure
- [ ] Quality attributes have current evidence
- [ ] External system integrations are current

## Output Format

```markdown
## Architecture Freshness Audit - {DATE}

### Summary
- Components documented: {N}
- Components verified: {N}
- Stale entries: {N}
- Missing entries: {N}

### Component Status
| Component | Doc Status | Code Status | Action |
|-----------|------------|-------------|--------|
| API Service | ✅ Current | ✅ Exists | None |
| Legacy Module | ⚠️ Documented | ❌ Removed | Remove from docs |
| New Feature | ❌ Missing | ✅ Exists | Add to docs |

### Diagram Status
| Diagram | Location | Status |
|---------|----------|--------|
| Context View | 0001a | ✅ Current |
| Container View | 0001b | ⚠️ Missing node |

### Actions Taken
- Removed {N} stale component entries
- Added {N} new component entries
- Updated {N} diagrams

### Recommended Next Steps
1. Review new components for architecture alignment
2. Update deployment view for infrastructure changes
```

---

*Template from: AssemblyZero/.claude/templates/docs/architecture-freshness-audit.md*
