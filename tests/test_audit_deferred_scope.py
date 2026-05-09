"""Unit tests for tools/audit_deferred_scope.py.

Covers the regex matcher and JSON-response parser. No live gh / claude
calls; those are exercised end-to-end at runtime via the cache.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make tools/ importable without poetry's package install
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import audit_deferred_scope as ads  # noqa: E402


# ---------------------------------------------------------------------------
# Regex matcher
# ---------------------------------------------------------------------------

class TestRegexPatterns:
    def test_deferred_keyword_hits(self):
        text = "We deferred the migration to a follow-up issue."
        keywords = [k for k, p in ads.DEFERRAL_PATTERNS if p.search(text)]
        assert "deferred" in keywords
        assert "follow_up" in keywords

    def test_out_of_scope_hyphenated(self):
        text = "This is out-of-scope for v1."
        hits = [k for k, p in ads.DEFERRAL_PATTERNS if p.search(text)]
        assert "out_of_scope" in hits

    def test_out_of_scope_spaced(self):
        text = "Refactoring is out of scope here."
        hits = [k for k, p in ads.DEFERRAL_PATTERNS if p.search(text)]
        assert "out_of_scope" in hits

    def test_phase_n_only_matches_2plus(self):
        text_p1 = "Phase 1 is complete."
        text_p2 = "Phase 2 will follow later."
        hits_p1 = [k for k, p in ads.DEFERRAL_PATTERNS if p.search(text_p1)]
        hits_p2 = [k for k, p in ads.DEFERRAL_PATTERNS if p.search(text_p2)]
        assert "phase_n" not in hits_p1
        assert "phase_n" in hits_p2

    def test_separate_issue_variants(self):
        for text in ["a separate issue", "new issue", "separate PR", "new ticket"]:
            hits = [k for k, p in ads.DEFERRAL_PATTERNS if p.search(text)]
            assert "separate_issue" in hits, f"failed for: {text}"

    def test_todo_in_close(self):
        text = "TODO: handle the case where..."
        hits = [k for k, p in ads.DEFERRAL_PATTERNS if p.search(text)]
        assert "todo_in_close" in hits

    def test_will_file_followup_variants(self):
        # The pattern matches "will <verb> ... <noun>" forms with "will" as a
        # standalone word. Contractions like "I'll" are caught by other
        # patterns (separate_issue) so we don't over-match.
        for text in [
            "We will file as a separate issue.",
            "Will track in a follow-up PR.",
            "We will cover via a new ticket.",
        ]:
            hits = [k for k, p in ads.DEFERRAL_PATTERNS if p.search(text)]
            assert "will_file_followup" in hits, f"failed for: {text}"

    def test_contracted_will_caught_by_separate_issue(self):
        # "I'll cover via a new ticket" — will_file_followup doesn't match
        # but separate_issue picks it up via "new ticket".
        text = "I'll cover via a new ticket."
        hits = [k for k, p in ads.DEFERRAL_PATTERNS if p.search(text)]
        assert "separate_issue" in hits

    def test_no_false_positive_on_ordinary_text(self):
        text = "This change adds a new feature, fixes a bug, and updates docs."
        hits = [k for k, p in ads.DEFERRAL_PATTERNS if p.search(text)]
        # 'new' alone shouldn't match separate_issue — it's gated by issue|PR|ticket
        assert "separate_issue" not in hits
        assert "deferred" not in hits
        assert "out_of_scope" not in hits


# ---------------------------------------------------------------------------
# Context extraction
# ---------------------------------------------------------------------------

class TestExtractContext:
    def test_extract_around_match(self):
        text = "x" * 500 + "DEFERRED" + "y" * 500
        span = (500, 508)
        ctx = ads.extract_context(text, span)
        # Should be roughly 250 + 8 + 250 = ~508 chars
        assert "DEFERRED" in ctx
        assert len(ctx) <= 250 + 8 + 250 + 5  # small slack

    def test_normalizes_newlines_to_spaces(self):
        text = "before\r\n\r\ndeferred\r\nafter"
        span = (text.index("deferred"), text.index("deferred") + 8)
        ctx = ads.extract_context(text, span)
        assert "\n" not in ctx
        assert "\r" not in ctx
        assert "deferred" in ctx


# ---------------------------------------------------------------------------
# JSON response parser
# ---------------------------------------------------------------------------

class TestParseJsonResponse:
    def test_pure_json(self):
        s = '{"is_deferral": true, "summary": "hello"}'
        parsed = ads.parse_json_response(s)
        assert parsed == {"is_deferral": True, "summary": "hello"}

    def test_json_with_fences(self):
        s = '```json\n{"is_deferral": false}\n```'
        parsed = ads.parse_json_response(s)
        assert parsed == {"is_deferral": False}

    def test_json_with_prose_prefix(self):
        s = 'Sure! Here is the answer:\n{"is_deferral": true, "summary": "x"}'
        parsed = ads.parse_json_response(s)
        assert parsed is not None
        assert parsed.get("is_deferral") is True

    def test_json_with_prose_suffix(self):
        s = '{"is_deferral": true}\n\nLet me know if you need more.'
        parsed = ads.parse_json_response(s)
        assert parsed is not None
        assert parsed.get("is_deferral") is True

    def test_no_json_returns_none(self):
        parsed = ads.parse_json_response("just prose, no json at all")
        assert parsed is None

    def test_malformed_json_returns_none(self):
        parsed = ads.parse_json_response('{"is_deferral": tru')  # truncated
        assert parsed is None


# ---------------------------------------------------------------------------
# Candidate cache key
# ---------------------------------------------------------------------------

class TestCandidateCacheKey:
    def test_deterministic(self):
        c1 = ads.Candidate(
            issue_number=42, issue_title="x", closed_at="2026-01-01",
            labels=[], keyword="deferred", location="body", context="abc",
        )
        c2 = ads.Candidate(
            issue_number=42, issue_title="DIFFERENT", closed_at="2026-02-02",
            labels=["a"], keyword="deferred", location="body", context="abc",
        )
        # Same number+keyword+location+context -> same key (title/closed/labels excluded)
        assert c1.cache_key() == c2.cache_key()

    def test_different_keyword_different_key(self):
        c1 = ads.Candidate(
            issue_number=42, issue_title="x", closed_at="2026-01-01",
            labels=[], keyword="deferred", location="body", context="abc",
        )
        c2 = ads.Candidate(
            issue_number=42, issue_title="x", closed_at="2026-01-01",
            labels=[], keyword="follow_up", location="body", context="abc",
        )
        assert c1.cache_key() != c2.cache_key()


# ---------------------------------------------------------------------------
# Categorization
# ---------------------------------------------------------------------------

class TestCategoryFor:
    def _cls(self, **kw) -> ads.Classification:
        defaults = dict(
            is_deferral=True, summary="x", addressed_in=None,
            addressed_status=None, new_repo_related=False,
            still_relevant=None, rationale="",
        )
        defaults.update(kw)
        return ads.Classification(**defaults)

    def test_false_positive(self):
        assert ads.category_for(self._cls(is_deferral=False)) == "FALSE_POSITIVE"

    def test_caught_when_addressed_closed(self):
        c = self._cls(addressed_in="#999", addressed_status="closed")
        assert ads.category_for(c) == "CAUGHT"

    def test_addressed_open(self):
        c = self._cls(addressed_in="#999", addressed_status="open")
        assert ads.category_for(c) == "ADDRESSED_OPEN"

    def test_obsolete(self):
        c = self._cls(still_relevant=False)
        assert ads.category_for(c) == "OBSOLETE"

    def test_orphaned(self):
        c = self._cls(still_relevant=True)
        assert ads.category_for(c) == "ORPHANED"

    def test_unclassified(self):
        c = self._cls(still_relevant=None)
        assert ads.category_for(c) == "UNCLASSIFIED"

    def test_error(self):
        c = self._cls(error="json parse failed")
        assert ads.category_for(c) == "ERROR"


# ---------------------------------------------------------------------------
# Cross-reference index
# ---------------------------------------------------------------------------

class TestBuildXrefIndex:
    def test_finds_references_in_body(self):
        corpus = [
            ads.IssueRecord(number=1, title="t", state="closed", closedAt=None,
                            body="see #2 for follow-up", labels=[], comments=[]),
            ads.IssueRecord(number=2, title="t", state="closed", closedAt=None,
                            body="", labels=[], comments=[]),
        ]
        idx = ads.build_xref_index(corpus)
        assert idx.get(2) == [1]

    def test_finds_references_in_comments(self):
        corpus = [
            ads.IssueRecord(number=1, title="t", state="closed", closedAt=None,
                            body="", labels=[],
                            comments=[{"author": "x", "body": "addressed in #5"}]),
            ads.IssueRecord(number=5, title="t", state="closed", closedAt=None,
                            body="", labels=[], comments=[]),
        ]
        idx = ads.build_xref_index(corpus)
        assert idx.get(5) == [1]

    def test_excludes_self_references(self):
        corpus = [
            ads.IssueRecord(number=42, title="t", state="closed", closedAt=None,
                            body="this fixes #42", labels=[], comments=[]),
        ]
        idx = ads.build_xref_index(corpus)
        assert 42 not in idx

    def test_dedupes_repeated_references(self):
        corpus = [
            ads.IssueRecord(number=1, title="t", state="closed", closedAt=None,
                            body="see #2 also #2 again", labels=[],
                            comments=[{"author": "x", "body": "and #2"}]),
            ads.IssueRecord(number=2, title="t", state="closed", closedAt=None,
                            body="", labels=[], comments=[]),
        ]
        idx = ads.build_xref_index(corpus)
        assert idx.get(2) == [1]
