# Implementation Report: the implementation-spec workflow under standard 0034 (#3585 step 5, first half)

The rule is ADR 0236 and standard 0034. This branch takes the first half of `assemblyzero/workflows/implementation_spec/`: N3's route in `graph.py`, then `nodes/validate_completeness.py`, then `nodes/compile_manifest.py`. The module issues were deleted on 2026-10-30, so ledger 0908 names every site; line numbers are the ledger's, at `79e18ad1`.

## Modules

### graph.py: N3's errors reach HALT

`route_after_validation` keyed its halt on `completeness_cannot_check` alone, so `tools/audit_loud_failure.py` listed N3 as a node whose `error_message` no router sends to HALT. Its comment said `error_message` also carries a cap message on a grace revision that must still reach N2 (#2304). N3's code does not do that: it writes the cap message only when no grace is granted. The router now reads `error_message` first and halts on any value. A grace revision carries an empty `error_message`, so it still reaches N2. The `completeness_cannot_check` branch went, because `error_message` carries the same text; N3 still writes the field.

The ledger's two `graph.py` rows (265, an unknown human-gate decision; 513, N6's errors) were fixed by #3887 before this sweep reached the file. They are pinned by tests here.

Compliance: the one failure path touched is N3's error. It is loud (N3 prints an ERROR line for a check that cannot run), logged (the message names the check and the cause), stops (the router sends it to HALT), and alerts (HALT calls `alert_operator`).

Baseline: the entry `assemblyzero.workflows.implementation_spec.graph::N3_validate_completeness::unrouted_error::1` leaves.

### nodes/validate_completeness.py: a check that cannot run halts N3 (33 sites; 2 fixed earlier by #3767)

The checks run in `_run_checks`; the node calls it in one `try`. Every check that cannot run raises `CompletenessCannotCheck`, naming the check, its subject and the cause. The node's one handler prints `ERROR [N3] ...` to stderr and returns `completeness_cannot_check` and `error_message`, which is the registry's existing `validate_completeness::return 0`, so no gate row moves. A defect in the draft fails its check and is revised.

- **What N3 needs.** No repo root (1342, 1455, 1702), no LLD (1879), and an LLD with no criteria table or with untagged rows (1892) raise. Each used to pass as "skipping" or "not applicable".
- **The target environment.** `_target_env_python` and `_probe_target_env` (4380 to 4423) raise with the return code and stderr, instead of returning None. So the import check (1530) and the unbound-root probe (3873) halt when the environment cannot answer, instead of passing with a note or judging with no notice.
- **The repo layout.** A pyproject that exists and cannot be read or parsed (4167, 4288, 1988, 2050) raises naming the file, through one `_read_pyproject`; a missing one is still an answer. A root or `src/` that cannot be listed raises (4355), the declared-package read is no longer swallowed (4360), and `_first_party_tops_for` no longer turns a read failure into "no packages" (3890). A base pyproject that cannot be read raises instead of falling back to the checkout (2036), and a failed `git ls-tree` raises with stderr (1614).
- **Telemetry** (280) that cannot be recorded halts N3 with its type and message. It used to print a WARNING to stdout.
- **Draft defects fail their check.** No Section 10 (2194), with a complaint revision pinning reads as a demand to add. The implementation stage's extractor refusing the draft (2222), quoted. A Section 10 block that does not parse (2419), with the SyntaxError and Section 10's lines. A python fence that does not parse, in manifest traceability (2641), which now reads fences through `_scan_fences`.
- **Recorded, not silent.** An empty draft (132) joins the cap bookkeeping, so a halt at the cap carries a reason. A standard-library base this host cannot resolve (3439) is printed at ERROR and named in the symbol check's details; the methods it would lend still abstain. An extracted test function the draft does not hold (2083) raises.
- **Empty symbols** (3932) no longer skip the symbol check. Unparseable python still fails it. A call that needs the table raises in a repo that has Python packages, and is a finding in one that has none. A spec whose calls need no table passes, and its details say why.

Every `# fail-open:` tag in the module is gone.

Compliance: each failure path above is loud (an ERROR line on stderr from the node, or the check's own failed result for a draft defect), logged (the message names the check, the repo or file, and the cause), stops (N3's cannot-check return is routed to HALT; a draft defect is revised, and halts at the cap), and alerts (HALT calls `alert_operator`). The unresolved stdlib base (3439) is loud and logged, as the ledger asks; it stops nothing, because the check still runs and only that class's inherited methods abstain.

On real runs, N3 now halts where it used to pass: when the target repo's poetry environment cannot answer a probe (third-party imports, or calls on roots nothing in the spec binds), when the LLD's criteria cannot be joined, and when N1 gathered no symbols from a repo that has Python packages (a plan that modifies no existing .py file, with no base branch).

Not changed, reported: `base_tree.read_from_base` returns "" both when the file is absent and when git fails, so `_pyproject_for_run` cannot tell a base with no pyproject from a git failure. It still falls to the checkout on "". The `spec.completeness_cannot_check` row's notes in `gate_registry.py` still name only the unparseable-callee case.

Baseline: nine loud-failure entries leave (seven tags and two swallowed handlers).
