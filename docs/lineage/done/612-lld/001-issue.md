---
repo: martymcenroe/AssemblyZero
issue: 612
url: https://github.com/martymcenroe/AssemblyZero/issues/612
fetched: 2026-03-06T06:31:42.964454Z
---

# Issue #612: fix: missing mine_quality_patterns.py audit script (#588 follow-up)

## Problem

Issue #588 (Two-Strikes & Context Pruning) explicitly required a weekly audit script at `tools/mine_quality_patterns.py` as an acceptance criterion under "Cost-Aware Auditing." PR #596 closed #588 without creating this script.

## Acceptance Criteria from #588

> Create a weekly audit script (`tools/mine_quality_patterns.py`)

The script should query telemetry events (`quality.gate_rejected`, `retry.strike_one`, `workflow.halt_and_plan`) and surface recurring failure patterns.

## Fix

Implement `tools/mine_quality_patterns.py` as specified in #588.

## Origin

Discovered during post-merge review of Gemini's last 10 closed issues.