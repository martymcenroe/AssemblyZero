# LLD Review: #444 - Feature: Enhance /test-gaps with Infrastructure Audit and Project-Aware Heuristics

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The Low-Level Design effectively expands the `/test-gaps` skill into a multi-layered analysis tool while maintaining backward compatibility. The choice to implement this as a skill prompt (Option A) rather than a Python tool imposes constraints on testing, which are adequately justified. The architecture correctly balances depth of analysis with token/tool-call costs via the "grep-first" strategy and explicit budgeting.

## Open Questions Resolved
- [x] ~~Should Layer 2 skip/xfail audit attempt GitHub API calls to check issue open/closed status, or rely on comment-based heuristics only?~~ **RESOLVED: Rely on comment-based heuristics only.** Avoiding an API dependency ensures the skill remains portable and avoids authentication friction or rate-limiting issues within the Claude session.
- [x] ~~What is the maximum file count threshold before Layer 3 heuristic file-pairing checks become too expensive?~~ **RESOLVED: Cap at 200 source files.** If matches exceed this count, the skill should sample the first 200 and add a warning to the output. This protects against excessive tool calls in large monorepos.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Running `/test-gaps` with no arguments MUST produce output identical to Layer 1 | 010 | ✓ Covered |
| 2 | `--layer infra` MUST detect `continue-on-error`, missing discovery, coverage gaps | 020, 110 | ✓ Covered |
| 3 | Skill MUST classify `skip`/`xfail`/`.only` markers as Tracked/Stale/Untracked | 030 | ✓ Covered |
| 4 | Skill MUST count test functions per tier and flag inverted pyramids | 040 | ✓ Covered |
| 5 | Skill MUST auto-detect project type from marker files | 050, 120 | ✓ Covered |
| 6 | Skill MUST run project-type-specific checks (EXT/API/WEB families) | 060 | ✓ Covered |
| 7 | Skill MUST grade test reports on 0-4 scale | 070 | ✓ Covered |
| 8 | Skill MUST produce structured output with severity-sorted actions & checklist | 080 | ✓ Covered |
| 9 | Tool calls MUST stay within budget (15 default, 50 full) | 090 | ✓ Covered |
| 10 | Skill MUST support `--full`, `--file`, `--layer`, `--project-type` args | 100 | ✓ Covered |

**Coverage Calculation:** 10 requirements covered / 10 total = **100%**

**Verdict:** PASS

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation.

### Cost
- [ ] No issues found. The design explicitly addresses loop bounds (200 file cap) and tool call budgets (grep-first optimization).

### Safety
- [ ] No issues found. Analysis is read-only and scoped to the worktree.

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] No issues found. The architectural decision to keep this as a single skill file (Option A) is well-reasoned despite the complexity it adds to the prompt.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Manual Testing Exception:** The Test Plan (Section 10) relies entirely on manual verification, which technically violates the "No Human Delegation" standard. However, this is accepted as a valid exception because the artifact is a **Claude Skill Prompt**, not executable Python code, and no automated harness exists for testing prompts within the Claude Code runtime environment. The justification in Section 10.3 is accepted.

## Tier 3: SUGGESTIONS
- **Heuristic Clarity:** Ensure the "Stale" skip detection (Issue closed vs open) output clearly labels it as "Potential" or "Heuristic" so users don't lose trust if the comment parsing is imperfect.
- **Maintainability:** Consider adding a "Developer Comments" block at the top of the prompt explaining the section structure for future maintainers, as 450 lines of Markdown instruction can be difficult to navigate.

## Questions for Orchestrator
1. None.

## Verdict
[x] **APPROVED** - Ready for implementation
[ ] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision