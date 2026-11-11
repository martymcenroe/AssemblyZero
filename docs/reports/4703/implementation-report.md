# Implementation report: #4703, #4704, #4705

One branch for three issues of one concern: tests whose placeholder paths, such as `/path/that/does/not/exist` and `/fake/projects/Chiron`, resolve on Windows to real folders at the root of the drive, where the suite then writes on every run.

## How they were found

The operator's machine has four such folders at the top of C:. Measured 2026-11-11 12:06 PM Central from Ubuntu, read only:

| Folder | Files | Folders | Newest change |
|---|---|---|---|
| `C:\nonexistent` | 885 | 3 | 2026-10-31 6:03 AM Central (a folder's mtime) |
| `C:\fake` | 2 | 403 | 2026-11-11 5:22 AM Central |
| `C:\path` | 1 | 5 | 2026-11-11 5:17 AM Central |
| `C:\c` | 117 | 20 | 2026-07-30 6:17 AM Central |

The Windows task that runs the dependabot review ran `poetry run pytest -q --tb=short` in `AssemblyZero-dependabot-4315` from 5:01 to 5:42 AM Central on 2026-11-11 (`AssemblyZero-scheduled/data/dependabot-runs/2026-11-11_050010.log`). Both of that morning's writes fall inside it, and every daily lineage folder since 2026-11-01 falls inside that day's run.

## #4703: the inventory node

`update_inventory_node` raises `ValueError` naming the path when `repo_path` is not an existing directory, before it reads or writes. It used to build the whole path, because `inject_inventory_table` runs `mkdir(parents=True)`. T060 passed `/path/that/does/not/exist` and accepted any result, so on Windows it created `C:\path\that\does\not\exist\docs\0003-file-inventory.md` on 2026-03-06 and rewrote it on every run. The node has no caller in `assemblyzero/` or `tools/`; a repo path that is not a directory is a caller bug, as a missing `repo_path` is (#1155).

## #4704: the repo-targeting tests

`test_lld_threads_target_repo`, `test_spec_threads_repo_root` and `test_impl_carves_worktree_from_target` now give the stage a target under `tmp_path` that does not exist, as `/fake/projects/Chiron` did not on Linux. On Windows that folder existed, made by an earlier version of the suite on 2026-07-14, so the spec stage took it for a checkout and added an empty `docs/lineage/active/5-implspec/<stamp>` folder each run: 386 of them from 2026-08-12 to 2026-11-11. `EXTERNAL` stays for the tests that only compute paths.

## #4705: the session guard

`tests/drive_root_guard.py` snapshots `/nonexistent`, `/fake`, `/path` and `/c`, every file and folder under each, as `(kind, size, mtime_ns)`. `conftest.py` takes it at session start and compares at session finish, beside the home-state (#3531) and checkout-telemetry (#4161) guards, and a difference fails the session with each path named. Folders count, since the spec-stage writer made only empty folders. A root that does not exist contributes nothing. A root that is a link is recorded and never walked: on the operator's Ubuntu `/c` is a link to `/mnt/c`, the whole Windows drive. `pytest_sessionfinish` now takes a snapshot function and a comparison per guard, so the drive-root guard can use its own.

## Earlier writers, already gone from main

PR #4425 replaced `"audit_dir": "/nonexistent"` in `test_diff_aware_review.py` (785 drafts in `C:\nonexistent`, 2026-02-27 to 2026-10-25) and the `/fake/repo` target in `test_review_resets_counter` (`C:\fake\repo\data\speedrun\telemetry\prompt-failures.jsonl`, last written 2026-10-25). PR #4430 replaced `/nonexistent/path/buffer` in `test_telemetry_emitter.py` (98 buffer files, 2026-02-24 to 2026-10-25). The guard is what would have caught each of them on its first Windows run.

## Lint

`ruff check` on the new files, `tests/conftest.py` and the repo-targeting test is clean. On `assemblyzero/nodes/inventory.py` and `tests/unit/test_inventory_node.py` it reports only findings on lines this change does not touch (import order, `BLE001`, `RUF010`, `RUF015`).
