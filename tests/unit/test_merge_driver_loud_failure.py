"""merge_driver.py under standard 0034, one test per sweep site (#3781).

A landing that names no PR number or no squash SHA used to be returned as a
success with an empty PR URL, and the caller recorded a landed stage it could
not point at. It now raises ``MergeDriverError``, which every caller turns
into a failed stage, a stopped finish or a git error. The driver names the PR
on one of four fixed lines (created, reused, merged, or already merged with
this tip), so each is read; a rerun that reuses its open PR is not a failure.
Line numbers in the names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from assemblyzero.core import merge_driver as md

LANDED = "[OK] stage=landed"


def _environ(tmp_path: Path) -> dict[str, str]:
    driver = tmp_path / "tracked_pr_land.py"
    driver.write_text("", encoding="utf-8")
    return {md.DRIVER_ENV: str(driver)}


def _land(tmp_path: Path, stdout: str) -> md.Landing:
    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    return md.land(
        worktree=tmp_path, branch="42-impl", title="t (Closes #42)",
        body_file=tmp_path / "b.md", issue=42, runner=runner,
        environ=_environ(tmp_path),
    )


class TestALandingMustNameWhatLanded:
    def test_163_a_landing_with_no_pr_number_raises(self, tmp_path):
        with pytest.raises(md.MergeDriverError, match="no PR number") as raised:
            _land(tmp_path, f"pushed 42-impl\nsquash SHA 0123abcd\n{LANDED}\n")
        assert "42-impl" in str(raised.value)
        assert "squash SHA 0123abcd" in str(raised.value), "the driver's output travels"

    def test_163_a_landing_with_no_squash_sha_raises(self, tmp_path):
        with pytest.raises(md.MergeDriverError, match="no squash SHA"):
            _land(tmp_path, f"created PR #77\nmerged PR #77\n{LANDED}\n")

    def test_163_a_rerun_that_reuses_its_open_pr_is_read_back(self, tmp_path):
        landing = _land(
            tmp_path,
            f"reusing open PR #77\nmerged PR #77\nsquash SHA 0123abcd\n{LANDED}\n",
        )
        assert landing.pr_number == 77
        assert landing.squash_sha == "0123abcd"

    def test_163_a_rerun_after_the_merge_is_read_back(self, tmp_path):
        landing = _land(
            tmp_path,
            "PR #77 from 42-impl already merged with this tip; skipping push, PR "
            "and merge, and finishing only the cleanup it owes\n"
            f"squash SHA 0123abcd\n{LANDED}\n",
        )
        assert landing.pr_number == 77


def test_a_full_landing_is_reported():
    """Kept: the driver's normal output is a landing with both facts."""
    output = f"created PR #77\nmerged PR #77\nsquash SHA 0123abcd\n{LANDED}\n"
    assert md.parse_output(output) == (77, "0123abcd", True)
