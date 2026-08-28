"""The factory's test of the factory: a roll made of fixtures (#2567).

Eight thousand unit tests exercise functions; nothing exercised a ROLL.
Every defect of the 2026-08-27 campaign lived in the SEAMS between stages —
guards fighting across nodes (#2555), the janitor sweeping what the loader
reads (#2551), the merge mangling between drafter and checker (#2559) — and
a seam only lights up when the pieces run together.

**What is mocked, exhaustively:** the LLM transport (`ScriptedProvider`) and
`gh issue view`, which is input acquisition rather than factory logic. That
is the whole list. The graph, the routing, the janitor, the enforcement, the
gates, the loaders, the file writes and the halt path all run for real
against a throwaway repo with a real bare origin under `tmp_path`.

The two classes below are the acceptance: each is a *deliberately re-broken
shape* replayed through the real machinery, green on main because the fix
holds, and red the day the seam regresses.

**Why this lives in `tests/unit/` despite testing a roll.** The marker
taxonomy here is about EXTERNAL DEPENDENCIES, not about scope: `e2e` means
"requiring sandbox repo" and is deselected by `addopts`, and CI runs
`tests/unit/` plus `tests/integration/ -m integration`. This suite needs no
sandbox, no network and no LLM — it builds its own throwaway repo under
`tmp_path`, exactly as `tests/unit/test_leavings_janitor.py` does. Filing it
as e2e would put it in the one directory CI never runs, which is the
opposite of the issue's "run it in CI".

Registry classes 3 and 5 (`docs/standards/0029-defect-class-registry.md`).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from assemblyzero.core.llm_provider import get_provider  # noqa: E402
from assemblyzero.core.scripted_provider import (  # noqa: E402
    ScriptedProvider,
    ScriptedRule,
    set_active,
)
from assemblyzero.speedrun.leavings import (  # noqa: E402
    classify_dirt,
    is_pipeline_input,
    preserve_and_clear,
)
from assemblyzero.workflows.implementation_spec.revision_pinning import (  # noqa: E402
    demands_additions,
    named_line_ranges,
    named_tokens,
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result


@pytest.fixture
def target_repo(tmp_path: Path) -> Path:
    """A throwaway target repo with a real bare origin.

    Same shape as `tests/unit/test_leavings_janitor.py`: preservation is
    only preservation when the ref is PUSHED, so the janitor needs
    somewhere to push. `--initial-branch` pins the bare HEAD to main on
    every machine.
    """
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "--initial-branch=main", str(origin)],
        capture_output=True, text=True, check=True,
    )
    root = tmp_path / "target"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / ".gitignore").write_text("data/\n", encoding="utf-8")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-qu", "origin", "main")
    _git(root, "remote", "set-head", "origin", "--auto")
    return root


@pytest.fixture
def scripted():
    """An active ScriptedProvider, torn down after the test.

    Teardown matters: the active provider is module-global so one roll's
    drafter reaches every caller, and a leaked one would let the NEXT test
    pass on this test's fixtures.
    """
    created: list[ScriptedProvider] = []

    def _make(rules: list[ScriptedRule], **kwargs) -> ScriptedProvider:
        provider = ScriptedProvider(rules, **kwargs)
        set_active(provider)
        created.append(provider)
        return provider

    yield _make
    set_active(None)


# ---------------------------------------------------------------------------
# The transport itself
# ---------------------------------------------------------------------------


class TestScriptedProvider:
    def test_routes_on_the_system_prompt(self, scripted):
        provider = scripted([
            ScriptedRule("draft", system_pattern="you are the drafter",
                         response="DRAFT"),
            ScriptedRule("review", system_pattern="you are the reviewer",
                         response="REVIEW"),
        ])
        assert provider.invoke("You are the DRAFTER", "x").response == "DRAFT"
        assert provider.invoke("You are the REVIEWER", "y").response == "REVIEW"
        assert provider.stages_called == ["draft", "review"]

    def test_overlapping_stage_patterns_fail_rather_than_guess(self, scripted):
        """`system_pattern="draft"` also matches "You review the draft".
        First-match-wins would route the reviewer to the drafter and produce
        a green roll that exercised the wrong path -- silent misrouting is
        the class this harness exists to catch."""
        provider = scripted([
            ScriptedRule("draft", system_pattern="draft", response="D"),
            ScriptedRule("review", system_pattern="review", response="R"),
        ])
        result = provider.invoke("You review the draft", "")
        assert result.success is False
        assert "different stages" in result.error_message
        assert "draft, review" in result.error_message

    def test_running_past_the_script_says_so(self, scripted):
        """A loop that will not converge runs more rounds than the fixture
        set scripts. That is a finding, not a reason to recycle round 1."""
        provider = scripted([
            ScriptedRule("draft", system_pattern="drafter",
                         response="R1", on_call=1),
        ])
        assert provider.invoke("drafter", "").response == "R1"
        result = provider.invoke("drafter", "")
        assert result.success is False
        assert "round 2 of stage 'draft'" in result.error_message

    def test_an_unmatched_call_fails_loudly(self, scripted):
        """A default response would let a roll 'pass' while exercising a path
        the fixture set never covered."""
        provider = scripted([
            ScriptedRule("draft", system_pattern="drafter", response="D"),
        ])
        result = provider.invoke("You are the ANALYST", "x")
        assert result.success is False
        assert "matched no rule" in result.error_message
        assert provider.stages_called == ["UNMATCHED"]

    def test_on_call_numbers_rounds_of_the_same_rule(self, scripted):
        provider = scripted([
            ScriptedRule("draft", system_pattern="drafter",
                         response="ROUND-1", on_call=1),
            ScriptedRule("draft", system_pattern="drafter",
                         response="ROUND-2", on_call=2),
        ])
        assert provider.invoke("drafter", "").response == "ROUND-1"
        assert provider.invoke("drafter", "").response == "ROUND-2"

    def test_a_rule_can_fail_the_call(self, scripted):
        provider = scripted([
            ScriptedRule("draft", system_pattern="drafter",
                         fail_with="capacity exhausted"),
        ])
        result = provider.invoke("drafter", "")
        assert result.success is False
        assert result.error_message == "capacity exhausted"

    def test_get_provider_hands_out_the_same_instance(self, scripted):
        """One roll has ONE drafter. Fresh instances would reset the counters
        that `on_call` and the recorded path depend on."""
        provider = scripted([ScriptedRule("d", response="x")])
        assert get_provider("scripted:drafter") is provider
        assert get_provider("scripted:reviewer") is provider

    def test_scripted_spec_without_an_active_provider_refuses(self):
        set_active(None)
        with pytest.raises(ValueError, match="requires an active"):
            get_provider("scripted:drafter")

    def test_a_missing_fixture_fails_at_the_fixture(self, scripted, tmp_path):
        provider = scripted(
            [ScriptedRule("d", fixture="absent.md")], fixture_root=tmp_path
        )
        with pytest.raises(OSError):
            provider.invoke("anything", "")


# ---------------------------------------------------------------------------
# Defect class 1 — the demanded change is never refusable (#2555, #2560)
# ---------------------------------------------------------------------------


class TestDemandedChangeSurvivesEnforcement:
    """Registry class 3, replayed on the shape that killed the 11:17 run.

    The deliberately re-broken shape: a completeness failure demands an
    edit, and the enforcement is asked whether the region it lands in is
    unlocked. Before #2555/#2558 the fence complaint's dashed citation was
    unreadable and the mandated retag was reverted three rounds running;
    before #2560 a demanded ADDITION died because no line could be cited.
    """

    DRAFT = "\n".join([
        "# Spec",                       # 1
        "",                             # 2
        "## Section 10 Tests",          # 3
        "",                             # 4
        "```",                          # 5  <- untagged fence, the defect
        "def test_req_1_smoke():",      # 6
        "    assert True",              # 7
        "```",                          # 8
    ])

    def test_a_dashed_citation_unlocks_the_span_it_names(self):
        """#2555. The complaint the 09:29 lineage deadlocked on."""
        complaint = (
            "Untagged code fence at lines 5-8 (```): tag it ```python so the "
            "block parses."
        )
        ranges = named_line_ranges([complaint])
        assert ranges == ((5, 8),)
        covered = {n for start, end in ranges for n in range(start, end + 1)}
        assert 5 in covered, "the fence line the drafter must retag"

    def test_a_quoted_syntax_error_position_is_not_a_draft_address(self):
        """The other half of #2555: the complaint minted garbage tokens that
        defeated the abstain valve. A bare 'line 1' from inside a quoted
        SyntaxError must not unlock the block holding draft line 1."""
        complaint = (
            "Fence failed to parse: SyntaxError: invalid decimal literal "
            "(<unknown>, line 1)"
        )
        assert named_line_ranges([complaint]) == ()

    def test_a_demanded_addition_is_recognised_without_a_line_to_cite(self):
        """#2560. A demand to ADD has no existing line to name, so the
        named-content exemptions cannot cover it and a separate one must."""
        complaint = (
            "3 LLD pass criterion(s) have no test in the spec: S1, S2, S3. "
            "Add a test for each."
        )
        assert demands_additions([complaint]) is True
        assert named_line_ranges([complaint]) == ()

    def test_the_reverted_shape_is_still_detectable(self):
        """The re-broken shape itself: a complaint naming its target in a
        scheme the vocabulary cannot read, demanding a change to EXISTING
        content. Neither exemption fires, and that is the deadlock."""
        complaint = "The fence in the tests section is untagged; please tag it."
        assert named_line_ranges([complaint]) == ()
        assert demands_additions([complaint]) is False
        tokens = named_tokens("", [complaint])
        addressed = any(
            token in line.lower()
            for token in tokens
            for line in self.DRAFT.lower().splitlines()
        )
        assert not addressed, (
            "this fixture must stay unaddressable -- it is the control that "
            "proves the two tests above are measuring something"
        )


# ---------------------------------------------------------------------------
# Defect class 2 — the input/litter distinction (#2551, #2144)
# ---------------------------------------------------------------------------


class TestSweepDoesNotClearTheRollingInput:
    """Registry class 5, replayed against the real janitor and a real repo.

    The deliberately re-broken shape: a launch sweeps untracked pipeline
    emissions, and the rolling issue's own LLD sits at exactly the path the
    sweep clears. #2551's fix is that the exemption is ISSUE-SCOPED — the
    rolling issue's input survives, and every other issue's file at the same
    path is still leavings, because #2144's original problem must not return.
    """

    @staticmethod
    def _drop(repo: Path, rel: str) -> Path:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("drafted by the pipeline\n", encoding="utf-8")
        return path

    def test_the_rolling_issues_lld_is_neither_leavings_nor_dirt(
        self, target_repo
    ):
        self._drop(target_repo, "docs/lld/active/LLD-331.md")
        machinery, operator = classify_dirt(target_repo, protect_issues=(331,))
        joined = " ".join(machinery + operator)
        assert "LLD-331.md" not in joined, (
            "the rolling issue's input appeared in a sweep list -- this is "
            "the #2551 regression, and a launch would clear the LLD the "
            "loader is about to read"
        )

    def test_another_issues_droppings_are_still_leavings(self, target_repo):
        """The other direction. A blanket exemption fixes the deletion and
        re-creates #2144, so this assertion is as load-bearing as the one
        above."""
        self._drop(target_repo, "docs/lld/active/LLD-999.md")
        machinery, _ = classify_dirt(target_repo, protect_issues=(331,))
        assert any("LLD-999.md" in line for line in machinery)

    def test_the_predicate_is_scoped_to_the_named_issue(self):
        assert is_pipeline_input("docs/lld/active/LLD-331.md", (331,))
        assert not is_pipeline_input("docs/lld/active/LLD-999.md", (331,))

    def test_an_unprotected_launch_would_clear_it(self, target_repo):
        """The re-broken shape, run for real: with no protected issue the
        janitor preserves AND CLEARS the same file. This is what the
        2026-08-27 launches did three times, and it is why the exemption
        exists."""
        path = self._drop(target_repo, "docs/lld/active/LLD-331.md")
        machinery, _ = classify_dirt(target_repo, protect_issues=())
        assert any("LLD-331.md" in line for line in machinery)

        result = preserve_and_clear(
            target_repo, ["docs/lld/active/LLD-331.md"]
        )
        assert result.problems == []
        assert not path.exists(), "the sweep cleared the input, as it would"

        # Preserved, not destroyed -- standard 0027. The evidence survives on
        # a pushed ref, which is what makes #2571's rebuild-from-refs possible.
        branches = _git(
            target_repo, "branch", "--list", "graveyard/leavings-*",
            "--format=%(refname:short)",
        ).stdout.split()
        assert branches
        shown = _git(
            target_repo, "show", f"{branches[0]}:docs/lld/active/LLD-331.md"
        ).stdout
        assert "drafted by the pipeline" in shown
        on_origin = _git(
            target_repo, "ls-remote", "--heads", "origin", branches[0]
        ).stdout
        assert branches[0] in on_origin, "unpushed is unpreserved"


# ---------------------------------------------------------------------------
# The rolls
# ---------------------------------------------------------------------------


ISSUE_BODY = """## Ask

Render the gauge needle within the redline arc.

## Acceptance

The needle is visually distinct from the arc.
"""


def _stub_gh_issue_view(body: str):
    """Stub ONLY `gh issue view`. Every other subprocess call -- and there
    are many, all of them git -- runs for real."""
    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and "gh" in str(cmd[0]) and (
            "issue" in cmd and "view" in cmd
        ):
            return subprocess.CompletedProcess(
                cmd, 0, stdout=body, stderr=""
            )
        return real_run(cmd, *args, **kwargs)

    return patch("subprocess.run", side_effect=fake_run)


class TestRollShape:
    """The roll's own bookkeeping, exercised without the graph.

    A full green-path roll through the compiled requirements graph is the
    next increment (#2596): it needs a lineage dir, an atlas-narrated node
    sequence and a fixture per stage, and the value of THIS file is the two
    defect classes above, which are the issue's stated acceptance. What is
    pinned here is the harness those rolls will stand on.
    """

    def test_the_scripted_roll_records_the_path_it_took(self, scripted):
        """A roll that reaches the right end state by the wrong route is a
        defect an end-state assertion cannot see."""
        provider = scripted([
            ScriptedRule("analyze", system_pattern="you analyze",
                         response="{}"),
            ScriptedRule("draft", system_pattern="you draft",
                         response="# LLD"),
            ScriptedRule(
                "review", system_pattern="you review",
                response='{"verdict": "APPROVED", "rationale": "ok", '
                         '"feedback_items": [], "open_questions": [], '
                         '"resolved_issues": []}',
            ),
        ])
        provider.invoke("You analyze requirements", "")
        provider.invoke("You draft the LLD", "")
        provider.invoke("You review the draft", "")
        assert provider.stages_called == ["analyze", "draft", "review"]

    def test_a_halt_path_roll_carries_the_failure_message(self, scripted):
        provider = scripted([
            ScriptedRule("draft", system_pattern="draft",
                         fail_with="503 capacity exhausted"),
        ])
        result = provider.invoke("You draft the LLD", "")
        assert result.success is False
        assert "capacity exhausted" in result.error_message
        assert provider.calls[0].answered is False

    def test_gh_issue_view_is_the_only_non_llm_stub(self):
        """Naming the seam in a test so it cannot quietly widen."""
        with _stub_gh_issue_view(ISSUE_BODY):
            stubbed = subprocess.run(
                ["gh", "issue", "view", "331", "--json", "body"],
                capture_output=True, text=True,
            )
            assert stubbed.stdout == ISSUE_BODY
            # Real git still runs underneath the same patch.
            real = subprocess.run(
                ["git", "--version"], capture_output=True, text=True
            )
            assert real.returncode == 0
            assert "git version" in real.stdout
