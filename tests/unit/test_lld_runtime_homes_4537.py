"""#4537: an LLD that puts a runtime mechanic in a module the target never runs.

A real run on a private target approved an LLD whose requirements said "the
runtime engine MUST evaluate each turn index" and "the observation generator
MUST set `stale: true`", while its Files Changed table modified an offline
compiler and added a new Python module beside it. The target built each turn's
Observation in one TypeScript function, `observe` in `web/shared/engine.ts`,
which the plan never listed. The fixture LLD here is that plan's file list and
requirements, with the target's identity taken out.

- T1 (R2): mechanical validation refuses that plan, naming the observation
  generator and the engine file.
- T2 (R1): for an issue naming "the Observation", the codebase analysis returns
  the file that defines the function building it, and the drafter is shown it.
- T3 (R3): the adversarial review prompt asks, for each requirement, which
  listed file implements it.
"""

from __future__ import annotations

import importlib
import textwrap
from pathlib import Path

import pytest

from assemblyzero.workflows.requirements.nodes.analyze_codebase import analyze_codebase
from assemblyzero.workflows.requirements.nodes.generate_draft import (
    _build_prompt,
    build_revision_context,
)
from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
    _validate_lld_mechanical_inner,
    parse_files_changed_table,
)
from assemblyzero.workflows.requirements.runtime_homes import (
    REQUIREMENT_TRACE_TITLE,
    RUNTIME_HOMES_TITLE,
    TRACE_QUESTION,
    find_runtime_homes,
    format_runtime_homes_section,
    issue_concept_names,
    requirement_names_concept,
    requirement_trace_brief,
    unlanded_requirements,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LLD = (
    REPO_ROOT / "tests" / "fixtures" / "lld_runtime_homes"
    / "lld-runtime-mechanic-in-offline-module.md"
).read_text(encoding="utf-8")

#: The issue as the run read it: the engine and the Observation in prose, and
#: no file path.
ISSUE = textwrap.dedent(
    """\
    ## What the engine has today

    Every turn's Observation carries the true price, the true status and the
    compiled forecast. Settlement uses the same actuals.

    ## The mechanic

    An optional `grid.observation_outage[]`: `{ turns_active, frozen_fields }`.
    On those turns the Observation repeats the last values seen for the named
    fields and flags `stale: true`; settlement uses the actuals as always.
    """
)

ENGINE_TS = textwrap.dedent(
    """\
    import type { Pack } from "./pack";

    export interface EngineState {
      turn: number;
    }

    export interface Observation {
      turn: number;
      price_usd_per_mwh: number;
      stale?: boolean;
    }

    export function init(pack: Pack): EngineState {
      return { turn: 0 };
    }

    export function isObservation(x: unknown): x is Observation {
      return typeof x === "object";
    }

    export function observe(pack: Pack, state: EngineState): Observation {
      return { turn: state.turn, price_usd_per_mwh: 0 };
    }
    """
)

#: The engine line `observe` is declared on.
OBSERVE_LINE = ENGINE_TS.splitlines().index(
    "export function observe(pack: Pack, state: EngineState): Observation {"
) + 1


@pytest.fixture
def target(tmp_path):
    """A target whose runtime is TypeScript and whose offline compiler is Python."""
    root = tmp_path / "target"
    (root / "web" / "shared").mkdir(parents=True)
    (root / "web" / "shared" / "engine.ts").write_text(ENGINE_TS, encoding="utf-8")
    (root / "web" / "shared" / "pack.ts").write_text(
        "export interface Pack { name: string }\n", encoding="utf-8"
    )
    # A test helper that returns the concept is not where the target builds it.
    (root / "web" / "shared" / "observe.test.ts").write_text(
        'import type { Observation } from "./engine";\n'
        "export function fakeObservation(): Observation { return {} as Observation; }\n",
        encoding="utf-8",
    )
    (root / "src" / "target").mkdir(parents=True)
    (root / "src" / "target" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "target" / "compiler.py").write_text(
        "def compile_pack(source: dict) -> dict:\n    return dict(source)\n",
        encoding="utf-8",
    )
    (root / "tests" / "unit").mkdir(parents=True)
    return root.resolve()


def _with_engine_listed(lld: str) -> str:
    row = "| `tests/unit/test_observation_outage.py` | Add |"
    engine = (
        "| `web/shared/engine.ts` | Modify | Build the stale observation in "
        "`observe`; carry the last shown values in `EngineState`. |\n"
    )
    return lld.replace(row, engine + row, 1)


# ---------------------------------------------------------------------------
# T1 (R2): the approved plan is refused
# ---------------------------------------------------------------------------


class TestT1ThePlanThatMissesTheRuntimeIsRefused:
    def _validate(self, target, lld, homes):
        return _validate_lld_mechanical_inner({
            "current_draft": lld,
            "target_repo": str(target),
            "issue_number": 101,
            "runtime_homes": homes,
        })

    def test_t1_refused_naming_the_observation_generator_and_the_engine_file(self, target):
        homes = find_runtime_homes(target, ISSUE)

        result = self._validate(target, LLD, homes)

        assert result["lld_status"] == "BLOCKED"
        refusals = [e for e in result["validation_errors"] if "(#4537)" in e]
        generator = [e for e in refusals if "the observation generator" in e]
        assert generator, result["validation_errors"]
        assert all("web/shared/engine.ts" in e for e in generator)
        assert any(e.startswith("Requirement 5 ") for e in generator)
        assert "MECHANICAL VALIDATION FAILED" in result["error_message"]

    def test_t1_only_the_requirements_that_name_the_concept_are_refused(self, target):
        result = self._validate(target, LLD, find_runtime_homes(target, ISSUE))

        numbers = sorted(
            int(e.split()[1]) for e in result["validation_errors"] if "(#4537)" in e
        )
        # 3 "observations", 5, 7 and 10 "the observation generator", 8 and 9
        # "observation stale status" and "observation freezing". 1, 2, 4 and 6
        # name the pack field `grid.observation_outage` or nothing.
        assert numbers == [3, 5, 7, 8, 9, 10]

    def test_t1_the_same_plan_with_the_engine_listed_passes(self, target):
        result = self._validate(
            target, _with_engine_listed(LLD), find_runtime_homes(target, ISSUE)
        )

        assert result["validation_errors"] == []
        assert result["lld_status"] == "PENDING"

    def test_t1_with_no_homes_there_is_nothing_to_compare(self, target):
        result = self._validate(target, LLD, {})

        assert not [e for e in result["validation_errors"] if "(#4537)" in e]


#: A concept declared in one file and built in another.
SPLIT_HOMES = {
    "Observation": {
        "declared_in": ["web/shared/types.ts"],
        "builders": [
            {"function": "observe", "file": "web/shared/engine.ts", "line": 9},
        ],
    },
}
GENERATOR_REQUIREMENT = [
    {"id": "REQ-1", "text": "The observation generator MUST flag stale turns."},
]


class TestR2Rules:
    def test_the_file_declaring_the_type_also_lands_it(self):
        files = [{"path": "web/shared/types.ts", "change_type": "Modify"}]

        assert unlanded_requirements(GENERATOR_REQUIREMENT, files, SPLIT_HOMES) == []

    def test_a_delete_lands_nothing(self):
        files = [{"path": "web/shared/engine.ts", "change_type": "Delete"}]

        [message] = unlanded_requirements(GENERATOR_REQUIREMENT, files, SPLIT_HOMES)

        assert "`web/shared/engine.ts`" in message
        assert "`observe` in `web/shared/engine.ts`" in message

    def test_a_dot_slash_path_is_the_same_file(self):
        files = [{"path": "./web/shared/engine.ts", "change_type": "Modify"}]

        assert unlanded_requirements(GENERATOR_REQUIREMENT, files, SPLIT_HOMES) == []

    @pytest.mark.parametrize("text, named", [
        ("generate observations that are bit-identical", True),
        ("the Observation's stale flag", True),
        ("accept an optional `grid.observation_outage` list", False),
        ("observational studies", False),
    ])
    def test_a_requirement_names_the_concept_by_its_word(self, text, named):
        assert requirement_names_concept(text, "Observation") is named


# ---------------------------------------------------------------------------
# T2 (R1): the analysis finds the function that builds the concept
# ---------------------------------------------------------------------------


class TestT2TheAnalysisFindsWhereTheConceptIsBuilt:
    def _analyze(self, target, issue_text):
        return analyze_codebase({
            "repo_path": str(target),
            "issue_text": issue_text,
            "directory_tree": "web/\n  shared/\n    engine.ts\nsrc/\n  target/\n    compiler.py\n",
        })

    def test_t2_an_issue_naming_the_observation_returns_the_engine_file(self, target):
        result = self._analyze(target, "On outage turns, the Observation is flagged stale.")

        assert "error_message" not in result
        assert result["runtime_homes"] == {
            "Observation": {
                "declared_in": ["web/shared/engine.ts"],
                "builders": [
                    {"function": "observe", "file": "web/shared/engine.ts", "line": OBSERVE_LINE},
                ],
            },
        }
        # Its signatures are read for the drafter too.
        assert "web/shared/engine.ts" in result["interface_map"]

    def test_t2_the_builder_file_is_found_where_the_type_is_declared_elsewhere(self, target):
        shared = target / "web" / "shared"
        (shared / "types.ts").write_text(
            "export interface Snapshot { turn: number }\n", encoding="utf-8"
        )
        (shared / "snap.ts").write_text(
            'import type { Snapshot } from "./types";\n'
            "export const takeSnapshot = (turn: number): Snapshot => ({ turn });\n",
            encoding="utf-8",
        )

        homes = find_runtime_homes(target, "Each turn the Snapshot is taken once.")

        assert homes["Snapshot"]["declared_in"] == ["web/shared/types.ts"]
        assert homes["Snapshot"]["builders"] == [
            {"function": "takeSnapshot", "file": "web/shared/snap.ts", "line": 2},
        ]

    def test_t2_python_builders_are_read_with_ast(self, target):
        pkg = target / "src" / "target"
        (pkg / "models.py").write_text("class Ledger:\n    total = 0\n", encoding="utf-8")
        (pkg / "books.py").write_text(
            "from .models import Ledger\n\n\ndef open_ledger() -> 'Ledger':\n    return Ledger()\n",
            encoding="utf-8",
        )

        homes = find_runtime_homes(target, "The run keeps one `Ledger` per player.")

        assert homes == {
            "Ledger": {
                "declared_in": ["src/target/models.py"],
                "builders": [{"function": "open_ledger", "file": "src/target/books.py", "line": 4}],
            },
        }

    def test_a_type_guard_and_a_test_helper_do_not_build_the_concept(self, target):
        homes = find_runtime_homes(target, ISSUE)

        assert [b["function"] for b in homes["Observation"]["builders"]] == ["observe"]

    def test_a_concept_the_target_never_builds_has_no_home(self, target):
        # `Pack` is declared and only ever taken as an argument.
        assert find_runtime_homes(target, "The engine reads the Pack once.") == {}

    def test_t2_the_drafter_is_shown_the_file_as_where_the_change_lands(self, target):
        homes = find_runtime_homes(target, ISSUE)
        state = {
            "issue_number": 101,
            "issue_title": "Stale observations",
            "issue_body": ISSUE,
            "runtime_homes": homes,
        }

        prompt = _build_prompt(state, "## Template", "lld")

        assert format_runtime_homes_section(homes) in prompt
        assert prompt.index(RUNTIME_HOMES_TITLE) < prompt.index("## Template")
        assert "`observe` in `web/shared/engine.ts`" in prompt

    def test_t2_a_revision_is_shown_the_homes_and_their_signatures(self, target):
        homes = find_runtime_homes(target, ISSUE)
        state = {
            "current_draft": LLD,
            "target_repo": str(target),
            "validation_errors": ["Requirement 5 needs the engine"],
            "repo_structure": "web/\nsrc/",
            "runtime_homes": homes,
        }

        context = build_revision_context(state)

        assert RUNTIME_HOMES_TITLE in context
        # The draft does not list the engine; its signatures are shown anyway.
        assert "export function observe(pack: Pack, state: EngineState): Observation" in context


class TestTheNamesTheIssueWrites:
    def test_capitalized_mid_sentence_backticked_and_camel_case_words_are_names(self):
        names = issue_concept_names(
            "Every turn's Observation carries `stale` and the EngineState.\n"
        )

        assert names == ["Observation", "stale", "EngineState"]

    @pytest.mark.parametrize("text", [
        "## Observation\n",
        "Observation opens this sentence.\n",
        "It ends. Observation opens the next.\n",
        "- Observation opens a bullet.\n",
        "| Observation | a table cell |\n",
        "the spec's Section 6 gives it\n",
        "```\nthe Observation in a log\n```\n",
        "THE MUST WORDS ARE CAPITALS\n",
    ])
    def test_words_capitalized_by_position_are_not_names(self, text):
        assert not ({"Observation", "Section", "THE", "MUST"} & set(issue_concept_names(text)))


# ---------------------------------------------------------------------------
# T3 (R3): the reviewer is asked which listed file implements each requirement
# ---------------------------------------------------------------------------


class _Stop(Exception):
    """Raised by the fake reviewer once it has the prompt."""


class TestT3TheReviewerIsAskedPerRequirement:
    @pytest.fixture
    def prompt_for(self, target, tmp_path, monkeypatch):
        review = importlib.import_module("assemblyzero.workflows.requirements.nodes.review")
        seen = {}

        class Reviewer:
            def invoke(self, system, prompt, **kwargs):
                seen["prompt"] = prompt
                raise _Stop

        monkeypatch.setattr(review, "get_provider", lambda spec, **k: Reviewer())
        audit = tmp_path / "audit"
        audit.mkdir()

        def run(draft, workflow_type="lld", homes=None):
            with pytest.raises(_Stop):
                review.review({
                    "workflow_type": workflow_type,
                    "assemblyzero_root": str(REPO_ROOT),
                    "audit_dir": str(audit),
                    "current_draft": draft,
                    "target_repo": str(target),
                    "runtime_homes": homes or {},
                })
            return seen["prompt"]

        return run

    def test_t3_the_prompt_asks_of_every_requirement_which_listed_file_implements_it(
        self, prompt_for
    ):
        prompt = prompt_for(LLD)

        brief = prompt[prompt.index(REQUIREMENT_TRACE_TITLE):]
        assert brief.count(TRACE_QUESTION) == 10
        unimplementable = (
            "5. On turns matching an active outage, the observation generator MUST set "
            "`stale: true`"
        )
        asked = brief.index(unimplementable)
        assert brief.index(TRACE_QUESTION, asked) < brief.index("\n6. ", asked)
        assert "Tier 1 BLOCKING finding" in brief
        for row in parse_files_changed_table(LLD)[0]:
            assert f"- `{row['path']}` ({row['change_type']})" in brief

    def test_t3_the_reviewer_sees_where_the_concepts_are_built(self, prompt_for, target):
        homes = find_runtime_homes(target, ISSUE)

        prompt = prompt_for(LLD, homes=homes)

        assert format_runtime_homes_section(homes) in prompt
        assert prompt.index(RUNTIME_HOMES_TITLE) < prompt.index("## Document to Review")

    def test_t3_the_standing_instructions_make_it_a_tier_one_check(self, prompt_for):
        prompt = prompt_for(LLD)

        tier1 = prompt[prompt.index("## Tier 1: BLOCKING (Must Pass)"):]
        assert "**Requirement → File (CRITICAL)**" in tier1[: tier1.index("## Tier 2")]

    def test_an_issue_draft_is_not_asked(self, prompt_for):
        assert REQUIREMENT_TRACE_TITLE not in prompt_for(LLD, workflow_type="issue")

    def test_a_draft_with_no_requirements_section_gets_no_brief(self):
        assert requirement_trace_brief("# a draft\n\n## 2. Proposed Changes\n") == ""
