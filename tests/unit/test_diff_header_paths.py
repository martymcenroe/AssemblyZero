"""A path read from a unified diff's file header loses git's `a/` or `b/`
prefix, and the halt for an unresolvable framework has a class (#4555).

A spec wrote its change to an existing test file as a git-style diff opening
`--- a/web/tests/replay.test.ts`. N0 read the spec's words for the test files
it names, took `a/web/tests/replay.test.ts` for one, and halted looking for
its runner in a directory named `a`. The halt's class was `unknown`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from assemblyzero.core.halt_node import classify_error
from assemblyzero.core.recovery_plan import generate_recovery_plan
from assemblyzero.utils.diff_headers import header_paths, with_header_paths
from assemblyzero.workflows.testing import framework_detector as fd
from assemblyzero.workflows.testing.nodes.load_lld import (
    _framework_resolution_failed,
    extract_files_to_modify,
    load_lld,
)

TF = fd.TestFramework

#: The change to an existing test file, as a spec's Section 6 writes it.
DIFF = """```diff
--- a/web/tests/replay.test.ts
+++ b/web/tests/replay.test.ts
@@ -1,3 +1,4 @@
 import { describe, it, expect } from "vitest";
+import { total } from "../src/ledger";
 describe("ledger", () => {
```"""

SPEC = """# 9 - Ledger totals

**Status:** APPROVED

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `web/src/ledger.ts` | Modify | The ledger |
| 2 | `web/tests/replay.test.ts` | Modify | Its tests |

## 3. Requirements

1. REQ-1: The ledger sums its entries.

## 6. Change Instructions

### 6.1 `web/tests/replay.test.ts` (Modify)

{diff}

## 10. Test Plan

### test_the_ledger_sums_its_entries
Verify that the ledger sums its entries.
Requirement: REQ-1
"""


def _spec(diff: str = DIFF) -> str:
    return SPEC.format(diff=diff)


def _vitest_in_web(root: Path) -> Path:
    """A target whose web/package.json declares Vitest, and nothing else."""
    web = root / "web"
    (web / "tests").mkdir(parents=True)
    (web / "package.json").write_text(
        json.dumps({
            "scripts": {"test": "vitest run"},
            "devDependencies": {"vitest": "^2.1.0"},
        }),
        encoding="utf-8",
    )
    return root


def _load(root: Path, spec: str) -> dict:
    path = root / "spec-9.md"
    path.write_text(spec, encoding="utf-8")
    return load_lld({"issue_number": 9, "repo_root": str(root), "lld_path": str(path)})


class TestT1ADiffHeaderNamesTheFileItChanges:
    """T1 (R1, R2): N0 and every reader of the spec's test files see the path."""

    def test_n0_resolves_vitest_for_the_file_the_diff_changes(self, tmp_path):
        """Fails on main: N0 halted on `a/web/tests/replay.test.ts`."""
        root = _vitest_in_web(tmp_path)

        result = _load(root, _spec())

        assert result.get("error_message", "") == ""
        assert [(c["framework"], c["working_directory"]) for c in result["framework_configs"]] == [
            ("vitest", "web"),
        ]

    def test_the_resolver_places_vitest_in_web(self, tmp_path):
        root = _vitest_in_web(tmp_path)

        assert fd.resolve_framework_dirs(_spec(), str(root)) == {TF.VITEST: "web"}
        assert fd.runner_for_test_path("web/tests/replay.test.ts", str(root)) == (TF.VITEST, "web")

    def test_every_reader_of_the_spec_test_files_sees_the_path(self, tmp_path):
        root = _vitest_in_web(tmp_path)
        spec = _spec()

        assert fd.named_js_test_paths(spec) == ["web/tests/replay.test.ts"]
        assert fd.named_test_files(spec) == ["web/tests/replay.test.ts"]
        assert fd.framework_source(spec, str(root)) == (
            "the LLD names its test files: web/tests/replay.test.ts"
        )

    def test_a_diff_git_header_names_the_file_too(self):
        diff = "```diff\ndiff --git a/web/tests/replay.test.ts b/web/tests/replay.test.ts\n```"

        assert fd.named_js_test_paths(_spec(diff)) == ["web/tests/replay.test.ts"]

    def test_a_header_whose_path_appears_nowhere_else_is_still_read(self):
        """A test file the spec names only in a diff header is named, unprefixed."""
        text = "--- a/web/tests/other.test.ts\n+++ b/web/tests/other.test.ts\n"

        assert fd.named_js_test_paths(text) == ["web/tests/other.test.ts"]

    @pytest.mark.parametrize("line, paths", [
        ("--- a/web/x.test.ts", ("web/x.test.ts",)),
        ("+++ b/web/x.test.ts", ("web/x.test.ts",)),
        ("diff --git a/web/x.test.ts b/web/x.test.ts", ("web/x.test.ts",)),
        ("diff --git a/web/old.ts b/web/new.ts", ("web/old.ts", "web/new.ts")),
        ("--- a/web/x.test.ts\t2026-11-02 15:00:00.000000000 -0600", ("web/x.test.ts",)),
        ("--- a/web/my file.ts\t", ("web/my file.ts",)),
        ('--- "a/web/caf\\303\\251.ts"', ("web/café.ts",)),
        ("+++ b/web/x.test.ts\r", ("web/x.test.ts",)),
        ("--- web/x.test.ts", ("web/x.test.ts",)),
        ("diff --git web/x.ts web/x.ts", ("web/x.ts",)),
    ])
    def test_each_header_form_names_its_path_with_one_prefix_off(self, line, paths):
        assert header_paths(line) == paths

    def test_exactly_one_prefix_comes_off(self):
        assert header_paths("--- a/a/b.ts") == ("a/b.ts",)
        assert header_paths("+++ b/b/c.ts") == ("b/c.ts",)
        assert header_paths("diff --git a/a/b.ts b/a/b.ts") == ("a/b.ts",)


class TestT2APathUnderADirectoryNamedAKeepsIt:
    """T2 (R3): only a diff header loses a prefix."""

    LLD = (
        "## 2.1 Files Changed\n"
        "| File | Change Type | Description |\n"
        "|------|-------------|-------------|\n"
        "| `a/b.ts` | Add | a module |\n"
        "| `a/b.test.ts` | Add | its tests |\n"
    )

    def test_a_section_2_1_entry_a_b_ts_keeps_its_path(self):
        assert with_header_paths(self.LLD) == self.LLD
        assert [f["path"] for f in extract_files_to_modify(self.LLD)] == ["a/b.ts", "a/b.test.ts"]
        assert fd.named_test_files(self.LLD) == ["a/b.test.ts"]

    @pytest.mark.parametrize("line", [
        "a/b.ts",
        "| 1 | `a/b.ts` | Add | a module |",
        "See a/b.ts and b/c.ts.",
        "    --- a/b.ts",
        "--- a/b.ts was removed",
        "---",
        "--- ",
        "diff --git",
        "-- a/b.ts",
    ])
    def test_a_line_that_is_not_a_header_is_not_altered(self, line):
        assert header_paths(line) is None
        assert with_header_paths(line) == line

    def test_a_dashed_line_without_its_plus_line_is_not_a_header(self):
        """A unified diff names its old file and its new one on adjacent lines;
        a `---` line alone is prose, or a removed line of the diff's body."""
        text = "--- a/b.test.ts\nsomething else\n"

        assert with_header_paths(text) == text
        assert fd.named_test_files(text) == ["a/b.test.ts"]

    def test_a_plus_line_without_its_dashed_line_is_not_a_header(self):
        text = "context\n+++ b/c.test.ts\n"

        assert with_header_paths(text) == text


class TestT3DevNullNamesNoFile:
    """T3 (R1): `/dev/null` is never taken as a path."""

    def test_dev_null_yields_no_path(self):
        assert header_paths("--- /dev/null") == ()
        assert header_paths("+++ /dev/null") == ()

    def test_a_new_file_s_header_names_only_the_new_file(self):
        text = "--- /dev/null\n+++ b/web/tests/new.test.ts\n@@ -0,0 +1 @@\n+x\n"

        assert with_header_paths(text) == "web/tests/new.test.ts\n@@ -0,0 +1 @@\n+x\n"
        assert fd.named_js_test_paths(text) == ["web/tests/new.test.ts"]

    def test_a_deleted_file_s_header_names_only_the_old_file(self):
        text = "--- a/web/tests/gone.test.ts\n+++ /dev/null\n"

        assert with_header_paths(text) == "web/tests/gone.test.ts\n"


class TestT4TheUnresolvableFrameworkHaltHasAClass:
    """T4 (R4): the halt is `framework_unresolved`, never `unknown`."""

    def test_the_halt_has_a_named_class(self):
        error = fd.FrameworkResolutionError(
            "the LLD names web/tests/x.test.ts, and no directory that holds it "
            "declares a JavaScript test runner (searched: web/tests, web, .)"
        )

        message = _framework_resolution_failed(9, error)["error_message"]

        assert classify_error(message) == "framework_unresolved"

    def test_a_path_that_reads_like_another_class_does_not_take_it(self):
        """The message quotes paths; `preflight` in one is not a preflight halt."""
        error = fd.FrameworkResolutionError("the LLD names web/preflight.test.ts")

        message = _framework_resolution_failed(9, error)["error_message"]

        assert classify_error(message) == "framework_unresolved"

    def test_n0_halts_with_that_class_when_no_directory_declares_a_runner(self, tmp_path):
        (tmp_path / "web" / "tests").mkdir(parents=True)

        result = _load(tmp_path, _spec())

        assert "web/tests/replay.test.ts" in result["error_message"]
        assert "a/web" not in result["error_message"]
        assert classify_error(result["error_message"]) == "framework_unresolved"

    def test_its_recovery_plan_says_what_to_change_and_is_not_transient(self):
        message = _framework_resolution_failed(
            9, fd.FrameworkResolutionError("the LLD names web/tests/x.test.ts"),
        )["error_message"]

        plan = generate_recovery_plan(
            9, "testing", "N0_load_lld", classify_error(message), message, {},
        )

        assert plan.error_type == "framework_unresolved"
        assert plan.is_transient is False
        assert plan.recommendation.startswith("Non-transient:")
        assert "the LLD names web/tests/x.test.ts" in plan.recommendation
