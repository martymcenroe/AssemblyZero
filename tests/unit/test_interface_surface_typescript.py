"""#4500: the LLD drafter sees TypeScript.

The interface surface read `.py` files alone, and a path the issue named was
recognised only if it ended in `.py`. On a real run a target's 442-line core
TypeScript module reached the drafter as two mentions in prose. The approved LLD
listed that module as a new file and guessed its types, and the reviewer, with no
source either, approved it. These tests pin what the drafter and reviewer get.
"""

from __future__ import annotations

import importlib
import logging
import textwrap
from pathlib import Path

import pytest

import assemblyzero.core.interface_surface as isurf
from assemblyzero.core.interface_surface import (
    build_interface_map,
    build_interface_map_for_paths,
    extract_explicit_paths,
    extract_interface_map,
    format_interface_map_section,
    has_extractor,
    list_repo_source_files,
    resolve_import_targets,
    summarize_tsx_file,
    summarize_typescript_file,
)

ENGINE_TS = textwrap.dedent(
    """\
    /**
     * The engine: pure bookkeeping.
     */
    import type { Pack } from "./pack";
    import { helper } from "some-package";

    export const ENGINE_VERSION = "0.5.0";

    /** What a player does on a turn. */
    export interface Action {
      diesel_mw: number;
    }

    export type Mode = "idle" | "run";

    export enum Phase {
      Early,
      Late,
    }

    const hidden = (x: number) => x * 2;

    function privateHelper(pack: Pack) {
      return "secret_helper_body";
    }

    export function resolve(pack: Pack, action: Action): number {
      return hidden(action.diesel_mw) + "secret_body".length;
    }

    export const replay = (pack: Pack, actions: Action[]): number => {
      return "secret_arrow_body".length;
    };

    export const TABLE: Record<string, number> = {
      """
) + ",\n  ".join(f'k{i}: {i}' for i in range(60)) + textwrap.dedent(
    """
    };

    export class Ledger {
      private hiddenField = 1;
      total: number = 0;

      add(amount: number): void {
        this.total += "secret_method_body".length;
      }

      private drop(): void {}
    }
    """
)


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "web" / "shared").mkdir(parents=True)
    (tmp_path / "web" / "shared" / "engine.ts").write_text(ENGINE_TS, encoding="utf-8")
    (tmp_path / "web" / "shared" / "pack.ts").write_text(
        "export interface Pack { name: string }\n", encoding="utf-8"
    )
    (tmp_path / "web" / "src").mkdir()
    (tmp_path / "web" / "src" / "App.tsx").write_text(
        'import { resolve } from "../shared/engine";\n'
        "export function App(props: { title: string }) {\n"
        "  return <div>{props.title}secret_jsx_body</div>;\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "web" / "worker-configuration.d.ts").write_text(
        "export interface Env {}\n", encoding="utf-8"
    )
    (tmp_path / "web" / "node_modules" / "dep").mkdir(parents=True)
    (tmp_path / "web" / "node_modules" / "dep" / "index.ts").write_text(
        "export const fromDep = 1;\n", encoding="utf-8"
    )
    (tmp_path / "web" / "tests").mkdir()
    (tmp_path / "web" / "tests" / "engine.test.ts").write_text(
        "export const inTests = 1;\n", encoding="utf-8"
    )
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "compiler.py").write_text("def compile_pack():\n    pass\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "design.md").write_text("# design\n", encoding="utf-8")
    (tmp_path / "tool.rs").write_text("fn main() {}\n", encoding="utf-8")
    return tmp_path.resolve()


@pytest.fixture
def selection(monkeypatch):
    """Selection mode, which every target over the whole-surface cap runs in."""
    monkeypatch.setattr(isurf, "WHOLE_SURFACE_MAX_FILES", 0)


class TestNamedPaths:
    def test_t1_a_named_typescript_file_is_found(self, repo):
        found = extract_explicit_paths("Change `web/shared/engine.ts` here.", repo)

        assert [p.relative_to(repo).as_posix() for p in found] == ["web/shared/engine.ts"]

    def test_t1_a_named_typescript_file_reaches_the_surface(self, repo, selection):
        surface = build_interface_map(repo, issue_text="The engine is `web/shared/engine.ts`.")

        assert "web/shared/engine.ts" in surface
        assert "export interface Action" in surface["web/shared/engine.ts"]

    def test_t1_a_named_file_comes_first_when_the_budget_is_short(self, repo, selection):
        surface = build_interface_map(
            repo,
            issue_text="`web/shared/engine.ts`",
            related_paths=[repo / "pkg" / "compiler.py"],
        )

        assert next(iter(surface)) == "web/shared/engine.ts"

    def test_a_file_that_is_not_there_is_nothing(self, repo):
        assert extract_explicit_paths("`web/shared/gone.ts` and site.diesel", repo) == []


class TestTheSummary:
    @pytest.fixture
    def summary(self):
        return summarize_typescript_file(ENGINE_TS)

    @pytest.mark.parametrize("expected", [
        "The engine: pure bookkeeping.",
        'import type { Pack } from "./pack";',
        'export const ENGINE_VERSION = "0.5.0";',
        "export interface Action {\n  diesel_mw: number;\n}",
        "/** What a player does on a turn. */",
        'export type Mode = "idle" | "run";',
        "export enum Phase",
        "export function resolve(pack: Pack, action: Action): number",
        "export const replay = (pack: Pack, actions: Action[]): number =>",
        "export class Ledger {",
        "total: number",
        "add(amount: number): void",
    ])
    def test_t2_the_interface_is_there(self, summary, expected):
        assert expected in summary

    @pytest.mark.parametrize("absent", [
        "secret_body", "secret_arrow_body", "secret_method_body",
        "privateHelper", "secret_helper_body", "const hidden",
        "hiddenField", "drop()",
    ])
    def test_t2_bodies_and_private_names_are_not(self, summary, absent):
        assert absent not in summary

    def test_a_long_constant_keeps_its_name_and_type_only(self, summary):
        assert "export const TABLE: Record<string, number> = ..." in summary
        assert "k59" not in summary

    def test_tsx_is_read_as_tsx(self):
        summary = summarize_tsx_file(
            "export function App(p: { t: string }) { return <div>secret_jsx_body</div>; }\n"
        )

        assert "export function App(p: { t: string })" in summary
        assert "secret_jsx_body" not in summary

    def test_an_empty_file_is_an_empty_summary(self):
        assert summarize_typescript_file("") == ""


class TestAGapInTheGrammar:
    GAP = "export function ok(): number { return 1; }\nconst broken = ((;\n"

    def test_it_never_stops_the_run_and_says_so_in_the_summary(self):
        summary = summarize_typescript_file(self.GAP)

        assert summary.startswith("// parser could not read line(s) 2")
        assert "export function ok(): number" in summary

    def test_the_log_names_the_file(self, tmp_path, caplog):
        path = tmp_path / "gap.ts"
        path.write_text(self.GAP, encoding="utf-8")

        with caplog.at_level(logging.WARNING, logger="assemblyzero.core.interface_surface"):
            surface = extract_interface_map([path], tmp_path.resolve())

        assert "gap.ts" in surface
        assert any("gap.ts" in r.getMessage() for r in caplog.records)


class TestTheWalk:
    def test_whole_surface_mode_reads_both_languages(self, repo):
        surface = build_interface_map(repo)

        assert {"web/shared/engine.ts", "web/shared/pack.ts", "web/src/App.tsx",
                "pkg/compiler.py"} <= set(surface)

    def test_it_stays_out_of_what_is_not_the_project(self, repo):
        rels = {p.relative_to(repo).as_posix() for p in list_repo_source_files(repo)}

        assert "web/node_modules/dep/index.ts" not in rels
        assert "web/worker-configuration.d.ts" not in rels
        assert "web/tests/engine.test.ts" not in rels

    def test_it_never_descends_into_node_modules(self, repo, monkeypatch):
        entered = []
        real_walk = isurf.os.walk

        def spy(top, **kwargs):
            for step in real_walk(top, **kwargs):
                entered.append(step[0])
                yield step

        monkeypatch.setattr(isurf.os, "walk", spy)
        list_repo_source_files(repo)

        assert not any("node_modules" in folder for folder in entered)

    def test_a_keyword_match_inside_node_modules_is_refused(self, repo, selection):
        dep = repo / "web" / "node_modules" / "dep" / "index.ts"

        assert build_interface_map(repo, related_paths=[dep]) == {}

    def test_a_repo_with_only_typescript_has_a_surface(self, tmp_path):
        (tmp_path / "a.ts").write_text("export const a = 1;\n", encoding="utf-8")

        assert "a.ts" in build_interface_map(tmp_path)


class TestImportExpansion:
    def test_a_relative_import_is_followed(self, repo):
        engine = repo / "web" / "shared" / "engine.ts"

        targets = resolve_import_targets(engine, repo)

        assert [p.relative_to(repo).as_posix() for p in targets] == ["web/shared/pack.ts"]

    def test_a_named_file_brings_its_collaborators(self, repo, selection):
        surface = build_interface_map(repo, issue_text="`web/src/App.tsx`")

        assert list(surface) == ["web/src/App.tsx", "web/shared/engine.ts"]

    def test_esm_js_and_index_files_resolve(self, tmp_path):
        root = tmp_path.resolve()
        (root / "lib").mkdir()
        (root / "lib" / "index.ts").write_text("export const a = 1;\n", encoding="utf-8")
        (root / "b.ts").write_text("export const b = 1;\n", encoding="utf-8")
        main = root / "main.ts"
        main.write_text(
            'export * from "./lib";\nimport { b } from "./b.js";\nimport x from "react";\n',
            encoding="utf-8",
        )

        targets = {p.relative_to(root).as_posix() for p in resolve_import_targets(main, root)}

        assert targets == {"lib/index.ts", "b.ts"}


class TestALanguageNothingReads:
    def test_t3_a_named_file_is_said_in_the_log(self, repo, caplog):
        with caplog.at_level(logging.WARNING, logger="assemblyzero.core.interface_surface"):
            build_interface_map(repo, issue_text="`tool.rs`")

        assert any(
            "tool.rs" in r.getMessage() and r.levelno >= logging.WARNING
            for r in caplog.records
        )

    def test_t3_and_in_the_prompt(self, repo):
        section = format_interface_map_section(build_interface_map(repo, issue_text="`tool.rs`"))

        assert "**tool.rs**" in section
        assert "No signatures" in section

    def test_a_named_document_is_no_gap(self, repo, caplog):
        with caplog.at_level(logging.WARNING, logger="assemblyzero.core.interface_surface"):
            surface = build_interface_map(repo, issue_text="`docs/design.md`")

        assert "docs/design.md" not in surface
        assert not caplog.records


class TestTheRevisionLoop:
    def test_a_files_changed_row_in_typescript_refreshes_the_surface(self, repo):
        surface = build_interface_map_for_paths(["web/shared/engine.ts"], repo)

        assert list(surface) == ["web/shared/engine.ts", "web/shared/pack.ts"]

    @pytest.mark.parametrize(("path", "readable"), [
        ("a.py", True), ("a.ts", True), ("a.tsx", True), ("a.md", False), ("", False),
    ])
    def test_has_extractor(self, path, readable):
        assert has_extractor(path) is readable


class TestRendering:
    def test_a_typescript_entry_is_fenced_as_typescript(self):
        section = format_interface_map_section({"a.ts": "export const a = 1;"})

        assert "```typescript\nexport const a = 1;" in section

    def test_a_python_entry_keeps_its_fence(self):
        assert "```python\n" in format_interface_map_section({"a.py": "x = 1"})

    def test_a_truncated_typescript_summary_says_so_in_its_language(self, repo):
        engine = repo / "web" / "shared" / "engine.ts"

        surface = extract_interface_map([engine], repo, per_file_char_cap=50)

        assert surface["web/shared/engine.ts"].endswith("// ... (truncated for budget)")


class _Stop(Exception):
    """Raised by the fake reviewer once it has the prompt."""


class TestTheReviewer:
    @pytest.fixture
    def prompt_with(self, repo, tmp_path, monkeypatch):
        review = importlib.import_module("assemblyzero.workflows.requirements.nodes.review")
        seen = {}

        class Reviewer:
            def invoke(self, system, prompt, **kwargs):
                seen["prompt"] = prompt
                raise _Stop

        monkeypatch.setattr(review, "get_provider", lambda spec, **k: Reviewer())
        audit = tmp_path / "audit"
        audit.mkdir()

        def run(interface_map):
            with pytest.raises(_Stop):
                review.review({
                    "workflow_type": "lld",
                    "assemblyzero_root": str(Path(__file__).resolve().parents[2]),
                    "audit_dir": str(audit),
                    "current_draft": "# the draft",
                    "target_repo": str(repo),
                    "interface_map": interface_map,
                })
            return seen["prompt"]

        return run

    def test_t4_it_sees_the_surface_the_drafter_saw(self, prompt_with):
        interface_map = {"web/shared/engine.ts": "export interface Action {}"}

        prompt = prompt_with(interface_map)

        assert format_interface_map_section(interface_map) in prompt
        assert prompt.index(isurf.INTERFACE_SECTION_TITLE) < prompt.index("# the draft")

    def test_t4_with_no_surface_there_is_no_section(self, prompt_with):
        assert isurf.INTERFACE_SECTION_TITLE not in prompt_with({})


def test_the_surface_is_read_from_real_source_on_disk(repo):
    # The summary reads the file, never a copy of it.
    path = repo / "web" / "shared" / "pack.ts"
    path.write_text("export interface Renamed {}\n", encoding="utf-8")

    assert "Renamed" in extract_interface_map([path], repo)["web/shared/pack.ts"]
    assert Path(path).is_file()
