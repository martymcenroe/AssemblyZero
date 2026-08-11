"""Deterministic completeness checker for the ADR 0226 requirement form (#2219).

ADR 0226 adopts an authoring form whose completeness a program can verify. This
is that program. It makes no model calls, reads nothing but the issue text, and
returns the same answer every time it is run against the same input.

It verifies three things:

1. **EARS conformance.** Bullets under a ``## Requirements`` heading must match
   one of the five patterns. Acceptance criteria are never EARS-validated: a
   row criterion is a table row's projection into the test list, not a
   requirement sentence, and its terse form is mandated by ADR 0226 section
   3.2.
2. **Table completeness and disjointness.** A decision table of ``n`` binary
   conditions carries ``2^n`` rows and repeats no combination.
3. **Row-to-criterion coverage.** Every row appears as its own acceptance
   criterion.

What it cannot do
-----------------

Report completeness as correctness. A table can enumerate every combination
and state the wrong outcome in every row, and nothing here can tell. The
report names what was verified and what was not, per standard 0028, and never
lets a reader mistake the weaker of the two join modes for the stronger.

The two join modes
------------------

With row IDs (the convention for every issue converted after boostgauge #7)
the join is exact: the ID sets on both sides must be a bijection, and each
criterion's outcome text must match the outcome cell of the row it names.

Without row IDs the checker runs two hard checks instead — a table of ``N``
rows requires exactly ``N`` criteria opening with the table's subject word,
and each row's outcome must match a distinct criterion in that group. What
this mode cannot verify, whether a criterion describes its own row's
combination of condition values, is delegated to the semantic
requirements-consistency gate. That delegation is real rather than hopeful: a
criterion naming the wrong combination contradicts its own table, which is
the conflict class the gate already fires on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# EARS (ADR 0226 section 3.1)
# ---------------------------------------------------------------------------

#: The five patterns, in match order. The keyword-led forms are tried before
#: the ubiquitous form so a conditional cannot be scored as a universal law --
#: which is the whole point of the rule (both halves of the boostgauge #7
#: collision were conditionals written as universals).
EARS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("event-driven", re.compile(r"^WHEN\b.*\bshall\s+\S")),
    ("state-driven", re.compile(r"^WHILE\b.*\bshall\s+\S")),
    ("unwanted behavior", re.compile(r"^IF\b.*\bTHEN\b.*\bshall\s+\S")),
    ("optional feature", re.compile(r"^WHERE\b.*\bshall\s+\S")),
    ("ubiquitous", re.compile(r"^The\b.*\bshall\s+\S")),
)

EARS_FORMS = (
    "The <system> shall <response> | "
    "WHEN <trigger> the <system> shall <response> | "
    "WHILE <state> ... | IF <condition> THEN ... | WHERE <feature> ..."
)

REQUIREMENTS_HEADING = "Requirements"
CRITERIA_HEADING = "Acceptance Criteria"

_BINARY_VALUES = frozenset({"yes", "no"})
_ROW_ID = re.compile(r"^[A-Z][A-Za-z]*[0-9]+$")
_LIST_ITEM = re.compile(r"^(\s*)[-*+]\s+(?:\[[ xX]\]\s*)?(.*)$")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_LEADING_ID = re.compile(r"^([A-Z][A-Za-z]*[0-9]+)[.):]?\s+")


def _norm(text: str) -> str:
    """Compare text the way a reader does: no code ticks, no case, one space."""
    stripped = text.replace("`", "").replace("*", "")
    return re.sub(r"\s+", " ", stripped).strip().casefold()


def _first_word(text: str) -> str:
    match = re.search(r"[A-Za-z][A-Za-z0-9_-]*", text.replace("`", ""))
    return match.group(0) if match else ""


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    """One thing the form requires that this document does not do."""

    kind: str
    where: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.where}: {self.detail}"


@dataclass
class TableReport:
    """What was checked about one decision table, and how strongly."""

    subject: str
    line_no: int
    condition_count: int
    row_count: int
    expected_rows: int
    join_mode: str
    row_ids: list[str] = field(default_factory=list)
    matched_rows: int = 0
    group_size: int = 0

    @property
    def exact_join(self) -> bool:
        return self.join_mode == "exact"

    @property
    def join_description(self) -> str:
        if self.exact_join:
            return "row join: exact (IDs)"
        return (
            "row join: count and outcome; combination correctness delegated "
            "to the semantic gate"
        )


@dataclass
class FormReport:
    """The whole verdict for one issue body."""

    requirements_examined: int = 0
    requirements_found: int = 0
    ears_ran: bool = False
    nested_bullets_skipped: int = 0
    criteria_examined: int = 0
    criteria_section_found: bool = False
    tables: list[TableReport] = field(default_factory=list)
    non_decision_tables: int = 0
    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


# ---------------------------------------------------------------------------
# Document structure
# ---------------------------------------------------------------------------


def section_lines(body: str, heading: str) -> list[str] | None:
    """Lines under an exact ``## <heading>``, up to the next heading.

    Returns None when the section is absent, which is a different fact from
    the section being empty and must not be flattened into one.
    """
    lines = body.splitlines()
    start = None
    level = 0
    for i, line in enumerate(lines):
        match = _HEADING.match(line)
        if not match:
            continue
        if start is None:
            if match.group(2).strip() == heading:
                start = i + 1
                level = len(match.group(1))
            continue
        if len(match.group(1)) <= level:
            return lines[start:i]
    if start is None:
        return None
    return lines[start:]


def list_items(lines: list[str]) -> tuple[list[str], int]:
    """Top-level list items, and the count of nested ones left unchecked.

    Nested bullets are elaboration on the item above them, not separate
    requirements. They are counted rather than silently dropped.
    """
    items: list[str] = []
    nested = 0
    for line in lines:
        match = _LIST_ITEM.match(line)
        if not match:
            continue
        text = match.group(2).strip()
        if not text:
            continue
        if match.group(1):
            nested += 1
        else:
            items.append(text)
    return items, nested


@dataclass
class RawTable:
    line_no: int
    header: list[str]
    rows: list[list[str]]


def _split_row(line: str) -> list[str]:
    cells = line.strip().split("|")
    if cells and not cells[0].strip():
        cells = cells[1:]
    if cells and not cells[-1].strip():
        cells = cells[:-1]
    return [c.strip() for c in cells]


def parse_tables(body: str) -> list[RawTable]:
    """Every markdown pipe table in the document, in order."""
    tables: list[RawTable] = []
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        if not lines[i].strip().startswith("|"):
            i += 1
            continue
        if i + 1 >= len(lines) or not re.fullmatch(
            r"\|?[\s:|-]+\|?", lines[i + 1].strip()
        ):
            i += 1
            continue
        header = _split_row(lines[i])
        rows: list[list[str]] = []
        j = i + 2
        while j < len(lines) and lines[j].strip().startswith("|"):
            rows.append(_split_row(lines[j]))
            j += 1
        tables.append(RawTable(line_no=i + 1, header=header, rows=rows))
        i = j
    return tables


def _has_id_column(table: RawTable) -> bool:
    if len(table.header) < 3 or not table.rows:
        return False
    return all(
        row and _ROW_ID.fullmatch(row[0].replace("`", "").strip())
        for row in table.rows
    )


def is_decision_table(table: RawTable) -> bool:
    """A table whose non-outcome columns hold only plain yes and no answers.

    ADR 0226 section 3.2 defines the grid this way. Anything else in an issue
    body -- a risk grid, a flag reference -- is a table but not a decision
    table, and is reported as unchecked rather than checked wrongly.
    """
    if not table.rows or len(table.header) < 2:
        return False
    first = 1 if _has_id_column(table) else 0
    condition_columns = range(first, len(table.header) - 1)
    if not condition_columns:
        return False
    for row in table.rows:
        if len(row) != len(table.header):
            return False
        for col in condition_columns:
            if _norm(row[col]) not in _BINARY_VALUES:
                return False
    return True


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def _max_matching(candidates: list[list[int]], right_size: int) -> list[int | None]:
    """Maximum bipartite matching (Kuhn's algorithm).

    Greedy assignment is wrong here: 'unchanged' is a substring of 'unchanged;
    the CLI value is not written', so matching in row order can consume the
    only criterion a later row could have used and report a false gap.
    """
    assigned: list[int | None] = [None] * right_size
    result: list[int | None] = [None] * len(candidates)

    def augment(left: int, seen: set[int]) -> bool:
        for right in candidates[left]:
            if right in seen:
                continue
            seen.add(right)
            holder = assigned[right]
            if holder is None or augment(holder, seen):
                assigned[right] = left
                result[left] = right
                return True
        return False

    for left in range(len(candidates)):
        augment(left, set())
    return result


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_ears(body: str, report: FormReport) -> None:
    """Validate the marked requirements section. Absence is a vacuous pass."""
    lines = section_lines(body, REQUIREMENTS_HEADING)
    if lines is None:
        report.ears_ran = False
        return

    report.ears_ran = True
    items, nested = list_items(lines)
    report.nested_bullets_skipped = nested
    report.requirements_found = len(items)
    report.requirements_examined = len(items)

    for index, item in enumerate(items, 1):
        sentence = re.sub(r"\s+", " ", item.replace("`", "")).strip()
        if any(pattern.match(sentence) for _, pattern in EARS_PATTERNS):
            continue
        report.violations.append(
            Violation(
                kind="ears",
                where=f"Requirements bullet {index}",
                detail=(
                    f"matches no EARS pattern: {sentence!r}. "
                    f"Expected one of: {EARS_FORMS}"
                ),
            )
        )


def _check_table_shape(
    table: RawTable, subject: str, has_ids: bool, report: FormReport
) -> tuple[int, list[tuple[str, ...]]]:
    """Completeness and disjointness. Returns (condition count, combinations)."""
    first = 1 if has_ids else 0
    condition_columns = list(range(first, len(table.header) - 1))
    n = len(condition_columns)
    expected = 2**n
    where = f"table '{subject}' (line {table.line_no})"

    if len(table.rows) != expected:
        report.violations.append(
            Violation(
                kind="table-rows",
                where=where,
                detail=(
                    f"{n} binary conditions require 2^{n} = {expected} rows; "
                    f"it carries {len(table.rows)}"
                ),
            )
        )

    combinations = [
        tuple(_norm(row[col]) for col in condition_columns) for row in table.rows
    ]
    seen: dict[tuple[str, ...], int] = {}
    for position, combo in enumerate(combinations, 1):
        if combo in seen:
            report.violations.append(
                Violation(
                    kind="table-duplicate",
                    where=where,
                    detail=(
                        f"rows {seen[combo]} and {position} repeat the same "
                        f"combination of condition values: {', '.join(combo)}"
                    ),
                )
            )
        else:
            seen[combo] = position
    return n, combinations


def _check_rows_exact(
    table: RawTable,
    subject: str,
    criteria: list[str],
    report: FormReport,
    table_report: TableReport,
) -> None:
    """ID mode: bijection on IDs, then outcome text per named row."""
    where = f"table '{subject}' (line {table.line_no})"
    row_ids = [row[0].replace("`", "").strip() for row in table.rows]
    outcomes = {
        rid: row[-1] for rid, row in zip(row_ids, table.rows, strict=False)
    }
    table_report.row_ids = row_ids

    criteria_by_id: dict[str, list[str]] = {}
    for text in criteria:
        match = _LEADING_ID.match(text)
        if match:
            criteria_by_id.setdefault(match.group(1), []).append(text)

    for rid in row_ids:
        matches = criteria_by_id.get(rid, [])
        if not matches:
            report.violations.append(
                Violation(
                    kind="row-criterion",
                    where=where,
                    detail=f"row {rid} has no acceptance criterion opening with {rid}",
                )
            )
            continue
        if len(matches) > 1:
            report.violations.append(
                Violation(
                    kind="row-criterion",
                    where=where,
                    detail=f"{len(matches)} acceptance criteria open with {rid}; expected exactly one",
                )
            )
            continue
        outcome = _norm(outcomes[rid])
        if outcome and outcome not in _norm(matches[0]):
            report.violations.append(
                Violation(
                    kind="row-criterion",
                    where=where,
                    detail=(
                        f"criterion {rid} does not carry its row's outcome. "
                        f"Row says {outcomes[rid]!r}; criterion reads {matches[0]!r}"
                    ),
                )
            )
        else:
            table_report.matched_rows += 1

    # A criterion carrying an ID with this table's letter prefix but no matching
    # row is this table's problem -- most likely a row deleted from the grid and
    # left behind in the list. IDs belonging to another table are not.
    prefixes = {re.sub(r"[0-9]+$", "", rid) for rid in row_ids}
    owned = {
        rid: texts
        for rid, texts in criteria_by_id.items()
        if re.sub(r"[0-9]+$", "", rid) in prefixes
    }
    table_report.group_size = sum(len(texts) for texts in owned.values())
    for orphan in sorted(set(owned) - set(row_ids)):
        report.violations.append(
            Violation(
                kind="row-criterion",
                where=where,
                detail=f"criterion {orphan} names a row this table does not contain",
            )
        )


def _check_rows_by_count_and_outcome(
    table: RawTable,
    subject: str,
    criteria: list[str],
    report: FormReport,
    table_report: TableReport,
) -> None:
    """No-ID mode: exact criterion count in the subject group, plus outcomes."""
    where = f"table '{subject}' (line {table.line_no})"
    if not subject:
        report.violations.append(
            Violation(
                kind="row-criterion",
                where=where,
                detail=(
                    "no subject word could be read from the outcome column "
                    "header, so its rows cannot be joined to criteria"
                ),
            )
        )
        return

    prefix = _norm(subject)
    group = [c for c in criteria if _norm(c).startswith(prefix)]
    table_report.group_size = len(group)

    if len(group) != len(table.rows):
        report.violations.append(
            Violation(
                kind="row-criterion",
                where=where,
                detail=(
                    f"{len(table.rows)} rows require exactly {len(table.rows)} "
                    f"acceptance criteria opening with '{subject}'; found {len(group)}"
                ),
            )
        )

    normalized_group = [_norm(c) for c in group]
    candidates = [
        [
            j
            for j, criterion in enumerate(normalized_group)
            if _norm(row[-1]) and _norm(row[-1]) in criterion
        ]
        for row in table.rows
    ]
    matching = _max_matching(candidates, len(group))
    table_report.matched_rows = sum(1 for m in matching if m is not None)

    for index, assigned in enumerate(matching):
        if assigned is None:
            report.violations.append(
                Violation(
                    kind="row-criterion",
                    where=where,
                    detail=(
                        f"row {index + 1} states {table.rows[index][-1]!r}, and no "
                        f"unclaimed criterion in the '{subject}' group carries that outcome"
                    ),
                )
            )


def check_tables(body: str, report: FormReport) -> None:
    """Completeness, disjointness and row coverage for every decision table."""
    criteria_lines = section_lines(body, CRITERIA_HEADING)
    report.criteria_section_found = criteria_lines is not None
    criteria: list[str] = []
    if criteria_lines is not None:
        criteria, _ = list_items(criteria_lines)
    report.criteria_examined = len(criteria)

    all_tables = parse_tables(body)
    decision_tables = [t for t in all_tables if is_decision_table(t)]
    report.non_decision_tables = len(all_tables) - len(decision_tables)

    seen_ids: dict[str, str] = {}

    for table in decision_tables:
        has_ids = _has_id_column(table)
        subject = _first_word(table.header[-1])
        n, _ = _check_table_shape(table, subject, has_ids, report)

        table_report = TableReport(
            subject=subject or "(unnamed)",
            line_no=table.line_no,
            condition_count=n,
            row_count=len(table.rows),
            expected_rows=2**n,
            join_mode="exact" if has_ids else "count-and-outcome",
        )

        if not report.criteria_section_found:
            report.violations.append(
                Violation(
                    kind="row-criterion",
                    where=f"table '{table_report.subject}' (line {table.line_no})",
                    detail=(
                        f"no '## {CRITERIA_HEADING}' section, so none of its "
                        f"{len(table.rows)} rows has a criterion"
                    ),
                )
            )
        elif has_ids:
            _check_rows_exact(table, subject, criteria, report, table_report)
        else:
            _check_rows_by_count_and_outcome(
                table, subject, criteria, report, table_report
            )

        for rid in table_report.row_ids:
            if rid in seen_ids:
                owner = seen_ids[rid]
                clash = (
                    "twice in this table"
                    if owner == table_report.subject
                    else f"already by table '{owner}'"
                )
                report.violations.append(
                    Violation(
                        kind="table-duplicate",
                        where=f"table '{table_report.subject}' (line {table.line_no})",
                        detail=(
                            f"row ID {rid} is used {clash}; IDs are unique "
                            f"across the issue"
                        ),
                    )
                )
            else:
                seen_ids[rid] = table_report.subject

        report.tables.append(table_report)


def check_form(body: str) -> FormReport:
    """Run every form check over one issue body."""
    report = FormReport()
    check_ears(body, report)
    check_tables(body, report)
    return report


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def render_report(report: FormReport, label: str) -> str:
    """Render the operator-facing report. Every zero carries its denominator."""
    rule = "=" * 70
    out = [rule, f"Requirements form check -- {label}", rule, "", "EARS"]

    if not report.ears_ran:
        out += [
            "  0 requirement sentences examined out of 0; EARS check did not run.",
            f"  This issue has no '## {REQUIREMENTS_HEADING}' section. That is an",
            "  honest vacuous result, not a pass: nothing was checked.",
        ]
    else:
        failures = sum(1 for v in report.violations if v.kind == "ears")
        out.append(
            f"  {report.requirements_examined - failures} of "
            f"{report.requirements_examined} requirement sentences match an "
            f"EARS pattern."
        )
        if report.nested_bullets_skipped:
            out.append(
                f"  {report.nested_bullets_skipped} nested bullet(s) were read as "
                f"elaboration and not EARS-checked."
            )

    out.append("")
    if not report.tables:
        out.append("Decision tables: 0 found, so 0 checked.")
    else:
        out.append(f"Decision tables: {len(report.tables)}")
        for table in report.tables:
            out += [
                f"  {table.subject} (line {table.line_no}) -- "
                f"{table.condition_count} binary condition(s), "
                f"{table.row_count} of {table.expected_rows} required rows",
                f"    {table.join_description}",
                f"    {table.matched_rows} of {table.row_count} rows joined to a "
                f"criterion; {table.group_size} criteria in its group",
            ]

    out.append("")
    if report.criteria_section_found:
        out.append(f"Acceptance criteria examined: {report.criteria_examined}")
    else:
        out.append(f"Acceptance criteria: no '## {CRITERIA_HEADING}' section found.")

    out += ["", "Not verified"]
    out += [
        "  - Whether any requirement, row or criterion states the CORRECT",
        "    behavior. Completeness is a property of form. A table can",
        "    enumerate every combination and be wrong in every row.",
    ]
    if any(not t.exact_join for t in report.tables):
        weak = ", ".join(t.subject for t in report.tables if not t.exact_join)
        out += [
            f"  - For {weak}: that each criterion describes its own row's",
            "    combination of condition values. Those tables carry no row IDs,",
            "    so the join rests on count and outcome text. Combination",
            "    correctness is delegated to the semantic consistency gate.",
        ]
    if report.non_decision_tables:
        out.append(
            f"  - {report.non_decision_tables} markdown table(s) whose non-outcome "
            f"columns are not plain yes/no, so they are not decision tables."
        )
    if not report.ears_ran:
        out += [
            "  - Every sentence in this issue. With no requirements section,",
            "    nothing was read as a requirement sentence, so the EARS rule",
            "    was not applied to anything.",
        ]

    out += [""]
    if report.ok:
        out.append("RESULT: PASS -- 0 violations of the ADR 0226 form.")
    else:
        out.append(f"RESULT: FAIL -- {len(report.violations)} violation(s).")
        out.append("")
        for violation in report.violations:
            out.append(f"  {violation}")

    out += ["", rule]
    return "\n".join(out) + "\n"
