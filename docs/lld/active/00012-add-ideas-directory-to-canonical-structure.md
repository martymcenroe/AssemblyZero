# 00012 - Add Ideas Directory to Canonical Project Structure

**Status:** Draft
**Created:** 2026-01-29
**Type:** Enhancement

---

## Problem

The canonical project structure (0009) does not include a `docs/ideas/` directory for briefs and proposals. During development of the RCA-PDF-extraction-pipeline project, we created:

```
docs/ideas/
├── active/     # Actionable briefs (004-011)
└── backlog/    # Future/speculative ideas (001-003)
```

This pattern proved useful for:
- Capturing requirements gaps before they're forgotten
- Tracking enhancement proposals
- Separating "must do" from "nice to have"
- Documenting technical debt

Currently, the canonical structure only has `docs/lld/` which is tied to GitHub issues. Briefs/ideas exist before issues are created and may never become formal issues.

---

## Proposal

### 1. Update Canonical Structure (0009)

Add to `docs/` structure:

```
docs/
├── ideas/                      # Briefs, proposals, technical debt
│   ├── active/                 # Actionable items
│   │   └── (Nxxx-brief-name.md files)
│   └── backlog/                # Future/speculative items
│       └── (Nxxx-brief-name.md files)
```

### 2. Define Numbering Scheme

Add to the 5-digit numbering scheme:

| Range | Category | Location |
|-------|----------|----------|
| `5xxxx` | Ideas, briefs, proposals | `docs/ideas/` |

Or alternatively, use project-specific numbering (ideas don't need cross-project uniqueness):
- Sequential 3-digit: `001-brief-name.md`, `002-brief-name.md`

### 3. Update new-repo-setup.py

Add to `DOCS_STRUCTURE` in `tools/new-repo-setup.py`:

```python
DOCS_STRUCTURE = [
    # ... existing ...
    "docs/ideas/active",
    "docs/ideas/backlog",
]
```

### 4. Update agentos-generate.py

If this script creates file inventory or structure docs, update to include ideas directory.

---

## Brief Template

Create `docs/templates/0110-brief-template.md`:

```markdown
# Idea: [Title]

**Status:** [Draft | Active | Blocked | Done | Rejected]
**Effort:** [Low | Medium | High] ([estimate])
**Value:** [Low | Medium | High | Critical]
**Blocked by:** [brief number if applicable]

---

## Problem

[What issue does this address?]

---

## Proposal

[What is the solution?]

---

## Implementation

[Technical details]

---

## Next Steps

1. [ ] Step 1
2. [ ] Step 2
```

---

## Migration

For existing projects:
1. Create `docs/ideas/active/` and `docs/ideas/backlog/`
2. Move any informal briefs or TODO docs into appropriate subdirectory
3. Renumber if needed

---

## Files to Update

| File | Change |
|------|--------|
| `docs/standards/0009-canonical-project-structure.md` | Add ideas/ to structure |
| `tools/new-repo-setup.py` | Add ideas/active and ideas/backlog to DOCS_STRUCTURE |
| `tools/agentos-generate.py` | Update if it creates structure |
| `docs/templates/` | Add brief template |
| `docs/0003-file-inventory.md` | Add ideas directory |

---

## Acceptance Criteria

- [ ] 0009 standard updated with ideas directory
- [ ] new-repo-setup.py creates ideas/active and ideas/backlog
- [ ] Brief template created
- [ ] File inventory updated
- [ ] Test by creating new project and verifying structure
