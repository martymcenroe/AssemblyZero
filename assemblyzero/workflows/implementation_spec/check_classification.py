"""Every completeness check, classified fact-verifier or proxy-heuristic (#2540).

Operator-ratified 2026-08-28: **a proxy metric never outranks an engaged judge
examining the same dimension with reasons.** Facts stay hard gates; proxies
demote to advisory whenever the adversarial review stage is engaged.

The week's evidence base is three deep, and each instance cost a full roll to
discover: `api_symbols_exist` on `str.isupper` (#2526), `change_instructions_
specific` on a fence-density off-by-one (#2539), and the same check's
no-target complaint (#2592). Fixing them one funeral at a time is the wrong
loop, so this is one deliberate pass over every check.

## Why a table and not scattered edits

#2539's demotion was an inline rewrite of one check's result inside the runner:
compute the check, notice it failed, build a replacement `CompletenessCheck`
with `passed=True` and an ADVISORY prefix. Correct, and invisible -- nothing
named the class, nothing stopped the next check from being demoted differently,
and a reader had to find the hack to know the rule existed. On the #2475 model
the classification is a reviewable artifact with a lint, so the sweep can be
re-run rather than re-remembered.

## The rule, and how a classification is decided

A check is a **fact-verifier** only if its failure is a fact about the
artifact: a cited symbol does not exist, a fence does not parse, a manifest row
is cited by no test. Those block, because the failure is true.

A check is a **proxy-heuristic** if its failure is a correlate: a count against
a threshold, a keyword within a window, a fence somewhere near a filename.
Those advise. The N5 adversarial reviewer judges the same dimension directly,
with reasons, every round, and a proxy adds no information it lacks.

**Proximity is the tell.** Three checks here pass on finding *something*
within N characters of *something else*. That answers "are these near each
other", never "is this an example OF that thing" -- and the drafter can satisfy
it without satisfying the intent, which is what makes it a correlate rather
than a fact.

## Conservative where it is arguable

Two entries are marked `flagged`: classified fact and left GATING, with the
tension recorded rather than resolved. Demoting a check on an agent's own
reading -- against an operator ruling, or across a mode boundary the operator
has not seen -- would be exactly the unilateral judgement this registry exists
to replace. A flag costs nothing and surfaces the question; a wrong demotion
removes a gate quietly.
"""

from __future__ import annotations

from dataclasses import dataclass

#: A check whose failure is a fact about the artifact. Blocks.
FACT = "fact-verifier"

#: A check whose failure is a correlate. Advises when review is engaged.
PROXY = "proxy-heuristic"


@dataclass(frozen=True)
class Classification:
    """One check's class, with the reading that decided it.

    `reads` is what the code actually looks at, not what the check is named
    after -- the sweep decides from the former, because several of these are
    named for the thing they wish they measured.
    """

    check: str
    kind: str
    reads: str
    reason: str
    #: Set when the classification is arguable and deliberately left gating.
    flagged: str = ""

    @property
    def gates(self) -> bool:
        return self.kind == FACT


CLASSIFICATIONS: dict[str, Classification] = {
    # ---------------------------------------------------------------- facts
    "api_symbols_exist": Classification(
        check="api_symbols_exist",
        kind=FACT,
        reads="calls in the spec against the gathered symbol table and the repo",
        reason=(
            "a symbol exists or it does not. #2526 was a defect in its symbol "
            "table -- `str.isupper` is real and the table did not know it -- "
            "not evidence that the question is a correlate. A wrong fact is "
            "fixed by fixing the fact."
        ),
    ),
    "python_fences_parse": Classification(
        check="python_fences_parse",
        kind=FACT,
        reads="ast.parse over every python-tagged fence",
        reason=(
            "the parser succeeds or raises. Reports under its own name since "
            "#2556 and is the precondition the symbol check depends on."
        ),
    ),
    "import_targets_exist": Classification(
        check="import_targets_exist",
        kind=FACT,
        reads=(
            "each imported module path on disk, cross-referenced against the "
            "spec's own Files Changed table for files it creates"
        ),
        reason=(
            "a module resolves or it does not. The cross-reference against "
            "the spec's own Files Changed table is what keeps it a fact rather "
            "than a false alarm on a module the spec is about to create (#842)."
        ),
    ),
    "pattern_references_valid": Classification(
        check="pattern_references_valid",
        kind=FACT,
        reads="each file:line pattern reference against real code in the repo",
        reason=(
            "a reference points at real code or it does not; a stale one sends "
            "the implementation agent to the wrong place."
        ),
    ),
    "manifest_traceability": Classification(
        check="manifest_traceability",
        kind=FACT,
        reads="manifest row ids against the source of each parsed test function",
        reason=(
            "an exact bookkeeping diff -- every row cited by exactly one test, "
            "every test citing a row. It abstains on fences it cannot parse "
            "(#2526's unknown-is-not-guilty) rather than guessing, which is a "
            "fact-verifier declining to state a fact it lacks."
        ),
    ),
    "error_paths_have_tests": Classification(
        check="error_paths_have_tests",
        kind=FACT,
        reads=(
            "`raise X` names in the spec's code fences against the exception "
            "names asserted in its test fences"
        ),
        reason=(
            "a set difference over names extracted from both halves of the "
            "same document. 'The spec raises ValueError and no test asserts "
            "ValueError' is a fact (#2333)."
        ),
    ),
    "spec_test_functions_have_assertions": Classification(
        check="spec_test_functions_have_assertions",
        kind=FACT,
        reads=(
            "Section 10's extracted test functions, assembled exactly as the "
            "scaffolder emits them, under `validate_test_structure`'s AST rule"
        ),
        reason=(
            "a function body is a lone pass/docstring or it carries an assert "
            "-- the same fact the implementation stage's scaffolder validator "
            "refuses on, asked one stage earlier with the same code (#2706)."
        ),
    ),
    "spec_test_fixtures_resolvable": Classification(
        check="spec_test_fixtures_resolvable",
        kind=FACT,
        reads=(
            "each test-function parameter against pytest's builtin fixtures, "
            "the block's own @pytest.fixture definitions, and the plugins the "
            "target repo's pyproject declares"
        ),
        reason=(
            "a parameter names a fixture one of those three routes provides or "
            "it does not; pytest errors at setup on the latter, which is the "
            "fact this check reports early (#2707)."
        ),
    ),
    "visual_baselines_not_self_referential": Classification(
        check="visual_baselines_not_self_referential",
        kind=FACT,
        reads=(
            "whether the spec adds or regenerates baseline images, and whether "
            "it carries the literal marker `baseline-independent`"
        ),
        reason=(
            "both halves are exact: a file list, and a literal string. #1902's "
            "failure -- a systematically wrong first render becoming its own "
            "reference -- is not a matter of degree."
        ),
    ),
    # ------------------------------------------- facts, flagged as arguable
    "functions_have_io_examples": Classification(
        check="functions_have_io_examples",
        kind=PROXY,
        reads=(
            "a +/-2000-character window around each function definition, for "
            "an I/O vocabulary word AND any concrete-looking value"
        ),
        reason=(
            "Operator-ruled a PROXY 2026-08-28 (#2620), superseding the "
            "earlier fact-verifier ruling on the #2590 work order. That "
            "ruling classified the check's INTENTION; this one classifies the "
            "implementation that actually runs, and the two disagree. A "
            "window plus a vocabulary plus any number or quoted string does "
            "not verify that the example is OF that function -- neighbouring "
            "definitions share the window, and #2302 documents the verdict "
            "moving on how often a name happened to be repeated. A false veto "
            "from a well-intentioned check is still the #2539 disease."
        ),
    ),
    "function_spec_sections_have_examples": Classification(
        check="function_spec_sections_have_examples",
        kind=FACT,
        reads=(
            "each `### 5.N `name()`` subsection of the spec's Function "
            "Specifications section, for an Input Example and an Output "
            "Example block INSIDE that subsection's own bounds"
        ),
        reason=(
            "the path back to a hard gate, named by #2620's ruling and built "
            "with it. Presence within a bounded region is a fact: the section "
            "either carries the block or it does not, no window is scanned, "
            "and no neighbour can satisfy it. Template 0701 defines the "
            "structure, and both preserved boostgauge specs follow it exactly "
            "-- #331's seven subsections carry seven Input Examples, #1's two "
            "carry two -- so the gate passes on real work rather than "
            "blocking it."
        ),
    ),
    "criteria_have_tests": Classification(
        check="criteria_have_tests",
        kind=FACT,
        reads=(
            "the REQ-N tag set in the LLD's pass-criteria table against the "
            "tag set cited by the spec's test functions"
        ),
        reason=(
            "an id-set difference: a criterion ID either has a test citing it "
            "or it does not (#2239). The sweep flagged this entry as "
            "mode-dependent, because a substring fallback ran whenever the "
            "criteria were not all tagged -- and the operator ruled 2026-08-28 "
            "(#2619) that the fallback be REMOVED rather than classified, "
            "since injection (#2607/#2611) carries criterion IDs byte-verbatim "
            "and the mangled-ID case it served is structurally gone. With one "
            "mode left, the class is no longer arguable: an untagged table now "
            "abstains and says so instead of guessing."
        ),
    ),
    # -------------------------------------------------------------- proxies
    "change_instructions_specific": Classification(
        check="change_instructions_specific",
        kind=PROXY,
        reads=(
            "fence count against `max(3, lines//50)` and indicator count "
            "against `max(5, lines//30)`"
        ),
        reason=(
            "a density ratio, and a self-defeating one: both thresholds derive "
            "from line count, so complying grows the spec and moves the demand "
            "with it -- observed live as 7-of-8 at 441 lines becoming 8-of-9 "
            "at 454, one or two rounds from approval on a spec the reviewer "
            "had certified for five consecutive rounds (#2539). It also parses "
            "nothing from its own message, so it cannot address its own "
            "complaint (#2592)."
        ),
    ),
    "modify_files_have_excerpts": Classification(
        check="modify_files_have_excerpts",
        kind=PROXY,
        reads=(
            "3000 characters after each Modify file's name, passing if the "
            "substring ``` appears anywhere in them"
        ),
        reason=(
            "any fence at all, about anything, within a fixed window. It "
            "measures proximity, never whether an excerpt of THAT file's "
            "current state is present -- and it passes on a fence that shows "
            "something else entirely."
        ),
    ),
    "data_structures_have_examples": Classification(
        check="data_structures_have_examples",
        kind=PROXY,
        reads=(
            "5000 characters after each structure name, for any of five loose "
            "patterns -- including any fenced block of 20 or more characters"
        ),
        reason=(
            "same proximity shape as the excerpts check and looser: a code "
            "fence anywhere in a 5000-character window satisfies it regardless "
            "of what it contains. Whether an example is OF the structure is "
            "the question, and this never asks it."
        ),
    ),
}


def classification_of(check_name: str) -> Classification | None:
    return CLASSIFICATIONS.get(check_name)


def is_proxy(check_name: str) -> bool:
    """True only for a check DECLARED a proxy.

    An unclassified check is never demoted. A name this table does not know is
    either new or renamed, and the honest response is to keep its authority and
    let the exhaustiveness lint fail -- silently demoting an unknown check
    would remove a gate as a side effect of forgetting to classify it.
    """
    entry = CLASSIFICATIONS.get(check_name)
    return entry is not None and entry.kind == PROXY


def advisory_details(details: str) -> str:
    """The demoted check's details, carrying its category with it.

    #2540 asks that a borderline check state its classification in its own
    output, so the next false alarm arrives already labelled instead of costing
    another investigation.
    """
    return (
        "ADVISORY (proxy-heuristic, not blocking -- #2540; the N5 adversarial "
        "reviewer judges this dimension directly, with reasons): " + details
    )
