"""Tests for codebase retrieval system.

Issue #92: Codebase Retrieval System (RAG Injection)
"""

from __future__ import annotations

import logging

from pathlib import Path
from unittest import mock

import pytest

from assemblyzero.rag.codebase_retrieval import (
    CodeChunk,
    CodebaseContext,
    RetrievalResult,
    apply_token_budget,
    estimate_token_count,
    extract_keywords,
    file_path_to_module_path,
    format_codebase_context,
    get_domain_stopwords,
    parse_python_file,
    query_codebase_collection,
    retrieve_codebase_context,
    split_compound_terms,
)


FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "rag"


# ---------------------------------------------------------------------------
# AST Parsing Tests
# ---------------------------------------------------------------------------


class TestParseFile:
    """Tests for parse_python_file() -- T010, T020, T030, T040, T050, T260."""

    def test_class_extraction_with_docstring(self) -> None:
        """T010: AST extracts class with docstring and methods."""
        chunks = parse_python_file(str(FIXTURES_DIR / "sample_module.py"))
        class_chunks = [c for c in chunks if c["entity_name"] == "GovernanceAuditLog"]
        assert len(class_chunks) == 1
        chunk = class_chunks[0]
        assert chunk["kind"] == "class"
        assert "GovernanceAuditLog" in chunk["content"]
        assert "Audit logging for governance events" in chunk["content"]
        assert chunk["module_path"].endswith("sample_module")

    def test_function_extraction_with_type_hints(self) -> None:
        """T020: AST extracts top-level function with type hints."""
        chunks = parse_python_file(str(FIXTURES_DIR / "sample_module.py"))
        func_chunks = [c for c in chunks if c["kind"] == "function"]
        assert len(func_chunks) >= 1
        # Check that at least one function has type hints in content
        has_type_hints = any("str" in c["content"] for c in func_chunks)
        assert has_type_hints

    def test_private_entity_skip(self) -> None:
        """T030: AST skips private entities."""
        chunks = parse_python_file(str(FIXTURES_DIR / "sample_module.py"))
        names = [c["entity_name"] for c in chunks]
        assert "_internal_helper" not in names
        assert "_PrivateProcessor" not in names

    def test_malformed_file_returns_empty(self) -> None:
        """T040: AST handles malformed Python file."""
        chunks = parse_python_file(str(FIXTURES_DIR / "sample_module_malformed.py"))
        assert chunks == []

    def test_malformed_logs_warning(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """T040/T290: Malformed Python file returns [] and logs warning with file path."""
        broken_file = tmp_path / "broken.py"
        broken_file.write_text("def broken(\n    # Missing closing paren\n", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            result = parse_python_file(str(broken_file))

        assert result == []
        assert "broken.py" in caplog.text
        assert any(record.levelname == "WARNING" for record in caplog.records)

    def test_docstring_only_init(self, tmp_path: Path) -> None:
        """T050: AST skips __init__.py with only docstring."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text('"""Package docstring."""\n', encoding="utf-8")

        result = parse_python_file(str(init_file))

        assert result == []

    def test_empty_init(self, tmp_path: Path) -> None:
        """T050 variant: AST skips completely empty __init__.py."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("", encoding="utf-8")

        result = parse_python_file(str(init_file))

        assert result == []

    def test_type_hints_preserved(self) -> None:
        """T260: AST extracts ClassDef with type hints preserved in content."""
        chunks = parse_python_file(str(FIXTURES_DIR / "sample_module.py"))
        class_chunks = [c for c in chunks if c["entity_name"] == "GovernanceAuditLog"]
        assert len(class_chunks) == 1
        content = class_chunks[0]["content"]
        assert "str" in content
        assert "bool" in content
        assert "list[dict[str, str]]" in content


class TestFilePathToModulePath:
    """Tests for file_path_to_module_path() -- T060."""

    def test_standard_path(self) -> None:
        """T060: Convert standard file path to module path."""
        assert file_path_to_module_path("assemblyzero/core/audit.py") == "assemblyzero.core.audit"

    def test_init_path(self) -> None:
        """T060 variant: Convert __init__.py path."""
        assert file_path_to_module_path("assemblyzero/rag/__init__.py") == "assemblyzero.rag"


# ---------------------------------------------------------------------------
# Keyword Extraction Tests
# ---------------------------------------------------------------------------


class TestSplitCompoundTerms:
    """Tests for split_compound_terms() -- T070, T080."""

    def test_camel_case(self) -> None:
        """T070: CamelCase splitting."""
        parts = split_compound_terms("GovernanceAuditLog")
        assert "Governance" in parts
        assert "Audit" in parts
        assert "Log" in parts
        assert "GovernanceAuditLog" in parts

    def test_snake_case(self) -> None:
        """T080: snake_case splitting."""
        parts = split_compound_terms("audit_log_entry")
        assert "audit" in parts
        assert "log" in parts
        assert "entry" in parts
        assert "audit_log_entry" in parts


class TestExtractKeywords:
    """Tests for extract_keywords() -- T090, T100, T110."""

    def test_stopword_filtering(self) -> None:
        """T090: Stopwords are filtered out."""
        keywords = extract_keywords(
            "Implement the feature using a new system that should create"
        )
        stopwords = get_domain_stopwords()
        for kw in keywords:
            assert kw.lower() not in stopwords

    def test_max_keywords_limit(self) -> None:
        """T100: Keyword extraction limits to top N."""
        # Text with many distinct technical terms
        text = (
            "GovernanceAuditLog ConfigValidator TextChunker VectorStore "
            "EmbeddingProvider CollectionManager QueryEngine RAGConfig "
            "ChunkMetadata IngestionSummary RetrievedDocument SecurityAudit "
            "WorkflowState GraphBuilder NodeRegistry TaskScheduler "
            "CacheManager ConnectionPool EventDispatcher MetricsCollector "
            "LogAggregator AlertSystem HealthChecker"
        )
        keywords = extract_keywords(text, max_keywords=5)
        assert len(keywords) <= 5

    def test_fallback_on_sparse_input(self) -> None:
        """T110: Keyword extraction fallback on sparse CamelCase input."""
        keywords = extract_keywords("Use FooBarBaz")
        assert "FooBarBaz" in keywords


class TestDomainStopwords:
    """Tests for get_domain_stopwords() -- T250."""

    def test_contains_expected_terms(self) -> None:
        """T250: Domain stopwords are comprehensive."""
        stopwords = get_domain_stopwords()
        for expected in ["def", "class", "implement", "the", "return", "self"]:
            assert expected in stopwords


# ---------------------------------------------------------------------------
# Retrieval Tests
# ---------------------------------------------------------------------------


class TestQueryCodebaseCollection:
    """Tests for query_codebase_collection() -- T120, T130, T140, T150, T280."""

    def test_threshold_filtering(self) -> None:
        """T120: Nonsense query returns empty results with mocked low scores."""
        with mock.patch("assemblyzero.rag.codebase_retrieval.chromadb") as mock_chromadb:
            mock_collection = mock.MagicMock()
            mock_client = mock.MagicMock()
            mock_chromadb.PersistentClient.return_value = mock_client
            mock_client.get_collection.return_value = mock_collection
            # Return results with very high distances (low similarity)
            mock_collection.query.return_value = {
                "documents": [["class X: pass"]],
                "metadatas": [[{"module_path": "mod.x", "entity_name": "X", "kind": "class", "file_path": "mod/x.py", "start_line": 1, "end_line": 1}]],
                "distances": [[10.0]],  # similarity = 1/(1+10) = 0.09 < 0.75
            }

            results = query_codebase_collection(["xyznonexistent123"])
            assert results == []

    def test_module_deduplication(self) -> None:
        """T130: Two chunks from same module keeps only highest score."""
        with mock.patch("assemblyzero.rag.codebase_retrieval.chromadb") as mock_chromadb:
            mock_collection = mock.MagicMock()
            mock_client = mock.MagicMock()
            mock_chromadb.PersistentClient.return_value = mock_client
            mock_client.get_collection.return_value = mock_collection
            # distance 0.111 -> similarity ~= 0.9;  distance 0.25 -> similarity = 0.8
            mock_collection.query.return_value = {
                "documents": [["class A: pass", "def b(): pass"]],
                "metadatas": [[
                    {"module_path": "assemblyzero.core.audit", "entity_name": "A", "kind": "class", "file_path": "assemblyzero/core/audit.py", "start_line": 1, "end_line": 1},
                    {"module_path": "assemblyzero.core.audit", "entity_name": "b", "kind": "function", "file_path": "assemblyzero/core/audit.py", "start_line": 5, "end_line": 5},
                ]],
                "distances": [[0.111, 0.25]],
            }

            results = query_codebase_collection(["audit"])
            assert len(results) == 1
            # Should keep the higher similarity one
            assert results[0]["relevance_score"] > 0.85

    def test_max_results_limit(self) -> None:
        """T140: Query returns at most max_results."""
        with mock.patch("assemblyzero.rag.codebase_retrieval.chromadb") as mock_chromadb:
            mock_collection = mock.MagicMock()
            mock_client = mock.MagicMock()
            mock_chromadb.PersistentClient.return_value = mock_client
            mock_client.get_collection.return_value = mock_collection

            # 15 results from different modules, all high similarity
            docs = [f"class C{i}: pass" for i in range(15)]
            metas = [{"module_path": f"mod.c{i}", "entity_name": f"C{i}", "kind": "class", "file_path": f"mod/c{i}.py", "start_line": 1, "end_line": 1} for i in range(15)]
            dists = [0.1] * 15  # similarity ~= 0.91

            mock_collection.query.return_value = {
                "documents": [docs],
                "metadatas": [metas],
                "distances": [dists],
            }

            results = query_codebase_collection(["test"], max_results=10)
            assert len(results) == 10

    def test_missing_collection_graceful(self, caplog: pytest.LogCaptureFixture) -> None:
        """T150: Missing collection returns empty list with warning."""
        with mock.patch("assemblyzero.rag.codebase_retrieval.chromadb") as mock_chromadb:
            mock_client = mock.MagicMock()
            mock_chromadb.PersistentClient.return_value = mock_client
            mock_client.get_collection.side_effect = Exception("Collection not found")

            with caplog.at_level(logging.WARNING):
                results = query_codebase_collection(["audit"])

            assert results == []
            assert "codebase" in caplog.text.lower() or "not found" in caplog.text.lower()

    def test_similarity_threshold_boundary(self) -> None:
        """T280: Results at boundary -- 0.76 passes, 0.74 fails."""
        with mock.patch("assemblyzero.rag.codebase_retrieval.chromadb") as mock_chromadb:
            mock_collection = mock.MagicMock()
            mock_client = mock.MagicMock()
            mock_chromadb.PersistentClient.return_value = mock_client
            mock_client.get_collection.return_value = mock_collection

            # distance for similarity 0.76: 1/0.76 - 1 ~= 0.3158
            # distance for similarity 0.74: 1/0.74 - 1 ~= 0.3514
            mock_collection.query.return_value = {
                "documents": [["class A: pass", "class B: pass"]],
                "metadatas": [[
                    {"module_path": "mod.a", "entity_name": "A", "kind": "class", "file_path": "mod/a.py", "start_line": 1, "end_line": 1},
                    {"module_path": "mod.b", "entity_name": "B", "kind": "class", "file_path": "mod/b.py", "start_line": 1, "end_line": 1},
                ]],
                "distances": [[0.3158, 0.3514]],
            }

            results = query_codebase_collection(["test"], similarity_threshold=0.75)
            assert len(results) == 1
            assert results[0]["chunk"]["entity_name"] == "A"


# ---------------------------------------------------------------------------
# Token Budget Tests
# ---------------------------------------------------------------------------


class TestApplyTokenBudget:
    """Tests for apply_token_budget() -- T160, T170."""

    def _make_result(self, name: str, score: float, tokens: int) -> RetrievalResult:
        return RetrievalResult(
            chunk=CodeChunk(
                content=f"class {name}: pass",
                module_path=f"mod.{name.lower()}",
                entity_name=name,
                kind="class",
                file_path=f"mod/{name.lower()}.py",
                start_line=1,
                end_line=1,
            ),
            relevance_score=score,
            token_count=tokens,
        )

    def test_budget_drops_lowest(self) -> None:
        """T160: Budget for 1.5 chunks keeps only top 1."""
        results = [
            self._make_result("A", 0.9, 100),
            self._make_result("B", 0.85, 100),
            self._make_result("C", 0.8, 100),
        ]
        trimmed = apply_token_budget(results, max_tokens=150)
        assert len(trimmed) == 1
        assert trimmed[0]["chunk"]["entity_name"] == "A"

    def test_budget_keeps_all(self) -> None:
        """T170: All chunks within budget returns all."""
        results = [
            self._make_result("A", 0.9, 100),
            self._make_result("B", 0.85, 100),
            self._make_result("C", 0.8, 100),
        ]
        trimmed = apply_token_budget(results, max_tokens=500)
        assert len(trimmed) == 3


# ---------------------------------------------------------------------------
# Context Formatting Tests
# ---------------------------------------------------------------------------


class TestFormatCodebaseContext:
    """Tests for format_codebase_context() -- T180, T190."""

    def test_markdown_formatting(self) -> None:
        """T180: Output has header, instruction, and code blocks."""
        results = [
            RetrievalResult(
                chunk=CodeChunk(
                    content="class GovernanceAuditLog:\n    pass",
                    module_path="assemblyzero.core.audit",
                    entity_name="GovernanceAuditLog",
                    kind="class",
                    file_path="assemblyzero/core/audit.py",
                    start_line=1,
                    end_line=2,
                ),
                relevance_score=0.87,
                token_count=10,
            ),
            RetrievalResult(
                chunk=CodeChunk(
                    content="def validate_config(): pass",
                    module_path="assemblyzero.core.config",
                    entity_name="validate_config",
                    kind="function",
                    file_path="assemblyzero/core/config.py",
                    start_line=1,
                    end_line=1,
                ),
                relevance_score=0.79,
                token_count=8,
            ),
        ]
        context = format_codebase_context(results)
        assert "## Reference Codebase" in context["formatted_text"]
        assert "DO NOT reinvent" in context["formatted_text"]
        assert "```python" in context["formatted_text"]
        assert context["chunks_included"] == 2

    def test_empty_results(self) -> None:
        """T190: Empty results produces empty formatted_text."""
        context = format_codebase_context([])
        assert context["formatted_text"] == ""
        assert context["total_tokens"] == 0
        assert context["chunks_included"] == 0


# ---------------------------------------------------------------------------
# Token Count Tests
# ---------------------------------------------------------------------------


class TestEstimateTokenCount:
    """Tests for estimate_token_count() -- T240."""

    def test_returns_positive(self) -> None:
        """T240: Token count is positive for non-empty text."""
        count = estimate_token_count("class Foo: pass")
        assert count > 0

    def test_no_network_calls(self) -> None:
        """T240: No network calls during token estimation."""
        with mock.patch("urllib3.PoolManager.request") as mock_request:
            count = estimate_token_count("class Foo: pass")
            assert count > 0
            mock_request.assert_not_called()


# ---------------------------------------------------------------------------
# End-to-End & Integration Tests
# ---------------------------------------------------------------------------


class TestRetrieveCodebaseContext:
    """Tests for retrieve_codebase_context() -- T200."""

    def test_audit_lld_retrieves_governance(self) -> None:
        """T200: LLD with 'audit logging' retrieves GovernanceAuditLog."""
        lld_content = (FIXTURES_DIR / "sample_lld_audit.md").read_text(encoding="utf-8")

        # Mock the collection query to return GovernanceAuditLog
        with mock.patch("assemblyzero.rag.codebase_retrieval.chromadb") as mock_chromadb:
            mock_collection = mock.MagicMock()
            mock_client = mock.MagicMock()
            mock_chromadb.PersistentClient.return_value = mock_client
            mock_client.get_collection.return_value = mock_collection
            mock_collection.query.return_value = {
                "documents": [["class GovernanceAuditLog:\n    \"\"\"Audit logging.\"\"\"\n    def log_event(self, event: str) -> bool: ..."]],
                "metadatas": [[{"module_path": "assemblyzero.core.audit", "entity_name": "GovernanceAuditLog", "kind": "class", "file_path": "assemblyzero/core/audit.py", "start_line": 15, "end_line": 30}]],
                "distances": [[0.1]],  # similarity ~= 0.91
            }

            context = retrieve_codebase_context(lld_content)
            assert "GovernanceAuditLog" in context["formatted_text"]


class TestInjectCodebaseContext:
    """Tests for inject_codebase_context() -- T210, T220, T230."""

    def test_inject_on_match(self) -> None:
        """T210: Modified prompt contains 'Reference Codebase' section."""
        from assemblyzero.workflows.implementation_spec.nodes.coder_node import (
            inject_codebase_context,
        )

        base_prompt = "You are a code generation assistant."
        lld_content = "Implement audit logging using GovernanceAuditLog."

        mock_context = CodebaseContext(
            formatted_text="## Reference Codebase\nUse these existing utilities. DO NOT reinvent them.\n\n```python\nclass GovernanceAuditLog: ...\n```\n",
            total_tokens=20,
            chunks_included=1,
            chunks_dropped=0,
            keywords_used=["GovernanceAuditLog", "audit"],
        )

        with mock.patch(
            "assemblyzero.rag.codebase_retrieval.retrieve_codebase_context",
            return_value=mock_context,
        ):
            result = inject_codebase_context(base_prompt, lld_content)
            assert "Reference Codebase" in result
            assert base_prompt in result

    def test_passthrough_on_no_match(self) -> None:
        """T220: Original prompt unchanged when no matches."""
        from assemblyzero.workflows.implementation_spec.nodes.coder_node import (
            inject_codebase_context,
        )

        base_prompt = "You are a code generation assistant."
        lld_content = "Something completely unrelated."

        mock_context = CodebaseContext(
            formatted_text="",
            total_tokens=0,
            chunks_included=0,
            chunks_dropped=0,
            keywords_used=[],
        )

        with mock.patch(
            "assemblyzero.rag.codebase_retrieval.retrieve_codebase_context",
            return_value=mock_context,
        ):
            result = inject_codebase_context(base_prompt, lld_content)
            assert result == base_prompt

    def test_exception_handling(self, caplog: pytest.LogCaptureFixture) -> None:
        """T230: Exception during retrieval logs warning, returns original prompt."""
        from assemblyzero.workflows.implementation_spec.nodes.coder_node import (
            inject_codebase_context,
        )

        base_prompt = "You are a code generation assistant."
        lld_content = "Any content."

        with mock.patch(
            "assemblyzero.rag.codebase_retrieval.retrieve_codebase_context",
            side_effect=RuntimeError("Connection failed"),
        ):
            with caplog.at_level(logging.WARNING):
                result = inject_codebase_context(base_prompt, lld_content)

            assert result == base_prompt
            assert "Codebase retrieval failed" in caplog.text


# ---------------------------------------------------------------------------
# Embedding Tests
# ---------------------------------------------------------------------------


class TestEmbeddings:
    """Tests for embedding generation -- T270."""

    @pytest.mark.rag
    def test_local_embedding_dimensions(self) -> None:
        """T270: SentenceTransformer generates 384-dim embeddings locally."""
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("all-MiniLM-L6-v2")
        embeddings = model.encode(["class Foo: pass"])
        assert embeddings.shape[1] == 384
