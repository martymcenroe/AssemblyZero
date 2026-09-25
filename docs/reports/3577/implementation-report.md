# Implementation Report: each node's calls recorded under its own seat (#3577)

Parent: #3562. Found by the offline rehearsal of 2026-09-25 at 2:40 AM Central, on `main` at `00bf2b31`.

## What was wrong

The per-call record (#3565) names the seat resolved last before a provider is built, when that seat's spec is the one being built. Four nodes resolved a second seat after their own:

- N1 (`generate_draft.py`) resolved `requirements.draft`, then `requirements.review` for the preflight.
- Spec N2 (`generate_spec.py`) resolved `spec.draft`, then `spec.review`.
- N0c (`analyze_requirements.py`) resolved `requirements.analyze`, then `requirements.analyze.escalation`.
- N4c's calls went through `call_claude_for_file`, which resolved `impl.code` before building.

The mock rehearsal recorded N1's call with no seat. Under `gemini.toml`, where every seat shares one spec, those calls would have been recorded under the other seat, silently.

## What changed

- N1 and spec N2 resolve the reviewer's seat first and the drafter's seat last.
- N0c resolves the escalation seat first and the analysis seat last, and resolves the escalation seat again immediately before building the escalation retry's provider.
- N4c passes `seat="impl.augment_tests"` to both of its `call_claude_for_file` calls.

No behaviour other than the record changes: each node builds the same provider from the same spec as before.
