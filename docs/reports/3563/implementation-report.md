# Implementation Report: seat registry, profile loader, resolver, and every node migrated (#3563, with #3553)

Parent: #3562. The coder seat (#3553) lands inside this change, as #3562's order asks.

## What was asked

Every model-calling site on a workflow path resolves its model through one registry of seats and one profile file per run: precedence flag, then `AZ_MODEL_PROFILE`, then `<target>/.assemblyzero/models.toml`, then the built-in `gemini.toml`; the profile snapshotted into `state["model_profile"]` and read from there on resume; `--seat <name>=<spec>` on every entry point with `--drafter` / `--reviewer` mapped onto it; `mock.toml` replacing the nodes' inline mock branches; and the coder moved off its hardcoded `claude:` spec, per the operator's ruling of 2026-09-24 that the coder runs on Gemini too.

## What changed

### The registry and the loader: `assemblyzero/core/seats.py` (new)

| Piece | What it does |
|---|---|
| `SEATS` | The closed list of seventeen dotted seat names, each with the site it serves |
| `check_spec` | Parses a spec with `parse_provider_spec`, refuses an unknown provider or model, resolves the model id (`GeminiProvider.MODEL_MAP`, `ClaudeCLIProvider.MODEL_MAP`), and applies `FORBIDDEN_MODELS` to every provider, exact match then family, naming the seat and the model |
| `parse_profile` / `load_profile` | TOML via `tomllib`; refuses unknown top-level keys, unknown seats, and a profile with no `[defaults]` spec that leaves a seat unnamed; the snapshot carries name, source, sha256, defaults, seats, overrides, and how it was selected |
| `select_profile_path` / `load_run_profile` | The precedence above. A name resolves against `assemblyzero/profiles/`, a path is read as given. `--mock` selects `mock.toml` over every source |
| `apply_overrides` | Per-seat overrides and an effort override for every seat, each checked like the file |
| `resolve(state, seat)` | The snapshot when state has one; otherwise `_legacy_profile(state)`, the one place the old per-node choices survive for one release (the legacy keys, the mock branches, #2375's escalation map) |
| `using_profile` / `resolve_active` | A context variable for calls no state reaches. N4 enters the run's profile once, so the coder's helpers need not carry state |
| `add_profile_arguments` / `profile_from_args` | `--models` and `--seat` on the three standalone tools; under `--mock` any real override is named and dropped, so a mock run stays offline |
| `default_spec(seat)` | For library signatures that need a default spec: read from `gemini.toml`, never restated |

### The profiles: `assemblyzero/profiles/` (new)

- `gemini.toml`: every seat `gemini:3.1-pro`, effort `max` (ADR 0234).
- `claude.toml`: the pre-law defaults seat by seat, per #3563's first comment: `claude:sonnet` for the analyze and draft seats, `claude:opus` for the escalation, the reviewers and the spec tool, `claude:sonnet` for `impl.code`, `claude:haiku` for `impl.code.small` and the triage summary, `claude:sonnet` at effort `low` for N4c, and Gemini for the four seats that were Gemini before the law, with a comment saying why.
- `mock.toml`: `mock:lld` for `requirements.draft` (#3533), `mock:review` for the reviewers and contract fidelity, `mock:draft` for `spec.draft`, `mock:mock` elsewhere.

### The nodes

| Site | Before | Now |
|---|---|---|
| N0c `analyze_requirements.py:537` | `state.get("config_drafter", "gemini:3.1-pro")`; escalation from `GATE_DRAFTER_ESCALATION` | `requirements.analyze`; the retry asks `requirements.analyze.escalation` when it names a different spec |
| N1 `generate_draft.py:333-342` | a mock branch choosing `mock:lld` / `mock:draft`, else `config_drafter` | `requirements.draft`; the preflight sees `requirements.review` |
| N3 `review.py:180-183` | mock branch, else `config_reviewer`; effort from `config_effort` | `requirements.review`, with the seat's effort |
| Spec N2 `generate_spec.py:84, 405-408` | `DEFAULT_DRAFTER` constant; mock branch | `spec.draft`; the constant is gone |
| Spec N5 `review_spec.py:50, 360-366` | `DEFAULT_REVIEWER` constant; mock branch | `spec.review`; the constant is gone |
| Impl N1 `review_test_plan.py:481-487` | `config_reviewer`, mock branch | `impl.test_plan.review` |
| Impl N1.5 `revise_test_plan.py:236` | `config_drafter` | `impl.test_plan.revise` |
| **N4, the coder** `claude_client.py:236`, `routing.py` | `get_provider(f"claude:{model or 'opus'}")`; routing returned `HAIKU_MODEL` or `CLAUDE_MODEL` | routing returns a seat (`impl.code` or `impl.code.small`); `call_claude_for_file` resolves it under the active profile; a bare model id with no provider prefix is refused as non-retryable; `HAIKU_MODEL` is gone. `implement_code` enters the run's profile around its unchanged body |
| N4c `augment_tests.py:609` | the coder's routing plus `AUGMENT_EFFORT = "low"` | `impl.augment_tests`, whose effort the profile carries (`low` in `claude.toml`) |
| N7.5 `adversarial_gemini.py:69-74`, `adversarial_node.py:143` | `ADVERSARIAL_MODEL_ALIAS`, `ADVERSARIAL_PROVIDER_SPEC` | `impl.adversarial`; `resolve_adversarial_model(spec)` checks the seat's spec, Gemini tiers as before and every other provider through `check_spec` |
| Contract fidelity `contract_fidelity.py:1000, 1068` | `drafter_spec="gemini:3.1-pro"` defaults | `requirements.contract_fidelity` under the active profile |
| Visual gate `modify.py:134` | `TRANSLATION_PROVIDER` constant | `visual_gate.translate` |
| Scout `scout/nodes.py:265` | bare `GeminiClient()`, whose model was `REVIEWER_MODEL` | `scout.analyze` through `get_provider` |
| Triage summary `orchestrator/stages.py:436` | `get_provider("claude:haiku")` | `orchestrator.triage_summary` |
| `tools/audit_deferred_scope.py:597` | a bare `claude --print` subprocess | `tools.audit_deferred_scope` through `get_provider`, so it now runs inside the provider layer's hook isolation (ADR 0232) and recording |
| Telemetry `analyze_requirements.py:728`, `validate_mechanical.py:1821`, `validate_test_plan.py:135` | `drafter_model=state.get("config_drafter", "")` | the resolved seat's spec |

`orchestrator/config.py` reads its stage drafter and reviewer specs from `gemini.toml`'s seats, and `precheck.DEFAULT_DRAFTER`, which reads the orchestrator's lld drafter, is therefore `requirements.draft` one hop removed. `requirements/config.py` and `requirements/state.py` take `None` defaults and fill them with `default_spec`.

### The entry points

`tools/run_requirements_workflow.py`, `tools/run_implementation_spec_workflow.py`, `tools/run_implement_from_lld.py`: `--models` and `--seat`; `--drafter`, `--reviewer` and `--effort` default to `None` and override the profile only when given (`--seat` wins over an old flag for the same seat); the profile is printed as a seat table at run start and snapshotted into state; the three legacy keys are written from it. On the LLD tool, `--drafter` also sets the escalation seat by #2375's map, and `--type issue --mock` drafts from `mock:draft`.

### State declarations

`model_profile: dict` on `RequirementsWorkflowState`, `ImplementationSpecState`, `TestingWorkflowState` and `AdversarialNodeState`. LangGraph drops undeclared keys at node boundaries (the lesson of #2926), so without these a checkpoint would not carry the snapshot.

## Decisions made here

- `precheck.DEFAULT_DRAFTER` is derived through the orchestrator's lld drafter, which is `requirements.draft`; #3563 requirement 7 names that seat. The gate it predicts reads `requirements.analyze`; both are `gemini:3.1-pro` in every built-in profile except `claude.toml`, where both are `claude:sonnet`.
- A hand-built state with no snapshot resolves through `_legacy_profile`, one function in `seats.py`, so tests and tools that still set `config_drafter` keep their behaviour for one release and no node carries the branch.
- Under `--mock`, a real spec passed beside it is dropped with a printed line, never honoured.
- `tools.audit_deferred_scope` in `claude.toml` is the profile's default, `claude:opus`; the tool's `claude --print` named no model, so the CLI's own default ran, and that is not readable from this repository.

## What did not change

- `GeminiClient` is still built directly by the preflight probe (`core/preflight.py`), which checks the transport, not a seat.
- `lld/assembly_node.py` (`ChatAnthropic`, no graph registers it) and `nodes/anthropic_provider.py` (no caller) are dead code, untouched.
- The orchestrator does not yet snapshot a profile of its own; `--models` on `orchestrate.py` and `speedrun_roll.py` is #3566.
- The per-call record is #3565.
