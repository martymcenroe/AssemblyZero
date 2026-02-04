All 15 tests pass. The tests are focused specifically on Issue #248 functionality - the open questions loop behavior. The coverage shows we're testing the specific functions related to Issue #248:

- `_check_open_questions_status` 
- `_draft_has_open_questions`
- `_verdict_has_human_required`
- `_verdict_has_resolved_questions`
- `route_after_generate_draft`
- `route_after_review`

The implementation code in the source files (`generate_draft.py`, `review.py`, `graph.py`) already exists and is correct. The test file was the only thing that needed implementation.

Here's a summary of what the tests verify:

1. **test_id** - Verifies `open_questions_status` field exists in state with default "NONE"
2. **test_t010** - Verifies drafts with open questions proceed to review (pre-review gate removed)
3. **test_t020** - Verifies detection of resolved questions in verdict
4. **test_t030** - Verifies unanswered questions trigger loop back to drafter
5. **test_t040** - Verifies HUMAN_REQUIRED escalates to human gate
6. **test_t050** - Verifies max iterations respected for unanswered questions
7. **test_t060** - Verifies resolved questions proceed to finalize
8. **test_t070** - Verifies 0702c prompt has Open Questions Protocol section
9. **test_010** - Same as t010 (duplicate test scenario)
10. **test_020** - Tests multiple questions resolved detection
11. **test_030** - Tests full flow: detection + routing for unanswered
12. **test_040** - Tests full flow: detection + routing for human required
13. **test_050** - Tests max iterations boundary (at limit vs under limit)
14. **test_060** - Tests both RESOLVED and NONE status proceed to finalize
15. **test_070** - Tests prompt file contains required format instructions
