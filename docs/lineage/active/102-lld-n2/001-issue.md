---
repo: martymcenroe/AgentOS
issue: 102
url: https://github.com/martymcenroe/AgentOS/issues/102
fetched: 2026-02-04T07:55:12.631617Z
---

# Issue #102: TDD Test Initialization Gate

# TDD Test Initialization Gate

## User Story
As a developer practicing Test-Driven Development,
I want the system to enforce writing failing tests before implementation,
So that I follow the red-green-refactor cycle and build reliable, well-tested code.

## Objective
Enforce TDD discipline by gating implementation work behind verified failing tests, ensuring the red-green-refactor cycle is followed for every feature.

## UX Flow

### Scenario 1: Happy Path - TDD Workflow
1. Developer creates a new feature branch
2. Developer writes test file with tests that define expected behavior
3. System runs **only the specific test file** (not full suite) and verifies tests fail (red phase) with exit code 1
4. System records red phase completion in commit message footer, unlocks implementation
5. Developer writes implementation code
6. System runs tests and verifies they pass (green phase)
7. Developer refactors with confidence
8. PR is created with full TDD audit trail

### Scenario 2: Missing Tests - Implementation Blocked
1. Developer attempts to create PR without test file
2. System detects no corresponding test file exists
3. System blocks PR creation with clear error message
4. Developer is directed to write tests first

### Scenario 3: Tests Don't Fail Initially (Invalid Red Phase)
1. Developer writes tests that already pass, are skipped, or not found
2. System runs **only the specific test file** and detects exit code is not `1` (test failure)
3. System distinguishes between:
   - Exit code `0`: Tests passed (invalid - must fail first)
   - Exit code `2`: Test collection error/interrupted (invalid - not meaningful failure)
   - Exit code `5`: No tests collected (invalid - tests not found; suggests checking file naming like `test_*.py`)
   - Exit code `1`: Tests failed (valid red phase)
4. System blocks implementation phase with specific warning based on exit code
5. Developer must write meaningful failing tests that return exit code `1`

### Scenario 4: Hotfix Override
1. Developer needs emergency hotfix
2. Developer uses explicit override flag: `--skip-tdd-gate --reason "P0 production outage"`
3. System logs override locally to pending debt file (`~/.tdd-pending-issues.json`)
4. Commit proceeds immediately (non-blocking for emergency)
5. PR is flagged for follow-up test coverage
6. CI or post-commit hook asynchronously creates technical debt issue via `gh issue create` when connectivity allows

### Scenario 5: Hotfix Override - Offline/API Unavailable
1. Developer needs emergency hotfix while offline or GitHub API is down
2. Developer uses explicit override flag: `--skip-tdd-gate --reason "P0 production outage"`
3. System logs override locally to pending debt file (`~/.tdd-pending-issues.json`)
4. Commit proceeds immediately (issue creation does not block)
5. On next successful `gh` command or CI run, pending issues are created and cleared from local queue

### Scenario 6: Squash/Rebase Workflow
1. Developer completes TDD cycle with red phase proof in commit footer
2. Developer opens PR and team uses "Squash and Merge"
3. CI extracts `TDD-Red-Phase` footer from **any commit in PR branch** before squash
4. CI also accepts PR if coverage requirements are met and red phase proof existed at any point in branch history
5. After squash, audit trail in `docs/reports/{IssueID}/tdd-audit.md` preserves the full TDD history

## Requirements

### Test Existence Gate
1. Test file must exist before implementation PR is allowed
2. Test file naming convention enforced (e.g., `test_*.py`, `*.test.js`)
3. Tests must reference the feature/issue being implemented
4. Minimum test count threshold (configurable, default: 1)

### Red Phase Verification
1. All new tests must fail on first run with exit code `1`
2. **Scoped Execution:** Hook runs **only the specific test file** being committed, not the full suite
3. Test file path is passed explicitly to runner (e.g., `pytest tests/test_new_feature.py`)
4. Exit code validation:
   - `pytest`: Exit code `1` = tests failed (valid), `0` = passed (invalid), `2` = interrupted/error (invalid), `5` = no tests (invalid)
   - `jest`: Exit code `1` = tests failed (valid), `0` = passed (invalid)
5. System captures test failure output as baseline
6. Red phase proof stored in commit message footer: `TDD-Red-Phase: <sha>:<timestamp>`

### Green Phase Tracking
1. Tests must pass after implementation (exit code `0`)
2. System compares red → green transition
3. No test deletions allowed between phases (without justification)
4. Coverage delta reported (new code must be covered)

### State Management & CI Synchronization
1. Red phase proof travels via commit message footers (e.g., `TDD-Red-Phase: <commit-sha>:<timestamp>`)
2. CI extracts and validates footers from **all commits in the PR branch** (handles squash/rebase)
3. For squashed PRs: CI accepts if footer existed in branch history OR coverage requirements met
4. No `.tdd-state.json` committed to avoid merge conflicts
5. Local `.tdd-state.json` is git-ignored for developer convenience only
6. Audit log at `docs/reports/{IssueID}/tdd-audit.md` is strictly additive (append-only)

### File Scope Exclusions
1. Documentation files (`*.md`, `*.rst`, `*.txt`) are **excluded** from TDD gate
2. Configuration files (`*.json`, `*.yaml`, `*.yml`, `*.toml`, `*.ini`) are **excluded** from TDD gate
3. Only source code files (`.py`, `.js`, `.ts`, etc.) trigger the test existence check
4. Exclusions are configurable in `.tdd-config.json`

### Audit Trail
1. Record red phase: timestamp, test names, failure messages, exit code
2. Record green phase: timestamp, test names, pass confirmation, exit code
3. Record refactor phase: any test modifications post-green
4. Generate TDD compliance report per PR

### Framework Support
1. Python: pytest with **file-scoped** discovery (specific file path passed)
2. JavaScript: Jest with **file-scoped** discovery (specific file path passed)
3. Configurable test commands per project
4. Extensible for additional frameworks

## Technical Approach
- **Pre-commit Hook:** Verify test file exists for changed implementation files (excludes docs/config)
- **Prepare-commit-msg Hook:** Append `TDD-Red-Phase` footer to commit messages after red phase verification
  - Hook runs **before** editor opens and **before** GPG signing
  - Footer injection happens during message preparation, not post-signing
- **CI Gate:** Extract `TDD-Red-Phase` footer from **all commits in PR branch**; supports squash workflows
- **State Tracking:** Local `.tdd-state.json` (git-ignored) for developer UX; commit footers for CI verification
- **Audit Logger:** Append to `docs/reports/{IssueID}/tdd-audit.md` (strictly additive)
- **Override System:** Explicit flag with required justification logged; issue creation is async/non-blocking
- **Pending Issue Queue:** Local file (`~/.tdd-pending-issues.json`) stores failed issue creations for retry
- **Test Scoping:** Hooks pass specific file paths to test runners to prevent full suite execution

## Security Considerations
- **Issue Auto-Creation Authentication:** Uses GitHub CLI (`gh`) which reads `GITHUB_TOKEN` from environment or uses existing `gh auth` session
- **Required Token Scope:** `repo` scope for issue creation in private repos, `public_repo` for public repos
- **CI Environment:** `GITHUB_TOKEN` is automatically provided by GitHub Actions with appropriate permissions
- **Local Environment:** Developers must have `gh auth login` completed or `GITHUB_TOKEN` exported
- **Input Sanitization:** The `--reason` argument is passed to `gh` CLI using safe subprocess calls (arguments as list, never `shell=True`) to prevent command injection
- Override flag usage is logged and visible in PR
- No secrets or sensitive data in test failure output logging
- Local state files (`.tdd-state.json`, `~/.tdd-pending-issues.json`) excluded from git and sensitive data scans
- Audit trail is append-only (no retroactive modifications)

## Files to Create/Modify
- `hooks/pre-commit-tdd-gate.sh` — Pre-commit hook for test existence check (excludes docs/config files)
- `hooks/prepare-commit-msg-tdd.sh` — Prepare-commit-msg hook to append TDD footer to commit messages (runs before signing)
- `tools/tdd-gate.py` — Main TDD enforcement CLI tool (uses subprocess list args, not shell=True; passes specific file paths)
- `tools/tdd-audit.py` — Audit trail generation and reporting
- `tools/tdd-pending-issues.py` — Async pending issue creation processor with `--flush` command
- `.tdd-config.json` — Project-specific TDD configuration (including file exclusions)
- `.gitignore` — Add `.tdd-state.json` to ignored files
- `.husky/pre-commit` — Husky hook configuration (required)
- `.husky/prepare-commit-msg` — Husky hook configuration (required)
- `package.json` — Add `prepare` script for automatic husky installation on `npm install`
- `docs/standards/0065-tdd-enforcement.md` — Standard documenting TDD gate rules
- `CLAUDE.md` — Add TDD workflow section

## Dependencies
- Issue #62: Governance Workflow StateGraph (may integrate with state machine)
- GitHub CLI (`gh`) must be installed for issue auto-creation feature
- `husky` (required) — Ensures hooks are automatically installed for all developers via npm lifecycle

## Out of Scope (Future)
- IDE integration for real-time TDD feedback — separate tooling issue
- Automatic test generation suggestions — AI enhancement, not MVP
- Cross-repository test dependency tracking — complex, defer
- Test quality scoring beyond pass/fail — enhancement
- Cryptographic signing of red phase proof — current text footer is sufficient for governance level
- Time-based expiration of red phase proof — future enhancement to consider staleness

## Acceptance Criteria
- [ ] Pre-commit hook blocks commits without corresponding test files
- [ ] Pre-commit hook excludes documentation files (`*.md`) and config files (`*.json`, `*.yaml`)
- [ ] `tdd-gate --verify-red <test-file>` runs **only the specified test file**, not full suite
- [ ] `tdd-gate --verify-red` confirms tests fail with exit code `1` and records red phase
- [ ] `tdd-gate --verify-red` rejects exit codes `0`, `2`, `5` with specific error messages
- [ ] `tdd-gate --verify-green` confirms tests pass (exit code `0`) and records green phase
- [ ] Red phase proof is written to commit message footer via prepare-commit-msg hook: `TDD-Red-Phase: <sha>:<timestamp>`
- [ ] Prepare-commit-msg hook runs before GPG signing (does not invalidate signatures)
- [ ] CI gate extracts `TDD-Red-Phase` footer from **all commits in PR branch** (supports squash)
- [ ] CI accepts squashed PRs if red phase proof existed in branch history
- [ ] Implementation PR is blocked if `TDD-Red-Phase` footer not found in branch commits
- [ ] `--skip-tdd-gate --reason "<justification>"` override works with required justification
- [ ] Override logs debt locally and allows commit immediately (non-blocking)
- [ ] Async process creates follow-up issue via `gh issue create` when connectivity allows
- [ ] Pending issues are stored in `~/.tdd-pending-issues.json` and retried on next opportunity
- [ ] `tdd-pending-issues --flush` command manually triggers pending issue upload
- [ ] `--reason` argument is sanitized via subprocess list args (no shell injection)
- [ ] Audit trail appends to `docs/reports/{IssueID}/tdd-audit.md`
- [ ] Works with pytest: `test_*.py` pattern detection, exit code validation, file-scoped execution
- [ ] Works with Jest: `*.test.js` and `*.spec.js` pattern detection, exit code validation, file-scoped execution
- [ ] Exit code 5 error message suggests checking file naming conventions (e.g., "Did you name your file `test_*.py`?")
- [ ] Configuration via `.tdd-config.json` for custom patterns and exclusions
- [ ] `.tdd-state.json` is listed in `.gitignore`
- [ ] Husky is configured with `prepare` script for automatic hook installation

## Definition of Done

### Implementation
- [ ] Core TDD gate tool implemented
- [ ] Pre-commit hook implemented (with file exclusions)
- [ ] Prepare-commit-msg hook implemented for footer injection
- [ ] Async pending issue processor implemented with `--flush` command
- [ ] Husky configuration complete with automatic setup
- [ ] CI integration documented with commit footer extraction (supports squash)
- [ ] Unit tests written and passing (yes, TDD for the TDD tool)

### Tools
- [ ] `tools/tdd-gate.py` CLI documented with examples
- [ ] `tools/tdd-audit.py` reporting tool documented
- [ ] `tools/tdd-pending-issues.py` documented (including `--flush`)

### Documentation
- [ ] Standard 0065 created for TDD enforcement rules
- [ ] CLAUDE.md updated with TDD workflow section
- [ ] README updated with TDD gate setup instructions
- [ ] Add new files to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created

### Verification
- [ ] Run 0809 Security Audit - PASS
- [ ] Run 0817 Wiki Alignment Audit - PASS

## Testing Notes

### Force Red Phase Failure (Exit Code Validation)
```bash
# Test that passes immediately (exit code 0) - should be blocked
echo "def test_always_passes(): assert True" > test_feature.py
tdd-gate --verify-red test_feature.py  # Should fail: "Invalid red phase: tests passed (exit code 0)"

# Test with syntax error (exit code 2) - should be blocked
echo "def test_broken(: pass" > test_feature.py
tdd-gate --verify-red test_feature.py  # Should fail: "Invalid red phase: collection error (exit code 2)"

# Test file with no tests (exit code 5) - should be blocked
echo "# empty file" > test_feature.py
tdd-gate --verify-red test_feature.py  # Should fail: "Invalid red phase: no tests found (exit code 5). Did you name your file test_*.py?"

# Proper failing test (exit code 1) - should succeed
echo "def test_feature(): assert False, 'Not implemented'" > test_feature.py
tdd-gate --verify-red test_feature.py  # Should succeed: "Red phase verified"
```

### Verify File-Scoped Execution
```bash
# Ensure only the specified file is run, not full suite
time tdd-gate --verify-red tests/test_single_feature.py
# Should complete in seconds, not minutes
# Should NOT run tests from other files
```

### Force Override Path
```bash
# Test hotfix override flow
tdd-gate --skip-tdd-gate --reason "P0 production outage"
# Verify: override logged to ~/.tdd-pending-issues.json, commit allowed

# Verify gh CLI auth is working
gh auth status  # Must show authenticated

# Trigger pending issue creation
tdd-pending-issues --process  # Creates issues from queue

# Manual flush command
tdd-pending-issues --flush  # Force upload all pending issues
```

### Test Offline Override
```bash
# Simulate offline by blocking gh
tdd-gate --skip-tdd-gate --reason "P0 outage"
# Commit should succeed even if gh fails
# Check ~/.tdd-pending-issues.json contains pending entry
```

### Verify Commit Footer
```bash
# After red phase, check commit contains footer
git log -1 --format=%B | grep "TDD-Red-Phase:"
# Should output: TDD-Red-Phase: abc123:2024-01-15T10:30:00Z
```

### Verify CI Extraction (Including Squash Support)
```bash
# Simulate CI footer extraction from all branch commits
git log --format=%B origin/main..HEAD | grep "TDD-Red-Phase:" || echo "BLOCKED: No red phase proof"

# Verify squash scenario - footer should be found in any commit
git log --all --format=%B | grep "TDD-Red-Phase:"
```

### Verify Audit Trail
```bash
# After full TDD cycle, check audit file contains:
# - Red phase entry with failure output and exit code
# - Green phase entry with pass confirmation
# - Timestamps for both phases
cat docs/reports/ISSUE-XX/tdd-audit.md
```

### Verify Input Sanitization
```bash
# Attempt injection via reason (should be safely escaped)
tdd-gate --skip-tdd-gate --reason '"; rm -rf / #'
# Verify: No shell execution, reason stored literally
```

### Verify File Exclusions
```bash
# Docs should not trigger TDD gate
git add README.md
git commit -m "Update docs"  # Should succeed without test requirement

# Config should not trigger TDD gate
git add .tdd-config.json
git commit -m "Update config"  # Should succeed without test requirement
```

### Verify GPG Signing Compatibility
```bash
# With commit.gpgsign = true
git config commit.gpgsign true
echo "def test_new(): assert False" > test_gpg.py
tdd-gate --verify-red test_gpg.py
git add test_gpg.py
git commit -m "Test GPG signing"
# Verify: Commit is signed AND contains TDD-Red-Phase footer
git log --show-signature -1
```

### Verify Husky Auto-Installation
```bash
# Fresh clone should auto-install hooks
git clone <repo>
cd <repo>
npm install  # Should trigger husky prepare script
ls .husky/   # Should show pre-commit and prepare-commit-msg hooks
```

## Labels
`governance`, `developer-experience`, `tooling`

## Effort Estimate
**XL** — Cross-platform hooks, CLI tool, CI integration, and comprehensive documentation

## Open Questions for Orchestrator
1. Does the team use "Squash and Merge" for Pull Requests? (Current design supports it, but please confirm)
2. Does the team prefer strict blocking (CI failure) or soft blocking (warning/audit log) for the MVP?
3. Should the "Hotfix Override" require manager approval (via CODEOWNERS), or is developer self-attestation sufficient?

## Original Brief
# TDD Test Initialization

## Problem

Developers often skip writing tests first, violating Test-Driven Development (TDD) principles:
- Implementation code is written before tests
- Tests are added as an afterthought (if at all)
- Test coverage is inconsistent
- Red-green-refactor cycle is not enforced

Without enforcement, the "red phase" (failing tests) never happens, which means:
- Requirements aren't validated before coding
- Edge cases are discovered late
- Refactoring is risky due to poor test coverage

## Proposed Solution

Require failing tests to exist before implementation code is written:

### Phase 1: Test Existence Gate
1. Developer creates test file with failing tests
2. System verifies tests exist for the issue/feature
3. Implementation PR cannot be created until test file exists

### Phase 2: Red Phase Verification
1. Tests must fail initially (red phase)
2. System runs tests and verifies they fail with expected reasons
3. Only then can implementation begin

### Phase 3: Green Phase Tracking
1. After implementation, tests must pass (green phase)
2. System tracks transition from red to green
3. Audit trail captures the TDD cycle

## Acceptance Criteria

- [ ] Pre-commit hook verifies test existence for new features
- [ ] Tests must fail initially (red phase gate)
- [ ] Implementation blocked until red phase passes
- [ ] Audit trail captures red/green/refactor cycle
- [ ] Works with pytest (Python) and Jest (JavaScript)
- [ ] Escape hatch for hotfixes with explicit override

## Technical Considerations

- Could integrate with existing worktree isolation rules
- Hook into PR creation workflow
- May need project-specific test naming conventions
- Consider test coverage thresholds (e.g., 80% minimum)

## Related

- CLAUDE.md: Worktree isolation rules
- Issue #62: Governance Workflow StateGraph
- Standard 0008: Documentation convention (test docs)