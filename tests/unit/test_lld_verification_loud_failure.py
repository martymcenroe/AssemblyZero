"""The LLD verification gate never skips its path check (ADR 0236, #3585).

``run_verification_gate`` checked that the LLD path lies inside the project only
when a ``project_root`` was passed. Without one the security check was skipped
and the gate went on to pass the file, so a check that never ran read as a
pass. The check now always runs, on the project root given or on the current
directory, which is what ``validate_lld_path`` documents as its default.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import pytest

from assemblyzero.utils.lld_verification import (
    LLDVerificationError,
    run_verification_gate,
)

APPROVED = (
    "# LLD\n\n"
    "<sub>**Gemini Review:** APPROVED | **Model:** gemini | **Date:** 2026-01-01</sub>\n"
)


def test_307_no_project_root_still_checks_the_path(tmp_path, monkeypatch, operator_alerts):
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "elsewhere" / "LLD-1.md"
    outside.parent.mkdir()
    outside.write_text(APPROVED, encoding="utf-8")
    monkeypatch.chdir(project)

    with pytest.raises(LLDVerificationError) as excinfo:
        run_verification_gate(outside)

    assert excinfo.value.error_type == "security"


def test_307_no_project_root_passes_a_path_inside_the_current_directory(
    tmp_path, monkeypatch, operator_alerts
):
    lld = tmp_path / "docs" / "lld" / "LLD-1.md"
    lld.parent.mkdir(parents=True)
    lld.write_text(APPROVED, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = run_verification_gate(lld)

    assert result["is_valid"] is True


def test_307_an_explicit_project_root_is_still_honoured(tmp_path, operator_alerts):
    lld = tmp_path / "LLD-1.md"
    lld.write_text(APPROVED, encoding="utf-8")

    assert run_verification_gate(lld, tmp_path)["is_valid"] is True
