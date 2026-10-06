"""The fleet merge driver is how a workflow lands a PR (#3704)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from assemblyzero.core import merge_driver as md

DRIVER_OUTPUT = """Worktree of /repo
Repo: owner/name  base=main  protection=protected
pushed 42-lld
created PR #77
PR #77 mergeable_state=clean -> ready
merged PR #77
squash SHA 0123abcd
squash 0123abcd confirmed on origin/main
primary main fast-forwarded
worktree /repo-42 removed
branch 42-lld deleted via ADR-0217 graft

[OK] stage=landed
"""


class TestConfiguration:
    def test_unset_is_a_reason_not_a_crash(self):
        reason = md.check_configured({})
        assert "AZ_MERGE_DRIVER is not set" in reason
        assert "gh pr create" in reason

    def test_a_path_that_is_no_file_is_a_reason(self, tmp_path):
        reason = md.check_configured({md.DRIVER_ENV: str(tmp_path / "missing.py")})
        assert "names no file" in reason

    def test_a_file_is_configured(self, tmp_path):
        driver = tmp_path / "tracked_pr_land.py"
        driver.write_text("", encoding="utf-8")
        assert md.check_configured({md.DRIVER_ENV: str(driver)}) is None
        assert md.driver_path({md.DRIVER_ENV: str(driver)}) == driver

    def test_driver_path_raises_with_the_reason(self):
        with pytest.raises(md.MergeDriverError, match="not set"):
            md.driver_path({})


class TestArgv:
    def test_the_no_issue_form(self, tmp_path):
        argv = md.build_argv(
            tmp_path / "d.py", worktree=tmp_path / "wt", branch="42-lld",
            title="docs: add LLD-42 (Ref #42)", body_file=tmp_path / "body.md",
            no_issue=True, base="main", python="/usr/bin/python3",
        )
        assert argv == [
            "/usr/bin/python3", str(tmp_path / "d.py"),
            "--repo", str((tmp_path / "wt").resolve()),
            "--branch", "42-lld",
            "--title", "docs: add LLD-42 (Ref #42)",
            "--body-file", str((tmp_path / "body.md").resolve()),
            "--no-issue",
            "--base", "main",
        ]

    def test_the_issue_form(self, tmp_path):
        argv = md.build_argv(
            tmp_path / "d.py", worktree=tmp_path, branch="b", title="t (Closes #9)",
            body_file=tmp_path / "b.md", issue=9, python="py",
        )
        assert argv[-2:] == ["--issue", "9"]
        assert "--base" not in argv

    def test_exactly_one_of_issue_and_no_issue(self, tmp_path):
        with pytest.raises(ValueError):
            md.build_argv(tmp_path, worktree=tmp_path, branch="b", title="t", body_file=tmp_path)
        with pytest.raises(ValueError):
            md.build_argv(tmp_path, worktree=tmp_path, branch="b", title="t",
                          body_file=tmp_path, issue=1, no_issue=True)


class TestOutput:
    def test_the_drivers_lines_are_read_back(self):
        assert md.parse_output(DRIVER_OUTPUT) == (77, "0123abcd", True)

    def test_a_run_that_did_not_land_says_so(self):
        text = DRIVER_OUTPUT.replace("[OK] stage=landed", "[FAIL] stage=merge")
        assert md.parse_output(text) == (77, "0123abcd", False)


class TestLand:
    def _driver(self, tmp_path: Path) -> dict[str, str]:
        driver = tmp_path / "tracked_pr_land.py"
        driver.write_text("", encoding="utf-8")
        return {md.DRIVER_ENV: str(driver)}

    def test_a_landing_is_reported(self, tmp_path):
        seen: dict = {}

        def runner(argv, **kwargs):
            seen["argv"] = argv
            return subprocess.CompletedProcess(argv, 0, stdout=DRIVER_OUTPUT, stderr="")

        landing = md.land(
            worktree=tmp_path, branch="42-lld", title="t (Ref #42)",
            body_file=tmp_path / "b.md", no_issue=True, base="main",
            runner=runner, environ=self._driver(tmp_path),
        )
        assert landing.pr_number == 77
        assert landing.pr_url == "#77"
        assert landing.squash_sha == "0123abcd"
        assert seen["argv"][1].endswith("tracked_pr_land.py")
        assert "--no-issue" in seen["argv"]
        assert not any(a == "gh" for a in seen["argv"]), "nothing here calls gh"

    def test_a_refusal_is_the_drivers_output_not_a_retry(self, tmp_path):
        calls = []

        def runner(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(
                argv, 1, stdout="PRE-FLIGHT FAILED: parasitic `Closes #543` in body", stderr="",
            )

        with pytest.raises(md.MergeDriverError, match="PRE-FLIGHT FAILED"):
            md.land(
                worktree=tmp_path, branch="b", title="t", body_file=tmp_path / "b.md",
                issue=5, runner=runner, environ=self._driver(tmp_path),
            )
        assert len(calls) == 1

    def test_exit_zero_without_the_landed_line_is_not_a_landing(self, tmp_path):
        def runner(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, stdout="created PR #3\n", stderr="")

        with pytest.raises(md.MergeDriverError, match="did not land"):
            md.land(
                worktree=tmp_path, branch="b", title="t", body_file=tmp_path / "b.md",
                issue=5, runner=runner, environ=self._driver(tmp_path),
            )

    def test_an_unconfigured_driver_never_runs_anything(self, tmp_path):
        def runner(argv, **kwargs):  # pragma: no cover
            raise AssertionError("the runner must not be reached")

        with pytest.raises(md.MergeDriverError, match="not set"):
            md.land(worktree=tmp_path, branch="b", title="t", body_file=tmp_path,
                    issue=1, runner=runner, environ={})
