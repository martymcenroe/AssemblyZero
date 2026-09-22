# Implementation Report — Guard the #2283 Landing Embed (#3448)

## The Defect

`tools/land_2283_ci_tiers.py` lands `.github/workflows/ci.yml` through the
Contents API, because the fine-grained PAT cannot push under
`.github/workflows/`. It embeds the workflow as a string literal and PUTs it,
which replaces the file wholesale.

It was written 2026-08-13 and never run. In the five weeks it sat, main's
`ci.yml` gained two things the embed did not have:

| on main | in the embed |
|---|---|
| a `concurrency:` block with `cancel-in-progress: true` | absent |
| `actions/setup-python@v7` | `@v5` |

Running it would have reverted both. The `concurrency:` block is an active
Actions-cost measure added during the same squeeze that disabled Dependabot, so
the revert would have undone cost control inside a PR whose title claimed a
test-coverage improvement.

## Why Nothing Would Have Caught It

A wholesale PUT has no diff to inspect. The script's only pre-flight compares
the embed to main for **equality**, which answered "differs" — the correct and
expected answer for an update, and silent about the *direction* of the
difference. Equality distinguishes "nothing to do" from "something to do". It
cannot distinguish "adds three steps" from "adds three steps and removes your
concurrency block".

This is a property of the embed-and-PUT pattern, not a one-off mistake: any
script holding a copy of a file it will overwrite ages against that file,
silently, for as long as it sits unrun.

## The Change

**1. The embed was refreshed** to current main plus the tier steps, and verified
byte-for-byte against the `ci.yml` it lands rather than by eye.

**2. `would_drop()` was added**, and this is the part that lasts. Before any
write it compares main's line set against the embed's and returns every
non-blank line present upstream that the embed lacks. `main()` aborts on a
non-empty result, in dry-run and live alike.

Lines this change removes on purpose are declared in `INTENDED_REMOVALS` — the
old header comment, the `if:` that deferred integration, and the old integration
run line. Anything else means the embed has gone stale.

It compares line **sets**, not a diff, so moving a step does not trip it. Only
genuinely absent content does.

## Scope

`.github/workflows/ci.yml` is deliberately not in this change. It cannot be
pushed with this PAT, which is the reason the script exists. The workflow lands
when the operator runs the script; this PR makes that run safe.

#2283 stays open. It is the CI tier change itself, and it closes when the script
lands the workflow.
