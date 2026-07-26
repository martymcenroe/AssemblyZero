"""Tiphys — shared interface-surface extraction (#1688).

Pins the design's load-bearing properties:

- the three summarizers moved to core ARE the spec stage's summarizers
  (aliases, not copies — one yardstick, drift impossible);
- whole-surface mode eliminates selection for small repos;
- selection mode composes explicit paths + related files + one-hop
  import expansion;
- the revision feedback loop extracts from the draft's own Files Changed
  paths;
- the rendered section survives prompt truncation while every sacrificial
  section is dropped;
- every failure path degrades to an empty map — Tiphys can never block
  an LLD.

Issue: #1688
"""

import textwrap

import pytest

import assemblyzero.core.interface_surface as isurf
from assemblyzero.core.interface_surface import (
    INTERFACE_SECTION_TITLE,
    build_interface_map,
    build_interface_map_for_paths,
    extract_explicit_paths,
    extract_interface_map,
    format_interface_map_section,
    list_repo_python_files,
    resolve_import_targets,
    summarize_python_file,
)

MODELS_PY = textwrap.dedent(
    '''
    """Domain models."""

    DEFAULT_LIMIT = 10


    class Question:
        """A question with plain-dataclass serialization."""

        def to_dict(self) -> dict:
            """Serialize."""
            return {"secret_internal_detail": True}

        @classmethod
        def from_dict(cls, data: dict) -> "Question":
            return cls()


    async def fetch_question(qid: int) -> Question:
        """Fetch by id."""
        return Question()
    '''
).strip()

SERVICE_PY = textwrap.dedent(
    '''
    """Service layer."""

    import os
    from pkg.models import Question


    def serve(q: Question) -> dict:
        """Serve a question."""
        return q.to_dict()
    '''
).strip()

RELATIVE_PY = textwrap.dedent(
    '''
    """Uses a relative import."""

    from .models import Question


    def relative_user() -> Question:
        return Question()
    '''
).strip()

UTIL_PY = '"""Utility."""\n\n\ndef helper() -> int:\n    return 1\n'


@pytest.fixture
def repo(tmp_path):
    """A small fake repo exercising every selection surface."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "models.py").write_text(MODELS_PY, encoding="utf-8")
    (pkg / "service.py").write_text(SERVICE_PY, encoding="utf-8")
    (pkg / "relative_user.py").write_text(RELATIVE_PY, encoding="utf-8")
    (pkg / "util.py").write_text(UTIL_PY, encoding="utf-8")
    # Never walked:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_models.py").write_text("def test_x(): pass\n", encoding="utf-8")
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "sneaky.py").write_text("def sneaky(): pass\n", encoding="utf-8")
    return tmp_path


# =============================================================================
# Summarizers — moved, aliased, self-consistent
# =============================================================================


class TestSummarizers:

    def test_summary_has_signatures_not_bodies(self):
        summary = summarize_python_file(MODELS_PY)
        assert "class Question:" in summary
        assert "def to_dict(self) -> dict:" in summary
        assert "async def fetch_question(qid: int) -> Question:" in summary
        assert "DEFAULT_LIMIT = 10" in summary
        assert '"""Domain models."""' in summary
        # Implementation details must NOT ride along.
        assert "secret_internal_detail" not in summary

    def test_syntax_error_falls_back_to_head(self):
        summary = summarize_python_file("def broken(:\n" * 3)
        assert "truncated, syntax error" in summary

    def test_spec_stage_aliases_are_the_core_functions(self):
        """The move must be aliasing, not copying — one yardstick."""
        from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import (
            _summarize_class,
            _summarize_function,
            _summarize_python_file,
        )

        assert _summarize_python_file is isurf.summarize_python_file
        assert _summarize_class is isurf.summarize_class
        assert _summarize_function is isurf.summarize_function

    def test_summary_names_subset_of_gate_symbols(self):
        """Self-consistency of the funnel's two ends: every def/class name
        the drafter is shown must exist in the symbol set the spec-stage
        gate checks. If these ever disagree, Tiphys teaches names the gate
        would then flag."""
        from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import (
            _extract_symbols_from_files,
        )

        gate_symbols = set(
            _extract_symbols_from_files(
                [{"path": "pkg/models.py", "current_content": MODELS_PY}]
            )
        )
        for name in ("Question", "to_dict", "from_dict", "fetch_question"):
            summary = summarize_python_file(MODELS_PY)
            assert name in summary
            assert name in gate_symbols


# =============================================================================
# Discovery and selection
# =============================================================================


class TestListRepoPythonFiles:

    def test_walk_includes_source_excludes_tests_and_hidden(self, repo):
        rels = {p.relative_to(repo).as_posix() for p in list_repo_python_files(repo)}
        assert "pkg/models.py" in rels
        assert "pkg/util.py" in rels
        assert not any(r.startswith("tests/") for r in rels)
        assert not any(r.startswith(".hidden/") for r in rels)


class TestExtractExplicitPaths:

    def test_resolves_mentioned_file(self, repo):
        issue = "Please refactor pkg/service.py to stop doing the thing."
        paths = extract_explicit_paths(issue, repo)
        assert [p.name for p in paths] == ["service.py"]

    def test_backslash_form_resolves(self, repo):
        paths = extract_explicit_paths(r"See pkg\models.py for details.", repo)
        assert [p.name for p in paths] == ["models.py"]

    def test_nonexistent_and_escaping_paths_rejected(self, repo):
        issue = "Touch pkg/nope.py and also ../../outside/evil.py please."
        assert extract_explicit_paths(issue, repo) == []


class TestResolveImportTargets:

    def test_absolute_intra_repo_import_resolves(self, repo):
        targets = resolve_import_targets(repo / "pkg" / "service.py", repo)
        assert [t.name for t in targets] == ["models.py"]

    def test_relative_import_resolves(self, repo):
        targets = resolve_import_targets(repo / "pkg" / "relative_user.py", repo)
        assert [t.name for t in targets] == ["models.py"]

    def test_stdlib_imports_resolve_to_nothing(self, repo):
        only_stdlib = repo / "pkg" / "stdlib_only.py"
        only_stdlib.write_text("import os\nimport json\n", encoding="utf-8")
        assert resolve_import_targets(only_stdlib, repo) == []


# =============================================================================
# Extraction budgets
# =============================================================================


class TestExtractInterfaceMap:

    def test_keys_are_repo_relative_posix(self, repo):
        surface = extract_interface_map([repo / "pkg" / "models.py"], repo)
        assert list(surface) == ["pkg/models.py"]

    def test_per_file_cap_truncates_with_marker(self, repo):
        surface = extract_interface_map(
            [repo / "pkg" / "models.py"], repo, per_file_char_cap=40
        )
        assert "truncated for budget" in surface["pkg/models.py"]

    def test_total_cap_drops_whole_files(self, repo):
        surface = extract_interface_map(
            [repo / "pkg" / "models.py", repo / "pkg" / "service.py"],
            repo,
            total_char_cap=len(summarize_python_file(MODELS_PY)) + 1,
        )
        assert "pkg/models.py" in surface
        assert "pkg/service.py" not in surface

    def test_non_python_contributes_nothing(self, repo):
        readme = repo / "README.md"
        readme.write_text("# hi", encoding="utf-8")
        assert extract_interface_map([readme], repo) == {}


# =============================================================================
# Mode logic
# =============================================================================


class TestBuildInterfaceMap:

    def test_small_repo_ships_whole_surface(self, repo):
        """No selection, therefore no selection miss: even a file with no
        keyword or import relationship to the issue is included."""
        surface = build_interface_map(repo, issue_text="Something unrelated.")
        assert "pkg/util.py" in surface
        assert "pkg/models.py" in surface

    def test_large_repo_selects_and_expands_imports(self, repo, monkeypatch):
        monkeypatch.setattr(isurf, "WHOLE_SURFACE_MAX_FILES", 0)
        surface = build_interface_map(
            repo, issue_text="Refactor pkg/service.py return shape."
        )
        assert "pkg/service.py" in surface, "explicit path must be selected"
        assert "pkg/models.py" in surface, "one-hop import must be expanded"
        assert "pkg/util.py" not in surface, "unrelated file must not ride along"

    def test_empty_repo_yields_empty_map(self, tmp_path):
        assert build_interface_map(tmp_path) == {}

    def test_missing_repo_yields_empty_map(self, tmp_path):
        assert build_interface_map(tmp_path / "gone") == {}


class TestBuildInterfaceMapForPaths:
    """The revision feedback loop's extractor."""

    def test_draft_declared_paths_plus_imports(self, repo):
        surface = build_interface_map_for_paths(["pkg/service.py"], repo)
        assert "pkg/service.py" in surface
        assert "pkg/models.py" in surface

    def test_escaping_and_missing_paths_skipped(self, repo):
        surface = build_interface_map_for_paths(
            ["../outside.py", "pkg/nope.py"], repo
        )
        assert surface == {}


# =============================================================================
# Rendering and prompt integration
# =============================================================================


class TestFormatSection:

    def test_section_carries_imperative_framing(self, repo):
        surface = build_interface_map(repo)
        section = format_interface_map_section(surface)
        assert section.startswith(INTERFACE_SECTION_TITLE)
        assert "DO NOT invent methods" in section
        assert "**pkg/models.py**:" in section

    def test_empty_map_renders_nothing(self):
        assert format_interface_map_section({}) == ""


class TestPromptIntegration:

    def _lld_state(self, repo, **overrides):
        state = {
            "issue_number": 77,
            "issue_title": "Do the thing",
            "issue_body": "Change pkg/service.py behavior.",
            "context_content": "",
            "target_repo": str(repo),
            "interface_map": build_interface_map(repo),
            "codebase_context": {"project_description": "A demo project."},
            "current_draft": "",
            "verdict_history": [],
            "user_feedback": "",
            "validation_errors": [],
        }
        state.update(overrides)
        return state

    def test_fresh_draft_places_surface_before_codebase_context(self, repo):
        from assemblyzero.workflows.requirements.nodes.generate_draft import (
            _build_prompt,
        )

        prompt = _build_prompt(self._lld_state(repo), "TEMPLATE", "lld")
        assert prompt.count(INTERFACE_SECTION_TITLE) == 1
        assert prompt.index(INTERFACE_SECTION_TITLE) < prompt.index(
            "## Codebase Analysis"
        )

    def test_revision_refreshes_from_files_changed_table(self, repo):
        from assemblyzero.workflows.requirements.nodes.generate_draft import (
            _build_prompt,
        )

        draft = textwrap.dedent(
            """
            # 77 - Feature: Do the thing

            ### 2.1 Files Changed

            | File | Change Type | Description |
            |------|-------------|-------------|
            | `pkg/relative_user.py` | Modify | rewire |

            ## 11 Acceptance
            ## 12 Done
            """
        ).strip()
        state = self._lld_state(
            repo,
            current_draft=draft,
            validation_errors=["Section 2.3 missing"],
            repo_structure="pkg/",
            # A stale N0b map that does NOT contain relative_user.py — the
            # refresh must supersede it.
            interface_map={"pkg/util.py": "def helper() -> int:\n    ..."},
        )
        prompt = _build_prompt(state, "TEMPLATE", "lld")
        # Exactly one surface section: refresh in revision context; the
        # input-content injection must be suppressed on revisions.
        assert prompt.count(INTERFACE_SECTION_TITLE) == 1
        assert "relative_user" in prompt.split(INTERFACE_SECTION_TITLE)[1]
        assert "def helper" not in prompt, "stale map must be superseded"

    def test_revision_falls_back_to_state_map_without_table(self, repo):
        from assemblyzero.workflows.requirements.nodes.generate_draft import (
            _build_prompt,
        )

        state = self._lld_state(
            repo,
            current_draft="# 77 - Feature: no table here\n\nProse only.",
            validation_errors=["Section 2.1 not found"],
            repo_structure="pkg/",
        )
        prompt = _build_prompt(state, "TEMPLATE", "lld")
        assert prompt.count(INTERFACE_SECTION_TITLE) == 1

    def test_truncation_sacrifices_codebase_context_not_the_surface(self, repo):
        from assemblyzero.workflows.requirements.nodes.generate_draft import (
            MAX_TOTAL_PROMPT_CHARS,
            _truncate_prompt,
        )

        surface_section = format_interface_map_section(build_interface_map(repo))
        oversized = (
            "## Issue\nDo the thing.\n\n"
            + surface_section
            + "\n\n## Codebase Analysis\n"
            + ("filler " * (MAX_TOTAL_PROMPT_CHARS // 6))
        )
        assert len(oversized) > MAX_TOTAL_PROMPT_CHARS
        result = _truncate_prompt(oversized)
        assert INTERFACE_SECTION_TITLE in result
        assert "## Codebase Analysis" not in result
