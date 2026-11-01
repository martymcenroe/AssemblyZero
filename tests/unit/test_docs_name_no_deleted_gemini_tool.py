"""No live document sends a reader to the deleted Gemini retry tool (#1655).

`tools/gemini-retry.py` was deleted, and its docs stayed: two runbooks told the
reader to run it, and the index and the inventory listed it as stable. A doc has
no way to be wrong loudly, so this asks every one of them.

History is left out on purpose. `docs/lld/done`, the reports and audits, and the
lessons page record what was true then, and they stay as they were.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

DELETED_TOOL = "gemini-retry"
DELETED_DOCS = (
    "docs/skills/0604-gemini-retry.md",
    "docs/skills/0628c-gemini-retry-cli.md",
    "docs/skills/0628p-gemini-retry-prompt.md",
)
#: The pages that tell a reader what to run or what exists today.
LIVE_DOCS = sorted(
    {
        REPO_ROOT / "docs" / "index.md",
        REPO_ROOT / "docs" / "0003-file-inventory.md",
        REPO_ROOT / "wiki" / "Tools-Reference.md",
        REPO_ROOT / "wiki" / "Gemini-Verification.md",
        *(REPO_ROOT / "docs" / "runbooks").glob("*.md"),
        *(REPO_ROOT / "docs" / "skills").glob("*.md"),
    }
)


def test_the_scan_has_something_to_read() -> None:
    """Guards the parametrized test from passing vacuously."""
    assert len(LIVE_DOCS) > 50


@pytest.mark.parametrize(
    "doc", LIVE_DOCS, ids=[path.name for path in LIVE_DOCS]
)
def test_no_live_doc_names_the_deleted_tool(doc: Path) -> None:
    assert DELETED_TOOL not in doc.read_text(encoding="utf-8"), doc


@pytest.mark.parametrize("doc", DELETED_DOCS)
def test_the_tools_own_docs_are_gone(doc: str) -> None:
    assert not (REPO_ROOT / doc).exists(), doc


def test_the_tool_is_gone() -> None:
    """The docs are right only while this holds."""
    assert not (REPO_ROOT / "tools" / "gemini-retry.py").exists()
