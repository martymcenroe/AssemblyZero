# LLD Review: 170-Feature: Add pre-commit check for type/class renames that miss usages

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD provides a solid foundation for a critical code integrity check. The logic for detecting removals via git diff and grepping for orphaned usages is sound. However, the design contains open questions that must be resolved before implementation, and there is a gap in test coverage regarding the performance requirement specified in Section 3.

## Open Questions Resolved
- [x] ~~What file extensions should be checked? (Assuming .py files only initially)~~ **RESOLVED: Restrict to `.py` files only.** Searching non-code files introduces noise and false positives irrelevant to build integrity.
- [x] ~~Should we detect renamed types (old→new) or just removed types?~~ **RESOLVED: Just removed types.** A rename manifests in git diff as a removal of the old definition. The logic should simply verify that if a definition is removed, no references to that identifier remain in the codebase.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Workflow node detects removed type definitions from git diff | T010, T020, T030 | ✓ Covered |
| 2 | Workflow node searches source files for orphaned references | T040, T050 | ✓ Covered |
| 3 | Workflow fails with clear error listing file, line, and content | T090, T100 | ✓ Covered |
| 4 | Check excludes `docs/`, `lineage/`, and markdown files | T060, T070 | ✓ Covered |
| 5 | Check runs in under 5 seconds for repositories with <1000 Python files | - | **GAP** |
| 6 | Error messages include actionable guidance (what to fix) | T100 | ✓ Covered |

**Coverage Calculation:** 5 requirements covered / 6 total = **83%**

**Verdict:** **BLOCK** (Must be ≥95%)

**Missing Test Scenarios:**
- **T110 - Performance/Timeout Enforcer:** A test that ensures the node enforces a timeout (or simulates a long-running grep) to verify the fail-safe mechanism mentioned in Section 7.2 ("Timeout limit (10s)"). While strict performance benchmarking is hard in unit tests, verification of the timeout logic is required if performance is a functional requirement.

## Tier 1: BLOCKING Issues
No blocking issues found in Tier 1 categories.

### Cost
- [ ] No issues found.

### Safety
- [ ] No issues found.

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] **Subprocess Safety:** The LLD mentions using `shlex.quote()` for mitigation. This implies the intention to construct shell command strings. **Recommendation:** Do not use `shell=True`. Use `subprocess.run(["git", "grep", pattern, ...], shell=False)` passing arguments as a list. This renders `shlex.quote()` largely unnecessary and is safer by design.

### Observability
- [ ] **Logging Strategy:** Section 2.3 defines the return structure, but the design should explicitly log *what* was scanned. **Recommendation:** Log the count of removed types detected and the number of files scanned. This is crucial for debugging false negatives (e.g., "Why didn't it catch this? Oh, it detected 0 removed types.").

### Quality
- [ ] **Requirement Coverage:** Coverage is 83%. Requirement #5 (Performance < 5s) is listed as a functional requirement but lacks a verification test. **Recommendation:** Add `T110` to verify the timeout mechanism or move R5 to a non-functional constraint section if strict automated testing isn't feasible.

## Tier 3: SUGGESTIONS
- **Regex Robustness:** Consider adding a negative lookahead for string literals in the regex to avoid matching type names inside strings (though `git grep` makes this harder without PCRE).
- **False Positives:** Add a mechanism (e.g., `# noqa: type-rename`) to allow developers to explicitly bypass the check for specific lines if legitimate legacy references exist.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision