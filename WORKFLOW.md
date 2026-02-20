# WORKFLOW.md - AssemblyZero Development Workflow

This file contains workflow gates and procedures for projects using
the full AssemblyZero development process. Only loaded when a project's
CLAUDE.md says to read it.

Projects using this workflow: Aletheia, Talos, Clio, maintenance, Hermes, RCA-PDF

---

## Gemini Reviews - Orchestrator Only (CRITICAL)

**Claude does NOT submit to Gemini. The orchestrator (human) controls all Gemini submissions.**

This is the Inversion of Control principle: The workflow script (orchestrator) controls when reviews happen. Claude prepares materials and waits for the orchestrator to run reviews.

**Claude's role:**
- Prepare review materials (LLD, reports, diffs)
- Save materials to appropriate locations
- Wait for orchestrator to run review and provide results

**Orchestrator's role:**
- Submit materials to Gemini
- Manage credentials and quota
- Provide review results back to Claude

**BANNED for Claude:**
- `gemini --prompt "..."` (any direct CLI)
- `gemini-retry.py` (orchestrator tool, not Claude tool)
- Any autonomous Gemini API calls

**When Orchestrator Provides Review Results:**
- **[APPROVE]**: Proceed past the gate
- **[BLOCK]**: Fix issues, wait for re-review
- **Nothing**: WAIT - do not assume approval

---

## LLD Review Gate (Before Coding)

**Before writing ANY code for an issue, this gate must pass:**

```
LLD Review Gate Check:
+-- Does an LLD exist for this issue?
|   +-- YES -> Proceed
|   +-- NO -> Ask user: Create LLD or waive requirement?
|
+-- Has orchestrator provided Gemini review results?
    +-- [APPROVE] -> Gate PASSED, proceed to coding
    +-- [BLOCK] -> Gate FAILED, fix issues and wait for re-review
    +-- Not yet reviewed -> WAIT for orchestrator
```

**Claude's responsibility:**
1. Write the LLD to `docs/LLDs/active/{issue-id}-*.md`
2. Commit the LLD
3. **STOP and wait** for orchestrator to run Gemini review
4. Resume only after orchestrator provides review results

**Escape hatch:** For [HOTFIX] tagged issues, orchestrator can explicitly waive.

---

## Report Generation Gate (After Coding)

**Before implementation review, generate required reports:**

Required files:
- `docs/reports/active/{issue-id}-implementation-report.md`
- `docs/reports/active/{issue-id}-test-report.md`

Move to `docs/reports/done/` after merge.

**Implementation Report minimum content:**
- Issue reference (link)
- Files changed
- Design decisions
- Known limitations

**Test Report minimum content:**
- Test command executed
- Full test output (not paraphrased)
- Skipped tests with reasons
- Coverage metrics (if available)

---

## Implementation Review Gate (Before PR)

**Before creating ANY PR, this gate must pass:**

```
Implementation Review Gate Check:
+-- Do reports exist?
|   +-- YES -> Proceed
|   +-- NO -> Execute REPORT GENERATION GATE first
|
+-- Has orchestrator provided Gemini review results?
    +-- [APPROVE] -> Gate PASSED, create PR
    +-- [BLOCK] -> Gate FAILED, fix issues and wait for re-review
    +-- Not yet reviewed -> WAIT for orchestrator
```

**Claude's responsibility:**
1. Create implementation report: `docs/reports/active/{issue-id}-implementation-report.md`
2. Create test report: `docs/reports/active/{issue-id}-test-report.md`
3. Commit reports and all implementation code
4. **STOP and wait** for orchestrator to run Gemini review
5. Resume only after orchestrator provides review results

**CRITICAL:** If orchestrator reports [BLOCK], Claude MUST NOT create the PR.

---

## Skipped Test Gate (Mandatory)

**After ANY test run with skipped tests, you MUST audit before claiming success.**

```
If test output shows "X skipped":
+-- AUDIT each skipped test
|   +-- What does this test verify?
|   +-- Why was it skipped?
|   +-- Is this critical functionality?
|   +-- Was it verified another way?
+-- If critical AND not verified -> Status = UNVERIFIED
+-- If critical AND verified manually -> Document verification
+-- If not critical -> Document and proceed
```

**Output format (REQUIRED when skips exist):**

```
SKIPPED TEST AUDIT:
- [SKIPPED] "test_name_here"
  - Verifies: {what functionality this test covers}
  - Skip reason: {why it was skipped}
  - Critical: YES/NO
  - Alt verification: {how verified, or NONE}
  - Status: VERIFIED/UNVERIFIED
```

**Rules:**
1. NEVER say "tests pass" if any critical functionality is UNVERIFIED
2. UNVERIFIED status blocks merge until resolved
3. Non-critical skips can proceed with documentation
4. `pytest.skip()` without reason in test code is always suspicious

---

## Worktree Isolation Rule (Multi-Agent Safety)

**ALL code changes MUST be made in a worktree. NEVER commit code directly to main.**

This rule exists because **multiple agents work on this project simultaneously**. If two agents both modify main directly, their changes will conflict and corrupt each other's work.

**What requires a worktree:**
- ANY change to `.py`, `.js`, `.ts`, `.sh`, `.json`, `.yaml`, `.html`, `.css` files
- ANY change to `provision.sh`, `pyproject.toml`, `package.json`
- ANY infrastructure or deployment changes
- Bug fixes, even "quick" ones

**What can be committed directly to main:**
- Documentation files (`docs/**/*.md`)
- `CLAUDE.md` updates (meta-documentation)
- `.gitignore` updates

**Before ANY code edit, verify:**
```bash
git worktree list
# You MUST see your worktree path, NOT just the main folder
```

**Worktree creation pattern:**
```bash
git worktree add ../ProjectName-{IssueID} -b {IssueID}-short-desc
git -C ../ProjectName-{IssueID} push -u origin HEAD
poetry install --directory ../ProjectName-{IssueID}  # Install dependencies
```

**If you discover a bug while doing other work:**
1. **STOP** - Do not fix it inline
2. **Create an issue** for the bug
3. **Create a worktree** for the fix
4. **Fix it properly** with PR review

### Post-Merge Cleanup (Mandatory)

**After ANY PR is merged, execute this cleanup IMMEDIATELY:**

```
Post-Merge Cleanup:
+-- Archive lineage: python tools/archive_worktree_lineage.py --worktree ../ProjectName-{ID} --issue {ID}
+-- Remove worktree: git worktree remove ../ProjectName-{ID}
+-- Delete local branch: git branch -d {ID}-desc
+-- Delete remote branch: git push origin --delete {ID}-desc
|   (or use --delete-branch flag on gh pr merge)
+-- Pull merged changes: git pull
+-- Verify: git branch -a (should show only main)
```

**Archive step details:**
- Copies `docs/lineage/active/{issue}-*/` to main repo's `docs/lineage/archived/`
- Cleans ephemeral files (`.coverage`, `__pycache__`, `.pytest_cache`)
- Commits archived lineage to main repo
- Skip with `--no-commit` if you want to review first

**This is NON-NEGOTIABLE.** Stale branches and orphaned worktrees confuse future agents, accumulate garbage, and signal incomplete work.

---

## Coding Task Gate (Execute Immediately)

**When you receive ANY task that involves modifying code files, STOP and execute this gate BEFORE reading docs or planning:**

```
Step 1: Identify task type
+-- Modifying .py, .js, .ts, .sh, .json, .yaml, .html, .css files?
    +-- YES -> Execute Step 2 (worktree required)
    +-- NO (docs only) -> Can work on main

Step 2: Create worktree FIRST
+-- git worktree list                              # Verify current state
+-- git worktree add ../ProjectName-{ID} -b {ID}-desc # Create worktree
+-- git push -u origin HEAD                        # Push immediately
+-- poetry install --directory ../ProjectName-{ID} # Install dependencies
+-- ONLY THEN proceed to read docs and plan
```

**Why this order matters:** If you read docs first, you enter "implementation mindset" and skip the worktree. Create the worktree BEFORE you start thinking about the code.

---

## Decision-Making Protocol

**When you encounter an unexpected error or decision point:**

1. **STOP** - Do not apply quick fixes
2. **Check documentation:** Lessons learned, open issues, design documents
3. **If still unsure: ASK** - Query the orchestrator
4. **Never prioritize "getting it done" over "getting it done right"**

The documentation system exists so you don't need persistent memory. USE IT.

---

## Post-Session Transcript Cleanup

**After any PTY-recorded session, clean the raw transcript:**

```bash
# Clean a raw transcript (removes TUI garbage, preserves conversation)
poetry run python tools/clean_transcript.py transcripts/session.raw

# Optional: fix word-merged text (requires: poetry add wordninja)
poetry run python tools/clean_transcript.py --fix-spaces transcripts/session.raw
```

**Outputs:**
- `session.clean` — Garbage removed, content preserved
- `session.user` — Extracted user input only

**Tools:**
- `tools/transcript_filters.py` — 95-pattern regex filter for PTY artifacts (spinners, status bars, permission UI)
- `tools/clean_transcript.py` — Multi-pass cleaner (garbage removal → dedup → block dedup → optional space fix)

**The original `.raw` file is NEVER modified.**

---

## You Are Not Alone

Other agents may work on this project. Check session logs for recent context. Coordinate via the project's issue tracker.
