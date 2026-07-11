---
description: Inscribe names into the Well of Names (Kastalia) — the fleet's mythological-naming store
allowed-tools: Bash, Read, Edit, Write, Glob
scope: global
---

# Rista — the pen of the Well of Names

`rista` (Old Norse *rísta*, "to carve runes"; Younger Futhark **ᚱᛁᛋᛏᛅ**) inscribes
naming material into the fleet's **Well of Names**, which is itself named
**Kastalia** (`dispatch/ideas/the-well-of-names.md`, on dispatch `main`). It is
the `/quote`-analog for names: where `/quote` memorializes Discworld wisdom to
Claude's World, `/rista` carves a drawn name — or a raw term — into the well so
no future naming starts from a dry bucket or collides with a name already on the
line.

This skill **replaces** the old universal-CLAUDE.md hand-commit instruction for
naming discussions. When a mythological name is discussed, run `/rista`.

> Adopted into the canonical skills source 2026-07-11 (previously machine-local
> only) with the landing sequence wired to the shared PR-lander.

## Doctrine (non-negotiable)

- **Native script always.** Greek in Greek (Κασταλία), Norse in runes (Younger
  Futhark), Hebrew in Hebrew (דממה) — native form **plus** transliteration in
  every entry. Do not invent rune/script spellings from memory beyond trivial
  transliteration; verify first.
- **Append-only.** Never rewrite an existing entry except to annotate a dedup.
  The well is a record of what was set down as much as what was chosen.
- **Every name keeps its losers.** An entry records the chosen name AND every
  candidate set back down, each with its reasoning and state (in service /
  drawn / set back down / reserve bucket). The set-down names are half the value.
- **Isolation.** NEVER edit the operator's live `dispatch` checkout — it
  routinely carries uncommitted work. All edits happen in an isolated worktree.

## Modes

**No arguments** — scan the recent conversation for a naming discussion (as
`/quote` finds the quote) and inscribe the full outcome: chosen name, candidate
set, reasoning, filed under the correct state and language mouth.

**Arguments — keywords and/or quoted phrases**, e.g. `/rista funklein 'scintilla anime'`.
Inscribe EACH term. Per term:
- **Spelling / diacritic correction, silent but noted**: `funklein` → **Fünklein**;
  `scintilla anime` → **scintilla animae**. Correct it; note the correction in the entry.
- **Language detection** → route to the right mouth (Greek / Latin / German /
  Norse / Hebrew / Spanish as of 2026-07-05). If the tongue is new, **create a
  new language section** under "The well has many mouths".
- Entry carries: term (native script where applicable + transliteration),
  meaning/gloss, **provenance** (who raised it, in which conversation / repo /
  session), **context** (one-line hook for why it surfaced), and the **date**.
- **Dedup**: if the term already lives in the well, annotate/update the existing
  entry instead of adding a duplicate.

## Step 1 — Determine the inscription

- **No-arg**: identify the naming discussion in the recent turns. Extract chosen
  name, every candidate + reasoning, the state of each, and the target section
  (a fleet guardian/gate/tool → a "Drawn for X" / "In service" section; a raw
  word in another tongue → that language's mouth).
- **Args**: parse each keyword and quoted phrase as a separate term to route.

If nothing nameable is found, say so and stop — do not invent an entry.

## Step 2 — Get the date

Run plain `date` (the machine clock is US Central; do NOT use PowerShell — the
operator's deny rules block it — and NEVER prefix `TZ=`, which returns UTC in Git
Bash). Parse to `YYYY-MM-DD`.

## Step 3 — Isolated worktree on dispatch main

dispatch `main` is branch-protected and the live checkout has uncommitted work.
Work only in a fresh worktree off `origin/main`:

```bash
git -C /c/Users/mcwiz/Projects/dispatch fetch origin -q
git -C /c/Users/mcwiz/Projects/dispatch worktree add -b rista-<slug> \
    /c/Users/mcwiz/Projects/dispatch-rista-<slug> origin/main
```

`<slug>` is a short kebab tag for the inscription (e.g. `kastalia`, `funklein`).

## Step 4 — Inscribe (in the worktree, anchor-asserted)

Read `dispatch-rista-<slug>/ideas/the-well-of-names.md`. Edit with the **Edit**
tool using a unique anchor (a real existing line near the target section) — a
silent `str.replace` no-op burned the prototype once, so every edit must change
the file. Confirm the diff is non-empty before committing:

```bash
git -C /c/Users/mcwiz/Projects/dispatch-rista-<slug> diff --stat
```

Follow the well's existing formatting: `## The well's own name`, `## In service`,
`## Drawn for <thing>`, and the `### <Language>` mouths under "The well has many
mouths". New tongues get a new `### <Language> (native name)` mouth.

## Step 5 — Land via the shared PR-lander

File the tracking issue, commit IN the worktree, remove the worktree (the
branch must not be checked out anywhere when the driver deletes it after
merge), then hand the whole push→PR→poll→merge→verify→graft cycle to the
shared driver. Do NOT hand-roll push / poll / merge / graft — the driver owns
that cycle with a bounded poll, a verify-gate before any deletion, the
ADR-0217 graft hardcoded, the squash SHA looked up by PR number, and a
fail-safe protection probe:

```bash
# capture #N from the issue URL (or use the driver's --no-issue with an
# operator-authorized reason)
ISSUE_N=$(gh issue create --repo martymcenroe/dispatch \
  --title "inscribe <term> into the Well of Names" --body "..." \
  | grep -oE '[0-9]+$')
git -C /c/Users/mcwiz/Projects/dispatch-rista-<slug> add ideas/the-well-of-names.md
git -C /c/Users/mcwiz/Projects/dispatch-rista-<slug> commit -m "ideas(well-of-names): inscribe <term> (Closes #${ISSUE_N})"
# Worktree out of the way FIRST — clean tree, plain remove (never --force):
git -C /c/Users/mcwiz/Projects/dispatch worktree remove /c/Users/mcwiz/Projects/dispatch-rista-<slug>
(cd /c/Users/mcwiz/Projects/unleashed && poetry run python src/tracked_pr_land.py \
  --repo /c/Users/mcwiz/Projects/dispatch \
  --branch rista-<slug> \
  --title "ideas(well-of-names): inscribe <term> (Closes #${ISSUE_N})" \
  --issue ${ISSUE_N} \
  --body "Inscribed by /rista.

Closes #${ISSUE_N}")
```

Exit `0` = merged, verified on dispatch `origin/main`, branch grafted +
deleted — nothing left to clean. Non-zero = STOP and report the issue number,
branch, and the driver's final `stage=…` line; never escalate to `--admin` /
`--no-verify` / force-push / `branch -D`.

## The `super` option (gated; operator-defined)

`/rista super …` is reserved for a heightened inscription mode, gated behind an
**active second confirmation** — a typed verbatim phrase (the `require_confirmation`
Danger-Zone pattern), never y/n. Its semantics are deliberately unspecified until
the operator defines them; until then, `super` prompts for the typed phrase and,
lacking a defined behavior, asks the operator what `super` should do rather than
guessing.

## The well's mouths (as of 2026-07-05)

Greek (ἑλληνικά, the main well) · Latin · German (Deutsch) · Norse (norrœnt, +
runes) · Hebrew (עברית) · Spanish (español). Add a mouth when a new tongue
arrives.

## Rules

- Native script + transliteration, always. Verify non-trivial scripts; never
  invent rune spellings from memory.
- Append-only; dedup by annotation, never by rewrite.
- Worktree isolation, always; never touch the live dispatch checkout.
- The skill commits its own writes (worktree → driver-landed PR); it does not
  defer the commit to a later session.
- No numbered/yes-no prompts to the operator (the session wrapper auto-fires
  them); ask open-ended questions only.
