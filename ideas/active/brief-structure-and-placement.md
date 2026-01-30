# Idea: Brief Structure and Placement Standard

**Status:** Active
**Effort:** Low (1 hour)
**Value:** High - consistency across all projects

---

## Problem

There is no standard for how briefs (ideas, proposals, technical debt notes) should be structured and where they should be placed in a project. This leads to:
- Briefs ending up in random locations (docs/, root, notes/)
- Inconsistent naming (numbered vs unnumbered)
- No clear lifecycle (when does a brief become an issue?)

---

## Proposal

### Location

Briefs live in `ideas/` at the **project root** (not in `docs/`):

```
project/
├── ideas/
│   ├── active/         # Briefs that need work
│   └── backlog/        # Future/speculative ideas
├── docs/               # Formal documentation only
├── src/
└── ...
```

**Rationale:**
- Ideas are working documents, not formal documentation
- They precede issues and may never become formal docs
- Keeps `docs/` clean for finalized documentation
- Clear separation: `ideas/` = "what we might do", `docs/` = "what we did/decided"

### Naming

Briefs are **unnumbered** with kebab-case names:

```
ideas/active/header-normalization.md       ✓ correct
ideas/active/004-header-normalization.md   ✗ wrong
```

**Rationale:**
- Numbers imply priority or sequence that doesn't exist
- Briefs get numbered only when promoted to GitHub issues
- Avoids renumbering hassle when briefs move to issues
- Prevents confusion between brief numbers and issue numbers

### File Structure

Each brief follows this template:

```markdown
# Idea: [Title]

**Status:** [Draft | Active | Blocked | Done | Rejected]
**Effort:** [Low | Medium | High] ([time estimate])
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

[Technical details, code samples, diagrams]

---

## Next Steps

1. [ ] Step 1
2. [ ] Step 2
```

### Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Draft     │────▶│   Active    │────▶│    Done     │
│  (backlog/) │     │  (active/)  │     │  (delete or │
└─────────────┘     └─────────────┘     │   archive)  │
                           │            └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ GitHub Issue│
                    │ (gets 1xxxx │
                    │  number)    │
                    └─────────────┘
```

1. **Draft** - Idea captured, needs refinement (lives in `backlog/`)
2. **Active** - Ready for work, may or may not become an issue (lives in `active/`)
3. **Promoted** - Becomes a GitHub issue with 1xxxx number, brief can be deleted
4. **Done** - Implemented without becoming an issue, delete or archive
5. **Rejected** - Not pursuing, delete or move to backlog with note

### What Goes Where

| Content | Location | Example |
|---------|----------|---------|
| Quick idea, may never happen | `ideas/backlog/` | `ideas/backlog/dark-mode.md` |
| Actionable work item | `ideas/active/` | `ideas/active/fix-login-bug.md` |
| Approved design with issue | `docs/lld/active/` | `docs/lld/active/10045-lld.md` |
| Completed work | `docs/reports/` | `docs/reports/done/10045-impl.md` |

---

## Files to Update

| File | Change |
|------|--------|
| `docs/standards/0009-canonical-project-structure.md` | Add `ideas/` to root structure |
| `tools/new-repo-setup.py` | Add `ideas/active` and `ideas/backlog` to OTHER_STRUCTURE |
| `docs/templates/0110-brief-template.md` | Create template |

---

## Next Steps

1. [ ] Update 0009 canonical structure standard
2. [ ] Update new-repo-setup.py
3. [ ] Create brief template
4. [ ] Update file inventory template
