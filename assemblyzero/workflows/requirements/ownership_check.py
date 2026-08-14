"""Deterministic ownership checker for the ADR 0228 discipline (#2315).

ADR 0226 gave requirements a checkable form for their conditions. ADR 0228 is
its sibling and does the same for outcomes: one variable, one owner, and only
the owner asserts. This is the program that enforces it.

Zero model calls, the same trajectory as the ADR 0226 table checks. Variables
are literal key names, so per-criterion extraction is lexical rather than
semantic: a criterion asserts ``theme`` when it writes ``theme`` in code ticks.

The five checks
---------------

1. **Table well-formedness** (clause 1). Each row names a variable, defines its
   extension by naming at least one literal key, and gives exactly one owner
   group. No variable is declared twice.
2. **Undeclared assertion** (clause 1). A criterion that names a key the table
   does not declare is asserting a variable whose extension nobody wrote down.
3. **Non-owner assertion** (clause 2). A criterion outside a variable's owner
   group may cite the owner. It may not name the variable on its own account.
4. **Boundary terms** (clause 4). A term used to partition variables
   (``threshold values``, ``a non-threshold key``) owes the table a membership
   test.
5. **Unscoped universals** (clause 3). ``never``, ``always``, ``only``,
   ``byte-identical``, ``nothing else`` and ``no other`` carry their held-fixed
   conditions in the same claim, or cite the exception that limits them.

Everything is reported in one pass, so one revision addresses the whole set
(the #2239 pattern). A checker that surfaces one violation per run turns a
converted issue into a queue of round trips.

The vacuous state
-----------------

An issue with no variable table gets ``ownership was not checked``, never a
bare pass. This follows the #2227 ruling on the vacuous EARS state and exists
for the same reason: silence over an unchecked document reads as assurance,
and it is not.

None of the five checks runs without a variable table. Clause 3 could in
principle be checked on any prose, but ADR 0226 section 8 converts an issue
when it next rolls rather than in a sweep, so nearly every issue in the fleet
is unconverted. A universal-quantifier check sprayed across all of them would
fire on the ordinary case, and a gate that fires on the ordinary case is one
people learn to wave through.

What it cannot do
-----------------

Report that an owner is the RIGHT owner. A table can assign exactly one owner
per variable, be well formed in every respect, and name the wrong group in
every row. Ownership is a property of form. Review adjudicates content, and
the semantic gate remains the backstop for what these clauses cannot express.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

#: The header signature that identifies a variable table. A decision table
#: never carries these three, so detection needs no heading convention.
_VARIABLE_HEADERS = ("variable", "extension", "owner")

#: Universals from ADR 0228 clause 3. The first four are the set #2315 names.
#: "nothing" and "no other" are added because boostgauge #277, a corpus member,
#: is exactly "Nothing else touches it" and would otherwise escape.
_UNIVERSALS: tuple[str, ...] = (
    "never",
    "always",
    "only",
    "byte-identical",
    "byte for byte",
    "nothing",
    "no other",
)

#: An exception marker limits a universal wherever it sits in the claim, because
#: naming the exception is the whole job: "only hand-changed keys, unless the
#: user reset the config" is scoped by a clause that comes after the "only".
_EXCEPTION_MARKERS: tuple[str, ...] = (
    "unless",
    "except",
    "other than",
    "apart from",
    "aside from",
    "besides",
    "subject to",
    "governed by",
    "save for",
    "see ",
    "per ",
)

#: A condition marker limits a universal only when it comes BEFORE it. A leading
#: condition scopes what follows ("WHEN the app exits, only hand-changed keys
#: are written"). A trailing one conditions something else, which is how
#: boostgauge #290 escaped review: its "while the app ran" qualifies a direct
#: file edit, not the "only" three clauses earlier.
_CONDITION_MARKERS: tuple[str, ...] = (
    "when",
    "while",
    "if ",
    "where ",
    "provided",
    "given that",
)

#: Words the classifier regex can grab in front of "keys" or "values" that are
#: not partitioning terms. Without these the check reports "the keys" and
#: "these values" as undefined partitions, which is noise, and a check that
#: cries wolf is one people stop reading.
_CLASSIFIER_STOPWORDS = frozenset(
    """the a an its it their this that these those any all each both other same
    such new old every no non and or but with for from into only first last more
    most own two three four config file session default current given whose
    which what when where while than then also just even""".split()
)

#: Classifier shapes. A term standing in front of one of these nouns, or
#: negated with a ``non-`` prefix, is sorting keys into groups.
_CLASSIFIED_NOUNS = (
    "key",
    "keys",
    "value",
    "values",
    "setting",
    "settings",
    "field",
    "fields",
    "entry",
    "entries",
)

_CODE_SPAN = re.compile(r"`([^`]+)`")
_LEADING_ID = re.compile(r"^([A-Z][A-Za-z]*)([0-9]+)[.):]?\s+")
_GROUP_TAG = re.compile(r"^([A-Z][A-Za-z]*)$")
#: A config key: an identifier, optionally dotted for a nested path. Excludes
#: command-line flags, which start with a dash and are not config state.
_KEY_LIKE = re.compile(r"^[a-z_][a-z0-9_]*(\.[a-z_*][a-z0-9_*]*)*$")

_NON_PREFIXED = re.compile(r"\bnon-([a-z][a-z_-]{2,})\b")


def _norm(text: str) -> str:
    """Compare text the way a reader does: no ticks, no case, one space."""
    stripped = text.replace("`", "").replace("*", "")
    return re.sub(r"\s+", " ", stripped).strip().casefold()


def _singular(term: str) -> str:
    return term[:-1] if len(term) > 3 and term.endswith("s") else term


def _partition_term(term: str) -> str:
    """The classifying term a modifier carries, or "" when it classifies nothing.

    Two reductions. A ``non-`` prefix negates a partition rather than naming a
    second one, so ``non-threshold`` and ``threshold`` are one finding and not
    two. A bare past participle (``the edited value``) points back at something
    the claim already named, so it partitions nothing; a hyphenated compound
    (``hand-changed keys``) names a class and does.
    """
    term = _singular(term.strip("-"))
    if term.startswith("non-"):
        term = term[4:]
    if not term:
        return ""
    if "-" not in term and term.endswith("ed"):
        return ""
    return term


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


@dataclass
class Variable:
    """One row of the variable table."""

    name: str
    extension: str
    owner_prefix: str
    owner_gloss: str
    line_no: int
    owner_source: str = ""

    @property
    def declared_keys(self) -> set[str]:
        """Every literal key this row puts under one owner.

        The name itself plus every key named in the extension, so a table
        saying ``position`` covers ``the x and y keys under position`` owns
        all three spellings a criterion might use.
        """
        keys = {_norm(self.name)}
        for span in _CODE_SPAN.findall(self.extension):
            token = _norm(span)
            if _KEY_LIKE.match(token):
                keys.add(token)
        return keys


@dataclass
class OwnershipReport:
    """What was checked about ownership, and how much of it ran.

    Three states, not two. No table at all is one. A table whose owners are
    named in prose is a second: it declares ownership honestly and supplies no
    handle a checker can join a criterion to, so the per-criterion clauses
    cannot run against it. A table carrying group tags is the third, and only
    there does the full set run.
    """

    table_found: bool = False
    table_line_no: int = 0
    variables: list[Variable] = field(default_factory=list)
    criteria_examined: int = 0
    criteria_with_group: int = 0
    boundary_terms: list[str] = field(default_factory=list)

    @property
    def joinable(self) -> bool:
        """Whether any row names its owner by group tag rather than in prose."""
        return any(v.owner_prefix for v in self.variables)

    @property
    def ran(self) -> bool:
        return self.table_found and self.joinable


# ---------------------------------------------------------------------------
# Parsing the variable table
# ---------------------------------------------------------------------------


def find_variable_table(tables) -> tuple[object | None, dict[str, int]]:
    """The first table whose header carries Variable, Extension and Owner.

    Returns the table and a map from column name to index, so the columns may
    appear in any order and extra columns are ignored rather than misread.
    """
    for table in tables:
        headers = [_norm(cell) for cell in table.header]
        columns = {}
        for wanted in _VARIABLE_HEADERS:
            for index, header in enumerate(headers):
                if header == wanted or header.startswith(wanted + " "):
                    columns[wanted] = index
                    break
        if len(columns) == len(_VARIABLE_HEADERS):
            return table, columns
    return None, {}


def _split_owner(cell: str) -> tuple[str, str]:
    """(group prefix, gloss) from an owner cell such as ``E`` (the exit-write criteria).

    The prefix is what makes the join mechanical: ADR 0226 gives every criterion
    a leading ID, so a group is the criteria sharing a prefix. The gloss is for
    the reader, and a criterion may cite either.
    """
    gloss = ""
    match = re.search(r"\(([^)]*)\)", cell)
    if match:
        gloss = match.group(1).strip()
        cell = cell[: match.start()] + cell[match.end() :]
    spans = _CODE_SPAN.findall(cell)
    candidate = spans[0].strip() if spans else cell.strip()
    prefix = candidate if _GROUP_TAG.match(candidate) else ""
    return prefix, gloss


def parse_variable_table(table, columns: dict[str, int]) -> list[Variable]:
    rows = []
    for offset, row in enumerate(table.rows):
        if max(columns.values()) >= len(row):
            rows.append(
                Variable("", "", "", "", table.line_no + 2 + offset)
            )
            continue
        name = row[columns["variable"]].strip()
        extension = row[columns["extension"]].strip()
        owner_cell = row[columns["owner"]].strip()
        prefix, gloss = _split_owner(owner_cell)
        rows.append(
            Variable(
                name=name,
                extension=extension,
                owner_prefix=prefix,
                owner_gloss=gloss or _norm(owner_cell),
                line_no=table.line_no + 2 + offset,
                owner_source=owner_cell,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def _named_owner_groups(cell: str) -> int:
    """How many distinct criteria groups one owner cell names.

    Two signals, both decidable without reading the prose. Criterion IDs give
    their groups away by prefix, so "P1-P4, S1-S8" names two. A semicolon in an
    owner cell separates owners; commas do not, because a single group's gloss
    routinely carries one.
    """
    prefixes = {
        match.group(1)
        for match in re.finditer(r"\b([A-Z][A-Za-z]*)[0-9]+\b", cell)
    }
    by_id = len(prefixes)
    by_list = cell.count(";") + 1
    return max(by_id, by_list, 1)


def check_table_form(report, own: OwnershipReport, violation_cls) -> None:
    """Clause 1: named, mechanically extended, exactly one owner, no repeats."""
    where = f"variable table (line {own.table_line_no})"
    seen: dict[str, int] = {}

    for variable in own.variables:
        row_where = f"{where} row {variable.line_no}"

        if not variable.name:
            report.violations.append(
                violation_cls(
                    kind="ownership-table",
                    where=row_where,
                    detail="the row names no variable",
                )
            )
            continue

        key = _norm(variable.name)

        if not variable.extension:
            report.violations.append(
                violation_cls(
                    kind="ownership-table",
                    where=row_where,
                    detail=(
                        f"variable {variable.name} has no extension, so which "
                        f"keys it covers is undefined"
                    ),
                )
            )
        elif own.joinable and not any(
            _KEY_LIKE.match(_norm(span))
            for span in _CODE_SPAN.findall(variable.extension)
        ) and not _KEY_LIKE.match(key):
            report.violations.append(
                violation_cls(
                    kind="ownership-table",
                    where=row_where,
                    detail=(
                        f"the extension of {variable.name} names no literal key, "
                        f"so it is not a mechanical definition: "
                        f"{variable.extension!r}"
                    ),
                )
            )

        owners = _named_owner_groups(variable.owner_source)
        if owners > 1:
            report.violations.append(
                violation_cls(
                    kind="ownership-table",
                    where=row_where,
                    detail=(
                        f"variable {variable.name} names {owners} owner groups. "
                        f"ADR 0228 clause 1 permits one, because two owners for "
                        f"one variable is the defect the discipline removes: "
                        f"{variable.owner_source!r}"
                    ),
                )
            )

        if key in seen:
            report.violations.append(
                violation_cls(
                    kind="ownership-table",
                    where=row_where,
                    detail=(
                        f"variable {variable.name} is declared twice (also at row "
                        f"{seen[key]}); ADR 0228 clause 1 permits one owner per "
                        f"variable"
                    ),
                )
            )
        else:
            seen[key] = variable.line_no


def _criterion_keys(text: str) -> set[str]:
    """Every literal config key a criterion names, read from its code spans."""
    keys = set()
    for span in _CODE_SPAN.findall(text):
        token = _norm(span)
        if _KEY_LIKE.match(token):
            keys.add(token)
    return keys


def _cites(text: str, variable: Variable) -> bool:
    """Whether a criterion points at the owner instead of stating a value."""
    normalized = _norm(text)
    if variable.owner_gloss and _norm(variable.owner_gloss) in normalized:
        return True
    if variable.owner_prefix:
        return bool(
            re.search(rf"\b{re.escape(variable.owner_prefix)}[0-9]*\b", text)
        )
    return False


def check_criteria(report, own: OwnershipReport, criteria, violation_cls) -> None:
    """Clauses 1 and 2, per criterion: undeclared keys, and non-owner claims."""
    owner_of: dict[str, Variable] = {}
    for variable in own.variables:
        for key in variable.declared_keys:
            owner_of.setdefault(key, variable)

    for index, text in enumerate(criteria, 1):
        match = _LEADING_ID.match(text)
        group = match.group(1) if match else ""
        label = match.group(0).strip() if match else f"criterion {index}"
        if group:
            own.criteria_with_group += 1
        where = f"acceptance criterion {label}"

        for key in sorted(_criterion_keys(text)):
            variable = owner_of.get(key)

            if variable is None:
                report.violations.append(
                    violation_cls(
                        kind="ownership-undeclared",
                        where=where,
                        detail=(
                            f"asserts `{key}`, which the variable table does not "
                            f"declare. Its extension and its owner are undefined"
                        ),
                    )
                )
                continue

            if not variable.owner_prefix:
                continue  # already reported as a malformed row

            if group == variable.owner_prefix:
                continue

            if _cites(text, variable):
                continue

            owner_name = variable.owner_gloss or variable.owner_prefix
            in_group = f"in group {group}" if group else "with no group ID"
            report.violations.append(
                violation_cls(
                    kind="ownership-non-owner",
                    where=where,
                    detail=(
                        f"states the fate of `{key}`, which is owned by "
                        f"{variable.owner_prefix} ({owner_name}). This criterion "
                        f"is {in_group}. A non-owner may cite the owner and may "
                        f"not state a value"
                    ),
                )
            )


#: A line declaring what a partitioning term covers. boostgauge #7's retrofit
#: invented this form on its own ("Boundary term: **threshold values** are
#: exactly the keys under the `thresholds` object"), which is the evidence that
#: it is the natural place to put a membership test that is not itself a
#: variable. Terms such as "hand-changed" belong here: they partition the keys
#: without being one, and #290 turned on nobody having written the test down.
_BOUNDARY_DECLARATION = re.compile(
    r"^\s*(?:[-*+]\s+)?\**boundary\s+terms?\**\s*[:.]", re.IGNORECASE
)


def declared_boundary_terms(body: str) -> set[str]:
    """Terms given a membership test by a Boundary term line."""
    terms: set[str] = set()
    for line in body.splitlines():
        if not _BOUNDARY_DECLARATION.match(line):
            continue
        for span in re.findall(r"\*\*([^*]+)\*\*", line) + _CODE_SPAN.findall(line):
            for word in re.findall(r"[a-z][a-z_-]{2,}", span.casefold()):
                terms.add(_singular(word))
    return terms


def check_boundary_terms(
    report, own: OwnershipReport, criteria, violation_cls, extra: set[str] | None = None
) -> None:
    """Clause 4: a term that partitions variables owes a membership test."""
    declared: set[str] = set(extra or ())
    for variable in own.variables:
        for key in variable.declared_keys:
            declared.add(_singular(key))
            for part in key.split("."):
                declared.add(_singular(part))
        for word in re.findall(r"[a-z_]{3,}", _norm(variable.extension)):
            declared.add(_singular(word))

    nouns = "|".join(_CLASSIFIED_NOUNS)
    classifier = re.compile(rf"\b([a-z][a-z_-]{{2,}})\s+(?:{nouns})\b")

    found: dict[str, str] = {}
    for index, text in enumerate(criteria, 1):
        match = _LEADING_ID.match(text)
        label = match.group(0).strip() if match else f"criterion {index}"
        plain = _norm(text)
        terms = set(_NON_PREFIXED.findall(plain))
        terms |= set(classifier.findall(plain))
        for term in terms:
            term = _partition_term(term)
            if not term or term in declared or term in _CLASSIFIER_STOPWORDS:
                continue
            found.setdefault(term, label)

    for term, label in sorted(found.items()):
        own.boundary_terms.append(term)
        report.violations.append(
            violation_cls(
                kind="ownership-boundary",
                where=f"acceptance criterion {label}",
                detail=(
                    f"partitions variables by {term!r}, and the variable table "
                    f"gives it no membership test. Which keys are {term} keys "
                    f"cannot be decided, so neither can their owner"
                ),
            )
        )


def _unscoped_universals(plain: str) -> list[str]:
    """Universals in this claim that carry no scope, in order of appearance.

    An exception marker anywhere in the claim scopes every universal in it. A
    condition marker scopes only the universals that come after it.
    """
    if any(marker in plain for marker in _EXCEPTION_MARKERS):
        return []

    conditions = [
        match.start()
        for marker in _CONDITION_MARKERS
        for match in re.finditer(re.escape(marker), plain)
    ]
    earliest = min(conditions) if conditions else None

    unscoped = []
    for word in _UNIVERSALS:
        for match in re.finditer(rf"\b{re.escape(word)}\b", plain):
            if earliest is not None and earliest < match.start():
                continue
            unscoped.append(word)
            break
    return unscoped


def check_universals(report, own: OwnershipReport, criteria, violation_cls) -> None:
    """Clause 3: a blanket carries its scope, or cites its exception."""
    for index, text in enumerate(criteria, 1):
        match = _LEADING_ID.match(text)
        label = match.group(0).strip() if match else f"criterion {index}"

        hits = _unscoped_universals(_norm(text))
        if not hits:
            continue

        report.violations.append(
            violation_cls(
                kind="ownership-universal",
                where=f"acceptance criterion {label}",
                detail=(
                    f"claims {', '.join(repr(h) for h in hits)} with no scope in "
                    f"the same claim. A universal carries the conditions it holds "
                    f"fixed, or cites the exception that limits it"
                ),
            )
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def check_ownership(tables, criteria, report, violation_cls, body="") -> OwnershipReport:
    """Run every ADR 0228 check. Absence of a table is disclosed, not passed."""
    own = OwnershipReport()
    own.criteria_examined = len(criteria)

    table, columns = find_variable_table(tables)
    if table is None:
        return own

    own.table_found = True
    own.table_line_no = table.line_no
    own.variables = parse_variable_table(table, columns)

    check_table_form(report, own, violation_cls)
    check_universals(report, own, criteria, violation_cls)

    if not own.joinable:
        # The table declares ownership in prose. Clause 2 asks which criteria
        # are outside a variable's owner group, and prose supplies no answer,
        # so the per-criterion clauses would report every criterion as a
        # violation. That is a false alarm about the table's form, not a
        # finding about its ownership, and a check that floods is one people
        # stop reading. The state is disclosed instead.
        return own

    check_criteria(report, own, criteria, violation_cls)
    check_boundary_terms(
        report, own, criteria, violation_cls, declared_boundary_terms(body)
    )
    return own


def render_ownership(own: OwnershipReport, violations) -> list[str]:
    """The ownership section of the operator-facing report."""
    out = ["Variable ownership (ADR 0228)"]
    failures = sum(1 for v in violations if v.kind.startswith("ownership-"))

    if not own.table_found:
        out += [
            "  Ownership was not checked: no variable table exists.",
            f"  0 variables examined out of 0, and 0 of {own.criteria_examined}",
            "  acceptance criteria were checked for ownership. That is an honest",
            "  vacuous result, not a pass.",
        ]
        return out

    if not own.joinable:
        out += [
            f"  {len(own.variables)} variable(s) declared at line "
            f"{own.table_line_no}, every owner named in prose.",
            "  Ownership was NOT checked per criterion: no owner cell carries a",
            "  group tag, so no criterion can be joined to an owner. Clauses 2",
            f"  and 4 did not run against any of the {own.criteria_examined}",
            "  acceptance criteria. That is a vacuous result, not a pass.",
            "  To make it checkable, give each owner cell the ID prefix of its",
            "  criteria group, as in `E` (the exit-write criteria).",
            f"  {failures} finding(s) below are the ones this form can support.",
        ]
        return out

    out.append(
        f"  {len(own.variables)} variable(s) declared; "
        f"{own.criteria_examined} acceptance criteria examined, "
        f"{own.criteria_with_group} carrying a group ID."
    )
    for variable in own.variables:
        owner = variable.owner_prefix or "(no group tag)"
        out.append(f"    `{variable.name}` -> {owner}")
    out.append(f"  {failures} ownership violation(s).")
    return out
