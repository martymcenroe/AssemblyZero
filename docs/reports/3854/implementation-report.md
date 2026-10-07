# Implementation Report: the ledger records requirements and implementation_spec (#3854, part of #3581)

## What changed

`docs/audits/0908-loud-failure-sweep-ledger.md` changes only through `ledger_record.py`, run once per package:

| Package | Files marked read | Findings appended | Violations | Compliant |
|---|---|---|---|---|
| `assemblyzero/workflows/requirements/` | 35 | 199 | 163 | 36 |
| `assemblyzero/workflows/implementation_spec/` | 26 | 158 | 125 | 33 |

Each file is marked "2026-10-07, one delegated reader per file, every finding's quoted line verified by script".

## How the findings were checked

For each package, two delegated readers read the files, each file by one reader, split by line count:
- requirements: 8,390 and 8,406 lines;
- implementation_spec: 6,851 and 6,847 lines.

`verify_findings.py` matched every quoted line to its file and line: requirements A 89 and B 110, implementation_spec A 84 and B 74. Two first-run line numbers were one too high, and were corrected by reading the files: `finalize.py:298` is 297, and `lineage_seed.py:141` is 140.

## Next

One issue per module for both packages, linked from #3581.
