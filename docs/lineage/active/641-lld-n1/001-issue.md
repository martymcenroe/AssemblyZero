---
repo: martymcenroe/AssemblyZero
issue: 641
url: https://github.com/martymcenroe/AssemblyZero/issues/641
fetched: 2026-03-07T01:40:09.355837Z
---

# Issue #641: feat: route scaffolding/boilerplate files to Haiku

## Problem

All code generation uses the same expensive model regardless of file complexity. Test scaffolds, \`__init__.py\` files, and boilerplate don't need Sonnet/Opus — Haiku at $1/$5 per M tokens is 80% cheaper.

## Fix

In \`implement_code.py\`, add model selection logic based on file characteristics:
- Files matching \`__init__.py\`, \`conftest.py\`, or under 50 lines → Haiku
- Test scaffold generation (N2 node) → Haiku
- All other code generation → configured default (Sonnet)

Requires updating \`call_claude_for_file()\` to accept a model parameter, and adding routing logic in \`generate_file_with_retry()\`.

## Impact

20-30% cost reduction on implementation workflows with many small files.

## Origin

Cost audit of API spend (~\$25 every other day).