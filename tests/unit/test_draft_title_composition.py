"""The drafter is not handed a title that fights the template (#2234).

The LLD template's first line is ``# {IssueID} - Feature: {Title}``, so the
template supplies the "Feature:" label. Handing it an issue title that already
begins with a conventional-commit type produced, on every draft of
run-issue7-234943 (boostgauge, 2026-08-11):

    # Issue #7 - Feature: feat: configuration file and CLI arguments

Cosmetic, and the smaller half of #2234 — but the prefix is the commit
convention's, not the document's, and it carries nothing the drafter needs.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.requirements.nodes.generate_draft import (
    _build_prompt,
    strip_conventional_commit_prefix,
)


class TestStripConventionalCommitPrefix:
    @pytest.mark.parametrize(
        "title,expected",
        [
            # The observed case, from boostgauge #7.
            (
                "feat: configuration file and CLI arguments",
                "configuration file and CLI arguments",
            ),
            ("fix: crash on empty config", "crash on empty config"),
            ("chore: bump deps", "bump deps"),
            ("docs: explain the gate", "explain the gate"),
            # Scoped and breaking-change forms.
            ("feat(config): add a flag", "add a flag"),
            ("fix(api)!: drop the legacy route", "drop the legacy route"),
            ("REFACTOR: rename the node", "rename the node"),
            # Leading whitespace is the author's slip, not a reason to skip.
            ("  feat: a thing", "a thing"),
        ],
    )
    def test_strips_the_type(self, title, expected):
        assert strip_conventional_commit_prefix(title) == expected

    @pytest.mark.parametrize(
        "title",
        [
            # Not a conventional-commit type — this is prose with a colon, and
            # rewriting it would silently damage the title.
            "config: reload on SIGHUP",
            "Feature: configuration file",
            "windows: paths are backslashed",
            # No colon at all.
            "configuration file and CLI arguments",
            # A type-like word that is not the prefix.
            "make the fix: apply it twice",
        ],
    )
    def test_leaves_everything_else_alone(self, title):
        assert strip_conventional_commit_prefix(title) == title

    def test_strips_only_the_first(self):
        """A title is not a commit message; the second colon is the author's."""
        assert (
            strip_conventional_commit_prefix("feat: fix: the thing")
            == "fix: the thing"
        )

    @pytest.mark.parametrize("title", ["", None])
    def test_tolerates_an_absent_title(self, title):
        assert strip_conventional_commit_prefix(title) == title


class TestPromptComposition:
    @staticmethod
    def _state(issue_title: str) -> dict:
        return {
            "workflow_type": "lld",
            "issue_number": 7,
            "issue_title": issue_title,
            "issue_body": "the issue body",
            "current_draft": "",
            "verdict_history": [],
            "validation_errors": [],
            "user_feedback": "",
            "target_repo": "",
        }

    def test_the_drafter_never_sees_the_doubled_prefix(self):
        """The composed input, against the real boostgauge #7 title."""
        prompt = _build_prompt(
            self._state("feat: configuration file and CLI arguments"),
            template="# {IssueID} - Feature: {Title}\n",
            workflow_type="lld",
        )

        assert "# Issue #7: configuration file and CLI arguments" in prompt
        assert "feat:" not in prompt

    def test_a_title_needing_no_strip_is_unchanged(self):
        prompt = _build_prompt(
            self._state("configuration file and CLI arguments"),
            template="# {IssueID} - Feature: {Title}\n",
            workflow_type="lld",
        )

        assert "# Issue #7: configuration file and CLI arguments" in prompt

    def test_the_issue_workflow_is_untouched(self):
        """Issue drafting reads brief_content and has no issue_title path."""
        state = self._state("feat: a thing")
        state["workflow_type"] = "issue"
        state["brief_content"] = "feat: this is the operator's own prose"

        prompt = _build_prompt(state, template="tpl\n", workflow_type="issue")

        assert "feat: this is the operator's own prose" in prompt
