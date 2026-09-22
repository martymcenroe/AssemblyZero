# Test Report — Land the PR-Stuck-Recovery ADR as 0231 (#3461)

## What This Change Is

One markdown file added. No code, no import, no runtime path. No test is
claimed; inventing one would produce a pass that measured nothing.

What is checkable is that the number is genuinely free, the content is the
original, and nothing unwanted rode along. All three were checked.

## What Was Verified

**1. 0231 is the next free number.** `ls docs/adrs/` ends at
`0228-variable-ownership-discipline.md`, `0229-fully-landed-state.md`,
`0230-fully-landed-from-a-dirty-shared-checkout.md`. Nothing occupies 0231.

Checked against the directory rather than inferred from the issue text, because
the issue was written before the landing and `main` has moved since.

**2. The content is the original.** Extracted with
`git show <branch>:docs/adrs/0229-pr-stuck-recovery-procedure.md` and written
straight to the new path — no retyping, so no character passed through a
transcription step. The only edits are the heading number and the added
renumber note, both made with exact-span replacement.

**3. Exactly one file is added.** The donor branch also carries `concurrency:`
additions to two workflow files, which are known-broken; `git status` confirms
they are absent here.

**4. #3185 is still open.** Verified after the commit message was written, since
the whole point of this change's framing is that the original would have closed
it. The pre-flight scan of the PR body reports exactly one closing directive,
for #3461, and no `fix`/`resolve` verb near any other issue number.

## What Is Not Verified

**Nothing validates ADR numbering.** No check would fail if a future ADR reused
0231, which is precisely the collision this change exists to repair — two
documents claimed 0229 on branches that could not see each other, and only the
merge order decided which kept it. A guard would have to be a test over
`docs/adrs/` asserting unique prefixes; it does not exist and is not added here,
because it deserves its own issue rather than riding along.

**The procedure itself is untested.** This records a decision; it does not
exercise `gh pr edit`, the close/reopen re-trigger, or the claim that the
`edited` webhook fails to trigger Cerberus. Those claims come from the original
author's observation and are preserved, not re-measured.
