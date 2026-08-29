"""The ADR 0226 form check as a launcher preflight (#2227).

#2219 built the checker and deliberately left this question open. The operator
ruled on 2026-08-12:

    The form check RUNS at launcher preflight, report-only by default. The
    launch refuses only when the issue carries at least one decision table and
    that table is malformed. An unconverted prose issue never refuses -- a
    refusal there is a false alarm by definition. The vacuous-EARS state is
    surfaced out loud. Form-check findings are labelled as the form check's,
    distinct from the semantic gate's output.

Why report-only is the default
------------------------------

ADR 0226 section 8 converts an issue when it next rolls, not in a sweep, so
nearly every issue in the fleet is still prose. A preflight that hard-refused on
form would block almost all of them, and a gate that fires on the ordinary case
is a gate people learn to wave through -- the same reasoning that scoped the
ADR-0217 equivalence check.

Why silence is not a pass
-------------------------

An issue with no ``## Requirements`` section passes every EARS check while
verifying nothing about its sentences. Reporting that as a clean bill would be
reading silence as assurance, which is the exact failure the checker's own
report is written to prevent. So the vacuous result is stated at launch.

What refuses, and what only reports
-----------------------------------

The ruling says "carries at least one decision table and that table is
malformed". Malformation is read as the table's OWN shape -- ADR 0226's second
check, completeness and disjointness -- because that is what a table can be
malformed about, and because a refusal has to be an unambiguous fact.

Row-to-criterion coverage is ADR 0226's third check and is treated separately,
on the checker's own account of its two join modes. With row IDs the join is
exact and a missing criterion is a hard fact, so it refuses. Without them the
join rests on count and outcome text, which the checker's docstring already
delegates to the semantic gate -- so it reports and does not refuse. EARS
findings never refuse: they are about prose sentences, which is precisely where
unconverted issues live.

`REFUSING_KINDS` and `EXACT_JOIN_REFUSES` are the two knobs. Widening the
refusal is a one-line change if the operator wants it wider.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from assemblyzero.workflows.requirements.discrimination_check import (  # noqa: E402  (#2387)
    DiscriminationReport,
    check_discrimination,
)
from assemblyzero.workflows.requirements.form_check import (
    FormReport,
    check_form,
)
from assemblyzero.workflows.requirements.scope_coverage import (  # noqa: E402  (#2645)
    ScopeReport,
    check_scope_coverage,
)

#: Violations of the table's own shape: wrong row count for its condition
#: count, or a repeated combination. These are what "malformed table" means.
REFUSING_KINDS = frozenset({"table-rows", "table-duplicate"})

#: Row-to-criterion coverage refuses only where the join is exact, i.e. the
#: table carries row IDs. Without IDs the checker itself calls the join weaker
#: and delegates combination correctness to the semantic gate.
EXACT_JOIN_REFUSES = True

LABEL = "Requirements form check (ADR 0226)"


@dataclass
class IssueForm:
    """One issue's form verdict at preflight."""

    issue: int
    report: FormReport | None = None
    error: str = ""            # the check could not run at all
    refusing: list = field(default_factory=list)   # violations that refuse
    reporting: list = field(default_factory=list)  # violations that only report
    #: #2387: the discrimination-coverage extension. Report-only, like the rest
    #: of the non-counting findings -- it reads intent from prose, so a refusal
    #: on it would block a roll over a phrasing choice.
    discrimination: DiscriminationReport | None = None
    #: #2645: the scope-coverage extension. Report-only for the same reason
    #: the form check is: no issue in the fleet declares a scope alias yet, so
    #: a refusal would fire on the ordinary case and be waved through.
    scope: ScopeReport | None = None

    @property
    def has_tables(self) -> bool:
        return bool(self.report and self.report.tables)

    @property
    def vacuous_ears(self) -> bool:
        return bool(self.report and not self.report.ears_ran)

    @property
    def vacuous_tables(self) -> bool:
        """A table is present and none of them was examined (#2650).

        `has_tables` cannot answer this: it is False both for an issue with no
        table and for one carrying a table this check does not examine, and
        the note it drove said "no decision table, so none was checked" for
        both. On boostgauge #331 that ran at every launch, over a nine-row
        table the rest of the pipeline treats as normative.
        """
        return bool(self.report and self.report.vacuous_tables)


def classify(report: FormReport) -> tuple[list, list]:
    """(refusing, reporting) violations, per the ruling.

    A table's own malformation refuses. A missing row criterion refuses only
    when the table it came from carries row IDs, because only then is the join
    exact enough for the finding to be a fact rather than a text-match.
    """
    exact_join_everywhere = bool(report.tables) and all(
        t.exact_join for t in report.tables
    )

    refusing, reporting = [], []
    for violation in report.violations:
        if violation.kind in REFUSING_KINDS:
            refusing.append(violation)
        elif (
            violation.kind == "row-criterion"
            and EXACT_JOIN_REFUSES
            and exact_join_everywhere
        ):
            refusing.append(violation)
        else:
            reporting.append(violation)
    return refusing, reporting


def check_issue(repo_root, issue: int, fetch) -> IssueForm:
    """Run the form check for one issue. Never raises."""
    result = IssueForm(issue=issue)
    try:
        title, body = fetch(repo_root, issue)
    except Exception as exc:  # noqa: BLE001 - a read failure is not a verdict
        result.error = str(exc)
        return result

    if not (body or "").strip():
        result.error = "the issue body is empty, so there was nothing to check"
        return result

    result.report = check_form(body)
    result.refusing, result.reporting = classify(result.report)
    # #2387: never allowed to cost the form check its verdict.
    try:
        result.discrimination = check_discrimination(body)
    except Exception:  # noqa: BLE001 - an extension is not the gate
        result.discrimination = None
    # #2645: same containment. The scope check reads the TITLE as well, which
    # is the witness that survived nineteen ruled conflicts on boostgauge #331
    # while the table lost a row.
    try:
        result.scope = check_scope_coverage(title, body)
    except Exception:  # noqa: BLE001
        # fail-open: an extension that crashes must not cost the form check
        # its verdict, and this one parses free-form prose from every issue in
        # the fleet. None is NOT a clean bill -- `render` prints nothing at all
        # for a None scope, so the operator sees the disclosure line missing
        # rather than a passing one. Report-only either way, so nothing is
        # gated on it.
        result.scope = None
    return result


def render(results: list[IssueForm]) -> tuple[str, bool]:
    """(operator-facing text, refuse). Labelled as the form check's own.

    The semantic gate's refusal opens "BLOCKED: this repository has N unanswered
    questions". This one always names itself, so one defect never reads as two
    complaints in two formats.
    """
    lines = [f"{LABEL} -- deterministic, no model calls:"]
    refuse = False

    for item in results:
        head = f"  #{item.issue}: "

        if item.error:
            lines.append(
                head + f"could not be checked ({item.error}). Nothing about "
                "this issue's form has been verified."
            )
            continue

        notes = []
        if item.vacuous_ears:
            # Load-bearing: a pass here verified nothing about any sentence.
            notes.append(
                "no '## Requirements' section, so NO sentence in it was checked "
                "-- this is a vacuous pass, not a clean bill"
            )
        if item.vacuous_tables:
            # #2650: the launch path said "no decision table" about an issue
            # carrying one. Load-bearing for the same reason the EARS note
            # above is: this is the surface an operator reads before spending
            # a roll, and it was reporting the checked-nothing case in the
            # words of the nothing-to-check case.
            notes.append(
                f"{item.report.non_decision_tables} table(s) present and NOT "
                f"of the checked kind (ADR 0226 3.2 wants plain yes/no "
                f"columns), so NO table was checked -- vacuous, not a clean bill"
            )
        elif not item.has_tables:
            notes.append("no table in this issue, so none was checked")

        if item.refusing:
            refuse = True
            lines.append(head + f"{len(item.refusing)} form violation(s) that "
                                "block a roll:")
            for violation in item.refusing:
                lines.append(f"      {violation}")
        elif item.reporting:
            lines.append(head + f"{len(item.reporting)} form finding(s), "
                                "reported only:")
            for violation in item.reporting:
                lines.append(f"      {violation}")
        elif not notes:
            lines.append(head + "form holds.")
        else:
            lines.append(head + "no form violations.")

        for note in notes:
            lines.append(f"      note: {note}")

        # #2387: printed on EVERY issue, pass or fail. A check that speaks only
        # when it complains leaves silence to mean two different things, which
        # is the same complaint #2381 makes about box health.
        if item.discrimination is not None:
            lines.append(f"      {item.discrimination.disclosure()}")
            for violation in item.discrimination.violations:
                lines.append(f"        {violation}")

        # #2645: printed on every issue for the same reason. This is the only
        # check in the stack that can see an element the table never carried,
        # so its silence has to be distinguishable from it not having run.
        if item.scope is not None:
            lines.append(f"      {item.scope.disclosure()}")
            for violation in item.scope.violations:
                lines.append(f"        {violation}")

        if item.reporting and item.refusing:
            lines.append(
                f"      plus {len(item.reporting)} further finding(s) reported "
                "but not blocking"
            )

    if refuse:
        lines += [
            "",
            "  BLOCKED by the form check: a decision table above is malformed.",
            "  This is a counting result, not a judgment -- the table does not",
            "  carry the rows its own conditions require, or a row has no",
            "  acceptance criterion. Fix the table in the issue, then launch",
            "  again. Nothing has been spent.",
        ]
    else:
        lines += [
            "",
            "  Reported only; the roll proceeds. The form check cannot report",
            "  CORRECTNESS -- a table can enumerate every combination and state",
            "  the wrong outcome in every row.",
        ]

    return "\n".join(lines), refuse


def check_form_at_preflight(repo_root, issues: list[int], fetch) -> tuple[str, bool]:
    """The whole preflight step: (text to print, whether to refuse)."""
    results = [check_issue(repo_root, issue, fetch) for issue in issues or []]
    if not results:
        return "", False
    return render(results)
