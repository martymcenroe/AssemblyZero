"""N1b/N1c: compile the assertion manifest, then gate on it (#2533).

The deterministic truth-producer runs ahead of the stochastic spender. N1b
compiles the LLD's decision tables plus the target contract's tables into the
assertion manifest — pure Python, no model call — and FAILS CLOSED: an
uncompilable criterion is an upstream-document defect, so the run halts with a
must-resolve filing (N0c's path) before any drafting spend. N1c is the
mechanical gate over the compiled manifest itself; a finding there means the
compiler broke its own contract, which is equally not a thing to spend a
draft on.

An LLD with no criteria decision table compiles to "not applicable" and the
stage proceeds exactly as before this node existed — most repos, every
non-visual issue.

The manifest is a lineage artifact (``NNN-assertion-manifest.md``), regenerable
from (LLD, contract) on every run including resumes — never hand-maintained.

#3585 (ADR 0236): what N1b needs and cannot get (a repo root, the contract a
repo declares, a lineage directory for the manifest) raises
``ManifestCannotRun``. N1b halts with it through one return, which the router
sends to HALT, and HALT alerts. A must-resolve filing that fails alerts the
operator; the halt it reports still stands. N1c passes through only on an
absence N1b recorded.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from assemblyzero.core import alert
from assemblyzero.speedrun.must_resolve import Origin
from assemblyzero.workflows.implementation_spec.assertion_manifest import (
    CompileResult,
    compile_manifest,
    gate_findings,
    render_manifest,
    rows_as_dicts,
)
from assemblyzero.workflows.implementation_spec.state import (
    ImplementationSpecState,
)

MANIFEST_ORIGIN = Origin(
    "N1b manifest",
    "Found by the assertion-manifest compiler (#2533) before any drafting "
    "spend. The compiler's verdict: this criterion cannot compile to a "
    "literal assertion from the LLD and contract as written, so an operator "
    "ruling on the upstream documents is required before any roll.",
)


class ManifestCannotRun(RuntimeError):
    """N1b cannot compile the manifest it owes (#3585).

    Not an uncompilable criterion, which is the upstream documents' defect:
    this is a missing input (a repo root, the declared contract, a lineage
    directory), so no ruling on the LLD would fix it.
    """


def _halt_manifest_cannot_run(exc: ManifestCannotRun) -> dict[str, Any]:
    """N1b's halt for a missing input: loud, and routed to HALT, which alerts."""
    message = f"N1b assertion manifest cannot run: {exc}"
    print(f"ERROR [N1b] {message}", file=sys.stderr)
    return {
        "assertion_manifest": "",
        "assertion_manifest_rows": [],
        "error_message": message,
    }


def _contract_text(repo_root: str) -> str:
    """The target repo's binding contract, when it declares one.

    Read through the visual-gate declaration (#2518) — the one place a repo
    names its contract. No declaration, no contract: the compiler then judges
    the LLD's literals on their own, which weakens only the cross-document
    hex check, and honestly.

    #3585: no repo root, a declaration that cannot be loaded, a declared
    contract that is not a file, and a contract that cannot be read raise
    ``ManifestCannotRun``. Each used to compile without the contract, with
    one line on stdout or none, and the cross-check was lost.
    """
    if not repo_root:
        raise ManifestCannotRun(
            "N1b was given no repo root, so the target's contract cannot be read"
        )
    from assemblyzero.visual_gate.config import load_gate_config

    root = Path(repo_root)
    try:
        config = load_gate_config(root)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        raise ManifestCannotRun(
            f"the visual-gate declaration in {repo_root} cannot be loaded: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    if config is None or not config.contract:
        return ""
    contract_path = root / config.contract
    if not contract_path.is_file():
        raise ManifestCannotRun(
            f"the visual-gate declaration in {repo_root} names the contract "
            f"{config.contract}, and {contract_path} is not a file"
        )
    try:
        return contract_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise ManifestCannotRun(
            f"cannot read the contract {contract_path}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def compile_assertion_manifest(
    state: ImplementationSpecState, *, filer=None
) -> dict[str, Any]:
    """N1b: compile. Halts (fail closed) on any uncompilable criterion.

    ``filer`` is the must-resolve seam for tests; production uses
    ``file_must_resolve`` directly.
    """
    lld_content = state.get("lld_content", "")
    repo_root = state.get("repo_root", "")
    mock_mode = state.get("config_mock_mode", False)

    try:
        contract = _contract_text(repo_root)
    except ManifestCannotRun as exc:
        return _halt_manifest_cannot_run(exc)

    result = compile_manifest(lld_content, contract)

    if not result.applicable:
        # #2608, and #3585 left it standing. The compiler sits out an issue
        # with no criteria decision table, and that is an answer, not a
        # failure: "abstained" means the LLD has tables and none carries an ID
        # and a binding column, the #332 visual-criteria shape. Every LLD in
        # this repository abstains (110 of 110, counted 2026-10-30), so an
        # alert or a halt here would fire on every non-visual run. What #2608
        # forbade was sitting out silently (run-issue331-093613 abstained on
        # fifteen tables with one log line), so the abstain prints, carries
        # the denominator it searched, and travels forward on state for the
        # report and for N1c.
        detail = result.denominator()
        if result.abstained:
            print(
                f"    [N1b] ABSTAIN: {detail}. The #2533 protection is OFF "
                f"for this run and the absence travels forward (#2608). A "
                f"document carrying tables but none in the criteria shape "
                f"is a shape mismatch, not an empty document."
            )
        else:
            print(
                f"    [N1b] not applicable: {detail} — assertion manifest "
                f"does not apply; drafting proceeds as before (#2608)"
            )
        return {
            "assertion_manifest": "",
            "assertion_manifest_rows": [],
            "assertion_manifest_absent": True,
            "assertion_manifest_absence_reason": detail,
            "assertion_manifest_abstained": result.abstained,
            "error_message": "",
        }

    if result.failures:
        for failure in result.failures:
            print(
                f"    [N1b] UNCOMPILABLE {failure.criterion_id}: "
                f"{failure.reason}"
            )
        if mock_mode and filer is None:
            # A mock run never writes GitHub issues; the halt below is the
            # same, and a test that wants the filing path injects a filer.
            print(
                "    [N1b] mock mode: no must-resolve is filed (a mock run "
                "never writes GitHub issues)"
            )
        else:
            _file_failures(state, result, filer=filer)
        listed = "; ".join(
            f"{f.criterion_id}: {f.reason}" for f in result.failures[:3]
        )
        more = (
            f" (and {len(result.failures) - 3} more)"
            if len(result.failures) > 3 else ""
        )
        return {
            "assertion_manifest": "",
            "assertion_manifest_rows": [],
            "error_message": (
                f"ASSERTION MANIFEST UNCOMPILABLE: {len(result.failures)} "
                f"criterion(s) cannot compile to literal assertions — the "
                f"upstream documents are incomplete or contradictory, caught "
                f"before any draft spend (#2533). {listed}{more}. An operator "
                f"ruling on the LLD/contract is required; a must-resolve was "
                f"filed per defect."
            ),
        }

    manifest_text = render_manifest(result)
    print(
        f"    [N1b] compiled {len(result.rows)} manifest row(s) from "
        f"{len(result.criteria_ids)} criteria"
    )

    try:
        path = _persist_manifest(state.get("audit_dir", ""), manifest_text)
    except ManifestCannotRun as exc:
        return _halt_manifest_cannot_run(exc)
    print(f"    [N1b] manifest persisted: {path.name}")

    return {
        "assertion_manifest": manifest_text,
        "assertion_manifest_rows": rows_as_dicts(result),
        "assertion_manifest_criteria": list(result.criteria_ids),
        "error_message": "",
    }


def _persist_manifest(audit_dir_str: str, manifest_text: str) -> Path:
    """Write the manifest into the run's lineage directory (#2533).

    The manifest is a lineage artifact, and the runner always creates the
    directory, so an unset or missing one, or a write that fails, raises
    ``ManifestCannotRun`` (#3585). It used to be skipped without a word.
    """
    if not audit_dir_str:
        raise ManifestCannotRun(
            "the state names no audit_dir, so the compiled manifest cannot be "
            "kept in the run's lineage"
        )
    audit_dir = Path(audit_dir_str)
    if not audit_dir.is_dir():
        raise ManifestCannotRun(
            f"the state names audit_dir {audit_dir}, which is not a directory, "
            f"so the compiled manifest cannot be kept in the run's lineage"
        )
    from assemblyzero.workflows.requirements.audit import (
        next_file_number,
        save_audit_file,
    )

    try:
        return save_audit_file(
            audit_dir, next_file_number(audit_dir), "assertion-manifest.md",
            manifest_text,
        )
    except OSError as exc:
        raise ManifestCannotRun(
            f"cannot write the manifest into {audit_dir}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def _file_failures(
    state: ImplementationSpecState,
    result: CompileResult,
    *,
    filer=None,
) -> None:
    """One must-resolve per uncompilable criterion — N0c's contract: it never
    changes the halt, which is already stopping the run.

    #3585: a filing that cannot be made alerts the operator, naming the cause
    and every criterion left unfiled; it used to print a WARNING to stdout.
    No repo root or no issue number is such a filing: it used to file against
    "." and issue 0. The caller decides mock mode, where nothing is filed.
    """
    repo_root = state.get("repo_root") or ""
    issue = state.get("issue_number") or 0
    unfiled = [failure.criterion_id for failure in result.failures]
    try:
        if not repo_root:
            raise ValueError("the state carries no repo_root to file against")
        if not issue:
            raise ValueError("the state carries no issue_number to file against")
        from assemblyzero.speedrun.must_resolve import file_must_resolve

        file = filer or file_must_resolve
        for failure in result.failures:
            file(
                repo_root,
                int(issue),
                {
                    "criterion_a": failure.row_text,
                    "criterion_b": "",
                    "diverging_situation": (
                        f"criterion {failure.criterion_id} cannot compile to "
                        f"a literal assertion: {failure.reason}"
                    ),
                },
                origin=MANIFEST_ORIGIN,
            )
            unfiled.remove(failure.criterion_id)
    except Exception as exc:  # noqa: BLE001 -- alerted; the halt stands
        alert.alert_operator(
            what="file the must-resolve for each uncompilable manifest criterion",
            where=(
                "assemblyzero.workflows.implementation_spec.nodes."
                "compile_manifest._file_failures (N1b)"
            ),
            cause=f"{type(exc).__name__}: {exc}",
            consequence=(
                f"the run halts on the uncompilable criteria regardless; no "
                f"must-resolve was filed for {', '.join(unfiled)}, so file "
                f"them by hand"
            ),
            repo=repo_root,
            issue=int(issue) if str(issue).isdigit() else None,
        )


def manifest_gate(state: ImplementationSpecState) -> dict[str, Any]:
    """N1c: the mechanical gate over the compiled manifest (#2533).

    Row/criteria count agreement, every expected value literal, the
    placeholder-word ban, no duplicate sample points. A finding halts: it
    means the compiler emitted a manifest that breaks its own invariants,
    and a draft built on it would inherit the defect.

    #3585: N1c passes through with no manifest only when N1b recorded the
    absence (``assertion_manifest_absent``), and says why. With no manifest
    and no such record, or with rows and no criteria list, N1b's output is
    not on the state, and that is a finding. Both used to pass: the first
    through, the second against criteria re-derived from the rows, which can
    only ever agree with them.
    """
    manifest_text = state.get("assertion_manifest", "")
    rows = state.get("assertion_manifest_rows", [])
    if not manifest_text and not rows and state.get("assertion_manifest_absent"):
        # #2608: nothing to gate is a real state, and the gate repeats WHY
        # rather than only that it passed — "no manifest to gate" alone gave
        # the operator a second reassuring line about a protection that was
        # off. The abstain passes too: it is every non-visual run (see N1b).
        reason = state.get("assertion_manifest_absence_reason", "")
        if state.get("assertion_manifest_abstained"):
            print(
                f"    [N1c] no manifest to gate — the compiler ABSTAINED "
                f"({reason}); the #2533 protection is off for this run "
                f"(#2608)"
            )
        else:
            print(f"    [N1c] no manifest to gate — {reason or 'not applicable'} (#2608)")
        return {"error_message": ""}

    from assemblyzero.workflows.implementation_spec.assertion_manifest import (
        ManifestRow,
    )

    findings: list[str] = []
    criteria = state.get("assertion_manifest_criteria")
    if not manifest_text and not rows:
        findings.append(
            "the state carries no manifest and N1b recorded no absence "
            "(assertion_manifest_absent), so there is nothing to gate and "
            "nothing that says why"
        )
    elif criteria is None:
        # The criteria list travels through state from N1b, so the coverage
        # check compares rows against the DOCUMENT's criteria rather than
        # against a list re-derived from the rows themselves.
        findings.append(
            f"{len(rows)} manifest row(s) arrived without N1b's criteria list "
            f"(assertion_manifest_criteria), so row coverage cannot be checked "
            f"against the document"
        )
    else:
        result = CompileResult(
            applicable=True,
            rows=tuple(
                ManifestRow(
                    row_id=r.get("row_id", ""),
                    criterion_id=r.get("criterion_id", ""),
                    criterion=r.get("criterion", ""),
                    sample_point=r.get("sample_point", ""),
                    expected=r.get("expected", ""),
                    source=r.get("source", ""),
                )
                for r in rows
            ),
            criteria_ids=tuple(criteria),
        )
        findings = gate_findings(result)
    if findings:
        for finding in findings:
            print(f"    [N1c] GATE: {finding}")
        return {
            "error_message": (
                f"ASSERTION MANIFEST GATE: {len(findings)} finding(s) in the "
                f"compiled manifest — not spending a draft on a manifest "
                f"that breaks its own invariants (#2533). "
                + " | ".join(findings[:3])
            ),
        }

    print(f"    [N1c] manifest gate passed ({len(rows)} row(s))")
    return {"error_message": ""}
