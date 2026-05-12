# Tracked log writers audit (2026-05-12, #1151)

Audit run via `tools/audit_tracked_log_writers.py`. Captures the
state after PR landing #1151 fixes (HISTORY_PATH, WORKFLOW_AUDIT_FILE,
LLD_STATUS_FILE relocated to absolute paths under `~/.claude/assemblyzero/`).

## Bug shape

A module-level path constant that is **relative** AND points at a path
that is currently **tracked** in git. Every git worktree inherits the
tracked file; the moment the writer fires from a worktree, the worktree
is dirty, `git worktree remove` (no `--force`) refuses, and the worktree
leaks. This is the #1134 pattern.

## Fixed in this PR (#1151)

| Constant | Old path | New path | Tracked file removed? |
|---|---|---|---|
| `HISTORY_PATH` (`workflows/death/constants.py`) | `data/hourglass/history.json` | `~/.claude/assemblyzero/hourglass/history.json` | yes |
| `AGE_METER_STATE_PATH` (`workflows/death/constants.py`) | `data/hourglass/age_meter.json` | `~/.claude/assemblyzero/hourglass/age_meter.json` | n/a (was already untracked) |
| `WORKFLOW_AUDIT_FILE` (`workflows/testing/audit.py`) | `docs/lineage/workflow-audit.jsonl` | `~/.claude/assemblyzero/workflow-audit.jsonl` | yes |
| `LLD_STATUS_FILE` (`workflows/requirements/audit.py`) | `docs/lld/lld-status.json` | `~/.claude/assemblyzero/lld-status.json` | yes |

Plus #1134 (prior PR): `_DEFAULT_LOG_PATH` (`telemetry/cascade_events.py`)
already absolute at `~/.claude/assemblyzero/cascade-events.jsonl`.

## Remaining candidates flagged by the audit (manual review: NOT bugs)

| Constant | Path | Why not a bug |
|---|---|---|
| `TARGET_PATH` (`tools/fleet_set_permission_mode.py:55`) | `.unleashed.json` | Read target (config file), not a write target. False positive of the heuristic. |
| `FIXTURES_PATH` (`tests/unit/test_cascade_detector.py:44`) | `tests/fixtures/cascade_samples.json` | Test fixture read, not a write target. False positive. |
| `_DEFAULT_CONFIG_PATH` (`assemblyzero/hooks/cascade_patterns.py:20`) | `data/unleashed/cascade_block_patterns.json` | Config file read at hook init, not a write target. False positive. |

The audit heuristic flags any relative-path constant pointing at a
tracked path — it does not yet distinguish read vs. write call-sites.
A future refinement could narrow the heuristic by parsing for
`open(path, 'w'/'a')` / `path.write_text` / `path.write_bytes` /
`json.dump(..., path)` to drop the 3 false positives above. For now,
the operator dismisses them by inspection.

## Out of scope for this PR (separate follow-up)

- `inventory.py` (`assemblyzero/nodes/inventory.py`) defaults `repo_path`
  to `"."` (cwd). When a test imports and fires this with no override,
  it writes to `{cwd}/docs/0003-file-inventory.md` — same dirty-worktree
  outcome via a different mechanism (cwd-relative function default, not
  module-level constant). Fix shape is different (remove the cwd default,
  require explicit `repo_path`). Filed as a separate issue.

## How to regenerate this audit

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/audit_tracked_log_writers.py
```

Output goes to `audit_tracked_log_writers_results.tsv` (gitignored).
Summary printed to stdout.
