# Implementation Report — A Factory Telemetry Rollup (#2575)

## Issue Reference
[#2575: a factory telemetry rollup -- counts decide what the next kill currently decides](https://github.com/martymcenroe/AssemblyZero/issues/2575)

## Files Changed
- `assemblyzero/speedrun/factory_report.py` (new): reads every factory store and returns the counted picture; renders it deterministically.
- `tools/factory_report.py` (new): the CLI — `--repo`, `--since`, `--save`, `--save-path`.
- `tests/unit/test_factory_report.py` (new): 31 tests.
- `docs/audits/0904-factory-report-boostgauge-2026-08-28.md` (new): the report run over the 2026-08-27 campaign window, with the reconciliation section the acceptance requires.

## What It Reads

All read-only. v1 adds no instrumentation — every number comes from a file another mechanism already writes, which is what makes the tool safe to run against a live campaign.

| store | written by | used for |
|---|---|---|
| `data/speedrun/telemetry/prompt-failures.jsonl` | `prompt_telemetry` (#2074) | failures per `stage:check`, fingerprint ranking |
| `data/speedrun/telemetry/heals.jsonl` | healing ledger (#2164) | heals by category/outcome, recurring targets |
| `data/speedrun/runs/preserved-branches.jsonl` | preservation record (#2355) | preservations by source |
| `data/speedrun/runs/run-issue*.log` | the pipeline | pinning, edit-script health, cap grants, review rounds, watchdog drift |
| `halt-evidence.json` | halt path (#2574) | halts per workflow:stage |

## Design Decisions

1. **The zero-fire denominator is declared, not inferred.** "Which gates never fire" needs the set of gates that *could* fire, and deriving it from observed records is circular — a gate that never fires is exactly the one absent from the data. `DECLARED_CHECKS` names the four `record_failure(s)` sites. `TestDeclaredChecks` greps the workflow tree in **both** directions: an undeclared recording site fails, and a declared pair with no site fails as a phantom (which would otherwise report as a permanently perfect gate that does not exist).

2. **Halt bundles are scoped to the target repo.** The halt path writes one copy of the bundle beside the state snapshot in `~/.assemblyzero/workflow_state` — shared across every repo the fleet has ever rolled — and one into the run's audit dir. Counting the shared directory unscoped attributes other repos' halts to this one. A bundle outside the target repo is kept only when its own `audit_dir` points back inside it. This was found by a test failing, not by reading the code.

3. **Run logs are read with `errors="replace"`.** The Python-side equivalent of `grep -a`. These logs carry stray bytes from model output, and GNU grep's binary detection silently suppresses matching lines in them — the 2026-08-27 near-miss, where real `[PINNING] refused:` lines were dropped while others printed. A fixture writes genuinely bad bytes and asserts events still count.

4. **Absence and zero are never collapsed.** A store that does not exist prints `| NO |`; a store that exists and is empty prints `0`. When *every* store is empty the shortlist says so first, so the zero-fire list below it reads as a finding about the window rather than about the gates.

5. **An unparseable `--since` raises.** Silently reading everything when the operator asked for a window would put a wrong denominator under every number that follows. This is the one condition the CLI refuses on.

6. **The watchdog elapsed is a floor, not a duration.** `[STAGE]` prints once a minute, so the last elapsed for a stage is the longest it was *observed* running; the stage ends between ticks. The module says so rather than presenting it as a measurement.

## Fail-Open Rulings (#2475 regime)

Six sites, each ruled in place. Five fail open toward inclusion (a record that cannot be dated is kept, because dropping it would silently shrink a printed denominator); `_under` fails open toward **exclusion**, because undercounting a halt is visible in the total while misattributing one is not.

## Known Limitations

- Halts before #2574 left no bundle, so their count is unrecorded rather than zero. The report states this instead of printing zero (#2587).
- A bundle with an empty `audit_dir` names no repo and is dropped (#2588).
- Run logs carry no header timestamp and no date in the filename, so windowing uses mtime. Verified correct for the campaign window: 4 of the 16 `#331` logs fall on 2026-08-27, and their refusals sum to exactly the reported 52.
