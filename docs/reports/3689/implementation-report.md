# Implementation Report: ADR-0206 is Accepted and its four questions are answered (#3689)

## The defect, as filed and as corrected

The issue was filed claiming an **accepted** ADR held four unanswered questions. That premise was wrong, and the correction is the useful part of this change.

`docs/adrs/0206-bidirectional-sync-architecture.md:3` read `**Status:** Proposed`, dated 2026-01-13. A proposal is entitled to carry open questions — that is what a proposal is for. The real defect was adjacent and worse: **the document sat at `Proposed` for nearly nine months while the thing it proposed was built, maintained and wired in.** A reader could not tell from it whether the proposal had been adopted, rejected or forgotten, and its four questions read as live design work on a design that was already running.

Asserting a document's status without reading its header is the same class of error as reading a settled paragraph as a live question. The measurement came second when it should have come first.

## What was measured, 2026-10-01

| Evidence | Finding |
|---|---|
| `assemblyzero/workflows/janitor/probes/harvest.py` | Invokes `assemblyzero-harvest.py` and parses its output for cross-project drift — harvest runs automatically, as a probe |
| `.github/workflows/` | Five workflows, none carrying a `schedule` trigger. The janitor is the automation route; cron is not used |
| `tools/assemblyzero-harvest.py` git log | Maintained, most recently touched under #3536 |
| `docs/0003-file-inventory.md:125-126` | Harvester CLI and prompt both listed `Stable` |
| `pyproject.toml:3`, `git tag` | `0.1.0`, one tag. Effectively unversioned |
| `CLAUDE.md` | "Tools execute from `AssemblyZero/tools/`, not copied locally" — nothing installs this as a package |
| Harvest and push tooling, searched for rollback/revert | **Nothing found.** The one real gap |

## What changed

**Status is `Accepted`**, with a dated retrospective note saying why and naming the three artifacts that prove the mechanism shipped. The status line, not the questions, is what made the document unreadable.

**Section 11 holds four recorded answers instead of four questions.** Three cite the measurements above. The fourth points at #3690.

The decisions recorded for the first three are deliberately narrow — each says what *is* true and what would reopen it, rather than ruling on a hypothetical:

- Harvest automation is answered by the implementation, and the absence of a `schedule` trigger across all five workflows is recorded as the repo's actual pattern rather than as an omission.
- The versioning answer rests on how the repo is consumed, which is a fact in `CLAUDE.md`, and names the condition that would reopen it: something consuming this as a dependency.
- Cross-org use is recorded as having no consumer, and as warranting a new ADR rather than a question held open against the possibility. A question kept alive "in case" is the shape this whole audit was about.

**The rollback row became #3690** rather than a decision, because it is the one row where the honest answer is "this does not exist". #3690 asks for the manual sequence to be written down first, for the child-side state a revert cannot reach to be named, and for the tooling question to be recorded either way — "rollback is manual, here is the procedure" being a complete answer.

## Why there is no new test in this repo

The enforcing check is a program, and it already exists in the private repo that is the fleet's canonical home for cross-repo audits: it reads a directory of ADRs and reports any section heading claiming an open or undecided state, testing heading *words* against a closed, enumerated set. It takes the directory as an argument, so it can be pointed at this repo's 37 ADRs without a second copy of the logic.

Writing a local equivalent here would be a second implementation of one rule, which is the drift the fleet's no-duplicate-rules principle exists to prevent. Fleet-wide coverage for this repo's ADRs is tracked on the audit side.

Two false positives were identified while building that check, both from this repo, and both are pinned by its tests:

- **`## 5. Not decided here`** (ADR-0232) bounds scope — it says where a question belongs rather than holding it, which is itself a decision. It must stay clean.
- **`## 4. Reference implementation — /onboard over pickup_decide.py`** (ADR-0224) matches a naive substring test on "decide" and must not match, which is why words are compared rather than substrings.

## What this does not do

It does not audit the other 36 ADRs' bodies. The heading sweep covered all 37 and found three hits, of which this was the only genuine one. A body-level sweep for deferral sentences was tried on the audit side and abandoned: most hits were legitimate, and a check that reports them trains its reader to ignore it.
