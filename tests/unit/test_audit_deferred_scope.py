"""Unit tests for tools/audit_deferred_scope.py.

Covers the regex matcher and JSON-response parser. No live gh / claude
calls; those are exercised end-to-end at runtime via the cache.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

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

    def test_there_is_no_error_category(self):
        """#3584: a failed classification stops the audit, so no report row
        can carry one."""
        assert "error" not in {f.name for f in ads.fields(ads.Classification)}


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


# ---------------------------------------------------------------------------
# #1049 bug 1: similarity helpers + content dedupe
# ---------------------------------------------------------------------------

class TestSimilarityHelpers:
    def test_meaningful_tokens_filters_stopwords(self):
        toks = ads._meaningful_tokens("The classic PAT and the gpg passphrase rotation TODO")
        assert "classic" in toks
        assert "pat" in toks
        assert "gpg" in toks
        assert "passphrase" in toks
        assert "rotation" in toks
        assert "todo" in toks
        assert "the" not in toks
        assert "and" not in toks

    def test_meaningful_tokens_filters_short_fragments(self):
        toks = ads._meaningful_tokens("a b cd ef")
        # Single chars filtered by the \w{2,} regex
        assert "a" not in toks
        assert "cd" in toks

    def test_jaccard_identical_is_one(self):
        s = ads._meaningful_tokens("rotate classic PAT")
        assert ads._jaccard(s, s) == 1.0

    def test_jaccard_disjoint_is_zero(self):
        a = ads._meaningful_tokens("alpha beta")
        b = ads._meaningful_tokens("gamma delta")
        assert ads._jaccard(a, b) == 0.0

    def test_jaccard_empty_returns_zero(self):
        empty = frozenset()
        non_empty = ads._meaningful_tokens("anything")
        assert ads._jaccard(empty, non_empty) == 0.0
        assert ads._jaccard(non_empty, empty) == 0.0


class TestFindCandidatesContentDedupe:
    def test_collapses_overlapping_contexts_within_issue(self):
        # Same passage hit by two different keywords; should dedupe to one.
        body = (
            "Phase 1 done. Classic PAT and gpg passphrase rotation TODO "
            "tracked in a separate follow-up issue, not this hardening PR."
        )
        corpus = [
            ads.IssueRecord(number=1018, title="hardening", state="closed",
                            closedAt=None, body=body, labels=[], comments=[]),
        ]
        cands = ads.find_candidates(corpus)
        # Multiple keywords match (TODO, separate_issue, follow_up,
        # tracked_separately, etc.) but all overlap heavily on same passage.
        # After bug-1 dedupe: at most one survives.
        assert len(cands) <= 1, f"expected <= 1 after dedupe, got {len(cands)}"

    def test_keeps_distinct_passages_within_issue(self):
        body = (
            "First deferral: GEMINI.md template generation deferred. "
            + ("x" * 800)  # padding to push next match outside CONTEXT_RADIUS overlap
            + " Second deferral: rotate classic PAT in a separate issue."
        )
        corpus = [
            ads.IssueRecord(number=931, title="t", state="closed",
                            closedAt=None, body=body, labels=[], comments=[]),
        ]
        cands = ads.find_candidates(corpus)
        # Two genuinely distinct deferrals — both should survive.
        assert len(cands) >= 2

    def test_does_not_dedupe_across_issues(self):
        # Same context in two different issues stays as two candidates.
        ctx = "deferred to a follow-up issue"
        corpus = [
            ads.IssueRecord(number=1, title="t", state="closed",
                            closedAt=None, body=ctx, labels=[], comments=[]),
            ads.IssueRecord(number=2, title="t", state="closed",
                            closedAt=None, body=ctx, labels=[], comments=[]),
        ]
        cands = ads.find_candidates(corpus)
        issues = {c.issue_number for c in cands}
        assert issues == {1, 2}


# ---------------------------------------------------------------------------
# #1049 bug 2: title-similarity xref supplement
# ---------------------------------------------------------------------------

class TestFindTitleSimilarOpenIssues:
    def test_finds_open_issue_sharing_topic_tokens(self):
        # The original miss: #1018's deferred summary ("rotate classic PAT
        # and gpg passphrase per runbook 0930") never text-references #1017,
        # but #1017's title shares 4+ topic tokens.
        ctx = ("Classic PAT and gpg passphrase rotation TODO tracked in a "
               "separate issue, per runbook 0930.")
        state_index = {
            1017: {"state": "open",
                   "title": "[TODO] Rotate classic PAT and gpg passphrase per runbook 0930"},
            42: {"state": "open", "title": "totally unrelated frontend bug"},
            1004: {"state": "closed", "title": "old work"},
        }
        result = ads.find_title_similar_open_issues(ctx, state_index, exclude=1018)
        assert 1017 in result
        assert 42 not in result

    def test_excludes_closed_issues(self):
        ctx = "rotate classic PAT"
        state_index = {
            999: {"state": "closed", "title": "rotate classic PAT — done"},
        }
        result = ads.find_title_similar_open_issues(ctx, state_index, exclude=1)
        assert result == []

    def test_excludes_self(self):
        ctx = "rotate classic PAT"
        state_index = {
            42: {"state": "open", "title": "rotate classic PAT"},
        }
        result = ads.find_title_similar_open_issues(ctx, state_index, exclude=42)
        assert result == []

    def test_respects_min_overlap_threshold(self):
        # Only one shared meaningful token ('rotate'); below threshold.
        ctx = "rotate something"
        state_index = {
            42: {"state": "open", "title": "rotate frontend cache"},
        }
        result = ads.find_title_similar_open_issues(ctx, state_index, exclude=1, min_overlap=2)
        assert result == []

    def test_caps_results(self):
        ctx = "rotate classic PAT and gpg passphrase per runbook 0930"
        state_index = {
            n: {"state": "open", "title": "rotate classic PAT gpg"}
            for n in range(100, 110)
        }
        result = ads.find_title_similar_open_issues(ctx, state_index, exclude=1, cap=5)
        assert len(result) == 5


# ---------------------------------------------------------------------------
# #1049 bug 3: state-aware prompt formatting
# ---------------------------------------------------------------------------

class TestBuildPromptStateAware:
    def _candidate(self) -> ads.Candidate:
        return ads.Candidate(
            issue_number=1018, issue_title="hardening", closed_at="2026-04-30",
            labels=[], keyword="todo_in_close", location="body",
            context="rotate PAT TODO tracked separately",
        )

    def test_prompt_with_state_index_annotates_xrefs(self):
        c = self._candidate()
        state_index = {
            1017: {"state": "open", "title": "rotate PAT"},
            1004: {"state": "closed", "title": "old"},
        }
        prompt = ads.build_prompt(c, [1017, 1004], state_index=state_index)
        assert "#1017 (open)" in prompt
        assert "#1004 (closed)" in prompt

    def test_prompt_without_state_index_uses_bare_numbers(self):
        c = self._candidate()
        prompt = ads.build_prompt(c, [1017, 1004], state_index=None)
        # Bare-number form on the cross-references line — no state suffix.
        assert "cross-references): #1017, #1004" in prompt
        assert "#1017 (open)" not in prompt
        assert "#1004 (closed)" not in prompt

    def test_prompt_handles_empty_xref(self):
        c = self._candidate()
        prompt = ads.build_prompt(c, [], state_index={1: {"state": "open", "title": "x"}})
        assert "(none found)" in prompt

    def test_prompt_handles_unknown_state(self):
        c = self._candidate()
        # state_index has #1017 but missing the queried #999
        state_index = {1017: {"state": "open", "title": "x"}}
        prompt = ads.build_prompt(c, [999], state_index=state_index)
        assert "#999 (unknown)" in prompt


# ---------------------------------------------------------------------------
# #3584: Gemini through agy under every profile, and a loud stop on failure
# ---------------------------------------------------------------------------


class _Result:
    def __init__(self, success: bool, response: str = "", error_message: str = ""):
        self.success = success
        self.response = response
        self.error_message = error_message


class _Provider:
    """Answers with valid JSON, except on the calls listed in ``fail_on``."""

    def __init__(self, fail_on: set[int], raise_on: set[int]):
        self.calls = 0
        self.fail_on, self.raise_on = fail_on, raise_on

    def invoke(self, system_prompt, content, timeout_seconds):
        self.calls += 1
        if self.calls in self.raise_on:
            raise RuntimeError("agy exited 1: transport down")
        if self.calls in self.fail_on:
            return _Result(False, error_message="quota exhausted")
        return _Result(True, response='{"is_deferral": true, "summary": "s", "still_relevant": true}')


class _Seat:
    spec = "gemini:3.1-pro"
    resolved_model_id = "gemini-3.1-pro-high"

    def __init__(self, provider):
        self._provider = provider

    def build(self):
        return self._provider


def _candidates(n: int) -> list:
    return [
        ads.Candidate(issue_number=100 + i, issue_title=f"t{i}", closed_at="2026-01-01",
                      labels=[], keyword="deferred", location="body", context=f"ctx {i}")
        for i in range(n)
    ]




@pytest.fixture
def audit_env(tmp_path, monkeypatch):
    """main() with gh, the corpus and the seat replaced; reports into tmp_path."""
    monkeypatch.setattr(ads, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(ads, "DOCS_DIR", tmp_path / "docs")
    monkeypatch.setattr(ads, "LLM_CACHE", tmp_path / "data" / "cache.json")
    monkeypatch.setattr(ads, "REPORT_FULL", tmp_path / "docs" / "full.md")
    monkeypatch.setattr(ads, "REPORT_NEW_REPO", tmp_path / "docs" / "new.md")
    monkeypatch.setattr(ads, "LLM_INTER_CALL_SLEEP_S", 0)
    monkeypatch.setattr(ads, "fetch_corpus", lambda refresh=False: [])
    monkeypatch.setattr(ads, "fetch_state_index", lambda refresh=False: {})
    monkeypatch.setattr(ads, "find_candidates", lambda corpus: _candidates(3))
    monkeypatch.setattr(ads, "build_xref_index", lambda corpus: {})
    monkeypatch.setattr(sys, "argv", ["audit_deferred_scope.py"])
    return tmp_path


class TestGeminiOnly:
    def test_T1_a_claude_profile_is_refused_before_any_call(self, monkeypatch):
        from assemblyzero.core import seats

        monkeypatch.setattr(seats, "_RUN_PROFILE", None)
        monkeypatch.setenv("AZ_MODEL_PROFILE", "claude")
        with patch("assemblyzero.core.seats.Seat.build") as build, \
                pytest.raises(ads.AuditFailed, match="claude:"):
            ads.require_gemini_seat()
        build.assert_not_called()

    def test_the_default_profile_resolves_to_gemini(self, monkeypatch):
        from assemblyzero.core import seats

        monkeypatch.setattr(seats, "_RUN_PROFILE", None)
        monkeypatch.delenv("AZ_MODEL_PROFILE", raising=False)
        assert ads.require_gemini_seat().spec.startswith("gemini:")


class TestLoudStop:
    @pytest.mark.parametrize("how", ["raise", "fail"])
    def test_T2_a_failure_on_the_second_candidate_stops_with_no_report(self, audit_env, how):
        provider = _Provider(fail_on={2} if how == "fail" else set(), raise_on={2} if how == "raise" else set())
        with patch.object(ads, "require_gemini_seat", return_value=_Seat(provider)), \
                patch("assemblyzero.core.alert.alert_operator") as alert:
            assert ads.main() == 1
        assert not (audit_env / "docs" / "full.md").exists()
        assert not (audit_env / "docs" / "new.md").exists()
        alert.assert_called_once()
        kwargs = alert.call_args.kwargs
        assert kwargs["issue"] == 101 and kwargs["spec"] == "gemini:3.1-pro"
        assert "phase C" in kwargs["where"]

    def test_unparseable_answer_stops(self, audit_env):
        provider = _Provider(set(), set())
        provider.invoke = lambda **kw: _Result(True, response="not json at all")
        with patch.object(ads, "require_gemini_seat", return_value=_Seat(provider)), \
                patch("assemblyzero.core.alert.alert_operator") as alert:
            assert ads.main() == 1
        assert "parseable JSON" in alert.call_args.kwargs["cause"]

    def test_a_refused_profile_alerts_and_writes_nothing(self, audit_env):
        refusal = ads.AuditFailed("seat resolves to 'claude:opus'")
        with patch.object(ads, "require_gemini_seat", side_effect=refusal), \
                patch("assemblyzero.core.alert.alert_operator") as alert:
            assert ads.main() == 1
        assert not (audit_env / "docs" / "full.md").exists()
        assert "claude:opus" in alert.call_args.kwargs["cause"]

    def test_T3_a_complete_run_names_the_resolved_model(self, audit_env):
        provider = _Provider(set(), set())
        with patch.object(ads, "require_gemini_seat", return_value=_Seat(provider)):
            assert ads.main() == 0
        report = (audit_env / "docs" / "full.md").read_text(encoding="utf-8")
        assert "`gemini:3.1-pro` (gemini-3.1-pro-high, through agy)" in report
        assert "claude --print" not in report and "Claude Opus" not in report
        assert "the first" not in report

    def test_a_limited_run_says_so(self, audit_env, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["audit_deferred_scope.py", "--limit", "2"])
        with patch.object(ads, "require_gemini_seat", return_value=_Seat(_Provider(set(), set()))):
            assert ads.main() == 0
        report = (audit_env / "docs" / "full.md").read_text(encoding="utf-8")
        assert "the first 2 of 3 candidates (--limit)" in report


class TestCache:
    def test_a_cached_error_is_dropped_and_reclassified(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "cache.json"
        cache_file.write_text(
            '{"a": {"is_deferral": true, "error": "json parse failed"}, "b": {"is_deferral": false}}',
            encoding="utf-8",
        )
        monkeypatch.setattr(ads, "LLM_CACHE", cache_file)
        assert set(ads.load_llm_cache()) == {"b"}

    def test_a_corrupt_cache_stops_the_audit(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "cache.json"
        cache_file.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(ads, "LLM_CACHE", cache_file)
        with pytest.raises(ads.AuditFailed, match="cannot read"):
            ads.load_llm_cache()

    def test_a_failed_state_index_fetch_stops_the_audit(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ads, "STATE_INDEX_CACHE", tmp_path / "absent.json")
        failed = ads.subprocess.CompletedProcess([], 1, stdout="", stderr="HTTP 502")
        monkeypatch.setattr(ads, "gh_with_backoff", lambda cmd, timeout=60: failed)
        with pytest.raises(ads.AuditFailed, match="HTTP 502"):
            ads.fetch_state_index(refresh=True)
