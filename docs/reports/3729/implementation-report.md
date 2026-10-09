# Implementation Report: every workflow checks the alert channel before its first node (#3729), and no tier sees the machine's `AZ_` environment (#4160)

The rule is ADR 0236: every failure alerts the operator, so a run whose alert channel cannot work refuses to start. #3728 built `check_alert_channel()`; nothing called it.

## #3729, requirements 1 and 2

- **`assemblyzero/core/alert.py`: `require_alert_channel(entry)`.** It calls `check_alert_channel()`, which resolves the sender and the AWS credentials without sending. On `AlertDeliveryError` it writes `ERROR [preflight] <entry>: the operator alert channel cannot work, so the run refuses to start: <reason>` to stderr and raises `SystemExit(1)`. It does not alert: the channel is what is broken. It returns the sender when the channel works.
- **Called right after argument parsing, before any other work,** in every entry point that runs a workflow:

| Entry point | Runs |
|---|---|
| `tools/run_requirements_workflow.py` | the LLD and issue graphs (every mode: `--all`, `--resume`, `--resume-review`, `--select`) |
| `tools/run_implement_from_lld.py` | the testing graph; before #4150's merge-driver check |
| `tools/run_implementation_spec_workflow.py` | the spec graph |
| `tools/orchestrate.py` | the orchestration graph and, in process, every sub-workflow |
| `tools/run_janitor_workflow.py` | the janitor graph, `--silent` too |
| `tools/run_scout_workflow.py` | the scout nodes, `--offline` too |
| `tools/replay_run.py` | the spec graph, replayed |
| `assemblyzero.workflows.death.hourglass.run_death` | the hourglass graph; the death skill's entry |

  Mock, dry and offline runs check too (requirement 2: the rule has no carve-out). A mock run's halts alert like any other.
- **Found by the census:** the issue named the LLD and implementation workflows "and every other workflow entry point that runs a graph". The six others came from a census: every `create_*_graph` and `build_*` graph builder under `assemblyzero/workflows/`, and every caller of each. `speedrun_roll.py` starts `orchestrate.py` as a child process, which is covered.

## The test tiers

- **`alert_channel_ready`** (`tests/conftest.py`, autouse, every tier) replaces `alert.check_alert_channel` with a stand-in returning `tests@example.invalid`. No test depends on the machine's sender or AWS credentials. `test_alert.py` is exempt and tests the real function. Requirement 2 named `tests/unit/conftest.py`; it lives in the shared `tests/conftest.py` because the e2e tier runs mock workflows too, the lesson of #3724's CI failure.
- **`child_env_with_alert_channel(base)`** is for a test that runs an entry point as a child process, which the stand-in cannot reach. It sets a stand-in sender and dummy AWS keys; boto3 resolves those with no network call, and nothing is sent because the child stops before any alert. The full tier found the one test that needed it: `test_orchestrate_refuses_without_the_driver`.

## #4160, the inherited environment

- **`AZ_ENVIRONMENT`** in `tests/conftest.py` names the eight `AZ_` variables the code reads. **`no_az_environment_from_the_machine`** unsets them all in every tier. It replaces #4150's `no_merge_driver_from_the_machine`, which unset only one.
- **`test_az_environment_isolation.py`** parses every tracked `.py` under `assemblyzero/` and `tools/` with `ast`, collects each string constant of the form `AZ_<UPPER>`, and fails in both directions: a name the code reads that the set lacks, or a set member the code never reads. It is a parser over string constants, not a pattern match over text.
- **Why this PR:** #3729 makes every entry point read `AZ_OPERATOR_EMAIL_FROM`, which this machine exports and CI does not. Without #4160 it would have repeated PR #4159's CI failure for that variable. Measured: with the old conftest, the stand-in tests read this machine's real sender address.

## Loud-failure compliance (standard 0034)

| Failure path | Loud | Logged | Stops | Alerts |
|---|---|---|---|---|
| alert channel cannot work at start | `ERROR [preflight]` on stderr, with the cause | the line names the entry point and the cause; there is no run to record yet | `SystemExit(1)` before any node | no: the channel is what failed, as #3729 requires |

## Baselines

- **Loud-failure baseline:** unchanged at 317. No broad handler was added; `require_alert_channel` catches `AlertDeliveryError` only and raises.
- **Fail-open baseline:** regenerated for the denominator only: sites examined 9708 to 9710, findings unchanged at 538.
- **Halt sites:** unchanged (152).

## Requirement 3 and AC3

Met before this PR, on both machines. The fleet environment deploy exports `AZ_OPERATOR_EMAIL_FROM`, and `tools/send_test_alert.py` delivered from Ubuntu at 5:05 PM Central and from Windows at 8:03 PM Central on 2026-10-08. Both are recorded in #3729's comment of 8:04 PM that day. A later comment there says the Windows send had not run; the earlier comment's Windows output contradicts it.
