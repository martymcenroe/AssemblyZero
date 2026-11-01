# 0958: The fleet model switch

`config/fleet-models.toml` names, for each role a model plays, the model that plays it. Every tool asks it, through `assemblyzero/fleet_models.py`, and no tool names a model itself. The file is read when a tool runs, so an edit takes effect at the next run, with no deploy.

## Change a role's model

Change the role's word under `[roles]`, then check the file:

```
python assemblyzero/fleet_models.py --check
```

The check prints every role and exits 1 when any role has no live model.

## Retire a model

Set its `status` to `"retired"` under `[models]`. Every role on it now stops its tool, naming the role and the model, until the role is pointed at a live model. Keep the entry: going back is one word.

## Go back to Codex

Two words:

1. Under `[models.codex-sol]`, `status = "live"`.
2. Under `[roles]`, `second-eye = "codex-sol"`.

The first word alone brings back `picture-maker` and `web-research`, which only Codex can play.

## What a dead model does

A role that cannot be played raises `ModelSwitchError`, which is built on `SystemExit`. A tool's `except Exception` around its call cannot swallow it, so the run stops, exits non-zero and records nothing. Nothing falls back to another model, on purpose: a fallback hides the failure this exists to show.

## Read it from another repository

A repository outside this one keeps a thin `fleet_switch.py` that finds `assemblyzero/fleet_models.py` beside its checkout and hands every call to it. It holds no logic and no table. That repository's CI has no AssemblyZero, so its `conftest.py` sets a small fake table.

## Add a role

Add one line under `[roles]`, with a comment saying what the role does. Name what it does, never which tool uses it: this file is public.
