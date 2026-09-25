# Test Report: the coder has a seat, and it runs on Gemini (#3553)

Landed inside #3563; the full run is in `docs/reports/3563/test-report.md`.

## The coder's tests

`tests/unit/test_implement_code_routing.py`:

| Test | #3553 requirement |
|---|---|
| `test_routing_picks_the_seat` (twelve cases) | the four routing rules now pick `impl.code.small` or `impl.code` |
| `test_the_default_profile_puts_the_coder_on_gemini` | 2: `gemini:3.1-pro` for both coder seats under `gemini.toml` |
| `test_no_profile_in_hand_means_the_built_in_default` | 2: with no profile entered, the precedence falls to `gemini.toml`, never to Claude |
| `test_the_claude_profile_reproduces_the_pre_law_split` | `claude.toml` is the old Sonnet/Haiku split exactly |
| `test_the_seat_reaches_the_provider_spec` | 1: the resolved seat's spec is what `get_provider` receives |
| `test_no_seat_means_impl_code_under_the_profile` | 4: no seat and no model is `gemini:3.1-pro` under the default, so the Claude CLI provider is never built |
| `test_a_bare_model_id_is_refused` | 4: `claude-haiku-4-5-20251001` with no prefix is refused before any provider is built |
| `test_an_explicit_spec_wins_over_the_seat`, `test_the_seat_effort_rides_along_unless_given` | the override and the effort |
| `test_generate_file_with_retry_passes_the_routed_seat` | N4's file loop hands the routed seat on |
| `test_the_n4_node_enters_the_run_profile` | N4 makes the run's snapshot the active profile |

`tests/unit/test_agy_both_seats.py::TestTheStandaloneDefaultsAreAgy::test_the_implementation_workflow_runs_every_seat_on_agy`: with no flag, the implementation tool resolves `impl.code`, `impl.code.small`, `impl.augment_tests`, `impl.adversarial` and both test-plan seats to `gemini:3.1-pro`.

`tests/unit/test_agy_sandbox_args.py` (unchanged) pins `--sandbox` on the `agy` argv the Gemini coder now uses.

## Requirement 3

The writer spec in the run record and the PR body is #3565's per-call record, which the umbrella orders after this change.
