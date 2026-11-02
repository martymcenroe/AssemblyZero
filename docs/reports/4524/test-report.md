# Test report: #4524, #4508, #4526

## Changed tests

`tests/unit/test_resume_and_halt_record.py` (new, 11 tests):

- #4508 T1: a resume's reused suite routes `continue`. Also: a resume after the third scaffold is not charged a fourth, and the markers last one pass.
- #4508 T2: on the real graph with the real N2 and N2.5, a run that crashes at N3 and is resumed reaches N3 again.
- #4508 T3: a regeneration with identical output still halts, a regeneration during a resume is still compared, and the red phase sending a suite back is not treated as a resume.
- #4526 T1: after N7 moves the lineage, `audit_dir` names `done/`. A move N7 did not make leaves the state alone. N9 writes the learning summary where N7 put the lineage, and returns `audit_dir` when it archives.

`tests/unit/test_impl_lands_through_driver.py`, through `main`:

- #4524 T1: a plain run after a halt with a changed input starts, says it set the contract aside, and consumes it.
- #4524 T2: `--resume` with a changed input refuses as before, and the graph never starts.
- `resume_pass` is set by `--resume` and only by it.
- #4526 T2: a driver refusal leaves the halt's evidence bundle and contract in the kept lineage, and no alert says either was not written.

`tests/unit/test_resume_commands_resolve.py`: #4524 T3, the plan's command through the tool's own parser, which reads `--resume`, and the spec and orchestrator lines, which carry none.

Existing tests changed:

- `test_halt_files_by_repository.py`: a halted issue run's command ended with no `--resume`, which was #4443's way of saying no brief follows. It now ends with the bare flag.

## Runs, 2026-11-02

Every test marked "Fails on main" in the issues was run against unchanged code first, and failed for the reason the issue gives.

The last code edit was at 1:40 AM Central. Both runs below came after it.

- Unit tier, finished 2:06 AM Central: 13757 passed, 66 skipped, 7 deselected, 7 xfailed, in 23m 15s.
- Integration, e2e and adversarial tiers, finished 2:12 AM Central: 84 passed, 8 skipped.
- `ruff check`: nothing new on the changed files.

An earlier unit run, before the last edit, failed four ratchet tests in `test_fail_open_audit.py` and `test_loud_failure_check.py`. Their findings are fixed as the implementation report says, not baselined.
