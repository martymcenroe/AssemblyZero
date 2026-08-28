# 0030 — The guard-vs-guard interaction matrix

**Status:** Active
**Issue:** #2568
**Data:** `assemblyzero/core/interaction_matrix.py`
**Lint:** `tests/unit/test_interaction_matrix.py`
**Sibling:** standard 0029, the defect-class registry — class 3 is the single-mechanism form of this; the matrix is the pairwise form.

Guard-vs-guard is the factory's emergent defect class. The 2026-08-27
campaign was almost entirely **pairwise failures between mechanisms that
are each locally correct**:

- the completeness check demanded the edit pinning refused (#2555);
- pinning's merge destroyed what the drafter and no verdict asked to
  remove (#2559);
- the cap halt blamed the drafter for what enforcement did (#2556, #2561);
- the leavings janitor swept what the loader reads (#2551).

Every one was found by a killed run. **None could have been found by any
single guard's own tests, because each guard passed its own tests.**

## The matrix is data, and the data is linted

The tables below are generated from `interaction_matrix.py`, and the lint
enforces three things prose cannot:

1. **No undeclared mechanism.** A module calling one of an artifact's
   signature symbols and appearing in no mechanism fails by name. This is
   the checklist lint: a new mechanism cannot silently join an artifact.
2. **No unruled cell.** Every mechanism pair is either fixture-backed or
   marked non-interacting **with a reason**. A blank cell is
   indistinguishable from an unconsidered one.
3. **No phantom.** Declared modules and named fixtures must exist, and a
   signature symbol nothing calls fails as dead — a scan looking for a
   symbol that is never called is weaker than it looks.

**Cells assert invariants, not implementations.** Implementations change;
the invariant is what makes the cell worth writing down.

## The lint found two mechanisms reading could not

Building this matrix from the package alone produced a matrix that missed
the mechanism responsible for #2551. The scan covers `tools/` as well, and
reported:

- **`tools/speedrun_roll.py`** and **`tools/speedrun_new_attempt.py`** call
  `classify_dirt`, `preserve_and_clear` and `is_pipeline_input`. These are
  the **sweep sites** — where a launch decides what to clear, and where the
  2026-08-27 kill happened.
- **`tools/run_implement_from_lld.py`** and
  **`tools/run_implementation_spec_workflow.py`** call `check_and_consume`.
  These are where a resume actually verifies its contract.

Both are now first-class mechanisms. Neither was in the issue's proposed
enumeration, which is the argument for the lint over a written list.

---

## Artifact: `draft-text`

The draft the drafter emits and every gate reads.

**Mechanisms:** `pinning-enforcement`, `completeness-checks`,
`message-addressability`, `spec-generation`.

| pair | ruling | invariant |
|---|---|---|
| pinning-enforcement × completeness-checks | `test_completeness_pinning_deadlock.py` | A change a completeness failure explicitly demands is never revertible by pinning in the same round. |
| pinning-enforcement × message-addressability | `test_completeness_message_addressability.py` | Enforcement can READ every complaint that demands an edit: the message addresses a draft line, or demands an addition and is exempt. |
| pinning-enforcement × spec-generation | `test_pinning_conservation.py` | The merge never emits a document that lost or multiplied an unnamed test definition — revision unenforced or previous entire, never the stitch. |
| completeness-checks × message-addressability | `test_completeness_message_addressability.py` | Every check's real emitted message is classified, and a rewording that drops its address fails the suite. |
| completeness-checks × spec-generation | `test_generate_spec_pinning.py` | A demanded addition lands: an expansion-replace passes unconditionally and a locked region introducing a new test is freed. |
| message-addressability × spec-generation | **non-interacting** | `message_addressability` holds no draft state and is never called from the generation path — it reads a message and a draft generation has already produced. Neither can change what the other sees within a round. |

## Artifact: `working-tree-files`

Untracked pipeline emissions on disk, and who may remove them.

**Mechanisms:** `leavings-janitor`, `restore-machinery`, `loaders`,
`launch-sweep`, `settlement`.

| pair | ruling | invariant |
|---|---|---|
| leavings-janitor × loaders | `test_leavings_janitor.py` | A file a later stage reads on entry is never removable by the sweep — and the exemption is scoped to the ROLLING issue, because a blanket one re-creates #2144. |
| leavings-janitor × restore-machinery | `test_restore_from_graveyard.py` | Preserve-then-clear is structural: whatever the sweep clears is recoverable from the refs the restorer searches. |
| loaders × restore-machinery | `test_restore_best_on_failure.py` | A working copy is a cache: the loader rebuilds a missing input from refs before concluding absence. |
| launch-sweep × leavings-janitor | `test_leavings_janitor.py` | The exemption is applied at BOTH sweep sites, and it is issue-scoped at each. |
| launch-sweep × loaders | `test_mock_roll.py` | A launch never clears the input the loader is about to read on entry. #2551's kill, replayed end to end against a real repo. |
| launch-sweep × restore-machinery | `test_restore_from_graveyard.py` | Whatever a launch sweeps is recoverable: the ref is pushed before the file is removed. |
| settlement × launch-sweep | `test_stage_finality_launcher.py` | A settled artifact survives `--fresh` and is stated as preserved; an unsettled one is archived and the mismatch that unsettled it is stated too. Settledness decides, never branch contents. |
| settlement × leavings-janitor | `test_stage_finality_launcher.py` | Preservation is a named-file veto on the reset's archiving step, never a widening of the janitor's input exemption — #2551's issue-scoping is untouched, and a preserved file is still re-verified against its inputs at the next stage entry. |
| settlement × loaders | `test_stage_finality_skip.py` | A loader reads what settlement preserved: reuse requires the artifact on disk to hash as the one that settled, so a file edited after settling is redrawn rather than loaded. |
| settlement × restore-machinery | **non-interacting** | Settlement only ever declines a removal and restore only ever re-materialises content — no shared write and no ordering between them. A rebuilt working copy is checked against its recorded artifact hash at stage entry like any other file, so the restorer never needs to consult settledness. |

## Artifact: `halt-resume-state`

What a halt records and a resume reads.

**Mechanisms:** `resume-contract`, `halt-evidence`, `halt-node`,
`workflow-runners`.

| pair | ruling | invariant |
|---|---|---|
| halt-node × resume-contract | `test_resume_after_ceiling_halt.py` | Every halt writes a contract, and verification CONSUMES it — a completed lifecycle leaves none behind. |
| halt-evidence × halt-node | `test_halt_evidence.py` | Every halt emits its bundle, and a bundle that cannot be written never masks the halt it describes. |
| halt-evidence × resume-contract | **non-interacting** | Both are write-only at halt and read by different readers — the contract by the next launch, the bundle by a human or a report. Neither reads the other's output, and the halt node wraps each in its own fail-open so one cannot suppress the other. |
| workflow-runners × resume-contract | `test_resume_after_ceiling_halt.py` | The runner verifies the contract FIRST and refuses by name on any mismatch, before a single token is spent; `--accept-changed-inputs` is the loud, logged override. |
| workflow-runners × halt-node | `test_resume_after_failure.py` | A resume seeds from the snapshot the halt wrote, and inherits its counters rather than rediscovering them. |
| workflow-runners × halt-evidence | **non-interacting** | The bundle is forensic output addressed to a human or a report; no runner reads it, and none should — a resume consulting the bundle would be reading a summary when the contract carries the authoritative hashes. Deliberate asymmetry. |

---

## Adding a mechanism

1. Add it to the artifact's `mechanisms` in `interaction_matrix.py`.
2. Rule **every** new pair it creates — fixture or reasoned non-interaction.
3. Add its row here.

The lint fails until all three are done, which is the point.

## The requirement/verdict-state artifact is not yet in the matrix

#2568 names a fourth artifact — requirement and verdict state, touched by
extraction, the N1 gates, N4b, the cap-halt classifier and resume seeding.
It is **deliberately absent**: its mechanisms are spread across nodes whose
signature symbols are called through the graph rather than directly, so the
call-site scan that makes this lint honest does not yet reach them. Adding
it with a weaker scan would give a matrix that looks complete and enforces
nothing. Tracked in #2602.
