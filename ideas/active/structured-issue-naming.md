# Structured Issue File Naming Scheme

**Date:** 2026-01-27
**Context:** Working on dozens of issues in parallel requires better file organization and unique identifiers.

## Problem

Current naming: `docs/audit/active/{brief-filename}/NNN-{type}.md`
- Brief filename collisions possible
- No repo identifier for multi-repo workflows
- Numbers don't correlate to issue numbers until filed
- Hard to track which files belong to which issue

## Proposed Solution

**New format:** `{REPO}-{WORD}-{NUM}-{TYPE}.md`

**Components:**
- **REPO**: 7-char repo identifier (e.g., "AgentOS")
- **WORD**: Unique 4-6 letter English word (vocabulary-expanding, deterministic from brief hash)
- **NUM**: 4-digit zero-padded number (GitHub issue number once filed, or sequential before)
- **TYPE**: File type (brief, draft, verdict, feedback, filed)

**Examples:**
```
AgentOS-quasar-0042-draft.md
AgentOS-quasar-0042-verdict.md
MyRepo-zenith-0001-brief.md
```

**Directory structure:**
```
docs/audit/active/AgentOS-quasar-0042/
  AgentOS-quasar-0042-brief.md
  AgentOS-quasar-0042-draft.md
  AgentOS-quasar-0042-verdict.md
  AgentOS-quasar-0042-draft2.md  (if revised)
  AgentOS-quasar-0042-verdict2.md
```

## Implementation Details

### Word Generation

**Algorithm:**
1. MD5 hash of brief content → deterministic seed
2. Use seed to select from curated wordlist (interesting vocabulary)
3. Check for collisions in active/ and done/
4. If collision, try next word in deterministic sequence

**Wordlist** (partial):
```python
ISSUE_WORDS = [
    "quasar", "zephyr", "nebula", "praxis", "axiom", "lucent",
    "vesper", "cipher", "zenith", "lotus", "apex", "ember",
    "fjord", "glyph", "haven", "jade", "jocote", "karma",
    # ... 80+ words total
]
```

### Repo ID

**Sources** (in priority order):
1. Git remote URL: `git@github.com:owner/AgentOS.git` → `AgentOS`
2. Fallback: Current directory name → truncate to 7 chars

**Rules:**
- Max 7 characters
- Capitalize first letter
- If >7 chars: intelligently abbreviate or truncate

### Number Assignment

**Before filing:**
- Sequential counter: scan active/ and done/ for max number, +1
- Format: 4 digits zero-padded (`0001`, `0042`)

**After filing:**
- Replace with GitHub issue number
- Rename audit directory: `AgentOS-quasar-0042/` → keep same
- File naming remains consistent

### Migration Path

**Phase 1: Add new functions**
- `get_repo_short_id() -> str`
- `generate_issue_word(brief_content, existing_words) -> str`
- `generate_slug(brief_file, brief_content) -> str  # New signature`
- `save_audit_file(audit_dir, slug, file_type, content, sequence?) -> Path`

**Phase 2: Update all nodes**
- load_brief.py: Generate new-format slug
- draft.py: Use new save_audit_file signature
- review.py: Use new save_audit_file signature
- human_edit_draft.py: Use new save_audit_file signature
- human_edit_verdict.py: Use new save_audit_file signature
- file_issue.py: Update done/ directory naming

**Phase 3: Update state**
- Add `issue_word` to IssueWorkflowState
- Track separately from slug

## Benefits

1. **Multi-repo clarity**: Repo ID prefix makes it obvious which repo an issue belongs to
2. **Unique identification**: Word + number creates memorable, collision-free IDs
3. **Vocabulary expansion**: Curated wordlist teaches new words
4. **Deterministic**: Same brief content → same word (reproducible)
5. **GitHub correlation**: Number becomes issue number once filed
6. **Grep-friendly**: Easy to find all files for an issue

## Open Questions

1. **Should wordlist be:**
   - Local curated list (fast, no network) ← Recommended
   - API-based (e.g., random-word-api.herokuapp.com)
   - Mix: local with API fallback

2. **Number format:**
   - Always 4 digits? Or allow 3 digits initially, expand to 4 for >999?
   - Recommended: Always 4 digits (0001-9999)

3. **Collision handling:**
   - Currently: Try next word in deterministic sequence
   - Alternative: Append random suffix (quasar2, quasar3)

4. **Backward compatibility:**
   - Old issues keep NNN-{type}.md format?
   - Or migrate all existing issues?
   - Recommended: Keep old format, new issues use new format

## Acceptance Criteria

- [ ] Slug generation produces {REPO}-{WORD}-{NUM} format
- [ ] Word selection is deterministic from brief hash
- [ ] No word collisions across active/ and done/
- [ ] All audit files use new naming scheme
- [ ] Audit directory named with slug
- [ ] Integration tests pass
- [ ] Existing issues still work (backward compat)

## Out of Scope (Future)

- Web dashboard for browsing issues by word/number
- Search by word: "What's the status of quasar?"
- Cross-repo issue linking
- Wordlist expansion API

---

**Note:** Partially implemented in audit.py (`get_repo_short_id`, `generate_issue_word`, new `generate_slug`), but node updates deferred to avoid breaking existing workflows. Complete migration requires updating all save_audit_file calls across 5 node files.
