"""templates/wiki_page.py under standard 0034, one test per sweep site (#3585).

N8 writes a wiki page from the LLD and links it from the wiki's sidebar. An
LLD with no overview (120) gave a page whose overview read "*Overview not
extracted from LLD.*"; it now raises ValueError naming the feature, the issue
and the section headings searched, after an ERROR line, and writes nothing.
A wiki with no `_Sidebar.md` (169) returned False, the same answer as "the
page is already linked", so N8 could not say which. It now returns None, a
legitimate absence kept quiet (N8's ledger row 289: most repositories have no
wiki sidebar), and N8 names it; False means only "already linked".

Every test writes under a temporary directory. Line numbers in the names are
ledger 0908's, at its base `79e18ad1`.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.testing.templates import wiki_page

LLD = "# Test Feature\n\n## 1. Overview\n\nThis is a test feature for documentation.\n"


class TestNoOverview:
    def test_120_an_lld_with_no_overview_raises_and_writes_nothing(self, tmp_path, capsys):
        with pytest.raises(ValueError, match="overview") as excinfo:
            wiki_page.generate_wiki_page(
                feature_name="Test Feature", lld_content="# Feature\n\nDetailed description here.",
                issue_number=42, repo_root=tmp_path,
            )

        assert "#42" in str(excinfo.value)
        assert not (tmp_path / "wiki").exists()
        assert "ERROR" in capsys.readouterr().err

    def test_an_lld_with_an_overview_is_written_from_it(self, tmp_path, capsys, operator_alerts):
        """Kept: the overview is the LLD's own, quietly."""
        path = wiki_page.generate_wiki_page(
            feature_name="Test Feature", lld_content=LLD, issue_number=42, repo_root=tmp_path,
        )

        content = path.read_text(encoding="utf-8")
        assert "This is a test feature for documentation." in content
        assert "not extracted" not in content
        assert "ERROR" not in capsys.readouterr().err
        assert operator_alerts == []


class TestTheSidebar:
    def _page(self, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        page = wiki / "New-Feature.md"
        page.write_text("# New Feature", encoding="utf-8")
        return page

    def test_169_a_wiki_with_no_sidebar_is_none_not_already_linked(
        self, tmp_path, capsys, operator_alerts
    ):
        page = self._page(tmp_path)

        assert wiki_page.update_wiki_sidebar(page) is None
        assert not (page.parent / "_Sidebar.md").exists()
        assert "ERROR" not in capsys.readouterr().err
        assert operator_alerts == []

    def test_a_page_already_linked_is_false_and_quiet(self, tmp_path, capsys, operator_alerts):
        """Kept: False means the sidebar already links the page."""
        page = self._page(tmp_path)
        (page.parent / "_Sidebar.md").write_text(
            "### Reference\n\n- [New-Feature](New-Feature)\n", encoding="utf-8",
        )

        assert wiki_page.update_wiki_sidebar(page) is False
        assert "ERROR" not in capsys.readouterr().err
        assert operator_alerts == []

    def test_a_new_page_is_linked(self, tmp_path):
        page = self._page(tmp_path)
        sidebar = page.parent / "_Sidebar.md"
        sidebar.write_text("### Reference\n\n- [Home](Home)\n", encoding="utf-8")

        assert wiki_page.update_wiki_sidebar(page) is True
        assert "- [New Feature](New-Feature)" in sidebar.read_text(encoding="utf-8")
