# 00012 - Add Ideas Directory to Canonical Project Structure

**Status:** Draft
**Created:** 2026-01-29
**Type:** Enhancement

---

## Problem

The canonical project structure (0009) does not include an `ideas/` directory for briefs and proposals. During development of the RCA-PDF-extraction-pipeline project, we created:

```
ideas/
├── active/     # Actionable briefs
└── backlog/    # Future/speculative ideas
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

Add to **root level** structure (NOT in docs/):

```
project/
├── ideas/                      # Briefs, proposals, technical debt
│   ├── active/                 # Actionable items
│   │   └── (brief-name.md files)
│   └── backlog/                # Future/speculative items
│       └── (brief-name.md files)
```

**Why root level, not docs/?**
- Ideas are working documents, not formal documentation
- They precede issues and may never become formal docs
- Keeps docs/ cleaner for finalized documentation

### 2. No Numbering for Briefs

Briefs are **unnumbered**. They get numbered only after an issue is filed:
- `ideas/active/header-normalization.md` (brief)
- `docs/lld/active/10045-lld.md` (after issue #45 filed)

This prevents:
- Premature numbering that creates false sense of priority
- Renumbering hassle when briefs are promoted to issues
- Confusion between brief numbers and issue numbers

### 3. Update new-repo-setup.py

Add to `OTHER_STRUCTURE` in `tools/new-repo-setup.py`:

```python
OTHER_STRUCTURE = [
    # ... existing ...
    "ideas/active",
    "ideas/backlog",
]
```

---

## Brief Template

Create `docs/templates/0110-brief-template.md`:

```markdown
# Idea: [Title]

**Status:** [Draft | Active | Blocked | Done | Rejected]
**Effort:** [Low | Medium | High] ([estimate])
**Value:** [Low | Medium | High | Critical]
**Blocked by:** [brief name if applicable]

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
1. Create `ideas/active/` and `ideas/backlog/` at project root
2. Move any informal briefs or TODO docs into appropriate subdirectory
3. Strip any numbers from filenames

---

## Files to Update

| File | Change |
|------|--------|
| `docs/standards/0009-canonical-project-structure.md` | Add ideas/ to root structure |
| `tools/new-repo-setup.py` | Add ideas/active and ideas/backlog to OTHER_STRUCTURE |
| `docs/templates/` | Add brief template |
| `docs/0003-file-inventory.md` | Add ideas directory |

---

## Acceptance Criteria

- [ ] 0009 standard updated with ideas directory at root
- [ ] new-repo-setup.py creates ideas/active and ideas/backlog
- [ ] Brief template created (unnumbered)
- [ ] File inventory updated
- [ ] Test by creating new project and verifying structure
