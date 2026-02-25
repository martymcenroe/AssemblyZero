---
repo: martymcenroe/AssemblyZero
issue: 358
url: https://github.com/martymcenroe/AssemblyZero/issues/358
fetched: 2026-02-25T07:51:28.479258Z
---

# Issue #358: Auto-approve safety: prevent cascading task execution

## Problem

When Claude finishes a task and asks "Should I start the next issue? 1. Yes 2. No", unleashed auto-approves this. Claude cascades through multiple tasks without human review — rewriting code, skipping review gates, burning API budget.

Gemini does the same thing: "I solved issue 1. Should I do issue 2? 1. Yes 2. No" — auto-approved, entire day wasted, everything has to be thrown away.

The permission system treats ALL prompts equally. It can't distinguish between "approve this git command" and "should I rewrite your entire codebase?"

## Root Cause

The model's "what should I do next?" prompts use the same UI affordance (numbered options) as permission prompts. Any auto-approval system that presses Enter or sends "1" cascades through these.

## Desired Behavior

When Claude finishes a task, it should ask **"What do you want to work on next?"** as an open-ended question — NOT offer a yes/no auto-approvable choice. The human decides next steps, not the model.

## Approach Options

1. **CLAUDE.md rule**: "After completing a task, ask 'What would you like to work on next?' — NEVER offer numbered options for next steps." (Advisory only, lowest confidence)
2. **Pre-command hook**: Detect "should I continue/proceed" patterns in output and block auto-approval
3. **Unleashed pattern**: Add "Should I" / "Do you want me to" to a BLOCK pattern list (not auto-approve list) — when matched, unleashed does NOT press Enter, forcing human input
4. **Friction logger enhancement**: Log these as "cascade_risk" events so we can measure how often it happens

## Context

From 2026-02-13 audit of the instruction chain. The permission system is designed for command approval, but gets co-opted by the model for workflow decisions. Three months of experience confirms this is a recurring problem with real cost (wasted API budget, thrown-away work).

## References
- unleashed issue #12 (sentinel local LLM safety gate)
- This session's instruction chain audit