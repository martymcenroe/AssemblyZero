"""Elements named in an issue's scope prose must reach the table (#2645).

Every gate this campaign built audits rows that EXIST. Row-absence is invisible
to all of them, and the gap cost boostgauge #331 its dominant visual element:
the title and the opening scope both name "bezel", nineteen ruled conflicts
hardened every row that existed, and nothing ever asked whether a row was
missing. The factory then carried a nine-row table through fourteen gates with
perfect fidelity and faithfully built an incomplete face (boostgauge #375).

The one place the full element list exists is the issue's own prose, inches
above the table that dropped one. This module reads it.

## The acceptance case is a near-miss, not a bare absence

The obvious implementation fails its own acceptance, and it took running four
matchers over the preserved body to see why. #331's table DOES carry a row
whose Element cell begins with the word bezel -- `S9 | Bezel seat` -- which
asserts a shadow on the transition annulus at 1.01 R and binds nothing about
the ring. Measured over the enumeration extracted from #331's title and scope
sentence, against what a human reader gives:

    matcher        errors
    substring      bezel FALSE PASS, tick marks false alarm
    token-subset   bezel FALSE PASS, tick marks false alarm
    exact          dial, ticks, tick marks false alarms
    head-noun      dial, tick marks false alarms

No rule does better, because the difference is not in the names:

    'Dial face'    modifier=dial   head=face   -> COVERS 'dial'
    'Bezel seat'   modifier=bezel  head=seat   -> does NOT cover 'bezel'

Identical shape, opposite answers. A name-matcher here is a proxy-heuristic in
#2540's exact sense -- a correlate, satisfiable without satisfying the intent
-- and its failure direction is a FALSE PASS. The two matchers that read as
most helpful are precisely the two that ship #331 unchanged.

## So the coverage judgement is not mechanical, and this module does not make it

Normalized-EXACT matching, and everything else needs a disposition written
down. Exact is the least accurate of the four by raw error count; it is the
only one whose errors all point the safe way. Its misses are false alarms an
author discharges once with a declared alias, and every alias is a falsifiable
claim a reader -- and the sibling contract-fidelity review -- can audit.

Three explicit sources dispose of an element. Nothing else does, and nothing is
guessed:

1. a criteria-table row whose Element cell equals the term (normalized);
2. a declared alias, ``<!-- scope-alias: tick marks -> S3, S4 -->``;
3. a declared exclusion in scope prose -- #331's ``NO pivot cap -- ... belongs
   to #332`` is the existing pattern and parses today.

That is exact bookkeeping over three named sets, which is the
`manifest_traceability` shape: a fact-verifier, not a proxy. What this module
can no longer do is decide that S9 covers "bezel". What it does is make
somebody write that claim down.

## It reads criteria tables, not ADR 0226 decision tables

`check_form` examines no table on #331's preserved body. `is_decision_table`
requires yes/no condition columns per ADR 0226 section 3.2; #331's table is
`ID | Element | Binding value | Assertion method`, which `is_criteria_table`
recognises and that predicate does not. A check keyed on the wrong predicate
would examine zero tables on the exact issue it was built for and report clean
-- a vacuous pass wearing a gate's clothes. This module keys on
`is_criteria_table`, the same predicate `table_injection` and the manifest
compiler already share, and adds no third notion of what a table is.

(When this module landed, `check_form` rendered that as `Decision tables: 0
found` under a bare `RESULT: PASS` -- the reporting defect filed as #2650 and
since fixed. The predicate split it describes is unchanged; only the wording
this paragraph used to quote is.)

## What it deliberately does not read

A draw-order list quoted IN the issue body is read like any other scope
enumeration. One that lives only in the cited design contract is not: loading
the contract belongs to the sibling contract-fidelity review (#2646), and two
loaders of one document is the #1698 class.

Report-only, at launcher preflight, beside the form check. No issue in the
fleet carries an alias yet, so a refusal here would fire on the ordinary case
-- the #2227 ruling's own reason for report-only, and #2387's. It prints on
every issue, pass or fail, and discloses a vacuous result separately from a
clean one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from assemblyzero.workflows.implementation_spec.assertion_manifest import (
    is_criteria_table,
)
from assemblyzero.workflows.requirements.form_check import (
    Violation,
    parse_tables,
)

LABEL = "Scope coverage (#2645)"

#: The alias an author writes to discharge a name this module cannot match --
#: `tick marks` against rows `S3` and `S4`. An HTML comment so it is invisible
#: in every markdown viewer and machine-findable, the same arrangement
#: `table_injection` uses for its machine-owned fence.
_ALIAS_RE = re.compile(
    r"<!--\s*scope-alias:\s*(?P<term>[^>\n]+?)\s*(?:->|-->|→)\s*"
    r"(?P<rows>[^>\n]*?)\s*-->",
    re.IGNORECASE,
)

#: An element the issue says it is NOT doing. #331 writes both forms in its
#: lede: `No needles and NO pivot cap -- the cap ... belongs to #332`.
#:
#: A reason is REQUIRED. "no gradient" with nothing after it is a binding
#: value's phrasing, not a scope exclusion, and #331's own S1 cell says exactly
#: that ("NO gradient, glass sweep, or reflection"). Requiring the reason is
#: what keeps a table cell from silently excusing an element -- and the
#: exclusion scan is confined to scope prose for the same reason.
_EXCLUSION_RE = re.compile(
    r"\bno\s+(?P<term>[a-z][a-z ]{1,28}?)\s*"
    r"(?=--|—|-\s|,|\.|;|\)|$|\band\b|\bbelongs\b|\bis\b|\bare\b)",
    re.IGNORECASE,
)

#: The reason that makes an exclusion a declared one rather than a phrasing.
_EXCLUSION_REASON = re.compile(
    r"belongs to|out of scope|excluded|#\d+|\bis\s+#|\bstop\b|scope:",
    re.IGNORECASE,
)

#: A `## Boundary terms` style section also declares exclusions, as bolded
#: lead-ins: `- **Needles** -- main needle is the sibling needle issue's`.
_BOUNDARY_TERM_RE = re.compile(r"^\s*[-*]\s*\*\*(?P<term>[^*]+)\*\*", re.MULTILINE)

_BOUNDARY_HEADINGS = ("boundary terms", "out of scope", "non-goals", "boundaries")

#: A markdown heading, used to find where the scope prose ends.
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)

#: The smallest comma list this module will read as an enumeration.
#:
#: #331's title carries two: the seven elements, and the two-item participle
#: tail `baked once, cached` that describes behaviour rather than naming parts.
#: Taking the longest separates them on the one real title available, and the
#: floor is what stops a two-item tail from reading as an enumeration when it
#: is the only list there. A quiet miss here is not the last line of defence:
#: the scope sentence is the richer source, and the contract-fidelity review
#: reaches the same elements from the contract side.
_MIN_ENUMERATION = 3


def _norm(text: str) -> str:
    """Lowercase, punctuation to spaces, whitespace collapsed.

    Backticks, hyphens and case are formatting; `Chrome housing` and
    `chrome housing` are the same element name and must compare equal.
    """
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


@dataclass(frozen=True)
class ScopeElement:
    """One element the issue's prose says is in scope.

    `source` is carried so a finding can say WHERE the claim was made -- the
    title survived nineteen ruled conflicts on #331 and is the strongest
    witness in the document. `also_named` carries the coarser wording when the
    same element was named twice at different grains.
    """

    term: str
    source: str
    also_named: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return _norm(self.term)


def _stems(text: str) -> frozenset[str]:
    """Token stems, for reconciling two PROSE names of one element.

    Used only by `_reconcile_grains`, never against a table row -- see its
    docstring for why that boundary is load-bearing.
    """
    return frozenset(
        tok[:-1] if tok.endswith("s") and len(tok) > 3 else tok
        for tok in _norm(text).split()
    )


def _reconcile_grains(elements: list[ScopeElement]) -> list[ScopeElement]:
    """Collapse a prose name that a more specific prose name already contains.

    #331 names the same two elements twice at different grains: the title says
    `dial` and `ticks`, the scope sentence says `dial face` and `tick marks`.
    Those are one element each, stated once coarsely and once precisely, and
    reporting both would put two findings on the board for one thing -- the
    #2539 disease.

    **This reconciles PROSE against PROSE and never against a table row**, and
    that boundary is the whole safety argument. Two prose names nesting means
    the author refined their own statement. A prose name nesting inside a ROW
    name means nothing of the kind: `bezel` sits inside `Bezel seat`, and S9
    binds a shadow annulus rather than the ring (boostgauge #375). Letting rows
    into this rule would reintroduce the token-subset matcher measured in the
    module docstring as a FALSE PASS on this module's own acceptance case.

    The more specific name wins, because it is the author's own refinement.
    """
    kept: list[ScopeElement] = []
    for element in elements:
        mine = _stems(element.term)
        broader = [
            other for other in elements
            if other is not element and mine < _stems(other.term)
        ]
        if broader:
            continue  # a more specific prose name carries this one
        coarser = tuple(
            other.term for other in elements
            if other is not element and _stems(other.term) < mine
        )
        kept.append(
            ScopeElement(
                term=element.term,
                source=element.source,
                also_named=coarser,
            )
            if coarser
            else element
        )
    return kept


@dataclass
class ScopeReport:
    """What was judged about one issue's scope coverage."""

    elements: list[ScopeElement] = field(default_factory=list)
    table_found: bool = False
    rows_examined: int = 0
    matched: dict[str, str] = field(default_factory=dict)
    aliased: dict[str, str] = field(default_factory=dict)
    excluded: dict[str, str] = field(default_factory=dict)
    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    @property
    def vacuous(self) -> bool:
        """Nothing was judged, which is NOT the same as nothing was wrong."""
        return not self.elements or not self.table_found

    def disclosure(self) -> str:
        """One line stating what the check actually did (#2227).

        A check with nothing to check must say so. Reporting "no findings" for
        a document it never judged is how a gate reads as thorough validation
        while verifying nothing.
        """
        if not self.elements:
            return (
                "scope coverage: NOT CHECKED — no scope enumeration found in "
                "the title or the opening scope prose, so no element was "
                "looked for."
            )
        if not self.table_found:
            return (
                f"scope coverage: NOT CHECKED — {len(self.elements)} element(s) "
                f"named in scope prose, but the issue carries no criteria "
                f"table (ID + binding value) to carry them."
            )
        return (
            f"scope coverage: {len(self.elements)} element(s) named in scope "
            f"prose against {self.rows_examined} table row(s) — "
            f"{len(self.matched)} matched a row, {len(self.aliased)} declared "
            f"an alias, {len(self.excluded)} declared an exclusion, "
            f"{len(self.violations)} undisposed."
        )


# ---------------------------------------------------------------------------
# Reading the document
# ---------------------------------------------------------------------------


def scope_prose(body: str) -> str:
    """The issue's lede: everything before its first markdown heading.

    The scope claim and the exclusions both live here on #331, and confining
    the scan to it is what keeps a binding value's `NO gradient` from reading
    as a scope exclusion.
    """
    match = _HEADING.search(body or "")
    return (body or "")[: match.start()] if match else (body or "")


def _comma_lists(text: str) -> list[list[str]]:
    """Every comma list in one span, longest first.

    Items split on commas and on a trailing ``and``. Empty items and pure
    citations are dropped rather than becoming elements nothing can match.
    """
    lists: list[list[str]] = []
    for chunk in re.split(r"—|--|–", text):
        parts = [
            p.strip().strip(".").strip()
            for p in re.split(r",|\band\b", chunk)
        ]
        items = [p for p in parts if _norm(p)]
        if len(items) >= _MIN_ENUMERATION:
            lists.append(items)
    return sorted(lists, key=len, reverse=True)


def title_elements(title: str) -> list[ScopeElement]:
    """The enumeration in the title, after any conventional-commit prefix.

    #331's title after `feat:` is
    ``static face renderer — bezel, ..., screws — baked once, cached``: two
    comma lists, and the longer is the element list.
    """
    if not title:
        return []
    text = title.split(":", 1)[1] if ":" in title.split("—")[0] else title
    lists = _comma_lists(text)
    if not lists:
        return []
    return [ScopeElement(term=item, source="title") for item in lists[0]]


def scope_sentence_elements(body: str) -> list[ScopeElement]:
    """Colon-introduced enumerations in the issue's lede.

    #331: ``this is the baked half of the renderer: bezel, chrome housing,
    dial face, redline band, tick marks, numerals, wordmark, and screws.``

    A span ends at the first period FOLLOWED BY WHITESPACE, so `PIL.Image` and
    `docs/design/0002-...md` never split a list, while the sentence after the
    enumeration is never swallowed into it.
    """
    found: list[ScopeElement] = []
    prose = scope_prose(body)
    for match in re.finditer(r":\s*", prose):
        tail = prose[match.end():]
        stop = re.search(r"\.(?=\s|$)", tail)
        span = tail[: stop.start()] if stop else tail
        lists = _comma_lists(span)
        if lists:
            found.extend(
                ScopeElement(term=item, source="scope prose")
                for item in lists[0]
            )
    return found


def declared_aliases(body: str) -> dict[str, str]:
    """Author-declared name -> the rows it is claimed to be carried by."""
    return {
        _norm(m.group("term")): m.group("rows").strip()
        for m in _ALIAS_RE.finditer(body or "")
        if _norm(m.group("term"))
    }


def declared_exclusions(body: str) -> dict[str, str]:
    """Elements the issue's scope prose says it is NOT doing, with the reason.

    Two forms, both taken from #331: a ``no <term>`` clause carrying a reason,
    and a bolded lead-in under a boundary-terms heading.
    """
    found: dict[str, str] = {}
    prose = scope_prose(body)

    for match in _EXCLUSION_RE.finditer(prose):
        term = _norm(match.group("term"))
        if not term:
            continue
        # The reason has to be nearby, in the same sentence-ish span.
        tail = prose[match.end(): match.end() + 240]
        if _EXCLUSION_REASON.search(tail):
            found[term] = tail.strip().split("\n")[0][:120]

    for heading in _find_sections(body or "", _BOUNDARY_HEADINGS):
        for match in _BOUNDARY_TERM_RE.finditer(heading):
            term = _norm(match.group("term"))
            if term:
                found.setdefault(term, "declared under a boundary-terms section")

    return found


def _find_sections(body: str, headings: tuple[str, ...]) -> list[str]:
    """The text under any heading whose name is one of ``headings``."""
    sections: list[str] = []
    matches = list(_HEADING.finditer(body))
    for i, match in enumerate(matches):
        if _norm(match.group(2)) not in headings:
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections.append(body[match.end(): end])
    return sections


def element_rows(body: str) -> dict[str, str]:
    """Normalized element name -> row ID, from every criteria table.

    The Element column is the second cell of a criteria table's row by the
    ruled #332 shape (`ID | Element | Binding value | Assertion method`). A
    table without one contributes no names rather than contributing wrong ones.
    """
    rows: dict[str, str] = {}
    for table in parse_tables(body or ""):
        if not is_criteria_table(table):
            continue
        for row in table.rows:
            if len(row) < 2:
                continue
            name = _norm(row[1])
            if name:
                rows.setdefault(name, row[0].strip())
    return rows


def criteria_row_count(body: str) -> int:
    return sum(
        len(t.rows) for t in parse_tables(body or "") if is_criteria_table(t)
    )


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------


def check_scope_coverage(title: str, body: str) -> ScopeReport:
    """Every element named in scope prose must reach a row, an alias, or an
    exclusion (#2645).

    Normalized-exact matching only. The module never decides that a row whose
    name merely CONTAINS the term carries it -- that judgement is what shipped
    boostgauge #375, and the measurement behind the ruling is in the module
    docstring.
    """
    report = ScopeReport()

    seen: set[str] = set()
    named: list[ScopeElement] = []
    for element in title_elements(title) + scope_sentence_elements(body):
        if element.key in seen:
            continue
        seen.add(element.key)
        named.append(element)
    report.elements = _reconcile_grains(named)

    rows = element_rows(body)
    report.table_found = bool(rows)
    report.rows_examined = criteria_row_count(body)

    if not report.elements or not report.table_found:
        return report

    aliases = declared_aliases(body)
    exclusions = declared_exclusions(body)

    for element in report.elements:
        key = element.key
        if key in rows:
            report.matched[key] = rows[key]
        elif key in aliases:
            report.aliased[key] = aliases[key]
        elif key in exclusions:
            report.excluded[key] = exclusions[key]
        else:
            also = (
                f" (also named {', '.join(repr(t) for t in element.also_named)})"
                if element.also_named
                else ""
            )
            report.violations.append(
                Violation(
                    kind="scope-uncovered",
                    where=element.term + also,
                    detail=(
                        f"named in the {element.source} but no table row is "
                        f"called {element.term!r}, no alias declares which row "
                        f"carries it, and no exclusion declares it out of "
                        f"scope. Add a row, or declare "
                        f"`<!-- scope-alias: {element.term} -> <row ids> -->` "
                        f"if an existing row already binds it, or say why it "
                        f"is excluded. Matching is exact by design: a row that "
                        f"merely mentions {element.term!r} is not evidence it "
                        f"binds it (boostgauge #375)."
                    ),
                )
            )

    return report
