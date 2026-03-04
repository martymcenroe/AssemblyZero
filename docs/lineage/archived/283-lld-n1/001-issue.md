---
repo: ThriveTech-AI/Hermes
issue: 283
url: https://github.com/ThriveTech-AI/Hermes/issues/283
fetched: 2026-03-04T01:07:14.969942Z
---

# Issue #283: refactor: extract ConversationDetail.tsx into focused components

## Problem

`ConversationDetail.tsx` is a 1132-line god component with:
- 13 `useMutation` hooks
- 6 inline sub-components (`Field`, `MilestonePanel`, `ProcessingBanner`, `AuditResultPanel`, `AuditHistoryPanel`, `MessageBubble`)
- Inconsistent mutation patterns (some close drawer on success, some don't)
- Mixed concerns (action bar, metadata fields, compose panel, audit panel, message history, rating)

## Proposed Extraction

### Phase 1 — File extraction

| New File | Elements Extracted | Lines (est.) |
|----------|-------------------|------------|
| `ConversationActionBar.tsx` | CD-02..CD-06 (Poke, Audit, Snooze, Interview, Delete) | ~80 |
| `ConversationFields.tsx` | CD-07..CD-11 (Clear username, Labels, Takeover, Star input, Verify) | ~120 |
| `ComposePanel.tsx` | CD-12..CD-16 (Subject, Body, Attach, File input, Send) | ~100 |
| `AuditResultPanel.tsx` | CD-17..CD-21 (Approve+Send, Load Draft, Approve, Mark State, Reject) | ~80 |
| `AuditHistoryPanel.tsx` | CD-25 (Details/Collapse per entry) | ~60 |
| `MessageBubble.tsx` | CD-23..CD-24 (Rating emojis, Rating note) + message rendering | ~150 |

### Phase 2 — Shared hooks

| Hook | Purpose |
|------|---------|
| `useConversationMutations(convId, onClose)` | All 13 mutations with centralized query invalidation |
| `useDrawerAction(mutation, onClose)` | Wraps mutation with onSuccess close pattern |

### Phase 3 — Admin pattern unification

| Hook | Purpose |
|------|---------|
| `useAdminAction(mutationFn)` | Shared approve/reject/snooze across AttentionQueue, AuditQueue, ConversationDetail |

## Why This Matters

- **Testability**: Each extracted component can have focused unit tests
- **Readability**: 1132 lines → ~200 lines for the orchestrator + 6 focused files
- **Consistency**: useDrawerAction ensures all mutations that should close the drawer DO close the drawer
- **Reusability**: useAdminAction eliminates duplicate approve/reject logic in 3 components

## Reference

docs/standards/00004-dashboard-button-spec.md Appendix A