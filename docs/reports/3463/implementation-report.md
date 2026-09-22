# Implementation Report — Raise the Requirements Drafter Timeout (#3463)

## The Change

Three `drafter.invoke(...)` call sites in
`assemblyzero/workflows/requirements/nodes/generate_draft.py` now pass
`timeout_seconds=1800` instead of inheriting the provider default of 300.

| site | context |
|---|---|
| `_generate_best_of_n` | the best-of-N candidate loop |
| the edit-script path | `EDIT_SCRIPT_SYSTEM_PROMPT` |
| the classic path | the `else` branch beside it |

9 insertions, 3 deletions, one file. The added lines are reflow — each call went
from one line to three to stay within the line length.

## Why 1800, and Why That Is Not a Guess

The issue was filed noting that 1800 might be "the number that was reached for"
rather than a measured ceiling. Checking `main` settles it:

```
assemblyzero/workflows/implementation_spec/nodes/generate_spec.py:451:  timeout_seconds=1800,
assemblyzero/workflows/implementation_spec/nodes/generate_spec.py:576:  timeout_seconds=1800,  # 30 min — impl specs are large
```

The spec stage already runs at 1800 on `main`, with a comment stating why.
`assemblyzero/workflows/orchestrator/config.py:75` carries a stage at the same
figure. So this is the requirements stage catching up to a ceiling the fleet
already uses, not a new number invented here.

That is a consistency argument rather than a measurement. Nobody has profiled
the p99 of a drafter call, and this change does not either — it aligns one
outlier with the established figure.

## What the 300s Default Was Doing

`generate_draft` is the requirements drafter, one of the longest single model
calls in the fleet, and `_generate_best_of_n` makes several in a row. At 300
seconds a slow candidate is killed and scored unusable, which arrives downstream
as a model quality signal rather than as a timeout. The failure is silent in the
way that matters: the loop continues, the draft is worse, and nothing says the
cause was the clock.

## Provenance

The change existed only on the unpushed local branch `adr/fully-landed` and was
on no remote. It is applied here by exact-span edit against current `main`
rather than by taking the branch's copy of the file, so nothing else from that
branch rides along.
