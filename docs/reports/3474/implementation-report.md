# Implementation Report — Remove 90 Placeholder-Free f-Strings (#3474)

Second piece of #3471.

## The Change

```
ruff check . --select F541 --fix
Found 90 errors (90 fixed, 0 remaining).
```

37 files, **90 insertions and 90 deletions** — exactly one line replaced per
finding. The symmetry is the signature of a pure prefix removal: no line was
added or lost anywhere.

Representative:

```diff
-        print(f"  HALT — Workflow stopped")
+        print("  HALT — Workflow stopped")
-    logger.info(f"Type rename check summary:")
+    logger.info("Type rename check summary:")
```

## Why This Family First

It is the only one in the set where the fix cannot change behaviour. An `f`
prefix on a string with nothing to interpolate does nothing at runtime, so
removing it produces a byte-identical value. Ruff classifies it `[*]`, safely
fixable.

That makes it the right tranche to run the whole path on — targeted fix, full
suite, PR — before reaching the families that need a human reading each site.

The fix was applied with `--select F541` rather than a blanket `--fix`, so the
diff contains exactly one kind of change and can be reviewed as such. A blanket
run would have taken 412 findings across several rules in one unreadable commit.

## Effect

| | before | after |
|---|---|---|
| total | 636 | **546** |
| F541 | 90 | **0** |

No other rule's count moved. The F401/E402/F841/F811/E731/E741/E712/E722 rows
are identical either side, which is what confirms the selector held.

## Running Total for #3471

737 at the start → 636 after scoping (#3472) → **546** now. 546 remain across
eight rules, and the parent stays open until they reach zero.
