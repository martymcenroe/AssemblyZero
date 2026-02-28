# Brief: The City Watch — Regression Guardian

**Status:** Active
**Created:** 2026-02-01
**Updated:** 2026-02-28
**Effort:** Medium
**Priority:** High
**Tracking Issue:** None

---

## Problem

With 3,788 tests across 165 test files, there is no automated way to detect regressions introduced by non-workflow changes (dependency updates, manual edits, environment drift). Tests pass at PR time, but nothing verifies the full suite on `main` on a schedule.

Concrete evidence: `test_route_after_finalize_continue` failed silently after a graph refactor — no workflow caught it because the failure happened between workflow runs. Dependabot automation (Issue #351) is blocked without a regression baseline: you cannot safely auto-merge dependency PRs if you don't know whether `main` is already broken.

## What Already Exists

- **pytest** — full test suite with markers (`integration`, `e2e`, `adversarial`, `expensive`, `rag`)
- **CI on PRs** — tests run on pull requests but not on schedule
- **Issue #351** — Dependabot automation, blocked on a health gate
- **Issue #94** — Janitor workflow (complementary: Janitor finds stale artifacts, Watch finds test failures)

## The Gap

No scheduled test runner. No baseline snapshot. No health gate that other automation can query. Without these, Dependabot automation and any future CI/CD pipeline have no way to know if `main` is healthy.

## Proposed Solution

A Python script (not a LangGraph workflow — this is deterministic, no LLM needed) that:

1. **Runs the full test suite** — `pytest --tb=short -q` with configurable markers to exclude (`--skip-markers expensive,rag`)
2. **Compares against a baseline** — a JSON file (`~/.assemblyzero/watch-baseline.json`) containing expected pass/fail/skip counts per test file
3. **Reports regressions** — new failures (tests that passed in baseline but fail now) vs known failures
4. **Exposes a health status** — exit code 0 (healthy) or 1 (regression detected), plus a JSON status file other tools can read
5. **Optionally creates GitHub issues** — one issue per new regression, labeled `regression`

### CLI Interface

```
poetry run python tools/run_watch.py                    # Run and compare to baseline
poetry run python tools/run_watch.py --update-baseline  # Snapshot current results as new baseline
poetry run python tools/run_watch.py --status           # Print current health (read-only)
poetry run python tools/run_watch.py --json             # Machine-readable output
```

### Health Gate Protocol

Other tools query health via exit code or JSON file:
- Dependabot automation checks `run_watch.py --status` before merging
- Orchestrator can optionally gate on Watch health before starting a pipeline

## Integration Points

- **Dependabot automation** (`dependabot-workflow-automation.md`) — Watch health gate is a prerequisite
- **Orchestrator** (`tools/orchestrate.py`) — optional pre-flight health check
- **GitHub Actions** — scheduled cron trigger (e.g., nightly or every 6 hours)

## Acceptance Criteria

- [ ] Runs full test suite and produces pass/fail/skip counts per file
- [ ] Compares against baseline and identifies new regressions
- [ ] Exit code 0 when healthy, 1 when regressions detected
- [ ] `--update-baseline` snapshots current state
- [ ] `--status` reads without running tests
- [ ] JSON output mode for machine consumption
- [ ] Does not require an LLM or API credentials to run

## Dependencies & Cross-References

- **Issue #351** — Dependabot automation (depends on Watch for health gate)
- **Issue #94** — Janitor workflow (complementary — Janitor cleans artifacts, Watch monitors test health)
- **Brief: `dependabot-workflow-automation.md`** — direct downstream dependency
- **Brief: `workflow-commit-checkpoints.md`** — checkpoints ensure code exists to test
