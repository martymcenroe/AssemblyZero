# Implementation Report — Land Four Stranded Lessons (#3460)

## What Was Stranded

Four rows of `docs/lessons-learned.md` existed only on the unpushed local branch
`adr/fully-landed`. Not on `origin/main`, not on any remote, on one machine.

Verified by content rather than by branch name, before the change:

```
grep -cF 'NEVER USE REGEX' docs/lessons-learned.md   -> 0
grep -cF 'unleashed #1035' docs/lessons-learned.md   -> 0
grep -cF 'PIPESTATUS' docs/lessons-learned.md        -> 0
```

`main`'s table ended at 2026-09-05. The stranded rows are dated 2026-09-08
(three) and 2026-09-11 (one).

## Why This Was the Urgent One

`docs/lessons-learned.md` is append-only institutional memory — the record of
how agents have failed, kept so a failure is paid for once. Four of those
payments were held in a single unreferenced local branch. Deleting that branch
would have made the failures repeatable, and nothing would have reported the
loss.

One of them is live against this repo's own documented procedure: `git merge
--ff-only ... 2>&1 | tail -1` reports a **refused** merge as a successful one,
because stdout block-buffers and flushes last and the pipeline's exit status is
tail's. The fleet merge sequence in the universal `CLAUDE.md` uses exactly that
shape. The hazard recorded there was swallowing a *warning*; this records it
swallowing the *failure*.

## The Change

An append. 265 lines to 269, `4 insertions(+)`, **zero deletions**, one file.

The rows were taken verbatim from the branch with `git show
adr/fully-landed:docs/lessons-learned.md | tail -4` and appended byte-for-byte.
Their original order is preserved, including the fact that the 2026-09-11 row
precedes the three 2026-09-08 rows. Re-sorting them would have been editing
institutional memory to taste, which is not this change's business.

## What Was Deliberately Not Taken

The donor branch carries two other things, and merging it wholesale would have
been wrong in both directions.

Its copy of `docs/adrs/0229-fully-landed-state.md` is **behind** main's by one
line — it predates ADR 0230 and lacks main's cross-reference to it. Taking the
branch as a merge would have deleted that line from main.

Its `generate_draft.py` timeout change is valid and wanted, and is filed
separately as #3463 so it lands as a code change with its own justification
rather than riding along inside a docs commit.
