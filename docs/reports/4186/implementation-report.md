# Implementation report: #4186

## The defect

`tools/new_repo.py` reads its post-create hooks from `~/.claude/new-repo-post-create-hooks.txt`, under the home of the side that runs it, and took a missing file to mean no hooks. A run from a side without the list printed "None listed", ran none of the hooks the other side runs, and still ended in `[SUCCESS]`.

## The change (R1)

- The hook stage of a GitHub run (reached only when the repository was created and the push succeeded) checks for the list first. A missing list prints `FAILED: no post-create hook list at <path>. Create it; an empty file runs no hooks on purpose (#4186).` and runs no hook.
- `failed_steps()` takes a keyword `hook_list_missing: Path | None = None` and names `post-create hook list (missing: <path>)` after branch protection, in run order. The run then prints `[FAILED]`, alerts and exits 1 through the existing path from #4136. The default `None` leaves every existing caller unchanged.
- A list that exists but holds no hooks, blank or comment lines only, is unchanged: "None listed", and not a failure.
- The stage now reads `DEFAULT_POST_CREATE_HOOKS` when it runs and passes it to `read_post_create_hooks`. Before, it called the reader with no argument, so the reader used its parameter default, fixed when the module was imported, and a patched path was never the one read.
- `read_post_create_hooks()` still returns `[]` for a missing file. Its docstring and the constant's comment now say the run reports a missing file, and ADR-0216 section 8, which said "no file means no hooks", says the same.
- A `--no-github` run never reaches the stage and is unaffected.

## R2 and R3

Both were already met on this machine since 2026-10-21: Ubuntu's hook list exists, and so does the encrypted file of the read-only CI token that the post-create hook decrypts. R3's record is tracked in a private repository's issue. Test 2, the operator's own `new-repo` run from Ubuntu, is recorded on #4186 by the coordinator.

## Tests

Test 1 is covered by three `failed_steps` tests and four `main()` runs of the hook stage; `test-report.md` maps them. One existing test that drives the GitHub path now points the hook list at an empty file.

## Ruff

`poetry run ruff check` on `tools/new_repo.py` and the three changed test files finds 22 on the branch and 22 on the primary at 94cc7239, the same findings in `tools/new_repo.py` once line numbers are set aside. The branch adds none.
