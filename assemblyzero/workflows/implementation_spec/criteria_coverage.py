"""Every LLD pass criterion must have a test in the spec (#2239).

The spec stage had no mechanical check that the LLD's pass criteria were each
tested. That judgment lived only in the adversarial reviewer, which makes a miss
cost a full review iteration and bounds detection by the iteration cap.

run-issue7-082047 (boostgauge, 2026-08-12) is the exhibit. LLD-007 carries
twenty-two requirements, twelve of them decision-table rows (REQ-9 through
REQ-20). The drafter omitted the row tests; the reviewer caught it semantically
in its second REVISE -- "completely omits 12 required state matrix tests" --
three iterations were spent, and the stage died at the cap with the omission
among the reasons. Counting is not what a reviewer is for. In that same run it
also caught a test feeding malformed JSON to dodge type validation, and an
exception-handling defect that would crash the app and lose user data; those are
the catches worth ninety seconds of model time. The twelve-test count was not.

One join mode, and an honest abstention (#2619)
-----------------------------------------------

**exact** -- the criteria carry ``REQ-N`` tags and the spec's tests cite them,
so the mapping is a join on identifiers. A criterion ID either has a test
citing it or it does not, which is a fact, so this gates.

There used to be a **count-and-outcome** fallback: with no usable tags, criteria
were matched to tests by outcome text under maximum bipartite matching. It
existed because derived criterion IDs could arrive mangled. **#2607/#2611
injection now carries the criteria tables byte-verbatim from issue to LLD to
spec, so the case it served is structurally gone**, and the operator ruled it
removed rather than classified -- classifying dead code enshrines it.

It was also a correlate in both directions, which is why removal rather than
demotion was right: a test containing a criterion's words is not a test
covering it, and a test covering a criterion in different words was reported
missing. A false veto is the #2539 disease.

Where the fallback used to guess, the check now **abstains and says so**: an
untagged criteria table is reported not-applicable, naming the untagged rows,
per the #1870 convention that a check which verified nothing must never render
as a check that passed. Verified before removal against boostgauge's live #331
state, where exact mode engages on both sides: every row of the LLD's `10.1
Test Scenarios` table carries a REQ tag, and its spec's thirteen tests cite
REQ-1 through REQ-13.

What exact mode still cannot see
--------------------------------

Two rows may carry the same tag -- LLD-007's rows 040 and 041 are both REQ-4,
one for ``--reset-config`` alone and one with ``--size`` -- and a single test
tagged REQ-4 marks both covered. Joining on a tag can only prove a tag was
tested. Row-level identity is what boostgauge #284 adds, and this check moves to
it for free when it lands, since the join key is read from the row. Until then
the residue is one test short on a shared tag, not twelve missing tests, and it
stays where it already was: with the semantic reviewer.

Reuse, deliberately
-------------------

``parse_tables`` and ``_norm`` come from the form checker rather than being
reimplemented here. One markdown-table parser, used by both callers: a second
copy would drift from the first, which is the failure this codebase has already
paid for twice (#1586, #1698).

``_max_matching`` was imported too, for the outcome fallback's bipartite
assignment. #2619 removed the fallback, so the import went with it -- an unused
import is a live reference to a removed mechanism.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from assemblyzero.workflows.requirements.form_check import (
    _norm,
    parse_tables,
)

#: A criterion tag as it appears in an LLD row or a spec test docstring.
REQ_TAG = re.compile(r"\bREQ-(\d+)\b", re.IGNORECASE)

#: Fenced blocks, with or without a language hint. Test docstrings live inside
#: them; prose outside them does not count. spec-0041 says "All test assertions
#: trace to requirements REQ-1 through REQ-7" in its closing prose -- a range in
#: a sentence, naming no test, which must not read as coverage of seven.
_CODE_FENCE = re.compile(r"```[\w]*\s*\n(.*?)```", re.DOTALL)

_TEST_DEF = re.compile(r"(?m)^[ \t]*(?:async[ \t]+)?def[ \t]+(test_\w+)")

#: The LLD table that states pass criteria. Both shapes in the fleet today are
#: "| ID | Scenario | Type | ... |", with the assertion in the last column and a
#: dedicated "Pass Criteria" column in the newer template.
_SCENARIO_COLUMN = "scenario"
_CRITERIA_COLUMN = "pass criteria"
_ID_COLUMN = "id"

MODE_EXACT = "exact (criterion IDs)"
#: #2619 removed the count-and-outcome fallback. The name is gone with it --
#: a constant kept "for compatibility" is how a removed mode gets resurrected.


@dataclass(frozen=True)
class Criterion:
    """One row of the LLD's pass-criteria table."""

    key: str          # "REQ-9", or the row's own ID when the row carries no tag
    row_id: str       # the table's ID column, for a report a human can look up
    scenario: str     # what the row is about, quoted back in the failure
    outcome: str      # the assertion text, used by count-and-outcome matching
    tagged: bool      # whether `key` came from a REQ tag


@dataclass
class CoverageReport:
    ran: bool = False
    join_mode: str = ""
    criteria: list[Criterion] = field(default_factory=list)
    missing: list[Criterion] = field(default_factory=list)
    test_count: int = 0
    reason: str = ""          # why it did not run, when it did not

    @property
    def ok(self) -> bool:
        return not self.missing

    @property
    def covered(self) -> int:
        return len(self.criteria) - len(self.missing)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def _column(header: list[str], wanted: str) -> int | None:
    for index, cell in enumerate(header):
        if _norm(cell) == wanted:
            return index
    return None


def _req_key(cells: list[str]) -> str | None:
    """The first REQ tag anywhere in the row, normalised to upper case."""
    for cell in cells:
        found = REQ_TAG.search(cell)
        if found:
            return f"REQ-{found.group(1)}"
    return None


def lld_criteria(lld: str) -> list[Criterion]:
    """Every pass criterion stated by the LLD's test-scenario table.

    A table qualifies when it has a Scenario column, or a Pass Criteria column
    beside an ID column. Anything else in an LLD -- a risk grid, an alternatives
    table -- is left alone rather than mis-read as criteria, the same
    conservatism ``is_decision_table`` applies in the form checker.
    """
    criteria: list[Criterion] = []

    for table in parse_tables(lld):
        header = table.header
        scenario_at = _column(header, _SCENARIO_COLUMN)
        criteria_at = _column(header, _CRITERIA_COLUMN)
        id_at = _column(header, _ID_COLUMN)

        if scenario_at is None and not (criteria_at is not None and id_at is not None):
            continue

        for row in table.rows:
            if len(row) != len(header) or not any(cell.strip() for cell in row):
                continue

            row_id = row[id_at].replace("`", "").strip() if id_at is not None else ""
            scenario = row[scenario_at] if scenario_at is not None else row_id
            outcome = row[criteria_at] if criteria_at is not None else row[-1]

            tag = _req_key(row)
            key = tag or row_id
            if not key:
                continue

            criteria.append(
                Criterion(
                    key=key,
                    row_id=row_id,
                    scenario=scenario,
                    outcome=outcome,
                    tagged=tag is not None,
                )
            )

    return criteria


def spec_tests(spec: str) -> list[tuple[str, str]]:
    """(test name, test source) for every test function in the spec's fences.

    Everything from one ``def test_`` up to the next belongs to the first, which
    keeps a docstring with its own function without needing to parse the file --
    spec snippets are frequently not valid standalone modules.
    """
    tests: list[tuple[str, str]] = []

    for fence in _CODE_FENCE.findall(spec):
        found = list(_TEST_DEF.finditer(fence))
        for index, match in enumerate(found):
            end = found[index + 1].start() if index + 1 < len(found) else len(fence)
            tests.append((match.group(1), fence[match.start():end]))

    return tests


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------


def criteria_coverage(spec: str, lld: str) -> CoverageReport:
    """Which LLD pass criteria have no test in the spec."""
    criteria = lld_criteria(lld)
    if not criteria:
        return CoverageReport(
            ran=False,
            reason="the LLD states no pass-criteria table to check against",
        )

    # #2619: no ID to join on is NOT APPLICABLE, never a weaker join.
    #
    # The substring fallback existed because derived criterion IDs could arrive
    # mangled. #2607/#2611 injection now carries the criteria tables
    # byte-verbatim from issue to LLD to spec, so the case it served is
    # structurally gone -- and classifying dead code enshrines it. Removed.
    #
    # Reporting not-applicable rather than guessing is the #1870 convention:
    # a check that verified nothing must never render as a check that passed.
    if not all(c.tagged for c in criteria):
        untagged = [c.row_id or "(no id)" for c in criteria if not c.tagged]
        return CoverageReport(
            ran=False,
            reason=(
                f"{len(untagged)} of {len(criteria)} pass criteria carry no "
                f"REQ tag to join on ({', '.join(untagged[:5])}"
                + (f", and {len(untagged) - 5} more" if len(untagged) > 5 else "")
                + "), so coverage cannot be established by identity. Tag the "
                "rows; matching outcome prose was removed in #2619 because a "
                "test containing a criterion's words is not a test covering it"
            ),
        )

    tests = spec_tests(spec)
    tagged_in_spec = {
        f"REQ-{n}"
        for _name, body in tests
        for n in REQ_TAG.findall(body)
    }

    if not tests or not tagged_in_spec:
        # Every criterion is tagged and the spec cites none of them: that is a
        # real, exact miss -- all of them -- not an absence of information.
        return CoverageReport(
            ran=True,
            join_mode=MODE_EXACT,
            criteria=criteria,
            missing=list(criteria),
            test_count=len(tests),
        )

    missing = [c for c in criteria if c.key not in tagged_in_spec]
    return CoverageReport(
        ran=True,
        join_mode=MODE_EXACT,
        criteria=criteria,
        missing=missing,
        test_count=len(tests),
    )


def format_report(report: CoverageReport) -> str:
    """The failure text the drafter reads. Names every miss at once, so one
    revision can address the whole set rather than one per iteration."""
    if not report.ran:
        return f"Criterion coverage not applicable: {report.reason}."

    head = (
        f"{report.covered}/{len(report.criteria)} LLD pass criteria have a test "
        f"across {report.test_count} spec test(s) [join {report.join_mode}]"
    )
    if report.ok:
        return head + "."

    lines = [
        f"{len(report.missing)} LLD pass criterion(s) have no test in the spec "
        f"[join {report.join_mode}]. Add a test for each:",
    ]
    # #2619: a report that RAN has only tagged criteria -- an untagged table
    # abstains above and never reaches here -- so the untagged label branch
    # this used to carry was unreachable and went with the fallback.
    for c in report.missing:
        where = f" (row {c.row_id})" if c.row_id else ""
        lines.append(f"  - {c.key}{where}: {c.scenario} -- expected: {c.outcome}")
    return "\n".join(lines)
