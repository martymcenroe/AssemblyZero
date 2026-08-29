"""The contract-to-issue compression is the pipeline's only ungated derivation
(#2646).

Every machine derivation is gated now. issue->LLD has injection, conservation
and structure; LLD->spec has injection, the manifest, traceability and
adversarial review; spec->code has red/green and honest coverage. The step
where a rich design contract is compressed into an issue's decision table is
human-and-chat work, and it has no gate at all. boostgauge #331 shipped all
three of its failure shapes in one feature:

* **a binding with no row** -- contract §Bezel binds polished chrome, a
  12-15% width, and two specular hot spots; the table carried only the seat
  shadow, so the ring was never drawn (boostgauge #375);
* **an assertion weaker than its binding** -- S7's binding cites #328's stops
  table and the hard-horizon step law; its assertion tests existence of
  contrast, which any ramp satisfies. The face shipped the contract's own
  named failure case fourteen days after the contract named it (#376);
* **a presupposition never bound** -- anti-aliasing is engineered around three
  times and bound nowhere, so the face shipped hard-edged (#377).

Prose law that never becomes assertion values is invisible to every downstream
gate, and the gates' own fidelity makes it worse: a faithful pipeline ships the
compression's gaps at production quality.

## The contract's identity is already declared. It is just never opened

`visual_gate/config.py` carries `"contract": "docs/design/0002-...md"` per
repo, and that path reaches exactly one consumer -- a sentence in `gate.py`
that interpolates it into a message. **The path is declared, carried, and
never read.** So this module resolves the contract through `load_gate_config`
rather than inventing a second answer to "which document binds this repo"; a
second answer is the #1698 class, and this one would disagree with the gate
that already renders against that contract.

`sync_binding_docs_to_arc` (#2205) already carries binding docs onto the arc,
so the file is on disk at ratification. Nothing is fetched.

## Two directions of matching, and they take opposite defaults

#2645 measured that no name-level matcher can decide whether a row COVERS an
element, and ruled exact matching because its errors point the safe way. That
ruling governs verdicts. It does not govern **which evidence to load**, where
the safe direction is the opposite one: under-selecting a section hides
evidence from the reviewer, while over-selecting costs context and nothing
else. But generosity has a floor, and the first cut fell through it: selecting
on any ruling number appearing anywhere in the issue body pulled in 21 of the
contract's 25 sections on #331, §References and §Out of scope included. The
rules are in `sections_in_play`, and the exclusion subtraction is what keeps a
check auditing #331 from raising findings about needles.

## What is mechanical, measured rather than assumed

Three shapes, and the measurements put them in three different places. Every
number below comes from running the detectors over the real contract and the
real #331 body, not from reasoning about them.

**Shape 3 is a fact-verifier.** The tolerance-justification pattern fires twice
across the whole 301-line contract, and both hits are `anti-aliasing`:

    64: ...no two entries are closer than 85 ... so anti-aliasing cannot flip
        a classification
   129: Sample away from edges (at least 2 px inside a feature) so
        anti-aliasing does not decide the result

Zero false alarms. A term used to justify a tolerance and bound in no table --
neither the contract's tables nor the issue's -- is a fact about two documents,
so it is reported as a finding.

**Shape 2 has an exact precursor**, and it is the whole signal. A binding cell
that CITES a contract table by reference while its assertion cell carries none
of that table's values is a set difference. It names S7 and nothing else, and
it quotes the law the cited section states -- "MUST remain a step, never a
ramp" -- so the finding arrives with its own evidence.

**Shape 1 does not close mechanically, and the attempt is instructive.** Every
rule tried either missed the real findings or fired on covered ones. Keyed on
the sub-binding's name against all rows, `§Bezel / Width` disappeared because
S3 and S4 both say "width" about ticks -- two thirds of boostgauge #375
silently marked covered. Keyed on the literal form of a value,
`§Tick marks / Major marks` ("10% of dial radius") read as uncovered though S3
binds "length 0.10 R", the same quantity. Attributing a value to an element is
the judgement #2645 measured as unmechanizable on names.

So shape 1 splits. Whether S9 *discharges* §Bezel is a judgement and goes to
the reviewer as `binding_ledger` -- each section's sub-bindings beside the rows
that reference that section, scoped, which is what makes it true. Whether ANY
row reaches a scoped section at all is a fact, and that is
`signal_sections_without_rows`. On #331 the ledger shows §Bezel's Material
rendering, Width and Highlights with no row naming them, against S9 for
Bezel-to-dial transition: exactly boostgauge #375's list.

The review half then adjudicates with the contract in hand -- the thing no
current stage does. Report-only, for the reasons #2227 and #2387 give, and only
for repos that declare a binding contract for the issue being rolled; every
other repo pays nothing and sees one line saying so.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from assemblyzero.visual_gate.config import gate_applies, load_gate_config
from assemblyzero.workflows.implementation_spec.assertion_manifest import (
    is_criteria_table,
)
from assemblyzero.workflows.requirements.form_check import RawTable, parse_tables
from assemblyzero.workflows.requirements.scope_coverage import (
    declared_exclusions,
    scope_sentence_elements,
    title_elements,
)

LABEL = "Contract fidelity (#2646)"

#: A markdown heading and its level.
_HEADING = re.compile(r"^(#{2,6})\s+(?P<name>.+?)\s*$", re.MULTILINE)

#: A bolded lead-in that opens a sub-binding: `- **Width:** Substantial...`.
_SUB_BINDING = re.compile(
    r"^\s*[-*]\s*\*\*(?P<name>[^*]+?)\s*:?\s*\*\*\s*(?P<text>.*)$", re.MULTILINE
)

#: A ruling number, wherever it is cited.
_RULING = re.compile(r"#(?P<n>\d{1,5})\b")

#: An explicit section citation in the issue: `contract §Bezel-to-dial transition`.
_SECTION_CITATION = re.compile(r"§\s*(?P<name>[A-Za-z][A-Za-z0-9 /'-]*)")

#: A tolerance engineered AROUND a property that is never bound (#377's shape).
#: Measured on the real contract: two hits, both `anti-aliasing`, no others.
_PRESUPPOSITION = re.compile(
    r"\bso\s+(?:that\s+)?(?P<term>[a-z][a-z -]{2,30}?)\s+"
    r"(?:cannot|can\s+not|does\s+not|do\s+not|is\s+not|are\s+not|never)\b",
    re.IGNORECASE,
)

#: The same property cited as a named rule that no table defines:
#: `safely interior per the 2-px anti-aliasing rule`.
_NAMED_RULE = re.compile(
    r"\bthe\s+(?:[\w.-]+\s+)?(?P<term>[a-z][a-z -]{2,30}?)\s+rule\b",
    re.IGNORECASE,
)

#: A law the contract states as binding rather than describing.
_MUST_LAW = re.compile(r"\b(?:MUST|NEVER|shall)\b")

#: Provenance, not specification: a ruling reference, an ISO date, or a
#: `(ruling ...)` parenthetical. Stripped BEFORE values are read.
#:
#: Measured, not guessed: without this, `§Face / Color` reported binding
#: "One, `#0A0A0C`, 2026, 08" -- two of those four are the date in "(operator
#: ruling 2026-08-15, #325)", and `§Form factor / Why this combination` was
#: reported as binding "45" because the prose cites #45. A citation is how the
#: contract says where a value came from, never a value the table must carry.
_PROVENANCE = re.compile(
    r"\(\s*(?:operator\s+)?ruling[^)]*\)|\bruling\s+#?\d+|#\d{1,5}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)

#: A literal value: a hex colour, an RGB triple, or a number carrying a unit.
#:
#: A BARE integer is deliberately not a value here. The contract's prose is
#: full of them -- "all five needles", "one word, all caps", scale positions in
#: a sentence -- and every one produced a candidate naming a sub-binding that
#: specifies nothing a row could carry. A number with a unit, a percentage, a
#: radius or a colour is what the contract means by "the tables carry the
#: values"; the rest is prose that happens to contain a digit.
_LITERAL_VALUE = re.compile(
    r"`#[0-9A-Fa-f]{3,8}`|\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)"
    r"|\b\d+(?:\.\d+)?\s*(?:%|px|R\b|×|°|units?\b)"
    r"|\b\d+(?:\.\d+)?\s*[–-]\s*\d+(?:\.\d+)?\s*%",
    re.IGNORECASE,
)

#: Numbers, for the assertion-carries-its-binding's-values set difference.
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def _tokens(text: str) -> set[str]:
    return {
        tok[:-1] if tok.endswith("s") and len(tok) > 3 else tok
        for tok in _norm(text).split()
    }


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubBinding:
    """One bolded lead-in inside a contract section, and what it binds."""

    name: str
    text: str

    @property
    def values(self) -> list[str]:
        return _LITERAL_VALUE.findall(_PROVENANCE.sub(" ", self.text))

    @property
    def carries_a_value(self) -> bool:
        """Adjectives are not a specification -- the contract's own words."""
        return bool(self.values)

    @property
    def delegates_to(self) -> list[str]:
        """Sections this sub-binding hands off to rather than binding itself."""
        return [m.group("name").strip() for m in _SECTION_CITATION.finditer(self.text)]


@dataclass(frozen=True)
class ContractSection:
    """One `##`/`###` section of the binding design doc."""

    name: str
    body: str
    line_no: int
    level: int = 2
    parent: str = ""
    rulings: tuple[str, ...] = ()
    sub_bindings: tuple[SubBinding, ...] = ()
    tables: tuple[RawTable, ...] = ()

    @property
    def laws(self) -> list[str]:
        """Sentences the contract states as binding, quoted for the reviewer."""
        return [
            sentence.strip()
            for sentence in re.split(r"(?<=[.;])\s+", self.body)
            if _MUST_LAW.search(sentence)
        ]

    @property
    def table_values(self) -> set[str]:
        return {
            value
            for table in self.tables
            for row in table.rows
            for cell in row
            for value in _NUMBER.findall(cell)
        }


def parse_contract(text: str) -> list[ContractSection]:
    """Every section of the contract, with its sub-bindings and tables."""
    sections: list[ContractSection] = []
    matches = list(_HEADING.finditer(text or ""))
    parent = ""
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[match.end(): end]
        name = match.group("name")
        level = len(match.group(1))
        if level <= 2:
            parent = name
        sections.append(
            ContractSection(
                name=name,
                body=body,
                line_no=text[: match.start()].count("\n") + 1,
                level=level,
                parent="" if level <= 2 else parent,
                rulings=tuple(m.group("n") for m in _RULING.finditer(name + body)),
                sub_bindings=tuple(
                    SubBinding(name=m.group("name").strip(), text=m.group("text").strip())
                    for m in _SUB_BINDING.finditer(body)
                ),
                tables=tuple(parse_tables(body)),
            )
        )
    return sections


def resolve_contract(repo_root: Path | str, issue: int) -> Path | None:
    """The contract this repo declares for this issue, or None.

    Read through `load_gate_config` rather than a convention of this module's
    own: the repo already declares which document binds it, and a second
    answer would disagree with the visual gate that renders against the first.
    """
    config = load_gate_config(repo_root)
    if not gate_applies(config, issue) or not config.contract:
        return None
    path = Path(repo_root) / config.contract
    return path if path.is_file() else None


# ---------------------------------------------------------------------------
# Which sections are in play
# ---------------------------------------------------------------------------


#: The `##` section whose subsections carry the contract's values. Every issue
#: derives from it regardless of which elements it scopes -- the contract says
#: so itself: "Every visual acceptance criterion is computed from this section."
_VALUE_PARENT = "numeric render contract"


def _table_of(body: str) -> RawTable | None:
    tables = [t for t in parse_tables(body or "") if is_criteria_table(t)]
    return tables[0] if tables else None


def sections_in_play(
    title: str, body: str, sections: list[ContractSection]
) -> list[ContractSection]:
    """The contract sections this issue's scope puts in play.

    Generous relative to #2645's exact matching, because under-selection hides
    evidence from the reviewer while over-selection only costs context -- but
    generosity has a floor, and the first cut fell through it. Selecting on any
    ruling number appearing anywhere in the issue body pulled in 21 of the
    contract's 25 sections on #331, including §References and §Out of scope,
    and each irrelevant section then contributed its own sub-bindings as
    candidates. A check that raises 24 candidates for 3 real findings is the
    #2539 disease, so:

    1. the value-carrying subsections of §The numeric render contract, always
       -- the contract states that every visual criterion is computed there;
    2. a section whose name tokens overlap a scope element;
    3. an explicit `§Name` citation in the issue;
    4. a ruling number cited **by the decision table's own cells** -- not
       anywhere in the body. A ruling in prose is usually provenance ("ruling
       on the #361 conflict"); one in a binding cell says where that row
       derives from, which is the relationship this check audits.

    Then subtract: a section whose name overlaps a DECLARED EXCLUSION is
    dropped. #331 excludes needles and the pivot cap in its own prose, and
    auditing it against §Main needle would be a finding about work the issue
    said it was not doing.
    """
    elements = title_elements(title) + scope_sentence_elements(body)
    element_tokens = [_tokens(e.term) for e in elements]
    excluded_tokens = [_tokens(term) for term in declared_exclusions(body)]
    cited_sections = {
        _norm(m.group("name")) for m in _SECTION_CITATION.finditer(body or "")
    }
    table = _table_of(body)
    table_rulings = {
        m.group("n")
        for row in (table.rows if table is not None else [])
        for cell in row
        for m in _RULING.finditer(cell)
    }

    chosen: list[ContractSection] = []
    for section in sections:
        name_tokens = _tokens(section.name)
        norm_name = _norm(section.name)

        if any(name_tokens & toks for toks in excluded_tokens):
            continue

        if _VALUE_PARENT in _norm(section.parent) or _VALUE_PARENT in norm_name:
            chosen.append(section)
            continue
        if any(name_tokens & toks for toks in element_tokens):
            chosen.append(section)
            continue
        if any(
            cited == norm_name or cited.startswith(norm_name + " ")
            or norm_name.startswith(cited + " ")
            for cited in cited_sections
        ):
            chosen.append(section)
            continue
        if table_rulings & set(section.rulings):
            chosen.append(section)
    return chosen


# ---------------------------------------------------------------------------
# The three signals
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Signal:
    """One candidate for the reviewer, with the evidence that raised it."""

    shape: str          # binding-no-row | assertion-cannot-falsify | unbound-presupposition
    where: str
    detail: str
    mechanical: bool    # a fact on its own, or a candidate needing judgement


def rows_referencing(section: ContractSection, rows: list[list[str]]) -> list[str]:
    """The row IDs that reference this contract section at all.

    Generous token overlap, because this selects EVIDENCE rather than deciding
    coverage -- §Bezel is referenced by S9 ("Bezel seat"), §Redline arc by S2
    ("Redline band"). Whether S9 *discharges* §Bezel is exactly the judgement
    this module refuses to make.
    """
    wanted = _tokens(section.name) - {"the", "a", "and", "of"}
    found: list[str] = []
    for row in rows:
        if not row:
            continue
        if wanted & _tokens(" ".join(row)):
            found.append(row[0].strip())
    return found


def binding_ledger(
    sections: list[ContractSection], rows: list[list[str]]
) -> list[tuple[str, str, list[str]]]:
    """(section, sub-binding, row IDs that name it) for every in-play section.

    Evidence for the reviewer, never a verdict -- shape 1 does not close
    mechanically and the measurements say so. Every rule tried either missed
    the real findings or fired on covered ones: keyed on a value's literal
    form, §Tick marks / Major marks ("10% of dial radius") reads as uncovered
    though S3 binds "length 0.10 R", which is the same quantity; keyed on the
    sub-binding's name against ALL rows, §Bezel / Width vanished because S3 and
    S4 both say "width" about ticks. Attributing a value to an element is the
    judgement #2645 measured as unmechanizable on names.

    **The row text is scoped to the rows that reference the section**, and that
    scoping is what makes the ledger true. Unscoped, §Bezel / Width and
    §Bezel / Highlights -- two thirds of boostgauge #375 -- were both reported
    as named by a row, by ticks and by nothing.
    """
    ledger: list[tuple[str, str, list[str]]] = []
    for section in sections:
        if not section.sub_bindings:
            continue
        referencing = rows_referencing(section, rows)
        scoped = _norm(
            " ".join(
                cell
                for row in rows
                if row and row[0].strip() in referencing
                for cell in row
            )
        )
        for binding in section.sub_bindings:
            name = _norm(binding.name)
            named_by = [
                row_id for row_id in referencing if name and name in scoped
            ]
            ledger.append((section.name, binding.name, named_by))
    return ledger


def signal_sections_without_rows(
    sections: list[ContractSection], rows: list[list[str]]
) -> list[Signal]:
    """A contract section the issue scopes that NO row references (shape 1).

    The hard half of shape 1, and the only half that closes mechanically:
    whether S9 discharges §Bezel is a judgement, but whether ANY row reaches
    §Bezel at all is a fact. The soft half -- which sub-bindings inside a
    referenced section went unbound -- reaches the reviewer as `binding_ledger`
    beside the section's own words.
    """
    signals: list[Signal] = []
    for section in sections:
        if not section.sub_bindings or rows_referencing(section, rows):
            continue
        values = [v for b in section.sub_bindings for v in b.values]
        signals.append(
            Signal(
                shape="section-no-row",
                where=f"§{section.name}",
                detail=(
                    f"this issue's scope puts the section in play and it binds "
                    f"{len(section.sub_bindings)} sub-binding(s)"
                    + (f" carrying {', '.join(values[:5])}" if values else "")
                    + ", and no row of the decision table references it at all."
                ),
                mechanical=True,
            )
        )
    return signals


def signal_assertions_that_cannot_falsify(
    sections: list[ContractSection], table: RawTable | None
) -> list[Signal]:
    """Rows whose binding cites a contract table their assertion never uses.

    The exact precursor to shape 2: a set difference over numbers, no
    judgement. A binding that points at where the values live while the
    assertion carries none of them cannot discriminate the law the section
    states -- which is exactly how S7 passed a ramp.
    """
    if table is None or len(table.header) < 4:
        return []

    # A ruling number maps to MANY sections, not one. The first cut used a
    # dict and last-writer-won: #328 is carried by §Chrome environment strip,
    # §How a colour is asserted, §Radial zones AND §Bezel, so `by_ruling[328]`
    # resolved to §Bezel -- which has no table -- and this signal reported
    # NOTHING on the one row it exists to name. Measured, not reasoned about:
    # the probe returned zero findings until this became a list.
    by_ruling: dict[str, list[ContractSection]] = {}
    for section in sections:
        for ruling in section.rulings:
            by_ruling.setdefault(ruling, []).append(section)
    by_name = {_norm(section.name): section for section in sections}

    signals: list[Signal] = []
    for row in table.rows:
        if len(row) < 4:
            continue
        row_id, binding_cell, assertion_cell = row[0], row[2], row[3]
        cited: list[ContractSection] = []
        for m in _RULING.finditer(binding_cell):
            cited.extend(by_ruling.get(m.group("n"), []))
        cited += [
            by_name[_norm(m.group("name"))]
            for m in _SECTION_CITATION.finditer(binding_cell)
            if _norm(m.group("name")) in by_name
        ]
        seen: set[str] = set()
        for section in cited:
            if section.name in seen:
                continue
            seen.add(section.name)
            values = section.table_values
            if not values:
                continue
            carried = values & set(_NUMBER.findall(assertion_cell))
            if carried:
                continue
            laws = section.laws
            signals.append(
                Signal(
                    shape="assertion-cannot-falsify",
                    where=f"row {row_id} -> §{section.name}",
                    detail=(
                        f"the binding cites this section's table but the "
                        f"assertion carries none of its "
                        f"{len(values)} value(s). "
                        + (f"The section states: {laws[0][:200]}" if laws else "")
                    ),
                    mechanical=True,
                )
            )
    return signals


def signal_unbound_presuppositions(
    contract_text: str, sections: list[ContractSection], rows: list[list[str]]
) -> list[Signal]:
    """Properties every tolerance is engineered around and no table binds.

    The one fact-verifier of the three. A term the contract uses to justify a
    tolerance -- or cites as a named rule -- while binding it nowhere is #377's
    shape, and the pattern fires twice on the real contract with both hits real.
    """
    terms: dict[str, list[str]] = {}
    for pattern in (_PRESUPPOSITION, _NAMED_RULE):
        for match in pattern.finditer(contract_text or ""):
            term = _norm(match.group("term"))
            if not term or len(term) < 4:
                continue
            start = max(0, match.start() - 90)
            terms.setdefault(term, []).append(
                contract_text[start: match.end() + 40].replace("\n", " ").strip()
            )

    row_text = _norm(" ".join(cell for row in rows for cell in row))
    table_text = _norm(
        " ".join(
            cell
            for section in sections
            for table in section.tables
            for r in table.rows
            for cell in r
        )
    )

    signals: list[Signal] = []
    for term, sites in sorted(terms.items()):
        if term in row_text or term in table_text:
            continue
        signals.append(
            Signal(
                shape="unbound-presupposition",
                where=term,
                detail=(
                    f"engineered around {len(sites)} time(s) in the contract "
                    f"and bound by no row of the contract's tables and no row "
                    f"of the issue's table. Sites: "
                    + " | ".join(f"...{s}..." for s in sites[:3])
                ),
                mechanical=True,
            )
        )
    return signals


# ---------------------------------------------------------------------------
# The brief
# ---------------------------------------------------------------------------


@dataclass
class FidelityBrief:
    """Everything the reviewer needs, and the record of what was assembled."""

    contract_path: str = ""
    sections: list[ContractSection] = field(default_factory=list)
    table: RawTable | None = None
    signals: list[Signal] = field(default_factory=list)
    ledger: list[tuple[str, str, list[str]]] = field(default_factory=list)
    error: str = ""

    @property
    def ready(self) -> bool:
        return bool(self.sections) and self.table is not None and not self.error

    def disclosure(self) -> str:
        if self.error:
            return f"contract fidelity: NOT CHECKED — {self.error}"
        if self.table is None:
            return (
                "contract fidelity: NOT CHECKED — the issue carries no criteria "
                "table (ID + binding value) to audit against the contract."
            )
        if not self.sections:
            return (
                f"contract fidelity: NOT CHECKED — no section of "
                f"`{self.contract_path}` is put in play by this issue's scope."
            )
        return (
            f"contract fidelity: {len(self.sections)} contract section(s) from "
            f"`{self.contract_path}` against {len(self.table.rows)} table "
            f"row(s) — {len(self.signals)} candidate(s) for review."
        )

    def as_prompt(self) -> str:
        """The reviewer's brief: the contract's own words, then the table.

        Sections are quoted VERBATIM. A summarised contract is a second
        compression of the document whose first compression is what is under
        audit.
        """
        parts = [f"# Contract: {self.contract_path}", ""]
        for section in self.sections:
            parts += [f"## §{section.name}", section.body.strip(), ""]
        parts += ["# The issue's decision table", ""]
        if self.table is not None:
            parts.append("| " + " | ".join(self.table.header) + " |")
            parts.append("|" + "---|" * len(self.table.header))
            for row in self.table.rows:
                parts.append("| " + " | ".join(row) + " |")
        parts += ["", "# Which sub-binding of each section a row names", ""]
        parts.append(
            "Evidence, not a verdict. Naming is not binding in either "
            "direction: a row may name a sub-binding and assert nothing that "
            "could falsify it, and a sub-binding no row names may be fully "
            "bound under another wording -- §Tick marks / Color says only "
            '"Pure white", and the row that binds it carries `#FFFFFF` '
            "without ever using the word Color. Judge against the section "
            "text above, not against this list."
        )
        parts.append("")
        for section_name, binding_name, named_by in self.ledger:
            mark = ", ".join(named_by) if named_by else "NO ROW NAMES IT"
            parts.append(f"- §{section_name} / {binding_name}: {mark}")
        if not self.ledger:
            parts.append("(no section in play carries bolded sub-bindings)")

        parts += ["", "# Mechanical signals already computed", ""]
        if not self.signals:
            parts.append("(none)")
        for signal in self.signals:
            kind = "FACT" if signal.mechanical else "CANDIDATE"
            parts.append(f"- [{kind}] [{signal.shape}] {signal.where}: {signal.detail}")
        return "\n".join(parts)


def build_brief(repo_root: Path | str, issue: int, title: str, body: str) -> FidelityBrief:
    """Assemble the reviewer's brief. Pure apart from reading the contract."""
    brief = FidelityBrief()

    contract_path = resolve_contract(repo_root, issue)
    if contract_path is None:
        brief.error = (
            "this repo declares no binding contract for this issue in "
            "docs/design/visual-gate.json"
        )
        return brief
    brief.contract_path = str(
        contract_path.relative_to(Path(repo_root))
    ).replace("\\", "/")

    try:
        text = contract_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        # fail-open: the ROLL continues, because this check is report-only and
        # an unreadable file must not brick a launch. The VERDICT does not:
        # `error` is set and `ready` stays False, so `disclosure` prints NOT
        # CHECKED and `review_fidelity` refuses to call the model at all.
        # "Was not audited" and "was audited and passed" never render the same.
        brief.error = f"the declared contract could not be read: {exc}"
        return brief

    sections = parse_contract(text)
    brief.sections = sections_in_play(title, body, sections)

    tables = [t for t in parse_tables(body or "") if is_criteria_table(t)]
    brief.table = tables[0] if tables else None
    rows = brief.table.rows if brief.table is not None else []

    brief.signals = (
        signal_unbound_presuppositions(text, sections, rows)
        + signal_assertions_that_cannot_falsify(brief.sections, brief.table)
        + signal_sections_without_rows(brief.sections, rows)
    )
    brief.ledger = binding_ledger(brief.sections, rows)
    return brief


# ---------------------------------------------------------------------------
# The review
# ---------------------------------------------------------------------------


FIDELITY_MARKER = "CONTRACT FIDELITY:"

FIDELITY_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "shape": {
                        "type": "string",
                        "enum": [
                            "binding-no-row",
                            "assertion-cannot-falsify",
                            "unbound-presupposition",
                        ],
                    },
                    "where": {"type": "string"},
                    "contract_quote": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["shape", "where", "contract_quote", "why"],
            },
        }
    },
    "required": ["findings"],
}

FIDELITY_SYSTEM_PROMPT = """\
You audit ONE compression: a binding design contract into an issue's decision
table. You are the only reader in the pipeline that has both documents.

Report only these three shapes:

1. binding-no-row -- the contract binds something the table never carries, so
   no test can exist for it and the implementer will not build it.
2. assertion-cannot-falsify -- a row exists, but its assertion cell cannot
   fail under a render that violates its own binding cell. The test question
   is always: name a WRONG implementation that passes this assertion. If you
   can, it is a finding; if you cannot, it is not.
3. unbound-presupposition -- the contract engineers tolerances around a render
   property it never binds, so every tolerance tolerates its absence.

Rules that decide the report:

* Quote the contract verbatim in contract_quote. A finding you cannot quote is
  not a finding.
* An adjective is not a binding. "Substantial", "confident", "smooth" carry no
  value a test can assert, and the contract says so itself. Do not report a
  missing row for prose that specifies nothing.
* Naming is not binding, in either direction. A row that names a sub-binding
  may still assert nothing that could falsify it; a sub-binding no row names
  may be fully bound under different words. The ledger tells you where to
  look, never what to conclude.
* Values already carried somewhere in the table are covered. Do not report a
  binding as missing because a row states it in a different but equivalent
  form (10% of R and 0.10 R are the same quantity).
* Say nothing about elements the issue declares out of scope.

Report no findings if there are none. An empty findings list is a real answer.
"""


@dataclass
class FidelityReview:
    """One audit's outcome. `reached` false is never a clean bill."""

    brief: FidelityBrief
    reached: bool = False
    findings: list[dict] = field(default_factory=list)
    reason: str = ""
    answered_by: str = ""

    @property
    def ok(self) -> bool:
        return self.reached and not self.findings

    def lines(self) -> list[str]:
        out = [self.brief.disclosure()]
        if not self.brief.ready:
            return out
        if not self.reached:
            out.append(
                f"  {FIDELITY_MARKER} NOT REACHED -- {self.reason}. The "
                f"compression was NOT audited; this is not a clean result."
            )
            return out
        for signal in self.brief.signals:
            out.append(f"  [{signal.shape}] {signal.where}: {signal.detail}")
        for finding in self.findings:
            out.append(
                f"  {FIDELITY_MARKER} [{finding.get('shape', '?')}] "
                f"{finding.get('where', '?')} -- {finding.get('why', '')}"
            )
            quote = (finding.get("contract_quote") or "").strip()
            if quote:
                out.append(f"      contract: {quote[:300]}")
        if not self.findings:
            out.append(
                f"  audited by {self.answered_by}: the table carries what the "
                f"cited sections bind."
            )
        return out


def review_fidelity(
    brief: FidelityBrief,
    drafter_spec: str = "gemini:3.1-pro",
    timeout_seconds: int = 300,
) -> FidelityReview:
    """Ask the reviewer to adjudicate, with the contract in hand.

    Fails CLOSED in reporting, per #2474's ruling and standard 0028: a review
    that cannot reach a verdict is recorded as NOT REACHED, never as clean.
    It does not block the roll -- this check is report-only -- but "was not
    audited" and "was audited and passed" never render the same.
    """
    review = FidelityReview(brief=brief)
    if not brief.ready:
        review.reason = brief.error or "the brief could not be assembled"
        return review

    from assemblyzero.core.llm_provider import GeminiProvider, get_provider

    try:
        provider = get_provider(drafter_spec)
    except ValueError as exc:
        # fail-open: the roll proceeds -- a bad provider spec is not this
        # check's to halt on, and #2474 already halts the requirements gate
        # for it. `reached` stays False, so the audit reports NOT REACHED
        # rather than clean.
        review.reason = f"invalid provider '{drafter_spec}': {exc}"
        return review

    schema_kwargs: dict = {}
    if isinstance(provider, GeminiProvider):
        schema_kwargs["response_schema"] = FIDELITY_SCHEMA
    else:
        schema_kwargs["json_schema"] = FIDELITY_SCHEMA

    result = provider.invoke(
        system_prompt=FIDELITY_SYSTEM_PROMPT,
        content=brief.as_prompt(),
        timeout_seconds=timeout_seconds,
        **schema_kwargs,
    )

    review.answered_by = drafter_spec
    if not getattr(result, "success", False) or not getattr(result, "response", None):
        review.reason = (
            getattr(result, "error_message", "") or "the provider returned no response"
        )
        return review

    try:
        parsed = json.loads(result.response)
    except (TypeError, ValueError) as exc:
        # fail-open: an unparseable answer does not halt the roll. It does not
        # pass either -- `reached` stays False and the reason is printed, per
        # standard 0028: a read that cannot be trusted never becomes a
        # degraded value dressed as a verdict.
        review.reason = f"the reviewer's answer was not JSON: {exc}"
        return review

    findings = parsed.get("findings") if isinstance(parsed, dict) else None
    if not isinstance(findings, list):
        review.reason = "the reviewer's answer carried no findings list"
        return review

    review.reached = True
    review.findings = [f for f in findings if isinstance(f, dict)]
    return review


def check_contract_fidelity_at_preflight(
    repo_root, issues: list[int], fetch, drafter_spec: str = "gemini:3.1-pro"
) -> tuple[str, bool]:
    """The whole preflight step: (text to print, whether to refuse).

    Never refuses. Report-only for the reason #2227 and #2387 give -- and with
    a further one of its own: this is the first check in the stack that spends
    a model call at preflight, and it only runs for a repo that declares a
    binding contract for the issue being rolled. Every other repo pays nothing
    and sees one line saying so.
    """
    lines = [f"{LABEL} -- reads the contract the issue cites:"]
    ran = False
    for issue in issues or []:
        try:
            title, body = fetch(repo_root, issue)
        except Exception as exc:  # noqa: BLE001
            # fail-open: a read failure is not a verdict, and the form check
            # above has already reported the same failure for the same issue.
            lines.append(f"  #{issue}: could not be read ({exc}).")
            continue
        brief = build_brief(repo_root, issue, title, body)
        if not brief.ready and "declares no binding contract" in brief.error:
            lines.append(f"  #{issue}: {brief.disclosure()}")
            continue
        ran = True
        review = review_fidelity(brief, drafter_spec=drafter_spec)
        lines.append(f"  #{issue}: " + review.lines()[0])
        lines.extend("    " + line for line in review.lines()[1:])

    if ran:
        lines += [
            "",
            "  Reported only; the roll proceeds. A finding here is a defect in "
            "the ISSUE, not in the pipeline -- fix the decision table before "
            "the roll hardens it.",
        ]
    return "\n".join(lines), False
