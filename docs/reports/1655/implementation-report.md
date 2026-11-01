# Implementation report: #1655, #4443

## A halted brief run resumes its brief (#4443)

- `assemblyzero/core/recovery_plan.py`: `build_resume_command` chooses by what the run has. A run with an issue number is unchanged. A requirements run with a `brief_file` and no number gets `--type issue --resume <brief>`, with the path quoted so a space stays one argument. Anything else gets a sentence saying the run has neither, in the same way an unknown workflow does. The saved plan, the printed block and the evidence bundle's resume line all come from this builder.
- `RecoveryPlan.print_summary`: a run with no issue number prints `Brief:` and its run key, where it printed `Issue: #0`.
- `tools/run_requirements_workflow.py`: `run_resume_workflow` called `relative_to` on the brief and crashed on one outside the target repository, which a run may take. It now keeps that path as given.

`--resume` was read, not assumed: it requires `--type`, finds the brief under `ideas/active/` or the repository root, and refuses with a named reason when there is no audit directory. It also reruns the brief from the start, which #4476 tracks.

## No live document names the deleted retry tool (#1655)

- Removed `docs/skills/0604-gemini-retry.md`, `0628c-gemini-retry-cli.md` and `0628p-gemini-retry-prompt.md`, and their rows in `docs/index.md` and `docs/0003-file-inventory.md`. The inventory's one-row "Gemini Integration" section went with its row. Two more rows named `0625c` and `0625p` files that do not exist.
- `docs/runbooks/0801-orchestrator-workflow.md`: section 4 and the Key Commands row now give the requirements workflow, which is where the review runs. The old block also wrote to `/tmp` and pinned a forbidden model.
- `docs/runbooks/0957-agy-never-elevates-the-pipelines-own-tool-less-agent.md`: "To repeat it" now gives the direct `agy` command, from the probe's working directory.
- `docs/skills/0704c-Ops-Health-Review-Prompt.md`: the sample suggestion no longer names the tool.
- `wiki/Tools-Reference.md`: the Gemini Tools section described three deleted tools and now describes the `agy` transport. The Gemini Reviews section gives a workflow command.
- `wiki/Gemini-Verification.md`: the submission block, the model verification section and the credential section no longer describe the tool or its rotation.

Left as they are: `docs/lld/done`, the dated reports and audits, `wiki/Lessons-from-the-Turtle.md`, which quotes the tool as history, and the January draft `docs/lld/drafts/spec-0101-implementation-readiness.md`.

Filed, not repaired here: #4475 (an LLD run's resume line lacks `--type`), #4476 (`--resume` reruns the brief), #4477 (runbook 0905 and the sibling deleted tools), #4478 (the verification page's model tables), #4479 (the evidence bundle's `#0` heading).
