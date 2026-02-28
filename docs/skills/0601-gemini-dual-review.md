# 0602 - Skill: Claude-Gemini Dual Review Automation

**Status:** Planned (Issue #222)
**Created:** 2026-01-09
**Related Issues:** #222
**Prerequisites:** Gemini CLI v0.23.0+, Google AI Pro subscription, jq

---

## ⚠️ CRITICAL: Model Requirements (READ FIRST)

**ONLY this model is valid for Gemini reviews:**
- `gemini-3-pro-preview`

**INVALID - DO NOT USE:**
- `gemini-2.0-flash` - WRONG MODEL, review invalid
- `gemini-2.5-flash` - WRONG MODEL, review invalid
- `gemini-*-lite` - WRONG MODEL, review invalid
- Any model not `gemini-3-pro-preview` - WRONG MODEL, review invalid

**If quota is exhausted:**
1. **STOP** - Do not substitute another model
2. **Report** - Tell user "Gemini 3 Pro quota exhausted"
3. **Wait** - Reviews cannot proceed until quota resets
4. **DO NOT** claim a Flash review is a valid "Gemini review"

**Why this matters:** Gemini 3 Pro has reasoning capabilities that lesser models lack. Reviews with Flash/Lite models miss critical issues. A review by the wrong model is worse than no review because it creates false confidence.

---

## Overview

This skill implements a fully automated dual-AI review system where Claude Code (Sonnet 4.5) and Gemini CLI (3 Pro) collaborate on the Aletheia project. Gemini acts as a senior architect providing review gates at three critical workflow stages: LLD design, implementation review, and issue filing.

**Key Innovation:** JSON output parsing detects mid-session model downgrades (Gemini 3 Pro → Flash), ensuring reviews are always performed by the correct model tier.

**Design Decisions:**
1. ✅ **Model Detection:** JSON output parsing with abort on downgrade
2. ✅ **Context Refresh:** Once per session (model switches trigger abort anyway)
3. ✅ **Trigger Mode:** Fully automatic for all reviews
4. ✅ **Handle Eagerness:** Ignore Gemini's implementation offers (extract review only)
5. ✅ **Prompt Strategy:** Prompt library files (gemini-prompts/ directory)
6. ✅ **Session Logging:** Gemini writes directly to session log file
7. ✅ **Output Format:** Hybrid natural language + confidence scores ([BLOCKING], [HIGH], [SUGGESTION])
8. ✅ **Quota Exhaustion:** Abort immediately and notify user

---

## Prerequisites

Before using this skill, ensure:

1. **Gemini CLI v0.23.0+** installed and authenticated
   ```bash
   gemini --version  # Should show 0.23.0 or higher
   ```

2. **Google AI Pro subscription** active
   - 1,500 requests/day, 120/min quota
   - Access to Gemini 3 Pro model

3. **jq** installed for JSON parsing
   ```bash
   jq --version  # Should work without error
   ```

4. **Environment configured:**
   - `~/.gemini/.env` contains `GOOGLE_GENAI_USE_GCA=true`
   - `~/.gemini/settings.json` has `previewFeatures.enabled: true`

---

## Architecture Overview

### Three-Phase Automated Workflow

```
┌──────────────────────────────────────────────────────────────┐
│                    PHASE 1: LLD REVIEW                       │
├──────────────────────────────────────────────────────────────┤
│ Trigger: User says "write LLD" or LLD file saved            │
│                                                              │
│ 1. Claude writes LLD (template 0102)                        │
│ 2. AUTO-INVOKE: Gemini reviews (prompt: lld-review.txt)    │
│ 3. Model Check: JSON parsing ensures Gemini 3 Pro          │
│ 4. Claude parses feedback: [BLOCKING]/[HIGH]/[SUGGESTION]  │
│ 5. Claude updates LLD                                        │
│ 6. WAIT for user "implement" command                        │
└──────────────────────────────────────────────────────────────┘
                               ↓
┌──────────────────────────────────────────────────────────────┐
│                PHASE 2: IMPLEMENTATION REVIEW                │
├──────────────────────────────────────────────────────────────┤
│ Trigger: User says "implement" (post-LLD approval)          │
│                                                              │
│ 1. Claude implements (worktree, code, reports)             │
│ 2. AUTO-INVOKE: Gemini reviews impl + test reports         │
│ 3. Model Check: Abort if downgrade detected                │
│ 4. Claude parses approval/concerns                          │
│ 5. WAIT for BOTH Gemini + User approval                    │
│ 6. Execute merge only after dual approval                   │
└──────────────────────────────────────────────────────────────┘
                               ↓
┌──────────────────────────────────────────────────────────────┐
│                  PHASE 3: ISSUE FILING                       │
├──────────────────────────────────────────────────────────────┤
│ Trigger: User says "write issue for [X]"                    │
│                                                              │
│ 1. Claude drafts issue (template 0101)                      │
│ 2. AUTO-INVOKE: Gemini reviews for completeness            │
│ 3. Model Check: Ensure Gemini 3 Pro                        │
│ 4. Claude incorporates feedback                             │
│ 5. WAIT for user approval to file                          │
└──────────────────────────────────────────────────────────────┘
```

---

## Workflow Phases

### Phase 1: LLD Review Automation

**Trigger Detection:**
- User message contains: "write LLD", "create LLD", "draft LLD"
- OR: File saved matching pattern `docs/lld/active/*.md`

**Process:**
1. Claude writes LLD using template `docs/0102-TEMPLATE-feature-lld.md`
2. Claude saves LLD to `docs/lld/active/{issue-id}-{feature-name}.md`
3. **AUTO-INVOKE GEMINI:**
   - Load prompt from `gemini-prompts/lld-review.txt`
   - Replace placeholders: `{{LLD_CONTENT}}`, `{{LLD_PATH}}`
   - Execute: `tools/gemini-model-check.sh` (validates Gemini 3 Pro)
4. **Model Downgrade Detection:**
   - If Gemini switches to Flash → ABORT + notify user
   - If quota exhausted → ABORT + display reset time + log event
5. **Parse Feedback:**
   - Extract `[BLOCKING]` issues (security, correctness, fail-safe gates)
   - Extract `[HIGH]` priority issues (testing, mocking, data pipeline)
   - Extract `[SUGGESTION]` improvements (performance, maintainability)
   - **IGNORE:** Any "I can implement" or code snippets from Gemini
6. **Update LLD:**
   - Incorporate feedback sections into LLD
   - Track changes in version history
7. **Notify User:**
   ```
   LLD reviewed by Gemini 3 Pro.
   - X BLOCKING issues
   - Y HIGH priority issues
   - Z Suggestions

   LLD updated. Ready to implement? (say 'implement' to proceed)
   ```

**Error Scenarios:**

| Error | Detection | Response |
|-------|-----------|----------|
| Model downgrade | JSON parsing shows `gemini-2.5-flash` in models | ABORT + notify user + log event |
| Quota exhausted | 429 error or "Resource exhausted" in output | ABORT + calculate reset time + notify user |
| Network timeout | Gemini CLI exit code != 0 | RETRY once, then ABORT if fails |
| Invalid response | Missing [BLOCKING]/[HIGH]/[SUGGESTION] markers | Parse as best-effort, flag to user |

---

### Phase 2: Implementation Review Automation

**Trigger Detection:**
- User message: "implement", "start implementation", "proceed with code"
- **CONDITION:** LLD must exist and have passed Gemini review (tracked in `.claude/workflow-state.json`)

**Process:**
1. **Claude Implements** (standard workflow):
   - Create worktree: `git worktree add ../Aletheia-{IssueID} -b {IssueID}-feature-name`
   - Write code per LLD specifications
   - Generate reports:
     - `docs/reports/{IssueID}/implementation-report.md`
     - `docs/reports/{IssueID}/test-report.md`
2. **AUTO-INVOKE GEMINI:**
   - Load prompt from `gemini-prompts/implementation-review.txt`
   - Replace placeholders:
     - `{{ISSUE_ID}}` → Issue number
     - `{{IMPL_REPORT}}` → Implementation report content
     - `{{TEST_REPORT}}` → Test report content
     - `{{FILE_DIFFS}}` → Git diffs of changed files
   - Execute: `tools/gemini-model-check.sh`
3. **Model Downgrade Detection:** Same as Phase 1
4. **Parse Review Decision:**
   - Look for: `## Decision: [APPROVE]` or `## Decision: [BLOCK]`
   - Extract blocking concerns if any
   - Extract high/low priority issues
5. **Dual Approval Gate:**
   - If Gemini BLOCKS → Notify user, do NOT proceed to merge
   - If Gemini APPROVES → Ask user for final approval
   - Merge ONLY if BOTH Gemini + User approve
6. **Notify User:**
   ```
   Gemini approved implementation ✓

   {summary from Gemini}

   User approval required to merge. Proceed? (yes/no)
   ```

**Context Strategy:**
- Load full repository context **once per session** at start
- Cache in `.claude/workflow-state.json`
- Pass **diffs only** for reviews (not full files)
- If model downgrade detected → session state invalidated, user must restart

---

### Phase 3: Issue Filing Automation

**Trigger Detection:**
- User message: "write issue", "create issue", "file issue"
- Extract issue topic from message

**Process:**
1. **Claude Drafts Issue:**
   - Load template: `docs/0101-TEMPLATE-issue.md`
   - Populate sections based on user request
2. **AUTO-INVOKE GEMINI:**
   - Load prompt from `gemini-prompts/issue-review.txt`
   - Replace `{{ISSUE_DRAFT}}` with draft content
   - Execute: `tools/gemini-model-check.sh`
3. **Model Downgrade Detection:** Same as Phase 1
4. **Parse Feedback:**
   - Extract `[BLOCKING]` missing requirements
   - Extract `[HIGH]` needs clarification items
   - Extract `[SUGGESTION]` improvements
5. **Update Draft:**
   - Incorporate feedback into issue draft
   - Add missing sections (acceptance criteria, security, etc.)
6. **User Approval:**
   ```
   Issue draft reviewed by Gemini:

   {updated draft}

   File this issue? (yes/no)
   ```
7. **File Issue:** If approved: `gh issue create --repo martymcenroe/Aletheia --body-file {draft}`

---

### Phase 4: Session Logging (Gemini Direct Write)

**Trigger:**
- User runs `/cleanup` (any mode: quick/normal/full)
- OR: After major milestone (LLD approved, PR merged)

**Process:**
1. **Claude Gathers Context:**
   - Run: `git status`, `git log -1`, `gh pr list`
   - Collect: branch name, recent commits, open PRs
2. **BUILD GEMINI PROMPT:**
   - Load: `gemini-prompts/session-log.txt`
   - Replace placeholders:
     - `{{GIT_STATUS}}` → Current git status
     - `{{RECENT_COMMITS}}` → Last commit message
     - `{{OPEN_PRS}}` → Open pull requests
     - `{{CLEANUP_MODE}}` → quick/normal/full
3. **INVOKE GEMINI (NO model check):**
   - Allow graceful degradation (session logs not critical)
   - Gemini writes directly to `docs/session-logs/YYYY-MM-DD.md`
4. **VALIDATE FORMAT:**
   - Claude reads session log file
   - Check structure matches template from `docs/0100-TEMPLATE-GUIDE.md`
   - If invalid → Warn user + offer to rewrite
5. **COMMIT:**
   - `git add docs/session-logs/YYYY-MM-DD.md`
   - `git commit -m "docs: {mode} cleanup YYYY-MM-DD (Gemini + Claude)"`
   - `git push`

**Risk Mitigation:**
- Gemini direct write violates single-writer principle
- Claude validates format before committing
- If format invalid, Claude can rewrite the entry
- Track authorship: commit message includes "(Gemini + Claude)"

---

## Model Downgrade Detection

### The Problem

Gemini CLI automatically switches from Gemini 3 Pro to lower-tier models (Gemini 2.5 Flash, Flash-Lite) when quota limits are reached. This happens:
- **Without warning** to the user
- **Mid-session** during active reviews
- **Even with explicit `--model` flag**

This creates risk: reviews performed by wrong model tier have lower quality.

### The Solution

Use `--output-format json` to get model usage statistics, then parse and validate:

```bash
# Invoke Gemini with JSON output
gemini -p "Your prompt" --model gemini-2.5-pro --output-format json

# Response structure:
{
  "response": "...",  # Actual review content
  "stats": {
    "models": {
      "gemini-2.5-pro": { "apiRequests": 1, "tokens": { ... } },
      "gemini-2.5-flash": { ... }  # ← If this appears = DOWNGRADE!
    }
  }
}
```

**Detection Logic:**
```bash
# Extract models used
models=$(echo "$result" | jq -r '.stats.models | keys[]')

# Check for unexpected models
for model in $models; do
  if [[ "$model" != "gemini-2.5-pro" && "$model" != "gemini-3-pro-preview" ]]; then
    echo "ERROR: Model downgrade detected!" >&2
    echo "Actually used: $model" >&2
    exit 3  # Abort code 3 = downgrade detected
  fi
done
```

**Abort Strategy:**
1. **Detect downgrade** → Exit immediately (code 3)
2. **Notify user:**
   ```
   Gemini quota exhausted. Model downgraded to Flash.
   Aborting review to maintain quality.
   Next quota reset: 2026-01-10 00:00:00 CT
   ```
3. **Log event** → Append to `tmp/gemini-quota-events.jsonl`
4. **Preserve partial work** → LLD/draft exists but marked "pending Gemini review"

---

## Prompt Library

### Structure

```
gemini-prompts/
├── README.md                    # Versioning and usage guide
├── lld-review.txt               # Phase 1: LLD review prompt
├── implementation-review.txt    # Phase 2: Implementation review prompt
├── issue-review.txt             # Phase 3: Issue filing prompt
└── session-log.txt              # Phase 4: Session logging prompt
```

### Template Format

All prompts use `{{PLACEHOLDER}}` syntax for variable replacement:

**Example: `lld-review.txt`**
```
You are reviewing a Low-Level Design document for the Aletheia project.

CRITICAL INSTRUCTIONS:
1. Follow the review process in docs/0601-skill-gemini-lld-review.md
2. Use the three-tier priority system:
   - [BLOCKING] - Must fix before implementation
   - [HIGH] - Should fix before implementation
   - [SUGGESTION] - Nice to have
3. Do NOT offer to implement code or provide code snippets
4. Focus on design review only

LLD TO REVIEW:
File: {{LLD_PATH}}

{{LLD_CONTENT}}

OUTPUT FORMAT:
## [BLOCKING] Issues
- Issue 1...

## [HIGH] Priority Issues
- Issue 1...

## [SUGGESTION] Improvements
- Suggestion 1...

## Summary
Overall assessment and next steps recommendation.
```

### Versioning

Prompts are versioned in git for audit trail:
- Each change to a prompt = new commit
- Commit message format: `prompts: update {prompt-name} - {reason}`
- Example: `prompts: update lld-review.txt - add security focus`

---

## Implementation Components

### 1. Model Detection Script

**File:** `tools/gemini-model-check.sh`

**Purpose:** Reusable bash wrapper that validates Gemini model tier

**Usage:**
```bash
./tools/gemini-model-check.sh "Review this LLD..." "gemini-2.5-pro"

# Exit codes:
# 0 = Success (correct model used)
# 1 = Gemini CLI failed
# 2 = Quota exhausted (429 error)
# 3 = Model downgrade detected
```

**Features:**
- JSON output parsing
- 429 quota error detection
- Model downgrade detection
- Quota reset time extraction
- Clean error messages

### 2. Workflow State Tracker

**File:** `.claude/workflow-state.json`

**Purpose:** Track current workflow phase and review status

**Schema:**
```json
{
  "session_id": "abc123",
  "current_phase": "lld_review|implementation|issue_filing|none",
  "active_issue": 222,
  "lld_path": "docs/lld/active/222-dual-review.md",
  "lld_reviewed": true,
  "lld_review_timestamp": "2026-01-09T10:30:00Z",
  "gemini_approved": false,
  "user_approved": false,
  "repo_context_loaded": true,
  "repo_context_timestamp": "2026-01-09T09:00:00Z"
}
```

**Usage:**
- Updated after each phase transition
- Checked before auto-invoking Gemini
- Reset at session start

### 3. Quota Event Log

**File:** `tmp/gemini-quota-events.jsonl`

**Purpose:** Log quota exhaustion events for analytics

**Format:**
```jsonl
{"timestamp":"2026-01-09T10:30:00Z","event":"quota_exhausted","models_used":["gemini-2.5-pro","gemini-2.5-flash"],"phase":"lld_review","issue":222}
{"timestamp":"2026-01-09T11:00:00Z","event":"quota_reset","estimated_reset":"2026-01-10T00:00:00Z"}
```

**Usage:**
- Track quota consumption patterns
- Identify peak usage times
- Plan review scheduling

---

## Troubleshooting

### Issue: "Model downgrade detected!" during review

**Cause:** Gemini quota exhausted (1,500/day limit reached)

**Solution:**
1. Check quota reset time: Next reset is midnight CT (00:00:00 CT)
2. Wait for quota reset, OR
3. Use API key authentication as backup (if configured)

**Prevention:**
- Monitor `tmp/gemini-quota-events.jsonl` for usage patterns
- Schedule heavy reviews (implementation) for early in day
- Save lighter reviews (issues) for later in day

---

### Issue: "Gemini CLI failed" error

**Cause:** Network timeout, authentication failure, or Gemini CLI bug

**Solution:**
1. Check internet connection
2. Verify authentication: `gemini --version` (should not error)
3. Check `~/.gemini/oauth_creds.json` expiry date
4. Re-authenticate if needed: `rm ~/.gemini/oauth_creds.json`, then run `gemini`

---

### Issue: Session log format corrupted by Gemini

**Cause:** Gemini doesn't follow template format exactly

**Solution:**
1. Claude detects format error and warns user
2. Review `docs/session-logs/YYYY-MM-DD.md` manually
3. Claude offers to rewrite the entry if invalid
4. Accept Claude's rewrite or fix manually

**Prevention:**
- Prompt engineering: Make format requirements VERY explicit
- Provide examples in `gemini-prompts/session-log.txt`
- Add format validation before commit

---

### Issue: Reviews taking too long (>2 minutes)

**Cause:** Large LLD or implementation diffs sent to Gemini

**Solution:**
1. Break large LLDs into multiple files
2. Use summary sections instead of full diffs for implementation review
3. Consider increasing timeout in `tools/gemini-model-check.sh`

**Prevention:**
- Keep LLDs under 2000 lines
- Split large features into multiple issues

---

## Examples

### Example 1: LLD Review End-to-End

**User:** "Write an LLD for adding user authentication"

**Claude:**
1. Creates `docs/lld/active/223-user-authentication.md` using template 0102
2. Populates sections: Context, Requirements, Alternatives, Technical Approach
3. **AUTO-INVOKES GEMINI:**
   - Prompt: `gemini-prompts/lld-review.txt`
   - Model check: ✓ Gemini 3 Pro confirmed
4. **Gemini Response:**
   ```
   ## [BLOCKING] Issues
   - Missing security consideration: Password storage method not specified (bcrypt? scrypt?)
   - No session timeout defined

   ## [HIGH] Priority Issues
   - Test scenarios missing: password reset flow
   - Dependency on JWT library not specified (jsonwebtoken? jose?)

   ## [SUGGESTION] Improvements
   - Consider adding 2FA support in future

   ## Summary
   Address BLOCKING issues before implementation. HIGH priority items should be clarified in LLD.
   ```
5. **Claude Updates LLD:**
   - Adds password hashing spec (bcrypt, 12 rounds)
   - Defines session timeout (30 minutes idle, 24 hours absolute)
   - Adds test scenario: password reset flow
   - Specifies dependency: `jose` library for JWT
6. **Claude Notifies User:**
   ```
   LLD reviewed by Gemini 3 Pro.
   - 2 BLOCKING issues (resolved)
   - 2 HIGH priority issues (resolved)
   - 1 Suggestion (noted for future)

   LLD updated. Ready to implement? (say 'implement' to proceed)
   ```

**User:** "implement"

**Claude:** Proceeds to Phase 2 (Implementation Review)

---

### Example 2: Quota Exhaustion Handling

**User:** "Write an LLD for performance optimization"

**Claude:**
1. Creates LLD
2. **AUTO-INVOKES GEMINI:**
3. **Model Check:** ❌ DOWNGRADE DETECTED
   - Expected: `gemini-2.5-pro`
   - Actually used: `gemini-2.5-flash`
4. **ABORT IMMEDIATELY:**
   ```
   ⚠️ Gemini quota exhausted. Model downgraded to Flash. Aborting review.

   Your LLD has been saved to docs/lld/active/224-performance-opt.md
   but has NOT been reviewed by Gemini 3 Pro.

   Next quota reset: 2026-01-10 00:00:00 CT (in 13 hours, 30 minutes)

   Options:
   1. Wait for quota reset and I'll auto-review then
   2. Review the LLD manually and say "proceed to implement"
   3. Use API key authentication (if configured)
   ```
5. **Event Logged:** `tmp/gemini-quota-events.jsonl`
   ```jsonl
   {"timestamp":"2026-01-09T10:30:00Z","event":"quota_exhausted","models_used":["gemini-2.5-pro","gemini-2.5-flash"],"phase":"lld_review","issue":224}
   ```

---

### Example 3: Implementation Review with Dual Approval

**User:** "implement" (after LLD approved)

**Claude:**
1. Creates worktree: `git worktree add ../Aletheia-223 -b 223-user-auth`
2. Implements per LLD specifications
3. Generates reports:
   - `docs/reports/223/implementation-report.md`
   - `docs/reports/223/test-report.md`
4. **AUTO-INVOKES GEMINI:**
   - Prompt includes: implementation report, test report, file diffs
   - Model check: ✓ Gemini 3 Pro confirmed
5. **Gemini Response:**
   ```
   ## Decision: [APPROVE]

   ## [BLOCKING] Concerns
   None

   ## [HIGH] Priority Issues
   - Test coverage at 85% - consider adding edge case tests for password reset flow

   ## [SUGGESTION] Improvements
   - Extract password validation logic to separate utility function

   ## Summary
   Implementation aligns with LLD. Code quality is high. Tests pass.
   Approve for merge with recommendation to add edge case tests in follow-up.
   ```
6. **Claude Asks User:**
   ```
   Gemini approved implementation ✓

   Test coverage at 85% - recommended to add edge case tests.
   Extract password validation suggested (low priority).

   User approval required to merge. Proceed? (yes/no)
   ```

**User:** "yes"

**Claude:**
7. Executes merge: `gh pr merge --squash`
8. Cleanup: Removes worktree and branches

---

## References

- **0004-orchestration-protocol.md** - 12-step workflow, review gates
- **0601-skill-gemini-lld-review.md** - Gemini's LLD review procedure (3-tier priority system)
- **0100-TEMPLATE-GUIDE.md** - Session log format specification
- **0102-TEMPLATE-feature-lld.md** - LLD template structure
- **0101-TEMPLATE-issue.md** - Issue template structure
- **0009-session-closeout-protocol.md** - Session cleanup procedure

---

## Rollout Plan

### Phase 1: Foundation (Week 1) - CURRENT
- [ ] Create `gemini-prompts/` directory and library files
- [ ] Implement `tools/gemini-model-check.sh` wrapper
- [ ] Create `.claude/workflow-state.json` schema
- [ ] Update `.claude/settings.local.json` permissions
- [ ] Test model detection in isolation

### Phase 2: LLD Review (Week 2)
- [ ] Implement trigger detection ("write LLD")
- [ ] Integrate `gemini-prompts/lld-review.txt`
- [ ] Test end-to-end with real LLD
- [ ] Verify downgrade detection with quota exhaustion test
- [ ] Document in CLAUDE.md

### Phase 3: Implementation Review (Week 3)
- [ ] Implement trigger detection ("implement")
- [ ] Integrate `gemini-prompts/implementation-review.txt`
- [ ] Build dual approval gate logic
- [ ] Test with real implementation + reports
- [ ] Update 0004-orchestration-protocol.md

### Phase 4: Issue Filing + Session Logs (Week 4)
- [ ] Implement issue filing automation
- [ ] Enable Gemini direct write to session logs
- [ ] Test session log validation
- [ ] Full system integration test
- [ ] User acceptance testing

---

## Success Criteria

1. ✅ LLD reviews happen automatically without user intervention
2. ✅ Model downgrades detected 100% of the time
3. ✅ Zero instances of wrong model used for reviews
4. ✅ Dual approval gate enforced (Gemini + User)
5. ✅ Session logs written by Gemini with <5% format error rate
6. ✅ Quota exhaustion handled gracefully (no crashes)
7. ✅ User satisfaction: "Feels like having a senior architect on the team"

---

**Last Updated:** 2026-01-09
**Status:** Documentation complete, awaiting implementation (Issue #222)
