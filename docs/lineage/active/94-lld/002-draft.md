# 194 - Feature: Lu-Tze: The Janitor - Automated Repository Hygiene Workflow

<!-- Template Metadata
Last Updated: 2025-01-XX
Updated By: Initial LLD creation
Update Reason: New feature design for automated repository maintenance
-->

## 1. Context & Goal
* **Issue:** #94
* **Objective:** Create an automated LangGraph-based maintenance workflow that monitors and fixes repository hygiene issues (broken links, stale worktrees, cross-project drift, stale TODOs), replacing manual audit checklists with automated enforcement.
* **Status:** Draft
* **Related Issues:** N/A

### Open Questions

- [ ] Should worktree staleness threshold (14 days) be configurable via CLI or config file?
- [ ] For the harvest probe, should we create a new issue or integrate with existing AgentOS issue tracking?
- [ ] What is the exact format expected from `agentos-harvest.py` for the harvest probe integration?
- [ ] Should `--create-pr` require a specific branch naming convention?

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `tools/run_janitor_workflow.py` | Add | CLI entry point with argparse interface |
| `agentos/workflows/janitor/__init__.py` | Add | Package initialization, exports graph and state |
| `agentos/workflows/janitor/graph.py` | Add | LangGraph state graph with Sweeper → Fixer → Reporter nodes |
| `agentos/workflows/janitor/state.py` | Add | JanitorState TypedDict and ProbeResult dataclass |
| `agentos/workflows/janitor/probes/__init__.py` | Add | Probe registry and base interface |
| `agentos/workflows/janitor/probes/base.py` | Add | BaseProbe abstract class definition |
| `agentos/workflows/janitor/probes/links.py` | Add | Broken markdown link detection probe |
| `agentos/workflows/janitor/probes/worktrees.py` | Add | Stale git worktree detection probe |
| `agentos/workflows/janitor/probes/harvest.py` | Add | Cross-project drift detection via agentos-harvest.py |
| `agentos/workflows/janitor/probes/todo.py` | Add | Stale TODO comment scanner (30+ days) |
| `agentos/workflows/janitor/fixers.py` | Add | Auto-fix implementations for links and worktrees |
| `agentos/workflows/janitor/reporter.py` | Add | ReporterInterface, GitHubReporter, LocalFileReporter |
| `docs/audits/083x/0834-*.md` | Modify | Archive with pointer to Janitor workflow |
| `docs/audits/083x/0838-*.md` | Modify | Archive with pointer to Janitor workflow |
| `docs/audits/083x/0840-*.md` | Modify | Archive with pointer to Janitor workflow |
| `docs/0003-file-inventory.md` | Modify | Add new Janitor workflow files |
| `tests/unit/test_janitor_probes.py` | Add | Unit tests for all probe implementations |
| `tests/unit/test_janitor_fixers.py` | Add | Unit tests for fixer implementations |
| `tests/unit/test_janitor_reporter.py` | Add | Unit tests for reporter implementations |
| `tests/integration/test_janitor_workflow.py` | Add | Integration tests for full workflow |

### 2.2 Dependencies

```toml
# pyproject.toml additions
langgraph = "^0.2.0"  # State graph orchestration
```

*Note: `gh` CLI is a runtime dependency (not Python package) - must be installed and authenticated.*

### 2.3 Data Structures

```python
# Pseudocode - NOT implementation

from typing import TypedDict, Literal
from dataclasses import dataclass
from enum import Enum

class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class Finding:
    probe_name: str           # Which probe found this
    file_path: str            # Affected file
    line_number: int | None   # Line if applicable
    description: str          # Human-readable description
    fixable: bool             # Can be auto-fixed
    severity: Severity        # info/warning/critical
    fix_data: dict | None     # Data needed for auto-fix (e.g., old_link, new_link)

@dataclass
class ProbeResult:
    probe_name: str
    status: Literal["success", "error"]
    findings: list[Finding]
    error_message: str | None  # If status == "error"
    duration_ms: int

@dataclass
class FixResult:
    finding: Finding
    success: bool
    commit_sha: str | None
    error_message: str | None

class JanitorState(TypedDict):
    # Input configuration
    scope: list[str]           # Probes to run: ["links", "worktrees", "harvest", "todo"]
    auto_fix: bool             # Enable automatic fixing
    dry_run: bool              # Preview mode, no changes
    silent: bool               # Suppress output
    create_pr: bool            # Create PR instead of direct commit
    reporter_type: str         # "github" or "local"
    
    # Sweeper output
    probe_results: list[ProbeResult]
    all_findings: list[Finding]
    
    # Fixer output
    fix_results: list[FixResult]
    fixable_findings: list[Finding]
    unfixable_findings: list[Finding]
    
    # Reporter output
    issue_url: str | None      # GitHub issue URL if created/updated
    report_path: str | None    # Local report path if using LocalFileReporter
    
    # Workflow metadata
    start_time: str
    end_time: str | None
    exit_code: int             # 0 = clean, 1 = unfixable issues remain
```

### 2.4 Function Signatures

```python
# === Entry Point ===
# tools/run_janitor_workflow.py

def main() -> int:
    """CLI entry point. Returns exit code (0=clean, 1=issues remain)."""
    ...

def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    ...

# === Graph Definition ===
# agentos/workflows/janitor/graph.py

def create_janitor_graph() -> StateGraph:
    """Create and return the LangGraph state graph."""
    ...

def sweeper_node(state: JanitorState) -> JanitorState:
    """N0: Run all probes in parallel, collect findings."""
    ...

def fixer_node(state: JanitorState) -> JanitorState:
    """N1: Apply auto-fixes to fixable findings."""
    ...

def reporter_node(state: JanitorState) -> JanitorState:
    """N2: Report unfixable findings to GitHub or local file."""
    ...

def should_fix(state: JanitorState) -> Literal["fix", "report"]:
    """Conditional edge: skip fixer if no fixable findings or dry_run."""
    ...

def should_report(state: JanitorState) -> Literal["report", "end"]:
    """Conditional edge: skip reporter if no unfixable findings."""
    ...

# === Probe Base & Registry ===
# agentos/workflows/janitor/probes/base.py

class BaseProbe(ABC):
    """Abstract base class for all probes."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique probe identifier."""
        ...
    
    @abstractmethod
    def run(self, repo_root: Path) -> ProbeResult:
        """Execute probe and return results."""
        ...

# agentos/workflows/janitor/probes/__init__.py

def get_probe_registry() -> dict[str, type[BaseProbe]]:
    """Return mapping of probe names to probe classes."""
    ...

def run_probes_parallel(
    probe_names: list[str], 
    repo_root: Path
) -> list[ProbeResult]:
    """Run specified probes in parallel, isolating failures."""
    ...

# === Individual Probes ===
# agentos/workflows/janitor/probes/links.py

class LinksProbe(BaseProbe):
    """Detect broken internal markdown links."""
    
    def run(self, repo_root: Path) -> ProbeResult:
        ...
    
    def _scan_markdown_files(self, repo_root: Path) -> list[Path]:
        ...
    
    def _extract_links(self, file_path: Path) -> list[tuple[str, int]]:
        """Extract (link_target, line_number) tuples."""
        ...
    
    def _check_link(self, source: Path, target: str, repo_root: Path) -> bool:
        """Return True if link resolves correctly."""
        ...

# agentos/workflows/janitor/probes/worktrees.py

class WorktreesProbe(BaseProbe):
    """Detect stale/detached git worktrees."""
    
    STALE_DAYS_THRESHOLD: int = 14
    
    def run(self, repo_root: Path) -> ProbeResult:
        ...
    
    def _list_worktrees(self) -> list[dict]:
        """Parse `git worktree list --porcelain` output."""
        ...
    
    def _is_stale(self, worktree: dict) -> bool:
        """Check if worktree is stale (no commits in 14+ days, branch merged/deleted)."""
        ...

# agentos/workflows/janitor/probes/harvest.py

class HarvestProbe(BaseProbe):
    """Detect cross-project drift via agentos-harvest.py."""
    
    def run(self, repo_root: Path) -> ProbeResult:
        ...
    
    def _run_harvest_script(self, repo_root: Path) -> dict:
        """Execute agentos-harvest.py and parse JSON output."""
        ...

# agentos/workflows/janitor/probes/todo.py

class TodoProbe(BaseProbe):
    """Scan for TODO comments older than 30 days."""
    
    STALE_DAYS_THRESHOLD: int = 30
    
    def run(self, repo_root: Path) -> ProbeResult:
        ...
    
    def _find_todos(self, repo_root: Path) -> list[dict]:
        """Find all TODO/FIXME/HACK comments with git blame dates."""
        ...
    
    def _get_blame_date(self, file_path: Path, line_number: int) -> datetime:
        """Get the last modification date for a specific line."""
        ...

# === Fixers ===
# agentos/workflows/janitor/fixers.py

class Fixer:
    """Applies fixes to findings."""
    
    def __init__(self, repo_root: Path, dry_run: bool, create_pr: bool):
        ...
    
    def fix_all(self, findings: list[Finding]) -> list[FixResult]:
        """Apply fixes to all fixable findings, grouped by type."""
        ...
    
    def fix_broken_link(self, finding: Finding) -> FixResult:
        """Fix a single broken link."""
        ...
    
    def fix_stale_worktree(self, finding: Finding) -> FixResult:
        """Prune a stale worktree."""
        ...
    
    def _create_commit(self, message: str, files: list[Path]) -> str:
        """Create atomic commit, return SHA."""
        ...
    
    def _generate_commit_message(self, fix_type: str, count: int) -> str:
        """Generate deterministic commit message from template."""
        ...

COMMIT_TEMPLATES: dict[str, str] = {
    "links": "fix(docs): update {count} broken markdown link(s)\n\nAuto-fixed by Janitor workflow",
    "worktrees": "chore: prune {count} stale worktree(s)\n\nAuto-fixed by Janitor workflow",
}

# === Reporters ===
# agentos/workflows/janitor/reporter.py

class ReporterInterface(ABC):
    """Abstract base for issue reporting."""
    
    @abstractmethod
    def report(self, findings: list[Finding]) -> str | None:
        """Report findings. Returns issue URL or file path."""
        ...
    
    @abstractmethod
    def find_existing_report(self) -> str | None:
        """Find existing Janitor Report. Returns issue number or file path."""
        ...

class GitHubReporter(ReporterInterface):
    """Reports findings as GitHub issues using `gh` CLI."""
    
    ISSUE_TITLE: str = "🧹 Janitor Report: Repository Hygiene Findings"
    
    def report(self, findings: list[Finding]) -> str | None:
        ...
    
    def find_existing_report(self) -> str | None:
        """Search for existing open issue with Janitor Report title."""
        ...
    
    def _create_issue(self, body: str) -> str:
        """Create new GitHub issue, return URL."""
        ...
    
    def _update_issue(self, issue_number: str, body: str) -> str:
        """Update existing issue, return URL."""
        ...
    
    def _format_issue_body(self, findings: list[Finding]) -> str:
        """Format findings into categorized markdown."""
        ...
    
    def _check_gh_auth(self) -> bool:
        """Verify gh CLI is authenticated (interactive or GITHUB_TOKEN)."""
        ...

class LocalFileReporter(ReporterInterface):
    """Reports findings to local files (for testing)."""
    
    OUTPUT_DIR: str = "./janitor-reports"
    
    def report(self, findings: list[Finding]) -> str | None:
        ...
    
    def find_existing_report(self) -> str | None:
        ...
```

### 2.5 Logic Flow (Pseudocode)

```
MAIN WORKFLOW:
1. Parse CLI arguments
2. Initialize JanitorState with config
3. Build LangGraph: Sweeper → Fixer → Reporter
4. Execute graph
5. Return exit_code from final state

SWEEPER NODE (N0):
1. Get probe registry
2. Filter probes by scope argument
3. FOR EACH probe IN parallel:
   TRY:
     - result = probe.run(repo_root)
     - Append result to probe_results
   EXCEPT Exception as e:
     - Log error, append error ProbeResult
     - Continue (isolated failure)
4. Flatten all findings from probe_results
5. Return updated state

FIXER NODE (N1):
1. IF dry_run THEN
   - Log what would be fixed
   - Skip actual fixes
   - Return state unchanged
2. Separate findings into fixable/unfixable
3. Group fixable findings by type (links, worktrees)
4. FOR EACH group:
   - Apply fixes
   - Create atomic commit with template message
   - IF create_pr THEN create PR instead
5. Return state with fix_results

REPORTER NODE (N2):
1. IF no unfixable_findings THEN return (nothing to report)
2. Get reporter based on reporter_type
3. Search for existing Janitor Report
4. IF existing report found:
   - Update existing issue/file
5. ELSE:
   - Create new issue/file
6. Set exit_code = 1 (unfixable issues remain)
7. Return state with issue_url or report_path

CONDITIONAL ROUTING:
- should_fix: IF auto_fix AND fixable_findings exist AND NOT dry_run → "fix" ELSE → "report"
- should_report: IF unfixable_findings exist → "report" ELSE → "end"
```

### 2.6 Technical Approach

* **Module:** `agentos/workflows/janitor/`
* **Pattern:** State Machine (LangGraph), Strategy Pattern (Reporters), Template Method (Probes)
* **Key Decisions:**
  - LangGraph for state management and conditional routing (not LLM orchestration)
  - Parallel probe execution with isolated failure handling
  - Deterministic commit messages via templates (no LLM)
  - Reporter abstraction enables testing without GitHub API calls

### 2.7 Architecture Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Workflow orchestration | Plain Python, Prefect, LangGraph | LangGraph | Native state management, conditional routing, matches existing patterns |
| Probe execution | Sequential, Parallel | Parallel with isolation | Faster execution, probe crashes don't block others |
| Commit message generation | LLM-generated, Templates | Templates | Deterministic, no external API calls, faster |
| Issue reporting | Direct API, gh CLI | gh CLI | Leverages existing auth, simpler implementation |
| Testing strategy | Mock GitHub API, Local reporter | Local reporter abstraction | Clean separation, no API mocking complexity |

**Architectural Constraints:**
- Must not introduce LLM dependencies (purely deterministic workflow)
- Must work in headless CI environments with `GITHUB_TOKEN`
- Must be reversible (all changes via git commits)
- Must integrate with existing `agentos-harvest.py` script

## 3. Requirements

*What must be true when this is done. These become acceptance criteria.*

1. Running `python tools/run_janitor_workflow.py` executes all probes and reports findings
2. `--dry-run` flag shows pending fixes without modifying any files
3. Broken markdown links are automatically fixed when `--auto-fix true`
4. Stale worktrees (14+ days inactive, branch merged/deleted) are automatically pruned
5. Unfixable issues create or update a single "Janitor Report" GitHub issue
6. Existing Janitor Report issue is updated (not duplicated) on subsequent runs
7. `--silent` mode produces no stdout on success, exits cleanly
8. Exit code 0 when all issues fixed, exit code 1 when unfixable issues remain
9. `--reporter local` writes reports to local files without GitHub API calls
10. CI execution with `GITHUB_TOKEN` environment variable authenticates successfully
11. Probe crashes are isolated and do not block other probes from running

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| LangGraph workflow | State management, conditional routing, parallel execution | Learning curve, dependency | **Selected** |
| Plain Python script | Simple, no dependencies | Manual state management, no parallelism | Rejected |
| Prefect/Airflow | Mature, scheduling built-in | Heavy dependency, overkill for scope | Rejected |
| GitHub Actions only | Native CI integration | Limited local execution, no interactive mode | Rejected |

**Rationale:** LangGraph provides the right balance of state management capabilities without requiring external services. It matches existing patterns in the codebase and supports the parallel execution model needed for probes.

## 5. Data & Fixtures

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | Local repository files, git history |
| Format | Markdown files, git porcelain output, JSON (harvest) |
| Size | Variable (depends on repo size) |
| Refresh | On-demand per workflow run |
| Copyright/License | N/A - operates on user's own repository |

### 5.2 Data Pipeline

```
Repository Files ──scan──► Probes ──findings──► Fixer ──commits──► Git
                                      │
                                      └──unfixable──► Reporter ──issue──► GitHub/Local
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| Test markdown with broken links | Generated | Created in test setup |
| Test git worktree (stale) | Generated | Created in test setup, cleaned in teardown |
| Mock harvest output | Hardcoded | JSON fixture matching expected format |
| Source files with old TODOs | Generated | Files with blamed TODO comments |

### 5.4 Deployment Pipeline

- **Development:** Run locally with `--reporter local`
- **Testing:** Automated tests use `LocalFileReporter`, no external calls
- **CI:** GitHub Actions with `GITHUB_TOKEN`, `--silent` mode
- **Production:** Cron job or Task Scheduler, full `gh` CLI auth

**External utilities:** Depends on existing `agentos-harvest.py` for harvest probe. No new utility needed.

## 6. Diagram

### 6.1 Mermaid Quality Gate

Before finalizing any diagram, verify in [Mermaid Live Editor](https://mermaid.live) or GitHub preview:

- [x] **Simplicity:** Similar components collapsed (per 0006 §8.1)
- [x] **No touching:** All elements have visual separation (per 0006 §8.2)
- [x] **No hidden lines:** All arrows fully visible (per 0006 §8.3)
- [x] **Readable:** Labels not truncated, flow direction clear
- [ ] **Auto-inspected:** Agent rendered via mermaid.ink and viewed (per 0006 §8.5)

**Auto-Inspection Results:**
```
- Touching elements: [ ] None / [ ] Found: ___
- Hidden lines: [ ] None / [ ] Found: ___
- Label readability: [ ] Pass / [ ] Issue: ___
- Flow clarity: [ ] Clear / [ ] Issue: ___
```

*Note: Auto-inspection to be completed during implementation phase.*

### 6.2 Diagram

```mermaid
flowchart TB
    subgraph CLI["CLI Entry Point"]
        A[tools/run_janitor_workflow.py]
    end

    subgraph Graph["LangGraph Workflow"]
        direction TB
        N0[N0: Sweeper]
        N1[N1: Fixer]
        N2[N2: Reporter]
        
        N0 -->|fixable findings| N1
        N0 -->|no fixable| N2
        N1 --> N2
        N2 --> END[End]
    end

    subgraph Probes["Probe System"]
        P1[LinksProbe]
        P2[WorktreesProbe]
        P3[HarvestProbe]
        P4[TodoProbe]
    end

    subgraph Reporters["Reporter System"]
        R1[GitHubReporter]
        R2[LocalFileReporter]
    end

    A --> N0
    N0 --> P1
    N0 --> P2
    N0 --> P3
    N0 --> P4
    
    N2 --> R1
    N2 --> R2
```

```mermaid
sequenceDiagram
    participant CLI as CLI
    participant Graph as LangGraph
    participant Sweeper as N0_Sweeper
    participant Probes as Probes
    participant Fixer as N1_Fixer
    participant Git as Git
    participant Reporter as N2_Reporter
    participant GitHub as GitHub/Local

    CLI->>Graph: Initialize state
    Graph->>Sweeper: Execute
    
    par Parallel Probe Execution
        Sweeper->>Probes: LinksProbe.run()
        Probes-->>Sweeper: ProbeResult
    and
        Sweeper->>Probes: WorktreesProbe.run()
        Probes-->>Sweeper: ProbeResult
    and
        Sweeper->>Probes: HarvestProbe.run()
        Probes-->>Sweeper: ProbeResult
    and
        Sweeper->>Probes: TodoProbe.run()
        Probes-->>Sweeper: ProbeResult
    end
    
    Sweeper-->>Graph: Updated state with findings
    
    alt Has fixable findings AND auto_fix=true
        Graph->>Fixer: Execute
        Fixer->>Git: Apply fixes
        Git-->>Fixer: Commit SHA
        Fixer-->>Graph: Updated state with fix_results
    end
    
    alt Has unfixable findings
        Graph->>Reporter: Execute
        Reporter->>GitHub: Create/Update issue
        GitHub-->>Reporter: Issue URL
        Reporter-->>Graph: Updated state
    end
    
    Graph-->>CLI: Final state (exit_code)
```

## 7. Security & Safety Considerations

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| Arbitrary file modification | Only modifies files within repo root, validates paths | Addressed |
| GitHub token exposure | Uses `gh` CLI auth or `GITHUB_TOKEN` env var, no token in logs | Addressed |
| Code injection via findings | All commit messages use templates, no user input interpolation | Addressed |
| External data transmission | No code/content sent externally, all processing local | Addressed |
| Unauthorized commits | Commits use existing git identity, respects branch protections | Addressed |

### 7.2 Safety

| Concern | Mitigation | Status |
|---------|------------|--------|
| Accidental data loss | All changes via git commits (fully reversible) | Addressed |
| Active worktree deletion | Only prunes detached/stale trees, never active work | Addressed |
| Runaway fixing | Atomic commits per category, can revert individually | Addressed |
| Probe crash cascade | Isolated probe execution, failures don't stop workflow | Addressed |
| Incorrect link fixes | Dry-run mode for preview, conservative matching | Addressed |

**Fail Mode:** Fail Closed - If authentication fails or critical error occurs, workflow exits with error code without making changes.

**Recovery Strategy:** 
- All fixes are git commits: `git revert <sha>` to undo
- Worktree prune is non-destructive (worktree data preserved if branch exists)
- GitHub issues can be manually closed/edited

## 8. Performance & Cost Considerations

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| Total runtime | < 60s for typical repo | Parallel probe execution |
| Memory | < 256MB | Stream large files, don't load all into memory |
| Git operations | Minimize by batching | Single commit per fix category |

**Bottlenecks:**
- `git blame` for TODO dating can be slow on large files
- Link checking scales with number of markdown files
- Harvest probe depends on external script performance

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| GitHub API (via gh) | Free (rate limited) | ~10 calls/run | $0 |
| Compute (local) | N/A | Developer machine | $0 |
| CI minutes | Varies by plan | ~1 min/run | Minimal |

**Cost Controls:**
- [x] No paid API dependencies
- [x] Local execution is free
- [x] CI runs are brief (~1 minute)

**Worst-Case Scenario:** Large repos may take several minutes for full scan. Solution: `--scope` flag to run specific probes only.

## 9. Legal & Compliance

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | No | Only processes code/docs, no personal data |
| Third-Party Licenses | No | No third-party content processed |
| Terms of Service | N/A | Uses official gh CLI per GitHub ToS |
| Data Retention | No | No data stored externally |
| Export Controls | No | No restricted algorithms |

**Data Classification:** Internal (operates on developer's own repository)

**Compliance Checklist:**
- [x] No PII stored without consent - N/A
- [x] All third-party licenses compatible with project license
- [x] External API usage compliant with provider ToS
- [x] Data retention policy documented - N/A (no external storage)

## 10. Verification & Testing

*Ref: [0005-testing-strategy-and-protocols.md](0005-testing-strategy-and-protocols.md)*

**Testing Philosophy:** Strive for 100% automated test coverage. Manual tests are a last resort for scenarios that genuinely cannot be automated.

### 10.0 Test Plan (TDD - Complete Before Implementation)

**TDD Requirement:** Tests MUST be written and failing BEFORE implementation begins.

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | LinksProbe detects broken links | Returns findings for invalid link targets | RED |
| T020 | LinksProbe ignores valid links | No findings for working links | RED |
| T030 | WorktreesProbe detects stale worktrees | Returns findings for 14+ day inactive trees | RED |
| T040 | WorktreesProbe ignores active worktrees | No findings for recent activity | RED |
| T050 | TodoProbe finds old TODOs | Returns findings for 30+ day TODOs | RED |
| T060 | TodoProbe ignores recent TODOs | No findings for recent TODOs | RED |
| T070 | Fixer repairs broken links | File updated with correct link | RED |
| T080 | Fixer prunes stale worktrees | Worktree removed from list | RED |
| T090 | Fixer respects dry_run | No changes made when dry_run=True | RED |
| T100 | GitHubReporter creates issue | Issue created with findings | RED |
| T110 | GitHubReporter updates existing | Existing issue updated, not duplicated | RED |
| T120 | LocalFileReporter writes file | Report written to local directory | RED |
| T130 | Graph routes correctly | Conditional edges fire appropriately | RED |
| T140 | Probe crash isolation | Other probes continue after one fails | RED |
| T150 | CLI argument parsing | All flags parsed correctly | RED |
| T160 | Exit code 0 on clean | Returns 0 when no unfixable issues | RED |
| T170 | Exit code 1 on issues | Returns 1 when unfixable issues remain | RED |

**Coverage Target:** ≥95% for all new code

**TDD Checklist:**
- [ ] All tests written before implementation
- [ ] Tests currently RED (failing)
- [ ] Test IDs match scenario IDs in 10.1
- [ ] Test file created at: `tests/unit/test_janitor_*.py`

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | LinksProbe detects broken links | Auto | Markdown with invalid link | Finding with file/line | finding.fixable == True |
| 020 | LinksProbe ignores valid links | Auto | Markdown with valid links | Empty findings | len(findings) == 0 |
| 030 | WorktreesProbe detects stale | Auto | Worktree with no recent commits | Finding for worktree | finding.description contains path |
| 040 | WorktreesProbe ignores active | Auto | Worktree with recent activity | Empty findings | len(findings) == 0 |
| 050 | TodoProbe finds old TODOs | Auto | File with 30+ day TODO | Finding with line number | finding.severity == WARNING |
| 060 | TodoProbe ignores recent | Auto | File with fresh TODO | Empty findings | len(findings) == 0 |
| 070 | Fixer repairs broken links | Auto | Finding with fix_data | Updated file content | new link in file |
| 080 | Fixer prunes stale worktrees | Auto | Stale worktree finding | Worktree removed | git worktree list shorter |
| 090 | Fixer dry_run mode | Auto | findings, dry_run=True | No file changes | git status clean |
| 100 | GitHubReporter creates issue | Auto-Live | Unfixable findings | Issue URL returned | URL matches pattern |
| 110 | GitHubReporter updates existing | Auto-Live | Existing issue, new findings | Same issue number | issue_number unchanged |
| 120 | LocalFileReporter writes file | Auto | Findings | File in ./janitor-reports/ | file exists |
| 130 | Graph conditional routing | Auto | State with fixable findings | Fixer node executed | fix_results populated |
| 140 | Probe crash isolation | Auto | One probe raises exception | Other results present | len(probe_results) == expected |
| 150 | CLI --scope links | Auto | --scope links | Only links probe runs | len(probe_results) == 1 |
| 160 | CLI --silent no output | Auto | --silent flag | Empty stdout | stdout == "" |
| 170 | Exit code 1 unfixable | Auto | Unfixable findings | exit_code == 1 | return value is 1 |
| 180 | Exit code 0 clean | Auto | All issues fixed | exit_code == 0 | return value is 0 |

### 10.2 Test Commands

```bash
# Run all automated tests
poetry run pytest tests/unit/test_janitor*.py tests/integration/test_janitor*.py -v

# Run only fast/mocked tests (exclude live)
poetry run pytest tests/unit/test_janitor*.py -v -m "not live"

# Run live integration tests (requires gh auth)
poetry run pytest tests/integration/test_janitor*.py -v -m live

# Run with coverage
poetry run pytest tests/unit/test_janitor*.py --cov=agentos/workflows/janitor --cov-report=term-missing
```

### 10.3 Manual Tests (Only If Unavoidable)

**If no manual tests required:** N/A - All scenarios automated.

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `agentos-harvest.py` format changes | Med | Low | Version check, graceful degradation |
| gh CLI not installed | Med | Low | Clear error message with install instructions |
| Large repo performance | Low | Med | `--scope` flag for targeted runs |
| False positive link detection | Med | Med | Conservative matching, dry-run preview |
| GitHub API rate limiting | Low | Low | Batch operations, respect limits |
| Branch protection blocks commits | Med | Low | `--create-pr` option for protected branches |

## 12. Definition of Done

### Code
- [ ] Implementation complete and linted
- [ ] Code comments reference this LLD (Issue #94)
- [ ] All probe implementations complete
- [ ] Fixer implementations for links and worktrees
- [ ] Both reporter implementations complete

### Tests
- [ ] All test scenarios pass (≥95% coverage)
- [ ] Unit tests use LocalFileReporter (no live API calls)
- [ ] Integration tests validate full workflow

### Documentation
- [ ] LLD updated with any deviations
- [ ] Implementation Report (0103) completed
- [ ] Test Report (0113) completed
- [ ] Wiki updated with Janitor workflow documentation
- [ ] Superseded audit docs archived (0834, 0838, 0840)
- [ ] Files added to `docs/0003-file-inventory.md`
- [ ] Example cron configuration provided
- [ ] CI example with `GITHUB_TOKEN` documented

### Review
- [ ] Code review completed
- [ ] User approval before closing issue

---

## Appendix: Review Log

*Track all review feedback with timestamps and implementation status.*

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| - | - | - | Pending initial review |

**Final Status:** PENDING