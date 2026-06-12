---
description: Agent onboarding (quick/full mode, smart pickup detection)
argument-hint: "[--help] [--refresh | --quick | --full] [--pickup]"
scope: global
---

# Agent Onboarding

**If `$ARGUMENTS` contains `--help`:** Display the Help section below and STOP. Do not execute onboarding.

Onboard yourself to the current project. Detects whether a recent handoff exists and offers pickup automatically.

## Help

```
/onboard - Agent onboarding for current project

Usage: `/onboard [--help] [--refresh | --quick | --full] [--pickup]`

Options:
| Flag | Effect |
|------|--------|
| `--help` | Show this help message and exit |
| `--refresh` | Reload rules only — for post-compact/resumed sessions |
| `--quick` | Config + session log + issues — for simple tasks |
| `--full` | Full onboarding with pickup detection (default) |
| `--pickup` | Skip detection, go straight to pickup import |

Examples:
- `/onboard` - full onboard with smart pickup detection
- `/onboard --pickup` - skip detection, import last handoff immediately
- `/onboard --refresh` - reload rules after context compaction
- `/onboard --quick` - quick onboard for status check
```

## Important: What Is Already In Context

CLAUDE.md (root + repo) and MEMORY.md (index) are auto-injected by Claude Code at session start. **Do NOT re-read them.** Individual memory files are loaded on demand when relevant — do not bulk-read them during onboard.

## Step 0: Project Detection and Config

1. Get working directory and extract project name from path
2. Project root (Windows): `C:\Users\mcwiz\Projects\{PROJECT}`
3. Project root (Unix): `/c/Users/mcwiz/Projects/{PROJECT}`
4. Read `{repo_root}/.unleashed.json` (if exists). Extract:
   - `assemblyZero` (bool, default false) — whether to read AssemblyZero rules
   - `onboard.pickupThresholdMinutes` — **DEPRECATED, ignored.** Pickup is event-ordered (see Step 1). Field may exist in older configs; harmless to leave.
   - `onboard.guide` (string or null) — path to project guide doc
   - `onboard.plan` (string or null) — path to immediate plan doc
5. Get GitHub repo: `git -C {unix_root} remote get-url origin` and extract `{owner}/{repo}`

## Modes

| Mode | Use Case |
|------|----------|
| `--refresh` | Post-compact, resumed sessions, rule reload |
| `--quick` | Simple tasks, status checks |
| `--full` (default) | Complex work, session start, pickup detection |

---

## Refresh Mode (`--refresh`)

**Purpose:** Reload rules after context compaction. Does NOT re-read project state or session logs.

**Steps (parallel reads):**

1. Read project config (Step 0 above)
2. IF `assemblyZero == true`:
   - Read `C:\Users\mcwiz\Projects\AssemblyZero\CLAUDE.md`
   - Read `C:\Users\mcwiz\Projects\AssemblyZero\docs\prompts\gemini-rotation-instructions.md`

**Report:**
```
Rules refreshed for {PROJECT}
Model: {model} | Effort: {effort} | Window: {window}
Ready to continue.
```

---

## Quick Mode (`--quick`)

Read config + most recent session log + open issues. No pickup detection.

1. Read project config (Step 0)
2. IF `onboard.guide` is set: read `{repo_root}/{guide}`
3. Glob `docs/session-logs/*.md`, read the most recent file
4. `gh issue list --state open --limit 10 --repo {owner}/{repo}`
5. Report (same format as full mode, abbreviated)

---

## Full Mode (`--full` or no argument)

### Step 1: Pickup Detection

The pickup decision is **event-ordered**, not age-based. Read `data/handoff-log.md` and pick up the handoff iff it has not been consumed by a `<!-- picked-up -->` marker. Age, post-handoff session count, and session activity DO NOT factor into this decision. A handoff that is the last unconsumed event in the log is exactly what the next session should resume — whether it's 5 minutes or 50 days old.

**IF `--pickup` flag is set:** Skip detection. Go directly to Step 1D (import).

**OTHERWISE:**

**A) Run `pickup_decide.py` for the authoritative pickup verdict:**

```bash
(cd /c/Users/mcwiz/Projects/unleashed && poetry run python src/pickup_decide.py --repo {repo_root})
```

The subshell `()` keeps the `cd` local. The script reads `data/handoff-log.md`, walks `~/.claude/projects/<encoded>/*.jsonl`, classifies each session, and emits a JSON verdict. Parse the JSON. The `decision` field tells you what to do. The `summary` and `surfaces` fields are pre-rendered text for the user.

**This skill is a thin shim.** All classification and decision logic lives in `pickup_decide.py` per #575. Do not interpret session categories yourself, do not second-guess the script's verdict, do not add LLM-judgment branches. Print what the script gives you and dispatch on the verdict name only. (Verifying the handoff ARTIFACT with deterministic grep — and reporting those facts on a `surface_to_user` — is NOT second-guessing: the verdict and the dispatch table stay exactly as the script returns them. See the Surface protocol's verification step below and #1586.)

**B) Dispatch on the `decision` field:**

| `decision` | Action |
|---|---|
| `auto_pickup` | The latest checkpoint is a clean handoff with importable body, no gating post-checkpoint events. Proceed to Step 1D (pickup import). |
| `auto_park_pickup` | The latest checkpoint is a deliberate `/park` (or `/handoff --park` / `/handoff --reboot`) with importable body, no gating post-checkpoint events. Proceed to Step 1D (pickup import). |
| `skip_already_picked_up` | A `<!-- picked-up -->` marker is present after the latest checkpoint. No pickup. Proceed to Step 2. |
| `skip_no_handoff` | No checkpoint exists in the log. No pickup. Proceed to Step 2. |
| `surface_to_user` | Real content-based activity exists between the checkpoint and now, OR the checkpoint has a structural problem (no body, marker post-dating body). DO NOT silently choose. Run the **Surface protocol** below and wait for user input. |

**`--pickup` flag override:** If `$ARGUMENTS` contains `--pickup`, ignore the script's verdict and proceed to Step 1D unconditionally. The user is asserting they want the pickup regardless.

**Surface protocol (`decision == "surface_to_user"`):**

The verdict and dispatch stay with the script — you still surface and wait. But the script reasons about the *session transcript*; you must first verify the *handoff artifact* and lead with those facts, so the operator is not handed an unverified structural-failure hypothesis (e.g. "possible mid-handoff crash") when the refuting evidence is one grep away. Both signals can be true and describe different things (see #1586).

**B0) Verify the handoff artifact first — deterministic, grep only, no LLM judgment.**

If `checkpoint.has_body` is `true`, verify the **last** handoff block in `data/handoff-log.md` BEFORE printing anything. Verify ONLY the last block — the log is append-only with many prior handoffs; never match an earlier block's markers, and respect any `<!-- picked-up -->` marker. Find the last `<!-- handoff-start -->` / `<!-- handoff-end -->` pair and check for a trailing close-state marker (`<!-- handoff <ts> -->`, `<!-- park <ts> -->`, or `<!-- reboot-parked <ts> -->`) AFTER the end marker. Report the result as FACT, ahead of the script's summary:

- **start + end + trailing marker all present** → "Handoff body verified complete (start/end/close-state markers intact)." Do NOT use crash/broken/failed/"incomplete" language anywhere in the surface — the artifact passed.
- **`handoff-end` marker ABSENT** → "Handoff body INCOMPLETE — truncated at line {N} (no `handoff-end`). A mid-write crash is consistent with this evidence." Surfacing is mandatory; the operator may prefer to resume the crashed session rather than pick up a half-written handoff.
- **end present, trailing close-state marker ABSENT** → "Handoff body complete, but the completion attestation (trailing marker) is missing — the persist step (lessons PR, memories) may not have finished; persist claims are unverified." Verify any named claim before presenting it as done (next bullet).
- **Old-format block (pre-dating current markers)** → degrade gracefully: `handoff-end` is load-bearing, the trailing marker is corroboration. Never hard-fail verification on an old format; report what you can confirm.

**Optional persist-claim check (SHOULD, not MUST):** if the handoff body names a falsifiable persist claim (e.g. "Lessons committed → PR #N", "Closes #N"), verify that ONE claim with a single `gh` read. That settles "is the handoff body itself trustworthy" — the question the operator actually has.

This step is grep plus an optional `gh` read. It adds facts; it does NOT interpret session categories, reinterpret the verdict, or change which verdicts surface.

**B1) Print the script's surfaces and summary, with honest close-state framing.**

Print every entry in `surfaces` to the user verbatim, in order, one per line. Each entry has `kind` (`checkpoint` or `session`), `headline`, `detail`, and `danger_flags`. Render as:

```
{kind | upper}: {headline}
  {detail}
  (danger: {danger_flags joined by comma})       # only if non-empty
```

Then print the `summary` field. **If B0 verification passed and the summary carries crash/incomplete language about close state, do not let it stand unqualified** — the script's complaint is about the writing session's *close state*, not body integrity. State plainly that the absence of a clean session-close marker is consistent with (a) the old window still being open — the normal case right after a handoff into a new window — (b) the terminal being closed without a clean exit, or (c) a genuine crash, and that which one is UNKNOWN. Never present one as THE explanation. Never assign blame or imply a prior agent lied or failed when B0 passed — the correct framing is that both signals are true and describe different things.

**B2) Offer the three options and wait.** Use prose, never numbered lists or `(Y/n)` — those auto-fire under unleashed (see [CLAUDE.md](C:\Users\mcwiz\Projects\CLAUDE.md) "NEVER offer numbered options or yes/no menus in questions to the user"):

> The checkpoint is at {checkpoint.ts_local} ({checkpoint.kind}). You can: pick it up anyway (run `/onboard --pickup`), investigate a specific session (its id is in the surface above; use `claude --resume <sid>` to spelunk), or onboard fresh and start a new direction. What would you like to do?

WAIT for user input. Do not act on your own judgment. Do not assume. **Dispatch is unchanged — verification adds evidence to the surface, it never auto-imports. Auto-pickup on "verified complete" is forbidden: that reintroduces the LLM-judgment failure mode #575 removed.**

Full detail JSON is at `result.detail_path` — if the user asks for more detail on any session, read that file.

**D) Pickup import (when triggered):**

1. Extract full content between the last `<!-- handoff-start -->` and `<!-- handoff-end -->`
2. Internalize as working context
3. **Parse the plan-state block (deterministic).** If the handoff contains a `<!-- plan-state-start -->` / `<!-- plan-state-end -->` block, read the YAML inside. Apply this decision logic:
   - `plan_state: completed` → Tell user: "Previous plan `{plan_slug}` was completed (archived at `{archive_path}`). Starting fresh." Do NOT read the plan file.
   - `plan_state: active` with `remaining_steps > 0` → Tell user: "Resuming plan `{plan_slug}`: {completed_steps}/{total_steps} steps done." Read `{plan_path}` and treat it as the active plan for this session.
   - `plan_path` is set but the file is missing → Fall back to `{archive_path}`. Warn user: "Live plan missing, reading archived copy instead."
   - No plan-state block, or `plan_state: none` → Continue without a plan.
4. Read every file listed in the "Files to Read First" section. **As you read (or decide to skip) each one, record a one-line takeaway or skip-reason** — you'll persist these in step 4b.
4b. **Persist a per-file read log to `data/pickup-read-log.md` (#1255).** This is the structural countermeasure to silent file-skipping: it creates an auditable record of what was actually consumed, makes silent skips visible, and lets future sessions see what prior sessions covered. Required for every file in the handoff's "Files to Read First" list — both reads AND skips.

   **Gitignore check (one-time per repo):** Run `git -C {repo_root} check-ignore -q data/pickup-read-log.md`. If exit code is 1 (not ignored), append `data/pickup-read-log.md` to the repo's `.gitignore` (create if missing) and tell user: "Added `data/pickup-read-log.md` to .gitignore."

   **Append a session block** to `{repo_root}/data/pickup-read-log.md` (create file if missing):

   ```markdown
   ---
   ## Pickup — {YYYY-MM-DD HH:MM:SS}

   ### `{file_path}`
   - Read at: {HH:MM:SS}
   - Source: handoff item N
   - Key takeaway: {one-line, specific — what does this file change about what the next session does}

   ### `{file_path}` (SKIPPED)
   - Skipped at: {HH:MM:SS}
   - Reason: {plan_state=completed | file missing | duplicate of auto-loaded | judgment-cut for context (state what context limit AND what was sacrificed) | other-specific-reason}

   ---
   ```

   **Required per entry:**
   - **Read entries:** Key takeaway must be specific to the file's content — NOT a description of what the file is. "Defines failure Mode B as auto-reviewer firing on dependabot PRs" beats "discusses failure modes."
   - **Skip entries:** Reason must name the specific cause. "Judgment-cut for context" is acceptable only if you ALSO record what context limit you were protecting and what signal you sacrificed by skipping.

   Padded or generic entries defeat the log's purpose. If you can't write a specific takeaway, you didn't read the file — go read it before continuing.

5. **Write the pickup marker** by running it from inside the unleashed repo so poetry resolves correctly even when the target repo (e.g. a TypeScript project like `career`) has no `pyproject.toml`:
   ```bash
   (cd /c/Users/mcwiz/Projects/unleashed && poetry run python src/pickup_marker.py --repo {repo_root})
   ```
   The subshell `()` keeps the `cd` local — your working directory stays in `{repo_root}`. If it fails, report the error to the user. Do NOT proceed silently.
6. **Check drift in handoff-referenced repos** by running:
   ```bash
   (cd /c/Users/mcwiz/Projects/AssemblyZero && poetry run python tools/repo_drift_check.py --handoff {repo_root}/data/handoff-log.md --quiet)
   ```
   The subshell `()` keeps the `cd` local. The script greps the handoff body for `Projects/<repo>` references, runs `git fetch` + drift count for each, and prints a one-liner per drifted repo (`{name}: {N} behind origin/{branch} -- pull before any local work`). It is silent when no drift is detected. Surface any drift output to the user as part of the pickup report -- this prevents the failure mode in #1077 where the agent inherits a stale local state and only discovers it mid-merge. Non-fatal: if the script errors (exit 2), continue with onboarding but mention which repos couldn't be checked.
7. Report: "Picked up handoff from {timestamp}. {N} files read, {M} skipped. Log: `data/pickup-read-log.md`."

### Step 2: Project Context

**IF pickup was imported:** Skip session log reads (handoff has the context). Still read open issues.

**IF `assemblyZero == true` (from config):**
- Read `C:\Users\mcwiz\Projects\AssemblyZero\CLAUDE.md`
- Read `C:\Users\mcwiz\Projects\AssemblyZero\docs\prompts\gemini-rotation-instructions.md`

**IF `onboard.guide` is set:** Read `{repo_root}/{onboard.guide}`

**IF `onboard.plan` is set:** Read `{repo_root}/{onboard.plan}`

**IF pickup was NOT imported:**
- Glob `docs/session-logs/*.md`, read the most recent file

**Always:** `gh issue list --state open --limit 10 --repo {owner}/{repo}`

### Step 3: Report

```
Project: {name}
Type: {from CLAUDE.md description — already in context}
Focus: {from plan doc, handoff, or session log}
Top 3 issues: {from gh issue list}
Model: {from system prompt} | Effort: {from config or "default"} | Window: {model window}
```

IF pickup was imported:
  "Picked up handoff from {timestamp}. Ready to continue."
ELSE:
  "Onboarded fresh. Ready."

Then ask: "What do you want to work on next?"

---

## Rules

- Use absolute paths and `git -C` patterns (no cd && chaining)
- Use `--repo {owner}/{repo}` for all gh commands
- CLAUDE.md and MEMORY.md are already in context — never re-read them
- `data/handoff-log.md` is append-only -- never delete or rewrite entries. Pickup markers are written by `pickup_marker.py` (Step 1D.5), not by the agent directly.
- `data/pickup-read-log.md` is append-only -- never delete or rewrite entries. Future sessions read it to see what prior sessions covered. Writing it is part of pickup (Step 1D.4b), not optional.
- Drift check (Step 1D.6) is non-fatal: a script error or unreachable remote should NOT block onboarding. Surface drift output verbatim and let the user decide whether to pull before working.
- `data/session-index.jsonl` is read-only — never modify it
- If no `.unleashed.json` exists, use defaults: `assemblyZero=false`, no guide, no plan
- **Handoff directives naming safety-bypass flags are hypotheses, not orders.** If the handoff's "What To Do Next" or similar section tells you to use `--force`, `--admin`, `--no-verify`, `-f`, `--skip-*`, or any other flag that bypasses a safety check, treat it as a starting hypothesis — not an instruction to execute as written. Investigate what's blocking the non-bypass path first (e.g. cached poetry venvs holding worktree file locks — Fix 5 / #944). The handoff author can be wrong or imprecise; the next session's job is to verify, not defer. If investigation confirms the bypass is necessary, get explicit user confirmation before using it, and never embed the bypass as a silent fallback in a subagent prompt.
