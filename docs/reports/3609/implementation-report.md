# Implementation Report: derive the Projects root, never spell it (#3609, #3727)

## The count

Measured on `main` at `d0221713` with `git grep -i -F -o` over `assemblyzero/`, `tools/`, `tests/` and `.claude/`. The total is 141 occurrences, not the 87 posted on #3609, because that first count used three spellings and the closed set has five:

| Spelling | Occurrences | Files |
|---|---|---|
| `C:\Users\mcwiz` | 4 | 4 |
| `C:\\Users\\mcwiz` (escaped in Python or JSON) | 36 | 16 |
| `C:/Users/mcwiz` | 20 | 18 |
| `/c/Users/mcwiz` (not inside `/mnt/c/...`) | 79 | 44 |
| `/mnt/c/Users/mcwiz` | 2 | 1 |

After this change the count is zero in all four directories, except `tests/unit/test_no_spelled_projects_root.py`, the guard that has to name what it forbids. The repository-root `project-registry.json` carried one more and is fixed too.

## What changed

- **`assemblyzero/core/projects_root.py`, the one derivation.**
  - `REPO_ROOT = Path(__file__).resolve().parents[2]` and `PROJECTS = REPO_ROOT.parent`.
  - `spellings(path)` gives the Windows, Git Bash and WSL forms of a drive path, and one POSIX form for a path on no drive, such as a CI runner.
- **Code that used a spelled root now imports `PROJECTS`.**
  - `tools/batch_deploy_hooks.py`, `tools/batch_cleanup_quality_hooks.py`, `tools/batch_cleanup_security_hooks.py`;
  - `tools/land_aletheia_775.py`, `tools/land_aletheia_ci_oidc.py`, `tools/land_aletheia_ci_pipestatus.py`, `tools/merge_aletheia_603_audit_gate.py`;
  - `tools/readonly_attribute_audit.py` (its `--root` default);
  - `tests/test_universal_claude_md.py`, `tests/unit/test_campaign_timing_dashboard.py`.
- **`tools/batch_deploy_hooks.py`'s generated hook commands** use `$CLAUDE_PROJECT_DIR`, which Claude Code sets on either side. Its `generate_settings_json` lost the `repo_name` parameter that only fed the old path.
- **Tools that recognise the root inside text build their patterns from `spellings()`.**
  - `tools/repo_drift_check.py` now also recognises the WSL spelling it never matched; its `PROJECTS_ROOT` is the module's.
  - `tools/transcript_filters.py`: the same.
  - `tools/lint_per_repo_claude_md.py`'s marker 9 now catches any `C:\Users\<user>\` path, not one user's.
- **Registries hold relative paths.**
  - `.claude/project-registry.json` entries are relative to the AssemblyZero checkout, and the unread `pathUnix` field is gone. `tools/assemblyzero-harvest.py` resolves them there.
  - The root `project-registry.json` is `["."]`, and `tools/verdict_analyzer/scanner.py` resolves a relative entry against the registry file.
- **Usage examples in about thirty tool docstrings** use paths relative to the AssemblyZero checkout (`../boostgauge`) and "from the AssemblyZero checkout".
- **`.claude/project.json.example`** uses placeholders and a relative generator command.
- **`.claude/templates/commands/cleanup.md.template`** (#3727):
  - its permissions command is relative to `{{PROJECT_ROOT}}`;
  - section 4.4 points at the root CLAUDE.md's merge-driver section instead of naming a private repository's path;
  - both inline `--body` calls are now `--body-file`.
- **Test data uses a neutral `dev` user**, in test strings and three fixture specs. Nothing pins those bytes.
- **`tests/unit/test_office_owner_file_ignores.py`** asks git for `core.excludesFile` instead of spelling it.
- **Two private-repository leaks found while editing** are removed:
  - `tools/transcript_filters.py`'s origin line;
  - the cleanup template's driver path.

## Requirement 2: virtualenv paths in the documents

Runbooks, standards, ADRs and CLAUDE.md carry none. They remain in two kinds of document, and are kept on purpose:
- captured test output in `docs/reports/`, `docs/lineage/` and the repository-root `48-review.md`. These are records of what ran, not instructions.
- `docs/workflow-lessons-learned-1.md`. Lessons-learned records are append-only.

## Found and filed

- #3730: `tests/test_universal_claude_md.py` used to be skipped on Ubuntu, and now runs on both sides. It reads every `ADR-NNNN` as AssemblyZero's, and fails on another repository's ADR-0003, which the universal file cites. It is not in the unit tier.
