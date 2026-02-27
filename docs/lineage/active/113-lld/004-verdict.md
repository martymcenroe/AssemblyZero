# LLD Review: #113-Feature: Vector Database Infrastructure (RAG Foundation)

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD provides a robust foundation for RAG infrastructure with clear boundaries, appropriate technology choices (ChromaDB, SentenceTransformers), and a comprehensive test plan. However, it requires revision to address a potential infinite loop vector in the chunking logic (Tier 1 Cost) and to verify the path traversal security mitigation claimed in Section 7.1 (Tier 2 Quality).

## Open Questions Resolved
- [x] ~~Should ChromaDB persistence use a single SQLite file or directory-based storage?~~ **RESOLVED: Use directory-based storage.** This aligns with the standard `PersistentClient` behavior and the proposed `.assemblyzero/vector_store/` directory structure.
- [x] ~~What is the maximum document chunk size for embeddings?~~ **RESOLVED: 512 tokens.** This matches the maximum context window of the selected model (`all-MiniLM-L6-v2`) and provides a good balance for code context.
- [x] ~~Should collection schemas be enforced via metadata validation or left flexible?~~ **RESOLVED: Flexible.** At this foundational stage, enforcing strict schemas for heterogeneous data (code vs. docs) creates unnecessary friction. Rely on consumer-side validation.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Vector store initializes on first use with lazy loading | T010, T020, T080, T330 | ✓ Covered |
| 2 | Multiple named collections are supported | T040, T050, T320 | ✓ Covered |
| 3 | Embedding generation is fully local using SentenceTransformers | T060, T070, T080 | ✓ Covered |
| 4 | Librarian (#88) and Hex (#92) can query independently | T090, T100 | ✓ Covered |
| 5 | Graceful degradation when store/deps missing | T030, T110, T120, T130, T340 | ✓ Covered |
| 6 | Persistent storage at `.assemblyzero/vector_store/` | T140, T150 | ✓ Covered |
| 7 | Documents can be added, queried, and deleted via Unified Engine | T160, T170, T180, T190, T200, T300, T310 | ✓ Covered |
| 8 | Text chunking utility provided | T210, T220, T230, T240, T250 | ✓ Covered |
| 9 | Thread-safe singleton store | T260, T270 | ✓ Covered |
| 10 | Public functions have type hints and docstrings | T280, T290 | ✓ Covered |

**Coverage Calculation:** 10 requirements covered / 10 total = **100%**

**Verdict:** PASS

## Tier 1: BLOCKING Issues

### Cost
- [ ] **Loop Bounds in Chunker:** The `TextChunker` logic implies a sliding window mechanism. If `chunk_overlap` is configured to be greater than or equal to `chunk_size`, the loop stride becomes $\le 0$, resulting in an infinite loop.
    *   **Recommendation:** Explicitly validate `chunk_overlap < chunk_size` in `RAGConfig.__post_init__` or `TextChunker.__init__`. Add a test case (e.g., T350) that asserts a `ValueError` is raised when initialized with invalid overlap settings.

### Safety
- [ ] No issues found.

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] No issues found.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Missing Security Test (Gap):** Section 7.1 explicitly claims a security mitigation: *"Path traversal in file chunking | TextChunker.chunk_file() validates path exists and is within project root"*. However, Section 10 does not contain a test case to verify this logic.
    *   **Recommendation:** Add a negative test scenario (e.g., T360) where `chunk_file` is called with a path outside the project root (e.g., a temp file created in `/tmp` or via `..`), asserting that it raises a `RAGError` or `ValueError` as claimed.

## Tier 3: SUGGESTIONS
- **Performance:** Consider adding a benchmark test (marked `@pytest.mark.slow`) that ingests a larger corpus (e.g., 1MB of text) to ensure the 50ms/batch target is realistic on standard hardware.
- **Dependency Management:** Explicitly pin `torch` to a CPU-only version in `pyproject.toml` if possible (e.g., via extra index url) to avoid downloading the multi-GB CUDA version for users who don't need it, though this is often handled at the environment level.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision