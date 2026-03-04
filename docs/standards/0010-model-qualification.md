# Standard 0010: Model Qualification Protocol

**Status:** Active
**Created:** 2026-03-03
**Issue:** #400

## Purpose

Systematic, evidence-based protocol for qualifying LLM models for workflow use. The Gemini review gate is the invariant quality bar — models change, the bar doesn't.

## Core Metric

**Cost per approval** = total_cost / approved_count

This is the single most important metric. A cheaper model that needs more iterations may still cost more per successful outcome.

## Qualification Protocol

### Prerequisites

- Model scorecard tool: `poetry run python tools/model_scorecard.py`
- Baseline data: at least 5 runs with the incumbent model
- The `--drafter` flag on the LLD workflow to specify the candidate model

### Steps

1. **Select 3 closed issues** with known Opus/incumbent results (pick varying complexity: simple bug fix, moderate feature, complex multi-file change)

2. **Run LLD workflow** with the candidate model on each:
   ```bash
   cd /c/Users/mcwiz/Projects/AssemblyZero
   PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
       --type lld --issue NUMBER --repo /c/Users/mcwiz/Projects/TARGET_REPO \
       --drafter MODEL_SPEC --yes
   ```

3. **Run scorecard** to compare:
   ```bash
   poetry run python tools/model_scorecard.py --since YYYY-MM-DD
   ```

4. **Decision rule** (based on `cost_per_approval`):

   | Candidate vs Incumbent | Decision |
   |------------------------|----------|
   | Candidate $/approval < Incumbent $/approval | **Qualify** — use for all drafting |
   | Candidate $/approval ≤ 2x Incumbent $/approval | **Qualify with caveats** — simple issues only |
   | Candidate $/approval > 2x Incumbent $/approval | **Not ready** — retest next release |

### Re-qualification Triggers

- New model release (e.g., Claude 4.7, Gemini 4)
- Pricing change on any qualified model
- Observed quality regression (3+ consecutive review failures)

## Task Routing Matrix

### Use Sonnet / cheaper model (when qualified)

- Triage, exploration, code reading
- Bug fixes with clear reproduction steps
- Single-file changes following existing patterns
- LLD drafting (IF qualified by scorecard)
- Implementation from detailed LLD specs

### Use Opus / premium model

- Architecture decisions, system design
- Multi-file refactors touching >5 files
- Ambiguous requirements needing interpretation
- Novel patterns with no codebase precedent
- Plan mode exploration

### The Decision Test

> "Is there a mechanical quality gate (Gemini review, test suite, linter) that will catch failures?"
>
> **Yes** → try cheaper model. **No** (only human judgment) → use premium model.

## Scorecard Usage

```bash
# Full scorecard against all data
poetry run python tools/model_scorecard.py

# Filter to recent data
poetry run python tools/model_scorecard.py --since 2026-02-01

# Compare specific workflow node
poetry run python tools/model_scorecard.py --node design_lld

# Machine-readable output
poetry run python tools/model_scorecard.py --json
```

### Reading the Output

```
Model                        | Runs  | Avg Cost | Approved | Appr Rate |    $/Appr | Avg Tokens | Tok Eff
gemini-3-pro-preview         |   336 |  $0.0312 |       48 |     14.3% |     $0.22 |      9,500 |  0.43x
claude:sonnet                |     6 |  $0.1800 |        4 |     66.7% |     $0.27 |     52,100 |  0.38x
```

- **$/Appr**: The key comparison metric. Lower = better value.
- **Appr Rate**: Higher is better but misleading alone — a model that only drafts (never reviews) will have 0% approval rate.
- **Tok Eff**: Output/input ratio. Higher means more output per input token.

## Immediate Cost Savings (Zero Risk)

These routing changes require no qualification — they have mechanical quality gates:

1. **Triage/exploration**: Use Sonnet in Claude Code for reading code, searching, asking questions
2. **Implementation from LLD**: Test suite catches failures. Use Sonnet.
3. **Simple bug fixes**: Clear repro → clear fix → tests verify. Use Sonnet.

Conservative estimate: 30-40% cost reduction from routing alone, before any LLD drafting qualification.

## Revision History

| Date | Change |
|------|--------|
| 2026-03-03 | Initial version (#400) |
