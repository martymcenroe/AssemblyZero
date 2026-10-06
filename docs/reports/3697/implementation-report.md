# Implementation report: #3697, #3698, #3699, #3700

## Retired Gemini CLI residue removed

- `.claude/tools/gemini-model-check.sh` (#3697): deleted. Nothing called it. It looked for the deleted `gemini-retry.py`, then fell back to `gemini -p`. `.claude/project.json.example` loses the three entries that named it: the generated-files row, the LLD-review usage line, and the `chmod` step. The rest of that file's `// GEMINI INTEGRATION` block is left for #3703.
- `tools/gemini-model-check.sh` (#3698): deleted rather than rewritten. It grepped a deleted `tools/gemini-rotate.py` and a `claude-4.6` string that never matches, so it exited 1 on every run. The `Key Files` line in `CLAUDE.md` no longer names it. `.agents/rules/repo-claude-md.md` is regenerated from `CLAUDE.md` with `agy_repo_rules.py --apply`.
- `assemblyzero/core/gemini_client.py` (#3699): the comment above `TRANSPORT_LABEL` now says the `gemini` binary was on PATH when the 2026-08-16 misreading happened and is no longer installed on Windows or WSL. Nothing else in the block changed.
- `tools/model_scorecard.py` (#3700): every old Gemini row is removed. `gemini-3-pro-preview` and `gemini-2.0-flash` are on `FORBIDDEN_MODELS`, and `gemini-2.5-pro-preview` is an id the pipeline never sends. They are replaced by the two ids the pipeline does send, `gemini-3.1-pro-high` and `gemini-3.1-pro-low`, priced at zero because agy runs them on the subscription. A comment over the rows states both rules.

Left as they are: the three prompt templates under `.claude/templates/gemini-prompts/`, which still name the deleted wrapper and forbidden ids (#3702); the dead and forbidden ids in `GeminiProvider.MODEL_MAP` (#3710); and the dated documents under `docs/`, which quote the script's name as history.
