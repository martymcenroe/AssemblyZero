# Implementation Report — Land the PR-Stuck-Recovery ADR as 0231 (#3461)

## What Was Stranded

A complete 35-line ADR, `docs/adrs/0229-pr-stuck-recovery-procedure.md`, existed
only on the unpushed local branch `docs/adr-0229-pr-stuck-recovery`. On no
remote.

It documents the non-destructive recovery path for a PR blocked by
`pr-sentinel`: fix the metadata with `gh pr edit`, re-trigger Cerberus with
`gh pr close && gh pr reopen` because the `edited` webhook does not trigger it,
then squash-merge. It states plainly why each step exists — no force-push, no
`--allow-empty` noise commits to re-trigger CI, and no escalation to the classic
PAT, because `gh pr` uses the Pull Request API rather than `git push` and so
never hits the `.github/workflows` scope block.

That procedure lives as prose in `CLAUDE.md` and
`docs/runbooks/0935-pr-stuck-recovery.md`. No ADR recorded the decision.

## Why It Could Not Land As Written

**The number was taken.** `main` carries `0229-fully-landed-state.md` and
`0230-fully-landed-from-a-dirty-shared-checkout.md`. Both 0229s were written
around 2026-09-13 on branches that could not see each other; one landed. This
takes 0231, the next free number, with a note in the document recording the
renumber so the gap in its history is not a mystery later.

**Its commit closed an issue it does not fix.** The branch's commit message is
`docs: formalize PR stuck recovery as ADR 0229 (Closes #3185)`. #3185 is *"ADR-0217's
graft recipe fails and leaves a replace ref behind when local `main` has not been
fast-forwarded"* — the graft recipe leaving residue, an unrelated subject.

Merging as written would have closed #3185 silently while leaving it entirely
unaddressed, because GitHub honours the directive in the commit. #3185 stays
open here and carries a separate comment with evidence observed on 2026-09-21.

## The Change

One added file. Content byte-identical to the branch's original except the
`# ADR 0229:` heading, now `# ADR 0231:`, and an added note recording the
renumber.

## What Was Deliberately Not Taken

The branch also adds a `concurrency:` block to `auto-reviewer.yml` and
`auto-reviewer-caller.yml`. That is the change a sibling branch reverts with the
message *"fix(ci): remove concurrency to fix workflow parser error"*, which is
why `main` carries that block in `ci.yml` only. Taking it would reintroduce a
known-broken workflow edit.
