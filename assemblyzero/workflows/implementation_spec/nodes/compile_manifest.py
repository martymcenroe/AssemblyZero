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
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

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


def _contract_text(repo_root: str) -> str:
    """The target repo's binding contract, when it declares one.

    Read through the visual-gate declaration (#2518) — the one place a repo
    names its contract. No declaration, no contract: the compiler then judges
    the LLD's literals on their own, which weakens only the cross-document
    hex check, and honestly.
    """
    if not repo_root:
        return ""
    try:
        from assemblyzero.visual_gate.config import load_gate_config

        config = load_gate_config(Path(repo_root))
        if config is None or not config.contract:
            return ""
        contract_path = Path(repo_root) / config.contract
        if not contract_path.is_file():
            return ""
        return contract_path.read_text(encoding="utf-8-sig")
    except Exception as exc:  # noqa: BLE001
        # fail-open: #2533 — a broken gate declaration is the visual stage's
        # finding to make (it fails the roll there); the manifest compiler
        # only loses the contract cross-check, and says so.
        print(f"    [N1b] contract unavailable ({exc}); compiling without it")
        return ""


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

    result = compile_manifest(lld_content, _contract_text(repo_root))

    if not result.applicable:
        # fail-open: #2608. The compiler sits out an issue with no decision
        # table, which is most of them, and that remains correct. What is
        # NOT correct is sitting out silently: run-issue331-093613 abstained
        # on an LLD holding fifteen tables because none carried the criteria
        # shape, and the #2533 protection switched off with one log line and
        # no downstream trace. Continuing is deliberate -- a repo with no
        # decision tables must still roll -- so the abstain is declared here,
        # carries the denominator it searched, and travels forward on state
        # for the report and for every later stage, which is what makes it a
        # declared fall-through rather than an accident.
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
        _file_failures(state, result, mock_mode=mock_mode, filer=filer)
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

    audit_dir_str = state.get("audit_dir", "")
    if audit_dir_str and Path(audit_dir_str).exists():
        from assemblyzero.workflows.requirements.audit import (
            next_file_number,
            save_audit_file,
        )

        path = save_audit_file(
            Path(audit_dir_str),
            next_file_number(Path(audit_dir_str)),
            "assertion-manifest.md",
            manifest_text,
        )
        print(f"    [N1b] manifest persisted: {path.name}")

    return {
        "assertion_manifest": manifest_text,
        "assertion_manifest_rows": rows_as_dicts(result),
        "assertion_manifest_criteria": list(result.criteria_ids),
        "error_message": "",
    }


def _file_failures(
    state: ImplementationSpecState,
    result: CompileResult,
    *,
    mock_mode: bool,
    filer=None,
) -> None:
    """One must-resolve per uncompilable criterion — N0c's contract: never
    raises, never changes the halt; a filing problem is loud and nothing more."""
    if mock_mode and filer is None:
        print("    [N1b] mock mode: must-resolve filing skipped")
        # fail-open: mock runs must not write real GitHub issues — the halt
        # itself (the thing that matters) is unchanged, the skip is printed,
        # and a test wanting the filing path injects a filer.
        return
    try:
        from assemblyzero.speedrun.must_resolve import file_must_resolve

        file = filer or file_must_resolve
        for failure in result.failures:
            file(
                state.get("repo_root") or ".",
                int(state.get("issue_number") or 0),
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
    except Exception as exc:  # noqa: BLE001
        # fail-open: filing must never mask the halt (the must_resolve
        # module's own contract) — the run is already stopping, and the
        # defect is fully stated in the halt message above.
        print(
            f"    [N1b] WARNING: must-resolve filing failed ({exc}); "
            f"halting anyway."
        )


def manifest_gate(state: ImplementationSpecState) -> dict[str, Any]:
    """N1c: the mechanical gate over the compiled manifest (#2533).

    Row/criteria count agreement, every expected value literal, the
    placeholder-word ban, no duplicate sample points. A finding halts: it
    means the compiler emitted a manifest that breaks its own invariants,
    and a draft built on it would inherit the defect.
    """
    manifest_text = state.get("assertion_manifest", "")
    rows = state.get("assertion_manifest_rows", [])
    if not manifest_text and not rows:
        # fail-open: #2608. Nothing to gate is a real state and passing
        # through is correct, but the gate must repeat WHY rather than say
        # only that it did — "no manifest to gate" alone gave the operator
        # a second reassuring line about a protection that was off.
        reason = state.get("assertion_manifest_absence_reason", "")
        if state.get("assertion_manifest_abstained"):
            print(
                f"    [N1c] no manifest to gate — the compiler ABSTAINED "
                f"({reason}); the #2533 protection is off for this run "
                f"(#2608)"
            )
        elif reason:
            print(f"    [N1c] no manifest to gate — {reason} (#2608)")
        else:
            print("    [N1c] no manifest to gate — passing through")
        return {"error_message": ""}

    from assemblyzero.workflows.implementation_spec.assertion_manifest import (
        ManifestRow,
    )

    # The criteria list travels through state from N1b, so the coverage
    # check here compares rows against the DOCUMENT's criteria rather than
    # against a list re-derived from the rows themselves (which could only
    # ever agree with them).
    criteria = state.get("assertion_manifest_criteria", []) or list(
        dict.fromkeys(r.get("criterion_id", "") for r in rows)
    )
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
