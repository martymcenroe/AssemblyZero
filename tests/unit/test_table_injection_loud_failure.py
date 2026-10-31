"""Source-table injection under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (base ``79e18ad1``), for
``assemblyzero/workflows/requirements/table_injection.py``. A table whose
header or rows lie outside the source raises, where it was clamped and a
partial table injected as "verbatim". The append when the LLD has no Section 3
is compliant and pinned.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.requirements import table_injection
from assemblyzero.workflows.requirements.form_check import RawTable


def test_120_a_table_running_past_the_source_raises():
    body = "| ID | Element |\n|---|---|\n| S1 | dial |\n"
    table = RawTable(line_no=1, header=["ID", "Element"],
                     rows=[["S1", "dial"], ["S2", "ring"], ["S3", "ticks"]])
    with pytest.raises(ValueError, match="past the end") as raised:
        table_injection.source_table_text(body, table)
    assert "line 1" in str(raised.value)


def test_120_a_line_number_before_the_source_raises():
    table = RawTable(line_no=0, header=["ID"], rows=[])
    with pytest.raises(ValueError, match="line 0"):
        table_injection.source_table_text("| ID |\n|---|\n", table)


def test_a_table_inside_the_source_is_sliced_verbatim():
    """Kept: byte-verbatim slicing is the point of the module."""
    body = "intro\n| ID | Element |\n|---|---|\n| S1 | dial `#0A0A0C` |\ntail\n"
    table = RawTable(line_no=2, header=["ID", "Element"], rows=[["S1", "dial"]])
    assert table_injection.source_table_text(body, table) == (
        "| ID | Element |\n|---|---|\n| S1 | dial `#0A0A0C` |"
    )


def test_184_no_section_3_appends_at_the_end():
    """Compliant, pinned: the manifest compiler finds the table anywhere."""
    lld = "# 42 - Feature\n\n## 1. Context\n\nprose\n"
    assert table_injection.apply_injection(lld, "BLOCK").rstrip().endswith("BLOCK")
