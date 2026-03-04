---
repo: martymcenroe/AssemblyZero
issue: 566
url: https://github.com/martymcenroe/AssemblyZero/issues/566
fetched: 2026-03-04T06:38:54.582736Z
---

# Issue #566: bug: LLD drafter lists files before parent directories in files table

## Problem

The LLD drafter puts files before their parent directories in Section 2.1 (Files Changed), failing mechanical validation:

```
[ERROR] MECHANICAL VALIDATION FAILED:
  File 'tests/unit/dashboard/components/ConversationActionBar.test.ts' depends on
  directory 'tests/unit/dashboard/components' which appears later in the table.
```

## Evidence

Every draft attempt for issue #283 had this ordering problem in the test file section. The drafter never self-corrected even when the error was fed back.

## Fix

Either:
1. Update the drafter prompt to explicitly say "list directories before their contents"
2. Make the mechanical validator auto-sort (directories first, then files) instead of failing
3. Add a Ponder Stibbons fix for this pattern

Option 2 or 3 is preferred — this is a formatting issue, not a content issue.