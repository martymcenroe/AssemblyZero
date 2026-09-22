# Test Report — Land Four Stranded Lessons (#3460)

## What This Change Is

Four rows appended to a markdown table. No code, no import, no runtime path, no
behaviour. No test is claimed, and inventing one would produce a pass that
measured nothing.

The property that matters here is not correctness of logic but **that nothing
was lost or altered**, since the file is append-only institutional memory. That
is mechanically checkable, and was checked.

## What Was Verified

**1. The change is purely additive.** `git diff --stat` reports
`1 file changed, 4 insertions(+)` with no deletions, and the line count moved
265 to 269. An append-only file that loses a line in an "append" is the failure
worth guarding against, so this is asserted rather than eyeballed.

**2. Exactly one file is touched.** `git status --porcelain` showed a single
`M docs/lessons-learned.md` before staging. This matters because the donor
branch carries other changes that must **not** ride along — in particular a copy
of `docs/adrs/0229-fully-landed-state.md` that is behind main's.

**3. The rows are present by content.** Three distinctive markers, each absent
before and present exactly once after:

| marker | before | after |
|---|---|---|
| `NEVER USE REGEX` | 0 | 1 |
| `unleashed #1035` | 0 | 1 |
| `PIPESTATUS` | 0 | 1 |

Checking by content rather than by counting rows is what distinguishes "four
lines were appended" from "the four intended lines were appended".

**4. The append could not join lines.** `tail -c 1 | cat -A` on main's file
returned `$` — it ended with a newline — so the first appended row starts on its
own line rather than being concatenated onto the last existing row.

**5. The rows are verbatim.** Extracted with `git show <branch>:<path> | tail -4`
and appended with `cat >>`. Nothing retyped them, so no character passed through
a transcription step.

## What Is Not Verified

**No check enforces that this file stays append-only.** Nothing in the suite
would fail if a future change deleted a row. That is the guard this incident
argues for, and it does not exist; it is not added here because a guard deserves
its own issue and its own test rather than being tacked onto the rescue.

**The lessons' claims are not re-verified.** The `| tail -1` row reports a
measurement on git 2.55.0.windows.3. This change preserves that record; it does
not re-run the measurement.
