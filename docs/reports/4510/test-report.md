# Test report: #4510

## Unit

- `tests/unit/test_agy_exit_probe.py`, 14 tests: the prompt is exactly the size asked; long replies are asked for by function count; the prompt is composed as the transport composes it; `/proc/<pid>/stat` is read from the last parenthesis; the TCP table maps inodes to endpoints; the log tail starts at the completion signal; agy's glog clock and a whole log are read for the process's end.
- `tests/unit/test_agy_answer_then_hang.py` adds two: the settle outlasts the slowest measured exit three times over, and a real stand-in that answers and exits 2.8 s later is neither ended nor warned about, at the real settle.

## Real calls

All on 2026-11-02 between 1:21 and 2:03 AM Central, agy 1.4.12, `gemini-3.8-flash-high`.

| Run | Calls | Exited by itself | After the answer |
|---|---|---|---|
| Prompt size, 2,000 to 110,000 chars | 10 | 10 | 1.3 to 2.5 s |
| 110,000 chars, long thinking | 8 | 8 | 0.5 to 1.3 s |
| Exact argv, 2,000 and 110,000 chars | 8 | 8 | 0.8 to 2.8 s |
| 110,000 chars, code replies | 4 | 4 | 0.5 to 0.8 s |
| Through the transport, 10 s settle | 6 | watcher ended none | |

## Full suite

14,273 passed, 19 failed. Eighteen fail the same way on `main` at `962f5d3a` and are already filed: the auto-reviewer wait loop (#4528), the full-pipeline integration test (#4529), and the ADR reference check (#3730). The nineteenth, `test_the_unit_tier_runs_the_serializer_strict`, fails only inside the full run and passes alone in this worktree.
