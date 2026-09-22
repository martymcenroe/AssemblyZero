# Test Report — Track Six Untracked Work Products (#3436)

## What This Change Is

Three prose documents, one prompt text file, one ADR, and one one-shot script,
all of which already existed on disk, becoming tracked. Nothing imports the
script, no runtime path reaches any of it, and no existing file is modified.

There is no behaviour to exercise, so no test is claimed. Recording that plainly
is the point: a test invented to fill this section would pass without measuring
anything, which is worse than an honest absence.

## What Was Verified

**1. The change is a pure addition.** `git diff --cached --diff-filter=MD
--name-only` returns zero lines — no modification, no deletion, on any path.
`--stat` reports 6 files changed, 237 insertions, 0 deletions. This was the
design constraint, so it is the property worth asserting mechanically rather
than reading by eye.

**2. Exactly the intended six paths are staged.** `git diff --cached
--name-only` returns 6 lines and they are the six named in the implementation
report. This check exists because a shared checkout can leave unrelated paths
in the index, and `git add <my-files>` still commits whatever was already
staged.

**3. No private-repo name appears in any of the six.** A fixed-string sweep over
all six files for the private repo names used across this fleet returned no
matches. AssemblyZero is public and git history is permanent, so this is checked
before the commit exists, not after.

**4. The two excluded files are genuinely absent from the commit.** Confirmed by
the same 6-line staged listing: neither `tools/hermes_pin_workflow_shas.py` nor
any rehomed scratch artifact appears.

## What Was Not Verified

`tools/fix_az_workflow_concurrency.py` was read but **not executed**. It is a
one-shot mutation tool against repository settings; running it to prove it runs
would perform the mutation. Its correctness is not asserted here — tracking a
script is not a claim that the script works. If it is ever to be relied on
rather than merely preserved, that claim needs its own issue and its own test.

This is the honest boundary of this change: it makes six files recoverable. It
makes no claim about what any of them do.
