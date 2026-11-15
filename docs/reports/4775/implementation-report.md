# Implementation report: #4775 R3

R1, R2 and R4 of #4775 landed in PR #4788, with #4776 and #4777; `docs/reports/4776/` reports them. This change does R3 and closes the issue.

## The defect

`tools/assemblyzero-generate.py` resolved `--project <name>` as `Path.home() / "Projects" / <name>`. That found only one side's repositories: on Ubuntu, those on the ext4 disk; on Windows, those on the C: drive. A repository under any other Projects root was reported not found.

## R3: `--project <name>` is looked up under every Projects root

- The generator puts AssemblyZero's root on `sys.path` and imports `locate_repo` from `assemblyzero/core/projects_root.py` (#4773), as other scripts in `tools/` do.
- A relative `--project` value is passed to `locate_repo(name)`, which reads every Projects root from the fleet's setting. A name held under one root is that copy. A name held under two roots raises RuntimeError naming both copies; the generator prints it as `ERROR: ...` and exits 1, and nothing is generated. A missing root, or a broken roots setting, is refused the same way.
- A name held under no root comes back as the first root's path, so the existing `not project_path.exists()` check still reports `ERROR: Project directory not found: <path>` and exits 1.
- An absolute `--project` path is used as given and is never looked up.
- With no roots setting configured, `locate_repo` uses the one root `projects_root` derives: the AssemblyZero checkout's parent. Before this change the generator used `~/Projects`.

## Help text

The usage line, the `--project` help and the epilog no longer say "relative to Projects dir". The help says an absolute path is used as given and a name is looked up under every Projects root, and that a name under two roots is refused. The epilog's two relative-path examples (`../Aletheia`, `.`) are replaced with an absolute path and a name, since a relative value is now always a name.

## Tests

Four tests in `tests/unit/test_assemblyzero_generate.py`, `TestProjectNameUnderEveryRoot`. The test report maps them to T3.

## Ruff

`ruff check` on the two changed files reports one finding, I001 on the generator's first import block, which it reports the same way on the file at 04cdd776. No changed line has a finding.
