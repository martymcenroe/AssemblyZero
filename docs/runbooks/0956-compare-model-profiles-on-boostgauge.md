# 0956 - Compare model profiles on boostgauge

**Issue:** #3566, under umbrella #3562. **Runs:** the operator, from the AssemblyZero checkout, in bash.

A *profile* is a TOML file that says which model answers every seat of the pipeline (`assemblyzero/profiles/`: `gemini.toml`, the default; `claude.toml`, the pre-2026-09-24 baseline; `mock.toml`, for rehearsals). boostgauge's rolls are idempotent (standard 0027), which means rerunnable, not identical. The second profile's roll reuses an LLD and spec already settled under the first, because settlement does not hash the profile, and it builds on an attempt branch that already carries the first roll's merged work. Read the comparison with that in mind. This runbook is the sequence, and what a new model costs to audition.

## What it spends

Every roll spends the credits of the vendor its profile names: Antigravity credits for `gemini`, Anthropic subscription usage for `claude`. The comparison itself reads files and calls no model. Do not use `--models mock` as a rehearsal: it swaps the models, not the pipeline's mock mode, so the roll still cuts branches and opens pull requests in boostgauge.

## The sequence

### 1. Pick the issue set

Use issues the answer-key audit covers where you can (`docs/audits/0907-answer-key-audit-boostgauge-2026-09-03.md` names #2, #4, #41, #332 and others), so the table can say how many are in the key. Use the same issues, in the same order, for every profile.

### 2. Roll under the first profile, from scratch

`--fresh` resets each issue before it rolls. The reset closes the issue's open PRs that come from its own pipeline branches (a PR somebody made by hand that names the issue is listed and left open), deletes its pipeline branches locally and on origin, removes its worktrees, and reopens the issue. Nothing it removes is lost: a branch tip is first proven to be on the base branch, or kept under a `graveyard/` branch (pushed to origin for a branch that is on origin) (#4215); a clean worktree's ignored files, which can hold the run's lineage, are copied to `data/speedrun/reset-artifacts/issue-N/worktree-ignored/` and compared with their sources before it is removed, and a failed copy keeps the worktree (#4219); the displaced lineage and the LLD and spec working copies go under `data/speedrun/reset-artifacts/` too (standard 0027). If a tip cannot be kept, the branch stays, you are alerted, and the reset stops. A reset refuses while another roll of the issue is running, whichever session started it (#4217).

Because the reset is destructive, `--fresh` alone only prints what it would close, delete and remove, then the phrase that authorizes it, and stops: no write, no roll (#4221). Read that plan first.

```
poetry run python tools/speedrun_roll.py --repo /c/Users/mcwiz/Projects/boostgauge --issue 2 --issue 4 --models gemini --fresh
```

To carry it out, add `--execute`, and type the phrase it prints, naming the repository and every `--issue`, on the console you launched from. It is asked before any `--detach`, because the detached roll has no console to answer; a detached roll that was not confirmed refuses instead of waiting. Anything else typed, or no console, changes nothing and exits 91.

```
poetry run python tools/speedrun_roll.py --repo /c/Users/mcwiz/Projects/boostgauge --issue 2 --issue 4 --models gemini --fresh --execute
```

Without `--fresh`, a relaunch resumes, and a resume keeps the profile the issue was first rolled under. Every run's events log opens with `START ... profile=gemini`, and every convergence row and every recorded call names the profile.

### 3. Roll under the second profile, from scratch

This roll starts nested Claude sessions, so only the operator runs it. While his Claude spend lock is on, it is refused at launch with exit 91, before any reset or spend.

```
poetry run python tools/speedrun_roll.py --repo /c/Users/mcwiz/Projects/boostgauge --issue 2 --issue 4 --models claude --fresh --execute
```

Run it without `--execute` first to read the plan, as in step 2. Leaving out `--fresh` here is refused rather than mixed. When step 2 left resumable state, the roll prints `REFUSED #2: its resumable state was rolled under model profile 'gemini', and this launch asks for 'claude'` and stops with exit 93. When step 2 succeeded, the launch stops earlier, at `ALREADY ROLLED TO SUCCESS ON THIS ARC`, and asks for a typed redraw phrase or `--redraw-completed`. Neither refusal is free for every issue. For boostgauge issues 331 and 332, which carry a visual gate, the launch spends one model call first, under the launcher's default profile. And the launch's sweep, janitor and binding-doc sync can push before either refusal.

### 4. Compare

```
poetry run python tools/compare_profiles.py --repo /c/Users/mcwiz/Projects/boostgauge --profiles gemini,claude
```

It prints one row per profile and writes the same table to `boostgauge/data/speedrun/comparisons/<timestamp>.md`. Each row counts every run ever recorded under that profile, archived runs included, not only the issues of steps 2 and 3 (#4220).

### 5. Read the table

| Column | What to look for |
|---|---|
| issues landed | the headline: of the issues rolled, how many reached a passed terminal |
| verdicts | APPROVED and BLOCKED counts from the review seats; a profile whose reviewer never blocks is not a better profile |
| revisions | mean redrafts per stage; high numbers mean the drafter and reviewer disagree, or the drafter cannot follow review |
| calls per seat | where the spend went |
| wall time per stage | where the time went |
| failures by node | where runs died, by node |
| answer key | how many of the rolled issues the answer-key audit covers; the audit scores gates, not rolls, so this is coverage, not a score |

## Auditioning a new model

One profile file and one roll. Copy `assemblyzero/profiles/gemini.toml` to `boostgauge/.assemblyzero/new-model.toml` and pass it by path, as below. Never name the copy `boostgauge/.assemblyzero/models.toml`: that file becomes boostgauge's profile for every later roll that passes no `--models`.

```
poetry run python tools/speedrun_roll.py --repo /c/Users/mcwiz/Projects/boostgauge --issue 2 --issue 4 --models /c/Users/mcwiz/Projects/boostgauge/.assemblyzero/new-model.toml --fresh --execute
```

Then compare it against the profile it would replace. A mixture is the same: a profile whose `[defaults]` names one vendor and whose `[seats."<name>"]` tables name another for the seats that differ. The seat names are the keys of `SEATS` in `assemblyzero/core/seats.py`.

A profile that names a forbidden model (`FORBIDDEN_MODELS`), a seat that does not exist, or a spec with no `provider:` prefix is refused when the roll starts, naming the line to fix, before anything is spent. Two mistakes are not caught at start: a Gemini alias that is not a key of `GeminiProvider.MODEL_MAP` (`assemblyzero/core/llm_provider.py`), such as a full model id, and any `anthropic:` spec. Each fails the first time its seat is used, after the `--fresh` reset has run and earlier seats have spent. Use only the Gemini aliases in `MODEL_MAP`.
