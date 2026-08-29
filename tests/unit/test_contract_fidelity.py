"""The contract-to-issue compression, audited against the contract itself.

boostgauge #331 shipped three defects through one ungated derivation: §Bezel's
ring never became a row (#375), S7's assertion could not falsify the step law
its own binding cites (#376), and anti-aliasing was engineered around three
times and bound nowhere (#377).

The contract excerpts below are VERBATIM from
`boostgauge/docs/design/0002-aesthetic-v1-stingray.md`, and the table is #331's
own. They are the evidence, not a paraphrase of it.

## What is asserted here, and what deliberately is not

The acceptance is written as "the pass names all three findings". Two of the
three are named mechanically and are asserted as such. The third is a judgement
and reaches a model, so what is asserted is that **the brief carries the
evidence for it** -- a reviewer cannot find what the brief does not contain --
plus the plumbing and the fail-closed path through `ScriptedProvider`.

What is NOT asserted is that a live model, given a correct brief, reaches the
right verdict. That is a claim about a model; pinning it to a fixture would be
a test that passes and tells nobody anything.
"""

from __future__ import annotations

import json

import pytest

from assemblyzero.core.llm_provider import LLMCallResult
from assemblyzero.workflows.requirements import contract_fidelity as cf
from assemblyzero.workflows.requirements.contract_fidelity import (
    FIDELITY_MARKER,
    build_brief,
    check_contract_fidelity_at_preflight,
    parse_contract,
    review_fidelity,
    rows_referencing,
    sections_in_play,
    signal_assertions_that_cannot_falsify,
    signal_sections_without_rows,
    signal_unbound_presuppositions,
)

# ---------------------------------------------------------------------------
# The contract, verbatim
# ---------------------------------------------------------------------------

CONTRACT = """\
# 0002 — v1 Aesthetic: Stingray Skin

## The numeric render contract (ruling #265, 2026-08-11)

**Every visual acceptance criterion is computed from this section.** The prose
subsections below describe intent; these tables carry the values.

Where it gave adjectives ("candy-apple red"), the same drafter wrote
`assert isinstance(img, Image.Image)`. Adjectives are not a specification.

### Palette

| Element | Name | RGB | Hex |
|---|---|---|---|
| Dial face | matte black | (10, 10, 12) | `#0A0A0C` |
| Tick marks, numerals, wordmark | white | (255, 255, 255) | `#FFFFFF` |
| Redline band | crimson | (170, 15, 25) | `#AA0F19` |

**Separation is a property of this table (ruling #267):** no two entries are
closer than **85** in Euclidean RGB distance — the tightest pair is 10-minute
orange against all-time coral, at ~88 — so anti-aliasing cannot flip a
classification.

### Chrome environment strip (ruling 2026-08-15, #328)

Chrome is a mirror, and a mirror needs a world to reflect. The 0.485 → 0.500
transition is the horizon and MUST remain a step, never a ramp — the hard split
is what makes rendered metal read as metal; a smoothed version reads as plastic
(the 2026-08-15 render review's grey-ramp failure is the documented case).

| t | RGB |
|---|---|
| 0.00 | (255, 255, 255) |
| 0.485 | (255, 255, 255) |
| 0.500 | (18, 19, 22) |
| 1.00 | (255, 252, 244) |

### How a colour is asserted

A sampled pixel is classified by **nearest palette entry**. Sample away from
edges (at least 2 px inside a feature) so anti-aliasing does not decide the
result.

## Decisions, codified

### Bezel

- **Material rendering:** Polished chrome. NOT brushed, NOT matte. Generated
  from the reflected environment defined in §Chrome environment strip (ruling
  #328) — a mirror with a hard horizon in it, never a grey ramp.
- **Width:** Substantial. Visibly weighty — the bezel is real metal, not a thin
  frame. As a fraction of total housing width, the bezel reads roughly 12–15%
  of the housing on each side.
- **Highlights:** Two soft specular hot spots, conventionally at top-left and
  bottom-right of the curved bezel surface.
- **Bezel-to-dial transition:** Slight inner shadow where the bezel rolls
  inward and meets the recessed dial face. The dial sits below the bezel plane
  — not flush.

### Face

- **Color:** One flat fill of the palette's matte black `#0A0A0C`, uniform
  across the entire dial face. Black as night (operator ruling 2026-08-15,
  #325).
- **Texture:** Smooth. No grain, no print pattern, no fake weave.

### Tick marks

- **Color:** Pure white.
- **Major marks:** Bold. Length approximately 10% of dial radius. 11 total.

### Main needle

- **Color:** Luminescent candy-apple red.
- **Position at rest:** Pointing to 0.

## Out of scope

Round-housing variants live in future skins per #45.
"""

TITLE_331 = (
    "feat: static face renderer — bezel, chrome housing, dial, ticks, "
    "numerals, wordmark, screws — baked once, cached"
)

BODY_331 = """\
Render the complete static face of the Stingray gauge — everything that never
moves — as one cached `PIL.Image`. Per the render-architecture ruling (#329)
this is the baked half of the renderer: bezel, chrome housing, dial face,
redline band, tick marks, numerals, wordmark, and screws. No needles and NO
pivot cap -- the cap draws on top of them and belongs to #332.

## Decision table — static elements and their binding values

| ID | Element | Binding value (quoted from the render contract) | Assertion method |
|---|---|---|---|
| S1 | Dial face | flat `#0A0A0C`, radius R = 0.40 × size (#325) | classification at 3 interior points |
| S2 | Redline band | `#AA0F19` crimson, inner 0.88 R to outer 1.00 R | classification at radius 0.94 R |
| S3 | Major ticks | `#FFFFFF`, 11 total, length 0.10 R, width 0.025 R | stroke predicate at each tick's midpoint: channel mean >= 100 |
| S7 | Chrome housing | square, chamfer radius 0.13 × size, environment-strip generation per #328's stops table | the #328 predicate: >=3 achromatic samples (max-min <= 14, mean 16-248) spanning the horizon, >=1 dark (mean < 100), >=1 bright (mean > 200) |
| S9 | Bezel seat | dial sits below the bezel plane — the slight inner shadow on the annulus containing 1.01 R (contract §Bezel-to-dial transition) | sample at 1.01 R is darker than chrome at 1.10 R |
"""

#: The control: S7's assertion carries the two stops that bracket the horizon,
#: so it can falsify a ramp. Everything else is byte-identical.
BODY_CONTROL = BODY_331.replace(
    "the #328 predicate: >=3 achromatic samples (max-min <= 14, mean 16-248) "
    "spanning the horizon, >=1 dark (mean < 100), >=1 bright (mean > 200)",
    "samples at t=0.485 and t=0.500 differ by >= 200 in channel mean, "
    "reproducing (255, 255, 255) above the horizon and (18, 19, 22) below",
)


@pytest.fixture
def contract_repo(tmp_path):
    """A repo that declares this contract for issue 331, as boostgauge does."""
    design = tmp_path / "docs" / "design"
    design.mkdir(parents=True)
    (design / "0002-aesthetic.md").write_text(CONTRACT, encoding="utf-8")
    (design / "visual-gate.json").write_text(
        json.dumps({
            "issues": [331, 332],
            "renderer_cmd": ["true"],
            "contract": "docs/design/0002-aesthetic.md",
            "separation_floor": 85,
        }),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def brief(contract_repo):
    return build_brief(contract_repo, 331, TITLE_331, BODY_331)


def _rows(body):
    from assemblyzero.workflows.implementation_spec.assertion_manifest import (
        is_criteria_table,
    )
    from assemblyzero.workflows.requirements.form_check import parse_tables
    return [t for t in parse_tables(body) if is_criteria_table(t)][0].rows


# ---------------------------------------------------------------------------
# Shape 3 -- the fact-verifier
# ---------------------------------------------------------------------------


class TestTheUnboundPresupposition:
    """#377: every tolerance is engineered around it and no table binds it."""

    def test_it_names_anti_aliasing(self):
        sections = parse_contract(CONTRACT)
        signals = signal_unbound_presuppositions(
            CONTRACT, sections, _rows(BODY_331)
        )
        assert [s.where for s in signals] == ["anti aliasing"]

    def test_it_names_nothing_else_on_the_whole_contract(self):
        """The precision claim, asserted rather than hoped for."""
        sections = parse_contract(CONTRACT)
        signals = signal_unbound_presuppositions(
            CONTRACT, sections, _rows(BODY_331)
        )
        assert len(signals) == 1

    def test_it_counts_every_site(self):
        sections = parse_contract(CONTRACT)
        signal = signal_unbound_presuppositions(
            CONTRACT, sections, _rows(BODY_331)
        )[0]
        assert "2 time(s)" in signal.detail
        assert signal.mechanical

    def test_a_bound_property_is_not_reported(self):
        """Binding it in a row is what makes the finding go away."""
        body = BODY_331.replace(
            "| S9 | Bezel seat |",
            "| S8 | Anti-aliasing | supersample 4x, LANCZOS downscale | "
            "a 1-px transect across a tick edge has an intermediate luminance |\n"
            "| S9 | Bezel seat |",
        )
        sections = parse_contract(CONTRACT)
        assert signal_unbound_presuppositions(CONTRACT, sections, _rows(body)) == []


# ---------------------------------------------------------------------------
# Shape 2 -- the exact precursor
# ---------------------------------------------------------------------------


class TestTheAssertionThatCannotFalsify:
    """#376: S7 tests existence of contrast, which any ramp satisfies."""

    def test_it_names_s7(self, contract_repo):
        sections = parse_contract(CONTRACT)
        chosen = sections_in_play(TITLE_331, BODY_331, sections)
        table = [
            t for t in __import__(
                "assemblyzero.workflows.requirements.form_check",
                fromlist=["parse_tables"],
            ).parse_tables(BODY_331)
            if len(t.header) >= 4
        ][0]
        signals = signal_assertions_that_cannot_falsify(chosen, table)
        assert [s.where.split(" -> ")[0] for s in signals] == ["row S7"]

    def test_it_quotes_the_law_the_section_states(self, brief):
        signal = next(
            s for s in brief.signals if s.shape == "assertion-cannot-falsify"
        )
        assert "MUST remain a step, never a ramp" in signal.detail
        assert signal.mechanical

    def test_the_control_passes_clean(self, contract_repo):
        """An assertion carrying its binding's discriminating values."""
        control = build_brief(contract_repo, 331, TITLE_331, BODY_CONTROL)
        assert [
            s for s in control.signals if s.shape == "assertion-cannot-falsify"
        ] == []

    def test_a_ruling_maps_to_every_section_that_carries_it(self):
        """The bug that silenced this signal entirely, kept as a test.

        #328 is carried by §Chrome environment strip AND §Bezel. A dict keyed
        on the ruling resolved to whichever came last -- §Bezel, which has no
        table -- and the probe returned zero findings on the one row this
        exists to name.
        """
        sections = parse_contract(CONTRACT)
        carrying = [s.name for s in sections if "328" in s.rulings]
        assert len(carrying) > 1
        assert any("Chrome environment strip" in name for name in carrying)
        assert any(name == "Bezel" for name in carrying)


# ---------------------------------------------------------------------------
# Shape 1 -- the ledger, and the fact underneath it
# ---------------------------------------------------------------------------


class TestTheBindingWithNoRow:
    """#375: §Bezel binds four things and the table carried one."""

    def test_the_ledger_shows_bezels_three_unbound_sub_bindings(self, brief):
        bezel = {
            binding: named
            for section, binding, named in brief.ledger
            if section == "Bezel"
        }
        assert bezel == {
            "Material rendering": [],
            "Width": [],
            "Highlights": [],
            "Bezel-to-dial transition": ["S9"],
        }

    def test_the_row_text_is_scoped_to_the_referencing_rows(self, brief):
        """Unscoped, S3's `width 0.025 R` marked §Bezel / Width as covered.

        Two thirds of boostgauge #375 vanished that way, silently, marked
        covered by a row about ticks.
        """
        rows = _rows(BODY_331)
        assert rows_referencing(
            next(s for s in parse_contract(CONTRACT) if s.name == "Bezel"), rows
        ) == ["S9"]
        assert any("width" in cell.lower() for row in rows for cell in row)

    def test_a_section_no_row_reaches_at_all_is_a_hard_finding(self):
        """The half that does close mechanically."""
        sections = [s for s in parse_contract(CONTRACT) if s.name == "Bezel"]
        signals = signal_sections_without_rows(sections, [["S1", "Dial face", "", ""]])
        assert [s.where for s in signals] == ["§Bezel"]
        assert signals[0].mechanical

    def test_a_referenced_section_is_not_a_hard_finding(self, brief):
        """S9 reaches §Bezel, so whether it DISCHARGES it is a judgement."""
        assert [s for s in brief.signals if s.shape == "section-no-row"] == []


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


class TestSectionsInPlay:
    def test_the_bezel_section_is_in_play(self):
        sections = parse_contract(CONTRACT)
        chosen = [s.name for s in sections_in_play(TITLE_331, BODY_331, sections)]
        assert "Bezel" in chosen

    def test_the_scope_element_alone_loads_it(self):
        """The title says "bezel"; the table need not cite the section at all.

        #331 happens to reach §Bezel a second way -- S9's cell carries
        `§Bezel-to-dial transition`, whose name starts with the section's. With
        every `§` citation stripped, the scope element is the only route left,
        and it is the one that survived nineteen ruled conflicts.
        """
        body = BODY_331.replace("(contract §Bezel-to-dial transition)", "")
        assert "§" not in body
        chosen = [
            s.name for s in sections_in_play(TITLE_331, body, parse_contract(CONTRACT))
        ]
        assert "Bezel" in chosen

    def test_the_value_carrying_subsections_are_always_in_play(self):
        chosen = [
            s.name for s in sections_in_play(TITLE_331, BODY_331, parse_contract(CONTRACT))
        ]
        assert "Palette" in chosen
        assert any("Chrome environment strip" in name for name in chosen)

    def test_a_declared_exclusion_drops_its_section(self):
        """#331 excludes needles; auditing it against §Main needle would be a
        finding about work the issue said it was not doing."""
        chosen = [
            s.name for s in sections_in_play(TITLE_331, BODY_331, parse_contract(CONTRACT))
        ]
        assert "Main needle" not in chosen

    def test_irrelevant_sections_stay_out(self):
        chosen = [
            s.name for s in sections_in_play(TITLE_331, BODY_331, parse_contract(CONTRACT))
        ]
        assert "Out of scope" not in chosen


# ---------------------------------------------------------------------------
# The brief
# ---------------------------------------------------------------------------


class TestTheBriefCarriesTheEvidence:
    """A reviewer cannot find what the brief does not contain."""

    def test_it_resolves_the_contract_the_repo_declares(self, brief):
        assert brief.ready
        assert brief.contract_path == "docs/design/0002-aesthetic.md"

    def test_it_quotes_bezels_four_sub_bindings_verbatim(self, brief):
        prompt = brief.as_prompt()
        assert "12–15%" in prompt
        assert "Two soft specular hot spots" in prompt
        assert "Polished chrome. NOT brushed, NOT matte." in prompt

    def test_it_quotes_the_step_law_with_both_bracketing_stops(self, brief):
        prompt = brief.as_prompt()
        assert "MUST remain a step, never a ramp" in prompt
        assert "| 0.485 | (255, 255, 255) |" in prompt
        assert "| 0.500 | (18, 19, 22) |" in prompt

    def test_it_carries_every_anti_aliasing_site(self, brief):
        prompt = brief.as_prompt()
        assert "so anti-aliasing cannot flip a classification" in prompt
        assert "so anti-aliasing does not decide the\nresult" in prompt

    def test_it_carries_the_issues_own_table(self, brief):
        prompt = brief.as_prompt()
        assert "| S7 | Chrome housing |" in prompt
        assert "| S9 | Bezel seat |" in prompt

    def test_the_ledger_caption_refuses_to_be_read_as_a_verdict(self, brief):
        assert "Evidence, not a verdict" in brief.as_prompt()

    def test_a_repo_declaring_no_contract_is_not_checked(self, tmp_path):
        result = build_brief(tmp_path, 331, TITLE_331, BODY_331)
        assert not result.ready
        assert "declares no binding contract" in result.error
        assert "NOT CHECKED" in result.disclosure()

    def test_an_issue_outside_the_declaration_is_not_checked(self, contract_repo):
        result = build_brief(contract_repo, 999, TITLE_331, BODY_331)
        assert not result.ready
        assert "NOT CHECKED" in result.disclosure()

    def test_an_issue_with_no_criteria_table_is_not_checked(self, contract_repo):
        result = build_brief(contract_repo, 331, TITLE_331, "Just prose.\n")
        assert not result.ready
        assert "no criteria table" in result.disclosure()


# ---------------------------------------------------------------------------
# The review, through the scripted transport
# ---------------------------------------------------------------------------


def _provider(monkeypatch, result):
    class _P:
        def invoke(self, **_kwargs):
            return result
    monkeypatch.setattr(cf, "get_provider", lambda *_a, **_k: _P(), raising=False)
    import assemblyzero.core.llm_provider as llm
    monkeypatch.setattr(llm, "get_provider", lambda *_a, **_k: _P())


def _result(success, response, error=None):
    return LLMCallResult(
        success=success, response=response, raw_response=response,
        error_message=error, provider="fake", model_used="fake-model",
        duration_ms=1, attempts=1,
    )


def _ok(payload):
    return _result(True, json.dumps(payload))


class TestTheReviewIsFailClosed:
    def test_a_verdict_with_findings_is_reported(self, brief, monkeypatch):
        _provider(monkeypatch, _ok({"findings": [
            {"shape": "binding-no-row", "where": "§Bezel / Width",
             "contract_quote": "roughly 12–15% of the housing on each side",
             "why": "no row binds the ring's radial extent"},
        ]}))
        review = review_fidelity(brief)
        assert review.reached
        assert not review.ok
        assert any(FIDELITY_MARKER in line for line in review.lines())

    def test_an_empty_findings_list_is_a_real_answer(self, brief, monkeypatch):
        _provider(monkeypatch, _ok({"findings": []}))
        review = review_fidelity(brief)
        assert review.reached
        assert review.ok

    def test_a_provider_failure_is_not_a_clean_bill(self, brief, monkeypatch):
        _provider(monkeypatch, _result(False, None, error="provider storm"))
        review = review_fidelity(brief)
        assert not review.reached
        assert not review.ok
        assert "NOT REACHED" in "\n".join(review.lines())
        assert "provider storm" in "\n".join(review.lines())

    def test_unparseable_json_is_not_a_clean_bill(self, brief, monkeypatch):
        _provider(monkeypatch, _result(True, "not json"))
        review = review_fidelity(brief)
        assert not review.reached
        assert "NOT REACHED" in "\n".join(review.lines())

    def test_a_missing_findings_key_is_not_a_clean_bill(self, brief, monkeypatch):
        _provider(monkeypatch, _ok({"verdict": "fine"}))
        review = review_fidelity(brief)
        assert not review.reached

    def test_an_unassembled_brief_never_reaches_the_model(self, tmp_path):
        review = review_fidelity(build_brief(tmp_path, 331, TITLE_331, BODY_331))
        assert not review.reached
        assert "declares no binding contract" in review.reason

    def test_the_signals_print_even_when_the_reviewer_finds_nothing(
        self, brief, monkeypatch
    ):
        """The mechanical facts do not depend on the model's verdict."""
        _provider(monkeypatch, _ok({"findings": []}))
        text = "\n".join(review_fidelity(brief).lines())
        assert "anti aliasing" in text
        assert "row S7" in text


# ---------------------------------------------------------------------------
# At the seam it runs at
# ---------------------------------------------------------------------------


def _fetch(title, body):
    def fetch(_repo_root, _issue):
        return (title, body)
    return fetch


class TestItRunsAtLauncherPreflight:
    def test_it_never_refuses(self, contract_repo, monkeypatch):
        _provider(monkeypatch, _ok({"findings": []}))
        _text, refuse = check_contract_fidelity_at_preflight(
            contract_repo, [331], _fetch(TITLE_331, BODY_331)
        )
        assert refuse is False

    def test_a_repo_with_no_contract_spends_nothing(self, tmp_path, monkeypatch):
        def _boom(*_a, **_k):
            raise AssertionError("no model call may happen for such a repo")
        monkeypatch.setattr(cf, "review_fidelity", _boom)
        text, refuse = check_contract_fidelity_at_preflight(
            tmp_path, [331], _fetch(TITLE_331, BODY_331)
        )
        assert refuse is False
        assert "declares no binding contract" in text

    def test_the_findings_reach_the_operators_console(
        self, contract_repo, monkeypatch
    ):
        _provider(monkeypatch, _ok({"findings": [
            {"shape": "unbound-presupposition", "where": "anti-aliasing",
             "contract_quote": "so anti-aliasing cannot flip a classification",
             "why": "presupposed three times, bound nowhere"},
        ]}))
        text, _ = check_contract_fidelity_at_preflight(
            contract_repo, [331], _fetch(TITLE_331, BODY_331)
        )
        assert FIDELITY_MARKER in text
        assert "anti-aliasing" in text

    def test_a_read_failure_is_reported_not_swallowed(self, contract_repo):
        def fetch(_r, _i):
            raise RuntimeError("no such issue")
        text, refuse = check_contract_fidelity_at_preflight(
            contract_repo, [331], fetch
        )
        assert "could not be read" in text
        assert refuse is False
