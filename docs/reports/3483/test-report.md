# Test Report — Remove 358 Unused Imports (#3483)

## What Was Run Locally

```
poetry run pytest tests/unit -k "llm_provider or implement_code or section_utils or generate_draft"
292 passed, 10268 deselected in 9.01s
```

That selection is not arbitrary. It covers the modules where a wrongly-removed
import would do the most damage: the provider layer, the package whose
re-export shim was declared one change earlier (#3480), and the two modules
whose imports were edited by hand rather than by ruff.

## The Full Tier Caught a Regression the Targeted Run Did Not

This is the entry that matters. The first push of this change **failed CI**, and
the local full tier — which returned after the PR was opened — found the same
single new failure:

```
FAILED tests/unit/test_interface_surface.py::TestSummarizers::test_spec_stage_aliases_are_the_core_functions
3 failed, 10524 passed, 21 skipped, 7 deselected, 5 xfailed in 621.56s
```

```
ImportError: cannot import name '_summarize_class' from
  assemblyzero.workflows.implementation_spec.nodes.analyze_codebase
```

A fourth re-export site — `analyze_codebase.py` aliases three core summarizers
to preserve its historical import surface, two of which are unused inside the
module. Its `noqa` named E402 but not F401, so the sweep had no signal to stop
at, exactly as in #3480.

**The 292-test targeted selection did not contain it.** That selection was
chosen for the modules most likely to break, and it missed the one that did.
Recorded plainly: a selection chosen by judgement is a hypothesis about where
breakage will be, and this one was wrong.

Fixed by restoring the two aliases with `# noqa: E402, F401`.
`tests/unit/test_interface_surface.py` → **27 passed**. Lint total unchanged at
123, F401 still 0.

The other two failures are the known #3468 pair. `test_create_initial_state_defaults_to_assemblyzero`
did **not** fail here, because this worktree is named `AssemblyZero-3483` and
contains the string — consistent with #3475.

## The PR Was Pushed Before the Full Tier Returned, and That Was the Wrong Order

The local full tier was started before the PR was opened and returned after.
pytest buffers its output, so a run in progress is indistinguishable from a
stalled one until it finishes; the PR went out on the strength of the targeted
selection, and CI failed first. Both then agreed on the same single new failure.

Recorded rather than glossed: this is the change that most needed the full tier
first — 358 imports across 193 files, where the failure mode is an `ImportError`
in a module the diff does not obviously implicate. The bug was caught, but by CI
being fast rather than by the verification running in the right order.

An earlier full-tier run in this same sequence (#3474, ten minutes, 10,519
passed) established the three known failures, all unrelated and filed: #3475
(a test asserting the checkout directory's name) and two under #3468 (a test
reading another repo's working tree).

## What Was Verified Beyond the Suite

**F401 reached zero.** `ruff check --select F401` reports no findings, from 358.

**F811 reached zero as a side effect.** Those ten were
redefined-while-unused; removing the unused import removed the redefinition. No
F811 work was done, and none is now needed.

**The three ruff declined were each traced, not deleted on the rule's say-so.**

- `BATCH_SIZE` — followed to its definition in `orchestrator.py`, confirmed used
  only there, confirmed absent from the package's `__all__` and from the #3480
  shim's, so no star import carries it.
- The two in `test_validate_mechanical.py` — sit in a TDD-era
  `try/except ImportError: pass`. The handler swallows rather than skips, so the
  probe asserts nothing; the other names in the block are used, these two are
  not.

**Two production sites were traced to confirm they were dead, not dropped
hand-offs.** `generate_draft.py` extracted `open_questions` and discarded it —
`review.py` does its own extraction and uses it, so the first is a leftover from
before that responsibility moved. `section_utils.py` computed
`full_indices = changed_indices | context_indices` while the loop below uses the
two sets separately. Neither is a lost value.

(Those two are F841, not F401, and are not fixed here — they were read because
the same investigation pass surfaced them, and the finding is recorded rather
than left for the next reader to re-derive.)

## Not Verified

**No test asserts the absence of F401.** Nothing stops a new unused import
tomorrow. That gate is the last piece of #3471 and is deliberately held until
the count reaches zero — a CI lint step added now would fail on the 123 findings
that remain.
