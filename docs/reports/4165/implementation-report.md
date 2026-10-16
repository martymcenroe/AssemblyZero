# Implementation Report: programs read the fleet's public identifiers from one file (#4165)

On 2026-09-27 `tools/cerberus_worker_key.py` was written to prompt the operator for the Cerberus App ID, which `tools/deploy_cerberus_secrets.py` already held as a constant. He asked for one home for the fleet's identifiers. The operator's private registry holds the full set; the entries already published in public files are generated here as `config/fleet-ids.json`.

## What landed

| File | Change |
|---|---|
| `config/fleet-ids.json` | the public identifiers: the GitHub owner, Cerberus's App ID and bot login, pr-sentinel's App ID, the fleet CloudFlare account, the AWS account and region. Generated; its `_about` says so |
| `tools/fleet_ids.py` | `get(key)` and `load()`, standard library only; an unknown key raises naming the known ones |
| `tools/cerberus_worker_key.py`, `tools/deploy_cerberus_secrets.py` | `fleet_ids.get("cerberus_app_id")` in place of the constant, and the docstrings no longer repeat it |
| `tools/sentinel_migrate.py` | `int(fleet_ids.get("pr_sentinel_app_id"))` in place of the constant |
| `tools/fleet_delete_pr_sentinel.py` | the issue and PR templates name the pr-sentinel App instead of repeating its ID |
| `sentinel/README.md` | the App ID row cites the file |
| `tests/unit/test_fleet_ids.py` | 13 tests |

## Decisions taken along the way

**Generated, not hand-kept.** A second hand-kept list would drift from the operator's registry. The file says it is generated, and a test holds that line. It carries only each identifier's value and what it is.

**The test sits in `tests/unit/`.** CI's unit job runs only `tests/unit/`, so a test under `tests/tools/` would not run on a pull request.

**`deploy_cerberus_secrets.py` imports `fleet_ids` with the same fallback it uses for `_pat_session`.** It runs as a script and is imported as a module by `tools/new_repo.py`, and the existing pattern covers both.

**The posted templates in `fleet_delete_pr_sentinel.py` change wording only.** Its phase of work is finished; the template text now names the App rather than its number, so no program in `tools/` carries either App ID, which a test checks.
