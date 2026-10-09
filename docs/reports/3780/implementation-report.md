# Implementation Report: the core/ package under standard 0034 (#3581 step 5)

The rule is ADR 0236 and standard 0034. This PR takes the `assemblyzero/core/` module issues from the #3581 sweep, highest harm first. Each module's sites are fixed, tested, and marked in ledger 0908.

## Scope

The modules a target run passes through, in order of harm. Harm means a failure the run reads as success on the model path, the verdict path or the resume path; failures that lose a record come after.

Not in this PR, because no target run passes through them:
- `fail_open_audit.py` (#3775), an audit tool;
- `gate_registry.py`'s halt-site scanner (#3776), an audit tool;
- `scripted_provider.py` (#3792), used only by mock rolls and replays.

## Also carried

- `tests/unit/test_alert_channel_at_start.py::test_the_implementation_workflow` passes a temporary `--repo`, and its stand-ins fail if reached (#4161). Measured against the old source, it had run a mock implementation run into the worktree.

## Modules

Filled in module by module below as each lands in this branch.
