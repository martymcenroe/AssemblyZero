# Test Report — The Scraper Must Import Without pywinpty (#3452)

```
poetry run pytest tests/unit/test_scraper_import_safety.py -q
4 passed
```

## Where These Tests Live, and Why Not the Obvious Place

The natural home is `tests/tools/`, beside the test that exposed the bug. They
are in `tests/unit/` instead, because **no CI step collects `tests/tools/`**
(#3453). A regression test that does not run is not a regression test. They move
once the selector change lands.

## Simulating a Linux Host on Windows

`monkeypatch.setitem(sys.modules, "winpty", None)` makes `import winpty` raise
`ImportError`, which is exactly what the Ubuntu runner does natively. The fault
is reproduced on the developer machine rather than waiting six minutes for CI to
reproduce it.

## What Is Asserted

| test | property |
|---|---|
| `test_imports_cleanly_when_pywinpty_is_absent` | the module loads and binds `winpty = None` |
| `test_importing_does_not_exit_the_process` | states the property directly, so a future module-level exit fails here rather than inside a collector |
| `test_the_cli_still_refuses_to_run_without_pywinpty` | `_require_winpty()` exits 1 and emits the original JSON — deferring the check did not weaken it |
| `test_the_guard_is_a_no_op_when_pywinpty_is_present` | on Windows the scraper behaves as it always has |

The third is the one that keeps the fix honest. Making a module importable is
easy if you are willing to delete its safety check; this asserts the check still
fires, with the same payload and the same exit code, at the moment it matters.

## The Regression Test Was Proved Non-Vacuous

A test that passes after a fix proves nothing on its own — it must fail before
it. `origin/main`'s unfixed scraper was extracted to a throwaway file under
gitignored `data/` and the same import machinery pointed at it:

```
with pytest.raises(SystemExit) as excinfo:
    spec.loader.exec_module(mod)
assert excinfo.value.code == 1

1 passed
```

The old code does raise `SystemExit(1)` on import. So the suite above would have
failed against it, which is what makes it a guard rather than decoration. That
proof file was deliberately not committed; it exists to be run once.

## What Is Not Verified

**Not executed on Linux.** The failure was reproduced by simulating the absent
import, not by running on Ubuntu. The simulation is faithful — binding a module
to `None` in `sys.modules` produces the same `ImportError` — but the first real
Linux collection happens on CI.

**The scraper's own behaviour is untested.** Nothing here runs the PTY path,
parses usage output, or checks the CLI end to end. This change makes the file
importable; it makes no claim that the scraper works.
