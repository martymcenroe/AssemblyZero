# Test Report: N4.5 runs the hook in the target's environment and halts when it fails (#3705, #3706)

## Before the change

A mock implementation run on 2026-10-06 against a target whose `.unleashed.json` carries `poetry run python -m <package>.<module>`:

```
Executing post_implement_command: poetry run python -m <package>.<module>
[WARN] post_implement_command failed (exit code 1)
Stderr: .../virtualenvs/assemblyzero-tools-...-py3.14/bin/python: Error while finding module specification for '<package>.<module>' (ModuleNotFoundError: No module named '<package>')
```

on all three iterations, and the run ended `Status: SUCCESS`.

## Tests added or changed

`tests/unit/test_mechanical_hooks.py`, rewritten:

- `test_hook_environment_drops_the_workflows_virtualenv`: `VIRTUAL_ENV`, `POETRY_ACTIVE` and the virtualenv's `bin` and `Scripts` entries are gone; everything else stays; the input mapping is untouched.
- `test_hook_runs_without_the_workflows_virtualenv_and_stages_its_output`: a probe hook run under a fake activated virtualenv sees `VIRTUAL_ENV` unset and the fake `bin` off `PATH`; its output file is staged; the route is `N5_verify_green`.
- `test_a_failed_hook_halts_with_its_exit_code`: `exit 3` yields `error_message` carrying `exit code 3` and the command; the route is `HALT`.
- `test_an_unreadable_config_halts`: `{not json` halts naming `.unleashed.json`.
- `test_no_hook_means_no_update`: no hook, or no file, is no update.
- `test_the_node_carries_no_fail_open_tag`.

`tests/unit/test_testing_graph_halts_through_halt.py`: `route_after_mechanical_hooks` added to the routing assertions and `N4_5_mechanical_hooks` to HALT's expected inbound set.

## Runs

- Targeted: `tests/unit/test_mechanical_hooks.py tests/unit/test_testing_graph_halts_through_halt.py tests/unit/test_interaction_matrix.py tests/unit/test_completeness_gate.py tests/unit/test_wave2_reliability.py tests/unit/test_gate_registry.py tests/unit/test_factory_report.py`: see the closing comment on #3706 for the line.
- `tools/audit_fail_open.py --check --strict`: `PASS -- 308 files, 9481 sites examined, no new fail-open, denominator matches.`
- Full unit tier in the worktree: on the closing comment.
