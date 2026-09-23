# Implementation Report — E402 Reaches Zero (#3484)

Piece of #3471.

## The Split the Issue Predicted, Confirmed by Reading Every Site

50 late imports were two different things. Both groups were identified by
reading the cause in each file, not by pattern-matching the rule.

## Group 1 — Incidental: a statement had drifted into the import block

Three files, 24 findings, fixed by **moving the statement**, not the imports.

**`assemblyzero/core/llm_provider.py`** (9) — a `logger = logging.getLogger(...)`
sat between imports. Everything after it was "not at top" purely because it was
there. The logger is read at call time only, so its position carried no meaning.
Moved below the imports; the comment recording *why it exists* (#1495 — every
call through a defensive branch raised `NameError`) moved with it, because that
history matters and its position did not.

**`assemblyzero/workflows/requirements/nodes/generate_draft.py`** (10) — same
shape: a logger plus two prompt-size constants. Moved below.

**`tools/verdict_analyzer/__init__.py`** (5) — the interesting one. It assigned
`PARSER_VERSION` above the imports with the comment *"Define PARSER_VERSION here
first, before any imports"*, which reads like a circular-import workaround that
must not be touched.

It was traced rather than trusted. `parser.py` defines its **own** copy, with its
own comment (*"Define PARSER_VERSION locally to avoid circular import"*), and
`database.py` imports that one. Nothing in the import chain needed the package's
copy early. It is now re-exported from the parser — which clears the findings and
removes a second definition that could drift from the one actually used. That
duplication is filed separately as #3486.

## Group 2 — Structural: the import *cannot* move

Eight files, 26 findings, `per-file-ignores`.

Each is a standalone script that puts the repo root on `sys.path` before
importing `assemblyzero`:

```python
sys.path.insert(0, str(Path(__file__).parent.parent))
from assemblyzero.tracing import configure_langsmith
```

Moving the import above the insert breaks the script. This is how a script in
`tools/` reaches the package without the package being installed.

**Verified per file, not assumed**: `grep -c 'sys.path.insert'` returns 1 for
every one of the eight. The list names each file rather than globbing `tools/*`,
so a future script does not inherit the ignore silently.

## Effect

| | before | after |
|---|---|---|
| total | 123 | **73** |
| E402 | 50 | **0** |

## Why Not Blanket-Ignore E402

Because group 1 was real. A statement drifting into an import block is how an
import ends up running after side effects it did not expect, and this rule is
the only thing that reports it. Silencing E402 repo-wide to quiet the `tools/`
scripts would have thrown that away — and would have left the `verdict_analyzer`
duplication unfound, since it surfaced only by asking why that one import was
late.

## Running Total for #3471

737 → 636 → 546 → 531 → 494 → 123 → **73**.
Remaining: F841 53, E731 8, E741 7, E712 4, E722 1.
