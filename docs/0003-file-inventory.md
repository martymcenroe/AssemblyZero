# AssemblyZero - File Inventory & Status Map

**Document:** 0003
**Version:** 2.0
**Last Updated:** 2026-03-01

## 1. Status Taxonomy

| Status | Meaning |
|--------|---------|
| **Stable** | Verified, documented, production-ready |
| **Beta** | Functional but lacks full test coverage or documentation |
| **In-Progress** | Active development; expect instability |
| **Placeholder** | Skeleton or empty file; do not run |
| **Legacy** | Deprecated/archived (reference only) |

---

## 2. Documentation Inventory

### Standards (00xx) - 14 files

| File | Status | Description |
|------|--------|-------------|
| `0001-orchestration-protocol.md` | Stable | Multi-agent coordination rules |
| `0002-coding-standards.md` | Stable | Code style and practices |
| `0003-agent-prohibited-actions.md` | Stable | Forbidden agent actions |
| `0004-mermaid-diagrams.md` | Stable | Diagram conventions |
| `0005-session-closeout-protocol.md` | Stable | End-of-session procedures |
| `0006-standard-labels.md` | Stable | GitHub labels |
| `0007-testing-strategy.md` | Stable | Test-first philosophy |
| `0008-documentation-convention.md` | Stable | c/p pattern for CLI vs Prompt docs |
| `0009-canonical-project-structure.md` | Stable | Standard project layout |
| `0010-prompt-schema.md` | Stable | Prompt template schema |
| `0011-audit-decisions.md` | Stable | Audit decision format |
| `0012-lineage-versioning.md` | Stable | Lineage file versioning |
| `0013-operational-dashboard-reference-architecture.md` | Stable | Dashboard reference architecture |
| `0014-extract-and-discard-pattern.md` | Stable | Extract-and-discard pattern |

### Templates (01xx) - 10 files

| File | Status | Description |
|------|--------|-------------|
| `0100-template-guide.md` | Stable | How to use templates |
| `0101-issue-template.md` | Stable | GitHub issue format |
| `0102-feature-lld-template.md` | Stable | Low-level design |
| `0103-implementation-report-template.md` | Stable | Post-impl docs |
| `0104-adr-template.md` | Stable | ADR format |
| `0105-implementation-plan-template.md` | Stable | Pre-impl planning |
| `0106-lld-pre-impl-review.md` | Stable | Review checklist |
| `0107-test-script-template.md` | Stable | Test case format |
| `0108-test-report-template.md` | Stable | Test results format |
| `0109-runbook-template.md` | Stable | Operational procedures |

### ADRs (02xx) - 14 files (12 active, 2 superseded)

| File | Status | Description |
|------|--------|-------------|
| `0201-adversarial-audit-philosophy.md` | Stable | Security mindset |
| `0202-claude-staging-pattern.md` | Stable | Safe deployment |
| `0203-git-worktree-isolation.md` | Stable | Multi-agent safety |
| `0204-janitor-probe-plugin-system.md` | Stable | Janitor probe registry pattern |
| `0204-single-identity-orchestration-superseded.md` | Legacy | Agent identity (superseded by 0204-janitor) |
| `0205-rag-librarian.md` | Stable | RAG retrieval for LLD context |
| `0205-test-first-philosophy-superseded.md` | Legacy | Quality approach (superseded by 0205-rag) |
| `0206-bidirectional-sync-architecture.md` | Stable | Cross-project propagation |
| `0207-llm-team-coverage-targets.md` | Stable | LLM team coverage targets |
| `0208-llm-invocation-strategy.md` | Stable | LLM invocation patterns |
| `0209-playwright-persistent-context-for-extensions.md` | Stable | Playwright browser context |
| `0210-discworld-persona-convention.md` | Stable | Persona naming rules |
| `0211-rag-architecture.md` | Stable | RAG architecture (Brutha foundation) |
| `0212-local-only-embeddings.md` | Stable | Local-only embeddings policy |

### Research (02xx-R) - 1 file

| File | Status | Description |
|------|--------|-------------|
| `research/0258-mcp-openclaw-investigation.md` | Stable | MCP and OpenClaw for coordination |

### Skills (06xx) - 28 files

Skill documentation uses the c/p convention (CLI + Prompt pairs).

| File | Status | Description |
|------|--------|-------------|
| `0600-command-index.md` | Stable | All commands documented |
| `0601-gemini-dual-review.md` | Stable | AI-to-AI review |
| `0602-gemini-lld-review.md` | Stable | Design review |
| `0604-gemini-retry.md` | Stable | Exponential backoff for Gemini |
| `0699-skill-instructions-index.md` | Stable | Skill index |
| `0620c-sync-permissions-cli.md` | Stable | CLI: Permission sync |
| `0620p-sync-permissions-prompt.md` | Stable | Prompt: Permission sync |
| `0621c-cleanup-cli.md` | Stable | CLI: Session cleanup |
| `0621p-cleanup-prompt.md` | Stable | Prompt: Session cleanup |
| `0622c-onboard-cli.md` | Stable | CLI: Agent onboarding |
| `0622p-onboard-prompt.md` | Stable | Prompt: Agent onboarding |
| `0623c-friction-cli.md` | Stable | CLI: Permission friction |
| `0623p-friction-prompt.md` | Stable | Prompt: Permission friction |
| `0625c-code-review-cli.md` | Stable | CLI: Code review |
| `0625p-code-review-prompt.md` | Stable | Prompt: Code review |
| `0625c-gemini-retry-cli.md` | Stable | CLI: Gemini retry |
| `0625p-gemini-retry-prompt.md` | Stable | Prompt: Gemini retry |
| `0626c-commit-push-pr-cli.md` | Stable | CLI: Git workflow |
| `0626p-commit-push-pr-prompt.md` | Stable | Prompt: Git workflow |
| `0626c-gemini-rotate-cli.md` | Stable | CLI: Gemini rotation |
| `0626p-gemini-rotate-prompt.md` | Stable | Prompt: Gemini rotation |
| `0627c-test-gaps-cli.md` | Stable | CLI: Test gap analysis |
| `0627p-test-gaps-prompt.md` | Stable | Prompt: Test gap analysis |
| `0627c-assemblyzero-harvest-cli.md` | Stable | CLI: Pattern harvester |
| `0627p-assemblyzero-harvest-prompt.md` | Stable | Prompt: Pattern harvester |
| `0628c-Manual-Issue-Review-Prompt.md` | Stable | Manual issue review |
| `0629c-Manual-LLD-Review-Prompt.md` | Stable | Manual LLD review |
| `0630c-Manual-Implementation-Review-Prompt.md` | Stable | Manual implementation review |

### Audits (08xx) - 34 files

| File | Status | Description |
|------|--------|-------------|
| `0800-audit-index.md` | Stable | Master audit list |
| `0801-security-audit.md` | Stable | OWASP security |
| `0802-privacy-audit.md` | Stable | IAPP privacy |
| `0803-code-quality-audit.md` | Stable | Maintainability |
| `0804-accessibility-audit.md` | Stable | WCAG compliance |
| `0805-license-compliance.md` | Stable | OSS licenses |
| `0806-bias-fairness.md` | Stable | AI fairness |
| `0807-explainability.md` | Stable | AI transparency |
| `0808-ai-safety-audit.md` | Stable | Safety measures |
| `0809-agentic-ai-governance.md` | Stable | Agent oversight |
| `0810-ai-management-system.md` | Stable | ISO 42001 |
| `0811-ai-incident-post-mortem.md` | Stable | Failure analysis |
| `0812-ai-supply-chain.md` | Stable | Dependencies |
| `0813-claude-capabilities.md` | Stable | Model features |
| `0814-horizon-scanning-protocol.md` | Stable | Threat monitoring |
| `0815-permission-friction.md` | Stable | Approval overhead |
| `0816-permission-permissiveness.md` | Stable | Access control |
| `0817-assemblyzero-audit.md` | Stable | Self-audit |
| `0817-audit-wiki-alignment.md` | Stable | Wiki sync |
| `0832-cross-project-harvest.md` | Stable | Pattern harvesting |
| `0832-audit-cost-optimization.md` | Stable | Token efficiency |
| `0833-audit-gitignore-encryption.md` | Stable | Encrypt vs ignore |
| `0834-audit-worktree-hygiene.md` | Stable | Worktree cleanup |
| `0835-audit-structure-compliance.md` | Stable | Project structure |
| `0836-audit-gitignore-consistency.md` | Stable | Gitignore patterns |
| `0837-audit-readme-compliance.md` | Stable | README standards |
| `0838-audit-broken-references.md` | Stable | Cross-reference validation |
| `0899-meta-audit.md` | Stable | Audit the audits |

### Runbooks (09xx) - 5 files

| File | Status | Description |
|------|--------|-------------|
| `0900-runbook-index.md` | Stable | All runbooks |
| `0901-new-project-setup.md` | Stable | Project init |
| `0902-nightly-assemblyzero-audit.md` | Stable | Scheduled audit |
| `0903-windows-scheduled-tasks.md` | Stable | Windows Task Scheduler |
| `0905-gemini-credentials.md` | Stable | Gemini credential management |

---

## 3. Tools Inventory (36 files)

### Workflow Runners

| File | Status | Description |
|------|--------|-------------|
| `tools/run_requirements_workflow.py` | Stable | LLD workflow orchestration |
| `tools/run_implement_from_lld.py` | Stable | TDD implementation workflow |
| `tools/run_implementation_spec_workflow.py` | Stable | Implementation spec workflow |
| `tools/run_issue_workflow.py` | Stable | Issue analysis workflow |
| `tools/run_scout_workflow.py` | Stable | Scout (Angua) intelligence workflow |
| `tools/run_janitor_workflow.py` | Stable | Janitor (Lu-Tze) hygiene workflow |
| `tools/run_audit.py` | Stable | Audit execution runner |
| `tools/orchestrate.py` | Stable | End-to-end pipeline orchestration (Moist) |

### Core Tools

| File | Status | Description |
|------|--------|-------------|
| `tools/assemblyzero-generate.py` | Stable | Config generator from templates |
| `tools/assemblyzero-permissions.py` | Stable | Permission manager (sync, clean, merge-up) |
| `tools/assemblyzero_config.py` | Stable | Config loader for path parameterization |
| `tools/assemblyzero_credentials.py` | Stable | Credential management utilities |
| `tools/assemblyzero-harvest.py` | Beta | Pattern harvester for permission discovery |
| `tools/archive_worktree_lineage.py` | Stable | Post-merge lineage archival |
| `tools/new_repo_setup.py` | Stable | New repository initialization |

### RAG & Knowledge Base

| File | Status | Description |
|------|--------|-------------|
| `tools/rebuild_knowledge_base.py` | Stable | Rebuild ChromaDB vector store from source docs |
| `tools/mine_verdict_patterns.py` | Stable | Analyze Gemini verdicts for template improvement |
| `tools/modernize_dependencies.py` | Stable | Dependency modernization tool |

### Gemini Integration

| File | Status | Description |
|------|--------|-------------|
| `tools/gemini-retry.py` | Stable | Exponential backoff for MODEL_CAPACITY_EXHAUSTED |
| `tools/gemini-rotate.py` | Stable | Credential rotation for quota management |
| `tools/gemini-test-credentials.py` | Stable | Credential validation tool |
| `tools/gemini-test-credentials-v2.py` | Stable | Credential validation (v2) |

### Analysis & Reporting

| File | Status | Description |
|------|--------|-------------|
| `tools/verdict-analyzer.py` | Stable | Parse and analyze Gemini verdicts |
| `tools/view_audit.py` | Stable | Display audit results |
| `tools/collect_cross_project_metrics.py` | Stable | Multi-repo analytics |
| `tools/collect-cross-project-metrics.py` | Stable | Multi-repo analytics (alt) |
| `tools/audit_schedule_check.py` | Stable | Audit scheduling verification |
| `tools/test-gate.py` | Stable | Test gate enforcement |

### Utilities

| File | Status | Description |
|------|--------|-------------|
| `tools/append_session_log.py` | Stable | Session tracking |
| `tools/update-doc-refs.py` | Beta | Documentation reference updater |
| `tools/claude-usage-scraper.py` | Stable | Quota visibility via TUI scraping |
| `tools/consolidate_logs.py` | Stable | Merge session logs |
| `tools/clean_transcript.py` | Stable | Session transcript sanitization |
| `tools/transcript_filters.py` | Stable | Transcript filter utilities |
| `tools/backfill_issue_audit.py` | Stable | Bulk audit backfill |
| `tools/backfill_telemetry.py` | Stable | Historical telemetry backfill |

---

## 4. RAG Subsystem (`assemblyzero/rag/`) - 14 files

| File | Status | Description |
|------|--------|-------------|
| `__init__.py` | Stable | Public API, singleton factories (`get_store`, `get_query_engine`) |
| `config.py` | Stable | Immutable `RAGConfig` dataclass |
| `models.py` | Stable | `ChunkMetadata`, `RetrievedDocument`, `IngestionSummary` |
| `errors.py` | Stable | `RAGError` hierarchy |
| `store.py` | Stable | VectorStore lifecycle management |
| `vector_store.py` | Stable | VectorStoreManager (low-level ChromaDB ops) |
| `embeddings.py` | Stable | `LocalEmbeddingProvider` (all-MiniLM-L6-v2) |
| `collections.py` | Stable | Collection CRUD operations |
| `chunking.py` | Stable | `TextChunk`, `TextChunker` |
| `chunker.py` | Stable | Chunking algorithm implementation |
| `query.py` | Stable | `QueryEngine`, `QueryResult`, `QueryResponse` |
| `librarian.py` | Stable | LibrarianNode (document retrieval) |
| `codebase_retrieval.py` | Stable | Hex: AST-based code indexing and retrieval |
| `dependencies.py` | Stable | Optional dependency checking |

---

## 5. Janitor Workflow (`assemblyzero/workflows/janitor/`) - 10 files

| File | Status | Description |
|------|--------|-------------|
| `__init__.py` | Stable | Package init |
| `state.py` | Stable | `JanitorState`, `ProbeResult`, `ProbeScope` |
| `graph.py` | Stable | LangGraph state machine |
| `fixers.py` | Stable | Auto-fix implementations |
| `reporter.py` | Stable | Hygiene report generation |
| `probes/__init__.py` | Stable | Probe registry (`PROBE_REGISTRY`) |
| `probes/links.py` | Stable | Broken link detection |
| `probes/worktrees.py` | Stable | Stale worktree detection |
| `probes/harvest.py` | Stable | Pattern harvest probe |
| `probes/todo.py` | Stable | TODO archaeology probe |

---

## 6. Architecture Diagrams (`docs/architecture/`) - 3 files

| File | Status | Description |
|------|--------|-------------|
| `system-overview.md` | Stable | Persona map with layer diagram |
| `data-flow.md` | Stable | Pipeline and RAG data flows |
| `workflow-interactions.md` | Stable | Workflow chaining and human gates |

---

## 7. Configuration Inventory

| File | Status | Description |
|------|--------|-------------|
| `CLAUDE.md` | Stable | Core agent rules |
| `.claude/project.json.example` | Stable | Project config template |
| `.claude/commands/*.md` | Stable | 9 skill definitions (see below) |
| `.claude/templates/*.template` | Stable | Config templates |

### Skills/Commands (9 files)

| File | Status | Description |
|------|--------|-------------|
| `.claude/commands/audit.md` | Stable | Full audit suite |
| `.claude/commands/cleanup.md` | Stable | Session cleanup |
| `.claude/commands/code-review.md` | Stable | Parallel code review |
| `.claude/commands/commit-push-pr.md` | Stable | Git workflow |
| `.claude/commands/friction.md` | Stable | Permission friction analysis |
| `.claude/commands/onboard.md` | Stable | Agent onboarding |
| `.claude/commands/promote.md` | Stable | Pattern promotion to AssemblyZero |
| `.claude/commands/test-gaps.md` | Stable | Test gap mining |
| `.claude/commands/checkpoint.md` | Stable | Session state checkpoint |

---

## 8. Summary Statistics

| Category | Count | Status |
|----------|-------|--------|
| Standards | 14 | All stable |
| Templates | 10 | All stable |
| ADRs | 14 | 12 active, 2 superseded |
| Skills docs | 28 | All stable |
| Audits | 34 | 28 stable, 6 stubs |
| Runbooks | 5 | All stable |
| Architecture | 3 | All stable |
| RAG subsystem | 14 | All stable |
| Janitor workflow | 10 | All stable |
| Tools | 36 | 34 stable, 2 beta |
| Commands | 9 | All stable |
| **Total Docs** | **132** | |
| **Total Tools** | **36** | |
| **Total Code (RAG + Janitor)** | **24** | |

---

## 9. Maintenance Notes

- Review this inventory during `/cleanup --full`
- Update when adding new files
- Run numbering audit if files added without numbers
- RAG and janitor subsystems are part of the `assemblyzero` package, not standalone docs

---

*Last audit: 2026-03-01*
