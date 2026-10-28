# Implementation Report: #4222

A read-only safety review of `docs/runbooks/0956-compare-model-profiles-on-boostgauge.md` (2026-10-28) found its text disagreeing with the code in several places. Its decision: the runbook stays in AssemblyZero, changed. Each change below is read from the code the review cited.

- **R1 (line 19).** The `--fresh` paragraph names everything the reset does: it closes the issue's open PRs, deletes its pipeline branches locally and on origin, removes its worktrees, reopens the issue, and archives only the lineage and the LLD and spec working copies. It cites #4215 for the path that can lose pushed commits.
- **R2 (line 5).** The second roll reuses an LLD and spec settled under the first, because settlement does not hash the profile, and builds on the first roll's base. So the table is not a comparison of the models and nothing else.
- **R3 (line 33).** Exit 93 fires only when step 2 left resumable state. After a successful step 2, the already-rolled gate stops the launch first. Issues 331 and 332 spend one model call before either refusal, and the launch's sweep, janitor and doc sync can push.
- **R4 (line 57).** The copy is named `new-model.toml`, as in the command, and the runbook says never to name it `models.toml`, which every later roll without `--models` would read.
- **R5 (line 65).** A Gemini alias outside `GeminiProvider.MODEL_MAP`, and an `anthropic:` spec, pass the start check and fail on first use, after the reset.
- **R6 (step 3).** The Claude roll starts nested Claude sessions, so only the operator runs it, and it is refused with exit 91 while his spend lock is on.
- **R7.** Until #4215 is repaired, `git ls-remote --heads origin issue-2 2-lld issue-4 4-lld` comes before a `--fresh` roll, and rolls run one at a time (#4217). Step 4 also says each row counts every run under the profile (#4220).
- **R8.** `assemblyzero/profiles/gemini.toml`'s description names the model that runs, `gemini-3.8-flash-high`, in place of "Gemini 3.1 Pro".
