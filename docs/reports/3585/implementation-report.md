# Implementation Report: Step 1, loud failure and no-API-key ADRs (#3585)

## What was done
Drafted and proposed ADR 0235 (Loud Failure) and ADR 0236 (No API Key) under `docs/adrs/`. The operator accepted them.

## Decisions made here
- ADR 0235 defines the four properties of a failure: loud, logged with details, stops dependent processing, alerts the operator.
- ADR 0236 completely bans Gemini and Google API keys and their SDK dependencies.
