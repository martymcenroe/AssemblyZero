"""str.isupper is not a hallucinated API, and unknown is not guilty (#2526).

Roll run-issue331-083839 died at the spec completeness cap — after passing the
lld stage AND the visual gate's first full operator loop — because
``api_symbols_exist`` flagged ``node.id.isupper()`` as a method "not found in
the target project's gathered symbols." ``isupper`` is a method on every
Python ``str``; the code was correct and idiomatic; the drafter was shown the
identical complaint three times and correctly declined to break working code;
the cap killed the run.

Three defects, three fixes, pinned here:

1.  The hand-curated allowlist held ``upper`` but not ``isupper``. The builtin
    surface is now DERIVED (``dir()`` over every builtin type), so it can
    never again lag the language by one method.
2.  A comprehension target was no binding at all — ``node`` in
    ``[... for node in ast.walk(tree)]`` had no provenance, fell into no
    category, and was judged against the target repo's symbols. Comprehension
    generators now record bindings exactly as ``for`` statements do, and
    type-unknowable binding forms (lambda parameters, bare ``except ... as``)
    are unresolved by construction: unknown is not guilty.
3.  The cap's halt message now distinguishes "the drafter kept failing to fix
    X" from "the drafter declined to change X" — an identical complaint
    surviving every revision is evidence of a false positive in the check,
    and the halt says so instead of blaming the spec.

What deliberately did NOT change: bare function parameters and free names
stay judged (#2391/#2399's carve-out — #1527's founding true positive,
``question.model_dump()`` on a plain dataclass, arrives exactly that way).
The guard tests at the bottom pin that boundary.
"""

from unittest.mock import patch

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    _BUILTIN_TYPE_METHODS,
    check_api_symbols_exist,
    detect_unknown_method_calls,
    validate_completeness,
)

#: A plausible small gathered surface; none of the methods below are in it.
SYMBOLS = ["AppConfig", "SessionState", "WindowsCollector", "load_config"]

#: The live run's killing fence, verbatim from the preserved draft
#: (boostgauge docs/lineage/active/331-implspec/.../018-spec-draft.md:483).
OBSERVED_SPEC = """# S

```python
import ast

def find_constants(tree):
    constants = [node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id.isupper()]
    return constants
```
"""


def _flag(body: str) -> dict:
    return detect_unknown_method_calls(body, set(SYMBOLS))


def _spec(body: str) -> str:
    return "# S\n\n```python\n" + body + "```\n"


class TestTheObservedKill:
    """The exact case the issue names: node.id.isupper() in an AST walk."""

    def test_the_observed_fence_flags_nothing(self):
        assert _flag(OBSERVED_SPEC) == {}

    def test_the_observed_fence_passes_the_check(self):
        result = check_api_symbols_exist(OBSERVED_SPEC, SYMBOLS)
        assert result["passed"] is True, result["details"]

    def test_isupper_never_flags_on_any_receiver(self):
        """The allowlist half alone closes it: even a bare-parameter receiver
        — which stays judged — cannot flag a builtin-type method."""
        assert "isupper" not in _flag(
            _spec("def f(name):\n    return name.isupper()\n")
        )


class TestTheBuiltinSurfaceIsDerived:
    def test_the_str_is_family_is_covered(self):
        for method in ("isupper", "islower", "isdigit", "isalpha",
                       "isidentifier", "casefold", "removeprefix"):
            assert method in _BUILTIN_TYPE_METHODS, method

    def test_the_other_builtin_types_are_covered(self):
        # int, bytes, set, BaseException — one method each, none in the
        # hand-curated list, all real Python.
        for method in ("bit_length", "to_bytes", "isdisjoint",
                       "with_traceback", "as_integer_ratio"):
            assert method in _BUILTIN_TYPE_METHODS, method

    def test_builtin_methods_clear_in_a_fence(self):
        flagged = _flag(_spec(
            "def f(name, n, chunk):\n"
            "    a = name.islower()\n"
            "    b = n.bit_length()\n"
            "    c = chunk.removeprefix('x')\n"
        ))
        assert flagged == {}

    def test_a_project_hallucination_is_not_a_builtin(self):
        """The derived surface must not swallow the check's whole purpose."""
        assert "model_dump" not in _BUILTIN_TYPE_METHODS
        assert "model_validate" not in _BUILTIN_TYPE_METHODS


class TestComprehensionTargetsAreBindings:
    def test_a_comprehension_target_inherits_its_iterables_owner(self):
        """`node` from `ast.walk(tree)` is stdlib's, so even a NON-builtin
        method on it is not the target repo's business."""
        assert _flag(_spec(
            "import ast\n"
            "names = [n.walk_away() for n in ast.walk(t)]\n"
        )) == {}

    def test_chained_generators_resolve_through_the_chain(self):
        assert _flag(_spec(
            "import ast\n"
            "out = [f.arg_names() for n in ast.walk(t) for f in n.fields()]\n"
        )) == {}

    def test_all_four_comprehension_forms_bind(self):
        assert _flag(_spec(
            "import ast\n"
            "a = {n.invent_a() for n in ast.walk(t)}\n"
            "b = {n.invent_b(): 1 for n in ast.walk(t)}\n"
            "c = list(n.invent_c() for n in ast.walk(t))\n"
        )) == {}


class TestOpaqueBindingsAbstain:
    """Unknown is not guilty: a receiver whose type is unknowable by
    construction cannot be called absent from anything."""

    def test_a_lambda_parameter_abstains(self):
        assert _flag(_spec(
            "result = sorted(xs, key=lambda g: g.rank_weight())\n"
        )) == {}

    def test_an_except_target_abstains(self):
        assert _flag(_spec(
            "try:\n"
            "    pass\n"
            "except ValueError as err:\n"
            "    err.render_hint()\n"
        )) == {}


class TestTheDeliberateBoundaryHolds:
    """What #2526 did NOT change: affirmatively-placeable receivers, bare
    parameters, and free names stay judged — #1527's founding true positive
    arrives as a bare parameter, and abstaining there would retire the check."""

    def test_the_founding_bare_parameter_case_still_flags(self):
        assert "model_dump" in _flag(_spec(
            "def apply(question):\n    return question.model_dump()\n"
        ))

    def test_a_constructor_bound_receiver_still_flags(self):
        assert "model_dump" in _flag(_spec(
            "g = SessionState()\ng.model_dump()\n"
        ))

    def test_a_comprehension_over_a_repo_rooted_source_stays_judged(self):
        """The comprehension fix routes ownership; it is not an exemption.
        A target bound from a chain rooted in a gathered symbol is the
        repo's business, and an invented method on it still flags."""
        flagged = _flag(_spec(
            "names = [c.invented_lookup() for c in AppConfig.instances()]\n"
        ))
        assert "invented_lookup" in flagged


class TestTheHaltSaysWhoDeclined:
    """Ask 3: 'kept failing to fix X' and 'the flagged content reached the
    check unchanged' are different facts, and the halt message states which
    one happened. (#2556 sharpened the claim: it holds only when no pinning
    reversion intervened — those cases live in
    test_completeness_pinning_deadlock.py.)"""

    def _state(self, iteration=3, shown=(), breakdown=()):
        return {
            "spec_draft": "# Spec\n\n" + ("body line\n" * 40),
            "files_to_modify": [],
            "pattern_references": [],
            "repo_root": "",
            "lld_content": "",
            "review_iteration": iteration,
            "max_iterations": 3,
            "checks_shown_to_drafter": list(shown),
            "prior_completeness_breakdown": [dict(e) for e in breakdown],
        }

    def _at_cap(self, details: str, make_breakdown):
        """Run once to DISCOVER what this minimal spec fails (mirroring
        test_halt_legibility), then again with everything marked tried and a
        history built by ``make_breakdown`` from the discovered failures."""
        with patch(
            "assemblyzero.workflows.implementation_spec.nodes."
            "validate_completeness.check_modify_files_have_excerpts",
            return_value={"check_name": "x", "passed": False, "details": details},
        ):
            first = validate_completeness(self._state())
            return validate_completeness(self._state(
                shown=first["checks_shown_to_drafter"],
                breakdown=make_breakdown(first["completeness_issues"]),
            ))

    def test_an_identical_complaint_with_no_reversions_reads_as_unchanged(self, capsys):
        out = self._at_cap(
            "Spec calls methods not found: `isupper`",
            # Every failing check drew this exact complaint on every prior
            # round — the live run's shape: identical code, identical flag.
            lambda failures: [
                {"iteration": i, "failures": list(failures)} for i in range(3)
            ],
        )
        capsys.readouterr()
        assert "IDENTICAL complaint" in out["error_message"]
        # #2556: observable facts only — no intent attribution ("declining",
        # "believes correct"), and the claim is conditioned on enforcement
        # having stayed out of the loop.
        assert "reached the check unchanged" in out["error_message"]
        assert "no pinning reversion intervened" in out["error_message"]
        assert "false positive" in out["error_message"]
        assert "declining" not in out["error_message"]
        assert "believes correct" not in out["error_message"]
        assert "survived a revision" not in out["error_message"]

    def test_a_changing_complaint_reads_as_kept_failing(self, capsys):
        out = self._at_cap(
            "missing excerpt for a.py",
            lambda failures: [
                {"iteration": 0, "failures": ["missing excerpt for b.py"]},
                {"iteration": 1, "failures": ["missing excerpt for c.py"]},
            ],
        )
        capsys.readouterr()
        assert "shown to the drafter and survived a revision" in out["error_message"]
        assert "IDENTICAL complaint" not in out["error_message"]

    def test_no_history_still_reads_as_tried(self, capsys):
        """The pre-#2526 shape — no breakdown in state — keeps the old
        sentence, so a first-failure-at-cap is not accused of declining."""
        out = self._at_cap("missing excerpt for a.py", lambda failures: [])
        capsys.readouterr()
        assert "shown to the drafter and survived a revision" in out["error_message"]
        assert "IDENTICAL complaint" not in out["error_message"]
