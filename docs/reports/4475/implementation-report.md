# Implementation report: #4475, #4476, #4479

## An LLD run's resume line carries its type (#4475)

`assemblyzero/core/recovery_plan.py`: `build_resume_command` gives a requirements run with an issue number `--type lld`. The tool requires `--type` and refused the old line.

## `--resume` says what it does (#4476)

`tools/run_requirements_workflow.py`: every graph in the tool is compiled with no checkpointer, so no run saves state to start from. `run_resume_workflow` announced "resuming..." and then ran the whole brief again.

- It now prints that it runs the brief again from the start, and names the audit directory it adds to. That directory is the one `create_audit_dir` reuses for the slug.
- `checkpoint_exists` and the tool's `get_checkpoint_db_path` are removed, because nothing writes that database. The `--resume` refusal for a brief with no audit directory stays, and still names `--brief`.
- The `--resume` help text and the banner say the same thing. The flag keeps its name, because the recovery plan's printed line uses it.
- Ledger 0908's row for the removed handler is updated in place.

Making `--resume` a real resume is not part of this issue.

## A brief run's evidence bundle names the brief (#4479)

`assemblyzero/core/halt_evidence.py`: the bundle now carries `brief`, and `_run_name` gives the heading and the draft issue body the issue or the brief. An issue run's text is unchanged, and a bundle written before this reads as before.

## Left out

#4481 was in this batch and is closed as won't-do: ADR 0236 says no class of failure is carved out, and a refused dry run is a failure.
