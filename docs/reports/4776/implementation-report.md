# Implementation report: #4776, #4777, and #4775 R1, R2, R4

## The defects

A repository that `tools/new_repo.py` creates on Ubuntu's ext4 disk, under `/home/<user>/Projects`, sits apart from AssemblyZero, which stays on the C: drive. Three things assumed they were siblings or that every path was a Windows one.

- #4775: `project.json`'s `inherit_from` holds AssemblyZero's root in its Windows spelling, and `tools/assemblyzero-generate.py` opened it with `Path(...)`. On Ubuntu `C:\...` is a relative file name, so the templates folder was never found.
- #4776: `.claude/templates/commands/cleanup.md.template` reached AssemblyZero as `{{PROJECT_ROOT}}/../AssemblyZero`, and `.claude/project.json.example` as `../AssemblyZero`. Beside a repository on ext4 there is no such folder.
- #4777: the new repository's CLAUDE.md wrote the raw `project_path` on its "Project Root (Windows)" line, a POSIX path when the run is on Ubuntu.

## #4775 R1: the generator reads `inherit_from` in any spelling

`inherit_from_path(value, *, windows, mount_root="/mnt", distro="Ubuntu")` in `tools/assemblyzero-generate.py` returns AssemblyZero's root spelled for the side it runs on.

| Spelling in the file | On Ubuntu (`windows=False`) | On Windows (`windows=True`) |
|---|---|---|
| `C:\X`, `C:/X`, `/c/X`, `/mnt/c/X` | `/mnt/c/X` | `C:\X` |
| plain POSIX `/home/u/X` | `/home/u/X` | `\\wsl.localhost\Ubuntu\home\u\X` |
| `\\wsl.localhost\<distro>\home\u\X`, `//wsl.localhost/<distro>/...` | `/home/u/X` | `\\wsl.localhost\<distro>\home\u\X` |
| a relative value | as written | as written |

A trailing separator is dropped. A relative value is returned as written, so it is read against the working directory as before. `mount_root` is where Ubuntu mounts the Windows drives; the tests point it at a temporary folder so drive spellings open a temporary AssemblyZero. `main()` calls it with `windows=os.name == "nt"`. Existing `project.json` files holding `C:\...` work unchanged on both sides.

## #4775 R2: what `new_repo.py` writes

`project_json_content()` keeps writing `config.assemblyzero_root()`: `C:\...` for an AssemblyZero on a drive, its POSIX path for one on ext4. R1 reads both on both sides, and every repository created so far holds the same spelling, so there was no reason to change it. A comment there now says so.

## #4775 R4

`.claude/project.json.example` says `inherit_from` is AssemblyZero's root and lists the spellings the generator reads.

## #4775 R3 waits

`--project <name>` across Projects roots waits for the change to `resolve_project_path` and `assemblyzero/core/projects_root.py`. This change does not touch the generator's `--project` lookup, and #4775 stays open for it.

## #4776: `{{ASSEMBLYZERO_ROOT}}`

- The generator adds `ASSEMBLYZERO_ROOT` to the variables it substitutes, from `inherit_from` through R1. Without `inherit_from` it is the folder holding the templates' `.claude`. `project.json` does not hold it.
- `root_variable()` gives it forward slashes: `C:/...` or `//wsl.localhost/...` on Windows, the POSIX path on Ubuntu. Templates put it in bash commands, where an unquoted backslash is lost, and Git Bash and Windows programs both read the forward-slash form.
- `.claude/templates/commands/cleanup.md.template:107` now reads `poetry run --directory {{ASSEMBLYZERO_ROOT}} python {{ASSEMBLYZERO_ROOT}}/tools/assemblyzero-permissions.py --quick-check --project {{PROJECT_NAME}}`. A fixed-string search under `.claude/` for `../AssemblyZero` and `{{PROJECT_ROOT}}/..` found no other template.
- `.claude/project.json.example:45` names `<AssemblyZero's root>` and the project's absolute path in place of `../AssemblyZero`.
- A repository generated before the change keeps its old files until it is regenerated.

## #4777: the CLAUDE.md line

`create_claude_md` now writes `claude_md_content()`, which builds the file without touching the disk, as `project_json_content()` does. Its "Project Root (Windows)" line holds `windows_spelling(project_path)`: `C:\...` for a drive path and `\\wsl.localhost\<distro>\...` for an ext4 one when `WSL_DISTRO_NAME` is set. From Windows, `windows_spelling` of a `C:\` path is that path, so the line is unchanged there.

## Tests

`tests/unit/test_assemblyzero_generate.py` (new, 31 tests) and two new classes in `tests/unit/test_new_repo_ubuntu_run.py` (8 tests). The test report maps them to the issues' tests.

## Ruff

`ruff check` on the four changed Python files reports the same 21 findings, by file and rule, as on the primary at a94a589f. The new test file has none.
