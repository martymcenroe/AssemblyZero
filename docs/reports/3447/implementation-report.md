# Implementation Report: require_status_check.py

**Issue:** #3447
**Branch:** `3447-require-status-check` (worktree `AssemblyZero-3447`)
**Date:** 2026-09-22

## What prompted it

A repository had just had a test workflow landed into `.github/workflows/`, and
the second half of that work, making the check required, had no tool. The
`--require-check` phase of `land_polybolos_ci_workflow.py` does the operation
correctly but has owner, repo, branch and check name as module constants. A
second repository needing the same thing would have meant copying the file, and
a third would have made three.

## What landed

`tools/require_status_check.py`. Every target detail arrives through argv:

```
poetry run python tools/require_status_check.py --repo <R> --context <name>
poetry run python tools/require_status_check.py --repo <R> --context <name> --apply
```

Dry-run by default per standard 0017. `--apply` is the mutation flag rather than
`--execute`, since the source contains no command from the banned table.

`--owner` defaults to the fleet owner and `--branch` to `main`.

## Why the POST endpoint and not a PUT

The write is `POST .../branches/<branch>/protection/required_status_checks/contexts`,
which appends one context.

A `PUT` to `/protection` replaces the **entire** protection payload, so every
setting not restated in the request body is silently dropped: `enforce_admins`,
review requirements, force-push and deletion blocks. A tool whose job is to add
one check has no business reconstructing all of that, and a reconstruction that
misses a field disables a protection while reporting success. Appending cannot
have that failure mode.

## What it refuses

Two repository states stop it, and `--apply` does not override either, because
both are decisions about the repository rather than steps in a task:

- the branch has no protection at all
- the branch is protected but required status checks are switched off

Turning either on changes what every pull request in that repository must
satisfy.

A third state is deliberately **not** a refusal: `contexts: []` means checks are
on with none listed, which is materially different from checks being off, and it
is a perfectly ordinary thing to add the first context to. There is a test for
that distinction because the two are easy to conflate in a truthiness check.

## The two traps written into the docstring

**Required checks are keyed by job, not by workflow.** A workflow named `Tests`
containing a job `pytest` registers a check called `pytest`. Requiring `Tests`
yields a check that never reports and a branch nothing can merge into. The tool
cannot know which the caller meant, so it prints the contexts already present
before writing anything: if that list holds job names and the addition is not
one, the dry-run is where it shows.

**Never require a check that has not been seen green**, or every open pull
request in the repository is blocked until someone with admin scope removes it.

## Membrane

The target is never named in this repository. ADR-0216 is explicit that a
hardcoded target name in a tool, docstring or commit message is a leak, because
this repo is public and some targets are not. The `reason=` string handed to
`classic_pat_session` is built from argv at run time for the same purpose, so
the pinentry banner names the operation without this repo carrying the name.
