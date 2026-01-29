# The Scout: External Intelligence Gathering Workflow

## User Story
As a **developer maintaining AgentOS**,
I want **an automated research agent that finds best practices from popular external projects**,
So that **I can identify gaps in our implementation before they become technical debt**.

## Objective
Create a proactive research workflow that searches GitHub/Web for solutions to a given problem, analyzes top implementations, compares them against our internal code, and produces an "Innovation Brief" documenting specific deficiencies and recommendations.

## UX Flow

### Scenario 1: Happy Path - Finding Better State Persistence
1. User runs: `python tools/run_scout_workflow.py --topic "LangGraph persistence patterns" --internal agentos/core/state.py`
2. System searches GitHub for repositories with >500 stars matching the topic
3. System identifies Top-3 relevant repositories
4. System extracts README.md, architecture docs, and key code files from each
5. System compares external patterns against `agentos/core/state.py`
6. System generates `ideas/active/innovation-langgraph-persistence-patterns.md`
7. Result: User receives actionable brief showing sqlite-vss pattern vs our JSON dumps

### Scenario 2: No Internal Target Specified
1. User runs: `python tools/run_scout_workflow.py --topic "secure credential rotation"`
2. System searches and analyzes external solutions
3. System generates brief without gap analysis section
4. Result: Pure research report documenting external best practices for future reference

### Scenario 3: No Relevant Results Found
1. User runs: `python tools/run_scout_workflow.py --topic "obscure niche pattern xyz"`
2. System searches but finds <3 relevant repositories
3. System logs warning: "Insufficient external data for topic"
4. System generates partial brief with available findings
5. Result: Brief includes "Low Confidence" flag and suggests alternative search terms

### Scenario 4: Rate Limited / Network Error
1. User runs scout workflow
2. GitHub API returns 403 rate limit error
3. System retries with exponential backoff (max 3 attempts)
4. If still failing, system saves partial state and exits gracefully
5. Result: Clear error message with instructions to retry later or provide GitHub token

## Requirements

### Research Engine
1. Search GitHub API for repositories matching topic query
2. Filter results by star count (configurable, default >500)
3. Extract README.md and architecture documentation from top results
4. Support web search fallback for non-GitHub sources
5. Handle pagination for comprehensive results

### Analysis Engine
1. Parse and summarize external implementation patterns
2. Identify key architectural decisions in external code
3. Compare external patterns against specified internal file(s)
4. Categorize gaps by type: Complexity, Performance, Reliability, Security
5. Quantify deficiency severity where possible

### Output Generation
1. Generate standardized Innovation Brief in Markdown
2. Include direct links to source repositories/files
3. Provide actionable recommendations with effort estimates
4. Support multiple output formats (markdown, JSON for programmatic use)

### CLI Interface
1. Accept `--topic` as required argument
2. Accept `--internal` as optional path to compare against
3. Accept `--min-stars` to filter repository quality (default: 500)
4. Accept `--output` to specify custom output path
5. Accept `--dry-run` to preview search without generating brief

## Technical Approach

- **State Graph (`agentos/workflows/scout/graph.py`):** LangGraph-based workflow with 4 nodes (Explorer → Extractor → Gap Analyst → Innovation Scribe) managing research state transitions
- **N0_Explorer Node:** Uses GitHub Search API and optional Google Search MCP tool to identify top repositories
- **N1_Extractor Node:** Fetches raw content via GitHub API, parses Markdown/code files, generates structured summaries
- **N2_Gap_Analyst Node:** LLM-powered comparison engine that diffs external patterns against internal code
- **N3_Innovation_Scribe Node:** Template-based Markdown generator producing standardized briefs
- **CLI Runner (`tools/run_scout_workflow.py`):** Thin wrapper that initializes graph, handles args, and manages output

## Security Considerations

- **API Keys:** GitHub token read from environment variable `GITHUB_TOKEN`, never logged or persisted
- **Rate Limiting:** Respect GitHub API limits (5000 req/hr authenticated, 60/hr unauthenticated)
- **Content Safety:** Extracted code is read-only, never executed
- **Network Requests:** All requests use HTTPS, timeout after 30s
- **Output Location:** Briefs written only to `ideas/active/` directory, path traversal prevented

## Files to Create/Modify

### New Files
- `agentos/workflows/scout/__init__.py` — Package initialization
- `agentos/workflows/scout/graph.py` — LangGraph state machine definition
- `agentos/workflows/scout/nodes.py` — Node implementations (Explorer, Extractor, Gap Analyst, Scribe)
- `agentos/workflows/scout/prompts.py` — LLM prompts for analysis nodes
- `agentos/workflows/scout/templates.py` — Innovation Brief Markdown templates
- `tools/run_scout_workflow.py` — CLI entry point
- `tests/workflows/scout/test_graph.py` — Unit tests for state transitions
- `tests/workflows/scout/test_nodes.py` — Unit tests for individual nodes
- `ideas/active/.gitkeep` — Ensure output directory exists

### Modified Files
- `agentos/workflows/__init__.py` — Register scout workflow
- `docs/0003-file-inventory.md` — Add new files to inventory

## Dependencies
- GitHub API access (via `PyGithub` or direct REST calls)
- Existing LangGraph infrastructure in `agentos/workflows/`
- LLM client for analysis nodes (existing `gemini_client.py`)

## Out of Scope (Future)
- **Automatic PR creation** — Brief is decision artifact only, human decides action
- **Continuous monitoring** — No scheduled/recurring scans (future cron job)
- **Multi-language support** — Focus on Python repositories initially
- **Code modification** — Scout reports gaps but never changes code
- **Competitive analysis** — No tracking of specific competitor projects over time

## Acceptance Criteria
- [ ] `python tools/run_scout_workflow.py --topic "python state persistence" --internal agentos/core/state.py` completes without error
- [ ] Generated brief includes at least one external repository with >500 stars
- [ ] Generated brief includes accurate README summary (verified manually)
- [ ] Generated brief identifies at least one specific gap when internal target provided
- [ ] Generated brief follows Innovation Brief Template structure exactly
- [ ] `--dry-run` flag outputs search plan without creating files
- [ ] Rate limit errors produce clear user-facing message with retry instructions
- [ ] Invalid `--internal` path produces helpful error (file not found)

## Definition of Done

### Implementation
- [ ] Core workflow graph implemented with all 4 nodes
- [ ] CLI tool with full argument parsing
- [ ] Unit tests written and passing (>80% coverage on nodes)
- [ ] Integration test with mocked GitHub API responses

### Tools
- [ ] `tools/run_scout_workflow.py` created and executable
- [ ] Tool includes `--help` with usage examples
- [ ] Tool documented in tools README

### Documentation
- [ ] Update wiki with Scout workflow documentation
- [ ] Update README.md with Scout feature description
- [ ] Create ADR for external research workflow design decisions
- [ ] Add new files to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/scout-workflow/implementation-report.md` created
- [ ] `docs/reports/scout-workflow/test-report.md` created

### Verification
- [ ] Run 0809 Security Audit - PASS (API key handling)
- [ ] Run 0810 Privacy Audit - PASS (no PII in briefs)
- [ ] Run 0817 Wiki Alignment Audit - PASS

## Testing Notes

**To test happy path:**
```bash
export GITHUB_TOKEN="your_token_here"
python tools/run_scout_workflow.py --topic "python async task queue" --internal agentos/core/scheduler.py
cat ideas/active/innovation-python-async-task-queue.md
```

**To test rate limiting:**
```bash
unset GITHUB_TOKEN  # Force unauthenticated (60 req/hr limit)
for i in {1..70}; do python tools/run_scout_workflow.py --topic "test $i" --dry-run; done
# Should see rate limit error and backoff behavior
```

**To test invalid internal path:**
```bash
python tools/run_scout_workflow.py --topic "test" --internal nonexistent/file.py
# Should see: "Error: Internal target 'nonexistent/file.py' not found"
```

**To verify brief accuracy:**
1. Run scout on known topic (e.g., "FastAPI dependency injection")
2. Manually visit top repository in brief
3. Confirm README summary matches actual README content
4. Confirm identified patterns exist in external codebase