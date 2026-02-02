# Issue #93: The Scout: External Intelligence Gathering Workflow

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
2. System displays warning: **"Warning: Target file 'agentos/core/state.py' will be sent to external LLM provider (Gemini) for analysis. Continue? [y/N]"**
3. User confirms with `y`
4. System searches GitHub for repositories with >500 stars matching the topic
5. System identifies Top-3 relevant repositories
6. System extracts README.md, architecture docs, and key code files from each
7. System captures license type from each external repository
8. System compares external patterns against `agentos/core/state.py`
9. System generates `ideas/active/innovation-langgraph-persistence-patterns.md`
10. Result: User receives actionable brief showing sqlite-vss pattern vs our JSON dumps, including license information for each external source

### Scenario 2: No Internal Target Specified
1. User runs: `python tools/run_scout_workflow.py --topic "secure credential rotation"`
2. System searches and analyzes external solutions (no internal code transmitted)
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

### Scenario 5: User Declines Data Transmission Warning
1. User runs: `python tools/run_scout_workflow.py --topic "patterns" --internal agentos/core/state.py`
2. System displays data transmission warning
3. User enters `n` or presses Enter (default)
4. System exits with message: "Aborted. Run without --internal flag for external-only research."
5. Result: No data transmitted, user informed of alternative

### Scenario 6: Token Budget Exceeded
1. User runs scout workflow with large internal file
2. System estimates token count exceeds `--max-tokens` limit
3. System exits with error: "Estimated token count (45,000) exceeds limit (30,000). Use --max-tokens to increase or reduce scope."
4. Result: Prevents runaway costs, user can adjust parameters

## Requirements

### Research Engine
1. Search GitHub API for repositories matching topic query
2. Filter results by star count (configurable, default >500)
3. Extract README.md and architecture documentation from top results
4. **Capture and record license type (MIT, Apache-2.0, GPL, etc.) for each external repository**
5. Support web search fallback for non-GitHub sources
6. Handle pagination for comprehensive results

### Analysis Engine
1. Parse and summarize external implementation patterns
2. Identify key architectural decisions in external code
3. Compare external patterns against specified internal file(s)
4. Categorize gaps by type: Complexity, Performance, Reliability, Security
5. Quantify deficiency severity where possible

### Output Generation
1. Generate standardized Innovation Brief in Markdown
2. Include direct links to source repositories/files
3. **Include license type for each external repository in the brief**
4. Provide actionable recommendations with effort estimates
5. Support multiple output formats: `--format markdown` (default) and `--format json` for programmatic use

### CLI Interface
1. Accept `--topic` as required argument
2. Accept `--internal` as optional path to compare against
3. Accept `--min-stars` to filter repository quality (default: 500)
4. Accept `--output` to specify custom output path
5. Accept `--dry-run` to preview search without generating brief
6. Accept `--format` to specify output format (`markdown` or `json`, default: `markdown`)
7. **Accept `--max-tokens` to set token budget cap (default: 30,000 tokens)**
8. **Accept `--yes` / `-y` to skip interactive confirmation prompts**

### Cost Controls
1. **Estimated cost per run: ~$0.05-0.15 via Gemini 1.5 Flash** (varies by internal file size)
2. **Model tier: Gemini 1.5 Flash** (balances cost/performance for research tasks)
3. **Default token cap: 30,000 tokens** (prevents runaway costs)
4. System MUST estimate token count before LLM calls and abort if exceeding `--max-tokens`
5. Display estimated cost in `--dry-run` output

### Data Privacy & Legal
1. **When `--internal` flag is used, internal proprietary source code is transmitted to the LLM provider (Google Gemini) for analysis**
2. **Display interactive warning and require confirmation before transmitting internal code** (unless `--yes` flag provided)
3. All data transmission uses HTTPS encryption
4. No internal code is persisted outside the LLM request/response cycle

## Technical Approach

- **State Graph (`agentos/workflows/scout/graph.py`):** LangGraph-based workflow with 4 nodes (Explorer → Extractor → Gap Analyst → Innovation Scribe) managing research state transitions
- **N0_Explorer Node:** Uses GitHub Search API and optional Google Search MCP tool to identify top repositories
- **N1_Extractor Node:** Fetches raw content via GitHub API, parses Markdown/code files, generates structured summaries, **captures repository license metadata**
- **N2_Gap_Analyst Node:** LLM-powered comparison engine that diffs external patterns against internal code
- **N3_Innovation_Scribe Node:** Template-based Markdown generator producing standardized briefs with license attribution
- **CLI Runner (`tools/run_scout_workflow.py`):** Thin wrapper that initializes graph, handles args, **enforces token budget**, **displays data transmission warnings**, and manages output
- **Token Estimator:** Pre-flight check that estimates total token usage before invoking LLM nodes

## Security Considerations

- **API Keys:** GitHub token read from environment variable `GITHUB_TOKEN`, never logged or persisted
- **Rate Limiting:** Respect GitHub API limits (5000 req/hr authenticated, 60/hr unauthenticated)
- **Content Safety:** Extracted code is read-only, never executed
- **Network Requests:** All requests use HTTPS, timeout after 30s
- **Output Location:** Briefs written only to `ideas/active/` directory, path traversal prevented
- **Data Transmission:** Internal code sent to Gemini API only with explicit user confirmation

## Files to Create/Modify

### New Files
- `agentos/workflows/scout/__init__.py` — Package initialization
- `agentos/workflows/scout/graph.py` — LangGraph state machine definition
- `agentos/workflows/scout/nodes.py` — Node implementations (Explorer, Extractor, Gap Analyst, Scribe)
- `agentos/workflows/scout/prompts.py` — LLM prompts for analysis nodes
- `agentos/workflows/scout/templates.py` — Innovation Brief Markdown templates
- `agentos/workflows/scout/token_estimator.py` — Token counting and budget enforcement
- `tools/run_scout_workflow.py` — CLI entry point
- `tests/workflows/scout/test_graph.py` — Unit tests for state transitions
- `tests/workflows/scout/test_nodes.py` — Unit tests for individual nodes
- `tests/workflows/scout/test_token_estimator.py` — Unit tests for token budget enforcement
- `tests/fixtures/golden-brief-summary.md` — Golden fixture for similarity testing
- `ideas/active/.gitkeep` — Ensure output directory exists

### Modified Files
- `agentos/workflows/__init__.py` — Register scout workflow
- `docs/0003-file-inventory.md` — Add new files to inventory

## Dependencies
- GitHub API access (via `PyGithub` or direct REST calls)
- Existing LangGraph infrastructure in `agentos/workflows/`
- LLM client for analysis nodes (existing `gemini_client.py`)
- Token counting library (`tiktoken` or equivalent for estimation)

## Out of Scope (Future)
- **Automatic PR creation** — Brief is decision artifact only, human decides action
- **Continuous monitoring** — No scheduled/recurring scans (future cron job)
- **Multi-language support** — Focus on Python repositories initially
- **Code modification** — Scout reports gaps but never changes code
- **Competitive analysis** — No tracking of specific competitor projects over time
- **License compliance enforcement** — Scout reports licenses but does not block based on them

## Acceptance Criteria
- [ ] `python tools/run_scout_workflow.py --topic "python state persistence" --internal agentos/core/state.py --yes` completes without error
- [ ] Generated brief includes at least one external repository with >500 stars
- [ ] **Generated brief README summary matches `tests/fixtures/golden-brief-summary.md` within 90% cosine similarity** (automated verification)
- [ ] Generated brief identifies at least one specific gap when internal target provided
- [ ] Generated brief follows Innovation Brief Template structure exactly
- [ ] **Generated brief includes license type for each external repository**
- [ ] `--dry-run` flag outputs search plan and estimated token cost without creating files
- [ ] Rate limit errors produce clear user-facing message with retry instructions
- [ ] Invalid `--internal` path produces helpful error (file not found)
- [ ] **Using `--internal` without `--yes` displays data transmission warning and requires confirmation**
- [ ] **Exceeding `--max-tokens` limit aborts with clear error message before LLM invocation**
- [ ] **`--format json` produces valid JSON output**

## Definition of Done

### Implementation
- [ ] Core workflow graph implemented with all 4 nodes
- [ ] CLI tool with full argument parsing including `--max-tokens`, `--format`, and `--yes`
- [ ] Token estimation and budget enforcement implemented
- [ ] Data transmission warning and confirmation flow implemented
- [ ] License extraction implemented in Extractor node
- [ ] Unit tests written and passing (>80% coverage on nodes)
- [ ] Integration test with mocked GitHub API responses
- [ ] Golden fixture similarity test for brief summaries

### Tools
- [ ] `tools/run_scout_workflow.py` created and executable
- [ ] Tool includes `--help` with usage examples
- [ ] Tool documented in tools README

### Documentation
- [ ] Update wiki with Scout workflow documentation
- [ ] Update README.md with Scout feature description
- [ ] Create ADR for external research workflow design decisions
- [ ] **Document data privacy implications of `--internal` flag**
- [ ] Add new files to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/scout-workflow/implementation-report.md` created
- [ ] `docs/reports/scout-workflow/test-report.md` created

### Verification
- [ ] Run 0809 Security Audit - PASS (API key handling)
- [ ] Run 0810 Privacy Audit - PASS (no PII in briefs, data transmission documented)
- [ ] Run 0817 Wiki Alignment Audit - PASS

## Testing Notes

**To test happy path:**
```bash
export GITHUB_TOKEN="your_token_here"
python tools/run_scout_workflow.py --topic "python async task queue" --internal agentos/core/scheduler.py --yes
cat ideas/active/innovation-python-async-task-queue.md
```

**To test data transmission warning:**
```bash
python tools/run_scout_workflow.py --topic "patterns" --internal agentos/core/state.py
# Should see: "Warning: Target file 'agentos/core/state.py' will be sent to external LLM provider (Gemini) for analysis. Continue? [y/N]"
# Enter 'n' to abort, 'y' to continue
```

**To test token budget enforcement:**
```bash
python tools/run_scout_workflow.py --topic "large topic" --internal large_file.py --max-tokens 1000 --yes
# Should see: "Error: Estimated token count (X) exceeds limit (1000)..."
```

**To test JSON output format:**
```bash
python tools/run_scout_workflow.py --topic "fastapi patterns" --format json --yes
# Should output valid JSON to stdout or file
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

**To verify brief accuracy (automated):**
```bash
pytest tests/workflows/scout/test_brief_similarity.py -v
# Runs cosine similarity check against golden fixture
```

**To verify brief accuracy (manual spot-check):**
1. Run scout on known topic (e.g., "FastAPI dependency injection")
2. Manually visit top repository in brief
3. Confirm README summary matches actual README content
4. Confirm identified patterns exist in external codebase
5. Confirm license type is correctly reported

## Labels
`feature`, `agent`, `langgraph`, `research`

## Effort Estimate
**Large (L)** — 4 distinct graph nodes + CLI wrapper + token estimation + confirmation flow

## Original Brief
# Innovation Workflow: The Scout (External Intelligence)

**Context:** We have successfully implemented internal governance (Issue/LLD/Implementation workflows). However, our current "Audit" system (`08xx`) is purely reactive and insular—it only checks what we have *already written*. It fails to bring in new knowledge from the outside world.

## Problem

**The "Not Invented Here" Failure Mode:**
We often solve complex problems (e.g., "How to persist agent state") from first principles, unaware that a highly-starred GitHub repository solved it better six months ago.

* *Result:* We maintain inferior, custom implementations of solved problems.
* *Missing Capability:* We have no automated way to say, "Look at the world, find the best pattern for X, and tell me how we fall short."

## Goal

Create `tools/run_scout_workflow.py`, a proactive research agent that acts as an **External Intelligence Gatherer**.

**Core Function:**

1. **Hunt:** Search GitHub/Web for solutions to a specific problem.
2. **Analyze:** Download and read the architecture of top solutions.
3. **Compare:** Diff the external best practice against our internal implementation.
4. **Report:** File an "Innovation Brief" detailing the gap.

## Proposed Architecture

### 1. The State Graph (`agentos/workflows/scout/graph.py`)

* **Input:** `research_topic` (e.g., "LangGraph persistence patterns"), `internal_target` (optional file path, e.g., `agentos/core/state.py`).
* **Nodes:**
    * **N0_Explorer:**
        * Tools: `Google Search`, `github_search` (Search for "python langgraph persistence stars:>500").
        * Action: Identifies Top-3 relevant repositories/articles.

    * **N1_Extractor:**
        * Action: Scrapes `README.md`, `architecture.md`, or key code files from the target URLs.
        * Context: Summarizes the "External Standard" (how the world does it).

    * **N2_Gap_Analyst:**
        * Input: "External Standard" + `internal_target` (our code).
        * Prompt: "Compare the External Standard to our `agentos/core/state.py`. Identify 3 specific ways we are deficient (Complexity, Performance, Reliability)."

    * **N3_Innovation_Scribe:**
        * Action: Formats the findings into a standard **Brief Template**.
        * Output: Creates `ideas/active/innovation-{topic}.md`.

### 2. The Innovation Brief Template

The workflow does *not* change code. It produces a decision artifact:

```markdown
# Innovation Opportunity: {Topic}

## External Standard
Top Solution: {Repo Name} ({Stars} stars)
License: {License Type}
Key Pattern: Uses `sqlite-vss` for vector check-pointing.

## Internal Gap
Our Approach: JSON dumps to disk.
Deficiency:
1. No semantic search capability.
2. Race conditions on file write (Solved by SQLite WAL in external pattern).

## Recommendation
[ ] Adopt `sqlite-vss` pattern (Est: 4 hours)
[ ] Ignore (Complexity cost too high)
```

### 3. The CLI Runner (`tools/run_scout_workflow.py`)

* **Usage:**
```bash
python tools/run_scout_workflow.py \
  --topic "secure api key rotation python" \
  --internal agentos/core/gemini_client.py \
  --max-tokens 30000 \
  --yes
```

## Success Criteria

* [ ] The workflow can find a relevant GitHub repo given a topic.
* [ ] It successfully reads the external code/docs without hallucinating features.
* [ ] It produces a Markdown brief that accurately identifies a deficiency in our current code.
* [ ] **Metric:** The user learns something new about their own stack from the report.