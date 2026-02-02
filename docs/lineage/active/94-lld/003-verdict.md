# LLD Review: 194-Feature: Lu-Tze: The Janitor - Automated Repository Hygiene Workflow

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD proposes a solid architecture using LangGraph for state management and a plugin-based probe system. The separation of concerns (Sweeper/Fixer/Reporter) is well-designed. However, the design is **BLOCKED** due to a critical Safety omission regarding execution bounds (marked as TODO in the text) and a gap in testing the production reporter implementation.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Probe System: Four built-in probes (links, worktrees, harvest, todo), parallel execution, failure isolation | 010, 030, 050, 060, 130 | ✓ Covered |
| 2 | Fixer System: Auto-fix for links/worktrees, atomic commits, dry-run | 020, 040, 070 | ✓ Covered |
| 3 | Reporter System: GitHub issue creation/update with deduplication, LocalFileReporter | 100, 110 | **GAP** (See below) |
| 4 | CLI Interface: Full CLI with flags (--scope, --auto-fix, etc.) | 070, 080, 090, 120, 140 | ✓ Covered |
| 5 | CI Compatibility: Silent mode with GITHUB_TOKEN auth | 080, 090 | ✓ Covered |
| 6 | Exit Codes: 0 clean, 1 unfixable | 150, 160 | ✓ Covered |
| 7 | Reversibility: All fixes create git commits | 020, 040 | ✓ Covered |

**Coverage Calculation:** 6 requirements covered / 7 total = **85%**

**Verdict:** **BLOCK** (<95%)

**Missing Test Scenarios:**
- Requirement #3 specifies "GitHub issue creation". While Test 100/110 verify the *reporting abstraction* via `LocalFileReporter`, there is no test scenario (unit or integration) that verifies the `GitHubReporter` class correctly constructs `gh` CLI commands or handles `gh` output.
- **Action:** Add a unit test scenario (e.g., "GitHubReporter constructs correct CLI args") using mocks to ensure the production reporter works.

## Tier 1: BLOCKING Issues

### Cost
- [ ] No issues found.

### Safety
- [ ] **Runaway Execution Bounds Undefined (CRITICAL):** Section 7.2 lists "Runaway execution" mitigation as "TODO". The Logic Flow (Section 2.5) does not implement timeouts. You must define a specific timeout strategy (e.g., `subprocess.run(..., timeout=30)` or async timeouts) in the `Sweeper` node to prevent the Janitor from hanging indefinitely on large files or symlink loops.

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] No issues found.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Test Coverage Gap:** As noted in the Coverage Analysis, relying solely on `LocalFileReporter` for testing leaves the actual `GitHubReporter` code path verified only by "deployment". Add a unit test that mocks the `subprocess.run` call within `GitHubReporter` to verify it sends the correct title, body, and labels to the `gh` CLI.

## Tier 3: SUGGESTIONS
- **CLI Robustness:** Consider adding a `--timeout` flag to the CLI args to override default probe timeouts.
- **Probe Registry:** In `agentos/workflows/janitor/probes/__init__.py`, ensure the registry dynamic loading is safe (e.g., doesn't execute code on import unintentionally).

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision