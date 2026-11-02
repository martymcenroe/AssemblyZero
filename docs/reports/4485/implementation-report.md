# Implementation report: #4485, #4503

Two halts in the requirements workflow that told the reader the wrong thing, and one of them stopped a run the model could have finished.

## #4485: the gate's halt says what came back

`_no_verdict_reason` now gives one of three reasons. A call that failed gives "the call failed" and the transport's error. An answer that is not JSON gives "the answer is not JSON" and its start. Valid JSON the gate cannot use gives that phrase and names the answer's top-level keys. All six answers behind #4483 were valid JSON, and each was called "unparseable". `_parse_analysis` reports the reason through a new `why` list, because a second `json.loads` with its own handler is a new fail-open site to the audit.

The retry loop decides the wait by kind, as R4 asked to be decided on the record. A failed call waits out the backoff as before, because a transport can recover. An answer the gate cannot use is resampled at once, and the line says so and names no capacity cause. In both real runs behind #4483 the same shape came back three times, four minutes apart, so the wait bought nothing. The number of attempts is unchanged.

The storm detector is read after every attempt. The halt carries `requirements_storm_seen`, and the recovery text names a storm only when it is true. It used to blame "a transient capacity storm" under a halt that printed `Transient: No`. The halt message now names the recording that holds the answers when one is armed, and says none exists when it is not. The attempts line gives the seconds the retries actually waited.

## #4503: a missed edit is re-asked once

When a revision's SEARCH blocks do not apply, `_reask_failed_edits` asks the drafter once more, in the same iteration. The prompt is the first prompt with the failures added under the heading the spec stage already uses (#2569), and with the section each failed block was aiming at, exactly as the draft has it. `_aimed_section` picks the heading-bounded section sharing the longest run of characters with the failed SEARCH, and the shorter one on a tie. A second miss halts as before. Nothing redraws the document (#2200). The re-ask adds no `return` to `generate_draft`, whose halt sites the gate registry pins by index.

A revision that returns no edit blocks at all still halts without a re-ask. That is the whole-document reply #2200 exists to refuse, not a near miss.

`classify_error` gives an `[EDIT-SCRIPT]` halt the class `edit_script_rejected`, for the LLD and the spec stage both. It was `unknown`. The halt message and its recovery text no longer say a relaunch resumes this stage. For the LLD they say what the printed command does: it asks before it moves the lineage to its `-n1` copy, and then drafts again from the start.

## Left open

None.
