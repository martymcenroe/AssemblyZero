# Test Report — E402 Reaches Zero (#3484)

## The Full Tier Ran Before the PR This Time

```
poetry run pytest tests/unit
2 failed, 10525 passed, 21 skipped, 7 deselected, 5 xfailed in 596.44s
```

Both failures are the known `TestAgainstEveryRecordedDraft` pair, filed as
#3468 — a test class that reads another repository's working tree and asserts
hardcoded counts, `skipif`-ed in CI and never enforced there. **No new failure.**

Run before opening the PR rather than alongside it. The previous tranche (#3483)
was pushed on the strength of a targeted selection while the full tier was still
running, and CI found a regression that selection had missed. Same ten minutes,
different order, and the order is the part that was wrong.

## Targeted Run on the Edited Modules

```
poetry run pytest tests/unit -k "llm_provider or generate_draft or verdict"
742 passed, 1 skipped, 9817 deselected in 35.55s
```

Fast signal on the three files whose statements moved, before committing ten
minutes to the full tier.

## What Was Verified Beyond the Suite

**E402 reached zero**, repo total 123 → 73. No other rule's count changed.

**The `verdict_analyzer` package still exports its constant.** The riskiest edit
here moved `PARSER_VERSION` from above the imports to a re-export below them, on
the strength of tracing rather than of the rule:

```
poetry run python -c "from tools.verdict_analyzer import PARSER_VERSION; print(...)"
PARSER_VERSION 1.4.0
```

`ruff check tools/verdict_analyzer/` → **All checks passed!**

That import was guarded by a comment reading *"Define PARSER_VERSION here first,
before any imports"*, which is what a circular-import workaround looks like.
Following it showed `parser.py` defines its own copy and `database.py` imports
that one, so nothing in the chain needed the package's copy early. The check
above confirms the export survived the move.

**Every per-file-ignore was justified individually.**
`grep -c 'sys.path.insert'` returns 1 for each of the eight files, so each
genuinely cannot hoist its imports. The list names files rather than globbing
`tools/*`, so a future script does not silently inherit the exemption.

## What Is Not Verified

**No test asserts that a module-level statement stays out of the import block.**
The three files fixed here could drift back, and only the linter would notice —
which is the argument for the CI lint step that closes #3471, not something to
assert per-file.

**The per-file-ignore list is not checked against reality.** If one of those
eight scripts later drops its `sys.path.insert`, its exemption becomes
unjustified and nothing reports it. Worth a check that every ignored file still
contains the construct that earned the ignore; not written here.

**`tools/` scripts have no test coverage exercising their imports.** The suite
does not run them, so "the imports still work" rests on the fact that nothing
about them changed — only the config that describes them.
