# Test Report — Every standalone run leaves a record (#3503)

Backfilled 2026-09-25 after the merge, from PR #3520 (merge `0a178b00`) and its body (#3559). The runs quoted are the ones the PR reported at the time; none was re-run for this backfill.

## Tests the PR added

`tests/unit/test_run_record.py`, 15 tests. The one #3503 was filed for: `test_lld_runner_records_a_crash_in_the_graph` patches the graph builder to raise and reads the crash record off disk; `test_impl_runner_records_a_crash_and_the_last_node` does the same through `main()`. `left_in_place` is tested against a throwaway repo with a bare origin (the `test_mock_roll` fixture shape): a worktree, a local branch, a pushed branch, an untracked LLD and a modified README all appear, and another issue's branch does not.

## Results the PR reported

Run with the four related suites: 172 passed.

## Not verified for this backfill

- Nothing was re-run. The PR's CI run is the record of the full tier at that commit.
- The PR body does not state an old-code run for these tests.
