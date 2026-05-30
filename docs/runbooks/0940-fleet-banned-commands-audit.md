# Runbook 0940: adding a banned command + auditing the fleet

This runbook covers two scenarios that often go together:

1. **Adding a new banned command/pattern** to the universal `Projects/CLAUDE.md`.
2. **Auditing the fleet** (all `martymcenroe` repos) for instances of any banned pattern — whether newly added or pre-existing.

The trigger is usually the same: a script, skill, or workflow is found to codify a destructive pattern that the principle table in `CLAUDE.md` already named but the literal table didn't enforce. The fix is twofold — close the loophole in `CLAUDE.md`, then find every other place the loophole was already exploited.

## When to use this runbook

- The agent (or operator) finds a tool/skill that encodes a destructive pattern (`git restore .`, `--force`, etc.) inside its own logic.
- The agent's behavioral pattern shows a recurring rationalization-then-bypass cycle around a specific command and the principle alone isn't deterring it.
- An incident review concludes "the principle table covers this, but the literal table didn't; add it" — see, e.g., the 2026-05-27 incident note in `CLAUDE.md` and the 2026-05-29 `git restore .` finding in `dependabot_review.py`.
- A new banned pattern is being added and we need to know whether legacy code already does it.

## Part A — Adding a new banned command/pattern

### Step 1: Update the literal banned table

File: `C:\Users\mcwiz\Projects\CLAUDE.md` § "Banned commands (ALWAYS, no exceptions, no per-invocation approval)".

- Add a row to the markdown table. Format: `| <command/pattern> | <alternative the agent uses> |`.
- The alternative MUST be concrete. Vague alternatives ("be careful") have been demonstrably ignored.
- If a related pattern is already in the table (e.g., `git restore .` pairs with `git clean -fd` — wholesale wipe of tracked vs untracked), place the new row adjacent to maintain the conceptual pairing.
- In the row's alternative cell, briefly note when the row was added and which incident/finding triggered it. This is the "earned through repeated failure" trail; future agents reading the table benefit from knowing why each row exists.

### Step 2: Check the principle table

File: same. § "Destroying uncommitted state — the principle".

- If the new pattern is a specific instance of an existing principle row, no further principle-table edits needed. The literal-table row makes it enforceable; the principle continues to cover variants.
- If the new pattern is a NEW class of destruction the principle table doesn't yet cover, add a row to the principle table too.

### Step 3: Check the STOP-token list

File: same. § "Reading the Banned List (Earned Through Repeated Failure)" § "Operational rule for the agent".

- The list includes tokens like `--force`, `-D`, `--no-verify`, etc. — flags within commands.
- If the new pattern's distinctive token is missing AND it's a flag (not a standalone command), add it. `git restore` is the whole command, not a flag — handled by the literal table without touching the STOP-token list. `--ff-only`-class flags would go in the STOP-token list.

### Step 4: Audit the fleet (Part B below)

Adding the row prevents future occurrences. Auditing finds existing ones.

## Part B — Auditing the fleet for a banned pattern

### Step 0: Decide scope

- **Single new pattern**: audit just that pattern.
- **All banned patterns**: a periodic check. Recommended every few months and after any incident.

Audits scoped to ALL patterns are cheaper per-pattern than repeating single-pattern audits, because the corpus-walk is the expensive part.

### Step 1: Define patterns

List every literal-table command AND every principle-table operation. Assign each an ID (B1, B2, ...) for cross-reference in the report. Note variants (e.g., `git push --force` has the short form `git push -f`; both need separate search strings).

For the canonical pattern list as of 2026-05-29, see `docs/audits/0900-banned-commands-fleet-audit-2026-05-29.md` "Patterns audited" table — use that as the starting point and add new rows as patterns get added to CLAUDE.md.

### Step 2: Enumerate the fleet

```bash
gh repo list martymcenroe --limit 200 --json name,nameWithOwner,isArchived,isFork
```

Skip archived. Forks usually skip too (they're upstream code we don't write); flag the rare fork where we've added meaningful tooling.

### Step 3: Choose search method per repo

**Per repo, check whether a local clone exists** at `C:\Users\mcwiz\Projects\<repo-short-name>\`.

- **Has clone**: prefer local `git grep`. Full context, fast, ignores `.gitignore`d content automatically.
- **No clone**: use `gh search code 'pattern' --owner martymcenroe --limit 100` (note: gh search is token-based, not regex — narrow with `repo:<owner>/<name>` for noisy patterns).

Don't clone repos just for the audit unless a finding warrants deep inspection. The cost-benefit isn't worth it for a one-time pass.

### Step 4: Search

For each pattern × each repo, run the appropriate search. Capture every hit. Don't filter at search time — filter at triage.

File types to include:
- `*.py`, `*.sh`, `*.ps1`, `*.bat`, `*.cmd`
- `*.yml`, `*.yaml` (workflows)
- `*.md` (skills, slash commands, runbooks, README)
- `Dockerfile`, `Makefile`, `justfile`, `Taskfile.yml`
- `.husky/*`, `.pre-commit-config.yaml`, `lefthook.yml`
- `.claude/skills/*`, `.claude/commands/*`

### Step 5: Triage each hit

Classify into one of:

| Class | Description | Fix needed |
|-------|-------------|------------|
| **CODE** | Pattern appears in active script logic (subprocess args, shell commands, workflow `run:`, etc.) | YES |
| **DOC** | Pattern appears in documentation as a warning, example, or anti-pattern | NO; consider cross-link to `CLAUDE.md` |
| **COMMENT** | Pattern appears in code comments referencing the banned command | NO; verify the comment isn't actually the docstring of a wrapper that DOES execute it |
| **TEST_FIXTURE** | Pattern appears in tests intentionally exercising the failure/forbidden path | REVIEW; ensure tests reject the pattern in production code |
| **GENERATED** | Pattern appears in lockfiles, build output, transcripts, etc. | NO |
| **FALSE_POSITIVE** | Substring match that isn't the dangerous pattern (e.g., `git restore --staged` is fine) | NO |

When uncertain, read a 20-line window around the hit. Better to over-classify as CODE and downgrade in remediation than under-classify and miss a real codified destruction.

### Step 6: Append findings to a report file

Use the audit report template at `docs/audits/0900-banned-commands-fleet-audit-2026-05-29.md` (or copy its structure to a new dated file for future audits).

**Format per finding:**
```
- **[<pattern-id>] [<class>]** `<repo>/<path>:<line>` — `<excerpt>` — note: <context>
```

**Critical: write incrementally to disk.** Append each finding as you find it, not in a batch at the end. The audit can take hours; a power event or crash should leave a partial-but-usable report.

If using the Edit tool from an agent, use the placeholder-replacement pattern:
- Initial replace of `_no findings yet_` with `<!-- next-append-here -->`.
- Each subsequent append: replace `<!-- next-append-here -->` with `<finding>\n\n<!-- next-append-here -->`.

### Step 7: Summarize

When findings stream is complete, fill in the report's `## Summary` section:
- Total findings by class
- Top repos by CODE-class finding count
- Top patterns by CODE-class finding count
- Surprises and recommended prioritization

## Part C — Remediation grouping

The remediation phase is the operator's call to direct. This runbook documents the recommended structure:

- **Group fixes by tool class, not by repo.** If `dependabot_review.py`, `fleet_delete_pr_sentinel.py`, and `cleanup_dispatch.py` all share an internal SDK that wraps git, fix the SDK. Otherwise per-script.
- **One PR per logical unit.** A 16-repo broadcast PR (find/replace) is harder to review than 16 small PRs in scripts that have nothing in common — but easier than 16 PRs that all do the same change.
- **Reference the CLAUDE.md row in every fix PR body.** "Per `Projects/CLAUDE.md` banned table (row added <date>), this script's use of `git restore .` is removed."
- **Add a regression test where possible.** If the script has any tests, add one that asserts the banned pattern isn't invoked.

## Part D — Lint / hook to prevent regression

After remediating, add a lint rule that flags any new occurrence of the pattern in tooling files. Options:

- **Pre-commit hook (per-repo)** via `.pre-commit-config.yaml`. Pattern: a custom `language: pygrep` or `language: script` entry that regex-matches the banned commands in tracked files under `tools/`, `.claude/`, etc.
- **CI lint job** in the workflow that catches new instances on PRs that the pre-commit doesn't.
- **Fleet-wide rollout**: do this as a separate runbook follow-up; rolling pre-commit changes across 64 repos is its own audit and rollout, not in scope here.

## Common gotchas

### Subagents don't auto-load `CLAUDE.md`

A subagent dispatched to do the audit will NOT have the principle/rationale context the operator's main agent has. When briefing a subagent:

- State the patterns as forbidden explicitly in the brief.
- Specify READ-ONLY constraint with no flexibility ("don't fix anything, even if it looks obviously wrong").
- Don't assume the subagent understands why these patterns are banned. It will treat them as text patterns to grep for; that's fine — the operator handles remediation.

### "It's already broken; the next run will fail anyway" rationalization

Pattern: the agent finds a script that uses `git restore .` and notes "it's broken anyway; let me 'fix' it." That's still self-authorization to destroy state and modify a script outside the audit's scope. The audit's job is to find. The fix is the operator's authorization.

### Comments as cover for code

Watch for code that "warns" against the pattern via a docstring but actually invokes it nearby. The comment text doesn't make the underlying call safe. Always check the executable path.

### Workflows that runs git via composite actions

A workflow with `uses: some/composite-action` won't show `git restore .` in the workflow file itself — but the composite action's source might. Audit composite actions used by `martymcenroe` workflows as well (if they're under `martymcenroe` or another org we control).

## Reference

- `Projects/CLAUDE.md` § "Banned commands (ALWAYS)"
- `Projects/CLAUDE.md` § "Destroying uncommitted state — the principle"
- `Projects/CLAUDE.md` § "Reading the Banned List (Earned Through Repeated Failure)"
- `docs/audits/0900-banned-commands-fleet-audit-2026-05-29.md` — first run of this audit
- `feedback_destructive_flag_scrutiny.md` (agent memory) — the recurring rationalization pattern this runbook tries to break
- `feedback_worktree_content_check.md` (agent memory) — 2026-05-27 incident, same shape as the script-level findings this runbook surfaces
