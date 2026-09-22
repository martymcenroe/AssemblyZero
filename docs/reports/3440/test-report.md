# Test Report — Track `tools/hermes_pin_workflow_shas.py` (#3440)

## What This Change Is

One file, already on disk, becoming tracked. Nothing imports it, no runtime path
reaches it, and no existing file is modified. There is no behaviour to exercise,
so no test is claimed. Inventing one would produce a pass that measured nothing.

## What Was Verified

**1. The change is a pure addition.** `git diff --cached --diff-filter=MD
--name-only` returns zero lines — no modification, no deletion. `git diff
--cached --name-only` returns exactly one path, the intended one. The
single-path check matters because this is a shared checkout and a concurrent
session holds its own worktree; `git add <file>` still commits whatever else was
already in the index.

**2. The precedent claim is real, not asserted.** `git ls-tree -r origin/main`
returns `tools/hermes_add_ci_workflow.py` — the sibling tool, already public.
Reading its header shows the same docstring structure: same repo named, same
issue-reference form, and a fuller description of that repo's CI gap than the
file being added here carries.

**3. The name is not newly exposed.** A fixed-string search over tracked paths on
`origin/main` returns that repo's name in many docs, audits and lessons-learned
files. This change introduces no name that main does not already carry.

These three are the checks that should have run before #3436 was filed. They
were run afterwards instead, which is the defect this issue records.

## What Was Not Verified

The script was **not executed**. It mutates another repository's workflow files
through the Contents API and requires a gpg-decrypted classic PAT; running it to
prove it runs would perform the mutation and trigger a pinentry prompt the agent
must never parent (ADR-0216, ADR-0227).

So this change makes the file recoverable. It asserts nothing about whether the
file works. If it is ever to be relied on rather than preserved, that claim needs
its own issue and its own test.
