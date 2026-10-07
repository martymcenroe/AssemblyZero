# Implementation report: #3758

## The post-reset recheck honours settledness

`tools/speedrun_roll.py::ensure_base`: after the `--fresh` reset, the recheck of the base now passes its committed-artifact findings through `partition_by_settledness`, as the first check already did (#2609), logs `BASE settled, preserved after reset: <finding>` for each settled one, and drops them. Unsettled findings still go to `replace_or_refuse`.

Found on boostgauge #2, run `run-issue2-033833` (2026-10-07 03:38 Central). The first check preserved the settled `LLD-002.md` on `hardening-run-20` (landed by run 53, PR #483) and the reset was told to preserve it; the recheck then reported it as `still dirty after reset` and the launch aborted. The same run showed #3756 working: the spec the old gate approved was archived as unsettled on `gate:spec-completeness`.
