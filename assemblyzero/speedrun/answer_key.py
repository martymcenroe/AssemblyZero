"""The answer-key audit: run the gates over code that is known to be right (#2722).

boostgauge `main` carries v1.0.0, built by hand on 2026-09-01 in one session:
the six features the factory has been asked to build, approved by the operator
and by the visual gate. That is the correct answer. A gate that judges the
drafter's output and refuses content the shipped code also contains is a false
positive by construction, and that is checkable without launching anything.

Run 11 (`run-issue4-183941`) is the exhibit: nine review rounds refusing the
drafter's ±1 tolerances, which are the tolerances the shipped collector's own
cross-check uses.

## What runs here, and what does not

Only gates that are pure functions over text can be run against a finished
artifact. The ones that need a live loop (stagnation, iteration caps, the
red phase, coverage) are named in `NOT_RUNNABLE_HERE` with the reason, so the
report says which gates it could not judge rather than implying it judged
them all. Each runnable gate is keyed by its `gate_registry` key, and the
test suite asserts every key names a registered gate that judges the
drafter's output or an upstream artifact -- the only two kinds an answer key
can speak to.

## Refusal is the finding, not the verdict

A refusal here means the gate would have rejected code the operator shipped.
That is the defect this audit exists to find. It does not mean the shipped
code is wrong; it means the gate's rule and the operator's judgment disagree,
and the operator's judgment is the answer key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

_TS_FMT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class Feature:
    """One issue in the arc and the artifacts the hand-build shipped for it."""

    issue: int
    title: str
    sources: tuple[str, ...]
    tests: tuple[str, ...]
    #: The LLD the factory drafted for it, where one survives on main.
    lld: str = ""


#: The six-feature arc, as shipped on boostgauge main by the 2026-09-01 hand
#: build (PRs #407, #408, #410, #411, #412, #413). File lists are the PRs' own
#: file lists. Authored; the tool refuses to guess a file that is not here.
BOOSTGAUGE_ARC: tuple[Feature, ...] = (
    Feature(
        4, "Windows collector",
        ("src/boostgauge/collector.py", "src/boostgauge/collectors/__init__.py",
         "src/boostgauge/collectors/windows.py"),
        ("tests/unit/test_collector.py", "tests/unit/test_collector_source_pin.py",
         "tests/integration/test_windows_sweep_crosscheck.py",
         "tests/benchmark/test_sweep_cost.py"),
        lld="docs/lld/active/LLD-004.md",
    ),
    Feature(
        41, "Telltale peak-hold logic",
        ("src/boostgauge/telltale.py",), ("tests/unit/test_telltale.py",),
    ),
    Feature(
        332, "Stingray dynamic layer",
        ("src/boostgauge/skins/stingray.py",),
        ("tests/visual/test_stingray_dynamic.py",),
    ),
    Feature(
        7, "configuration file and CLI",
        ("src/boostgauge/config.py",), ("tests/unit/test_config.py",),
    ),
    Feature(
        2, "telltale wiring",
        ("src/boostgauge/session.py",), ("tests/unit/test_session.py",),
    ),
    Feature(
        5, "the window",
        ("src/boostgauge/app.py",), ("tests/unit/test_app.py",),
    ),
)

#: Gates this audit can run, by registry key, and what artifact each reads.
RUNNABLE_GATES: tuple[tuple[str, str], ...] = (
    ("impl.file_generation_failed", "every shipped .py file, as the implementer validates a file it wrote"),
    ("impl.scaffold_suite_invalid", "every shipped test file, as the scaffolder's structural validator"),
    ("impl.deterministic_failure", "every shipped test file, as the scaffolder's stub count"),
    ("impl.path_enforcement", "every shipped file against the LLD's allowed paths"),
    ("lld.mechanical_validation", "the LLD, where one survives on main"),
    ("impl.scenario_ratio_guard", "the LLD's requirements against its test plan"),
    # #2787 removed `pr.commit_message_guard` and the merged-commit-subject
    # arm with it. The gate was retired because no graph runs it, so scoring
    # it was scoring nothing: six verdicts a year, none of which measured a
    # check any run performs.
)

#: Gates that judge model output but need a live loop, a run, or a second
#: draft, so an answer key cannot exercise them. Named so the report's
#: coverage is honest.
NOT_RUNNABLE_HERE: tuple[tuple[str, str], ...] = (
    ("impl.stagnation.coverage", "needs two iterations of a live green loop"),
    ("impl.stagnation.test_count", "needs two iterations of a live green loop"),
    ("impl.stagnation.test_identity", "needs two iterations of a live green loop"),
    ("impl.stagnation.full_suite", "needs a live full-suite run"),
    ("impl.stagnation.e2e", "needs a live e2e loop"),
    # #2796 retired `impl.red_phase_failed`. Its one site moved to
    # `impl.red.preexisting_implementation`, which is absent from this list
    # because that row judges the state of the worktree -- infrastructure --
    # rather than model output, and this list is about model-output rows.
    ("impl.red.import_errors", "needs pytest run against the pre-implementation tree"),
    ("impl.green.collection_broken", "needs a pytest collection run"),
    ("spec.pinning_refusal", "needs a previous draft and a revision"),
    ("spec.conservation_gate", "needs a previous draft and a revision"),
    ("spec.edit_script_rejected", "needs a spec and a SEARCH/REPLACE revision"),
    ("spec.finalize.draft_guard", "needs a spec draft; none survives on main"),
    ("spec.review.empty_draft", "needs a spec draft; none survives on main"),
    ("spec.review_blocked", "is a reviewer model's verdict, not a mechanical rule"),
    ("spec.reviewer_verdict_unreadable", "is about the reviewer's output"),
    ("impl.reviewer_verdict_unreadable", "is about the reviewer's output"),
    ("impl.test_plan_revision_incomplete", "needs a test-plan revision"),
    ("lld.test_plan_validation", "needs the LLD draft loop"),
    ("lld.best_of_n_unusable", "needs N drafts"),
    ("lld.edit_script_rejected", "needs an LLD and a SEARCH/REPLACE revision"),
)


@dataclass
class Verdict:
    """One gate, run over one artifact of one feature."""

    issue: int
    gate: str
    artifact: str
    refused: bool
    message: str = ""

    @property
    def outcome(self) -> str:
        return "REFUSE" if self.refused else "pass"


@dataclass
class AuditCoverage:
    """What was examined. Counted, never estimated."""

    features: int = 0
    files_examined: int = 0
    files_missing: list[str] = field(default_factory=list)
    llds_examined: int = 0
    # #2787 removed `commits_examined` and `git_unreadable`. They counted the
    # merged-commit-subject arm, which went with `pr.commit_message_guard`.


# ---------------------------------------------------------------------------
# The gates, each as the pipeline's own function
# ---------------------------------------------------------------------------


def _gate_code_response(code: str, rel: str, repo: Path) -> tuple[bool, str]:
    """impl.file_generation_failed: the implementer's mechanical validation."""
    from assemblyzero.workflows.testing.nodes.implementation.parsers import (
        validate_code_response,
    )

    valid, message = validate_code_response(code, rel, "", str(repo))
    return (not valid), message


def _gate_test_structure(content: str, path: Path | None = None) -> tuple[bool, str]:
    """impl.scaffold_suite_invalid: the scaffolder's structural validator.

    ``path`` is the shipped file's own location, so the checker can resolve an
    assertion helper imported from a neighbouring module exactly as the
    pipeline does at N2.5 (#2737). Without it only same-module helpers are
    followed, which is the weaker reading and would let this audit pass while
    the shipped gate still refused.
    """
    from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
        imported_helper_sources,
        validate_test_structure,
    )

    imported = imported_helper_sources(content, path.parent) if path else {}
    errors = validate_test_structure(content, [], imported)
    return bool(errors), "; ".join(errors)[:400]


def _gate_stub_count(content: str) -> tuple[bool, str]:
    """impl.deterministic_failure: the scaffolder's stub count."""
    from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
        count_stub_tests,
    )

    total, stubs, names = count_stub_tests(content)
    if stubs:
        return True, f"{stubs} of {total} test(s) read as stubs: {', '.join(names[:5])}"
    return False, f"0 of {total} test(s) read as stubs"


def _gate_path_enforcement(rel: str, lld_content: str) -> tuple[bool, str]:
    """impl.path_enforcement: what the gate says about a file it did not plan.

    Advisory since #2736, so this can no longer report a refusal: the gate says
    its sentence and the implementer writes the file. The sentence is still
    carried into the report, because "the plan did not name this and it was
    written anyway" is worth reading -- it is the refusal's evidence, minus the
    consequence.

    It calls `path_advisory`, the same function the implementation stage calls,
    so the audit cannot pass while the shipped gate would still object.
    """
    from assemblyzero.hooks.file_write_validator import path_advisory
    from assemblyzero.utils.lld_path_enforcer import extract_paths_from_lld

    spec = extract_paths_from_lld(lld_content)
    allowed = set(spec.get("all_allowed_paths") or ())
    if not allowed:
        return False, "LLD declares no paths; the gate is inert"
    notice = path_advisory(rel, allowed)
    return False, notice or "Path matches LLD specification"


def _gate_lld_mechanical(lld_content: str, repo: Path, issue: int) -> tuple[bool, str]:
    """lld.mechanical_validation over the LLD as the requirements stage runs it."""
    from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
        _validate_lld_mechanical_inner,
    )

    result = _validate_lld_mechanical_inner(
        {"current_draft": lld_content, "target_repo": str(repo), "issue_number": issue}
    )
    errors = [str(e) for e in (result.get("validation_errors") or [])]
    return bool(errors), "; ".join(errors)[:400]


def _gate_scenario_ratio(lld_content: str) -> tuple[bool, str]:
    """impl.scenario_ratio_guard: the LLD's test plan against its requirements."""
    from assemblyzero.workflows.testing.nodes.load_lld import (
        extract_requirements,
        extract_test_plan_section,
        parse_test_scenarios,
    )
    from assemblyzero.workflows.testing.nodes.review_test_plan import (
        _run_mechanical_gates,
    )

    requirements = extract_requirements(lld_content)
    scenarios = parse_test_scenarios(extract_test_plan_section(lld_content))
    errors = _run_mechanical_gates(
        {
            "lld_content": lld_content,
            "test_scenarios": list(scenarios),
            "requirements": list(requirements),
        }
    )
    detail = f"{len(scenarios)} scenario(s), {len(requirements)} requirement(s)"
    return bool(errors), ("; ".join(errors)[:300] + " | " if errors else "") + detail


# ---------------------------------------------------------------------------
# The audit
# ---------------------------------------------------------------------------


# #2787: `merged_subject` stood here, reading the subject of the commit that
# closed each issue so `pr.commit_message_guard` could be scored against it.
# That gate is retired -- no graph ran it -- and it was this function's only
# caller. Reading an artifact no gate judges would be the same promise about
# nothing the retirement is removing, so the reader went with the gate.


def audit_feature(
    repo: Path, feature: Feature, coverage: AuditCoverage
) -> list[Verdict]:
    """Every runnable gate over every artifact of one feature."""
    verdicts: list[Verdict] = []
    coverage.features += 1

    lld_content = ""
    if feature.lld:
        lld_path = repo / feature.lld
        if lld_path.is_file():
            lld_content = lld_path.read_text(encoding="utf-8", errors="replace")
            coverage.llds_examined += 1
            refused, message = _gate_lld_mechanical(lld_content, repo, feature.issue)
            verdicts.append(Verdict(feature.issue, "lld.mechanical_validation",
                                    feature.lld, refused, message))
            refused, message = _gate_scenario_ratio(lld_content)
            verdicts.append(Verdict(feature.issue, "impl.scenario_ratio_guard",
                                    feature.lld, refused, message))
        else:
            coverage.files_missing.append(feature.lld)

    for rel in feature.sources + feature.tests:
        path = repo / rel
        if not path.is_file():
            coverage.files_missing.append(rel)
            continue
        coverage.files_examined += 1
        content = path.read_text(encoding="utf-8", errors="replace")
        if rel.endswith(".py"):
            refused, message = _gate_code_response(content, rel, repo)
            verdicts.append(Verdict(feature.issue, "impl.file_generation_failed",
                                    rel, refused, message))
        if rel in feature.tests and rel.endswith(".py"):
            refused, message = _gate_test_structure(content, path)
            # #2753: labelled `impl.test_file_validation` until 2026-09-04,
            # which named a row whose only code was the unreachable
            # `run_tests` node. The check below is the LIVE one at N2.5, and
            # its live consequence is this row -- so a refusal here now names
            # the gate that would actually have ended the run.
            verdicts.append(Verdict(feature.issue, "impl.scaffold_suite_invalid",
                                    rel, refused, message))
            refused, message = _gate_stub_count(content)
            verdicts.append(Verdict(feature.issue, "impl.deterministic_failure",
                                    rel, refused, message))
        if lld_content:
            refused, message = _gate_path_enforcement(rel, lld_content)
            verdicts.append(Verdict(feature.issue, "impl.path_enforcement",
                                    rel, refused, message))

    # #2787: the merged commit's subject was read here and scored against
    # `pr.commit_message_guard`. That gate is retired -- no graph ran it --
    # so nothing judges a commit subject any more, and the reader, the two
    # coverage counters and the report's line for them went with it.
    return verdicts


def audit(repo: Path, arc: tuple[Feature, ...] = BOOSTGAUGE_ARC) -> tuple[list[Verdict], AuditCoverage]:
    coverage = AuditCoverage()
    verdicts: list[Verdict] = []
    for feature in arc:
        verdicts.extend(audit_feature(repo, feature, coverage))
    return verdicts, coverage


def render(repo: Path, verdicts: list[Verdict], coverage: AuditCoverage,
           *, generated_at: str = "") -> str:
    """The report. Deterministic for a given input, except the timestamp."""
    stamp = generated_at or datetime.now().strftime(_TS_FMT)
    refusals = [v for v in verdicts if v.refused]
    by_gate: dict[str, tuple[int, int]] = {}
    for v in verdicts:
        ran, refused = by_gate.get(v.gate, (0, 0))
        by_gate[v.gate] = (ran + 1, refused + (1 if v.refused else 0))

    lines = [
        f"# Answer-key audit — {repo}",
        "",
        f"Generated {stamp}. The shipped code on main is the answer key; a "
        "refusal below is a gate rejecting content the operator shipped.",
        "",
        "`impl.path_enforcement` can no longer refuse anything (#2736, "
        "operator ruling 2026-09-04: the LLD's file list is a plan, not a "
        "contract). Where it once refused, its row now carries the advisory "
        "the implementation stage prints while writing the file anyway, so "
        "the disagreement between plan and build stays visible without a "
        "consequence attached. A refusal on the test-file gates means a "
        "hand-written test states its expectation in a way the gate does not "
        "recognise.",
        "",
        "## Coverage — counted, not estimated",
        "",
        f"- Features: {coverage.features}",
        f"- Files examined: {coverage.files_examined}"
        + (f" (missing: {', '.join(coverage.files_missing)})" if coverage.files_missing else ""),
        f"- LLDs examined: {coverage.llds_examined}",
        f"- Verdicts: {len(verdicts)}; refusals: {len(refusals)}",
        "",
        "## Per gate",
        "",
        "| gate | ran | refused |",
        "|---|---|---|",
    ]
    for gate, (ran, refused) in sorted(by_gate.items()):
        lines.append(f"| {gate} | {ran} | {refused} |")
    lines += ["", "## Refusals — each one is a false positive by construction", ""]
    if refusals:
        for v in sorted(refusals, key=lambda v: (v.issue, v.gate, v.artifact)):
            lines.append(f"- #{v.issue} `{v.gate}` on `{v.artifact}`: {v.message}")
    else:
        lines.append("None. Every runnable gate accepted every shipped artifact.")
    lines += ["", "## Every verdict", "", "| issue | gate | artifact | outcome | detail |", "|---|---|---|---|---|"]
    for v in sorted(verdicts, key=lambda v: (v.issue, v.gate, v.artifact)):
        detail = v.message.replace("|", "\\|").replace("\n", " ")[:160]
        lines.append(f"| #{v.issue} | {v.gate} | `{v.artifact}` | {v.outcome} | {detail} |")
    lines += ["", "## Not runnable against a finished artifact", ""]
    for gate, reason in NOT_RUNNABLE_HERE:
        lines.append(f"- `{gate}`: {reason}")
    lines.append("")
    return "\n".join(lines)
