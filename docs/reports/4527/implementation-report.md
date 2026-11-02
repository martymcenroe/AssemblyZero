# Implementation Report: Codex is back (#4527)

Runbook 0958's two words: `status = "live"` under `[models.codex-sol]`, and `second-eye = "codex-sol"` under `[roles]`. The comment on `second-eye` saying how to go back is gone, because it no longer applies. The block at the top of `config/fleet-models.toml` still says how, so a later retirement is two words again.

`picture-maker` and `web-research` needed only the first word. The second puts the reader beside the judge on a different model from the judge again, as it was before Codex was retired.

The file is read when a tool runs, so nothing is deployed.
