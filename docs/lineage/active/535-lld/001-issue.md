---
repo: martymcenroe/AssemblyZero
issue: 535
url: https://github.com/martymcenroe/AssemblyZero/issues/535
fetched: 2026-03-02T00:01:34.603293Z
---

# Issue #535: feat: DEATH as Age Transition — the Hourglass Protocol

## The Insight

> *"The most dangerous document is not the one that lies. A lie, at least, has the decency to know what it is. The truly dangerous document is the one that was true six weeks ago and hasn't been told otherwise. It will defend itself with the righteous confidence of the sincerely outdated."*

During the DEATH documentation reconciliation (#114), we discovered that the system had evolved past its own records. Six persona implementations had merged. The README said "not vector embeddings" while 14 RAG files existed. The file inventory listed 11 tools; there were 36. The age had already ended. The documentation just hadn't been told.

This led to a realization: **DEATH is not an audit. DEATH is an age transition.**

## The Age Meter (Civilization VII Analogy)

In Civ VII, an internal age progress meter fills based on achievements. Build a wonder: +5. Conquer a city: +10. When the meter fills, the age ends — not optionally, not "when you're ready." The world has changed enough that the old age no longer describes reality.

AssemblyZero works the same way. Issues close. Features merge. Architecture evolves. At some point, the documentation describes a civilization that no longer exists. **That's when DEATH arrives.**

DEATH in Discworld is not hostile. He's the most compassionate character Pratchett ever wrote. He doesn't end things because he wants to — he ends them because things that don't end properly can't become what comes next.

> WHAT CAN THE HARVEST HOPE FOR, IF NOT FOR THE CARE OF THE REAPER MAN?

The harvest is the documentation. The code was planted, grown, and ripened. Without the Reaper Man, the wheat rots in the field.

## Design

### The Age Meter

Every closed issue advances an implicit meter. Not equally:

| Event Type | Weight | Rationale |
|-----------|--------|-----------|
| Bug fix | +1 | Fixes reality but doesn't change the shape |
| Single feature | +3 | Adds capability |
| New persona / subsystem | +5 | Changes what the system *is* |
| Foundation work (RAG, pipeline) | +8 | Changes how everything else works |
| Cross-cutting architectural change | +10 | The old map is now wrong |

Weights derive from issue labels and complexity estimates already present in our workflow.

### The Hourglass

DEATH's hourglass tracks the age meter. The sand runs based on closed issue weights. Lu-Tze's janitor probes feed drift signals — not broken links (Lu-Tze fixes those), but *factual inaccuracies in documentation*. Each drift finding is a grain of sand.

### Three Triggers (Any One Suffices)

1. **Meter threshold** — Enough weighted issues have closed since the last DEATH visit. A janitor probe or GitHub Action computes the score. When it crosses threshold: "THE SAND HAS RUN OUT."

2. **Om summons DEATH** — `/death` skill. The human sees the moment — a batch of implementations merged, an interview approaches, a release is near. The records must match reality.

3. **Critical drift** — Lu-Tze's drift score exceeds a threshold. Not broken links. Factual inaccuracies. The README contradicts the codebase. The inventory is stale. The plague symptoms of an age that has already ended.

### The Reconciliation Protocol

When DEATH arrives (by any trigger):

1. **Walk the field** — Spelunk the codebase. Compare docs/wiki/inventory against code reality.
2. **Harvest** — Write the ADRs that capture what was decided. Draw the diagrams that show what was built.
3. **Archive** — Move the old age's artifacts to done. Update the inventory.
4. **Chronicle** — Update README and wiki to describe the civilization as it now exists.
5. **Rest** — DEATH departs. The new age begins with clean documentation.

### Two Modes

- **Report mode** — DEATH walks the field and produces a reconciliation report (what's stale, missing, wrong). Cheap. Good for triage.
- **Reaper mode** — DEATH fixes everything. Writes ADRs, draws diagrams, updates inventory, reconciles wiki. What happened in #114.

### The Feedback Loop

The output of DEATH becomes input for the next age's RAG. The ADRs DEATH writes get indexed by Brutha. The architecture diagrams inform future LLDs. The Librarian retrieves what DEATH recorded. The harvest feeds the next planting.

## Deliverables

- [ ] Standard `0015-age-transition-protocol.md` — the Hourglass Protocol
- [ ] `/death` skill (report mode + reaper mode)
- [ ] Age meter computation (issue weights from labels, running total)
- [ ] Drift scoring in janitor probes (factual accuracy, not just broken links)
- [ ] Integration: janitor drift score feeds the hourglass

## Dependencies

- #534 (Spelunking Audits) — spelunking is DEATH's methodology
- #94 (Janitor) — drift probes extend janitor infrastructure

## Philosophy

Ages are not named in advance. You'll know an age ended because DEATH arrived. Looking back, you'll see the shape. Looking forward, you just build.

DEATH doesn't patrol. DEATH doesn't sweep. DEATH arrives when the hourglass empties. Not as punishment. As care.

> *"WHAT CAN THE HARVEST HOPE FOR, IF NOT FOR THE CARE OF THE REAPER MAN?"*
> — Terry Pratchett, *Reaper Man*