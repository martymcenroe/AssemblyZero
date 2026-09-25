# Implementation Report — agy in both seats (#3517)

Parent: #3502. The operator's directive of 2026-09-24, recorded on #3517 by
the supervising session at 11:08 PM Central: Gemini (agy) drafts and
validates, for the LLD workflow and the implementation workflow; Claude is
out of both seats; reason, budget constraints on the Anthropic account. That
directive superseded the issue's original body ("the Claude side keeps
drafting") and lifted the hold placed after ADR 0233.

## What changed

Defaults, all to `gemini:3.1-pro`, which `GeminiProvider.MODEL_MAP` resolves
to `gemini-3.1-pro-high`, a Pro identifier not on `FORBIDDEN_MODELS`:

| Tool | Flag | Was |
|---|---|---|
| `tools/run_requirements_workflow.py` | `--drafter` | `claude:sonnet` |
| `tools/run_requirements_workflow.py` | `--reviewer` | `claude:opus` |
| `tools/run_implement_from_lld.py` | `--reviewer` (the revisor reuses it, #1072) | `claude:opus` |
| `tools/run_implementation_spec_workflow.py` | `--drafter` | `claude:opus` |
| `tools/run_implementation_spec_workflow.py` | `--reviewer` | `claude:opus` |

These now match the orchestrator's `StageConfig` defaults for the lld, spec
and impl stages, and the library's own `RequirementsConfig` defaults
(`requirements/config.py:93-94`), which the CLI had been overriding. The two
"custom providers" examples in the LLD tool's docstring and epilog showed
`--drafter gemini:2.5-flash`, a forbidden model; they now show an all-Claude
override, which is the override that still means something.

The spec workflow is included: the directive names the LLD and implementation
workflows, the spec stage sits between them, the orchestrator already ran it
on agy in both seats, and the reason given was budget, which the spec drafter
on Opus spends against. If the operator meant the spec tool to stay on Claude,
that is one default to put back.

N4, the coder inside the implementation workflow, is not a seat either flag
names. It runs through the Claude CLI as before. The directive said "drafter
and reviewer seats" and "matching the orchestrator's existing defaults", and
the orchestrator's impl stage codes on Claude with agy in both seats; this PR
reads the directive as written and says so here so it can be corrected.

The reason on record (#3519's fact):

- `orchestrator/config.py:44-48` said the Claude `json_schema` crash (#1431)
  "remains the reason this defaults to Gemini rather than Claude". On
  2026-09-24 one nested call with the schema the crash was reported against
  succeeded on haiku and on opus. The comment now says that, and cites #1434
  and the directive.
- `requirements/precheck.py` carried the same claim in its `DEFAULT_DRAFTER`
  note; reworded the same way.

ADR status:

- ADR 0232 (nested `claude -p` calls load no user hooks): Accepted. The
  operator directed the outcome in #3504 and the flag shipped in PR #3543.
- ADR 0233 (what `agy` can do inside the workflow): Accepted. The operator
  ruled #3517 with the finding in view; the flag shipped in PR #3545; the
  blast-radius statement stands as the record.

Docs: `docs/standards/0020-test-plan-quality.md` §4.4 names the new reviewer
default; `core/preflight.py`'s `preflight_for_specs` docstring says the
default run now gets the agy probe (#3506) and an all-Claude override still
does not.

## What did not change

- `--mock` runs. The preflight and every model call are skipped under
  `mock_mode` inside the nodes, so the rehearsal stays offline with these
  defaults.
- `RequirementsConfig`, the orchestrator config values, `FORBIDDEN_MODELS`,
  `resolve_adversarial_model`. N7.5's transport is #2926's PR.
- `core/recovery_plan.py` still advises `--reviewer claude:opus` when agy is
  down; that is an override, and it is the right one.

## Not in this PR

- The #3517 body's fourth requirement, a skipped adversarial review visible
  in the run report and the PR body, is delivered by the #2926 PR opened in
  the same session.
- The CLAUDE.md line naming the product (#3519) is the operator's.
