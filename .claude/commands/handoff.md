---
description: Generate a high-fidelity context transfer prompt for the next session
argument-hint: "[--help] [--reboot]"
scope: global
---

# Handoff

**If `$ARGUMENTS` contains `--help`:** Display the Help section below and STOP.

## Help

```
/handoff - Context transfer + lessons learned + hygiene report

Usage: `/handoff [--reboot]`

Options:
  --reboot    Save state but skip spawning a new terminal (for reboots/shutdowns)

This is context transfer AND institutional memory capture:
- Captures what matters for the next session (forward-looking)
- Records lessons learned (institutional knowledge)
- Reports hygiene exposure (stale branches, stashes, uncommitted — never deletes)
- Appends session log (backward-looking record)

Call /handoff at session end or BEFORE context compaction kills your memory.
```

## Execution

**Do NOT delegate to a subagent.** The whole point is that YOU have the context. A subagent would need to reconstruct it from files, which is the problem we're solving.

### Step 0: Leave It Clean

Before generating the handoff, clean up after yourself:

1. **Delete scratch/tmp files** you created this session (e.g. `tmp-*.json`, `*.tmp`, scratch debug files). Use `git status` to spot them — anything untracked that's clearly session debris gets removed. **Ask before deleting** if you're unsure whether a file is intentional.
2. **Flag uncommitted changes** — If there are staged or unstaged changes, warn the user: "You have uncommitted changes in {repo}. Commit, stash, or discard before handoff?"
3. **Flag stale worktrees** — If you created worktrees this session that were merged/abandoned, mention them so the user can prune.
4. **Purge tmpclaude files** — Delete session debris:
   ```bash
   find /c/Users/mcwiz/Projects/{REPO_NAME} -name "tmpclaude-*-cwd" -type f -delete 2>/dev/null
   ```

5. **Skill sync (AssemblyZero only):** If the current repo is AssemblyZero, run:
   ```bash
   python /c/Users/mcwiz/Projects/unleashed/src/skill_sync.py
   ```
   This deploys updated `scope: global` skills to `~/.claude/commands/` and warns on local drift. Zero LLM cost — Python handles the comparison.

This step is fast — don't skip it. The next session shouldn't start by cleaning up after this one.

### Step 1: Gather State (parallel)

Run these in parallel to supplement your memory with current facts:

1. **Session context:**
   ```bash
   pwd && git rev-parse --show-toplevel 2>/dev/null && echo $UNLEASHED_VERSION && date '+%Y-%m-%d %H:%M:%S'
   ```

2. **Plan snapshot (deterministic):** Run
   ```bash
   python /c/Users/mcwiz/Projects/unleashed/src/plan_archiver.py status
   ```
   Read the emitted JSON. Use its fields (`plan_path`, `plan_slug`, `plan_state`, `total_steps`, `completed_steps`, `remaining_steps`) in the `## The Plan` section below. Do NOT reconstruct plan state from memory — the JSON is the source of truth. If `status: "no_plan"`, skip the `## The Plan` section entirely. If `status: "error"`, note the error in `## The Plan` and continue.

3. **Git status across touched repos** — For every repo you modified this session, run:
   ```bash
   git -C /c/Users/mcwiz/Projects/{REPO} log --oneline -3
   git -C /c/Users/mcwiz/Projects/{REPO} status --short
   ```

4. **Task list** — Check if there are active tasks (use TaskList tool). Note completed vs pending.

5. **Open issues** — For repos where you closed or created issues, note the current state.

6. **Hygiene scan** — For every repo you touched this session (and the current repo at minimum), run these in parallel:
   ```bash
   # Stale local branches (merged into main but not deleted)
   git -C /c/Users/mcwiz/Projects/{REPO} branch --merged main | grep -v 'main$'
   # Branches where remote is gone
   git -C /c/Users/mcwiz/Projects/{REPO} branch -vv | grep ': gone]'
   # Worktrees beyond main
   git -C /c/Users/mcwiz/Projects/{REPO} worktree list
   # Stashes
   git -C /c/Users/mcwiz/Projects/{REPO} stash list
   ```
   Store results for the Hygiene Report section in Step 2. This is REPORTING only — never delete anything.

### Step 2: Write the Handoff Prompt

Output a single markdown block to the screen (NOT to a file). The user will copy-paste it.

**Structure:**

```markdown
# Session Handoff — {DATE} {TIME}

> **Directory:** `{CWD}` | **Repo:** `{REPO_NAME}` (or "none — started from Projects root")
> **Unleashed:** v{VERSION} (or "not running under unleashed")

## What Was Accomplished

{Concrete outcomes: file paths, commit SHAs, issue numbers. Facts, not summaries.}

## Current State

{For each repo touched — one line per repo:}
| Repo | Branch | Status | Last Commit |
|------|--------|--------|-------------|

## The Plan

{If Step 1.2 emitted `status: "ok"`, include the parseable block below filled in from the JSON. /onboard and /pickup parse this block to decide whether to resume the plan. If `status: "no_plan"`, omit this section entirely.}

<!-- plan-state-start -->
```yaml
plan_path: {from JSON plan_path}
plan_slug: {from JSON plan_slug}
plan_state: {active | completed}
total_steps: {from JSON}
completed_steps: {from JSON}
remaining_steps: {from JSON}
archive_path: {from the Step 5.4B archive call result, or omit if archive failed}
```
<!-- plan-state-end -->

{Optional human-readable checklist or narrative below the block — agents can read it, but machines read the block above.}

## What To Do Next

{Specific, actionable next steps with file paths. Not "continue the plan."}

## Key Decisions Made This Session

{Decisions not written down elsewhere. User preferences, approach choices, discoveries.}

## Open Threads

{Discussed but not implemented. Questions raised but not answered.}

## Lessons Learned

{Aletheia three-column format. 0 rows fine for routine sessions. Don't pad.}

| Date | Lesson | Rule/Action |
|:-----|:-------|:------------|
| {YYYY-MM-DD} | **{What happened.}** {The specifics — error messages, user feedback, surprising behavior.} | **{The rule I now follow.}** {How to prevent or replicate this.} |

## Session Summary

- **Session:** {SESSION_NAME or "unnamed"}
- **Duration:** {approximate duration}
- **Issues touched:** {comma-separated, e.g., "unleashed #84, #86, dotfiles #31"}
- **Lessons:** {count} captured

## Hygiene Report

{For each repo scanned in Step 1 item 6, show actual git output. Only include repos where something was found. Skip repos where everything is clean. This is an EXPOSURE REPORT — never fix or delete anything here.}

### {REPO_NAME}
| Check | Status |
|-------|--------|
| Stale local branches | {list or "none"} |
| Remote-gone branches | {list or "none"} |
| Worktrees | {list beyond main, or "only main"} |
| Stashes | {count and description, or "none"} |
| Uncommitted | {count, or "clean"} |

{If all scanned repos are clean, write: "All repos clean — no hygiene issues found."}

## Files to Read First

{Ordered list of files the next session should read to get oriented:}
1. `{plan file}` — the master plan
2. `{key file}` — because...
3. ...
```

### Step 2B: Memory Line Check

Check the current project's MEMORY.md line count:
```bash
wc -l C:/Users/mcwiz/.claude/projects/*/memory/MEMORY.md 2>/dev/null | sort -rn | head -5
```
If any MEMORY.md exceeds 150 lines, warn: "MEMORY.md at {N} lines (200 auto-loaded limit). Consider extracting reference material to standalone files."

### Step 3: Verify Completeness

Before outputting, self-check:
- [ ] Every repo touched is listed with its status
- [ ] Every issue opened/closed is mentioned with number and repo
- [ ] The "what to do next" section is specific enough that a fresh agent could start working immediately
- [ ] No hallucinated file paths — only reference files you actually read or wrote
- [ ] Key user preferences are captured (not just technical state)
- [ ] Lessons reflected honestly — 0 rows is fine, but "nothing happened" when things DID happen is not
- [ ] Hygiene shows actual git output, not summaries or guesses

### Step 4: Output

Print the handoff prompt directly to the user. Surround it with a clear delimiter so they know exactly what to copy:

```
---BEGIN HANDOFF PROMPT---

{the prompt}

---END HANDOFF PROMPT---
```

### Step 5: Persist to Handoff Log

After outputting the prompt to screen, persist it to the repo's handoff log so it survives clipboard loss:

1. **Determine repo root:** `git rev-parse --show-toplevel`
2. **Ensure `data/` directory exists** in the repo root (create if missing)
3. **Ensure gitignore coverage:** Run `git check-ignore -q data/handoff-log.md`. If NOT ignored, append `data/handoff-log.md` to the repo's `.gitignore` file (create it if missing). Tell the user: "Added `data/handoff-log.md` to .gitignore."
4. **Fresh timestamp** — Run `date '+%Y-%m-%d %H:%M:%S'` NOW. Do NOT reuse the Step 1 timestamp — after long sessions or context compaction, your memory of it drifts. Use this exact output for the `## Handoff` header below.
5. **Append entry** to `{repo_root}/data/handoff-log.md` using the fresh timestamp from step 4:

```markdown
---
## Handoff — {FRESH_TIMESTAMP}
<!-- handoff-start -->
{the full handoff prompt text from Step 4}
<!-- handoff-end -->
---
```

6. **Confirm to user:** "Handoff logged to `{path}`"

7. **Archive the active plan (deterministic):** If the Step 1.2 JSON had `status: "ok"`, run:
   ```bash
   python /c/Users/mcwiz/Projects/unleashed/src/plan_archiver.py archive --slug {plan_slug}
   ```
   If `plan_state == "completed"` in that JSON, add `--mark-completed` to the command. The archiver is idempotent — if the live plan matches the newest archive, it emits `status: "already_archived"` and no-ops. Skip this step if Step 1.2 returned `status: "no_plan"` or `status: "error"`.

   After archiving succeeds, update the `archive_path` field in the `<!-- plan-state-start -->` block in `data/handoff-log.md` with the path from the archiver's JSON output. This is what /onboard and /pickup read to resume or ignore the plan.

### Step 5B: Persist Lessons Learned

Lessons learned are institutional knowledge — they get committed, unlike the handoff log.

1. **Per-repo file:** `{repo_root}/docs/lessons-learned.md`
   - If missing, create with this header:
     ```markdown
     # Lessons Learned — {REPO_NAME}

     | Date | Lesson | Rule/Action |
     |:-----|:-------|:------------|
     ```
   - Append each lesson row from the handoff's Lessons Learned section.
   - If there are 0 lessons this session, skip — don't touch the file.

2. **Global index:** `C:\Users\mcwiz\Projects\dispatch\lessons-learned-index.md`
   - If missing, create with this header:
     ```markdown
     # Lessons Learned — Global Index

     Cross-repo index for blog/newsletter mining. One line per lesson.

     | Date | Repo | Lesson (one-line) |
     |:-----|:-----|:------------------|
     ```
   - Append one line per lesson: `| {date} | {repo_name} | {one-line summary} |`
   - The summary is the bold portion of the Lesson column (the "what happened" part).

3. **Do NOT commit these files during handoff.** The next session or a manual commit handles that. Handoff just appends.

### Step 5C: Append Session Log

Brief backward-looking record of the session. One entry per session.

1. **File:** `{repo_root}/docs/session-logs/{YYYY-MM-DD}.md`
   - If the `docs/session-logs/` directory doesn't exist, create it.
   - If the file doesn't exist, create it with a header: `# Session Log — {YYYY-MM-DD}`
   - Append:
     ```markdown

     ## {HH:MM} — {SESSION_NAME or "unnamed"}

     - **Duration:** {approximate}
     - **Issues:** {comma-separated list, e.g., "#84, #86"}
     - **Lessons:** {count} captured
     - **Next:** {one-line summary of what to do next}
     ```

2. **Do NOT commit.** Same as 5B — handoff appends, next session commits.

### Step 6: Spawn New Unleashed Session

**MANDATORY unless `--reboot` is in `$ARGUMENTS`.** The CLAUDE.md "Skill Instructions Are Explicit Authorization" rule applies. Do NOT skip this step for any reason not listed in these instructions. Do NOT invent conditions (e.g., "not running under unleashed", "environment variable empty") to justify skipping.

**IF `$ARGUMENTS` contains `--reboot`:** Skip this step entirely. Tell user: "Handoff saved. Skipping new session (--reboot). Ready to reboot."

**OTHERWISE:**

After persisting the handoff log, spawn a new `unleashed-alpha` session. Auto-onboard (default in v30+) detects the fresh handoff and auto-picks up the context. **Always spawn the alpha tier**, not production — this ensures every post-handoff session lands on the current-iteration build so new fixes get exercised. Users who need production can still invoke `unleashed` manually.

1. **Get repo root Windows path:** Convert the git toplevel path to a Windows path with backslashes (e.g. `C:\Users\mcwiz\Projects\AssemblyZero`)
2. **Get repo name uppercased** for the window title (e.g. `ASSEMBLYZERO`)
3. **Get Unix-style repo path** for the cd command (e.g. `/c/Users/mcwiz/Projects/AssemblyZero`)
4. **Spawn via Python** (MSYS2 mangles paths — must go through cmd.exe):
   ```bash
   python -c "import subprocess; subprocess.Popen(r'wt.exe -w new nt --title \"{REPO_NAME}\" --suppressApplicationTitle -d \"{WINDOWS_PATH}\" \"C:\Program Files\Git\usr\bin\bash.exe\" -l -c \"cd {UNIX_PATH} && unleashed-alpha\"', shell=True)"
   ```
   This opens a new Windows Terminal window, cd's to the target repo, and runs `unleashed-alpha`. The wrapper auto-injects `/onboard` after Claude's first prompt. Onboard detects the fresh handoff (< 10 min old) and auto-imports it. Zero manual steps.
5. **Tell user:** "New unleashed-alpha session spawning in {REPO_NAME} with auto-onboard."

## Rules

- **Be concrete, not summary.** "Updated 3 files" is useless. "Updated `Architecture.md`, `Version-History.md`, `Version-Promotions.md`" is useful.
- **Include commit SHAs.** The next agent can `git show` them to understand changes.
- **Plan state is machine-read.** The `<!-- plan-state-start -->` YAML block in `## The Plan` is the source of truth for /onboard and /pickup. Fill it from `plan_archiver.py status` output — do NOT reconstruct it from memory. Archive the plan in Step 5.7 so the next session knows whether to resume it.
- **Don't pad.** If nothing happened in a section, skip it. A shorter, accurate prompt beats a longer, padded one.
- **User preferences go in "Key Decisions."** Things like "user doesn't want numbered options" or "always use poetry run python" — if you learned it this session and it's not in CLAUDE.md or MEMORY.md, capture it here.
- **Always persist** — the log survives even if the clipboard is lost.
- **Always spawn without flags** — v30+ auto-onboard detects the fresh handoff and auto-imports it. No `--pickup` needed. Exception: `--reboot` skips the spawn entirely.
- **Lessons are institutional memory.** One real lesson is worth more than a perfect handoff. If something surprised you, cost time, or changed your approach — write it down. 0 rows is fine for routine sessions; padding is not.
- **Hygiene is exposure, not action.** NEVER delete branches, stashes, worktrees, or files during handoff. Report what exists so the user can rescue work. `/cleanup` is for destructive operations.
- **Session log is backward-looking, handoff prompt is forward-looking.** The session log records what happened (for mining later). The handoff prompt tells the next agent what to do. Don't conflate them.
