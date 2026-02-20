"""Tests for tools/audit_schedule_check.py — audit schedule compliance checker."""

import textwrap
from datetime import datetime
from pathlib import Path

import pytest

from tools.audit_schedule_check import (
    check_audit_schedule,
    detect_audit_index,
    get_latest_audit_date,
    parse_frequency_matrix,
    to_project_number,
)


# --- detect_audit_index ---


def test_detect_index_assemblyzero(tmp_path):
    """AssemblyZero uses 0800 numbering."""
    audits = tmp_path / "audits"
    audits.mkdir()
    (audits / "0800-audit-index.md").write_text("# Index")

    path, base, pad = detect_audit_index(tmp_path)
    assert path is not None
    assert base == 800
    assert pad == 4


def test_detect_index_aletheia(tmp_path):
    """Aletheia uses 10800 numbering."""
    audits = tmp_path / "audits"
    audits.mkdir()
    (audits / "10800-audit-index.md").write_text("# Index")

    path, base, pad = detect_audit_index(tmp_path)
    assert path is not None
    assert base == 10800
    assert pad == 5


def test_detect_index_no_audits_dir(tmp_path):
    """Returns None when docs/audits/ doesn't exist."""
    path, base, pad = detect_audit_index(tmp_path)
    assert path is None
    assert base is None
    assert pad is None


def test_detect_index_no_index_file(tmp_path):
    """Returns None when no audit-index.md is found."""
    audits = tmp_path / "audits"
    audits.mkdir()
    (audits / "0809-some-audit.md").write_text("not an index")

    path, base, pad = detect_audit_index(tmp_path)
    assert path is None


# --- parse_frequency_matrix ---


SAMPLE_INDEX = textwrap.dedent("""\
    # Audit Index

    ## 5. Frequency Matrix

    ### 5.1 By Frequency

    | Frequency | Audits |
    |-----------|--------|
    | **Per PR** | 0813 |
    | **Weekly** | 0816, 0828 |
    | **Monthly + on change** | 0811, 0817 |
    | **Monthly** | 0815, 0821 |
    | **Quarterly** | 0809, 0810, 0899 |
    | **On Event** | 0823, 0824 |
    | **Ultimate** | 0801, 0802 |

    ### 5.2 Calendar View
""")


def test_parse_frequency_matrix():
    """Parses weekly, monthly, quarterly; skips per-pr, on-event, ultimate."""
    result = parse_frequency_matrix(SAMPLE_INDEX)

    assert result["0816"] == "weekly"
    assert result["0828"] == "weekly"
    assert result["0811"] == "monthly"
    assert result["0817"] == "monthly"
    assert result["0815"] == "monthly"
    assert result["0821"] == "monthly"
    assert result["0809"] == "quarterly"
    assert result["0810"] == "quarterly"
    assert result["0899"] == "quarterly"

    # Skipped categories
    assert "0813" not in result  # per pr
    assert "0823" not in result  # on event
    assert "0801" not in result  # ultimate


def test_parse_frequency_matrix_empty():
    """Returns empty dict when no frequency section found."""
    result = parse_frequency_matrix("# No frequency section here")
    assert result == {}


def test_parse_frequency_matrix_starred_audits():
    """Handles asterisk-suffixed audit numbers (under development)."""
    content = textwrap.dedent("""\
        ### 5.1 By Frequency

        | Frequency | Audits |
        |-----------|--------|
        | **Weekly** | 0816, 0841*, 0842* |
    """)
    result = parse_frequency_matrix(content)
    assert result["0816"] == "weekly"
    assert result["0841"] == "weekly"
    assert result["0842"] == "weekly"


# --- to_project_number ---


def test_to_project_number_assemblyzero():
    """AssemblyZero: 0809 stays 0809."""
    assert to_project_number("0809", 800, 4) == "0809"
    assert to_project_number("0816", 800, 4) == "0816"
    assert to_project_number("0899", 800, 4) == "0899"


def test_to_project_number_aletheia():
    """Aletheia: 0809 becomes 10809."""
    assert to_project_number("0809", 10800, 5) == "10809"
    assert to_project_number("0816", 10800, 5) == "10816"
    assert to_project_number("0899", 10800, 5) == "10899"


# --- get_latest_audit_date ---


def test_get_latest_audit_date():
    """Extracts most recent date from audit record table."""
    content = textwrap.dedent("""\
        ## 7. Audit Record

        | Date | Auditor | Findings Summary | Issues Created |
        |------|---------|------------------|----------------|
        | 2026-01-10 | Claude | PASS | None |
        | 2026-02-15 | Claude | PASS | None |
        | 2026-01-25 | Claude | PASS | None |
    """)
    result = get_latest_audit_date(content)
    assert result == datetime(2026, 2, 15)


def test_get_latest_audit_date_no_section():
    """Returns None when no Audit Record section exists."""
    assert get_latest_audit_date("# Some other content") is None


def test_get_latest_audit_date_empty_table():
    """Returns None when Audit Record has no data rows."""
    content = textwrap.dedent("""\
        ## 7. Audit Record

        | Date | Auditor | Findings Summary |
        |------|---------|------------------|
    """)
    assert get_latest_audit_date(content) is None


# --- check_audit_schedule ---


def test_check_ok(tmp_path):
    """Audit run recently is OK."""
    audit_file = tmp_path / "0809-audit.md"
    audit_file.write_text(textwrap.dedent("""\
        ## 7. Audit Record

        | Date | Auditor | Findings |
        |------|---------|----------|
        | 2026-02-18 | Claude | PASS |
    """))
    result = check_audit_schedule("0809", "quarterly", audit_file, datetime(2026, 2, 20))
    assert result["status"] == "ok"
    assert result["days_since"] == 2


def test_check_warn(tmp_path):
    """Audit approaching deadline gets a warning."""
    audit_file = tmp_path / "0816-audit.md"
    audit_file.write_text(textwrap.dedent("""\
        ## 7. Audit Record

        | Date | Auditor | Findings |
        |------|---------|----------|
        | 2026-02-14 | Claude | PASS |
    """))
    # 6 days ago for a weekly audit (warn threshold = 5)
    result = check_audit_schedule("0816", "weekly", audit_file, datetime(2026, 2, 20))
    assert result["status"] == "warn"


def test_check_block(tmp_path):
    """Overdue audit blocks."""
    audit_file = tmp_path / "0816-audit.md"
    audit_file.write_text(textwrap.dedent("""\
        ## 7. Audit Record

        | Date | Auditor | Findings |
        |------|---------|----------|
        | 2026-02-01 | Claude | PASS |
    """))
    # 19 days ago for weekly (block threshold = 7)
    result = check_audit_schedule("0816", "weekly", audit_file, datetime(2026, 2, 20))
    assert result["status"] == "block"


def test_check_no_audit_record(tmp_path):
    """New audit with no record gets a warning, not a block."""
    audit_file = tmp_path / "0809-audit.md"
    audit_file.write_text("# New Audit\n\nNo record yet.\n")
    result = check_audit_schedule("0809", "quarterly", audit_file, datetime(2026, 2, 20))
    assert result["status"] == "warn"
    assert "new audit" in result["reason"]


def test_check_unreadable_file(tmp_path):
    """Missing file returns block status."""
    missing = tmp_path / "does-not-exist.md"
    result = check_audit_schedule("0809", "quarterly", missing, datetime(2026, 2, 20))
    assert result["status"] == "block"
    assert "cannot read" in result["reason"]


# --- Integration: end-to-end with project detection ---


def test_end_to_end_assemblyzero_numbering(tmp_path):
    """Full flow with AssemblyZero 0xxx numbering."""
    audits = tmp_path / "audits"
    audits.mkdir()

    # Create index with frequency matrix
    (audits / "0800-audit-index.md").write_text(textwrap.dedent("""\
        # Audit Index

        ### 5.1 By Frequency

        | Frequency | Audits |
        |-----------|--------|
        | **Weekly** | 0816 |
    """))

    # Create the audit file with a recent date
    (audits / "0816-audit-permissiveness.md").write_text(textwrap.dedent("""\
        ## 7. Audit Record

        | Date | Auditor | Findings |
        |------|---------|----------|
        | 2026-02-19 | Claude | PASS |
    """))

    path, base, pad = detect_audit_index(tmp_path)
    assert base == 800

    content = path.read_text()
    freq_map = parse_frequency_matrix(content)
    assert freq_map == {"0816": "weekly"}

    project_num = to_project_number("0816", base, pad)
    assert project_num == "0816"

    matches = list(audits.glob(f"{project_num}-*.md"))
    assert len(matches) == 1


def test_end_to_end_aletheia_numbering(tmp_path):
    """Full flow with Aletheia 10xxx numbering."""
    audits = tmp_path / "audits"
    audits.mkdir()

    # Create index with frequency matrix
    (audits / "10800-audit-index.md").write_text(textwrap.dedent("""\
        # Audit Index

        ### 5.1 By Frequency

        | Frequency | Audits |
        |-----------|--------|
        | **Weekly** | 0816 |
        | **Quarterly** | 0809, 0899 |
    """))

    # Create audit files with Aletheia numbering
    (audits / "10816-audit-dependabot-prs.md").write_text(textwrap.dedent("""\
        ## 7. Audit Record

        | Date | Auditor | Findings |
        |------|---------|----------|
        | 2026-02-19 | Claude | PASS |
    """))
    (audits / "10809-audit-security.md").write_text(textwrap.dedent("""\
        ## 7. Audit Record

        | Date | Auditor | Findings |
        |------|---------|----------|
        | 2026-01-10 | Claude | PASS |
    """))
    (audits / "10899-meta-audit.md").write_text(textwrap.dedent("""\
        ## 7. Audit Record

        | Date | Auditor | Findings |
        |------|---------|----------|
        | 2026-02-01 | Claude | PASS |
    """))

    path, base, pad = detect_audit_index(tmp_path)
    assert base == 10800
    assert pad == 5

    content = path.read_text()
    freq_map = parse_frequency_matrix(content)
    assert freq_map == {"0816": "weekly", "0809": "quarterly", "0899": "quarterly"}

    # Verify number conversion
    assert to_project_number("0816", base, pad) == "10816"
    assert to_project_number("0809", base, pad) == "10809"
    assert to_project_number("0899", base, pad) == "10899"

    # All files found with project-specific numbering
    for base_num in freq_map:
        project_num = to_project_number(base_num, base, pad)
        matches = list(audits.glob(f"{project_num}-*.md"))
        assert len(matches) == 1, f"No file found for {project_num} (base: {base_num})"
