# Test report: #4509

## Changed tests

`tests/unit/test_agy_answer_then_hang.py` (new) runs a real process as a stand-in for agy, because the defect sits between a process and its pipes, where a mock of `communicate` hid it.

- `test_t1_the_answer_is_used_and_the_call_returns_in_seconds` and `test_t1_the_process_is_gone_when_the_call_returns` (R1, R6): a reply printed with no exit is used, and the process is gone.
- `test_t2_a_bad_status_is_still_a_failed_call` and `test_the_failed_exit_of_a_process_we_ended_is_not_held_against_it` (R2): the reply's own status decides.
- `test_t3_unfinished_output_waits_for_the_timeout` (R3): half a reply and plain text both wait.
- `test_a_reply_that_grows_is_not_cut_off` (R3): a reply still arriving is not cut off.
- `test_t4_a_failed_exit_still_counts`, `test_a_clean_exit_is_as_it_was` and `test_plain_text_and_an_exit_is_as_it_was` (R4): an agy that exits takes the old path.
- `test_t5_silence_times_out` (R5): silence still times out.
- `test_a_broken_reply_still_raises` (R2): output that opens like a reply and does not parse raises.

## Runs, 2026-11-01

The last code edit was at 4:21 PM Central. Both runs below came after it.

- Unit tier, finished 4:37 PM Central: 13660 passed, 66 skipped, 7 deselected, 7 xfailed in 14m 57s.
- The other tiers together, finished 4:39 PM Central: 84 passed, 7 skipped, in 2m 12s.
- T6, one real call: the same 108,522-character prompt that failed twice at 300 s returned its full 15,275-character answer in 31.1 s, with tokens recorded. This was one call, and it is the only real proof in this report. The tests above use a stand-in.
- `ruff check`: nothing new. `gemini_client.py` carries the same findings as `main`, and the new test file has none.
