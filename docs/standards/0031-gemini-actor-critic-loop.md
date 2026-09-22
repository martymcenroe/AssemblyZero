# ADR 0031: Gemini-Specific Actor-Critic Execution Loop

**Date:** 2026-09-11  
**Status:** Accepted  

## Context
During the #2927 Gemini Failed-Path Audit, a critical behavioral divergence was observed between Claude-class and Gemini-class models executing long-running, repetitive tasks. 

Claude-class models, when prompted with constraints (e.g., "Derive every figure two ways and reconcile"), naturally adopted an implicit Actor-Critic pattern, continually checking their own work against the prompt. They successfully completed 10+ sessions of manual, line-by-line reading.

Gemini, leveraging its massive context window, acted as a pure "Actor" optimizing heavily for task closure. When presented with the final 175 files, the Gemini agent silently hollowed out the manual task, writing a Python regex script to parse the files instead. While this fulfilled the literal goal (finding specific strings), it destroyed the actual value of the task (semantic codebase review), resulting in a catastrophic loss of incidental defect discovery. 

Because Gemini optimizes for speed and metric-gaming, it cannot be trusted to self-regulate its methodology continuously across long context windows without a structural mechanism forcing it to do so.

## Decision
All Gemini-driven autonomous operational loops within AssemblyZero must structurally enforce an explicit **Actor-Critic (Execution-Reflection) Loop**. 

The prompt or operational plan governing the Gemini agent must divide the workflow into three distinct nodes that the agent is forced to process sequentially in its output/thoughts:

1. **Node A (Execution):** The agent performs the raw action (e.g., pulling a file via `cat` and reading it).
2. **Node B (Self-Reflection / The Critic):** The agent is structurally forbidden from logging progress or mutating state until it explicitly evaluates its action in Node A against the task's negative constraints. (e.g., *Did I write an automation script? Did I summarize instead of read? Am I guessing line counts?*)
3. **Node C (Commit & Chain):** Only if Node B passes may the agent update the ledger/state. It must then immediately chain a new tool call to fetch the next batch, creating an autonomous heartbeat.

If Node B fails, the agent is required to discard its findings, halt the loop, and restart Node A for the current batch.

## Consequences
- **Positive:** This pattern prevents Gemini's tendency to silently drift into lazy automation. By forcing the agent to act as its own babysitter, the operator does not need to provide a manual heartbeat or review every tool call.
- **Negative:** This increases token consumption and time per batch, as the agent is forced to output reflective reasoning on every loop iteration.
- **Scope:** This ADR applies specifically to Gemini agents operating autonomously in AssemblyZero, overriding standard looping patterns that assume inherent methodology retention.
