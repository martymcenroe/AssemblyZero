# Implementation report: #3702, #3703, #3710

## The Gemini review prompt templates (#3702)

- `.claude/templates/gemini-prompts/{lld-review,issue-review,implementation-review}.txt`: line 3 no longer says the request arrives "via gemini-model-check.sh wrapper" and no longer names the model the reviewer runs as. Two of the three named the forbidden `gemini-3-pro-preview`, and the third named the retired `gemini-3.1-pro-preview`. The line now names no model, so it cannot go stale again. Nothing else in the templates changed.

## `project.json.example` (#3703)

- `.claude/project.json.example`, the `// GEMINI INTEGRATION` block: the prerequisites no longer name the retired Gemini CLI, `gemini-3-pro`, or `jq`, which only the deleted wrapper used. They now name agy on the subscription (ADR 0220) and point at `config.REVIEWER_MODEL` and `config.FORBIDDEN_MODELS`. The description says the generator creates review prompts, since it creates no tools.

## `GeminiProvider.MODEL_MAP` (#3710)

- `assemblyzero/core/config.py`: new `AGY_GEMINI_MODELS`, the single declared set of Gemini ids the provider may send. It holds `gemini-3.1-pro-high` and `gemini-3.1-pro-low`, the two Pro models `agy models` listed on 2026-10-06.
- `assemblyzero/core/llm_provider.py`: `gemini-2.5-pro`, `gemini-2.5-flash` and `gemini-3.1-flash-preview` are absent from that catalog. The `2.5-pro` and `pro` aliases now resolve to `gemini-3.1-pro-high`, as #1764 did for the Pro previews, so older configs keep working. The `flash`, `2.5-flash` and `3.1-flash-preview` aliases are removed: Flash is forbidden for governance, and pointing a Flash alias at a Pro model would mislead. The class docstring lists the aliases the map carries and names `3.1-pro` as the default.
- `assemblyzero/workflows/requirements/config.py`: the docstring example spec is `gemini:3.1-pro` instead of `gemini:2.5-pro`.

Behaviour of the removed Flash aliases, checked against the callers. The seats profile check falls back to `gemini-<alias>` for an alias the map does not carry, so `gemini:2.5-flash` still resolves to `gemini-2.5-flash`, and `gemini:flash` now resolves to `gemini-flash`. Both are on `FORBIDDEN_MODELS`, and both are still refused. The adversarial client refuses an alias missing from the map before it builds any transport. `GeminiProvider("flash")` now fails at construction with "Unknown Gemini model". Before, it constructed and failed later, when `GeminiClient` refused the id.
