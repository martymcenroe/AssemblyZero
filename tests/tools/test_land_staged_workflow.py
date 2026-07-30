"""Unit tests for tools/land_staged_workflow.py.

Issue #1882. The pure, credential-free parts of the lander: header stripping
and argument derivation. The network path is not exercised here -- it needs a
classic PAT, and per the _pat_session operational rule that decrypt belongs to
the operator, never to a test or an agent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

from land_staged_workflow import (  # noqa: E402
    parse_args,
    strip_header_comment,
    workflow_name,
)

WORKFLOW = "name: tests\non:\n  pull_request:\n"


class TestStripHeaderComment:
    def test_removes_leading_comment_block_and_following_blanks(self):
        staged = (
            "# Staged CI workflow. Lives in docs/ci/ because the fine-grained\n"
            "# PAT cannot push .github/workflows/ files.\n"
            "\n" + WORKFLOW
        )
        assert strip_header_comment(staged) == WORKFLOW

    def test_leaves_a_file_without_a_header_untouched(self):
        assert strip_header_comment(WORKFLOW) == WORKFLOW

    def test_preserves_comments_that_appear_after_content(self):
        """Only the HEADER goes. Inline comments are part of the workflow."""
        staged = "# header\n\nname: tests\n# keep me -- explains the next step\non:\n"
        result = strip_header_comment(staged)
        assert result.startswith("name: tests")
        assert "# keep me" in result

    def test_handles_a_file_that_is_only_comments(self):
        assert strip_header_comment("# a\n# b\n") == ""

    def test_handles_empty_input(self):
        assert strip_header_comment("") == ""

    def test_does_not_strip_indented_yaml_that_merely_contains_a_hash(self):
        staged = 'name: tests\non:\n  pull_request:\n  # trailing note\n'
        assert strip_header_comment(staged) == staged


class TestWorkflowName:
    """#1913. The tool used to poll for a check-run name supplied by the caller.
    Check runs are named after the JOB; `name:` at the top of the file names the
    WORKFLOW. Matching one against the other never succeeded, and the tool then
    reported 'never registered' for ten minutes while the run was failing."""

    def test_parses_the_top_level_name(self):
        assert workflow_name(WORKFLOW, None) == "tests"

    def test_does_not_pick_up_a_job_name(self):
        """The exact confusion that caused the bug: `python` is the job, and the
        check run is named after it -- but the workflow is `tests`."""
        content = "name: tests\non:\n  pull_request:\njobs:\n  python:\n    runs-on: x\n"
        assert workflow_name(content, None) == "tests"

    def test_ignores_indented_name_keys(self):
        """Steps carry their own `name:`; only column zero is the workflow."""
        content = "name: tests\njobs:\n  build:\n    steps:\n      - name: not this\n"
        assert workflow_name(content, None) == "tests"

    def test_strips_quotes(self):
        assert workflow_name('name: "tests"\non:\n', None) == "tests"
        assert workflow_name("name: 'tests'\non:\n", None) == "tests"

    def test_override_wins(self):
        assert workflow_name(WORKFLOW, "something-else") == "something-else"

    def test_missing_name_is_a_clear_error_not_a_silent_guess(self):
        with pytest.raises(SystemExit) as e:
            workflow_name("on:\n  pull_request:\n", None)
        assert "--check" in str(e.value)


class TestParseArgs:
    BASE = [
        "--repo", "EXAMPLE",
        "--issue", "7",
        "--staged", "docs/ci/tests.yml",
        "--workflow", ".github/workflows/tests.yml",
    ]

    def test_branch_is_derived_from_the_issue_when_unset(self):
        assert parse_args(self.BASE).branch == "ci/staged-workflow-7"

    def test_explicit_branch_wins(self):
        cfg = parse_args([*self.BASE, "--branch", "ci/custom"])
        assert cfg.branch == "ci/custom"

    def test_issue_is_an_int_so_the_closes_directive_cannot_be_malformed(self):
        assert parse_args(self.BASE).issue == 7

    def test_defaults_are_conservative(self):
        """The safe defaults: keep nothing staged, stop on red, strip nothing."""
        cfg = parse_args(self.BASE)
        assert cfg.keep_staged is False
        assert cfg.merge_on_red is False, "must not merge a red check by default"
        assert cfg.strip_header_comment is False
        assert cfg.check is None

    def test_check_defaults_to_none_so_the_name_is_derived(self):
        """#1913: a guessed default check name is what let a failing run be
        reported as 'never registered'. The default must be derive-from-file."""
        assert parse_args(self.BASE).check is None

    def test_no_target_repository_is_baked_in(self):
        """#1882: this repo is public and some targets are not, so the target
        must arrive at run time. --repo is required and has no default."""
        with pytest.raises(SystemExit):
            parse_args([
                "--issue", "7",
                "--staged", "docs/ci/tests.yml",
                "--workflow", ".github/workflows/tests.yml",
            ])
