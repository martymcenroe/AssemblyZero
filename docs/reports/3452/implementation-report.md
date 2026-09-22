# Implementation Report — The Scraper Must Import Without pywinpty (#3452)

## The Defect

`tools/claude-usage-scraper.py` called `sys.exit(1)` at module level:

```python
try:
    import winpty
except ImportError:
    print(json.dumps({...}))
    sys.exit(1)
```

pywinpty is Windows-only. On Linux the import fails, the exit fires **during
import**, and it terminates whatever process imported the file. When that
process is pytest, the collector dies:

```
INTERNALERROR> ... tests/tools/test_claude_usage_scraper.py, line 31
INTERNALERROR>     _spec.loader.exec_module(scraper)
INTERNALERROR> ... tools/claude-usage-scraper.py, line 37
INTERNALERROR>     sys.exit(1)
INTERNALERROR> SystemExit: 1
Process completed with exit code 3
```

Exit 3 is a pytest internal error. No test ran, passed, or failed. The output
reads as "the test framework broke" rather than "this file cannot be imported
here", which is what made it expensive to diagnose.

The importing test already stated the contract it needed, at
`tests/tools/test_claude_usage_scraper.py:27`:

> This relies on the `__main__` guard being present — importing must not
> trigger execution.

The guard it relied on was not there.

## The Change

The import no longer decides the process's fate:

```python
try:
    import winpty
except ImportError:
    winpty = None
```

and `_require_winpty()` performs the original refusal, called from `main()`.

**CLI behaviour is unchanged.** Same JSON on stdout, same exit code 1, same
message. Only the timing moved — from import to invocation. A guard clause may
refuse to run; it must not refuse to import.

## Why This Was Invisible

No CI step has ever collected `tests/tools/` (#3453). Unit runs `tests/unit/`,
integration ran `tests/integration/`. The file sat committed and never executed
until #2283 changed the selector to `tests/` plus a marker, at which point it
failed in 0.87 seconds.

## Blast Radius

`main()` is the only caller, reached only through the `__main__` guard, so the
scraper run as a CLI on Windows is byte-for-byte unaffected. Nothing else in the
tree imports this module except the test that could not previously import it.

Unblocks #2283, whose PR could not go green while collection died.
