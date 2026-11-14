"""#4274: the spec's N0 halts on a Files Changed row shorter than its header.

A two-cell row of the LLD's Section 2.1 Files Changed table used to be dropped
without a word (or, followed by another row, read across the line break into a
garbled entry), so a file listed with too few cells never reached the spec.
The row now raises at N0, naming the row and the table, and ``load_lld``
returns an ``error_message`` that ``route_after_load`` sends to HALT.
"""
from __future__ import annotations

import importlib

import pytest

from assemblyzero.workflows.implementation_spec.graph import route_after_load

# `nodes/__init__` re-exports the FUNCTION load_lld, which shadows the module
# of the same name, so the module is imported by its dotted path.
ll = importlib.import_module("assemblyzero.workflows.implementation_spec.nodes.load_lld")

HEADER = "# LLD-005: A feature\n\n* **Status:** Approved (gemini, 2026-10-30)\n\n## 1. Context\n\nWhy.\n\n"
TABLE = (
    "### 2.1 Files Changed\n\n"
    "| File | Change Type | Description |\n"
    "|------|-------------|-------------|\n"
    "{rows}"
    "\n**Final Status:** APPROVED\n"
)
GOOD_ROWS = "| `src/a.py` | Add | the new module |\n| `src/b.py` | Modify | extend it |\n"
SHORT_ROW = "| `src/c.py` | Add |"


def _lld(tmp_path, text: str):
    path = tmp_path / "LLD-005.md"
    path.write_text(text, encoding="utf-8")
    return path


def _state(tmp_path, path) -> dict:
    return {"issue_number": 5, "lld_path": str(path), "repo_root": str(tmp_path)}


class TestTheNodeHalts:
    @pytest.mark.parametrize("rows", [
        SHORT_ROW + "\n",
        GOOD_ROWS + SHORT_ROW + "\n",
        SHORT_ROW + "\n" + GOOD_ROWS,
    ], ids=["alone", "last", "first"])
    def test_t1_a_two_cell_row_halts_n0_with_the_row_named(self, tmp_path, rows):
        path = _lld(tmp_path, HEADER + TABLE.format(rows=rows))
        result = ll.load_lld(_state(tmp_path, path))
        message = result["error_message"]
        assert message, "N0 must return an error_message for a two-cell row"
        assert route_after_load(result) == "HALT"
        for needle in ("#5", str(path), "Section 2.1 Files Changed", SHORT_ROW, "2 cells", "3"):
            assert needle in message, f"{needle!r} not in {message!r}"
        assert "files_to_modify" not in result

    def test_the_halt_is_loud_on_stderr(self, tmp_path, capsys):
        path = _lld(tmp_path, HEADER + TABLE.format(rows=SHORT_ROW + "\n"))
        ll.load_lld(_state(tmp_path, path))
        assert SHORT_ROW in capsys.readouterr().err


class TestTheParser:
    def test_a_short_row_raises_naming_the_row_and_the_table(self):
        with pytest.raises(ValueError, match="Section 2.1 Files Changed") as exc:
            ll.parse_files_to_modify(HEADER + TABLE.format(rows=GOOD_ROWS + SHORT_ROW + "\n"))
        assert SHORT_ROW in str(exc.value)

    def test_a_short_directory_row_raises_too(self):
        """The cell count is read before the change type: a short row is short."""
        with pytest.raises(ValueError, match="Section 2.1 Files Changed"):
            ll.parse_files_to_modify(HEADER + TABLE.format(rows="| `src/pkg` | Add (Directory) |\n"))

    def test_a_row_with_an_empty_description_cell_is_full(self):
        """Kept: three cells, one of them empty, is a full row."""
        files = ll.parse_files_to_modify(HEADER + TABLE.format(rows="| `src/a.py` | Add | |\n"))
        assert [(f["path"], f["change_type"]) for f in files] == [("src/a.py", "Add")]

    def test_full_rows_parse_as_before(self):
        files = ll.parse_files_to_modify(HEADER + TABLE.format(rows=GOOD_ROWS))
        assert [(f["path"], f["change_type"]) for f in files] == [
            ("src/a.py", "Add"),
            ("src/b.py", "Modify"),
        ]
