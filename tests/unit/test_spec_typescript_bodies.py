"""A spec's TypeScript test bodies are checked before a run (#4519).

On a real run a spec's test body read `score.cost_usd`, a member the target's
`Score` does not have. The implementer copied it, and the run spent all three
of its iterations on the one line.

The tests marked `compiles` run a real TypeScript compiler, installed once per
session; they skip where node and npm are absent, as on CI. The rest read
recorded compiler output and need nothing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from assemblyzero.workflows.implementation_spec import typescript_bodies
from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    CompletenessCannotCheck,
    check_spec_typescript_tests_read_real_members,
)

SCORING = textwrap.dedent('''\
    export interface Score {
      cost: { value_usd: number };
      turns: number;
    }

    export function computeScore(): Score {
      return { cost: { value_usd: 1 }, turns: 0 };
    }
''')


def _spec(body: str) -> str:
    return textwrap.dedent('''\
        ## 6. Change Instructions

        ```typescript
        // web/tests/not-section-ten.test.ts
        const x: number = "never read";
        ```

        ## 10. Test Mapping

        ### 10.1 Per-criterion test functions

        ```typescript
        // web/tests/replay.test.ts (TypeScript per-criterion test functions)
        import { describe, expect, it } from "./vitest-stub";
        import { computeScore } from "../shared/scoring";

        describe("stocks", () => {
          it("satisfies REQ-11 (row 150): replay scores hold (REQ-11)", () => {
            const score = computeScore();
        BODY
          });
        });
        ```

        ## 11. Implementation Notes
    ''').replace("BODY", body)


VITEST_STUB = textwrap.dedent('''\
    export function describe(_: string, f: () => void): void { f(); }
    export function it(_: string, f: () => void): void { f(); }
    export function expect(_: unknown): { toBe(v: unknown): void } {
      return { toBe() {} };
    }
''')

compiles = pytest.mark.skipif(
    shutil.which("npm") is None or shutil.which("node") is None,
    reason="node and npm are not on this machine",
)


@pytest.fixture(scope="session")
def typescript_modules(tmp_path_factory) -> Path:
    """A real TypeScript compiler's node_modules, installed once."""
    where = tmp_path_factory.mktemp("typescript")
    result = subprocess.run(
        ["npm", "install", "--no-save", "--no-audit", "--no-fund", "--silent", "typescript@5"],
        cwd=where, capture_output=True, text=True, timeout=300, check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"TypeScript could not be installed: {result.stderr.strip()[-300:]}")
    return where / "node_modules"


def _target(tmp_path: Path, modules: Path | None) -> Path:
    web = tmp_path / "web"
    (web / "shared").mkdir(parents=True)
    (web / "tests").mkdir()
    (web / "shared" / "scoring.ts").write_text(SCORING, encoding="utf-8")
    (web / "tests" / "vitest-stub.ts").write_text(VITEST_STUB, encoding="utf-8")
    (web / "package.json").write_text('{"name": "web"}', encoding="utf-8")
    (web / "tsconfig.json").write_text(json.dumps({
        "compilerOptions": {
            "target": "ES2022", "module": "ESNext", "moduleResolution": "bundler",
            "strict": True, "noEmit": True, "skipLibCheck": True,
        },
        "include": ["shared", "tests"],
    }), encoding="utf-8")
    if modules is not None:
        (web / "node_modules").symlink_to(modules, target_is_directory=True)
    return tmp_path


def _tree(root: Path) -> set[str]:
    return {
        p.relative_to(root).as_posix() for p in root.rglob("*")
        if "node_modules" not in p.parts
    }


@compiles
class TestTheCheckOnARealCompile:
    def test_t1_a_member_the_unchanged_type_lacks_is_refused(self, tmp_path, typescript_modules):
        root = _target(tmp_path, typescript_modules)
        check = check_spec_typescript_tests_read_real_members(
            _spec("    expect(score.cost_usd).toBe(1);"),
            [{"path": "web/tests/replay.test.ts", "change_type": "Modify"}],
            str(root),
        )
        assert not check["passed"]
        details = check["details"]
        assert "satisfies REQ-11 (row 150): replay scores hold (REQ-11)" in details
        assert "`cost_usd` of `Score`" in details
        assert "web/shared/scoring.ts" in details

    def test_t2_a_type_the_plan_modifies_is_left_alone(self, tmp_path, typescript_modules):
        root = _target(tmp_path, typescript_modules)
        check = check_spec_typescript_tests_read_real_members(
            _spec("    expect(score.cost_usd).toBe(1);"),
            [{"path": "web/shared/scoring.ts", "change_type": "Modify"}],
            str(root),
        )
        assert check["passed"], check["details"]

    def test_t3_a_member_the_type_has_passes(self, tmp_path, typescript_modules):
        root = _target(tmp_path, typescript_modules)
        check = check_spec_typescript_tests_read_real_members(
            _spec("    expect(score.cost.value_usd).toBe(1);"), [], str(root),
        )
        assert check["passed"], check["details"]
        assert "not applicable" not in check["details"]

    def test_a_name_the_plan_adds_is_not_a_fault(self, tmp_path, typescript_modules):
        root = _target(tmp_path, typescript_modules)
        body = (
            '    expect(score.turns).toBe(0);\n'
            '    // eslint-disable-next-line\n'
            '    const stocks = (globalThis as any).planned;\n'
            '    expect(stocks.not_yet_written).toBe(1);'
        )
        spec = _spec(body).replace(
            'import { computeScore } from "../shared/scoring";',
            'import { computeScore } from "../shared/scoring";\n'
            'import { applyStockBurn } from "../shared/stocks";\n'
            'expect(applyStockBurn().level).toBe(1);',
        )
        check = check_spec_typescript_tests_read_real_members(spec, [], str(root))
        assert check["passed"], check["details"]

    def test_a_library_type_is_not_the_targets_to_answer_for(self, tmp_path, typescript_modules):
        root = _target(tmp_path, typescript_modules)
        check = check_spec_typescript_tests_read_real_members(
            _spec("    expect(new Date().no_such_member).toBe(1);"), [], str(root),
        )
        assert check["passed"], check["details"]

    def test_nothing_is_left_in_the_target(self, tmp_path, typescript_modules):
        root = _target(tmp_path, typescript_modules)
        before = _tree(root)
        check_spec_typescript_tests_read_real_members(
            _spec("    expect(score.cost_usd).toBe(1);"), [], str(root),
        )
        assert _tree(root) == before


class TestNotApplicable:
    def test_no_typescript_body(self):
        check = check_spec_typescript_tests_read_real_members("## 10. Tests\n\nnone\n", [], "/x")
        assert check["passed"]
        assert "not applicable" in check["details"]

    def test_a_target_that_has_not_installed_typescript(self, tmp_path):
        root = _target(tmp_path, None)
        check = check_spec_typescript_tests_read_real_members(
            _spec("    expect(score.cost_usd).toBe(1);"), [], str(root),
        )
        assert check["passed"]
        assert "TypeScript is not installed" in check["details"]
        assert "not applicable" in check["details"]

    def test_a_body_with_no_tsconfig_above_it(self, tmp_path):
        root = _target(tmp_path, None)
        (root / "web" / "tsconfig.json").unlink()
        check = check_spec_typescript_tests_read_real_members(
            _spec("    expect(score.cost_usd).toBe(1);"), [], str(root),
        )
        assert check["passed"]
        assert "no tsconfig.json" in check["details"]

    def test_no_repo_root_cannot_check(self):
        with pytest.raises(CompletenessCannotCheck):
            check_spec_typescript_tests_read_real_members(
                _spec("    expect(score.cost_usd).toBe(1);"), [], "",
            )


class TestTheParts:
    def test_only_section_ten_bodies_that_name_their_file(self):
        bodies = typescript_bodies.spec_typescript_bodies(
            _spec("x;") + "\n## 10.2 More\n\n```ts\nconst unnamed = 1;\n```\n"
        )
        assert [b.path for b in bodies] == ["web/tests/replay.test.ts"]
        assert "computeScore" in bodies[0].text

    def test_the_title_of_the_test_holding_a_line(self):
        body = typescript_bodies.spec_typescript_bodies(_spec("    score.cost_usd;"))[0].text
        line = next(n for n, text in enumerate(body.splitlines(), 1) if "cost_usd" in text)
        assert typescript_bodies.title_of_test_at(body, line) == (
            "satisfies REQ-11 (row 150): replay scores hold (REQ-11)"
        )
        assert typescript_bodies.title_of_test_at(body, 1) == "the body's line 1"

    def test_where_a_type_is_declared(self, tmp_path):
        root = _target(tmp_path, None)
        (root / "web" / "shared" / "other.ts").write_text(
            "export type Score = number;\nexport const Scoreboard = 1;\n", encoding="utf-8",
        )
        assert typescript_bodies.declared_in(root, "Score") == [
            "web/shared/other.ts", "web/shared/scoring.ts",
        ]
        assert typescript_bodies.declared_in(root, "Scoreboard") == []

    def test_the_project_and_its_compiler(self, tmp_path):
        root = _target(tmp_path, None)
        assert typescript_bodies.project_of(root, "web/tests/replay.test.ts") == (root / "web").resolve()
        assert typescript_bodies.typescript_compiler(root / "web", root) is None
        compiler = root / "node_modules" / "typescript" / "bin" / "tsc"
        compiler.parent.mkdir(parents=True)
        compiler.write_text("", encoding="utf-8")
        assert typescript_bodies.typescript_compiler(root / "web", root) == compiler.resolve()

    @pytest.mark.parametrize("name, bare", [
        ("Score", True), ("Score<number>", False), ("{ a: number; }", False),
        ("string[]", False), ("A | B", False),
    ])
    def test_only_a_bare_type_name_is_looked_up(self, name, bare):
        assert typescript_bodies.is_bare_type_name(name) is bare

    def test_a_compiler_that_cannot_be_read_cannot_check(self, tmp_path):
        root = _target(tmp_path, None)
        compiler = root / "web" / "node_modules" / "typescript" / "bin" / "tsc"
        compiler.parent.mkdir(parents=True)
        compiler.write_text("process.exit(7);\n", encoding="utf-8")
        if shutil.which("node") is None:
            pytest.skip("node is not on this machine")
        with pytest.raises(CompletenessCannotCheck, match="exited 7"):
            check_spec_typescript_tests_read_real_members(
                _spec("    expect(score.cost_usd).toBe(1);"), [], str(root),
            )
        assert not list((root / "web" / "tests").glob(".az-spec-probe-*"))
        assert not list((root / "web").glob("tsconfig.az-spec-probe-*"))
