# Implementation Report: one file chooses each role's model (#4450)

`config/fleet-models.toml` names, under `[roles]`, the model that plays each role, and under `[models]`, how each model is reached and whether it is live. `assemblyzero/fleet_models.py` is its only reader. It uses the standard library alone and imports nothing from the package, so a tool outside this environment loads the one file by path.

A role that cannot be played raises `ModelSwitchError`, built on `SystemExit`, so a tool's `except Exception` around its model call cannot swallow it. The message names the role and the model. Nothing falls back to another model.

`REVIEWER_MODEL`, `FORBIDDEN_MODELS`, `AGY_GEMINI_MODELS` and `DEFAULT_PROBE_MODEL` read the file, and so do the dead aliases in `GeminiProvider.MODEL_MAP`, so the default profile's `gemini:3.1-pro` seats follow the `workflow` role. The profile keeps its alias because tests and persisted states name it. The live `3.8-flash-*` aliases stay literal: each maps a spelled name to its own id.

`REVIEWER_MODEL` no longer reads the environment, which would have been a second switch. `CLAUDE_MODEL` is gone: nothing read it.

Runbook 0958 says how to change a role, retire a model and go back to Codex.

`picture-maker` and `web-research` stay on Codex, marked retired, so `--check` exits 1 today. That is intended: no other model can play them, and nothing picks a substitute for the operator.
