# Test Report: seat registry, profile loader, resolver, and every node migrated (#3563, with #3553)

## New tests

`tests/unit/test_seats.py`:

| Class | Owns | What it pins |
|---|---|---|
| `TestTheLoader` | #3563 T1 | seventeen seats; a valid file round-trips; an unknown seat, a forbidden model (under any provider), a spec with no colon, an unknown provider, an unknown top-level key, and a profile with no default that leaves a seat unnamed all fail closed naming what is wrong; an effort override reaches every seat |
| `TestPrecedence` | #3563 T2 | with all four levels present: the flag wins, then the environment, then the target's `models.toml`, then `gemini.toml`; a name resolves against the built-in directory and an unknown one fails listing them; `--mock` wins over every source; a resumed state reads its snapshot after the file on disk changed |
| `TestTheBuiltInProfiles` | #3563 T3 | `gemini.toml` resolves all seventeen seats to `gemini:3.1-pro` at `max` (`gemini-3.1-pro-high`, `GeminiProvider`); `claude.toml` equals the seat table in #3563's first comment, `impl.code.small` resolving to `claude:haiku` and N4c at `low`; `mock.toml` is all `MockProvider`; the legacy keys come from the profile |
| `TestTheEntryPoints` | #3563 T4, T5 | `--mock` selects `mock.toml` on the implementation tool and drops a real `--seat` by name; the issue workflow's mock drafts from `mock:draft`; `--drafter claude:opus` moves only the drafter seats and the escalation; `--seat` wins over the old flag; `--models claude` selects the built-in |
| `TestHandBuiltState` | requirement 5 | a state with no snapshot resolves as the nodes' old branches did, and a snapshot wins over the legacy keys |
| `TestEveryModelChoiceIsASeat` | umbrella T1, #3563 requirement 5 | an `ast` walk of `assemblyzero/` and `tools/` finds no module-level provider-spec constant, no `get_provider` with a literal or f-string spec, no provider-spec parameter default, and no read of `config_drafter` / `config_reviewer` / `config_effort` outside `core/seats.py`; a planted file shows the walk sees each kind. No regular expression is used |

`tests/unit/test_implement_code_routing.py`, rewritten for #3553: the routing picks a seat by the four rules (twelve cases); the coder resolves to `gemini:3.1-pro` under `gemini.toml` and with no profile in hand, and to `claude:sonnet` / `claude:haiku` under `claude.toml`; the resolved seat's spec is what `get_provider` receives; no seat means `impl.code`; an explicit spec wins; a bare model id is refused without building a provider; the seat's effort rides along unless one is given; `generate_file_with_retry` passes the routed seat; N4 enters the run's profile.

## Updated tests

| File | Why |
|---|---|
| `test_adversarial_gemini.py` | the two removed constants: the default client is the `impl.adversarial` seat of the default profile; forbidden and unknown aliases are passed as specs; a forbidden model under another provider is refused; the spec checked is the spec built |
| `test_agy_both_seats.py` | the defaults moved from argparse to the profile: each tool's default arguments resolve every seat it reaches to `gemini:3.1-pro`, the coder's included |
| `test_requirements_cli.py` | the seat flags default to not given; `--mock` with a real `--drafter` stays offline (`mock:lld`); `--drafter claude:sonnet` moves the drafter seats and the escalation to `claude:opus`; a forbidden drafter (`gemini:2.5-flash`, which the old test used as ordinary data) fails closed |
| `test_requirements_gate_escalation.py` | `fake:model` and `bogus:spec` are refused at load now, so the no-escalation case uses `gemini:3.1-pro` and the broken-target case a valid spec whose transport will not build; a new test shows `bogus:spec` fails closed at load |
| `test_n4c_keeps_the_suite_and_bounds_output.py` | N4c's `low` effort comes from `claude.toml`'s `impl.augment_tests`; no effort given is the seat's (`max`), not an absent flag |
| `test_implementation_edit_script_fix.py` | the fake call takes `seat=` |
| `test_scout_nodes.py`, `test_visual_gate_live_resume.py` | the seats go through `get_provider`, not a bare `GeminiClient` or a module constant |
| `tests/conftest.py` | an autouse fixture removes `AZ_MODEL_PROFILE`, so a profile exported on the machine never changes the suite |

## Runs

Full unit tier, from the worktree with the main checkout's interpreter and `PYTHONPATH` set to the worktree, on `6c311b86` plus this change, no other pytest session running:

```
2 failed, 10748 passed, 21 skipped, 7 deselected, 5 xfailed, 13 warnings in 681.78s (0:11:21)
FAILED tests/unit/test_section_ten_carries_tests.py::TestAgainstEveryRecordedDraft::test_it_refuses_only_the_two_runs_that_moved_their_tests
FAILED tests/unit/test_section_ten_carries_tests.py::TestAgainstEveryRecordedDraft::test_every_other_draft_passes
```

The two are #3468's pair (a unit test reading another repository's working tree), red on `main` before this change.

The first full run of this branch had 83 failures. Most came from `check_spec` refusing providers and models it did not know, which requirement 2 does not ask for; it now fails closed only on an unparseable spec, a seat outside the registry, and a forbidden model. The others were the gate registry and the halt-site walker finding moved sites, which led to the registered `implement_code_under_profile` wrapper and to seat errors held and raised inside each node's existing "Invalid drafter" handler, and test fakes that did not accept `seat=` or `effort=`.

`tools/audit_fail_open.py --check`: PASS after `--write-baseline`, whose only change was renumbering one existing `generate_draft` handler from index 0 to 1.

`ruff check` on every changed file: the nine findings reported all predate this branch.
