---
repo: martymcenroe/AssemblyZero
issue: 642
url: https://github.com/martymcenroe/AssemblyZero/issues/642
fetched: 2026-03-07T02:20:14.780387Z
---

# Issue #642: fix: reduce retry prompt context more aggressively

## Problem

Pruned retry prompts already drop \`completed_files\` but still send the full LLD. On retry 2, this wastes tokens on context that hasn't helped. Each retry at 80K+ tokens costs \$0.05-0.10 for context that's already been seen.

## Fix

Implement tiered context pruning in \`build_retry_prompt()\`:
- Retry 1: Current behavior (LLD + target file spec + error)
- Retry 2: Only the relevant file spec section from LLD + error + previous attempt snippet

This could cut retry prompt size by 50-60%.

## Impact

~$0.05-0.10 savings per retry × multiple retries per workflow = meaningful cumulative savings.

## Origin

Cost audit of API spend (~\$25 every other day).