# Implementation Report — Track `tools/hermes_pin_workflow_shas.py` (#3440)

## What This Change Is

One untracked file becomes tracked. Pure addition, no existing file touched.

`tools/hermes_pin_workflow_shas.py` pins Hermes CI workflow refs to commit SHAs
through the classic-PAT Contents API, because the fine-grained PAT cannot create
or update files under `.github/workflows/` (ADR-0216). Its direct sibling,
`tools/hermes_add_ci_workflow.py`, is already tracked here and lands a different
workflow file by the same mechanism.

## Why It Was Not in #3436

It was held back on the claim that its docstring describes another repo's CI
configuration and therefore should not land on a public surface. That claim was
not checked before it was surfaced, and it is wrong.

| what was claimed | what is actually true |
|---|---|
| naming that repo's CI detail here is a new exposure | `tools/hermes_add_ci_workflow.py` is already tracked on main with the same docstring shape, naming the same repo and describing its CI gap in more detail |
| the name needed a public-shadow exception to be permissible | the name already appears across many tracked docs, audits and lessons-learned in this repo |
| the tool belongs in the other repo | it is fleet tooling, run from this repo's `tools/`, exactly like its sibling |

The established, published pattern was already there. One `git ls-tree` would
have shown it.

## Consequence of the Error

A working tool was moved into gitignored scratch, where nothing protects it, and
a decision was handed to the operator that did not need making. The cost was not
a leak; it was invented friction plus an unprotected file — the opposite of what
the objection was meant to achieve.

## Placement

`tools/`, beside its sibling. No new directory, no new convention.
