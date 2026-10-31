"""document.py (N8) under standard 0034, one test per sweep site.

N8 writes the run's documentation. Every artifact that raised was printed as
"SKIPPED" on stdout and the run went on, with partial c/p paths; a README the
node decided to update that was not there read as "no update needed". Each
now raises ``DocumentationError`` naming the artifact and the cause, after an
ERROR line on stderr; N8 has no route to HALT, so the raise reaches the run's
entry point, which alerts. A README with no Features section and a wiki with
no sidebar are absences, kept and pinned. Line numbers in the names are ledger
0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

# The nodes package re-exports the node FUNCTION under the module's name.
doc = importlib.import_module("assemblyzero.workflows.testing.nodes.document")

# #3585: the wiki page and the runbook are written from the LLD's own
# sections and raise on an LLD that has none, so this LLD carries them.
LLD = (
    "# 99 - Widget workflow\n\n"
    "<!-- doc-scope: full -->\n<!-- update-readme: true -->\n\n"
    "A new feature: the widget workflow.\n\n"
    "## 1. Overview\n\nThe widget workflow turns widgets into reports.\n\n"
    "## Prerequisites\n\n- Python 3.11\n\n"
    "## Procedure\n\n1. Run the widget workflow.\n\n"
    "## Verification\n\n- The report is written.\n"
)


def _state(tmp_path: Path, **overrides) -> dict:
    audit = tmp_path / "audit"
    audit.mkdir(exist_ok=True)
    state = {
        "issue_number": 99,
        "repo_root": str(tmp_path),
        "lld_content": LLD,
        "audit_dir": str(audit),
        "implementation_files": ["tools/widget.py"],
        "skip_cp_docs": True,
    }
    state.update(overrides)
    return state


@pytest.fixture(autouse=True)
def quiet_templates(monkeypatch, tmp_path):
    """Stand-ins for the lessons template and the execution log, which
    belong to other modules; the artifacts under test are real."""
    lessons = tmp_path / "audit" / "lessons.md"

    def fake_lessons(**kwargs):
        lessons.parent.mkdir(parents=True, exist_ok=True)
        lessons.write_text("lessons", encoding="utf-8")
        return lessons

    monkeypatch.setattr(doc, "generate_lessons_learned", fake_lessons)
    monkeypatch.setattr(doc, "log_workflow_execution", lambda **kwargs: None)


def _readme(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "README.md"
    path.write_text(text, encoding="utf-8")
    return path


def _raise(exc: Exception):
    def fail(*args, **kwargs):
        raise exc
    return fail


# --- line 182: the README the node decided to update is missing --------------


def test_182_a_missing_readme_raises_naming_it(tmp_path):
    with pytest.raises(FileNotFoundError) as raised:
        doc.update_readme(_state(tmp_path), tmp_path)
    assert str(tmp_path / "README.md") in str(raised.value)


def test_182_the_node_stops_on_a_missing_readme(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(doc, "should_generate_wiki", lambda state: False)
    monkeypatch.setattr(doc, "is_operational_feature", lambda state: False)

    with pytest.raises(doc.DocumentationError) as raised:
        doc.document(_state(tmp_path))
    assert "README" in str(raised.value)
    assert str(tmp_path / "README.md") in str(raised.value)
    assert "ERROR [N8]" in capsys.readouterr().err


# --- line 215: the README has no Features section (kept) ---------------------


def test_215_a_readme_with_no_features_section_is_left_alone_and_said(tmp_path, capsys, monkeypatch):
    """A README that keeps no feature list has no list to add to: most of
    the fleet's READMEs, AssemblyZero's among them, have no Features
    section. Left unchanged, and said as that rather than "no update
    needed"."""
    readme = _readme(tmp_path, "# Widget\n\n## Install\n\npip install widget\n")
    before = readme.read_text(encoding="utf-8")
    assert doc.update_readme(_state(tmp_path), tmp_path) is False
    assert readme.read_text(encoding="utf-8") == before

    monkeypatch.setattr(doc, "should_generate_wiki", lambda state: False)
    monkeypatch.setattr(doc, "is_operational_feature", lambda state: False)
    result = doc.document(_state(tmp_path))
    assert result["doc_readme_updated"] is False
    assert "no Features section" in capsys.readouterr().out


def test_a_readme_with_a_features_section_gets_the_entry(tmp_path):
    """Kept: the entry is added under Features."""
    readme = _readme(tmp_path, "# Widget\n\n## Features\n\n- Old thing\n\n## Install\n")
    assert doc.update_readme(_state(tmp_path), tmp_path) is True
    assert "Widget workflow" in readme.read_text(encoding="utf-8")


# --- line 289: the wiki sidebar is not updated (kept) -------------------------


def test_289_a_wiki_with_no_sidebar_keeps_the_page_and_says_so(tmp_path, capsys, monkeypatch):
    """generate_wiki_page makes the wiki directory itself, so a repository
    with no wiki gets a page and no _Sidebar.md: nothing to link from."""
    monkeypatch.setattr(doc, "is_operational_feature", lambda state: False)
    _readme(tmp_path, "# Widget\n\n## Features\n\n- Old\n")

    result = doc.document(_state(tmp_path))

    assert Path(result["doc_wiki_path"]).is_file()
    assert "no _Sidebar.md" in capsys.readouterr().out


def test_289_a_sidebar_that_cannot_be_written_stops_the_node(tmp_path, monkeypatch):
    """A real sidebar failure raises from inside update_wiki_sidebar, and
    the node no longer swallows it."""
    monkeypatch.setattr(doc, "is_operational_feature", lambda state: False)
    monkeypatch.setattr(doc, "update_wiki_sidebar", _raise(PermissionError(13, "denied")))
    _readme(tmp_path, "# Widget\n\n## Features\n\n- Old\n")

    with pytest.raises(doc.DocumentationError) as raised:
        doc.document(_state(tmp_path))
    assert "wiki page" in str(raised.value)
    assert "PermissionError" in str(raised.value)


# --- line 292: the wiki page cannot be generated ------------------------------


def test_292_a_wiki_page_that_cannot_be_written_stops_the_node(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(doc, "generate_wiki_page", _raise(OSError(28, "No space left")))

    with pytest.raises(doc.DocumentationError) as raised:
        doc.document(_state(tmp_path))
    assert "wiki page" in str(raised.value)
    assert "No space left" in str(raised.value)
    assert "ERROR [N8]" in capsys.readouterr().err


# --- line 308: the runbook cannot be generated --------------------------------


def test_308_a_runbook_that_cannot_be_written_stops_the_node(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(doc, "should_generate_wiki", lambda state: False)
    monkeypatch.setattr(doc, "generate_runbook", _raise(ValueError("no procedure steps")))

    with pytest.raises(doc.DocumentationError) as raised:
        doc.document(_state(tmp_path))
    assert "runbook" in str(raised.value)
    assert "no procedure steps" in str(raised.value)
    assert "ERROR [N8]" in capsys.readouterr().err


# --- line 338: the c/p docs cannot be generated -------------------------------


def test_338_a_cp_doc_that_cannot_be_written_stops_the_node(tmp_path, capsys, monkeypatch):
    """The second doc failing after the first was written used to return a
    partial list; nothing partial is returned now."""
    monkeypatch.setattr(doc, "should_generate_wiki", lambda state: False)
    monkeypatch.setattr(doc, "is_operational_feature", lambda state: False)
    monkeypatch.setattr(doc, "generate_cli_doc", lambda **kwargs: tmp_path / "cli.md")
    monkeypatch.setattr(doc, "generate_prompt_doc", _raise(OSError(5, "I/O error")))

    with pytest.raises(doc.DocumentationError) as raised:
        doc.document(_state(tmp_path, skip_cp_docs=False))
    assert "c/p" in str(raised.value)
    assert "I/O error" in str(raised.value)
    assert "ERROR [N8]" in capsys.readouterr().err


# --- line 350: the README update raises ---------------------------------------


def test_350_a_readme_that_cannot_be_written_stops_the_node(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(doc, "should_generate_wiki", lambda state: False)
    monkeypatch.setattr(doc, "is_operational_feature", lambda state: False)
    readme = _readme(tmp_path, "# Widget\n\n## Features\n\n- Old\n")
    real_write_text = Path.write_text

    def refuse(self, *args, **kwargs):
        if self == readme:
            raise PermissionError(13, "read-only", str(self))
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", refuse)

    with pytest.raises(doc.DocumentationError) as raised:
        doc.document(_state(tmp_path))
    assert "README" in str(raised.value)
    assert "read-only" in str(raised.value)
    assert "ERROR [N8]" in capsys.readouterr().err


def test_a_readme_that_already_names_the_feature_needs_no_update(tmp_path, capsys, monkeypatch):
    """Kept: an entry already there is "no update needed"."""
    monkeypatch.setattr(doc, "should_generate_wiki", lambda state: False)
    monkeypatch.setattr(doc, "is_operational_feature", lambda state: False)
    _readme(tmp_path, "# Widget\n\n## Features\n\n- Widget workflow\n")

    result = doc.document(_state(tmp_path))
    assert result["doc_readme_updated"] is False
    assert "README: no update needed" in capsys.readouterr().out
