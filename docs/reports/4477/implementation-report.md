# Implementation report: #4477, #4478, #4482

## Runbook 0905 is retired (#4477)

`docs/runbooks/0905-gemini-credentials.md` was entirely about the retired API-key rotation and told the reader to run two deleted tools. It keeps its number and now says it is retired, what replaced it, and what happens when a Gemini call fails. The runbook index says so too.

Also removed: the four inventory rows for rotation skill docs that do not exist, and the section of `wiki/Tools-Reference.md` on `assemblyzero_credentials.py`, a tool that is deleted and was the last live mention of the rotation wrapper.

## The verification page states the fleet's model rules (#4478)

`wiki/Gemini-Verification.md` approved a forbidden model and forbade the Flash family, the only one the fleet may use. Its tables now come from `config/fleet-models.toml`: the approved table gives the two models the roles use for reviews and preflight, and the forbidden table is the file's `[policy]` list. The prose, the diagram, the sample record and the flow diagram no longer say "Gemini 3 Pro".

The old table's reasons are gone. The file gives a reason only for Argon, so the page gives only that one.

## An auth halt points at `agy` (#4482)

`assemblyzero/core/recovery_plan.py`: the `auth` recommendation sent the operator to a credentials file that belongs to the retired rotation. It now says to check that `agy` is signed in to the subscription.
