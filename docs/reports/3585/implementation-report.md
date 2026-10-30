# Implementation Report: the implementation-spec workflow under standard 0034 (#3585 step 5)

The rule is ADR 0236 and standard 0034. The module issues were deleted on 2026-10-30, so ledger 0908 names every site; line numbers are the ledger's, at `79e18ad1`. The package was swept in two halves and assembled on one branch.

## The first half: N3's route in `graph.py`, then `nodes/validate_completeness.py`, then `nodes/compile_manifest.py`

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

### nodes/compile_manifest.py: N1b halts on a missing input, a failed filing alerts, N1c passes only a recorded absence (13 sites fixed, 2 WON'T DO)

What N1b needs and cannot get raises `ManifestCannotRun`. N1b halts through `_halt_manifest_cannot_run`, which prints `ERROR [N1b] ...` to stderr and returns "N1b assertion manifest cannot run: ..."; the existing router sends it to HALT, which alerts.

- **The contract** (54, 63, 66, 67): no repo root, a visual-gate declaration that cannot be loaded, a declared contract that is not a file, and a contract that cannot be read each raise. They used to compile without the contract, losing the cross-document hex check with a stdout line or none. No declaration is still an answer.
- **The lineage artifact** (155): an unset or missing `audit_dir`, or a write that fails, raises. It used to skip the manifest's lineage copy silently.
- **The must-resolve filing** (198, 199, 210, 211): no repo root, no issue number, or a filer that raises calls `alert_operator` with the cause and every criterion left unfiled. The halt on the uncompilable criteria stands. It used to file against "." and issue 0, and print a WARNING on failure.
- **Mock mode** (186, 188): N1b decides it and files nothing, as documented test-mode behaviour, with no early return.
- **N1c** (230, 231, 256) passes through only on an absence N1b recorded, and says why. No manifest and no record, or rows with no criteria list, is a finding through the existing GATE return. The fallback that re-derived criteria from the rows, which could only agree with them, is gone.

**WON'T DO: the abstain (89, and the abstain half of 230).** The ledger asks for at least an ERROR and an alert when the compiler abstains, meaning the LLD has tables and none in the criteria shape. Counted on 2026-10-30 over the 110 LLDs in this repository: 110 abstain, 0 compile, 0 have no tables. Only the #332 visual-criteria shape carries a binding column, so an alert there would fire on every non-visual run. The tags are gone; the comment states the contract and the count, the abstain still prints and travels forward on state, and the pass-through is pinned.

Compliance: each new failure path is loud (an ERROR line on stderr from N1b, or alert_operator's own line), logged (the message names the repo, the declared path or the audit dir, and the cause), stops (N1b's cannot-run return and N1c's findings route to HALT; a failed filing changes nothing because the run is already halting), and alerts (HALT calls `alert_operator`; the filing calls it directly).

**Shared files changed:** `assemblyzero/core/gate_registry.py` gains the row `spec.manifest_cannot_run` for the new halt site, citing the operator's 2026-10-06 ADR 0236 acceptance in `created_by`. `tests/fixtures/gate_registry_baseline.json` raises `halt_rows_per_stage.spec` from 20 to 21 in the same change, as the ratchet requires.

Baseline: seven loud-failure entries leave (five tags and two swallowed handlers).
## The second half: the nodes and helpers other than `graph.py`, `nodes/validate_completeness.py` and `nodes/compile_manifest.py`

Each site is the ledger row in `docs/audits/0908-loud-failure-sweep-ledger.md` named by file and line at `79e18ad1`.

### `workflows/implementation_spec/base_tree.py` (4 sites)

- **A failed fetch (41) and a base not on origin (45).** `base_ref` ignored the fetch's exit code, and when `origin/<base>` did not resolve it fell back to the local branch, which nothing fast-forwards (#2021). Both now raise `BaseTreeError` with the command, the exit code and git's stderr.
- **A git error read as absence (54, 63).** `exists_on_base` used `git cat-file -e`, which exits non-zero both for a missing path and for a ref git cannot read. It now asks `git ls-tree --full-tree`, which exits 0 with no output for a missing path and fails only for a git error, which raises. `read_from_base` returns `""` only for a path the base does not ship, and raises on any other failed `git show`.
- **`BaseTreeError`** is a `RuntimeError`, not an `OSError`, so no caller reads a git failure as a missing file.
- **Callers.** `analyze_codebase` catches it and halts (below). `validate_completeness.py` does not catch it yet; a git failure there now raises out of N3 rather than reading as absent.

### `workflows/implementation_spec/nodes/analyze_codebase.py` (23 sites, 1 compliant)

- **The node halts.** Every failure below reaches the node as `BaseTreeError` or the new `CodebaseReadError`, and the node returns an `error_message` of the form `[N1] analyze_codebase for issue #N: ...`, with an ERROR line on stderr. `route_after_analyze` already sends it to HALT, which alerts. The repo_root guard (110) was already compliant.
- **The plan's own files (118, 183, 196, 216, 261, 310).** An empty plan, a Modify or Delete target that is missing, not a file, unreadable or unparseable, and an unknown change type each used to pass with a WARNING on stdout and no content. They now halt, at the first file that fails. A file that does not parse is reported by interface_surface, which raises since #3779.
- **An Add whose directory does not exist yet** is still not a failure: the implementation creates it. The note is no longer a WARNING, and the `warnings` list is gone.
- **The context files (567, 627, 676, 734, 782, 831, 843, 871, 914).** A pattern file, CLAUDE.md, README, pyproject or planned file that exists and cannot be read or parsed raises naming it; it used to be dropped. An absent one still contributes nothing.
- **The base sweep (947, 959, 988, 1024, 1037, 1044, 1054).** A failed `git ls-tree` raises; the 200-file caps are gone; a file git cannot show raises (through `read_from_base`); a base file that does not parse raises, where it used to be regex-scraped.
- **The symbol gather (1127).** `gather_symbols` still names every file that did not parse; the node halts on the list, and `_extract_symbols_from_files` raises instead of returning a shorter list.
- **`core/gate_registry.py`.** The new `_halt` return is a halt site, added to the existing `spec.input_precondition` row. No row is added, so the ratchet is unchanged.
