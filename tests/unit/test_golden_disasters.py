"""The disaster museum, replayable (#2572).

Registry classes 3 and 4 (`docs/standards/0029-defect-class-registry.md`).

Two things need pinning and they are different. First, that the corpus
SURVIVES — every case green on main, which is what makes it a gate. Second,
that each case would actually go RED if its guard regressed: a corpus of
tautologies passes forever and protects nothing, and that is a harder
property to get right than the first.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = REPO_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import golden_disasters as cli  # noqa: E402

from assemblyzero.speedrun.golden_disasters import (  # noqa: E402
    CASES,
    DETERMINISTIC,
    LIVE,
    CaseResult,
    DisasterCase,
    fixture_digest,
    render_report,
    run_case,
    run_tier,
)


class TestTheCorpusSurvives:
    """The acceptance: every deterministic case green on main."""

    def test_every_deterministic_case_survives(self):
        results = run_tier(DETERMINISTIC, REPO_ROOT)
        assert results, "the deterministic tier registered no cases"
        regressed = [r for r in results if not r.passed]
        assert not regressed, "\n".join(
            f"{r.slug}: {r.detail}" for r in regressed
        )

    @pytest.mark.parametrize("slug", sorted(CASES))
    def test_every_case_has_its_fixtures_committed(self, slug):
        """A corpus pointing at live lineage decays: the scratch replay
        script this gathers opens a lineage dir that no longer exists, one
        day after it was written. Fixtures are committed for exactly that
        reason, and this asserts they are actually here."""
        case = CASES[slug]
        assert case.artifacts, f"{slug} declares no artifacts"
        for artifact in case.artifacts:
            path = case.path(REPO_ROOT, artifact)
            assert path.is_file(), f"missing committed fixture: {path}"
            assert path.stat().st_size > 0

    @pytest.mark.parametrize("slug", sorted(CASES))
    def test_every_case_records_its_provenance(self, slug):
        """A case whose kill cannot be traced is an assertion nobody can
        evaluate later."""
        case = CASES[slug]
        assert case.provenance.strip()
        assert case.guards.strip()
        assert "#" in case.guards, "guards must name the issue it protects"


class TestTheCasesAreNotTautologies:
    """Each case, shown to go RED when its guard is defeated.

    A corpus that cannot fail is worse than none: it reports green forever
    and is trusted for exactly as long as it takes for something to break
    unnoticed.
    """

    def test_the_fence_case_fails_when_the_range_vocabulary_is_defeated(
        self, monkeypatch
    ):
        """Defeat `named_line_ranges` -- the #2555 repair -- and the fence
        case must report the deadlock, not pass."""
        import assemblyzero.workflows.implementation_spec.message_addressability as ma

        monkeypatch.setattr(
            ma, "named_line_ranges", lambda issues: ()
        )
        monkeypatch.setattr(
            ma, "named_tokens", lambda feedback, issues=None: set()
        )
        result = run_case(CASES["fence-deadlock"], REPO_ROOT)
        assert result.passed is False
        assert "REGRESSION (#2555)" in result.detail

    def test_the_eliding_case_fails_when_a_test_definition_is_lost(
        self, tmp_path
    ):
        """Feed the case a revision with a test definition removed -- the
        exact shape #2559's conservation gate exists to refuse."""
        case = CASES["eliding-rewrite"]
        previous = case.read(REPO_ROOT, "draft.md")
        revision = case.read(REPO_ROOT, "revision.md")

        # Drop the first test definition from the revision.
        kept = []
        dropped = False
        for line in revision.splitlines():
            if not dropped and line.lstrip().startswith("def test_"):
                dropped = True
                continue
            kept.append(line)
        assert dropped, "the fixture holds no test definition to drop"

        staged = tmp_path / "tests" / "fixtures" / "golden_disasters"
        target = staged / case.slug
        target.mkdir(parents=True)
        (target / "draft.md").write_text(previous, encoding="utf-8")
        (target / "revision.md").write_text(
            "\n".join(kept), encoding="utf-8"
        )

        result = run_case(case, tmp_path)
        assert result.passed is False
        assert "REGRESSION (#2559)" in result.detail

    def test_a_missing_fixture_errors_rather_than_failing(self, tmp_path):
        """'The guard regressed' and 'the corpus is broken' are different
        findings and must never render identically."""
        result = run_case(CASES["fence-deadlock"], tmp_path)
        assert result.errored is True
        assert result.passed is False
        assert "fixture missing" in result.detail


class TestFixtureIntegrity:
    def test_a_digest_changes_when_a_fixture_changes(self, tmp_path):
        """The corpus's value depends on the fixture being what came out of
        the kill. An edit must be visible, not silent."""
        case = CASES["fence-deadlock"]
        staged = tmp_path / "tests" / "fixtures" / "golden_disasters"
        target = staged / case.slug
        target.mkdir(parents=True)

        original = case.read(REPO_ROOT, "draft.md")
        (target / "draft.md").write_text(original, encoding="utf-8")
        first = fixture_digest(case, tmp_path)

        (target / "draft.md").write_text(original + "\nedited\n", encoding="utf-8")
        assert fixture_digest(case, tmp_path) != first

    def test_the_digest_is_stable_for_identical_content(self):
        case = CASES["fence-deadlock"]
        assert fixture_digest(case, REPO_ROOT) == fixture_digest(
            case, REPO_ROOT
        )


class TestReporting:
    def test_regressed_and_errored_render_differently(self):
        results = [
            CaseResult("a", DETERMINISTIC, True, "survived"),
            CaseResult("b", DETERMINISTIC, False, "guard gone"),
            CaseResult("c", DETERMINISTIC, False, "no fixture", errored=True),
        ]
        text = render_report(results, DETERMINISTIC)
        assert "[ok] a" in text
        assert "[REGRESSED] b" in text
        assert "[ERROR] c" in text
        assert "1 survived, 1 regressed, 1 could not run, of 3 case(s)." in text

    def test_an_empty_tier_says_so(self):
        assert "No cases registered" in render_report([], LIVE)


class TestCli:
    def test_deterministic_tier_exits_zero_on_main(self, capsys):
        assert cli.main(["--tier", DETERMINISTIC]) == 0
        out = capsys.readouterr().out
        assert "survived" in out

    def test_the_empty_live_tier_is_not_reported_as_a_pass(self, capsys):
        """A tier with no cases measured nothing. Exiting 0 would let 'the
        live tier is green' be said about a tier that never ran."""
        assert cli.main(["--tier", LIVE]) == 1
        assert "not a pass" in capsys.readouterr().out

    def test_list_prints_provenance_and_digests(self, capsys):
        assert cli.main(["--list"]) == 0
        out = capsys.readouterr().out
        for slug in CASES:
            assert slug in out
        assert "provenance:" in out
        assert "guards:" in out


def test_every_registered_case_has_a_runner():
    """A case with no runner would silently never execute."""
    from assemblyzero.speedrun.golden_disasters import _RUNNERS

    assert set(_RUNNERS) == set(CASES), (
        f"runner/case mismatch: "
        f"cases without runners {sorted(set(CASES) - set(_RUNNERS))}, "
        f"runners without cases {sorted(set(_RUNNERS) - set(CASES))}"
    )


def test_a_case_declaring_an_unknown_tier_is_not_silently_skipped():
    """`run_tier` filters on tier, so a typo would drop a case from every
    tier and from every report, invisibly."""
    known = {DETERMINISTIC, LIVE}
    unknown = {
        case.slug: case.tier
        for case in CASES.values()
        if case.tier not in known
    }
    assert not unknown, f"cases with an unknown tier: {unknown}"


def test_disaster_case_paths_are_repo_relative():
    """The corpus must be readable from any checkout, so no case may carry
    an absolute path -- the failure that decayed the scratch replays."""
    for case in CASES.values():
        for artifact in case.artifacts:
            assert not Path(artifact).is_absolute()
        assert isinstance(case, DisasterCase)
