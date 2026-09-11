# 0032: Autonomous Subagent Relays for Infinite Context Execution

**Status:** Accepted

## Context

Large-scale autonomous operations, such as exhaustive codebase audits (e.g., the 450,000+ line Check 10 in AssemblyZero), require LLMs to maintain state and execute operations for many hours. 

However, LLM context windows (even massive 2M+ token contexts) are mathematically bound. Continuing to push large files, script outputs, and reasoning blocks into a single accumulating context window eventually results in severe reasoning degradation. The agent begins to hallucinate file reads, skip explicit instructions, or crash entirely. 

Previous mitigations relied on human-in-the-loop `/handoff` checkpoints:
1. The agent stops after N files.
2. It dumps its exact position and state to a ledger.
3. The human operator executes `/handoff` to spin up a fresh session with a cleared context window.

This approach breaks true autonomy, forcing operators to act as babysitters for long-running batches.

## Decision

We will implement the **Autonomous Subagent Relay** pattern to handle context window exhaustion seamlessly without human intervention.

1. **The Orchestrator:** The parent agent (the Orchestrator) NEVER performs the heavy reading or execution. It maintains a near-empty context window. Its only job is to index the global target queue (e.g., using `find` to create a tracking file) and manage subagents.
2. **The Relay Spawn:** The Orchestrator uses the `invoke_subagent` tool to spawn a zero-context, short-lived clone (using the `self` type). It passes an explicitly hard-bounded subset of the task (e.g., "Read lines 1-50 from `target_files.txt`, append your results to `ledger.md`").
3. **The Subagent Loop:** The Subagent runs its actor-critic loop on the small batch of files. Because its scope is tightly constrained, it completes its task long before experiencing context degradation.
4. **The Handoff Ping:** When the Subagent finishes its batch, it uses the `send_message` tool to report exactly one line back to the Orchestrator (e.g., `"BATCH COMPLETE: 1-50"`), and then terminates.
5. **Reactive Wakeup:** The Orchestrator remains idle. The `send_message` ping automatically wakes the Orchestrator. The Orchestrator reads the message, updates its internal pointer, and immediately spawns the *next* subagent ("Read lines 51-100...").

## Consequences

* **Infinite Execution:** The system can chew through infinite lines of code without a context crash and without user intervention.
* **Zero Reasoning Degradation:** Every batch is processed by a pristine context window, eliminating late-session hallucinations.
* **State Safety:** Ledger appends happen safely per-batch.

## Implementation Guide (Operator Invocation)

To trigger this pattern, the operator should instruct the agent with an overarching goal, explicitly authorizing the Subagent Relay:

```
/goal Execute the Autonomous Subagent Relay pattern to audit the tests/unit/ directory. 
- Save the file list to a text file.
- Spawn subagents to process 50 files at a time.
- Chain the subagents continuously using the reactive wakeup system until all files are processed.
```
