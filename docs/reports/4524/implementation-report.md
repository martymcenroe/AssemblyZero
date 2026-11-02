# Implementation report: #4524, #4508, #4526

Three defects from the first real implementation run, on a private target, 2026-11-01. Each sits on the path from a halt back to a finished run.

## #4524: a plain run is not a resume

`check_and_consume` ran on every start, so a run without `--resume` was refused under the last halt's contract, although the plain path clears the checkpoint database and seeds nothing from it. `tools/run_implement_from_lld.py` now calls it only under `--resume`. A plain run calls the new `set_aside_contract`, which says the contract is set aside and deletes it, so a later `--resume` is never checked against a halt this run replaced. A legacy contract in the shared directory is consumed only when it can be attributed to this repository, and is otherwise left where it is, with a line saying so.

`set_aside_contract` has no exception handler. A contract it cannot read, attribute or remove raises, and `main`'s one handler alerts and exits 1. The first version logged and went on, and the loud-failure and fail-open ratchets refused it, rightly.

`build_resume_command` adds `--resume` to the testing workflow's line. The other three tools take no such flag.

## #4508: a resume reaches the node that crashed

A resume re-enters the graph at the top. N2 found the suite on disk and skipped, and N2.5 then hashed the same files against the hash it had stored from them, so every resume after a crash at the red phase halted, naming a scaffolder that repeated itself.

`--resume` now puts `resume_pass` in the initial state. When N2 skips on that pass it returns `scaffold_reused`. N2.5 is wrapped so a reused suite is validated as usual, but is compared with no previous hash and is not counted as a new scaffold. The wrapper clears both markers on every pass, so they last one pass.

The exemption is tied to the resume, not to the skip. The red phase sending a suite back (#2767) also reaches N2's skip, and that loop is bounded only by the hash comparison and the budget. Exempting every skip would have left it bounded by the recursion limit alone.

## #4526: the state follows the lineage

The issue says cleanup moved the folder. The run's kept files show two moves. N7 finalize moved `active/462-testing` to `done/`, and N8 recreated the old path because the state still named it. Then the landing's `_keep_uncommitted` moved both ignored folders into `data/runs-kept/`, and the driver refused.

- N7 returns `audit_dir` when its move happened. When `done/` already exists, `move_lineage_to_done` leaves the lineage where it is, and the state keeps naming it.
- N9 writes the learning summary where the lineage is, and returns `audit_dir` when it archives the folder itself.
- `_keep_uncommitted` records each move, and a refused landing points the HALT at the lineage where it was kept, so the evidence bundle and the contract are written into it.

## Also changed

- The interaction matrix's sentence on runners and the resume contract, and standard 0030's copy of it, now say a plain run sets the contract aside.
- The fail-open baseline loses `scaffold_tests::warned_return::0`. That return is no longer a bare `{}`, so the audit no longer lists it. No site was added.

## Left open

- The spec workflow has no `--resume`, and a rerun is how it recovers, so its contract still holds on every run.
