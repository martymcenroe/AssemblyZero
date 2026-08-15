"""Make the non-discriminating-test class unwritable (#2387).

The semantic gate found the same defect four times across six samples of
boostgauge #2 and #7: a criterion whose test points all sit at COINCIDENCE
POINTS -- values where a correct implementation and a degenerate one produce
identical output. Each instance was real; each cost a gate round (~5 minutes of
model call) to find; and the class is mechanically characterizable, which by
ADR 0228's own doctrine means it should be unwritable rather than serially
findable.

Rounds on boostgauge #2 went 3, 3, 1, 2, 1, 1 findings. The tail is entirely
this class. A deterministic check would have named all of them in one free pass.

## The two shapes, both mechanical

**Coincidence-point coverage.** A criterion pins its expected outputs *at
default config* and nowhere else. boostgauge #308, verbatim from the gate:

    "The U1 test plan checks only the four default-config strings; at those
     exact values a hardcoded implementation ('1m — cyan', '10m — orange',
     '1h — magenta', 'All-time — coral red') and a genuine dynamic formatter
     produce identical output."

The repair that satisfied the gate is the shape this check demands: the
criterion carries a non-default case as well ("short at 90 seconds must read
'90s — cyan'").

**Absence-only oracle.** A criterion asserts only that nothing changed, so it
passes under an implementation that ignores the input entirely. boostgauge
#300, verbatim:

    "S3 passes identically under both readings -- it checks only that the
     file's `size` key remains 300 and that 500 is not written to the file,
     which is equally true whether the window displayed 500 or 300."

A no-change assertion is a real thing to test and is not banned. What is
flagged is a criterion that has *nothing else* -- no positive observation of
the value actually taking effect.

## Why it is narrow on purpose

A check that cries wolf gets switched off within a day, and this session has
already had to retract one audit for reporting seven suspects of which zero
were real. So each rule fires only on POSITIVE evidence: the criterion must
itself declare that its values are default-config ones, or must itself consist
of nothing but absence assertions. A criterion that pins no values at all is
not guessed about -- it is out of scope and said so.

The vacuous state is disclosed rather than passed, per the #2227 ruling:
"checked and found nothing to check" and "checked and found none" are different
facts and are printed differently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from assemblyzero.workflows.requirements.form_check import (
    Violation,
    acceptance_criteria,
)

#: The criterion says, in its own words, that these outputs are what default
#: configuration produces. Written as the ADR 0226/0228 convention writes it.
_DEFAULT_ANCHOR = re.compile(
    r"\b(?:at|under|with)\s+(?:the\s+)?default(?:\s+config(?:uration)?)?\b"
    r"|\bdefault\s+config(?:uration)?\s+(?:renders|reads|gives|produces)\b"
    r"|\bdefault-config\b",
    re.IGNORECASE,
)

#: The criterion also pins a value away from the defaults. Any one of these is
#: enough -- the point is that SOME non-coincident point is covered, not that
#: it is covered in a particular phrasing.
_NON_DEFAULT_ANCHOR = re.compile(
    r"\bnon-?default\b"
    r"|\boff\s+the\s+defaults?\b"
    r"|\bdiscriminating\s+case\b"
    r"|\bother\s+than\s+(?:the\s+)?defaults?\b",
    re.IGNORECASE,
)

#: An assertion that nothing happened. These are legitimate individually; a
#: criterion built ONLY from them has no oracle for the value taking effect.
_ABSENCE = re.compile(
    r"\bunchanged\b|\bnot\s+written\b|\bnever\s+written\b|\bno\s+\w+\s+is\s+"
    r"written\b|\bremains?\b|\bis\s+not\s+(?:changed|modified|updated)\b"
    r"|\buntouched\b|\bnot\s+persisted\b",
    re.IGNORECASE,
)

#: A positive observation -- something is rendered, returned, displayed, held,
#: or equals a value. Presence of one of these means the criterion is not
#: absence-only.
#:
#: `holds` earns its place from boostgauge #7's S7: "`size` holds the default;
#: the CLI value is not written". That states what the value IS, which an
#: implementation ignoring the input can fail. The gate flagged S3 and not S7,
#: and this is the difference between them.
_POSITIVE = re.compile(
    r"\brenders?\b|\breads?\b|\bdisplays?\b|\bshows?\b|\breturns?\b"
    r"|\bopens?\s+at\b|\bemits?\b|\bcalls?\b|\breceives?\b|\bequals?\b"
    r"|\bmust\s+be\b|\bproduces?\b|\bconstructed\b|\bpasses\s+all\b"
    r"|\bholds?\b",
    re.IGNORECASE,
)

#: The scenario actually supplies an input that could be ignored. Without one,
#: "nothing changed" is the whole truth rather than a weak oracle.
#:
#: Measured on boostgauge #7: S3 ("`--size` given ... `size` unchanged; the CLI
#: value is not written") is the real defect the gate found. P1 ("no reset, not
#: moved, no direct edits: `position` unchanged") and S1 ("no `--size` ...
#: unchanged") are not -- nothing was supplied, so there is nothing an
#: implementation could be ignoring. A first cut without this condition flagged
#: all three.
#: The negative lookbehinds are load-bearing. These scenarios are written as
#: matched pairs -- "`--size` given" against "not resized", "no `--size`" --
#: so a bare verb match reads "no `--size`, not resized" as an input being
#: supplied, which is the exact opposite of what it says.
_INPUT_SUPPLIED = re.compile(
    r"(?<!not )(?<!no )"
    r"\b(?:given|supplied|provided|passed|specified|resized|moved)\b"
    r"|\bwith\s+--[\w-]+",
    re.IGNORECASE,
)

#: Criteria that pin no expected value at all are out of scope: there is
#: nothing to judge the discrimination of. A quoted or backticked literal is
#: the signal that the criterion states an expected output.
_LITERAL = re.compile(r"'[^']+'|\"[^\"]+\"|`[^`]+`")

#: The ID a criterion leads with, so a violation can name it.
_CRITERION_ID = re.compile(r"^\s*([A-Z][A-Za-z]*[0-9]+)\b")


@dataclass
class DiscriminationReport:
    """What was judged about a document's discriminating coverage."""

    criteria_examined: int = 0
    criteria_pinning_values: int = 0
    default_anchored: int = 0
    absence_only: int = 0
    violations: list[Violation] = field(default_factory=list)
    criteria_section_found: bool = True

    @property
    def ok(self) -> bool:
        return not self.violations

    @property
    def vacuous(self) -> bool:
        """Nothing was judged -- which is NOT the same as nothing was wrong."""
        return self.criteria_pinning_values == 0

    def disclosure(self) -> str:
        """One line stating what the check actually did (#2227).

        A check with nothing to check must say so. Reporting "no findings" for
        a document it never judged is how a gate reads as thorough validation
        while verifying nothing.
        """
        if not self.criteria_section_found:
            return (
                "discrimination coverage: NOT CHECKED — no Acceptance Criteria "
                "section found."
            )
        if self.vacuous:
            return (
                f"discrimination coverage: nothing to check — "
                f"{self.criteria_examined} criterion(s) examined, none pins an "
                f"expected value, so none can be judged for discrimination."
            )
        return (
            f"discrimination coverage: {self.criteria_pinning_values} of "
            f"{self.criteria_examined} criterion(s) pin expected values; "
            f"{self.default_anchored} anchored at default config, "
            f"{len(self.violations)} finding(s)."
        )


def criterion_id(text: str) -> str:
    match = _CRITERION_ID.match(text)
    return match.group(1) if match else text[:24].strip()


def pins_a_value(text: str) -> bool:
    """Does this criterion state an expected output at all?"""
    return bool(_LITERAL.search(text))


def is_default_anchored(text: str) -> bool:
    """Does the criterion itself say its values are default-config ones?"""
    return bool(_DEFAULT_ANCHOR.search(text))


def has_non_default_case(text: str) -> bool:
    """Does the criterion also pin a value away from the defaults?

    Two ways to qualify, both taken from how the boostgauge repairs were
    actually written: an explicit non-default marker, or a concrete magnitude
    stated alongside a unit ("short at 90 seconds reads 'Reset 90s'"). The
    second is what a real discriminating case looks like when the author does
    not use the word "non-default".
    """
    if _NON_DEFAULT_ANCHOR.search(text):
        return True
    # "at 90 seconds", "at 900 seconds", "configured to 90s"
    if re.search(
        r"\b(?:at|to|of)\s+\d+\s*(?:s\b|ms\b|seconds?\b|minutes?\b|hours?\b|px\b|%)",
        text,
        re.IGNORECASE,
    ):
        return True
    # A SYMBOLIC value supplied through a flag -- "`--reset-config --size N`,
    # it opens at the default position and size N". Boostgauge #7's L4 states
    # its discriminating case this way, with a placeholder rather than a
    # number, and a literal-only rule reported it as uncovered. A placeholder
    # standing for "any value" is a stronger discriminating claim than one
    # number, not a weaker one.
    return bool(re.search(r"--[\w-]+\s+([A-Z])\b", text))


def is_absence_only(text: str) -> bool:
    """Are ALL this criterion's assertions no-change assertions, on a scenario
    that actually supplies an input?

    A no-change assertion is legitimate and common. What is flagged is the
    combination boostgauge #300 found: a value IS supplied, and the only thing
    asserted is that nothing was written -- which is equally true whether the
    value took effect or was ignored entirely.

    Both conditions are required. Dropping the supplied-input condition flags
    "no reset, not moved, no direct edits: `position` unchanged", where nothing
    was supplied and "unchanged" is the whole truth.
    """
    if not _ABSENCE.search(text):
        return False
    if _POSITIVE.search(text):
        return False
    return bool(_INPUT_SUPPLIED.search(text))


def family_of(criterion: str) -> str:
    """The ID prefix a criterion belongs to: RS1 -> RS, U1 -> U.

    ADR 0228 names one owning criteria group per variable by ID prefix, so the
    prefix IS the surface. Coverage is judged per family for that reason -- see
    `check_discrimination`.
    """
    ident = criterion_id(criterion)
    match = re.match(r"^([A-Z][A-Za-z]*)", ident)
    return match.group(1) if match else ident


def check_discrimination(body: str) -> DiscriminationReport:
    """Judge a document's criteria for discriminating coverage (#2387).

    Coverage is judged PER FAMILY, not per criterion, and that is the whole
    difference between a usable check and a wolf. Measured against boostgauge
    #2 as a human left it after seven gate rounds: a per-criterion rule flagged
    RS1, RS2 and RS3 because each pins only its default-config label -- while
    RS6, in the same family, carries the non-default case for every window on
    that surface. The document is correctly covered; the coverage simply lives
    in a sibling. Three findings, all false.

    An absence-only oracle stays per-criterion, because each criterion is its
    own scenario and needs its own oracle -- a sibling asserting something
    positive about a different scenario does not rescue it.
    """
    report = DiscriminationReport()

    criteria, section_found = acceptance_criteria(body)
    report.criteria_section_found = section_found
    if not section_found:
        return report

    report.criteria_examined = len(criteria)

    valued = [c for c in criteria if pins_a_value(c)]
    report.criteria_pinning_values = len(valued)

    # Which families have a discriminating case anywhere in them.
    covered: set[str] = {
        family_of(c) for c in valued if has_non_default_case(c)
    }

    flagged_families: set[str] = set()
    for text in valued:
        where = criterion_id(text)
        family = family_of(text)

        if is_default_anchored(text):
            report.default_anchored += 1
            if family not in covered and family not in flagged_families:
                flagged_families.add(family)
                report.violations.append(
                    Violation(
                        kind="non-discriminating",
                        where=where,
                        detail=(
                            f"every expected value in the {family} family is "
                            f"pinned at default config, so an implementation "
                            f"that hardcodes the default outputs passes every "
                            f"planned assertion. Add at least one case at a "
                            f"non-default value, per branch and per surface."
                        ),
                    )
                )

        if is_absence_only(text):
            report.absence_only += 1
            report.violations.append(
                Violation(
                    kind="absence-only-oracle",
                    where=where,
                    detail=(
                        "an input is supplied and every assertion is a "
                        "no-change assertion, which is equally true under an "
                        "implementation that ignores the input entirely. Add a "
                        "positive observation of the value taking effect."
                    ),
                )
            )

    return report
