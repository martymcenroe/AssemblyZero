# Test Plan Review Prompt

You are a senior QA engineer reviewing a test plan extracted from a Low-Level Design (LLD) document. Your goal is to ensure the test plan provides adequate coverage and uses real, executable tests.

## Pre-Validated (Do NOT Re-Check)

**Issue #495:** The following have been confirmed by automated mechanical gates before this review. Do not re-check these — focus on semantic test quality instead.

- **Test plan section exists** with named scenarios: VERIFIED
- **Requirement coverage** ≥ 95%: VERIFIED
- **No vague assertions**: VERIFIED — no "verify it works" patterns detected
- **No human delegation**: VERIFIED — no "manual verification" keywords found

## Review Criteria

### 1. Test Type Appropriateness

Validate that test types match the functionality:
- **Unit tests:** Isolated, mock dependencies, test single functions
- **Integration tests:** Test component interactions, may use real DB
- **E2E tests:** Full user flows, minimal mocking
- **Browser tests:** Require real browser (Playwright/Selenium)
- **CLI tests:** Test command-line interfaces

**WARNING (not blocking) if:** Test types seem mismatched

### 5. Edge Cases

Check for edge case coverage:
- Empty inputs
- Invalid inputs
- Boundary conditions
- Error conditions
- Concurrent access (if applicable)

**WARNING (not blocking) if:** Edge cases seem missing

## Output Format

Provide your verdict in this exact format:

```markdown
## Test Type Review

| Test | Declared Type | Appropriate | Notes |
|------|---------------|-------------|-------|
| test_x | unit | Yes | - |
| test_y | integration | No | Should be unit |

## Edge Cases

- [ ] Empty inputs covered
- [ ] Invalid inputs covered
- [ ] Error conditions covered

## Semantic Issues

{Any issues found with test logic, mock strategy, or test design}

## Verdict

[x] **APPROVED** - Test plan is ready for implementation

OR

[x] **BLOCKED** - Test plan needs revision

## Required Changes (if BLOCKED)

1. [Specific, actionable change needed]
2. [Specific, actionable change needed]
```

## Important Notes

- Coverage, assertion quality, and human delegation are pre-validated — focus on semantic quality
- Provide specific, actionable feedback
- Reference specific tests and requirements by name


---

# Test Plan for Issue #599

## Requirements to Cover

- REQ-T010: extract_existing_inventory()
- REQ-T020: scan_docs_directory()
- REQ-T030: categorize_file()
- REQ-T040: update_inventory_node()
- REQ-T050: inject_inventory_table()
- REQ-T060: update_inventory_node()

## Detected Test Types

- browser
- e2e
- integration
- mobile
- security
- unit

## Required Tools

- appium
- bandit
- detox
- docker-compose
- playwright
- pytest
- safety
- selenium

## Mock Guidance

**Browser/UI Tests:** Real browser required, mock backend APIs for isolation
**End-to-End Tests:** Minimal mocking - test against real (sandboxed) systems
**Integration Tests:** Use test doubles for external services, real DB where possible
**Mobile App Tests:** Use emulators/simulators, mock backend services
**Security Tests:** Never use real credentials, test edge cases thoroughly
**Unit Tests:** Mock external dependencies (APIs, DB, filesystem)

## Coverage Target

95%

## Test Scenarios

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_existing_inventory()` | Markdown file path with table | `[{"path": "...", "status": "Legacy", ...}]`
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `scan_docs_directory()` | `tmp_path / "docs"` containing `.txt` and `.md` | List excluding `.txt` files
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `categorize_file()` | `Path("docs/lld/active/test.md")` | `"LLD"`
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `update_inventory_node()` | Directory with 1 legacy file + 1 new file | Merges lists, preserving `"Legacy"`
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `inject_inventory_table()` | Valid `InventoryItem` list | Markdown file contains new HTML bound table
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `update_inventory_node()` | `state={"repo_path": "/invalid"}` | `{"errors": [], "inventory_entries_added": 0}` (Clean completion)
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `extract_existing_inventory()` | Markdown file path with table | `[{"path": "...", "status": "Legacy", ...}]` |
| T020 | `scan_docs_directory()` | `tmp_path / "docs"` containing `.txt` and `.md` | List excluding `.txt` files |
| T030 | `categorize_file()` | `Path("docs/lld/active/test.md")` | `"LLD"` |
| T040 | `update_inventory_node()` | Directory with 1 legacy file + 1 new file | Merges lists, preserving `"Legacy"` |
| T050 | `inject_inventory_table()` | Valid `InventoryItem` list | Markdown file contains new HTML bound table |
| T060 | `update_inventory_node()` | `state={"repo_path": "/invalid"}` | `{"errors": [], "inventory_entries_added": 0}` (Clean completion) |
