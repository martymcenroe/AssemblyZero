# Issue #83: Structured Issue File Naming Scheme for Multi-Repo Workflows

# Structured Issue File Naming Scheme for Multi-Repo Workflows

## User Story
As a developer managing dozens of issues across multiple repositories,
I want a structured, collision-free file naming scheme for audit files,
So that I can easily identify, track, and correlate files with their GitHub issues.

## Objective
Implement a new naming convention `{REPO}-{WORD}-{NUM}-{TYPE}.md` that provides unique, memorable identifiers for issue files across multi-repo workflows.

## UX Flow

### Scenario 1: Creating a New Issue (Happy Path)
1. User creates a brief file with issue content
2. System generates slug: extracts repo ID (sanitized to alphanumeric), hashes brief content to select word, assigns next sequential number
3. System creates audit directory: `docs/audit/active/AgentOS-quasar-0042/`
4. System saves files with consistent naming: `AgentOS-quasar-0042-brief.md`, `AgentOS-quasar-0042-draft.md`
5. Result: All files for this issue share the same memorable identifier

### Scenario 2: Word Collision Detection
1. User creates a brief that hashes to word "zenith"
2. System detects "zenith" already exists in `active/` or `done/`
3. System selects next word in deterministic sequence from hash
4. Result: Unique word assigned without collision

### Scenario 3: Filing Issue to GitHub
1. User runs file_issue node on completed draft
2. System creates GitHub issue, receives issue number (e.g., #142)
3. System updates internal tracking but keeps directory name unchanged
4. Result: Files remain at `AgentOS-quasar-0042/` with GitHub issue #142 linked in metadata

### Scenario 4: Multi-Repo Workflow
1. User works on issues across AgentOS, Unleash, and DispatchRepo
2. Each issue has repo prefix: `AgentOS-quasar-0042`, `Unleash-praxis-0015`, `Dispatc-nebula-0003`
3. Result: Clear visual separation of which repo each issue belongs to

### Scenario 5: Malformed Directory/Repo Name (Edge Case)
1. User has a repo with special characters or path traversal attempt in name (e.g., `../evil-repo` or `my repo!@#`)
2. System sanitizes repo ID to alphanumeric characters only using regex `[a-zA-Z0-9]+`
3. System truncates to first 7 characters, capitalizes first letter
4. Result: Safe, consistent repo ID generated (e.g., `Myrepo` or `Evilrep`)

### Scenario 6: Directory Rename (Edge Case)
1. User renames project directory from `AgentOS` to `AgentOS-v2`
2. System detects change: new files would get different Repo ID
3. System logs warning about identifier discontinuity
4. Result: User informed; can create `.audit-config` to lock Repo ID

## Requirements

### Slug Generation
1. Slug format: `{REPO}-{WORD}-{NUM}` (e.g., `AgentOS-quasar-0042`)
2. Repo ID: Max 7 characters, first letter capitalized, derived from sources in priority order
3. Word: 4-6 letter English word from curated vocabulary list
4. Number: 4-digit zero-padded sequential number (0001-9999), scoped per-repo

### Repo ID Resolution (Priority Order)
1. **Priority 1:** `.audit-config` file in repo root (if exists, use `repo_id` field)
2. **Priority 2:** Git remote URL (extract repo name from `git@github.com:owner/RepoName.git`)
3. **Priority 3:** Current directory name (fallback)

### Repo ID Sanitization (SECURITY REQUIREMENT)
1. **MUST** sanitize all Repo ID sources to alphanumeric characters only
2. Apply regex filter: `[a-zA-Z0-9]+` â€” strip all other characters
3. Truncate to first 7 alphanumeric characters
4. Capitalize first letter
5. Reject empty results with clear error message

### Word Selection
1. Deterministic: MD5 hash of brief content seeds word selection
2. Collision-free: Check against all words in `active/` and `done/` directories
3. Fallback: On collision, try next word in deterministic sequence from hash (index + 1, + 2, etc.)
4. Curated list: 80+ interesting vocabulary-expanding words

### Number Assignment (Per-Repo Scope)
1. Sequential counter scoped to each Repo ID
2. Parse only files matching current Repo ID prefix in `active/` and `done/`
3. Find `MAX(number)` for that Repo ID, assign `MAX + 1`
4. Format: 4 digits zero-padded (`0001`, `0042`)

### File Naming
1. Format: `{SLUG}-{TYPE}.md` (e.g., `AgentOS-quasar-0042-draft.md`)
2. Types: brief, draft, verdict, feedback, filed
3. Revisions: Append sequence number (draft2, verdict2)
4. Directory: Named with slug, contains all related files

### Backward Compatibility
1. Existing issues with `NNN-{type}.md` format continue to work
2. New issues use new format exclusively
3. No migration of existing issues required

## Technical Approach

- **`get_repo_short_id()`:** 
  1. Check for `.audit-config` file, read `repo_id` if present
  2. Else extract repo name from git remote URL
  3. Else use current directory name
  4. **Sanitize result:** Apply regex `re.sub(r'[^a-zA-Z0-9]', '', raw_id)` to remove all non-alphanumeric characters
  5. Truncate to first 7 characters
  6. Capitalize first letter
  7. Raise `ValueError` if result is empty after sanitization

- **`get_next_issue_number(repo_id, active_dir, done_dir)`:**
  1. Glob for `{repo_id}-*-????-*.md` pattern in both directories
  2. Extract 4-digit numbers from matching filenames
  3. Return `max(numbers) + 1` or `1` if none exist
  4. Zero-pad to 4 digits

- **`generate_issue_word(brief_content, existing_words)`:** MD5 hash brief, use as seed to select index from wordlist, check collisions, increment index on collision, return unique word

- **`generate_slug(brief_file, brief_content)`:** Combine sanitized repo ID, word, and next sequential number (per-repo scoped)

- **`save_audit_file(audit_dir, slug, file_type, content, sequence?)`:** Save file with new naming convention

- **IssueWorkflowState:** Add `issue_word` field to track word separately from slug

## Security Considerations
- **Input Sanitization (CRITICAL):** All Repo ID sources (git remote, directory name, config file) MUST be sanitized to alphanumeric characters only via regex `[a-zA-Z0-9]+` before use in file paths
- **Path Traversal Prevention:** Sanitization removes `../`, `./`, and all special characters that could enable directory traversal attacks
- **No external API calls:** Local wordlist only, no network dependency
- **No sensitive data in filenames:** Only contains repo identifier, vocabulary word, and sequence number

## Files to Create/Modify
- `src/skills/audit/utils.py` â€” Add `get_repo_short_id()` with sanitization, `get_next_issue_number()`, `generate_issue_word()`, update `generate_slug()`, update `save_audit_file()`
- `src/skills/audit/wordlist.py` â€” New file containing curated `ISSUE_WORDS` list (80+ words)
- `src/skills/audit/nodes/load_brief.py` â€” Use new slug generation
- `src/skills/audit/nodes/draft.py` â€” Use updated `save_audit_file()` signature
- `src/skills/audit/nodes/review.py` â€” Use updated `save_audit_file()` signature
- `src/skills/audit/nodes/human_edit_draft.py` â€” Use updated `save_audit_file()` signature
- `src/skills/audit/nodes/human_edit_verdict.py` â€” Use updated `save_audit_file()` signature
- `src/skills/audit/nodes/file_issue.py` â€” Update `done/` directory naming
- `src/skills/audit/state.py` â€” Add `issue_word` to `IssueWorkflowState`

## Dependencies
- None: self-contained feature

## Out of Scope (Future)
- Web dashboard for browsing issues by word/number
- Search by word: "What's the status of quasar?"
- Cross-repo issue linking
- Wordlist expansion via external API
- Migration of existing issues to new format
- Automatic directory rename detection/migration

## Acceptance Criteria
- [ ] `get_repo_short_id()` returns â‰¤7 char capitalized repo identifier
- [ ] `get_repo_short_id()` sanitizes input to alphanumeric only (regex `[a-zA-Z0-9]+`)
- [ ] `get_repo_short_id()` follows priority order: `.audit-config` â†’ git remote â†’ directory name
- [ ] `get_repo_short_id()` raises `ValueError` for empty result after sanitization
- [ ] `generate_issue_word()` produces deterministic word from brief hash
- [ ] Word selection detects and avoids collisions in `active/` and `done/`
- [ ] `get_next_issue_number()` scopes counter to current Repo ID only
- [ ] Slug format matches `{REPO}-{WORD}-{NUM}` pattern
- [ ] All new audit files use `{SLUG}-{TYPE}.md` naming
- [ ] Audit directories named with full slug
- [ ] Revision files append sequence number (draft2, verdict2)
- [ ] Existing old-format issues continue to work unchanged
- [ ] Wordlist contains 80+ curated vocabulary-expanding words
- [ ] `issue_word` tracked in workflow state

## Definition of Done

### Implementation
- [ ] Core slug generation implemented with all three components
- [ ] Repo ID sanitization with alphanumeric-only regex
- [ ] Per-repo number scoping implemented
- [ ] Wordlist module created with curated words
- [ ] All 5 node files updated to use new naming
- [ ] State schema updated with `issue_word` field
- [ ] Unit tests for slug generation and collision detection
- [ ] Unit tests for Repo ID sanitization (including malicious inputs)
- [ ] Integration tests for full workflow with new naming

### Tools
- [ ] Update any CLI tools that reference audit file paths

### Documentation
- [ ] Document naming scheme in audit skill README
- [ ] Document `.audit-config` file format and Repo ID override
- [ ] Add wordlist documentation with contribution guidelines
- [ ] Update file inventory with new wordlist.py

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created

### Verification
- [ ] All existing tests pass (backward compatibility)
- [ ] New naming scheme tests pass
- [ ] Sanitization tests pass with special characters and path traversal attempts
- [ ] Manual verification: create issue, verify naming throughout workflow

## Testing Notes

**Testing Repo ID sanitization (SECURITY):**
```python
# Path traversal attempt
assert get_repo_short_id("../../../etc") == "Etc"

# Special characters stripped
assert get_repo_short_id("my-repo!@#$%") == "Myrepo"

# Spaces and unicode stripped
assert get_repo_short_id("my repo æ—¥æœ¬èªž") == "Myrepo"

# Empty after sanitization raises error
with pytest.raises(ValueError):
    get_repo_short_id("!@#$%^&*()")
```

**Testing slug generation:**
```python
# Same brief content should produce same word
brief1 = "Test brief content"
word1 = generate_issue_word(brief1, set())
word2 = generate_issue_word(brief1, set())
assert word1 == word2

# Different content produces different word (usually)
brief2 = "Different brief content"
word3 = generate_issue_word(brief2, set())
# May or may not differ, but deterministic for same input
```

**Testing collision avoidance:**
```python
existing = {"quasar", "zenith", "nebula"}
# Should return word not in existing set
word = generate_issue_word(brief_content, existing)
assert word not in existing
```

**Testing per-repo number scoping:**
```python
# Given active/ contains: AgentOS-quasar-0042-draft.md, Unleash-praxis-0015-draft.md
# Next number for AgentOS should be 0043
assert get_next_issue_number("AgentOS", active_dir, done_dir) == 43
# Next number for Unleash should be 0016
assert get_next_issue_number("Unleash", active_dir, done_dir) == 16
# Next number for new repo should be 0001
assert get_next_issue_number("NewRepo", active_dir, done_dir) == 1
```

**Testing repo ID extraction:**
```bash
# In a git repo with remote git@github.com:owner/AgentOS.git
# get_repo_short_id() should return "AgentOS"

# In a repo with long name "MyVeryLongRepoName"
# Should return "MyVeryL" (first 7 alphanumeric chars)

# With .audit-config containing repo_id: "Custom"
# Should return "Custom" (priority 1)
```

---

**Labels:** `enhancement`, `dx`

**Effort Estimate:** Medium (3-5 points)