```markdown
# ADR 0015: Age Transition Protocol

| Field | Value |
|-------|-------|
| Status | Accepted |
| Issue | #535 |
| Date | 2026-02-17 |
| Deciders | Handsome Monkey King (orchestrator) |

## Context

AssemblyZero's documentation drifts from codebase reality as issues are closed and features evolve. Closed issues accumulate structural debt — each one changes what the system *is*, but documentation only updates when someone remembers to do it. Nobody remembers.

Prior to this ADR, drift detection was limited to the Janitor's link and orphan probes (Issue #94), which catch broken references but not *factual inaccuracies*. A README claiming "12+ specialized AI agents" when 36 persona TOML files exist is not a broken link — it is a lie the documentation tells with a straight face.

The gap: no mechanism existed to (a) measure how much the codebase has changed since documentation was last reconciled, (b) detect factual claims that contradict code reality, or (c) systematically reconcile documentation with the system as it actually exists.

## Decision

Implement DEATH as an age transition mechanism using the **Hourglass Protocol** — a LangGraph state machine that detects documentation drift, measures accumulated change via a weighted age meter, and produces reconciliation reports or applies fixes.

### Core Concepts

**Age Meter.** Each closed GitHub issue contributes a weighted score based on its labels. Bug fixes score 1 (they fix reality but don't change the shape). New components score 5. Architecture changes score 10 (the old map is now wrong). When the cumulative score crosses a threshold (default: 50), DEATH arrives — the sand has run out.

**Drift Scoring.** Independent of the age meter, drift scanners compare documentation claims against codebase reality using regex heuristics and glob verification. Numeric claims ("12+ agents") are checked against actual file counts. Inventory entries are verified against the filesystem. Architecture docs are scanned for negation claims ("does not use X") contradicted by existing code.

**Three Triggers.** DEATH arrives through three independent paths:

1. **Meter threshold** — accumulated issue weight crosses the configured threshold
2. **Summon** — orchestrator invokes `/death` directly
3. **Critical drift** — drift score exceeds 30.0 (approximately 3 critical findings)

**Two Modes.** The protocol operates in two modes:

- **Report** (default) — walk the field, produce a reconciliation report, change nothing
- **Reaper** — walk the field, apply fixes with orchestrator confirmation gate

### State Machine Phases

The Hourglass Protocol executes five phases as a LangGraph StateGraph:

1. **Walk the Field** — run drift scanners against README, inventory, and architecture docs
2. **Harvest** — produce reconciliation actions and generate ADRs for architecture drift
3. **Archive** — move stale artifacts to legacy directories
4. **Chronicle** — update README and documentation to describe current reality
5. **Rest** — reset the age meter, increment the age number, record history entry

### Weight Table

| Label Category | Weight | Rationale |
|---------------|--------|-----------|
| bug, fix, hotfix, patch | 1 | Fixes reality, doesn't change shape |
| enhancement, feature | 3 | Adds capability |
| persona, subsystem, new-component, new-workflow | 5 | Changes what the system *is* |
| foundation, rag, pipeline, infrastructure | 8 | Changes how everything else works |
| architecture, cross-cutting, breaking | 10 | The old map is now wrong |
| (unlabeled) | 2 | Conservative default |

### Persistence

- `data/hourglass/age_meter.json` — local per-developer state (gitignored)
- `data/hourglass/history.json` — shared audit trail (tracked in git)

### Integration Points

- **Janitor probe** — `drift` probe registered in the Janitor's probe registry, enabling drift detection during routine sweeps
- **Skill interface** — `/death` command provides orchestrator access to report and reaper modes

## Alternatives Considered

### 1. Time-Based Triggers Only

Trigger reconciliation on a fixed schedule (e.g., every 2 weeks). Rejected because time alone doesn't correlate with drift magnitude — two weeks of bug fixes create less drift than one architecture change.

### 2. Manual Documentation Reviews

Rely on the orchestrator to periodically review documentation. Rejected because this is exactly the status quo that produced the drift problem. Humans forget. Mechanisms don't.

### 3. LLM-Based Semantic Comparison

Use an LLM to semantically compare documentation against code. Rejected for v1 because it introduces API cost per scan, non-deterministic results, and latency. The regex/glob heuristic approach is deterministic, free, and fast. LLM-based analysis can be added as a future enhancement for claims that heuristics cannot verify.

### 4. Git Diff-Based Detection

Analyze git diffs to detect documentation that should have been updated alongside code changes. Rejected because it requires real-time hook integration and cannot detect pre-existing drift that accumulated before the mechanism was installed.

## Consequences

### Positive

- Documentation drift is detected automatically via weighted scoring and heuristic verification
- The age meter provides a quantitative measure of accumulated change, replacing subjective "feels stale" assessments
- Report mode enables safe inspection before any modifications occur
- Reaper mode requires explicit confirmation, preventing accidental documentation changes
- History file creates an audit trail of DEATH visits across the project's lifetime
- Integration with the Janitor probe system enables drift detection during routine maintenance sweeps

### Negative

- Heuristic-based drift detection has limited coverage — only numeric claims, inventory entries, and negation patterns are verified in v1
- The age meter weight table requires calibration and may need adjustment as the project evolves
- False positives from regex matching may produce noise in drift reports (mitigated by confidence scores)

### Neutral

- ADR generation is limited to `architecture_drift` category findings; other categories produce reconciliation actions but not ADRs
- The `/death` skill uses `--force` flag for scripted reaper invocation, bypassing the confirmation gate

## References

- Issue #535: DEATH as Age Transition — the Hourglass Protocol
- Issue #94: Lu-Tze: The Janitor (probe infrastructure)
- Issue #114: Age Meter retroactive scoring calibration
- Terry Pratchett, *Reaper Man*: "WHAT CAN THE HARVEST HOPE FOR, IF NOT FOR THE CARE OF THE REAPER MAN?"
```
