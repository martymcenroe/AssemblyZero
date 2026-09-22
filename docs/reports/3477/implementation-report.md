# Implementation Report: ADR-0217 from a parked checkout

**Issue:** #3477
**Branch:** `3477-adr0217-parked-checkout`
**Date:** 2026-09-22

## What landed

Three additions to `docs/adrs/0217-squash-merge-orphan-graft-cleanup.md`, all
in the recipe and its notes; no other file.

1. **Step 2b.** When `git branch --show-current` is not the default branch, set
   the orphan's upstream to `origin/<default>` before step 3. The comment says
   why: `-d` proves "merged" against the upstream when there is one and against
   HEAD when there is not; after the platform's squash-and-delete and a prune,
   the upstream is gone and HEAD is another lane's branch, so the orphan is
   reachable from the default branch through the graft and from nothing `-d`
   looks at. The proof stays the graft; the upstream only tells `-d` where to
   look.
2. **Step 3's expected warning** from a parked checkout, named next to the
   command so it is not read as a failure.
3. **Steps 4 and 5 run whether or not step 3 succeeded**, stated at both
   steps. A `&&` chain skipped the graft removal and the residue check in
   exactly the case that produced residue.

Plus a section, *Two warnings that look alike*, distinguishing the honest
`merged to origin/<default>, but not yet merged to HEAD` of step 2b from the
stale-own-ref hazard the universal instruction file's step 4e records, with
the tell (which ref the warning names) and the worktree alternative.

## Why a doc change and not a script

The ADR is the recipe agents run by hand; the lander that automates it lives
elsewhere and has its own issue tracker. The recipe is what was wrong.
