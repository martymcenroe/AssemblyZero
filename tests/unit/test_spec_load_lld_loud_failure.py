"""The spec workflow's N0 load_lld under standard 0034 (#3585).

Named ``test_spec_...`` because the testing workflow has a node module of the
same name. Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md. Every failure returns an
``error_message`` naming the issue and the LLD's path, which
``route_after_load`` sends to HALT, and HALT alerts.
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


def _lld(tmp_path, text: str):
    path = tmp_path / "LLD-005.md"
    path.write_text(text, encoding="utf-8")
    return path


def _state(tmp_path, path, **extra) -> dict:
    state = {"issue_number": 5, "lld_path": str(path), "repo_root": str(tmp_path)}
    state.update(extra)
    return state


def _halts(result: dict, *needles: str) -> None:
    message = result["error_message"]
    assert message, "the node must return an error_message"
    assert route_after_load(result) == "HALT"
    for needle in needles:
        assert needle in message, f"{needle!r} not in {message!r}"


class TestTheNodeHalts:
    def test_105_an_lld_without_a_files_changed_table_halts(self, tmp_path):
        path = _lld(tmp_path, HEADER + "No table at all, only prose.\n" * 3 + "\n**Final Status:** APPROVED\n")
        _halts(ll.load_lld(_state(tmp_path, path)), "#5", "Section 2.1", str(path))

    def test_165_an_unrecognised_change_type_halts(self, tmp_path):
        path = _lld(tmp_path, HEADER + TABLE.format(rows="| `src/a.py` | Rename | moved |\n"))
        _halts(ll.load_lld(_state(tmp_path, path)), "#5", "src/a.py", "'Rename'")

    def test_196_approved_mentioned_only_in_passing_is_not_approved(self, tmp_path):
        """A BLOCKED LLD whose review log shows an earlier APPROVED row used to
        pass on the substring alone."""
        text = (
            "# LLD-005: A feature\n\n* **Status:** Blocked (gemini, 2026-10-30)\n\n"
            + TABLE.format(rows=GOOD_ROWS).replace("APPROVED", "BLOCKED")
            + "\n| 1 | 2026-10-29 | APPROVED | gemini |\n"
        )
        _halts(ll.load_lld(_state(tmp_path, _lld(tmp_path, text))), "#5", "not approved")

    def test_226_no_issue_number_halts(self):
        """Compliant, pinned."""
        result = ll.load_lld({"issue_number": 0})
        assert result["error_message"] == "No issue number provided"
        assert route_after_load(result) == "HALT"

    def test_234_a_missing_repo_root_halts(self, tmp_path):
        """It used to fall back to the process's working directory."""
        path = _lld(tmp_path, HEADER + TABLE.format(rows=GOOD_ROWS))
        _halts(ll.load_lld(_state(tmp_path, path, repo_root="")), "#5", "repo_root")

    def test_244_a_missing_lld_halts(self, tmp_path):
        """Compliant, pinned."""
        result = ll.load_lld(_state(tmp_path, tmp_path / "gone.md"))
        _halts(result, "LLD not found for issue #5")

    def test_260_an_lld_that_cannot_be_read_names_issue_path_and_type(self, tmp_path):
        folder = tmp_path / "LLD-005.md"
        folder.mkdir()
        _halts(ll.load_lld(_state(tmp_path, folder)), "#5", str(folder), "IsADirectoryError")

    def test_260_an_lld_that_is_not_utf8_halts(self, tmp_path):
        path = tmp_path / "LLD-005.md"
        path.write_bytes(b"\xff\xfe not utf-8 " * 20)
        _halts(ll.load_lld(_state(tmp_path, path)), "#5", "UnicodeDecodeError")

    def test_266_a_trivial_lld_names_issue_path_and_length(self, tmp_path):
        path = _lld(tmp_path, "# Short\nAPPROVED")
        _halts(ll.load_lld(_state(tmp_path, path)), "#5", str(path), "16 chars")

    def test_274_an_unapproved_lld_halts(self, tmp_path):
        """Compliant, pinned."""
        text = HEADER.replace("Approved", "Pending") + TABLE.format(rows=GOOD_ROWS).replace(
            "APPROVED", "PENDING"
        )
        _halts(ll.load_lld(_state(tmp_path, _lld(tmp_path, text))), "issue #5 is not approved")

    def test_290_a_table_with_no_file_rows_halts(self, tmp_path):
        rows = "| `src/pkg` | Add (Directory) | a directory |\n"
        path = _lld(tmp_path, HEADER + TABLE.format(rows=rows))
        _halts(ll.load_lld(_state(tmp_path, path)), "#5", "no files")

    def test_the_halt_is_loud_on_stderr(self, tmp_path, capsys):
        path = _lld(tmp_path, HEADER + TABLE.format(rows="| `src/a.py` | Rename | moved |\n"))
        ll.load_lld(_state(tmp_path, path))
        assert "ERROR" in capsys.readouterr().err

    def test_a_good_lld_loads(self, tmp_path):
        path = _lld(tmp_path, HEADER + TABLE.format(rows=GOOD_ROWS))
        result = ll.load_lld(_state(tmp_path, path))
        assert result["error_message"] == ""
        assert [f["change_type"] for f in result["files_to_modify"]] == ["Add", "Modify"]


class TestTheParser:
    def test_105_parsing_without_the_table_raises(self):
        with pytest.raises(ValueError, match="Section 2.1"):
            ll.parse_files_to_modify("# LLD\n\nNo table here.\n")

    def test_165_an_unknown_change_type_raises(self):
        with pytest.raises(ValueError, match="'unknown'"):
            ll._normalize_change_type("unknown")

    def test_a_directory_row_is_skipped_whatever_its_type(self):
        """Kept: directory rows are not files to specify."""
        rows = "| `src/pkg` | Directory (directory) | a directory |\n" + GOOD_ROWS
        files = ll.parse_files_to_modify(HEADER + TABLE.format(rows=rows))
        assert [f["path"] for f in files] == ["src/a.py", "src/b.py"]


class TestApproval:
    def test_196_the_substring_alone_is_not_approval(self):
        assert ll._check_approved_status("# LLD\n\nReviewer said APPROVED once.\n") is False

    @pytest.mark.parametrize("marker", [
        "* **Status:** Approved (gemini, 2026)\n",
        "**Final Status:** APPROVED\n",
    ])
    def test_an_explicit_marker_is_approval(self, marker):
        """Kept: the two markers embed_review_evidence writes."""
        assert ll._check_approved_status(marker) is True
