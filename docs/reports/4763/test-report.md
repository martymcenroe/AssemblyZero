# Test report: #4763 (work in progress)

Status: no tests run yet for this change. The unit tier has not been run, so no pass or fail counts are claimed.

Planned:

- T1: `resolve_project_path()` with `new_repo_root` configured, with no config file, with a file holding only `new_repo_root`, and with an invalid-JSON file (stops before creating anything and names the file).
- T2: an offline scaffold into a tmp root with the new-repo root and the AssemblyZero root both pointed at tmp paths; no written file names `/mnt/c/Users/mcwiz/Projects`, `/c/Users/mcwiz/Projects` or `C:\Users\mcwiz\Projects`, and `PROJECT_ROOT` is the tmp path.
- The default-case `project.json` equals today's values.
- Config tests for per-key optional validation and `load_error`.
- T3 (end to end on `/home/mcwiz/Projects`) waits for the operator and is tracked in a follow-up issue the coordinator is filing.
