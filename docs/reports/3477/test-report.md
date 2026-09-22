# Test Report: ADR-0217 from a parked checkout

**Issue:** #3477
**Branch:** `3477-adr0217-parked-checkout`
**Date:** 2026-09-22

## The mechanism, verified

The claim step 2b rests on — `git branch -d` judges against the upstream when
one is set and against HEAD otherwise — is git's documented behaviour and was
exercised on 2026-09-22: from a checkout parked on a feature branch,
`git branch -d <orphan>` refused after a successful graft, and after
`git branch --set-upstream-to=origin/main <orphan>` the same command deleted
the branch with the warning the ADR now quotes. The recipe's earlier steps
(0b, 1, 2) had all succeeded; nothing about the graft was at fault.

## What this change cannot break

It is prose in an ADR. The suite is unaffected: `poetry run pytest -q` on the
branch is the same run as on `main`. Nothing executes the recipe from a test,
which is the standing gap the ADR's own "Option E: verified ineffective" note
shows was filled by sandbox trials rather than by CI.

## What a reader can now tell apart

The section *Two warnings that look alike* is the deliverable that matters:
the same warning text means "stop, the evidence proves nothing" in one
situation and "the recipe worked from a parked checkout" in the other, and the
tell is the ref the warning names. Both are written next to each other.
