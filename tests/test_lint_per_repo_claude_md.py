"""Tests for tools/lint_per_repo_claude_md.py (#1290)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from lint_per_repo_claude_md import (  # noqa: E402
    _strip_identifiers_block,
    detect_drift,
    format_json,
    format_text,
    load_allowlist,
    load_unleashed_assemblyzero,
    scan_fleet,
)


# ────────────────────────────────────────────────────────────────────
# Fixture helpers
# ────────────────────────────────────────────────────────────────────


def make_repo(tmp_path: Path, name: str, claude_md: str | None,
              unleashed: dict | None = None) -> Path:
    """Create a fake repo dir with optional CLAUDE.md and .unleashed.json."""
    repo = tmp_path / name
    repo.mkdir()
    if claude_md is not None:
        (repo / "CLAUDE.md").write_text(claude_md, encoding="utf-8")
    if unleashed is not None:
        (repo / ".unleashed.json").write_text(json.dumps(unleashed), encoding="utf-8")
    return repo


def lean_template(name: str = "test-repo") -> str:
    """Return a 25-line lean CLAUDE.md per ADR 0219 (passes all detectors)."""
    return f"""# CLAUDE.md - {name} Project

You are a team member on the {name} project, not a tool.

## Project Identifiers

- **Repository:** `martymcenroe/{name}`
- **Project Root (Windows):** `C:\\Users\\someone\\Projects\\{name}`
- **Project Root (Unix):** `/c/Users/someone/Projects/{name}`
- **Worktree Pattern:** `{name}-{{IssueID}}`

## Project-Specific Context

_TODO: Add tech stack, architecture, file map, project-type-specific notes,
and any workflow overrides specific to this project. The universal CLAUDE.md
(auto-loaded) covers all fleet-wide rules; this file only adds what is true
for THIS repo specifically._

## Notes

- Some specific note here
- Another note
- Filler to clear the stub threshold
- More filler
- Even more filler so we exceed 20 lines
"""


# ────────────────────────────────────────────────────────────────────
# Marker tests
# ────────────────────────────────────────────────────────────────────


def test_lean_template_passes(tmp_path: Path) -> None:
    """Lean reference template per ADR 0219 must trip zero detectors."""
    # Note: lean template uses C:\Users\someone\ NOT mcwiz, so marker 9 doesn't fire
    repo = make_repo(tmp_path, "lean-repo", lean_template("lean-repo"))
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert result.status == "PASS", f"Expected PASS, got {result.status}, findings: {[(f.marker, f.description) for f in result.findings]}"
    assert result.findings == []


def test_marker_1_false_az_rules_list(tmp_path: Path) -> None:
    content = lean_template() + """

## False claim

The AssemblyZero/CLAUDE.md file contains bash-command rules and visible self-check
patterns plus worktree isolation and decision-making protocol.
"""
    repo = make_repo(tmp_path, "drifted", content)
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert result.status == "DRIFT"
    assert any(f.marker == 1 for f in result.findings)


def test_marker_2_orchestrator_gate(tmp_path: Path) -> None:
    content = lean_template() + """

## PRE-MERGE GATE

Wait for orchestrator review before merging.
"""
    repo = make_repo(tmp_path, "drifted", content)
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert any(f.marker == 2 for f in result.findings)


def test_marker_3_wrong_report_format(tmp_path: Path) -> None:
    content = lean_template() + "\n\nReport filenames are `1{IssueID}-foo.md`.\n"
    repo = make_repo(tmp_path, "drifted", content)
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert any(f.marker == 3 for f in result.findings)


def test_marker_4_session_logs_as_source(tmp_path: Path) -> None:
    content = lean_template() + (
        "\n\nFor cross-session continuity, read docs/session-logs/ first.\n"
    )
    repo = make_repo(tmp_path, "drifted", content)
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert any(f.marker == 4 for f in result.findings)


def test_marker_5_first_read_az(tmp_path: Path) -> None:
    content = lean_template() + "\n\n## FIRST: Read AssemblyZero Core Rules\n"
    repo = make_repo(tmp_path, "drifted", content)
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert any(f.marker == 5 for f in result.findings)


def test_marker_6_az_refs_when_opted_out(tmp_path: Path) -> None:
    content = lean_template() + "\n\nThis repo references AssemblyZero workflows.\n"
    repo = make_repo(
        tmp_path, "opted-out", content,
        unleashed={"assemblyZero": False},
    )
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert any(f.marker == 6 for f in result.findings)


def test_marker_6_skipped_when_no_unleashed_json(tmp_path: Path) -> None:
    """No .unleashed.json = no signal; marker 6 should NOT fire even with AZ refs."""
    content = lean_template() + "\n\nThis repo references AssemblyZero workflows.\n"
    repo = make_repo(tmp_path, "no-config", content)  # no .unleashed.json
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert not any(f.marker == 6 for f in result.findings)


def test_marker_6_skipped_when_opted_in(tmp_path: Path) -> None:
    """assemblyZero=true => AZ refs are legitimate, marker 6 must not fire."""
    content = lean_template() + "\n\nUses AssemblyZero workflows for X.\n"
    repo = make_repo(
        tmp_path, "opted-in", content,
        unleashed={"assemblyZero": True},
    )
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert not any(f.marker == 6 for f in result.findings)


def test_marker_7_universal_dupe_no_override(tmp_path: Path) -> None:
    """Phrases like 'merge sequence' without nearby 'override' qualifier fire."""
    content = lean_template() + (
        "\n\n## Process\n\nFollow the standard merge sequence on every PR.\n"
    )
    repo = make_repo(tmp_path, "drifted", content)
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert any(f.marker == 7 for f in result.findings)


def test_marker_7_skipped_when_override_nearby(tmp_path: Path) -> None:
    """Aletheia-style: 'merge sequence override' must not trip marker 7."""
    content = lean_template() + (
        "\n\n## Override\n\n"
        "This repo overrides the universal merge sequence — use tools/merge_pr.py instead.\n"
    )
    repo = make_repo(tmp_path, "aletheia-like", content)
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert not any(f.marker == 7 for f in result.findings)


def test_marker_8_stub_under_threshold(tmp_path: Path) -> None:
    content = "# CLAUDE.md\n\nStub.\n"  # 3 lines
    repo = make_repo(tmp_path, "stub", content)
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert result.status == "STUB"
    assert any(f.marker == 8 for f in result.findings)


def test_marker_9_hardcoded_mcwiz_path(tmp_path: Path) -> None:
    content = lean_template() + "\n\nSee C:\\Users\\mcwiz\\Projects\\X\\foo.md\n"
    repo = make_repo(tmp_path, "drifted", content)
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert any(f.marker == 9 for f in result.findings)


def test_marker_9_skipped_when_only_in_identifiers(tmp_path: Path) -> None:
    """Scaffolder-emitted path in Identifiers block must NOT trip marker 9 (#1300)."""
    content = """# CLAUDE.md - test Project

You are a team member on the test project, not a tool.

## Project Identifiers

- **Repository:** `martymcenroe/test`
- **Project Root (Windows):** `C:\\Users\\mcwiz\\Projects\\test`
- **Project Root (Unix):** `/c/Users/mcwiz/Projects/test`
- **Worktree Pattern:** `test-{IssueID}`

## Project-Specific Context

Filler so we clear stub threshold.
More filler.
Even more.
Filler line.
Another line.
And another.
And more.
Last filler.
"""
    repo = make_repo(tmp_path, "ident-only", content)
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert not any(f.marker == 9 for f in result.findings), (
        f"Marker 9 fired on Identifiers-only path: {[(f.marker, f.description) for f in result.findings]}"
    )


def test_marker_9_fires_outside_identifiers_even_when_also_inside(tmp_path: Path) -> None:
    """Identifiers + body occurrence => marker 9 fires (on the body one)."""
    content = """# CLAUDE.md - test Project

You are a team member on the test project, not a tool.

## Project Identifiers

- **Repository:** `martymcenroe/test`
- **Project Root (Windows):** `C:\\Users\\mcwiz\\Projects\\test`
- **Project Root (Unix):** `/c/Users/mcwiz/Projects/test`
- **Worktree Pattern:** `test-{IssueID}`

## Notes

For more info see `C:\\Users\\mcwiz\\Projects\\SomeOther\\bar.md` in the body.
Filler to clear stub threshold.
More filler.
And more.
"""
    repo = make_repo(tmp_path, "both", content)
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert any(f.marker == 9 for f in result.findings)


def test_marker_9_fires_when_no_identifiers_heading(tmp_path: Path) -> None:
    """No `## Project Identifiers` heading => no exception, marker 9 fires on any match."""
    content = """# CLAUDE.md - test Project

Body content with no Identifiers heading.

See `C:\\Users\\mcwiz\\Projects\\X\\foo.md` for details.
Filler to clear stub threshold.
More filler.
And more.
And more lines.
Even more.
"""
    repo = make_repo(tmp_path, "no-ident", content)
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert any(f.marker == 9 for f in result.findings)


def test_strip_identifiers_block_removes_section(tmp_path: Path) -> None:
    text = """# Title

Body before.

## Project Identifiers

- a
- b
- c

## Next Section

Body after.
"""
    out = _strip_identifiers_block(text)
    assert "## Project Identifiers" not in out
    assert "- a" not in out
    assert "Body before" in out
    assert "Body after" in out
    assert "## Next Section" in out


def test_strip_identifiers_block_no_heading_returns_unchanged(tmp_path: Path) -> None:
    text = "# Title\n\nBody with no Identifiers heading.\n"
    assert _strip_identifiers_block(text) == text


def test_strip_identifiers_block_at_eof(tmp_path: Path) -> None:
    """Identifiers block at EOF (no following h2) is stripped to EOF."""
    text = """# Title

Body before.

## Project Identifiers

- a
- b
"""
    out = _strip_identifiers_block(text)
    assert "## Project Identifiers" not in out
    assert "- a" not in out
    assert "Body before" in out


def test_missing_claude_md(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "empty", None)  # no CLAUDE.md
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert result.status == "MISSING"
    assert result.findings == []


# ────────────────────────────────────────────────────────────────────
# Helper / config tests
# ────────────────────────────────────────────────────────────────────


def test_load_unleashed_missing(tmp_path: Path) -> None:
    repo = tmp_path / "norepo"
    repo.mkdir()
    assert load_unleashed_assemblyzero(repo) is None


def test_load_unleashed_present(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "r", lean_template(), unleashed={"assemblyZero": True})
    assert load_unleashed_assemblyzero(repo) is True


def test_load_unleashed_missing_key(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "r", lean_template(), unleashed={"other": "thing"})
    assert load_unleashed_assemblyzero(repo) is None


def test_load_allowlist_strips_comments_and_blanks(tmp_path: Path) -> None:
    allow = tmp_path / "allow.txt"
    allow.write_text("# comment\nrepo-a\n\nrepo-b\n# another comment\n", encoding="utf-8")
    assert load_allowlist(allow) == {"repo-a", "repo-b"}


def test_load_allowlist_none_returns_empty() -> None:
    assert load_allowlist(None) == set()


def test_load_allowlist_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_allowlist(tmp_path / "nonexistent.txt")


# ────────────────────────────────────────────────────────────────────
# scan_fleet integration
# ────────────────────────────────────────────────────────────────────


def test_scan_fleet_mixed(tmp_path: Path) -> None:
    """Mixed fleet: one pass, one stub, one missing, one allowlisted."""
    make_repo(tmp_path, "good", lean_template("good"))
    make_repo(tmp_path, "stubby", "# Tiny\n")
    make_repo(tmp_path, "noclaude", None)
    make_repo(tmp_path, "skipme", "# Whatever\n" * 50)
    (tmp_path / ".hidden").mkdir()  # hidden dir; should be ignored

    results = scan_fleet(tmp_path, {"skipme"})
    status_by_name = {r.repo_name: r.status for r in results}
    assert status_by_name["good"] == "PASS"
    assert status_by_name["stubby"] == "STUB"
    assert status_by_name["noclaude"] == "MISSING"
    assert status_by_name["skipme"] == "SKIPPED"
    assert ".hidden" not in status_by_name


# ────────────────────────────────────────────────────────────────────
# Output formatting
# ────────────────────────────────────────────────────────────────────


def test_format_text_summary(tmp_path: Path) -> None:
    make_repo(tmp_path, "good", lean_template())
    make_repo(tmp_path, "stub", "# tiny\n")
    results = scan_fleet(tmp_path, set())
    out = format_text(results)
    assert "good: PASS" in out
    assert "stub: STUB" in out
    assert "Summary:" in out


def test_format_json_is_valid(tmp_path: Path) -> None:
    make_repo(tmp_path, "good", lean_template())
    results = scan_fleet(tmp_path, set())
    parsed = json.loads(format_json(results))
    assert isinstance(parsed, list)
    assert parsed[0]["repo"] == "good"
    assert parsed[0]["status"] == "PASS"
    assert parsed[0]["findings"] == []
