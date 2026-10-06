# Implementation Report: remove the repo-local Claude Code hooks (#3684)

## What landed

| File | Change |
|---|---|
| `.claude/hooks/bare-claude-guard.sh` | removed |
| `.claude/hooks/bash-gate.sh` | removed |
| `.claude/hooks/post-plan-write.sh` | removed |
| `.claude/hooks/secret-file-guard.sh` | removed |
| `.claude/hooks/secret-guard.sh` | removed |
| `.claude/settings.json` | their registrations removed |
| `tests/unit/test_bare_claude_guard.py` | drives the installed guard instead of a tracked copy (#3686) |

916 deletions in the removal commit, made 2026-09-30 by the fleet pass that removed these
files from the other repositories.

## Why the copies were safe to remove

A machine-wide managed settings file registers the central guard on both sides of the machine,
on the same tool matchers these copies used, with scripts whose line endings parse and which
deny with the only exit code the hook protocol treats as a denial. Project settings are
additive, so these ran beside the central set and never in place of it.

They were not a second layer:

- Each reads a harness environment variable that is no longer set, hits its own empty-string
  guard, and allows everything.
- `bash-gate.sh` encodes a retired policy: it blocks `&&`, `|` and `;` in a command to avoid
  permission dialogs. That is no longer how any session works, so it would be a regression if
  it ever started running.
- Most deny with exit 1, which the protocol treats as a non-blocking error. The banner reaches
  the transcript and the command proceeds.
- Those with CRLF line endings fail to parse under Ubuntu bash and exit 2, which the protocol
  treats as a denial, so in practice they refuse every tool call they match.

The last point is why this is a repair rather than housekeeping: the registrations were costing
refused tool calls in ordinary work.

## Why this did not land on 2026-09-30, and what changed

The fleet pass made the removal commit and stopped. It declines to touch a branch carrying a
commit of its own, which was right, and the branch then sat with a failing check.

The check failure was this repository's own test suite, and reading the CI log showed the only
failures were `tests/unit/test_bare_claude_guard.py`. That file hard-coded
`.claude/hooks/bare-claude-guard.sh`, one of the files being removed, so the change broke it by
construction. Nothing else in the suite failed.

## The test now drives what actually runs

`bare-claude-guard.sh` was registered by nothing in this repository: no settings file referenced
it and it gated no tool call. These tests were the only thing still pointing at it, which is
what made a dead file look alive.

So they drive the installed copy, in the user's hook directory, registered by the machine-wide
managed settings. Keeping a tracked second copy and testing that instead is how the dead file
came to exist and would recreate it.

Where no guard is installed, such as a CI runner, the cases skip. That is in the module
docstring rather than left to be discovered: they assert a property of an installed guard, and a
runner has none to assert it about. Verifying that every registered hook on a machine returns
the right exit code is a separate program, run where the hooks are.

## Two notes for whoever reads this next

A second local clone of this repository shares this remote, so one pull request covers both.
After this merges, both clones need a pull before their working trees stop showing the deleted
files.

`.gitattributes` is untouched by this work.
