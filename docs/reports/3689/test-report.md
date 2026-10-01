# Test Report: ADR-0206 is Accepted and its four questions are answered (#3689)

**No new tests in this repo, deliberately.** This is a documentation change whose enforcing program lives on the fleet-audit side, and duplicating that program here would create the second implementation the no-duplicate-rules principle exists to prevent.

## What was verified, and how

| Claim written into the ADR | How it was checked |
|---|---|
| Harvest runs automatically as a janitor probe | Read `assemblyzero/workflows/janitor/probes/harvest.py`: it locates and invokes `assemblyzero-harvest.py` and parses its output for cross-project drift |
| No scheduled workflow exists | Enumerated `.github/workflows/` — five files — and searched all of them for a `schedule` trigger. None has one |
| The harvester is live, not abandoned | `git log` on `tools/assemblyzero-harvest.py`: most recent change under #3536. `docs/0003-file-inventory.md:125-126` lists its CLI and prompt as `Stable` |
| The repo is effectively unversioned | `pyproject.toml:3` is `0.1.0`; `git tag` returns one tag |
| Nothing installs it as a package | `CLAUDE.md`: tools execute from `AssemblyZero/tools/`, not copied locally |
| No rollback path exists | Searched the harvest and push tooling for rollback/revert. Nothing found — which is why that row became #3690 rather than a recorded decision |

Every row in the ADR's section 11 cites one of these. **Counted and read, not estimated:** the workflow count is an enumeration of the directory, and all three heading-sweep hits across the 37 ADRs were read individually rather than counted, which is how two of them turned out to be false positives.

## The enforcing check, and the two false positives this repo contributed

The check reads a directory of ADRs and reports any section heading asserting an open or undecided state, comparing heading *words* against a closed, enumerated six-member set. It is offline — no network, no tracker — and takes the directory as an argument so it can be aimed here without a second copy.

Both of its false-positive tests are drawn from this repo's real headings, because invented fixtures would not have caught either:

- **`## 5. Not decided here`** (ADR-0232). Bounding scope is the one legitimate use of this language: it names where a question belongs instead of holding it. A check that punished this would be rewarding silence over an explicit handoff of scope.
- **`## 4. Reference implementation — /onboard over pickup_decide.py`** (ADR-0224). The naive form of the check is a substring test, and it reports this line. A filename is one token and keeps its dot, so word comparison does not match it.

Had the check shipped with either, it would have reported a scope statement and a filename as undecided sections — two false alarms out of three hits, which is the rate at which a check stops being read.

## What is NOT verified

**That the three recorded decisions are the ones the operator would make.** They are recorded as what is true today plus the condition that would reopen each, not as rulings. Nothing is blocked by any of the three: harvest runs, the repo is consumed by path, and no external consumer exists. A decision that blocks nothing is not a decision to put to anyone — which is the finding this whole audit rests on.

**That rollback works.** It does not exist. #3690 is the issue, and its first requirement is to write down the manual sequence that is currently re-derived under pressure.

**The other 36 ADRs' bodies.** The sweep was over headings, which is the surface a program can judge. A body-level sweep for deferral sentences was tried on the audit side and abandoned because most hits were legitimate.

## Commands

```
git log --oneline -3 -- tools/assemblyzero-harvest.py
grep -l "schedule" .github/workflows/*.yml     # no output: none is scheduled
grep -nE '^version' pyproject.toml ; git tag
```
