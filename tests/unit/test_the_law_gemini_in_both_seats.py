"""Gemini in agy drafts and Gemini in agy validates: the 2026-09-24 law (ADR 0234, #3552).

Two things pinned here. The standalone tools default both seats to Gemini.
And no tracked document, runbook, wiki page, tool or package module puts
Claude back into a seat by wording. The second check walks the tree for a
closed list of phrases and matches by substring after lower-casing: never a
regex, per this repository's audit rule and the closed-set rule the fleet's
writing law states.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: The closed list. Every entry is a phrase that has actually appeared in this
#: repository and put Claude in the drafter or reviewer seat (#3552's ledger).
#: Add to it when a new wording is found; never widen it into a pattern.
PHRASES = (
    "claude drafts",
    "claude draft ",
    "claude side drafting",
    "claude side keeps drafting",
    "drafter stays claude",
    "claude drafter",
    "drafter llm (claude)",
)

ROOTS = ("docs", "wiki", "tools", "assemblyzero")

#: Historical and append-only places, by path part: never rewritten by rule.
EXCLUDED_PARTS = frozenset({"done", "lineage", "reports"})

#: Narrative or append-only files that mention Claude drafting something that
#: is not a workflow seat (a quotes page, the lessons files).
EXCLUDED_FILES = frozenset({
    "wiki/Claudes-World.md",
    "docs/workflow-lessons-learned-1.md",
    "docs/lessons-learned.md",
})

SUFFIXES = frozenset({".md", ".py", ".txt", ".yml", ".yaml", ".json", ".toml"})


def offending_lines(root: Path = REPO) -> list[str]:
    """Every line under ROOTS that carries one of PHRASES, as ``rel:line: text``."""
    hits: list[str] = []
    for top in ROOTS:
        base = root / top
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in SUFFIXES:
                continue
            rel_path = path.relative_to(root)
            rel = rel_path.as_posix()
            if rel in EXCLUDED_FILES or EXCLUDED_PARTS & set(rel_path.parts):
                continue
            if "lessons-learned" in path.name:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for number, line in enumerate(text.splitlines(), 1):
                low = line.lower()
                if any(phrase in low for phrase in PHRASES):
                    hits.append(f"{rel}:{number}: {line.strip()[:120]}")
    return hits


class TestTheStandaloneDefaults:
    """The default values themselves are pinned in ``test_agy_both_seats.py``
    (#3517); this pins that no seat argument in the three tools is Claude."""

    def test_no_seat_argument_defaults_to_claude(self):
        for tool in (
            "tools/run_requirements_workflow.py",
            "tools/run_implement_from_lld.py",
            "tools/run_implementation_spec_workflow.py",
        ):
            source = (REPO / tool).read_text(encoding="utf-8")
            assert 'default="claude:' not in source, tool


class TestNoDocumentPutsClaudeBackInASeat:
    def test_the_tree_is_clean(self):
        hits = offending_lines()
        assert hits == [], "\n".join(hits)

    def test_the_guard_sees_a_planted_line(self, tmp_path):
        for top in ROOTS:
            (tmp_path / top).mkdir()
        (tmp_path / "docs" / "x.md").write_text("1. Claude drafts LLD\n", encoding="utf-8")
        assert offending_lines(tmp_path) == ["docs/x.md:1: 1. Claude drafts LLD"]

    def test_the_guard_leaves_history_alone(self, tmp_path):
        for top in ROOTS:
            (tmp_path / top).mkdir()
        (tmp_path / "docs" / "done").mkdir()
        (tmp_path / "docs" / "done" / "old.md").write_text("Claude drafts LLD\n", encoding="utf-8")
        assert offending_lines(tmp_path) == []
