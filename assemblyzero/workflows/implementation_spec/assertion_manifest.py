"""Compile the LLD's decision tables into an assertion manifest (#2533).

Most of an implementation spec for a numeric contract is compilation, not
composition: the creative decisions already happened, in the LLD's decision
tables and the render contract's tables. Asking a stochastic drafter to perform
that deterministic expansion is why the spec stage churns — it invents ~60
coupled assertions per draft and gets a few wrong each round. This module is
the third repetition of the factory's proven pattern (N0c for issue text, the
visual gate for aesthetics): move the deterministic truth-producer ahead of the
stochastic spender, and gate on it.

What compiles
-------------

A **criteria decision table** is any markdown pipe table whose header carries
an ``ID`` column and a ``Binding value`` column — the operator-ratified shape
(boostgauge #332's needle and telltale tables are the reference):

    | ID | Criterion | Binding value (quoted) | Assertion method |

Each table row expands into one manifest row per assertion FRAGMENT — the
method cell split on top-level ``;`` — so a criterion measured at two sample
points yields two citable rows. A fragment's expected values are the literals
found in it (hex colours, RGB tuples, degrees, R-fractions, alpha/percent
values, channel predicates, plain thresholds); the binding-value cell's
literals back any fragment that carries none of its own. **The manifest quotes;
it never derives** — the fragment text IS the sample-point description, exactly
as the operator wrote it, which is what made every previous quotable table end
its churn class.

Fail closed (the #2474 lesson, enforced by the #2475 gate)
----------------------------------------------------------

A criterion that will not compile — no literal anywhere in its row, a
placeholder word standing where a value should be, a hex colour that resolves
to no row of the target contract, two rows claiming the same ID — is an
upstream-document defect, caught in seconds for free, before any draft spend.
The node HALTS and files a must-resolve per defect, exactly N0c's path. There
is no fall-through.

Not applicable is not failure: an LLD with no criteria decision table (most
repos, every non-visual issue) compiles to an empty manifest and the stage
proceeds exactly as before this node existed.

The manifest is a lineage artifact, regenerable from (LLD, contract) at spec
time, never hand-maintained — per the audits-are-programs rule.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from assemblyzero.workflows.requirements.form_check import RawTable, parse_tables

# ---------------------------------------------------------------------------
# Literal extraction
# ---------------------------------------------------------------------------

#: Hex colour, e.g. #F73923. The one literal class the contract can be asked
#: to confirm mechanically, so it is captured separately.
_HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")

#: Everything else that counts as a literal value. Order matters only for
#: readability of the extracted list; extraction is a set union.
_LITERAL_RES: tuple[re.Pattern, ...] = (
    _HEX_RE,
    re.compile(r"\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)"),  # RGB tuple
    re.compile(r"[-−]?\d+(?:\.\d+)?\s*°"),                          # degrees
    re.compile(r"\d+(?:\.\d+)?\s*R\b"),                             # R-fraction
    re.compile(r"\balpha\s+\d{1,3}\b", re.IGNORECASE),              # alpha 166
    re.compile(r"\d+(?:\.\d+)?\s*%"),                               # percent
    re.compile(r"\d+(?:\.\d+)?\s*px\b"),                            # pixels
    re.compile(r"\b[A-Za-z]\s*(?:[<>]=?|≥|≤|=)\s*\d+(?:\.\d+)?"),   # R ≥ 180
    re.compile(r"(?:[<>]=?|≥|≤)\s*\d+(?:\.\d+)?"),                  # bare bound
    re.compile(r"\b\d+(?:\.\d+)?\s*[x×]\b"),                        # 0.45 x
    # Exact ABSENCE and IDENTITY expectations. "renders nothing", "no
    # telltale-family pixel present", "identical to the bare face" are
    # literal expected outcomes — mechanically checkable, nothing adjectival
    # about them. Found on the first live compile: #332's T1 (a None peak
    # renders nothing) is a real criterion whose value is an absence, and
    # halting on it would be the false alarm the fleet rule forbids.
    re.compile(
        r"\b(?:renders?\s+nothing|draws?\s+nothing|nothing\s+is\s+drawn"
        r"|no\s+[\w-]+(?:\s+[\w-]+)?\s+pixel|identical|empty|absent)\b",
        re.IGNORECASE,
    ),
)

#: Words that fill a value slot without being a value. The class ruling #265
#: retired ("Adjectives are not a specification") — their presence in a
#: binding-value cell means the upstream doc still owes a number.
PLACEHOLDER_WORDS = frozenset({
    "tbd", "todo", "approximately", "approx", "roughly", "about",
    "appropriate", "suitable", "reasonable", "some", "several",
    "unspecified", "unknown", "unclear", "n/a", "various",
})

_WORD_RE = re.compile(r"[A-Za-z/]+")


def extract_literals(text: str) -> list[str]:
    """Every literal value in ``text``, in order of first appearance."""
    found: list[tuple[int, str]] = []
    seen: set[str] = set()
    for pattern in _LITERAL_RES:
        for match in pattern.finditer(text or ""):
            value = match.group(0).strip()
            if value not in seen:
                seen.add(value)
                found.append((match.start(), value))
    return [value for _, value in sorted(found)]


def placeholder_words_in(text: str) -> list[str]:
    """The placeholder words present in ``text``, lowercased, in order."""
    hits: list[str] = []
    for word in _WORD_RE.findall(text or ""):
        lowered = word.lower()
        if lowered in PLACEHOLDER_WORDS and lowered not in hits:
            hits.append(lowered)
    return hits


# ---------------------------------------------------------------------------
# Decision-table recognition
# ---------------------------------------------------------------------------


def _header_index(table: RawTable, *needles: str) -> int | None:
    for index, cell in enumerate(table.header):
        lowered = cell.lower()
        if all(needle in lowered for needle in needles):
            return index
    return None


def is_criteria_table(table: RawTable) -> bool:
    """A decision table in the ruled #332 shape: an ID and a binding value."""
    return (
        _header_index(table, "id") is not None
        and _header_index(table, "binding") is not None
        and bool(table.rows)
    )


def _split_fragments(method_cell: str) -> list[str]:
    """The method cell's assertion fragments: split on ``;`` outside parens.

    Each fragment is one sample-point description in the operator's own words.
    A cell with no ``;`` is one fragment.
    """
    fragments: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in method_cell:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == ";" and depth == 0:
            fragments.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    fragments.append("".join(current).strip())
    return [f for f in fragments if f]


# ---------------------------------------------------------------------------
# The manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ManifestRow:
    """One criterion × sample-point row, citable by id."""

    row_id: str        # "N4.2"
    criterion_id: str  # "N4"
    criterion: str     # the criterion cell, verbatim
    sample_point: str  # the assertion fragment, verbatim (the operator's words)
    expected: str      # the literal expected values backing this fragment
    source: str        # which table row it compiled from


@dataclass(frozen=True)
class CompileFailure:
    """One uncompilable criterion — an upstream-document defect, named."""

    criterion_id: str
    reason: str
    row_text: str


@dataclass(frozen=True)
class CompileResult:
    applicable: bool
    rows: tuple[ManifestRow, ...] = ()
    failures: tuple[CompileFailure, ...] = ()
    criteria_ids: tuple[str, ...] = ()
    #: Hex colours the contract carries, empty when no contract was given.
    contract_hexes: frozenset[str] = field(default_factory=frozenset)


def contract_hex_universe(contract_text: str) -> frozenset[str]:
    """Every hex colour the contract document states, uppercased."""
    return frozenset(h.upper() for h in _HEX_RE.findall(contract_text or ""))


def compile_manifest(
    lld_content: str, contract_text: str = ""
) -> CompileResult:
    """Compile every criteria decision table in ``lld_content``.

    Pure and deterministic: no model call, no filesystem, no clock. The
    contract text, when given, supplies the hex universe every cited colour
    must resolve into — a colour in neither the palette nor any other contract
    table is the "sample point resolving to no zone row" defect.
    """
    tables = [t for t in parse_tables(lld_content or "") if is_criteria_table(t)]
    if not tables:
        return CompileResult(applicable=False)

    contract_hexes = contract_hex_universe(contract_text)
    rows: list[ManifestRow] = []
    failures: list[CompileFailure] = []
    criteria_ids: list[str] = []
    seen_ids: dict[str, str] = {}  # id -> row text, for the contradiction check

    for table in tables:
        id_col = _header_index(table, "id")
        binding_col = _header_index(table, "binding")
        criterion_col = _header_index(table, "criterion")
        method_col = _header_index(table, "assertion")
        if method_col is None:
            method_col = _header_index(table, "method")

        for raw_row in table.rows:
            def cell(index: int | None) -> str:
                if index is None or index >= len(raw_row):
                    return ""
                return raw_row[index].replace("`", "").strip()

            criterion_id = cell(id_col)
            row_text = " | ".join(raw_row)
            if not criterion_id:
                failures.append(CompileFailure(
                    "(missing)", "a decision-table row carries no ID", row_text,
                ))
                continue

            if criterion_id in seen_ids:
                if seen_ids[criterion_id] != row_text:
                    failures.append(CompileFailure(
                        criterion_id,
                        "two decision-table rows claim this ID with different "
                        "content — the documents contradict each other",
                        row_text,
                    ))
                continue
            seen_ids[criterion_id] = row_text
            criteria_ids.append(criterion_id)

            binding = cell(binding_col)
            criterion = cell(criterion_col)
            method = cell(method_col)

            placeholders = placeholder_words_in(binding)
            if placeholders:
                failures.append(CompileFailure(
                    criterion_id,
                    f"the binding value contains placeholder wording "
                    f"({', '.join(placeholders)}) where a literal belongs — "
                    f"adjectives are not a specification (ruling #265)",
                    row_text,
                ))
                continue

            binding_literals = extract_literals(binding)
            fragments = _split_fragments(method) if method else []
            if not fragments:
                fragments = [binding or criterion]

            compiled_any = False
            fragment_rows: list[ManifestRow] = []
            for index, fragment in enumerate(fragments, start=1):
                literals = extract_literals(fragment) or binding_literals
                if not literals:
                    continue
                compiled_any = True
                fragment_rows.append(ManifestRow(
                    row_id=f"{criterion_id}.{index}",
                    criterion_id=criterion_id,
                    criterion=criterion,
                    sample_point=fragment,
                    expected="; ".join(literals),
                    source=f"decision table row {criterion_id}",
                ))

            if not compiled_any:
                failures.append(CompileFailure(
                    criterion_id,
                    "no literal value anywhere in the row — a criterion "
                    "without a number compiles to the assert-isinstance "
                    "non-test ruling #265 retired",
                    row_text,
                ))
                continue

            # Every hex the row cites must resolve into the contract.
            if contract_hexes:
                cited = {
                    h.upper()
                    for h in _HEX_RE.findall(binding + " " + method)
                }
                orphans = sorted(cited - contract_hexes)
                if orphans:
                    failures.append(CompileFailure(
                        criterion_id,
                        f"cites {', '.join(orphans)}, which appears nowhere "
                        f"in the target contract — the decision table and the "
                        f"contract disagree about the palette",
                        row_text,
                    ))
                    continue

            rows.extend(fragment_rows)

    return CompileResult(
        applicable=True,
        rows=tuple(rows),
        failures=tuple(failures),
        criteria_ids=tuple(criteria_ids),
        contract_hexes=contract_hexes,
    )


# ---------------------------------------------------------------------------
# Rendering and the mechanical gate
# ---------------------------------------------------------------------------


def render_manifest(result: CompileResult) -> str:
    """The manifest as a markdown table — the lineage artifact and the
    drafter's binding input, ~one line per row."""
    lines = [
        "# Assertion manifest (compiled — regenerable, never hand-edited)",
        "",
        "| Row | Criterion | Sample point (verbatim) | Expected (literal) |",
        "|---|---|---|---|",
    ]
    for row in result.rows:
        lines.append(
            f"| {row.row_id} | {row.criterion} | {row.sample_point} "
            f"| {row.expected} |"
        )
    return "\n".join(lines) + "\n"


def rows_as_dicts(result: CompileResult) -> list[dict]:
    """State-serializable rows (TypedDict state carries plain values)."""
    return [
        {
            "row_id": r.row_id,
            "criterion_id": r.criterion_id,
            "criterion": r.criterion,
            "sample_point": r.sample_point,
            "expected": r.expected,
            "source": r.source,
        }
        for r in result.rows
    ]


def gate_findings(result: CompileResult) -> list[str]:
    """The mechanical gate over a compiled manifest (#2533 property 2).

    Judges the MANIFEST, not the documents — compile failures already halted
    upstream. Everything here is a compiler-output invariant: a finding means
    the compiler broke its own contract, and the run must not spend a draft
    on a manifest that cannot be trusted.
    """
    findings: list[str] = []
    if not result.applicable:
        return findings

    covered = {row.criterion_id for row in result.rows}
    missing = [cid for cid in result.criteria_ids if cid not in covered]
    if missing:
        findings.append(
            f"criteria with no manifest row: {', '.join(missing)} — "
            f"row count does not match the criteria count"
        )
    orphan = sorted(covered - set(result.criteria_ids))
    if orphan:
        findings.append(
            f"manifest rows citing no known criterion: {', '.join(orphan)}"
        )

    for row in result.rows:
        if not extract_literals(row.expected):
            findings.append(
                f"row {row.row_id}: expected value is not literal "
                f"({row.expected!r})"
            )
        hits = placeholder_words_in(row.expected) + placeholder_words_in(
            row.sample_point
        )
        if hits:
            findings.append(
                f"row {row.row_id}: placeholder wording survived compilation "
                f"({', '.join(sorted(set(hits)))})"
            )

    seen: dict[tuple[str, str], str] = {}
    for row in result.rows:
        key = (row.criterion_id, " ".join(row.sample_point.lower().split()))
        if key in seen:
            findings.append(
                f"rows {seen[key]} and {row.row_id} duplicate the same "
                f"sample point for {row.criterion_id}"
            )
        else:
            seen[key] = row.row_id

    return findings
