# Test report: #4485, #4503

## Changed tests

`tests/unit/test_requirements_halt_says_what_came_back.py` (new, 10 tests), #4485:

- T1: a failed call, an answer that is not JSON and valid JSON the gate cannot use give three different reasons, and the third names the answer's keys.
- T2: with no storm the recovery text says nothing about one, and with a storm during the attempts it names it.
- T3: an armed recording is named in the halt by its `calls.jsonl` path, and with none the halt says none exists.
- T4: a shape failure's retry lines say "resampling", name no capacity cause, and wait for nothing. A failed call still waits out the backoff.

`tests/unit/test_lld_revision_reask.py` (new, 7 tests), #4503:

- T1: a near miss is re-asked, and the second prompt names the failed block and holds the section it aimed at.
- T2: two misses halt after exactly two calls, inside one iteration.
- T3: both calls are edit-script calls; neither asks for a document.
- T4: the halt classifies as `edit_script_rejected`, does not say it resumes, and the plan's printed command, run through the tool's own parser and its regeneration check, asks and then moves the lineage aside to draft again.

Existing tests changed:

- `test_check_requirements.py`, `test_requirements_conflict.py`, `test_requirements_gate_timeout.py`: an answer that is not JSON is now reported as "not JSON". It was "unparseable".
- `test_lld_edit_script_revision.py`, `test_finalize_repair_routing.py`: a revision whose blocks miss now makes two calls, both edit scripts, and then halts.

## Runs

RUNS
