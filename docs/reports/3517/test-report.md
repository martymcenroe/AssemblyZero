# Test Report — agy in both seats (#3517)

## What was run

From the main checkout's venv, against this worktree
(`PYTHONPATH=<worktree>`, `--rootdir <worktree>`, `-p no:cacheprovider`):

```
tests/unit/test_agy_both_seats.py tests/unit/test_requirements_cli.py
tests/unit/test_cli_gates_syntax.py tests/unit/test_precheck_predicts_the_roll.py
tests/unit/test_preflight_transport.py tests/unit/test_implement_from_lld_cli.py
tests/unit/test_implementation_spec_workflow.py
365 passed, 1 warning in 12.65s
```

Those seven files are every test that parses the three tools' arguments,
reads the orchestrator's defaults through the pre-check, or exercises the
preflight on the standalone specs.

```
poetry run ruff check <the eight changed .py files>
Found 2 errors.
```

Both are `F841` and both exist on `main` before this change
(`tools/run_requirements_workflow.py:952` `compiled`,
`tests/unit/test_requirements_cli.py:279` `result`), confirmed by running ruff
on the main checkout's copies. They are #3471's F841 tranche, not this PR's
lines, and are left as found.

## The new tests fail on the old sources

The nine changed source and doc files were stashed by name, the two test
files run, and the stash popped:

```
tests/unit/test_agy_both_seats.py tests/unit/test_requirements_cli.py
6 failed, 72 passed, 1 warning in 1.21s
FAILED ...test_agy_both_seats.py::TestTheStandaloneDefaultsAreAgy::test_the_lld_workflow_drafts_and_reviews_on_agy
FAILED ...test_agy_both_seats.py::TestTheStandaloneDefaultsAreAgy::test_the_implementation_workflow_reviews_on_agy
FAILED ...test_agy_both_seats.py::TestTheStandaloneDefaultsAreAgy::test_the_spec_workflow_drafts_and_reviews_on_agy
FAILED ...test_agy_both_seats.py::TestTheReasonOnRecord::test_the_orchestrator_config_no_longer_rests_on_the_crash
FAILED ...test_agy_both_seats.py::TestTheReasonOnRecord::test_the_two_adrs_are_accepted
FAILED ...test_requirements_cli.py::TestArgumentParsing::test_default_values
```

The three that pass on both (`test_the_defaults_match_the_orchestrator`,
`test_the_default_resolves_to_a_permitted_pro_model`,
`test_an_override_to_claude_still_parses`) pin things this PR relies on and
does not change: the orchestrator already had agy in both seats, the id is a
permitted Pro model, and an override still parses.

## What each new test shows

| Test | Shows |
|---|---|
| `test_the_lld_workflow_drafts_and_reviews_on_agy` | `run_requirements_workflow.py` with no seat flags: `gemini:3.1-pro` in both. |
| `test_the_implementation_workflow_reviews_on_agy` | `run_implement_from_lld.py` with no seat flag: reviewer `gemini:3.1-pro`; the revisor reuses it (#1072). |
| `test_the_spec_workflow_drafts_and_reviews_on_agy` | `run_implementation_spec_workflow.py`: both seats. |
| `test_the_defaults_match_the_orchestrator` | The lld, spec and impl stages of `get_default_config()` say the same. |
| `test_the_default_resolves_to_a_permitted_pro_model` | `gemini:3.1-pro` maps to a Pro id, not Flash, not on `FORBIDDEN_MODELS`. |
| `test_an_override_to_claude_still_parses` | `--drafter claude:sonnet --reviewer claude:opus` is honoured. |
| `test_the_orchestrator_config_no_longer_rests_on_the_crash` | `config.py` no longer says #1431 "remains the reason", and names #3519 and #3517. |
| `test_the_two_adrs_are_accepted` | ADR 0232 and 0233 status lines begin `Accepted`. |

`test_requirements_cli.py::test_default_values` asserts the new defaults where
it asserted the old.

## Not verified

- A real run with the new defaults. The mock rehearsal (sequence step 9)
  stays offline by construction, so it cannot exercise agy; the first real
  standalone run under these defaults is the operator's to start and watch,
  per the #3502 work order, and it will meet the #3506 transport probe first.
- The full unit tier was not run for this PR: the change is five argparse
  defaults, three comments and two status lines, and the seven files above
  are their only readers in `tests/`. CI runs the full tier on the PR.
