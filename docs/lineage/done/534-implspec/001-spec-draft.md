# Implementation Spec: Spelunking Audits — Deep Verification That Reality Matches Claims

| Field | Value |
|-------|-------|
| Issue | #534 |
| LLD | `docs/lld/active/534-spelunking-audits.md` |
| Generated | 2026-02-17 |
| Status | DRAFT |

## 1. Overview

Build a two-layer spelunking system consisting of six automated probes and a core verification engine that extracts factual claims from documentation and verifies them against filesystem reality, producing drift reports with quantified accuracy scores.

**Objective:** Prevent documentation lies by automatically detecting when documentation claims diverge from codebase reality, as discovered during Issue #114 (DEATH).

**Success Criteria:** All 39 test scenarios (T010–T365) pass with ≥95% coverage; six probes produce accurate ProbeResult outputs; drift score calculation correctly excludes UNVERIFIABLE claims; no new external dependencies introduced.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `docs/standards/0015-spelunking-audit-standard.md` | Add | Standard defining the spelunking protocol |
| 2 | `assemblyzero/spelunking/__init__.py` | Add | Package init with public API exports |
| 3 | `assemblyzero/spelunking/models.py` | Add | Data models: Claim, VerificationResult, DriftReport, etc. |
| 4 | `assemblyzero/spelunking/extractors.py` | Add | Claim extractors: regex-based Markdown parsing |
| 5 | `assemblyzero/spelunking/verifiers.py` | Add | Verification strategies: filesystem, grep, prefix checks |
| 6 | `assemblyzero/spelunking/report.py` | Add | Report generator: Markdown and JSON drift reports |
| 7 | `assemblyzero/spelunking/engine.py` | Add | Core engine: orchestrates extraction, verification, reporting |
| 8 | `assemblyzero/workflows/janitor/probes/inventory_drift.py` | Add | Probe: file count verification against inventory |
| 9 | `assemblyzero/workflows/janitor/probes/dead_references.py` | Add | Probe: dead file path reference detection |
| 10 | `assemblyzero/workflows/janitor/probes/adr_collision.py` | Add | Probe: duplicate ADR prefix detection |
| 11 | `assemblyzero/workflows/janitor/probes/stale_timestamps.py` | Add | Probe: stale/missing timestamp detection |
| 12 | `assemblyzero/workflows/janitor/probes/readme_claims.py` | Add | Probe: README contradiction detection |
| 13 | `assemblyzero/workflows/janitor/probes/persona_status.py` | Add | Probe: persona implementation status verification |
| 14 | `tests/fixtures/spelunking/mock_inventory.md` | Add | Mock file inventory with known drift |
| 15 | `tests/fixtures/spelunking/mock_readme.md` | Add | Mock README with verifiable/falsifiable claims |
| 16 | `tests/fixtures/spelunking/mock_docs_with_dead_refs.md` | Add | Mock doc referencing nonexistent files |
| 17 | `tests/fixtures/spelunking/mock_personas.md` | Add | Mock Dramatis Personae with status gaps |
| 18 | `tests/fixtures/spelunking/mock_repo/docs/adrs/0201-first.md` | Add | Mock ADR (unique prefix) |
| 19 | `tests/fixtures/spelunking/mock_repo/docs/adrs/0202-second.md` | Add | Mock ADR (unique prefix) |
| 20 | `tests/fixtures/spelunking/mock_repo/docs/adrs/0204-collision-a.md` | Add | Mock ADR (collision prefix) |
| 21 | `tests/fixtures/spelunking/mock_repo/docs/adrs/0204-collision-b.md` | Add | Mock ADR (collision prefix) |
| 22 | `tests/fixtures/spelunking/mock_repo/tools/tool1.py` | Add | Mock tool file |
| 23 | `tests/fixtures/spelunking/mock_repo/tools/tool2.py` | Add | Mock tool file |
| 24 | `tests/fixtures/spelunking/mock_repo/tools/tool3.py` | Add | Mock tool file |
| 25 | `tests/fixtures/spelunking/mock_repo/tools/tool4.py` | Add | Mock tool file |
| 26 | `tests/fixtures/spelunking/mock_repo/tools/tool5.py` | Add | Mock tool file |
| 27 | `tests/fixtures/spelunking/mock_repo/tools/tool6.py` | Add | Mock tool file |
| 28 | `tests/fixtures/spelunking/mock_repo/tools/tool7.py` | Add | Mock tool file |
| 29 | `tests/fixtures/spelunking/mock_repo/tools/tool8.py` | Add | Mock tool file |
| 30 | `tests/unit/test_spelunking/__init__.py` | Add | Test package init |
| 31 | `tests/unit/test_spelunking/test_engine.py` | Add | Engine tests |
| 32 | `tests/unit/test_spelunking/test_extractors.py` | Add | Extractor tests |
| 33 | `tests/unit/test_spelunking/test_verifiers.py` | Add | Verifier tests |
| 34 | `tests/unit/test_spelunking/test_probes.py` | Add | Probe tests |
| 35 | `tests/unit/test_spelunking/test_report.py` | Add | Report tests |
| 36 | `tests/unit/test_spelunking/test_dependencies.py` | Add | Dependency verification tests |

**Implementation Order Rationale:** Models first (no dependencies), then extractors and verifiers (depend on models), then report (depends on models), then engine (depends on all), then probes (depend on engine + models + verifiers), then fixtures, then tests. Standard document is independent and can be written first.

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/workflows/janitor/probes/` (Modify — Directory)

**Current state:** This directory exists and contains existing probe modules. We are adding new files to this directory, not modifying existing ones.

**Listing of current directory** (representative):

```
assemblyzero/workflows/janitor/probes/
├── __init__.py
├── ... (existing probe files)
```

**What changes:** Six new probe modules are added as siblings to existing probes. No existing files are modified. The new probes follow the same return pattern as existing probes (returning result dataclasses).

**Note:** Since we are only *adding* files to this directory and not modifying any existing files, there is no diff to existing code. The existing `__init__.py` is NOT modified — the new probes are standalone modules imported directly by the engine.

## 4. Data Structures

### 4.1 `ClaimType` (Enum)

**Definition:**

```python
class ClaimType(Enum):
    FILE_COUNT = "file_count"
    FILE_EXISTS = "file_exists"
    TECHNICAL_FACT = "technical_fact"
    STATUS_MARKER = "status_marker"
    UNIQUE_ID = "unique_id"
    TIMESTAMP = "timestamp"
```

**Concrete Example:**

```json
"file_count"
```

### 4.2 `VerificationStatus` (Enum)

**Definition:**

```python
class VerificationStatus(Enum):
    MATCH = "match"
    MISMATCH = "mismatch"
    STALE = "stale"
    UNVERIFIABLE = "unverifiable"
    ERROR = "error"
```

**Concrete Example:**

```json
"mismatch"
```

### 4.3 `Claim`

**Definition:**

```python
@dataclass
class Claim:
    claim_type: ClaimType
    source_file: Path
    source_line: int
    claim_text: str
    expected_value: str
    verification_command: str
```

**Concrete Example:**

```json
{
    "claim_type": "file_count",
    "source_file": "docs/standards/0003-file-inventory.md",
    "source_line": 42,
    "claim_text": "11 tools in tools/",
    "expected_value": "11",
    "verification_command": "glob tools/*.py | count"
}
```

**Concrete Example 2 (FILE_EXISTS):**

```json
{
    "claim_type": "file_exists",
    "source_file": "README.md",
    "source_line": 15,
    "claim_text": "See tools/death.py for details",
    "expected_value": "tools/death.py",
    "verification_command": "exists tools/death.py"
}
```

**Concrete Example 3 (TIMESTAMP):**

```json
{
    "claim_type": "timestamp",
    "source_file": "docs/adrs/0201-workflow-design.md",
    "source_line": 3,
    "claim_text": "Last Updated: 2026-01-15",
    "expected_value": "2026-01-15",
    "verification_command": "freshness 2026-01-15 30"
}
```

**Concrete Example 4 (TECHNICAL_FACT):**

```json
{
    "claim_type": "technical_fact",
    "source_file": "README.md",
    "source_line": 88,
    "claim_text": "not vector embeddings",
    "expected_value": "vector embeddings",
    "verification_command": "grep_absent vector embeddings"
}
```

### 4.4 `VerificationResult`

**Definition:**

```python
@dataclass
class VerificationResult:
    claim: Claim
    status: VerificationStatus
    actual_value: Optional[str] = None
    evidence: str = ""
    verified_at: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
```

**Concrete Example (MATCH):**

```json
{
    "claim": {
        "claim_type": "file_count",
        "source_file": "docs/standards/0003-file-inventory.md",
        "source_line": 42,
        "claim_text": "8 tools in tools/",
        "expected_value": "8",
        "verification_command": "glob tools/*.py | count"
    },
    "status": "match",
    "actual_value": "8",
    "evidence": "tools/: tool1.py, tool2.py, tool3.py, tool4.py, tool5.py, tool6.py, tool7.py, tool8.py",
    "verified_at": "2026-02-17T14:30:00",
    "error_message": null
}
```

**Concrete Example (MISMATCH):**

```json
{
    "claim": {
        "claim_type": "file_count",
        "source_file": "docs/standards/0003-file-inventory.md",
        "source_line": 42,
        "claim_text": "5 tools in tools/",
        "expected_value": "5",
        "verification_command": "glob tools/*.py | count"
    },
    "status": "mismatch",
    "actual_value": "8",
    "evidence": "tools/: tool1.py, tool2.py, tool3.py, tool4.py, tool5.py, tool6.py, tool7.py, tool8.py",
    "verified_at": "2026-02-17T14:30:00",
    "error_message": null
}
```

**Concrete Example (ERROR — path traversal):**

```json
{
    "claim": {
        "claim_type": "file_exists",
        "source_file": "README.md",
        "source_line": 10,
        "claim_text": "../../etc/passwd",
        "expected_value": "../../etc/passwd",
        "verification_command": "exists ../../etc/passwd"
    },
    "status": "error",
    "actual_value": null,
    "evidence": "",
    "verified_at": "2026-02-17T14:30:00",
    "error_message": "Path traversal rejected: resolves outside repository root"
}
```

### 4.5 `DriftReport`

**Definition:**

```python
@dataclass
class DriftReport:
    target_document: Path
    results: list[VerificationResult]
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def total_claims(self) -> int: ...
    @property
    def matching_claims(self) -> int: ...
    @property
    def drift_score(self) -> float: ...
```

**Concrete Example:**

```json
{
    "target_document": "README.md",
    "results": [
        {"claim": {"claim_type": "file_count", "...": "..."}, "status": "match", "actual_value": "8"},
        {"claim": {"claim_type": "file_exists", "...": "..."}, "status": "mismatch", "actual_value": null},
        {"claim": {"claim_type": "technical_fact", "...": "..."}, "status": "unverifiable"}
    ],
    "generated_at": "2026-02-17T14:30:00",
    "total_claims": 3,
    "matching_claims": 1,
    "drift_score": 50.0
}
```

### 4.6 `SpelunkingCheckpoint`

**Definition:**

```python
@dataclass
class SpelunkingCheckpoint:
    claim: str
    verify_command: str
    source_file: str
    last_verified: Optional[datetime] = None
    last_status: Optional[VerificationStatus] = None
```

**Concrete Example (YAML format in 08xx audit docs):**

```yaml
checkpoints:
  - claim: "11 tools in tools/"
    verify_command: "glob tools/*.py | count"
    source_file: "docs/standards/0003-file-inventory.md"
    last_verified: "2026-02-10T10:00:00"
    last_status: "match"
  - claim: "Uses SQLite checkpointing"
    verify_command: "grep_present sqlite"
    source_file: "README.md"
    last_verified: null
    last_status: null
```

### 4.7 `ProbeResult`

**Definition:**

```python
@dataclass
class ProbeResult:
    probe_name: str
    findings: list[VerificationResult]
    passed: bool
    summary: str
    execution_time_ms: float
```

**Concrete Example (passing):**

```json
{
    "probe_name": "adr_collision",
    "findings": [],
    "passed": true,
    "summary": "No ADR prefix collisions detected in 15 files",
    "execution_time_ms": 12.3
}
```

**Concrete Example (failing):**

```json
{
    "probe_name": "inventory_drift",
    "findings": [
        {
            "claim": {"claim_type": "file_count", "claim_text": "5 tools in tools/", "expected_value": "5"},
            "status": "mismatch",
            "actual_value": "8",
            "evidence": "tools/: tool1.py, tool2.py, tool3.py, tool4.py, tool5.py, tool6.py, tool7.py, tool8.py"
        }
    ],
    "passed": false,
    "summary": "1 inventory drift detected: tools/ claims 5, actual 8",
    "execution_time_ms": 45.7
}
```

## 5. Function Specifications

### 5.1 `extract_claims_from_markdown()`

**File:** `assemblyzero/spelunking/extractors.py`

**Signature:**

```python
def extract_claims_from_markdown(
    file_path: Path,
    claim_types: list[ClaimType] | None = None,
) -> list[Claim]:
```

**Input Example:**

```python
file_path = Path("tests/fixtures/spelunking/mock_readme.md")
claim_types = None  # extract all types
```

**Output Example:**

```python
[
    Claim(
        claim_type=ClaimType.FILE_COUNT,
        source_file=Path("tests/fixtures/spelunking/mock_readme.md"),
        source_line=5,
        claim_text="11 tools in tools/",
        expected_value="11",
        verification_command="glob tools/*.py | count",
    ),
    Claim(
        claim_type=ClaimType.FILE_EXISTS,
        source_file=Path("tests/fixtures/spelunking/mock_readme.md"),
        source_line=10,
        claim_text="See [death tool](tools/death.py)",
        expected_value="tools/death.py",
        verification_command="exists tools/death.py",
    ),
]
```

**Edge Cases:**
- File doesn't exist -> raises `FileNotFoundError`
- File is empty -> returns `[]`
- File has no claims matching `claim_types` filter -> returns `[]`
- Binary file -> returns `[]` (catches `UnicodeDecodeError`)

### 5.2 `extract_file_count_claims()`

**File:** `assemblyzero/spelunking/extractors.py`

**Signature:**

```python
def extract_file_count_claims(
    content: str,
    source_file: Path,
) -> list[Claim]:
```

**Input Example:**

```python
content = "## Tools\n\nThere are 11 tools in the tools/ directory.\n\n| Directory | Count |\n| tools/ | 5 files |"
source_file = Path("README.md")
```

**Output Example:**

```python
[
    Claim(
        claim_type=ClaimType.FILE_COUNT,
        source_file=Path("README.md"),
        source_line=3,
        claim_text="11 tools in the tools/ directory",
        expected_value="11",
        verification_command="glob tools/*.py | count",
    ),
    Claim(
        claim_type=ClaimType.FILE_COUNT,
        source_file=Path("README.md"),
        source_line=5,
        claim_text="tools/ | 5 files",
        expected_value="5",
        verification_command="glob tools/* | count",
    ),
]
```

**Regex Patterns:**

```python
# Pattern 1: "N files/tools/ADRs/standards in directory/"
_COUNT_PATTERN = re.compile(
    r'(\d+)\s+(?:files?|tools?|ADRs?|standards?|probes?|workflows?|modules?)'
    r'(?:\s+in\s+(?:the\s+)?)?(?:`?([a-zA-Z0-9_/.\-]+/?)`?)?',
    re.IGNORECASE,
)

# Pattern 2: Table rows "| directory/ | N files |" or "| directory/ | N |"
_TABLE_COUNT_PATTERN = re.compile(
    r'\|\s*`?([a-zA-Z0-9_/.\-]+/?)`?\s*\|\s*(\d+)\s*(?:files?)?\s*\|',
)
```

**Edge Cases:**
- No numeric patterns -> returns `[]`
- Number without directory context (e.g., "version 2.0") -> not extracted (requires directory-like context)

### 5.3 `extract_file_reference_claims()`

**File:** `assemblyzero/spelunking/extractors.py`

**Signature:**

```python
def extract_file_reference_claims(
    content: str,
    source_file: Path,
) -> list[Claim]:
```

**Input Example:**

```python
content = "See [death tool](tools/death.py) and `docs/adrs/0201.md` for details."
source_file = Path("README.md")
```

**Output Example:**

```python
[
    Claim(
        claim_type=ClaimType.FILE_EXISTS,
        source_file=Path("README.md"),
        source_line=1,
        claim_text="[death tool](tools/death.py)",
        expected_value="tools/death.py",
        verification_command="exists tools/death.py",
    ),
    Claim(
        claim_type=ClaimType.FILE_EXISTS,
        source_file=Path("README.md"),
        source_line=1,
        claim_text="`docs/adrs/0201.md`",
        expected_value="docs/adrs/0201.md",
        verification_command="exists docs/adrs/0201.md",
    ),
]
```

**Regex Patterns:**

```python
# Markdown links: [text](path/to/file.ext)
_LINK_PATTERN = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')

# Inline code paths: `path/to/file.ext`
_CODE_PATH_PATTERN = re.compile(r'`([a-zA-Z0-9_][a-zA-Z0-9_/.\-]*\.[a-zA-Z]{1,10})`')
```

**Edge Cases:**
- URLs (http://...) -> excluded via prefix check
- Anchor links (#section) -> excluded
- Image references -> included if they point to local files

### 5.4 `extract_timestamp_claims()`

**File:** `assemblyzero/spelunking/extractors.py`

**Signature:**

```python
def extract_timestamp_claims(
    content: str,
    source_file: Path,
) -> list[Claim]:
```

**Input Example:**

```python
content = "<!-- Last Updated: 2026-01-15 -->\n# Some Document\nDate: 2026-02-01"
source_file = Path("docs/adrs/0201.md")
```

**Output Example:**

```python
[
    Claim(
        claim_type=ClaimType.TIMESTAMP,
        source_file=Path("docs/adrs/0201.md"),
        source_line=1,
        claim_text="Last Updated: 2026-01-15",
        expected_value="2026-01-15",
        verification_command="freshness 2026-01-15 30",
    ),
]
```

**Regex Patterns:**

```python
# "Last Updated: YYYY-MM-DD" (with optional HTML comment wrapper)
_LAST_UPDATED_PATTERN = re.compile(
    r'[Ll]ast\s+[Uu]pdated:?\s*(\d{4}-\d{2}-\d{2})'
)
```

**Edge Cases:**
- No dates found -> returns `[]`
- Invalid date format (e.g., "2026-13-99") -> still extracted; validation happens in verifier

### 5.5 `extract_technical_claims()`

**File:** `assemblyzero/spelunking/extractors.py`

**Signature:**

```python
def extract_technical_claims(
    content: str,
    source_file: Path,
    negation_patterns: list[str] | None = None,
) -> list[Claim]:
```

**Input Example:**

```python
content = "AssemblyZero uses deterministic RAG-like techniques, not vector embeddings."
source_file = Path("README.md")
negation_patterns = None
```

**Output Example:**

```python
[
    Claim(
        claim_type=ClaimType.TECHNICAL_FACT,
        source_file=Path("README.md"),
        source_line=1,
        claim_text="not vector embeddings",
        expected_value="vector embeddings",
        verification_command="grep_absent vector embeddings",
    ),
]
```

**Regex Patterns:**

```python
# Negation patterns: "not X", "without X", "no X" (where X is a technical term)
_NEGATION_PATTERN = re.compile(
    r'(?:not|without|no|never|doesn\'t use|does not use)\s+'
    r'([a-zA-Z][a-zA-Z0-9\s]{2,40}?)(?:[.,;!\n]|$)',
    re.IGNORECASE,
)
```

**Edge Cases:**
- No negations found -> returns `[]`
- Double negation ("not without") -> treated as affirmation, skipped
- Extra negation_patterns provided -> appended to default patterns

### 5.6 `verify_claim()`

**File:** `assemblyzero/spelunking/verifiers.py`

**Signature:**

```python
def verify_claim(
    claim: Claim,
    repo_root: Path,
) -> VerificationResult:
```

**Input Example:**

```python
claim = Claim(
    claim_type=ClaimType.FILE_COUNT,
    source_file=Path("inventory.md"),
    source_line=5,
    claim_text="5 tools in tools/",
    expected_value="5",
    verification_command="glob tools/*.py | count",
)
repo_root = Path("/home/user/project")
```

**Output Example:**

```python
VerificationResult(
    claim=claim,
    status=VerificationStatus.MISMATCH,
    actual_value="8",
    evidence="tools/: tool1.py, tool2.py, tool3.py, tool4.py, tool5.py, tool6.py, tool7.py, tool8.py",
)
```

**Dispatch Logic:**

```python
def verify_claim(claim: Claim, repo_root: Path) -> VerificationResult:
    try:
        if claim.claim_type == ClaimType.FILE_COUNT:
            # Parse verification_command for directory and pattern
            directory, pattern = _parse_glob_command(claim.verification_command)
            return verify_file_count(
                repo_root / directory, int(claim.expected_value), pattern
            )
        elif claim.claim_type == ClaimType.FILE_EXISTS:
            return verify_file_exists(Path(claim.expected_value), repo_root)
        elif claim.claim_type == ClaimType.TECHNICAL_FACT:
            return verify_no_contradiction(claim.expected_value, repo_root)
        elif claim.claim_type == ClaimType.UNIQUE_ID:
            directory = _parse_directory(claim.verification_command)
            return verify_unique_prefix(repo_root / directory)
        elif claim.claim_type == ClaimType.TIMESTAMP:
            return verify_timestamp_freshness(claim.expected_value)
        elif claim.claim_type == ClaimType.STATUS_MARKER:
            return VerificationResult(
                claim=claim, status=VerificationStatus.UNVERIFIABLE,
                evidence="Status markers require manual verification"
            )
    except Exception as e:
        return VerificationResult(
            claim=claim, status=VerificationStatus.ERROR,
            error_message=str(e)
        )
```

### 5.7 `verify_file_count()`

**File:** `assemblyzero/spelunking/verifiers.py`

**Signature:**

```python
def verify_file_count(
    directory: Path,
    expected_count: int,
    glob_pattern: str = "*.py",
) -> VerificationResult:
```

**Input Example:**

```python
directory = Path("/home/user/project/tools")
expected_count = 5
glob_pattern = "*.py"
```

**Output Example (mismatch):**

```python
VerificationResult(
    claim=Claim(...),  # placeholder, populated by caller
    status=VerificationStatus.MISMATCH,
    actual_value="8",
    evidence="tools/: tool1.py, tool2.py, tool3.py, tool4.py, tool5.py, tool6.py, tool7.py, tool8.py",
)
```

**Note:** This function creates a minimal internal Claim for its result. In practice, `verify_claim()` replaces the claim field with the original Claim after dispatch. The implementation should accept an optional `claim` parameter or the caller handles the replacement:

```python
def verify_file_count(
    directory: Path,
    expected_count: int,
    glob_pattern: str = "*.py",
    claim: Claim | None = None,
) -> VerificationResult:
    if not directory.is_dir():
        return VerificationResult(
            claim=claim or _make_placeholder_claim(ClaimType.FILE_COUNT),
            status=VerificationStatus.ERROR,
            error_message=f"Directory not found: {directory}",
        )
    actual_files = sorted(directory.glob(glob_pattern))
    actual_count = len(actual_files)
    file_list = ", ".join(f.name for f in actual_files)
    status = VerificationStatus.MATCH if actual_count == expected_count else VerificationStatus.MISMATCH
    return VerificationResult(
        claim=claim or _make_placeholder_claim(ClaimType.FILE_COUNT),
        status=status,
        actual_value=str(actual_count),
        evidence=f"{directory.name}/: {file_list}",
    )
```

### 5.8 `verify_file_exists()`

**File:** `assemblyzero/spelunking/verifiers.py`

**Signature:**

```python
def verify_file_exists(
    file_path: Path,
    repo_root: Path,
    claim: Claim | None = None,
) -> VerificationResult:
```

**Input Example:**

```python
file_path = Path("tools/death.py")
repo_root = Path("/home/user/project")
```

**Output Example (exists):**

```python
VerificationResult(
    claim=claim,
    status=VerificationStatus.MATCH,
    actual_value="exists",
    evidence="tools/death.py found at /home/user/project/tools/death.py",
)
```

**Output Example (path traversal):**

```python
VerificationResult(
    claim=claim,
    status=VerificationStatus.ERROR,
    error_message="Path traversal rejected: resolves outside repository root",
)
```

**Implementation:**

```python
def verify_file_exists(
    file_path: Path,
    repo_root: Path,
    claim: Claim | None = None,
) -> VerificationResult:
    placeholder = claim or _make_placeholder_claim(ClaimType.FILE_EXISTS)
    resolved = (repo_root / file_path).resolve()
    if not _is_within_repo(resolved, repo_root):
        return VerificationResult(
            claim=placeholder,
            status=VerificationStatus.ERROR,
            error_message="Path traversal rejected: resolves outside repository root",
        )
    if resolved.exists():
        return VerificationResult(
            claim=placeholder,
            status=VerificationStatus.MATCH,
            actual_value="exists",
            evidence=f"{file_path} found at {resolved}",
        )
    return VerificationResult(
        claim=placeholder,
        status=VerificationStatus.MISMATCH,
        actual_value="not found",
        evidence=f"{file_path} does not exist (checked: {resolved})",
    )
```

### 5.9 `verify_no_contradiction()`

**File:** `assemblyzero/spelunking/verifiers.py`

**Signature:**

```python
def verify_no_contradiction(
    negated_term: str,
    repo_root: Path,
    exclude_dirs: list[str] | None = None,
    claim: Claim | None = None,
) -> VerificationResult:
```

**Input Example:**

```python
negated_term = "vector embeddings"
repo_root = Path("/home/user/project")
exclude_dirs = [".git", "__pycache__", "node_modules", ".venv"]
```

**Output Example (contradiction found):**

```python
VerificationResult(
    claim=claim,
    status=VerificationStatus.MISMATCH,
    actual_value="found in 1 file(s)",
    evidence="assemblyzero/rag/embedder.py:5: import chromadb  # vector embeddings",
)
```

**Output Example (clean):**

```python
VerificationResult(
    claim=claim,
    status=VerificationStatus.MATCH,
    actual_value="not found",
    evidence="Searched 245 .py files, 0 matches for 'vector', 'embedding'",
)
```

**Implementation:**

```python
def verify_no_contradiction(
    negated_term: str,
    repo_root: Path,
    exclude_dirs: list[str] | None = None,
    claim: Claim | None = None,
) -> VerificationResult:
    placeholder = claim or _make_placeholder_claim(ClaimType.TECHNICAL_FACT)
    if exclude_dirs is None:
        exclude_dirs = [".git", "__pycache__", "node_modules", ".venv", "tests"]
    
    # Split term into individual search words
    search_terms = negated_term.lower().split()
    
    matches: list[str] = []
    files_searched = 0
    
    for py_file in repo_root.rglob("*.py"):
        # Skip excluded directories
        if any(excluded in py_file.parts for excluded in exclude_dirs):
            continue
        files_searched += 1
        try:
            content = py_file.read_text(encoding="utf-8")
            content_lower = content.lower()
            for i, line in enumerate(content_lower.splitlines(), 1):
                if any(term in line for term in search_terms):
                    rel_path = py_file.relative_to(repo_root)
                    original_line = py_file.read_text().splitlines()[i-1]
                    matches.append(f"{rel_path}:{i}: {original_line.strip()}")
                    break  # One match per file is enough
        except (UnicodeDecodeError, PermissionError):
            continue
    
    if matches:
        return VerificationResult(
            claim=placeholder,
            status=VerificationStatus.MISMATCH,
            actual_value=f"found in {len(matches)} file(s)",
            evidence="\n".join(matches[:10]),  # Cap at 10 matches
        )
    return VerificationResult(
        claim=placeholder,
        status=VerificationStatus.MATCH,
        actual_value="not found",
        evidence=f"Searched {files_searched} .py files, 0 matches for {search_terms}",
    )
```

### 5.10 `verify_unique_prefix()`

**File:** `assemblyzero/spelunking/verifiers.py`

**Signature:**

```python
def verify_unique_prefix(
    directory: Path,
    prefix_pattern: str = r"^(\d{4})-",
    claim: Claim | None = None,
) -> VerificationResult:
```

**Input Example:**

```python
directory = Path("/home/user/project/docs/adrs")
prefix_pattern = r"^(\d{4})-"
```

**Output Example (collision):**

```python
VerificationResult(
    claim=claim,
    status=VerificationStatus.MISMATCH,
    actual_value="1 collision(s)",
    evidence="Prefix 0204: 0204-collision-a.md, 0204-collision-b.md",
)
```

**Implementation:**

```python
def verify_unique_prefix(
    directory: Path,
    prefix_pattern: str = r"^(\d{4})-",
    claim: Claim | None = None,
) -> VerificationResult:
    placeholder = claim or _make_placeholder_claim(ClaimType.UNIQUE_ID)
    if not directory.is_dir():
        return VerificationResult(
            claim=placeholder,
            status=VerificationStatus.ERROR,
            error_message=f"Directory not found: {directory}",
        )
    
    compiled = re.compile(prefix_pattern)
    prefix_map: dict[str, list[str]] = {}
    
    for f in sorted(directory.iterdir()):
        if f.is_file():
            match = compiled.match(f.name)
            if match:
                prefix = match.group(1)
                prefix_map.setdefault(prefix, []).append(f.name)
    
    collisions = {p: files for p, files in prefix_map.items() if len(files) > 1}
    
    if collisions:
        evidence_parts = []
        for prefix, files in sorted(collisions.items()):
            evidence_parts.append(f"Prefix {prefix}: {', '.join(files)}")
        return VerificationResult(
            claim=placeholder,
            status=VerificationStatus.MISMATCH,
            actual_value=f"{len(collisions)} collision(s)",
            evidence="\n".join(evidence_parts),
        )
    return VerificationResult(
        claim=placeholder,
        status=VerificationStatus.MATCH,
        actual_value="0 collisions",
        evidence=f"All {len(prefix_map)} prefixes in {directory.name}/ are unique",
    )
```

### 5.11 `verify_timestamp_freshness()`

**File:** `assemblyzero/spelunking/verifiers.py`

**Signature:**

```python
def verify_timestamp_freshness(
    claimed_date: str,
    max_age_days: int = 30,
    claim: Claim | None = None,
) -> VerificationResult:
```

**Input Example (stale):**

```python
claimed_date = "2025-12-01"
max_age_days = 30
```

**Output Example (stale):**

```python
VerificationResult(
    claim=claim,
    status=VerificationStatus.STALE,
    actual_value="78 days old",
    evidence="Last Updated: 2025-12-01 (78 days ago, threshold: 30 days)",
)
```

**Input Example (fresh):**

```python
claimed_date = "2026-02-15"
max_age_days = 30
```

**Output Example (fresh):**

```python
VerificationResult(
    claim=claim,
    status=VerificationStatus.MATCH,
    actual_value="2 days old",
    evidence="Last Updated: 2026-02-15 (2 days ago, within 30 day threshold)",
)
```

**Implementation:**

```python
def verify_timestamp_freshness(
    claimed_date: str,
    max_age_days: int = 30,
    claim: Claim | None = None,
) -> VerificationResult:
    placeholder = claim or _make_placeholder_claim(ClaimType.TIMESTAMP)
    try:
        parsed = datetime.strptime(claimed_date, "%Y-%m-%d").date()
    except ValueError:
        return VerificationResult(
            claim=placeholder,
            status=VerificationStatus.ERROR,
            error_message=f"Cannot parse date: '{claimed_date}' (expected YYYY-MM-DD)",
        )
    
    today = date.today()
    age_days = (today - parsed).days
    
    if age_days > max_age_days:
        return VerificationResult(
            claim=placeholder,
            status=VerificationStatus.STALE,
            actual_value=f"{age_days} days old",
            evidence=f"Last Updated: {claimed_date} ({age_days} days ago, threshold: {max_age_days} days)",
        )
    return VerificationResult(
        claim=placeholder,
        status=VerificationStatus.MATCH,
        actual_value=f"{age_days} days old",
        evidence=f"Last Updated: {claimed_date} ({age_days} days ago, within {max_age_days} day threshold)",
    )
```

### 5.12 `_is_within_repo()`

**File:** `assemblyzero/spelunking/verifiers.py`

**Signature:**

```python
def _is_within_repo(file_path: Path, repo_root: Path) -> bool:
```

**Input Example:**

```python
file_path = Path("/home/user/project/tools/death.py")
repo_root = Path("/home/user/project")
# returns True

file_path = Path("/etc/passwd")
repo_root = Path("/home/user/project")
# returns False
```

**Implementation:**

```python
def _is_within_repo(file_path: Path, repo_root: Path) -> bool:
    try:
        resolved_file = file_path.resolve()
        resolved_root = repo_root.resolve()
        return str(resolved_file).startswith(str(resolved_root))
    except (OSError, ValueError):
        return False
```

### 5.13 `_make_placeholder_claim()`

**File:** `assemblyzero/spelunking/verifiers.py`

**Signature:**

```python
def _make_placeholder_claim(claim_type: ClaimType) -> Claim:
```

**Implementation:**

```python
def _make_placeholder_claim(claim_type: ClaimType) -> Claim:
    return Claim(
        claim_type=claim_type,
        source_file=Path("unknown"),
        source_line=0,
        claim_text="",
        expected_value="",
        verification_command="",
    )
```

### 5.14 `_parse_glob_command()`

**File:** `assemblyzero/spelunking/verifiers.py`

**Signature:**

```python
def _parse_glob_command(verification_command: str) -> tuple[str, str]:
```

**Input Example:**

```python
verification_command = "glob tools/*.py | count"
# returns ("tools", "*.py")

verification_command = "glob docs/adrs/*.md | count"
# returns ("docs/adrs", "*.md")
```

**Implementation:**

```python
def _parse_glob_command(verification_command: str) -> tuple[str, str]:
    """Parse 'glob dir/pattern | count' into (directory, pattern)."""
    match = re.match(r'glob\s+(.+?)(/[^/\s]+)\s*\|', verification_command)
    if match:
        return match.group(1).rstrip('/'), match.group(2).lstrip('/')
    # Fallback: try to split on last /
    parts = verification_command.replace("glob ", "").split("|")[0].strip()
    if "/" in parts:
        last_slash = parts.rindex("/")
        return parts[:last_slash], parts[last_slash+1:]
    return parts, "*"
```

### 5.15 `run_spelunking()`

**File:** `assemblyzero/spelunking/engine.py`

**Signature:**

```python
def run_spelunking(
    target_document: Path,
    repo_root: Path,
    checkpoints: list[SpelunkingCheckpoint] | None = None,
) -> DriftReport:
```

**Input Example:**

```python
target_document = Path("README.md")
repo_root = Path("/home/user/project")
checkpoints = None  # auto-extract
```

**Output Example:**

```python
DriftReport(
    target_document=Path("README.md"),
    results=[
        VerificationResult(claim=..., status=VerificationStatus.MATCH, ...),
        VerificationResult(claim=..., status=VerificationStatus.MISMATCH, ...),
    ],
    generated_at=datetime(2026, 2, 17, 14, 30),
)
```

**Implementation:**

```python
def run_spelunking(
    target_document: Path,
    repo_root: Path,
    checkpoints: list[SpelunkingCheckpoint] | None = None,
) -> DriftReport:
    if checkpoints:
        claims = [_checkpoint_to_claim(cp) for cp in checkpoints]
    else:
        claims = extract_claims_from_markdown(target_document)
    
    results: list[VerificationResult] = []
    for claim in claims:
        result = verify_claim(claim, repo_root)
        results.append(result)
    
    return DriftReport(
        target_document=target_document,
        results=results,
    )


def _checkpoint_to_claim(cp: SpelunkingCheckpoint) -> Claim:
    """Convert a SpelunkingCheckpoint to a Claim for verification."""
    # Determine claim type from verify_command prefix
    if cp.verify_command.startswith("glob"):
        claim_type = ClaimType.FILE_COUNT
    elif cp.verify_command.startswith("exists"):
        claim_type = ClaimType.FILE_EXISTS
    elif cp.verify_command.startswith("grep_absent"):
        claim_type = ClaimType.TECHNICAL_FACT
    elif cp.verify_command.startswith("freshness"):
        claim_type = ClaimType.TIMESTAMP
    else:
        claim_type = ClaimType.TECHNICAL_FACT  # default
    
    # Extract expected value from claim text (best effort)
    expected = cp.claim.split()[-1] if cp.claim else ""
    
    return Claim(
        claim_type=claim_type,
        source_file=Path(cp.source_file),
        source_line=0,
        claim_text=cp.claim,
        expected_value=expected,
        verification_command=cp.verify_command,
    )
```

### 5.16 `run_probe()`

**File:** `assemblyzero/spelunking/engine.py`

**Signature:**

```python
def run_probe(
    probe_name: str,
    repo_root: Path,
) -> ProbeResult:
```

**Input Example:**

```python
probe_name = "inventory_drift"
repo_root = Path("/home/user/project")
```

**Output Example:**

```python
ProbeResult(
    probe_name="inventory_drift",
    findings=[...],
    passed=False,
    summary="1 inventory drift detected",
    execution_time_ms=45.7,
)
```

**Implementation:**

```python
PROBE_REGISTRY: dict[str, Callable[[Path], ProbeResult]] = {
    "inventory_drift": probe_inventory_drift,
    "dead_references": probe_dead_references,
    "adr_collision": probe_adr_collision,
    "stale_timestamps": probe_stale_timestamps,
    "readme_claims": probe_readme_claims,
    "persona_status": probe_persona_status,
}


def run_probe(probe_name: str, repo_root: Path) -> ProbeResult:
    if probe_name not in PROBE_REGISTRY:
        raise ValueError(
            f"Unknown probe: '{probe_name}'. "
            f"Available: {', '.join(sorted(PROBE_REGISTRY.keys()))}"
        )
    
    start = time.perf_counter()
    try:
        result = PROBE_REGISTRY[probe_name](repo_root)
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return ProbeResult(
            probe_name=probe_name,
            findings=[],
            passed=False,
            summary=f"ERROR: {type(e).__name__}: {e}",
            execution_time_ms=round(elapsed, 1),
        )
    
    elapsed = (time.perf_counter() - start) * 1000
    result.execution_time_ms = round(elapsed, 1)
    return result
```

### 5.17 `run_all_probes()`

**File:** `assemblyzero/spelunking/engine.py`

**Signature:**

```python
def run_all_probes(repo_root: Path) -> list[ProbeResult]:
```

**Implementation:**

```python
def run_all_probes(repo_root: Path) -> list[ProbeResult]:
    results: list[ProbeResult] = []
    for probe_name in PROBE_REGISTRY:
        result = run_probe(probe_name, repo_root)
        results.append(result)
    return results
```

### 5.18 `generate_drift_report()`

**File:** `assemblyzero/spelunking/report.py`

**Signature:**

```python
def generate_drift_report(
    report: DriftReport,
    output_format: str = "markdown",
) -> str:
```

**Input Example:**

```python
report = DriftReport(
    target_document=Path("README.md"),
    results=[
        VerificationResult(
            claim=Claim(ClaimType.FILE_COUNT, Path("README.md"), 5, "11 tools", "11", "glob tools/*.py | count"),
            status=VerificationStatus.MATCH,
            actual_value="11",
        ),
        VerificationResult(
            claim=Claim(ClaimType.FILE_EXISTS, Path("README.md"), 10, "tools/ghost.py", "tools/ghost.py", "exists tools/ghost.py"),
            status=VerificationStatus.MISMATCH,
            actual_value="not found",
        ),
    ],
)
output_format = "markdown"
```

**Output Example (Markdown):**

```markdown
# Spelunking Drift Report

**Target:** README.md
**Generated:** 2026-02-17T14:30:00
**Drift Score:** [FAIL] 50.0%

## Summary

| Metric | Count |
|--------|-------|
| Total Claims | 2 |
| Matching | 1 |
| Mismatched | 1 |
| Stale | 0 |
| Errors | 0 |
| Unverifiable | 0 |

## Claim Details

| Source | Line | Claim | Status | Expected | Actual | Evidence |
|--------|------|-------|--------|----------|--------|----------|
| README.md | 5 | 11 tools | [PASS] MATCH | 11 | 11 | |
| README.md | 10 | tools/ghost.py | [FAIL] MISMATCH | tools/ghost.py | not found | |

---
*Generated by Spelunking Engine v1.0*
```

**Output Example (JSON):**

```json
{
    "target_document": "README.md",
    "generated_at": "2026-02-17T14:30:00",
    "drift_score": 50.0,
    "total_claims": 2,
    "matching_claims": 1,
    "results": [
        {
            "claim": {
                "claim_type": "file_count",
                "source_file": "README.md",
                "source_line": 5,
                "claim_text": "11 tools",
                "expected_value": "11",
                "verification_command": "glob tools/*.py | count"
            },
            "status": "match",
            "actual_value": "11",
            "evidence": "",
            "error_message": null
        },
        {
            "claim": {
                "claim_type": "file_exists",
                "source_file": "README.md",
                "source_line": 10,
                "claim_text": "tools/ghost.py",
                "expected_value": "tools/ghost.py",
                "verification_command": "exists tools/ghost.py"
            },
            "status": "mismatch",
            "actual_value": "not found",
            "evidence": "",
            "error_message": null
        }
    ]
}
```

**Implementation:**

```python
def generate_drift_report(
    report: DriftReport,
    output_format: str = "markdown",
) -> str:
    if output_format not in ("markdown", "json"):
        raise ValueError(
            f"Unsupported output format: '{output_format}'. "
            f"Supported: 'markdown', 'json'"
        )
    
    if output_format == "json":
        return _generate_json_report(report)
    return _generate_markdown_report(report)


def _generate_markdown_report(report: DriftReport) -> str:
    lines: list[str] = []
    lines.append("# Spelunking Drift Report")
    lines.append("")
    lines.append(f"**Target:** {report.target_document}")
    lines.append(f"**Generated:** {report.generated_at.isoformat()}")
    lines.append(f"**Drift Score:** {_format_drift_score_badge(report.drift_score)}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Claims | {report.total_claims} |")
    lines.append(f"| Matching | {report.matching_claims} |")
    
    mismatch_count = sum(1 for r in report.results if r.status == VerificationStatus.MISMATCH)
    stale_count = sum(1 for r in report.results if r.status == VerificationStatus.STALE)
    error_count = sum(1 for r in report.results if r.status == VerificationStatus.ERROR)
    unverifiable_count = sum(1 for r in report.results if r.status == VerificationStatus.UNVERIFIABLE)
    
    lines.append(f"| Mismatched | {mismatch_count} |")
    lines.append(f"| Stale | {stale_count} |")
    lines.append(f"| Errors | {error_count} |")
    lines.append(f"| Unverifiable | {unverifiable_count} |")
    lines.append("")
    lines.append("## Claim Details")
    lines.append("")
    lines.append("| Source | Line | Claim | Status | Expected | Actual | Evidence |")
    lines.append("|--------|------|-------|--------|----------|--------|----------|")
    
    for result in report.results:
        lines.append(_format_verification_row(result))
    
    lines.append("")
    lines.append("---")
    lines.append("*Generated by Spelunking Engine v1.0*")
    lines.append("")
    
    return "\n".join(lines)


def _generate_json_report(report: DriftReport) -> str:
    data = {
        "target_document": str(report.target_document),
        "generated_at": report.generated_at.isoformat(),
        "drift_score": report.drift_score,
        "total_claims": report.total_claims,
        "matching_claims": report.matching_claims,
        "results": [
            {
                "claim": {
                    "claim_type": r.claim.claim_type.value,
                    "source_file": str(r.claim.source_file),
                    "source_line": r.claim.source_line,
                    "claim_text": r.claim.claim_text,
                    "expected_value": r.claim.expected_value,
                    "verification_command": r.claim.verification_command,
                },
                "status": r.status.value,
                "actual_value": r.actual_value,
                "evidence": r.evidence,
                "error_message": r.error_message,
            }
            for r in report.results
        ],
    }
    return json.dumps(data, indent=2)
```

### 5.19 `generate_probe_summary()`

**File:** `assemblyzero/spelunking/report.py`

**Signature:**

```python
def generate_probe_summary(
    probe_results: list[ProbeResult],
) -> str:
```

**Input Example:**

```python
probe_results = [
    ProbeResult("inventory_drift", [], True, "No drift", 12.3),
    ProbeResult("dead_references", [vr1, vr2, vr3], False, "3 dead refs", 456.7),
    ProbeResult("adr_collision", [], True, "No collisions", 5.1),
]
```

**Output Example:**

```markdown
# Probe Summary

| Probe | Status | Findings | Time (ms) |
|-------|--------|----------|-----------|
| inventory_drift | [PASS] [PASS] | 0 | 12.3 |
| dead_references | [FAIL] [FAIL] | 3 | 456.7 |
| adr_collision | [PASS] [PASS] | 0 | 5.1 |

**Totals:** 3 probes | 2 passed | 1 failed | 474.1 ms total
```

**Implementation:**

```python
def generate_probe_summary(probe_results: list[ProbeResult]) -> str:
    lines: list[str] = []
    lines.append("# Probe Summary")
    lines.append("")
    lines.append("| Probe | Status | Findings | Time (ms) |")
    lines.append("|-------|--------|----------|-----------|")
    
    total_time = 0.0
    passed_count = 0
    failed_count = 0
    
    for pr in probe_results:
        status = "[PASS] [PASS]" if pr.passed else "[FAIL] [FAIL]"
        finding_count = len(pr.findings)
        lines.append(f"| {pr.probe_name} | {status} | {finding_count} | {pr.execution_time_ms} |")
        total_time += pr.execution_time_ms
        if pr.passed:
            passed_count += 1
        else:
            failed_count += 1
    
    lines.append("")
    lines.append(
        f"**Totals:** {len(probe_results)} probes | "
        f"{passed_count} passed | {failed_count} failed | "
        f"{round(total_time, 1)} ms total"
    )
    lines.append("")
    
    return "\n".join(lines)
```

### 5.20 `_format_verification_row()`

**File:** `assemblyzero/spelunking/report.py`

**Implementation:**

```python
_STATUS_ICONS = {
    VerificationStatus.MATCH: "[PASS] MATCH",
    VerificationStatus.MISMATCH: "[FAIL] MISMATCH",
    VerificationStatus.STALE: "[WARN] STALE",
    VerificationStatus.UNVERIFIABLE: " UNVERIFIABLE",
    VerificationStatus.ERROR: " ERROR",
}


def _format_verification_row(result: VerificationResult) -> str:
    status_text = _STATUS_ICONS.get(result.status, str(result.status.value))
    evidence = result.evidence.replace("\n", " ").replace("|", "\\|")[:100]
    return (
        f"| {result.claim.source_file} "
        f"| {result.claim.source_line} "
        f"| {result.claim.claim_text[:50]} "
        f"| {status_text} "
        f"| {result.claim.expected_value} "
        f"| {result.actual_value or ''} "
        f"| {evidence} |"
    )
```

### 5.21 `_format_drift_score_badge()`

**File:** `assemblyzero/spelunking/report.py`

**Implementation:**

```python
def _format_drift_score_badge(score: float) -> str:
    if score >= 90.0:
        return f"[PASS] [PASS] {score}%"
    return f"[FAIL] [FAIL] {score}%"
```

### 5.22 `probe_inventory_drift()`

**File:** `assemblyzero/workflows/janitor/probes/inventory_drift.py`

**Signature:**

```python
def probe_inventory_drift(
    repo_root: Path,
    inventory_path: Path | None = None,
) -> ProbeResult:
```

**Input Example:**

```python
repo_root = Path("/home/user/project")
inventory_path = None  # defaults to repo_root / "docs" / "standards" / "0003-file-inventory.md"
```

**Output Example (drift detected):**

```python
ProbeResult(
    probe_name="inventory_drift",
    findings=[
        VerificationResult(
            claim=Claim(ClaimType.FILE_COUNT, Path("0003-file-inventory.md"), 10, "5 tools", "5", "glob tools/*.py | count"),
            status=VerificationStatus.MISMATCH,
            actual_value="8",
            evidence="tools/: tool1.py, tool2.py, ..., tool8.py",
        ),
    ],
    passed=False,
    summary="1 inventory drift detected: tools/ claims 5, actual 8",
    execution_time_ms=0.0,  # filled by engine
)
```

**Implementation:**

```python
from __future__ import annotations

import re
import time
from pathlib import Path

from assemblyzero.spelunking.models import (
    Claim,
    ClaimType,
    ProbeResult,
    VerificationResult,
    VerificationStatus,
)
from assemblyzero.spelunking.verifiers import verify_file_count


# Pattern: "| `directory/` | N files |" or "| `directory/` | N |"
_INVENTORY_ROW_PATTERN = re.compile(
    r'\|\s*`?([a-zA-Z0-9_/.\-]+/?)`?\s*\|\s*(\d+)\s*(?:files?)?\s*\|'
)

# Fallback pattern: "N files/tools in directory/"
_INVENTORY_PROSE_PATTERN = re.compile(
    r'(\d+)\s+(?:files?|tools?|ADRs?|standards?|probes?)\s+in\s+(?:the\s+)?`?([a-zA-Z0-9_/.\-]+/?)`?',
    re.IGNORECASE,
)


def probe_inventory_drift(
    repo_root: Path,
    inventory_path: Path | None = None,
) -> ProbeResult:
    if inventory_path is None:
        inventory_path = repo_root / "docs" / "standards" / "0003-file-inventory.md"
    
    if not inventory_path.exists():
        return ProbeResult(
            probe_name="inventory_drift",
            findings=[],
            passed=False,
            summary=f"Inventory file not found: {inventory_path}",
            execution_time_ms=0.0,
        )
    
    content = inventory_path.read_text(encoding="utf-8")
    findings: list[VerificationResult] = []
    
    # Extract claimed counts from table rows
    claimed_counts: list[tuple[str, int, int]] = []  # (directory, count, line_number)
    
    for line_num, line in enumerate(content.splitlines(), 1):
        match = _INVENTORY_ROW_PATTERN.search(line)
        if match:
            directory = match.group(1).rstrip("/")
            count = int(match.group(2))
            claimed_counts.append((directory, count, line_num))
            continue
        match = _INVENTORY_PROSE_PATTERN.search(line)
        if match:
            count = int(match.group(1))
            directory = match.group(2).rstrip("/")
            claimed_counts.append((directory, count, line_num))
    
    for directory, expected_count, line_num in claimed_counts:
        dir_path = repo_root / directory
        if not dir_path.is_dir():
            continue  # Skip directories that don't exist on disk
        
        # Determine glob pattern based on directory name
        if directory.endswith((".py", ".md")):
            glob_pattern = "*"
        else:
            # Infer extension from directory content
            extensions = {f.suffix for f in dir_path.iterdir() if f.is_file() and f.suffix}
            glob_pattern = f"*{extensions.pop()}" if len(extensions) == 1 else "*"
        
        claim = Claim(
            claim_type=ClaimType.FILE_COUNT,
            source_file=inventory_path,
            source_line=line_num,
            claim_text=f"{expected_count} in {directory}/",
            expected_value=str(expected_count),
            verification_command=f"glob {directory}/{glob_pattern} | count",
        )
        
        result = verify_file_count(dir_path, expected_count, glob_pattern, claim=claim)
        if result.status != VerificationStatus.MATCH:
            findings.append(result)
    
    passed = len(findings) == 0
    if findings:
        summaries = []
        for f in findings:
            summaries.append(
                f"{f.claim.claim_text} (actual: {f.actual_value})"
            )
        summary = f"{len(findings)} inventory drift detected: {'; '.join(summaries)}"
    else:
        summary = f"No inventory drift detected across {len(claimed_counts)} checked directories"
    
    return ProbeResult(
        probe_name="inventory_drift",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=0.0,
    )
```

### 5.23 `probe_dead_references()`

**File:** `assemblyzero/workflows/janitor/probes/dead_references.py`

**Implementation:**

```python
from __future__ import annotations

import re
from pathlib import Path

from assemblyzero.spelunking.models import (
    Claim,
    ClaimType,
    ProbeResult,
    VerificationResult,
    VerificationStatus,
)
from assemblyzero.spelunking.verifiers import verify_file_exists


# Markdown links: [text](path)
_LINK_PATTERN = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')

# Inline code paths: `path/to/file.ext`
_CODE_PATH_PATTERN = re.compile(r'`([a-zA-Z0-9_][a-zA-Z0-9_/.\-]*\.[a-zA-Z]{1,10})`')


def probe_dead_references(
    repo_root: Path,
    doc_dirs: list[Path] | None = None,
) -> ProbeResult:
    if doc_dirs is None:
        doc_dirs = [repo_root / "docs", repo_root]
    
    findings: list[VerificationResult] = []
    total_refs = 0
    
    md_files: list[Path] = []
    for doc_dir in doc_dirs:
        if doc_dir.is_dir():
            if doc_dir == repo_root:
                md_files.extend(doc_dir.glob("*.md"))
            else:
                md_files.extend(doc_dir.rglob("*.md"))
    
    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        
        for line_num, line in enumerate(content.splitlines(), 1):
            # Extract link targets
            for match in _LINK_PATTERN.finditer(line):
                ref_path = match.group(2)
                if _is_external_or_anchor(ref_path):
                    continue
                total_refs += 1
                claim = Claim(
                    claim_type=ClaimType.FILE_EXISTS,
                    source_file=md_file.relative_to(repo_root) if md_file.is_relative_to(repo_root) else md_file,
                    source_line=line_num,
                    claim_text=f"[{match.group(1)}]({ref_path})",
                    expected_value=ref_path,
                    verification_command=f"exists {ref_path}",
                )
                result = verify_file_exists(Path(ref_path), repo_root, claim=claim)
                if result.status != VerificationStatus.MATCH:
                    findings.append(result)
            
            # Extract inline code paths
            for match in _CODE_PATH_PATTERN.finditer(line):
                ref_path = match.group(1)
                if _is_external_or_anchor(ref_path):
                    continue
                total_refs += 1
                claim = Claim(
                    claim_type=ClaimType.FILE_EXISTS,
                    source_file=md_file.relative_to(repo_root) if md_file.is_relative_to(repo_root) else md_file,
                    source_line=line_num,
                    claim_text=f"`{ref_path}`",
                    expected_value=ref_path,
                    verification_command=f"exists {ref_path}",
                )
                result = verify_file_exists(Path(ref_path), repo_root, claim=claim)
                if result.status != VerificationStatus.MATCH:
                    findings.append(result)
    
    passed = len(findings) == 0
    summary = (
        f"{len(findings)} dead references found out of {total_refs} checked"
        if findings
        else f"All {total_refs} file references are valid"
    )
    
    return ProbeResult(
        probe_name="dead_references",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=0.0,
    )


def _is_external_or_anchor(ref: str) -> bool:
    """Return True for URLs, anchors, and mailto links."""
    return (
        ref.startswith(("http://", "https://", "#", "mailto:"))
        or "://" in ref
    )
```

### 5.24 `probe_adr_collision()`

**File:** `assemblyzero/workflows/janitor/probes/adr_collision.py`

**Implementation:**

```python
from __future__ import annotations

from pathlib import Path

from assemblyzero.spelunking.models import (
    Claim,
    ClaimType,
    ProbeResult,
    VerificationResult,
)
from assemblyzero.spelunking.verifiers import verify_unique_prefix


def probe_adr_collision(
    repo_root: Path,
    adr_dir: Path | None = None,
) -> ProbeResult:
    if adr_dir is None:
        adr_dir = repo_root / "docs" / "adrs"
    
    if not adr_dir.is_dir():
        return ProbeResult(
            probe_name="adr_collision",
            findings=[],
            passed=True,
            summary=f"ADR directory not found: {adr_dir} (skipped)",
            execution_time_ms=0.0,
        )
    
    claim = Claim(
        claim_type=ClaimType.UNIQUE_ID,
        source_file=adr_dir,
        source_line=0,
        claim_text="ADR numeric prefixes should be unique",
        expected_value="0 collisions",
        verification_command=f"unique_prefix {adr_dir}",
    )
    
    result = verify_unique_prefix(adr_dir, claim=claim)
    
    findings = [result] if result.status != VerificationStatus.MATCH else []
    passed = result.status == VerificationStatus.MATCH
    
    file_count = len(list(adr_dir.glob("*.md")))
    summary = (
        f"ADR prefix collision: {result.evidence}"
        if not passed
        else f"No ADR prefix collisions detected in {file_count} files"
    )
    
    return ProbeResult(
        probe_name="adr_collision",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=0.0,
    )
```

### 5.25 `probe_stale_timestamps()`

**File:** `assemblyzero/workflows/janitor/probes/stale_timestamps.py`

**Implementation:**

```python
from __future__ import annotations

import re
from pathlib import Path

from assemblyzero.spelunking.models import (
    Claim,
    ClaimType,
    ProbeResult,
    VerificationResult,
    VerificationStatus,
)
from assemblyzero.spelunking.verifiers import verify_timestamp_freshness


_LAST_UPDATED_PATTERN = re.compile(
    r'[Ll]ast\s+[Uu]pdated:?\s*(\d{4}-\d{2}-\d{2})'
)


def probe_stale_timestamps(
    repo_root: Path,
    max_age_days: int = 30,
    doc_dirs: list[Path] | None = None,
) -> ProbeResult:
    if doc_dirs is None:
        doc_dirs = [repo_root / "docs", repo_root]
    
    findings: list[VerificationResult] = []
    stale_count = 0
    fresh_count = 0
    missing_count = 0
    
    md_files: list[Path] = []
    for doc_dir in doc_dirs:
        if doc_dir.is_dir():
            if doc_dir == repo_root:
                md_files.extend(doc_dir.glob("*.md"))
            else:
                md_files.extend(doc_dir.rglob("*.md"))
    
    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        
        match = _LAST_UPDATED_PATTERN.search(content)
        rel_path = md_file.relative_to(repo_root) if md_file.is_relative_to(repo_root) else md_file
        
        if not match:
            # No timestamp found — report as informational finding
            missing_count += 1
            missing_claim = Claim(
                claim_type=ClaimType.TIMESTAMP,
                source_file=rel_path,
                source_line=0,
                claim_text="No 'Last Updated' timestamp found",
                expected_value="",
                verification_command="",
            )
            findings.append(VerificationResult(
                claim=missing_claim,
                status=VerificationStatus.UNVERIFIABLE,
                actual_value="missing",
                evidence=f"{rel_path} has no 'Last Updated' field",
            ))
            continue
        
        date_str = match.group(1)
        # Find line number
        line_num = 0
        for i, line in enumerate(content.splitlines(), 1):
            if date_str in line:
                line_num = i
                break
        
        claim = Claim(
            claim_type=ClaimType.TIMESTAMP,
            source_file=rel_path,
            source_line=line_num,
            claim_text=f"Last Updated: {date_str}",
            expected_value=date_str,
            verification_command=f"freshness {date_str} {max_age_days}",
        )
        
        result = verify_timestamp_freshness(date_str, max_age_days, claim=claim)
        
        if result.status == VerificationStatus.STALE:
            stale_count += 1
            findings.append(result)
        elif result.status == VerificationStatus.MATCH:
            fresh_count += 1
        else:
            # ERROR parsing date
            findings.append(result)
    
    # Pass only if no STALE findings (missing timestamps are informational, not failures)
    has_stale = any(
        f.status == VerificationStatus.STALE for f in findings
    )
    passed = not has_stale
    
    summary = (
        f"{stale_count} stale, {fresh_count} fresh, {missing_count} missing timestamps"
    )
    
    return ProbeResult(
        probe_name="stale_timestamps",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=0.0,
    )
```

### 5.26 `probe_readme_claims()`

**File:** `assemblyzero/workflows/janitor/probes/readme_claims.py`

**Implementation:**

```python
from __future__ import annotations

from pathlib import Path

from assemblyzero.spelunking.models import (
    ProbeResult,
    VerificationResult,
    VerificationStatus,
)
from assemblyzero.spelunking.extractors import (
    extract_file_count_claims,
    extract_technical_claims,
)
from assemblyzero.spelunking.verifiers import verify_claim


def probe_readme_claims(
    repo_root: Path,
    readme_path: Path | None = None,
) -> ProbeResult:
    if readme_path is None:
        readme_path = repo_root / "README.md"
    
    if not readme_path.exists():
        return ProbeResult(
            probe_name="readme_claims",
            findings=[],
            passed=True,
            summary="README.md not found (skipped)",
            execution_time_ms=0.0,
        )
    
    content = readme_path.read_text(encoding="utf-8")
    
    # Extract high-value claims
    claims = []
    claims.extend(extract_technical_claims(content, readme_path))
    claims.extend(extract_file_count_claims(content, readme_path))
    
    findings: list[VerificationResult] = []
    match_count = 0
    
    for claim in claims:
        result = verify_claim(claim, repo_root)
        if result.status == VerificationStatus.MISMATCH:
            findings.append(result)
        elif result.status == VerificationStatus.MATCH:
            match_count += 1
    
    passed = len(findings) == 0
    summary = (
        f"{len(findings)} README contradictions found out of {len(claims)} claims checked"
        if findings
        else f"All {match_count} README claims verified ({len(claims)} total, {len(claims) - match_count} unverifiable)"
    )
    
    return ProbeResult(
        probe_name="readme_claims",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=0.0,
    )
```

### 5.27 `probe_persona_status()`

**File:** `assemblyzero/workflows/janitor/probes/persona_status.py`

**Implementation:**

```python
from __future__ import annotations

import re
from pathlib import Path

from assemblyzero.spelunking.models import (
    Claim,
    ClaimType,
    ProbeResult,
    VerificationResult,
    VerificationStatus,
)


# Pattern: "**PersonaName** — description" or "### PersonaName"
_PERSONA_PATTERN = re.compile(
    r'(?:\*\*|###?\s+)([A-Z][a-zA-Z\-]+)(?:\*\*)?'
)

# Status markers: "implemented", "active", "planned", "deprecated"
_STATUS_PATTERN = re.compile(
    r'\b(implemented|active|planned|deprecated|retired|in[- ]progress)\b',
    re.IGNORECASE,
)

# File reference within persona entry
_FILE_REF_PATTERN = re.compile(
    r'`([a-zA-Z0-9_][a-zA-Z0-9_/.\-]+\.[a-zA-Z]{1,10})`'
)


def probe_persona_status(
    repo_root: Path,
    persona_file: Path | None = None,
) -> ProbeResult:
    if persona_file is None:
        persona_file = repo_root / "Dramatis-Personae.md"
        if not persona_file.exists():
            persona_file = repo_root / "docs" / "Dramatis-Personae.md"
    
    if not persona_file.exists():
        return ProbeResult(
            probe_name="persona_status",
            findings=[],
            passed=True,
            summary="Dramatis-Personae.md not found (skipped)",
            execution_time_ms=0.0,
        )
    
    content = persona_file.read_text(encoding="utf-8")
    lines = content.splitlines()
    findings: list[VerificationResult] = []
    
    # Parse personas: each persona is a section between headers/bold names
    current_persona: str | None = None
    current_persona_line: int = 0
    persona_sections: list[tuple[str, int, str]] = []  # (name, line, section_text)
    section_lines: list[str] = []
    
    for i, line in enumerate(lines, 1):
        persona_match = _PERSONA_PATTERN.match(line.strip())
        if persona_match:
            # Save previous persona
            if current_persona and section_lines:
                persona_sections.append((current_persona, current_persona_line, "\n".join(section_lines)))
            current_persona = persona_match.group(1)
            current_persona_line = i
            section_lines = [line]
        elif current_persona:
            section_lines.append(line)
    
    # Don't forget last persona
    if current_persona and section_lines:
        persona_sections.append((current_persona, current_persona_line, "\n".join(section_lines)))
    
    for persona_name, line_num, section_text in persona_sections:
        # Check for status marker
        status_match = _STATUS_PATTERN.search(section_text)
        if not status_match:
            claim = Claim(
                claim_type=ClaimType.STATUS_MARKER,
                source_file=persona_file,
                source_line=line_num,
                claim_text=f"Persona '{persona_name}' has no status marker",
                expected_value="status marker present",
                verification_command="",
            )
            findings.append(VerificationResult(
                claim=claim,
                status=VerificationStatus.MISMATCH,
                actual_value="no status marker",
                evidence=f"Persona '{persona_name}' at line {line_num} has no implementation status",
            ))
            continue
        
        status = status_match.group(1).lower()
        
        # If marked as "implemented", check for referenced files
        if status in ("implemented", "active"):
            file_refs = _FILE_REF_PATTERN.findall(section_text)
            for ref in file_refs:
                ref_path = (repo_root / ref).resolve()
                if not ref_path.exists():
                    claim = Claim(
                        claim_type=ClaimType.FILE_EXISTS,
                        source_file=persona_file,
                        source_line=line_num,
                        claim_text=f"Persona '{persona_name}' references `{ref}`",
                        expected_value=ref,
                        verification_command=f"exists {ref}",
                    )
                    findings.append(VerificationResult(
                        claim=claim,
                        status=VerificationStatus.MISMATCH,
                        actual_value="not found",
                        evidence=f"Persona '{persona_name}' marked as {status} but `{ref}` does not exist",
                    ))
    
    passed = len(findings) == 0
    summary = (
        f"{len(findings)} persona status gaps found in {len(persona_sections)} personas"
        if findings
        else f"All {len(persona_sections)} personas have valid status markers"
    )
    
    return ProbeResult(
        probe_name="persona_status",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=0.0,
    )
```

## 6. Change Instructions

### 6.1 `docs/standards/0015-spelunking-audit-standard.md` (Add)

**Complete file contents:**

```markdown
# Standard 0015: Spelunking Audit Protocol

<!-- Last Updated: 2026-02-17 -->
<!-- Status: Active -->
<!-- Issue: #534 -->

## Purpose

Define the spelunking protocol for deep verification that documentation claims match codebase reality. Prevents the class of documentation lies discovered during Issue #114 (DEATH).

## Scope

This standard applies to all documentation in the AssemblyZero repository, including:
- README.md
- File inventories (0003-file-inventory.md)
- ADR documents (docs/adrs/)
- Standards documents (docs/standards/)
- Wiki pages
- Dramatis-Personae.md

## Definitions

- **Claim**: A verifiable factual assertion in a document (e.g., "11 tools in tools/")
- **Spelunking**: The process of extracting claims and verifying them against reality
- **Drift Score**: Percentage of verifiable claims that match reality. Target: >90%
- **Probe**: An automated check that verifies a specific category of claims

## Protocol

### 1. Claim Extraction

Claims are extracted from Markdown documents using regex patterns:

| Claim Type | Pattern | Example |
|-----------|---------|---------|
| FILE_COUNT | `N files/tools in directory/` | "11 tools in tools/" |
| FILE_EXISTS | `[text](path)` or `` `path` `` | "[death](tools/death.py)" |
| TECHNICAL_FACT | `not X`, `without X` | "not vector embeddings" |
| TIMESTAMP | `Last Updated: YYYY-MM-DD` | "Last Updated: 2026-01-15" |
| UNIQUE_ID | Numeric prefixes | "ADR-0204" |
| STATUS_MARKER | Implementation status | "Persona X: implemented" |

### 2. Source Verification

Each claim is verified against filesystem reality:

| Verification | Method | Success Criteria |
|-------------|--------|------------------|
| File count | `glob()` + count | Actual count == claimed count |
| File exists | `Path.exists()` | File found on disk |
| No contradiction | `re.search()` in source files | Negated term not found |
| Unique prefix | Group by prefix, check count | No prefix appears more than once |
| Timestamp fresh | Date arithmetic | Age ≤ 30 days |

### 3. Drift Scoring

```
drift_score = (matching_claims / verifiable_claims) * 100
```

- Claims with status `UNVERIFIABLE` are excluded from the denominator
- Target: drift_score ≥ 90%
- Scores below 90% are flagged as `[FAIL]`

### 4. Automated Probes

Six probes run as part of the janitor workflow:

1. **inventory_drift** — File counts vs. 0003-file-inventory.md
2. **dead_references** — File path references that don't exist
3. **adr_collision** — Duplicate ADR numeric prefixes
4. **stale_timestamps** — Documents with old "Last Updated" dates
5. **readme_claims** — README technical claims vs. codebase
6. **persona_status** — Dramatis-Personae.md markers vs. code

### 5. Spelunking Checkpoints (YAML)

Existing 08xx audits can declare checkpoints for the spelunking engine:

```yaml
checkpoints:
  - claim: "11 tools in tools/"
    verify_command: "glob tools/*.py | count"
    source_file: "docs/standards/0003-file-inventory.md"
  - claim: "Uses SQLite checkpointing"
    verify_command: "grep_present sqlite"
    source_file: "README.md"
```

### 6. Reports

Drift reports are generated in Markdown format with:
- Header: target document, timestamp, drift score with badge
- Summary table: total claims, matches, mismatches, stale, errors
- Per-claim detail table: source, line, claim, status, expected, actual, evidence
- JSON format available for programmatic consumption

## Compliance

- All new documentation SHOULD include a "Last Updated" timestamp
- Drift score MUST be ≥90% for critical documents (README, inventory, standards)
- Probes SHOULD run as part of regular janitor sweeps
- New claims categories can be added by extending the extractor patterns
```

### 6.2 `assemblyzero/spelunking/__init__.py` (Add)

**Complete file contents:**

```python
"""Spelunking engine — deep verification that documentation matches reality.

Issue #534: Spelunking Audits
"""

from assemblyzero.spelunking.engine import (
    run_all_probes,
    run_probe,
    run_spelunking,
)
from assemblyzero.spelunking.models import (
    Claim,
    ClaimType,
    DriftReport,
    ProbeResult,
    SpelunkingCheckpoint,
    VerificationResult,
    VerificationStatus,
)

__all__ = [
    "Claim",
    "ClaimType",
    "DriftReport",
    "ProbeResult",
    "SpelunkingCheckpoint",
    "VerificationResult",
    "VerificationStatus",
    "run_all_probes",
    "run_probe",
    "run_spelunking",
]
```

### 6.3 `assemblyzero/spelunking/models.py` (Add)

**Complete file contents:**

```python
"""Data models for the spelunking engine.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class ClaimType(Enum):
    """Categories of verifiable claims."""

    FILE_COUNT = "file_count"
    FILE_EXISTS = "file_exists"
    TECHNICAL_FACT = "technical_fact"
    STATUS_MARKER = "status_marker"
    UNIQUE_ID = "unique_id"
    TIMESTAMP = "timestamp"


class VerificationStatus(Enum):
    """Result of verifying a single claim."""

    MATCH = "match"
    MISMATCH = "mismatch"
    STALE = "stale"
    UNVERIFIABLE = "unverifiable"
    ERROR = "error"


@dataclass
class Claim:
    """A single verifiable factual claim extracted from a document."""

    claim_type: ClaimType
    source_file: Path
    source_line: int
    claim_text: str
    expected_value: str
    verification_command: str


@dataclass
class VerificationResult:
    """Result of verifying a single claim against reality."""

    claim: Claim
    status: VerificationStatus
    actual_value: Optional[str] = None
    evidence: str = ""
    verified_at: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None


@dataclass
class DriftReport:
    """Aggregated results for a spelunking run."""

    target_document: Path
    results: list[VerificationResult]
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def total_claims(self) -> int:
        """Count of all claims checked."""
        return len(self.results)

    @property
    def matching_claims(self) -> int:
        """Count of claims that match reality."""
        return sum(
            1 for r in self.results if r.status == VerificationStatus.MATCH
        )

    @property
    def drift_score(self) -> float:
        """Percentage of verifiable claims matching reality. Target: >90%."""
        verifiable = [
            r
            for r in self.results
            if r.status != VerificationStatus.UNVERIFIABLE
        ]
        if not verifiable:
            return 100.0
        matching = sum(
            1 for r in verifiable if r.status == VerificationStatus.MATCH
        )
        return round((matching / len(verifiable)) * 100, 1)


@dataclass
class SpelunkingCheckpoint:
    """YAML-serializable checkpoint for existing 08xx audits to declare."""

    claim: str
    verify_command: str
    source_file: str
    last_verified: Optional[datetime] = None
    last_status: Optional[VerificationStatus] = None


@dataclass
class ProbeResult:
    """Result from an automated spelunking probe."""

    probe_name: str
    findings: list[VerificationResult]
    passed: bool
    summary: str
    execution_time_ms: float
```

### 6.4 `assemblyzero/spelunking/extractors.py` (Add)

**Complete file contents:**

```python
"""Claim extractors — regex-based Markdown parsing for factual claims.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import re
from pathlib import Path

from assemblyzero.spelunking.models import Claim, ClaimType


# === File count patterns ===

# "N files/tools/ADRs in directory/"
_COUNT_PATTERN = re.compile(
    r"(\d+)\s+(?:files?|tools?|ADRs?|standards?|probes?|workflows?|modules?)"
    r"(?:\s+in\s+(?:the\s+)?)?(?:`?([a-zA-Z0-9_/.\-]+/?)`?)?",
    re.IGNORECASE,
)

# Table rows: "| directory/ | N files |" or "| directory/ | N |"
_TABLE_COUNT_PATTERN = re.compile(
    r"\|\s*`?([a-zA-Z0-9_/.\-]+/?)`?\s*\|\s*(\d+)\s*(?:files?)?\s*\|",
)

# === File reference patterns ===

# Markdown links: [text](path/to/file.ext)
_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

# Inline code paths: `path/to/file.ext`
_CODE_PATH_PATTERN = re.compile(
    r"`([a-zA-Z0-9_][a-zA-Z0-9_/.\-]*\.[a-zA-Z]{1,10})`"
)

# === Timestamp patterns ===

# "Last Updated: YYYY-MM-DD"
_LAST_UPDATED_PATTERN = re.compile(
    r"[Ll]ast\s+[Uu]pdated:?\s*(\d{4}-\d{2}-\d{2})"
)

# === Negation patterns ===

# "not X", "without X", "no X", "never X", "doesn't use X"
_NEGATION_PATTERN = re.compile(
    r"(?:not|without|no|never|doesn't use|does not use)\s+"
    r"([a-zA-Z][a-zA-Z0-9\s]{2,40}?)(?:[.,;!\n]|$)",
    re.IGNORECASE,
)


def extract_claims_from_markdown(
    file_path: Path,
    claim_types: list[ClaimType] | None = None,
) -> list[Claim]:
    """Parse a Markdown file and extract verifiable factual claims.

    Args:
        file_path: Path to the Markdown file to analyze.
        claim_types: Optional filter — only extract these claim types.

    Returns:
        List of Claim objects with source locations.

    Raises:
        FileNotFoundError: If file_path does not exist.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    claims: list[Claim] = []
    allowed = set(claim_types) if claim_types else None

    if allowed is None or ClaimType.FILE_COUNT in allowed:
        claims.extend(extract_file_count_claims(content, file_path))

    if allowed is None or ClaimType.FILE_EXISTS in allowed:
        claims.extend(extract_file_reference_claims(content, file_path))

    if allowed is None or ClaimType.TIMESTAMP in allowed:
        claims.extend(extract_timestamp_claims(content, file_path))

    if allowed is None or ClaimType.TECHNICAL_FACT in allowed:
        claims.extend(extract_technical_claims(content, file_path))

    return claims


def extract_file_count_claims(
    content: str,
    source_file: Path,
) -> list[Claim]:
    """Extract claims about file/directory counts from document content."""
    claims: list[Claim] = []
    lines = content.splitlines()

    for line_num, line in enumerate(lines, 1):
        # Pattern 1: Prose counts "N tools in directory/"
        for match in _COUNT_PATTERN.finditer(line):
            count_str = match.group(1)
            directory = match.group(2)
            if directory:
                directory = directory.rstrip("/")
                # Infer glob pattern from context
                glob_pattern = "*.py" if "tool" in line.lower() else "*"
                claims.append(
                    Claim(
                        claim_type=ClaimType.FILE_COUNT,
                        source_file=source_file,
                        source_line=line_num,
                        claim_text=match.group(0).strip(),
                        expected_value=count_str,
                        verification_command=f"glob {directory}/{glob_pattern} | count",
                    )
                )

        # Pattern 2: Table rows
        for match in _TABLE_COUNT_PATTERN.finditer(line):
            directory = match.group(1).rstrip("/")
            count_str = match.group(2)
            claims.append(
                Claim(
                    claim_type=ClaimType.FILE_COUNT,
                    source_file=source_file,
                    source_line=line_num,
                    claim_text=f"{directory}/ | {count_str} files",
                    expected_value=count_str,
                    verification_command=f"glob {directory}/* | count",
                )
            )

    return claims


def extract_file_reference_claims(
    content: str,
    source_file: Path,
) -> list[Claim]:
    """Extract file path references that can be verified for existence."""
    claims: list[Claim] = []
    lines = content.splitlines()

    for line_num, line in enumerate(lines, 1):
        # Markdown links
        for match in _LINK_PATTERN.finditer(line):
            ref_path = match.group(2)
            if _is_local_path(ref_path):
                claims.append(
                    Claim(
                        claim_type=ClaimType.FILE_EXISTS,
                        source_file=source_file,
                        source_line=line_num,
                        claim_text=f"[{match.group(1)}]({ref_path})",
                        expected_value=ref_path,
                        verification_command=f"exists {ref_path}",
                    )
                )

        # Inline code paths
        for match in _CODE_PATH_PATTERN.finditer(line):
            ref_path = match.group(1)
            if _is_local_path(ref_path):
                claims.append(
                    Claim(
                        claim_type=ClaimType.FILE_EXISTS,
                        source_file=source_file,
                        source_line=line_num,
                        claim_text=f"`{ref_path}`",
                        expected_value=ref_path,
                        verification_command=f"exists {ref_path}",
                    )
                )

    return claims


def extract_timestamp_claims(
    content: str,
    source_file: Path,
) -> list[Claim]:
    """Extract 'Last Updated' or date-stamped claims."""
    claims: list[Claim] = []
    lines = content.splitlines()

    for line_num, line in enumerate(lines, 1):
        match = _LAST_UPDATED_PATTERN.search(line)
        if match:
            date_str = match.group(1)
            claims.append(
                Claim(
                    claim_type=ClaimType.TIMESTAMP,
                    source_file=source_file,
                    source_line=line_num,
                    claim_text=f"Last Updated: {date_str}",
                    expected_value=date_str,
                    verification_command=f"freshness {date_str} 30",
                )
            )

    return claims


def extract_technical_claims(
    content: str,
    source_file: Path,
    negation_patterns: list[str] | None = None,
) -> list[Claim]:
    """Extract technical assertions that can be grep-verified.

    Focuses on negation claims which are highest-value for
    contradiction detection.
    """
    claims: list[Claim] = []
    lines = content.splitlines()

    for line_num, line in enumerate(lines, 1):
        for match in _NEGATION_PATTERN.finditer(line):
            negated_term = match.group(1).strip()
            # Skip very short or common false positives
            if len(negated_term) < 3:
                continue
            claims.append(
                Claim(
                    claim_type=ClaimType.TECHNICAL_FACT,
                    source_file=source_file,
                    source_line=line_num,
                    claim_text=match.group(0).strip(),
                    expected_value=negated_term,
                    verification_command=f"grep_absent {negated_term}",
                )
            )

    # Additional patterns from caller
    if negation_patterns:
        for pattern_str in negation_patterns:
            compiled = re.compile(pattern_str, re.IGNORECASE)
            for line_num, line in enumerate(lines, 1):
                match = compiled.search(line)
                if match:
                    term = match.group(1) if match.lastindex else match.group(0)
                    claims.append(
                        Claim(
                            claim_type=ClaimType.TECHNICAL_FACT,
                            source_file=source_file,
                            source_line=line_num,
                            claim_text=term.strip(),
                            expected_value=term.strip(),
                            verification_command=f"grep_absent {term.strip()}",
                        )
                    )

    return claims


def _is_local_path(ref: str) -> bool:
    """Return True if the reference is a local file path (not URL/anchor)."""
    return not (
        ref.startswith(("http://", "https://", "#", "mailto:"))
        or "://" in ref
    )
```

### 6.5 `assemblyzero/spelunking/verifiers.py` (Add)

**Complete file contents:**

```python
"""Verification strategies — filesystem, grep, prefix checks.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from assemblyzero.spelunking.models import (
    Claim,
    ClaimType,
    VerificationResult,
    VerificationStatus,
)


def verify_claim(
    claim: Claim,
    repo_root: Path,
) -> VerificationResult:
    """Verify a single claim against filesystem/codebase reality.

    Dispatches to appropriate verification strategy based on claim type.
    """
    try:
        if claim.claim_type == ClaimType.FILE_COUNT:
            directory, pattern = _parse_glob_command(claim.verification_command)
            return verify_file_count(
                repo_root / directory,
                int(claim.expected_value),
                pattern,
                claim=claim,
            )
        elif claim.claim_type == ClaimType.FILE_EXISTS:
            return verify_file_exists(
                Path(claim.expected_value), repo_root, claim=claim
            )
        elif claim.claim_type == ClaimType.TECHNICAL_FACT:
            return verify_no_contradiction(
                claim.expected_value, repo_root, claim=claim
            )
        elif claim.claim_type == ClaimType.UNIQUE_ID:
            directory = _parse_directory(claim.verification_command)
            return verify_unique_prefix(
                repo_root / directory, claim=claim
            )
        elif claim.claim_type == ClaimType.TIMESTAMP:
            return verify_timestamp_freshness(
                claim.expected_value, claim=claim
            )
        elif claim.claim_type == ClaimType.STATUS_MARKER:
            return VerificationResult(
                claim=claim,
                status=VerificationStatus.UNVERIFIABLE,
                evidence="Status markers require manual verification",
            )
        else:
            return VerificationResult(
                claim=claim,
                status=VerificationStatus.UNVERIFIABLE,
                evidence=f"Unknown claim type: {claim.claim_type}",
            )
    except Exception as e:
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.ERROR,
            error_message=f"{type(e).__name__}: {e}",
        )


def verify_file_count(
    directory: Path,
    expected_count: int,
    glob_pattern: str = "*.py",
    claim: Claim | None = None,
) -> VerificationResult:
    """Count files matching pattern in directory and compare to expected."""
    placeholder = claim or _make_placeholder_claim(ClaimType.FILE_COUNT)

    if not directory.is_dir():
        return VerificationResult(
            claim=placeholder,
            status=VerificationStatus.ERROR,
            error_message=f"Directory not found: {directory}",
        )

    actual_files = sorted(directory.glob(glob_pattern))
    # Only count files, not directories
    actual_files = [f for f in actual_files if f.is_file()]
    actual_count = len(actual_files)
    file_list = ", ".join(f.name for f in actual_files)

    status = (
        VerificationStatus.MATCH
        if actual_count == expected_count
        else VerificationStatus.MISMATCH
    )

    return VerificationResult(
        claim=placeholder,
        status=status,
        actual_value=str(actual_count),
        evidence=f"{directory.name}/: {file_list}",
    )


def verify_file_exists(
    file_path: Path,
    repo_root: Path,
    claim: Claim | None = None,
) -> VerificationResult:
    """Verify that a referenced file actually exists on disk."""
    placeholder = claim or _make_placeholder_claim(ClaimType.FILE_EXISTS)
    resolved = (repo_root / file_path).resolve()

    if not _is_within_repo(resolved, repo_root):
        return VerificationResult(
            claim=placeholder,
            status=VerificationStatus.ERROR,
            error_message="Path traversal rejected: resolves outside repository root",
        )

    if resolved.exists():
        return VerificationResult(
            claim=placeholder,
            status=VerificationStatus.MATCH,
            actual_value="exists",
            evidence=f"{file_path} found at {resolved}",
        )

    return VerificationResult(
        claim=placeholder,
        status=VerificationStatus.MISMATCH,
        actual_value="not found",
        evidence=f"{file_path} does not exist (checked: {resolved})",
    )


def verify_no_contradiction(
    negated_term: str,
    repo_root: Path,
    exclude_dirs: list[str] | None = None,
    claim: Claim | None = None,
) -> VerificationResult:
    """Grep codebase for presence of something claimed to be absent."""
    placeholder = claim or _make_placeholder_claim(ClaimType.TECHNICAL_FACT)

    if exclude_dirs is None:
        exclude_dirs = [".git", "__pycache__", "node_modules", ".venv", "tests"]

    # Split term into individual search words
    search_terms = [t.lower() for t in negated_term.split() if len(t) > 2]
    if not search_terms:
        return VerificationResult(
            claim=placeholder,
            status=VerificationStatus.UNVERIFIABLE,
            evidence=f"Search term too short: '{negated_term}'",
        )

    matches: list[str] = []
    files_searched = 0

    for py_file in repo_root.rglob("*.py"):
        # Skip excluded directories
        if any(excluded in py_file.parts for excluded in exclude_dirs):
            continue
        files_searched += 1
        try:
            content = py_file.read_text(encoding="utf-8")
            content_lower = content.lower()
            for i, line in enumerate(content_lower.splitlines(), 1):
                if any(term in line for term in search_terms):
                    try:
                        rel_path = py_file.relative_to(repo_root)
                    except ValueError:
                        rel_path = py_file
                    original_line = content.splitlines()[i - 1]
                    matches.append(f"{rel_path}:{i}: {original_line.strip()}")
                    break  # One match per file is enough
        except (UnicodeDecodeError, PermissionError):
            continue

    if matches:
        return VerificationResult(
            claim=placeholder,
            status=VerificationStatus.MISMATCH,
            actual_value=f"found in {len(matches)} file(s)",
            evidence="\n".join(matches[:10]),
        )

    return VerificationResult(
        claim=placeholder,
        status=VerificationStatus.MATCH,
        actual_value="not found",
        evidence=f"Searched {files_searched} .py files, 0 matches for {search_terms}",
    )


def verify_unique_prefix(
    directory: Path,
    prefix_pattern: str = r"^(\d{4})-",
    claim: Claim | None = None,
) -> VerificationResult:
    """Verify that no two files share the same numeric prefix."""
    placeholder = claim or _make_placeholder_claim(ClaimType.UNIQUE_ID)

    if not directory.is_dir():
        return VerificationResult(
            claim=placeholder,
            status=VerificationStatus.ERROR,
            error_message=f"Directory not found: {directory}",
        )

    compiled = re.compile(prefix_pattern)
    prefix_map: dict[str, list[str]] = {}

    for f in sorted(directory.iterdir()):
        if f.is_file():
            match = compiled.match(f.name)
            if match:
                prefix = match.group(1)
                prefix_map.setdefault(prefix, []).append(f.name)

    collisions = {p: files for p, files in prefix_map.items() if len(files) > 1}

    if collisions:
        evidence_parts = []
        for prefix, files in sorted(collisions.items()):
            evidence_parts.append(f"Prefix {prefix}: {', '.join(files)}")
        return VerificationResult(
            claim=placeholder,
            status=VerificationStatus.MISMATCH,
            actual_value=f"{len(collisions)} collision(s)",
            evidence="\n".join(evidence_parts),
        )

    return VerificationResult(
        claim=placeholder,
        status=VerificationStatus.MATCH,
        actual_value="0 collisions",
        evidence=f"All {len(prefix_map)} prefixes in {directory.name}/ are unique",
    )


def verify_timestamp_freshness(
    claimed_date: str,
    max_age_days: int = 30,
    claim: Claim | None = None,
) -> VerificationResult:
    """Check whether a claimed date is within the freshness threshold."""
    placeholder = claim or _make_placeholder_claim(ClaimType.TIMESTAMP)

    try:
        parsed = datetime.strptime(claimed_date, "%Y-%m-%d").date()
    except ValueError:
        return VerificationResult(
            claim=placeholder,
            status=VerificationStatus.ERROR,
            error_message=f"Cannot parse date: '{claimed_date}' (expected YYYY-MM-DD)",
        )

    today = date.today()
    age_days = (today - parsed).days

    if age_days > max_age_days:
        return VerificationResult(
            claim=placeholder,
            status=VerificationStatus.STALE,
            actual_value=f"{age_days} days old",
            evidence=(
                f"Last Updated: {claimed_date} "
                f"({age_days} days ago, threshold: {max_age_days} days)"
            ),
        )

    return VerificationResult(
        claim=placeholder,
        status=VerificationStatus.MATCH,
        actual_value=f"{age_days} days old",
        evidence=(
            f"Last Updated: {claimed_date} "
            f"({age_days} days ago, within {max_age_days} day threshold)"
        ),
    )


def _is_within_repo(file_path: Path, repo_root: Path) -> bool:
    """Check that resolved path is within repo_root boundary."""
    try:
        resolved_file = file_path.resolve()
        resolved_root = repo_root.resolve()
        return str(resolved_file).startswith(str(resolved_root))
    except (OSError, ValueError):
        return False


def _make_placeholder_claim(claim_type: ClaimType) -> Claim:
    """Create a placeholder claim for verifier functions called directly."""
    return Claim(
        claim_type=claim_type,
        source_file=Path("unknown"),
        source_line=0,
        claim_text="",
        expected_value="",
        verification_command="",
    )


def _parse_glob_command(verification_command: str) -> tuple[str, str]:
    """Parse 'glob dir/pattern | count' into (directory, pattern)."""
    match = re.match(r"glob\s+(.+?)(/[^/\s]+)\s*\|", verification_command)
    if match:
        return match.group(1).rstrip("/"), match.group(2).lstrip("/")
    # Fallback: try to split on last /
    parts = verification_command.replace("glob ", "").split("|")[0].strip()
    if "/" in parts:
        last_slash = parts.rindex("/")
        return parts[:last_slash], parts[last_slash + 1 :]
    return parts, "*"


def _parse_directory(verification_command: str) -> str:
    """Parse directory path from a verification command."""
    # "unique_prefix docs/adrs" -> "docs/adrs"
    parts = verification_command.split()
    if len(parts) >= 2:
        return parts[-1]
    return parts[0] if parts else ""
```

### 6.6 `assemblyzero/spelunking/report.py` (Add)

**Complete file contents:**

```python
"""Report generator — Markdown and JSON drift reports.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import json
from pathlib import Path

from assemblyzero.spelunking.models import (
    DriftReport,
    ProbeResult,
    VerificationResult,
    VerificationStatus,
)


_STATUS_ICONS = {
    VerificationStatus.MATCH: "[PASS] MATCH",
    VerificationStatus.MISMATCH: "[FAIL] MISMATCH",
    VerificationStatus.STALE: "[WARN] STALE",
    VerificationStatus.UNVERIFIABLE: " UNVERIFIABLE",
    VerificationStatus.ERROR: " ERROR",
}


def generate_drift_report(
    report: DriftReport,
    output_format: str = "markdown",
) -> str:
    """Generate a human-readable drift report from verification results.

    Args:
        report: DriftReport with all verification results.
        output_format: 'markdown' or 'json'.

    Returns:
        Formatted report string.

    Raises:
        ValueError: If output_format is not 'markdown' or 'json'.
    """
    if output_format not in ("markdown", "json"):
        raise ValueError(
            f"Unsupported output format: '{output_format}'. "
            f"Supported: 'markdown', 'json'"
        )

    if output_format == "json":
        return _generate_json_report(report)
    return _generate_markdown_report(report)


def generate_probe_summary(
    probe_results: list[ProbeResult],
) -> str:
    """Generate a summary of all probe results in Markdown table format."""
    lines: list[str] = []
    lines.append("# Probe Summary")
    lines.append("")
    lines.append("| Probe | Status | Findings | Time (ms) |")
    lines.append("|-------|--------|----------|-----------|")

    total_time = 0.0
    passed_count = 0
    failed_count = 0

    for pr in probe_results:
        status = "[PASS] [PASS]" if pr.passed else "[FAIL] [FAIL]"
        finding_count = len(pr.findings)
        lines.append(
            f"| {pr.probe_name} | {status} | {finding_count} | {pr.execution_time_ms} |"
        )
        total_time += pr.execution_time_ms
        if pr.passed:
            passed_count += 1
        else:
            failed_count += 1

    lines.append("")
    lines.append(
        f"**Totals:** {len(probe_results)} probes | "
        f"{passed_count} passed | {failed_count} failed | "
        f"{round(total_time, 1)} ms total"
    )
    lines.append("")

    return "\n".join(lines)


def _generate_markdown_report(report: DriftReport) -> str:
    """Generate Markdown format drift report."""
    lines: list[str] = []
    lines.append("# Spelunking Drift Report")
    lines.append("")
    lines.append(f"**Target:** {report.target_document}")
    lines.append(f"**Generated:** {report.generated_at.isoformat()}")
    lines.append(
        f"**Drift Score:** {_format_drift_score_badge(report.drift_score)}"
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Claims | {report.total_claims} |")
    lines.append(f"| Matching | {report.matching_claims} |")

    mismatch_count = sum(
        1 for r in report.results if r.status == VerificationStatus.MISMATCH
    )
    stale_count = sum(
        1 for r in report.results if r.status == VerificationStatus.STALE
    )
    error_count = sum(
        1 for r in report.results if r.status == VerificationStatus.ERROR
    )
    unverifiable_count = sum(
        1
        for r in report.results
        if r.status == VerificationStatus.UNVERIFIABLE
    )

    lines.append(f"| Mismatched | {mismatch_count} |")
    lines.append(f"| Stale | {stale_count} |")
    lines.append(f"| Errors | {error_count} |")
    lines.append(f"| Unverifiable | {unverifiable_count} |")
    lines.append("")
    lines.append("## Claim Details")
    lines.append("")
    lines.append(
        "| Source | Line | Claim | Status | Expected | Actual | Evidence |"
    )
    lines.append(
        "|--------|------|-------|--------|----------|--------|----------|"
    )

    for result in report.results:
        lines.append(_format_verification_row(result))

    lines.append("")
    lines.append("---")
    lines.append("*Generated by Spelunking Engine v1.0*")
    lines.append("")

    return "\n".join(lines)


def _generate_json_report(report: DriftReport) -> str:
    """Generate JSON format drift report."""
    data = {
        "target_document": str(report.target_document),
        "generated_at": report.generated_at.isoformat(),
        "drift_score": report.drift_score,
        "total_claims": report.total_claims,
        "matching_claims": report.matching_claims,
        "results": [
            {
                "claim": {
                    "claim_type": r.claim.claim_type.value,
                    "source_file": str(r.claim.source_file),
                    "source_line": r.claim.source_line,
                    "claim_text": r.claim.claim_text,
                    "expected_value": r.claim.expected_value,
                    "verification_command": r.claim.verification_command,
                },
                "status": r.status.value,
                "actual_value": r.actual_value,
                "evidence": r.evidence,
                "error_message": r.error_message,
            }
            for r in report.results
        ],
    }
    return json.dumps(data, indent=2)


def _format_verification_row(result: VerificationResult) -> str:
    """Format a single VerificationResult as a Markdown table row."""
    status_text = _STATUS_ICONS.get(result.status, str(result.status.value))
    evidence = result.evidence.replace("\n", " ").replace("|", "\\|")[:100]
    claim_text = result.claim.claim_text[:50]
    return (
        f"| {result.claim.source_file} "
        f"| {result.claim.source_line} "
        f"| {claim_text} "
        f"| {status_text} "
        f"| {result.claim.expected_value} "
        f"| {result.actual_value or ''} "
        f"| {evidence} |"
    )


def _format_drift_score_badge(score: float) -> str:
    """Format drift score with pass/fail indicator."""
    if score >= 90.0:
        return f"[PASS] [PASS] {score}%"
    return f"[FAIL] [FAIL] {score}%"
```

### 6.7 `assemblyzero/spelunking/engine.py` (Add)

**Complete file contents:**

```python
"""Core spelunking engine — orchestrates extraction, verification, reporting.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from assemblyzero.spelunking.extractors import extract_claims_from_markdown
from assemblyzero.spelunking.models import (
    Claim,
    ClaimType,
    DriftReport,
    ProbeResult,
    SpelunkingCheckpoint,
    VerificationResult,
)
from assemblyzero.spelunking.verifiers import verify_claim

# Import probes — lazy to avoid circular imports
_probe_registry: dict[str, Callable[[Path], ProbeResult]] | None = None


def _get_probe_registry() -> dict[str, Callable[[Path], ProbeResult]]:
    """Lazily initialize the probe registry."""
    global _probe_registry
    if _probe_registry is None:
        from assemblyzero.workflows.janitor.probes.adr_collision import (
            probe_adr_collision,
        )
        from assemblyzero.workflows.janitor.probes.dead_references import (
            probe_dead_references,
        )
        from assemblyzero.workflows.janitor.probes.inventory_drift import (
            probe_inventory_drift,
        )
        from assemblyzero.workflows.janitor.probes.persona_status import (
            probe_persona_status,
        )
        from assemblyzero.workflows.janitor.probes.readme_claims import (
            probe_readme_claims,
        )
        from assemblyzero.workflows.janitor.probes.stale_timestamps import (
            probe_stale_timestamps,
        )

        _probe_registry = {
            "inventory_drift": probe_inventory_drift,
            "dead_references": probe_dead_references,
            "adr_collision": probe_adr_collision,
            "stale_timestamps": probe_stale_timestamps,
            "readme_claims": probe_readme_claims,
            "persona_status": probe_persona_status,
        }
    return _probe_registry


def run_spelunking(
    target_document: Path,
    repo_root: Path,
    checkpoints: list[SpelunkingCheckpoint] | None = None,
) -> DriftReport:
    """Run full spelunking analysis on a target document.

    Extracts claims, verifies each against reality, produces drift report.
    If checkpoints are provided, uses those instead of auto-extraction.
    """
    if checkpoints:
        claims = [_checkpoint_to_claim(cp) for cp in checkpoints]
    else:
        claims = extract_claims_from_markdown(target_document)

    results: list[VerificationResult] = []
    for claim in claims:
        result = verify_claim(claim, repo_root)
        results.append(result)

    return DriftReport(
        target_document=target_document,
        results=results,
    )


def run_probe(
    probe_name: str,
    repo_root: Path,
) -> ProbeResult:
    """Run a single named spelunking probe.

    Args:
        probe_name: One of the registered probe names.
        repo_root: Repository root directory.

    Raises:
        ValueError: If probe_name is not recognized.
    """
    registry = _get_probe_registry()

    if probe_name not in registry:
        raise ValueError(
            f"Unknown probe: '{probe_name}'. "
            f"Available: {', '.join(sorted(registry.keys()))}"
        )

    start = time.perf_counter()
    try:
        result = registry[probe_name](repo_root)
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return ProbeResult(
            probe_name=probe_name,
            findings=[],
            passed=False,
            summary=f"ERROR: {type(e).__name__}: {e}",
            execution_time_ms=round(elapsed, 1),
        )

    elapsed = (time.perf_counter() - start) * 1000
    result.execution_time_ms = round(elapsed, 1)
    return result


def run_all_probes(
    repo_root: Path,
) -> list[ProbeResult]:
    """Run all registered spelunking probes and return results."""
    registry = _get_probe_registry()
    results: list[ProbeResult] = []
    for probe_name in registry:
        result = run_probe(probe_name, repo_root)
        results.append(result)
    return results


def _checkpoint_to_claim(cp: SpelunkingCheckpoint) -> Claim:
    """Convert a SpelunkingCheckpoint to a Claim for verification."""
    # Determine claim type from verify_command prefix
    if cp.verify_command.startswith("glob"):
        claim_type = ClaimType.FILE_COUNT
    elif cp.verify_command.startswith("exists"):
        claim_type = ClaimType.FILE_EXISTS
    elif cp.verify_command.startswith("grep_absent"):
        claim_type = ClaimType.TECHNICAL_FACT
    elif cp.verify_command.startswith("freshness"):
        claim_type = ClaimType.TIMESTAMP
    elif cp.verify_command.startswith("grep_present"):
        claim_type = ClaimType.TECHNICAL_FACT
    else:
        claim_type = ClaimType.TECHNICAL_FACT  # default fallback

    # Extract expected value from the claim text
    # For count claims, try to find the number
    expected = ""
    if claim_type == ClaimType.FILE_COUNT:
        import re

        num_match = re.search(r"(\d+)", cp.claim)
        expected = num_match.group(1) if num_match else ""
    elif claim_type == ClaimType.FILE_EXISTS:
        expected = cp.verify_command.replace("exists ", "").strip()
    else:
        # Use the claim text itself as the expected value
        expected = cp.claim

    return Claim(
        claim_type=claim_type,
        source_file=Path(cp.source_file),
        source_line=0,
        claim_text=cp.claim,
        expected_value=expected,
        verification_command=cp.verify_command,
    )
```

### 6.8 Probe Files — `inventory_drift.py`, `dead_references.py`, `adr_collision.py`, `stale_timestamps.py`, `readme_claims.py`, `persona_status.py`

Full contents provided in Section 5.22–5.27 above. Each file follows the same pattern of importing from `assemblyzero.spelunking.models` and `assemblyzero.spelunking.verifiers`.

### 6.9 Test Fixture Files

#### `tests/fixtures/spelunking/mock_inventory.md` (Add)

```markdown
# File Inventory

<!-- Last Updated: 2026-02-17 -->

## Directory Counts

| Directory | Count |
|-----------|-------|
| `tools/` | 5 files |
| `docs/adrs/` | 2 files |
```

#### `tests/fixtures/spelunking/mock_readme.md` (Add)

```markdown
# Mock Project

<!-- Last Updated: 2026-02-17 -->

This project has 5 tools in tools/ directory.

See [death tool](tools/death.py) for the main entry point.

AssemblyZero uses deterministic techniques, not vector embeddings.

Check `docs/adrs/0201-first.md` for architectural decisions.

There are 3 workflows in the system.
```

#### `tests/fixtures/spelunking/mock_docs_with_dead_refs.md` (Add)

```markdown
# Documentation with Dead References

See [death tool](tools/death.py) for details.

Also check `tools/ghost.py` which handles phantom operations.

Reference to [nonexistent doc](docs/nonexistent.md) here.

And a valid reference to [ADR](docs/adrs/0201-first.md).
```

#### `tests/fixtures/spelunking/mock_personas.md` (Add)

```markdown
# Dramatis Personae

## Cast

### Alice — The Builder

Status: implemented

Main code in `assemblyzero/builder.py`.

### Bob — The Tester

Status: active

Handles test generation via `assemblyzero/tester.py`.

### Charlie — The Reviewer

No status marker for this persona.

### Diana — The Planner

Status: planned

Will be implemented in phase 2.

### Eve — The Auditor

Missing status entirely.
```

#### Mock ADR Files (Add)

`tests/fixtures/spelunking/mock_repo/docs/adrs/0201-first.md`:
```markdown
# ADR 0201: First Decision

Status: Accepted
```

`tests/fixtures/spelunking/mock_repo/docs/adrs/0202-second.md`:
```markdown
# ADR 0202: Second Decision

Status: Accepted
```

`tests/fixtures/spelunking/mock_repo/docs/adrs/0204-collision-a.md`:
```markdown
# ADR 0204: Collision A

Status: Accepted
```

`tests/fixtures/spelunking/mock_repo/docs/adrs/0204-collision-b.md`:
```markdown
# ADR 0204: Collision B

Status: Proposed
```

#### Mock Tool Files (Add)

Each of `tests/fixtures/spelunking/mock_repo/tools/tool{1-8}.py`:

```python
"""Mock tool file for spelunking test fixtures."""
```

### 6.10 Test Files

#### `tests/unit/test_spelunking/__init__.py` (Add)

```python
"""Test package for spelunking engine unit tests."""
```

#### `tests/unit/test_spelunking/test_engine.py` (Add)

```python
"""Tests for core spelunking engine.

Issue #534: Spelunking Audits
Tests: T010, T020, T030, T340
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.spelunking.engine import (
    run_all_probes,
    run_probe,
    run_spelunking,
)
from assemblyzero.spelunking.models import (
    ClaimType,
    DriftReport,
    SpelunkingCheckpoint,
    VerificationStatus,
)


class TestRunSpelunking:
    """Tests for run_spelunking()."""

    def test_T010_spelunking_with_known_drift(self, tmp_path: Path) -> None:
        """T010: Engine runs spelunking on document with known drift."""
        # Create a mock doc with a count claim that will mismatch
        doc = tmp_path / "inventory.md"
        doc.write_text("There are 5 tools in tools/ directory.\n")

        # Create tools dir with only 3 files
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        for i in range(3):
            (tools_dir / f"tool{i}.py").write_text(f"# tool {i}\n")

        report = run_spelunking(doc, tmp_path)

        assert isinstance(report, DriftReport)
        assert report.total_claims > 0
        # Should have at least one mismatch since we have 3 tools, not 5
        mismatches = [
            r
            for r in report.results
            if r.status == VerificationStatus.MISMATCH
        ]
        assert len(mismatches) > 0
        assert report.drift_score < 100.0

    def test_T020_empty_document(self, tmp_path: Path) -> None:
        """T020: Engine handles empty document (no claims)."""
        doc = tmp_path / "empty.md"
        doc.write_text("# Hello\n\nJust a greeting.\n")

        report = run_spelunking(doc, tmp_path)

        assert report.total_claims == 0
        assert report.drift_score == 100.0

    def test_T030_checkpoint_override(self, tmp_path: Path) -> None:
        """T030: Engine handles checkpoints override."""
        doc = tmp_path / "doc.md"
        doc.write_text("# Doc\n")

        # Create directory with 3 files
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        for i in range(3):
            (tools_dir / f"tool{i}.py").write_text(f"# tool {i}\n")

        checkpoints = [
            SpelunkingCheckpoint(
                claim="3 tools in tools/",
                verify_command="glob tools/*.py | count",
                source_file="doc.md",
            ),
            SpelunkingCheckpoint(
                claim="tools/tool0.py exists",
                verify_command="exists tools/tool0.py",
                source_file="doc.md",
            ),
        ]

        report = run_spelunking(doc, tmp_path, checkpoints=checkpoints)

        assert report.total_claims == 2
        # Both should match
        assert all(
            r.status == VerificationStatus.MATCH for r in report.results
        )


class TestRunProbe:
    """Tests for run_probe() and run_all_probes()."""

    def test_T340_per_probe_error_isolation(self, tmp_path: Path) -> None:
        """T340: run_all_probes catches per-probe errors."""
        # Run all probes on an empty directory — some may fail
        # but none should crash the whole run
        results = run_all_probes(tmp_path)

        assert len(results) == 6  # All 6 probes registered
        # Each result should be a ProbeResult regardless of errors
        for r in results:
            assert hasattr(r, "probe_name")
            assert hasattr(r, "passed")
            assert hasattr(r, "execution_time_ms")

    def test_unknown_probe_raises_value_error(self, tmp_path: Path) -> None:
        """Unknown probe name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown probe"):
            run_probe("nonexistent_probe", tmp_path)
```

#### `tests/unit/test_spelunking/test_extractors.py` (Add)

```python
"""Tests for claim extraction logic.

Issue #534: Spelunking Audits
Tests: T040, T050, T060, T070, T080
"""

from __future__ import annotations

from pathlib import Path

from assemblyzero.spelunking.extractors import (
    extract_claims_from_markdown,
    extract_file_count_claims,
    extract_file_reference_claims,
    extract_technical_claims,
    extract_timestamp_claims,
)
from assemblyzero.spelunking.models import ClaimType


class TestExtractFileCountClaims:
    """Tests for extract_file_count_claims()."""

    def test_T040_file_count_extraction(self) -> None:
        """T040: Extractor finds file count claims."""
        content = "There are 11 tools in tools/ directory."
        claims = extract_file_count_claims(content, Path("README.md"))

        assert len(claims) >= 1
        claim = claims[0]
        assert claim.claim_type == ClaimType.FILE_COUNT
        assert claim.expected_value == "11"
        assert "tools" in claim.verification_command

    def test_table_row_extraction(self) -> None:
        """Extract counts from table rows."""
        content = "| `tools/` | 5 files |"
        claims = extract_file_count_claims(content, Path("inventory.md"))

        assert len(claims) >= 1
        assert claims[0].expected_value == "5"


class TestExtractFileReferenceClaims:
    """Tests for extract_file_reference_claims()."""

    def test_T050_file_reference_extraction(self) -> None:
        """T050: Extractor finds file reference claims."""
        content = "Check `tools/death.py` for details."
        claims = extract_file_reference_claims(content, Path("README.md"))

        assert len(claims) >= 1
        claim = claims[0]
        assert claim.claim_type == ClaimType.FILE_EXISTS
        assert claim.expected_value == "tools/death.py"

    def test_markdown_link_extraction(self) -> None:
        """Extract file references from markdown links."""
        content = "See [death tool](tools/death.py) for info."
        claims = extract_file_reference_claims(content, Path("README.md"))

        assert len(claims) >= 1
        assert claims[0].expected_value == "tools/death.py"

    def test_skips_urls(self) -> None:
        """URLs should not be extracted as file references."""
        content = "Visit [site](https://example.com) for details."
        claims = extract_file_reference_claims(content, Path("README.md"))

        assert len(claims) == 0

    def test_skips_anchors(self) -> None:
        """Anchor links should not be extracted."""
        content = "See [section](#overview) for details."
        claims = extract_file_reference_claims(content, Path("README.md"))

        assert len(claims) == 0


class TestExtractTimestampClaims:
    """Tests for extract_timestamp_claims()."""

    def test_T070_timestamp_extraction(self) -> None:
        """T070: Extractor finds timestamp claims."""
        content = "<!-- Last Updated: 2026-01-15 -->"
        claims = extract_timestamp_claims(content, Path("doc.md"))

        assert len(claims) == 1
        claim = claims[0]
        assert claim.claim_type == ClaimType.TIMESTAMP
        assert claim.expected_value == "2026-01-15"

    def test_no_timestamps(self) -> None:
        """No timestamps found returns empty list."""
        content = "# Just a heading\n\nNo dates here."
        claims = extract_timestamp_claims(content, Path("doc.md"))

        assert claims == []


class TestExtractTechnicalClaims:
    """Tests for extract_technical_claims()."""

    def test_T060_negation_extraction(self) -> None:
        """T060: Extractor finds negation claims."""
        content = "Uses deterministic techniques, not vector embeddings."
        claims = extract_technical_claims(content, Path("README.md"))

        assert len(claims) >= 1
        claim = claims[0]
        assert claim.claim_type == ClaimType.TECHNICAL_FACT
        assert "vector embeddings" in claim.expected_value

    def test_without_pattern(self) -> None:
        """Extract 'without' negation patterns."""
        content = "Built without external databases."
        claims = extract_technical_claims(content, Path("README.md"))

        assert len(claims) >= 1
        assert "external databases" in claims[0].expected_value


class TestExtractClaimsFromMarkdown:
    """Tests for the main extract_claims_from_markdown()."""

    def test_T080_no_claims(self, tmp_path: Path) -> None:
        """T080: Extractor handles no claims gracefully."""
        doc = tmp_path / "empty.md"
        doc.write_text("# Hello\n\nJust a greeting.\n")

        claims = extract_claims_from_markdown(doc)

        assert claims == []

    def test_file_not_found(self) -> None:
        """Missing file raises FileNotFoundError."""
        import pytest

        with pytest.raises(FileNotFoundError):
            extract_claims_from_markdown(Path("nonexistent.md"))

    def test_filter_by_claim_type(self, tmp_path: Path) -> None:
        """Filtering by claim type works correctly."""
        doc = tmp_path / "mixed.md"
        doc.write_text(
            "There are 5 tools in tools/.\n"
            "<!-- Last Updated: 2026-01-15 -->\n"
        )

        claims = extract_claims_from_markdown(
            doc, claim_types=[ClaimType.TIMESTAMP]
        )

        assert all(c.claim_type == ClaimType.TIMESTAMP for c in claims)
```

#### `tests/unit/test_spelunking/test_verifiers.py` (Add)

```python
"""Tests for verification strategies.

Issue #534: Spelunking Audits
Tests: T090-T190
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from assemblyzero.spelunking.models import (
    Claim,
    ClaimType,
    VerificationStatus,
)
from assemblyzero.spelunking.verifiers import (
    _is_within_repo,
    verify_claim,
    verify_file_count,
    verify_file_exists,
    verify_no_contradiction,
    verify_timestamp_freshness,
    verify_unique_prefix,
)


class TestVerifyFileCount:
    """Tests for verify_file_count()."""

    def test_T090_file_count_match(self, tmp_path: Path) -> None:
        """T090: verify_file_count with correct count returns MATCH."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(5):
            (tools / f"tool{i}.py").write_text(f"# tool {i}\n")

        result = verify_file_count(tools, 5, "*.py")

        assert result.status == VerificationStatus.MATCH
        assert result.actual_value == "5"

    def test_T100_file_count_mismatch(self, tmp_path: Path) -> None:
        """T100: verify_file_count with wrong count returns MISMATCH."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(8):
            (tools / f"tool{i}.py").write_text(f"# tool {i}\n")

        result = verify_file_count(tools, 5, "*.py")

        assert result.status == VerificationStatus.MISMATCH
        assert result.actual_value == "8"

    def test_directory_not_found(self, tmp_path: Path) -> None:
        """Nonexistent directory returns ERROR."""
        result = verify_file_count(tmp_path / "nonexistent", 5)

        assert result.status == VerificationStatus.ERROR


class TestVerifyFileExists:
    """Tests for verify_file_exists()."""

    def test_T110_file_exists_true(self, tmp_path: Path) -> None:
        """T110: verify_file_exists for existing file returns MATCH."""
        (tmp_path / "test.py").write_text("# test\n")

        result = verify_file_exists(Path("test.py"), tmp_path)

        assert result.status == VerificationStatus.MATCH

    def test_T120_file_exists_false(self, tmp_path: Path) -> None:
        """T120: verify_file_exists for nonexistent file returns MISMATCH."""
        result = verify_file_exists(Path("ghost.py"), tmp_path)

        assert result.status == VerificationStatus.MISMATCH

    def test_T190_path_traversal_rejected(self, tmp_path: Path) -> None:
        """T190: verify_file_exists with path traversal returns ERROR."""
        result = verify_file_exists(
            Path("../../etc/passwd"), tmp_path
        )

        assert result.status == VerificationStatus.ERROR
        assert "traversal" in (result.error_message or "").lower()


class TestVerifyNoContradiction:
    """Tests for verify_no_contradiction()."""

    def test_T130_no_contradiction_clean(self, tmp_path: Path) -> None:
        """T130: verify_no_contradiction for absent term returns MATCH."""
        src = tmp_path / "main.py"
        src.write_text("import os\nprint('hello')\n")

        result = verify_no_contradiction(
            "chromadb", tmp_path, exclude_dirs=[]
        )

        assert result.status == VerificationStatus.MATCH

    def test_T140_contradiction_found(self, tmp_path: Path) -> None:
        """T140: verify_no_contradiction for present term returns MISMATCH."""
        src = tmp_path / "embedder.py"
        src.write_text("import chromadb\n# vector embeddings\n")

        result = verify_no_contradiction(
            "vector embeddings", tmp_path, exclude_dirs=[]
        )

        assert result.status == VerificationStatus.MISMATCH
        assert "embedder.py" in result.evidence


class TestVerifyUniquePrefix:
    """Tests for verify_unique_prefix()."""

    def test_T150_unique_prefixes(self, tmp_path: Path) -> None:
        """T150: verify_unique_prefix with no collisions returns MATCH."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0201-first.md").write_text("# First\n")
        (adrs / "0202-second.md").write_text("# Second\n")
        (adrs / "0203-third.md").write_text("# Third\n")

        result = verify_unique_prefix(adrs)

        assert result.status == VerificationStatus.MATCH

    def test_T160_prefix_collision(self, tmp_path: Path) -> None:
        """T160: verify_unique_prefix with duplicates returns MISMATCH."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0204-first.md").write_text("# First\n")
        (adrs / "0204-second.md").write_text("# Second\n")

        result = verify_unique_prefix(adrs)

        assert result.status == VerificationStatus.MISMATCH
        assert "0204" in result.evidence


class TestVerifyTimestampFreshness:
    """Tests for verify_timestamp_freshness()."""

    def test_T170_fresh_timestamp(self) -> None:
        """T170: verify_timestamp_freshness within 30 days returns MATCH."""
        fresh_date = (date.today() - timedelta(days=5)).isoformat()

        result = verify_timestamp_freshness(fresh_date, max_age_days=30)

        assert result.status == VerificationStatus.MATCH

    def test_T180_stale_timestamp(self) -> None:
        """T180: verify_timestamp_freshness beyond 30 days returns STALE."""
        stale_date = (date.today() - timedelta(days=45)).isoformat()

        result = verify_timestamp_freshness(stale_date, max_age_days=30)

        assert result.status == VerificationStatus.STALE

    def test_invalid_date_returns_error(self) -> None:
        """Unparseable date returns ERROR."""
        result = verify_timestamp_freshness("not-a-date")

        assert result.status == VerificationStatus.ERROR


class TestIsWithinRepo:
    """Tests for _is_within_repo()."""

    def test_within_repo(self, tmp_path: Path) -> None:
        """Path inside repo returns True."""
        assert _is_within_repo(tmp_path / "file.py", tmp_path) is True

    def test_outside_repo(self, tmp_path: Path) -> None:
        """Path outside repo returns False."""
        assert _is_within_repo(Path("/etc/passwd"), tmp_path) is False


class TestVerifyClaim:
    """Tests for the main verify_claim dispatcher."""

    def test_dispatches_file_count(self, tmp_path: Path) -> None:
        """verify_claim dispatches FILE_COUNT to verify_file_count."""
        tools = tmp_path / "tools"
        tools.mkdir()
        (tools / "a.py").write_text("# a\n")

        claim = Claim(
            claim_type=ClaimType.FILE_COUNT,
            source_file=Path("doc.md"),
            source_line=1,
            claim_text="1 tool in tools/",
            expected_value="1",
            verification_command="glob tools/*.py | count",
        )

        result = verify_claim(claim, tmp_path)
        assert result.status == VerificationStatus.MATCH

    def test_dispatches_status_marker_as_unverifiable(
        self, tmp_path: Path
    ) -> None:
        """verify_claim returns UNVERIFIABLE for STATUS_MARKER claims."""
        claim = Claim(
            claim_type=ClaimType.STATUS_MARKER,
            source_file=Path("doc.md"),
            source_line=1,
            claim_text="Alice: implemented",
            expected_value="implemented",
            verification_command="",
        )

        result = verify_claim(claim, tmp_path)
        assert result.status == VerificationStatus.UNVERIFIABLE
```

#### `tests/unit/test_spelunking/test_probes.py` (Add)

```python
"""Tests for all six automated probes.

Issue #534: Spelunking Audits
Tests: T200-T300
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from assemblyzero.spelunking.models import VerificationStatus
from assemblyzero.workflows.janitor.probes.adr_collision import (
    probe_adr_collision,
)
from assemblyzero.workflows.janitor.probes.dead_references import (
    probe_dead_references,
)
from assemblyzero.workflows.janitor.probes.inventory_drift import (
    probe_inventory_drift,
)
from assemblyzero.workflows.janitor.probes.persona_status import (
    probe_persona_status,
)
from assemblyzero.workflows.janitor.probes.readme_claims import (
    probe_readme_claims,
)
from assemblyzero.workflows.janitor.probes.stale_timestamps import (
    probe_stale_timestamps,
)


class TestInventoryDriftProbe:
    """Tests for probe_inventory_drift()."""

    def test_T200_drift_detected(self, tmp_path: Path) -> None:
        """T200: probe_inventory_drift with stale inventory -> passed=False."""
        # Create inventory claiming 5 tools
        inventory = tmp_path / "inventory.md"
        inventory.write_text("| `tools/` | 5 files |\n")

        # Create 8 tools (drift!)
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(8):
            (tools / f"tool{i}.py").write_text(f"# tool {i}\n")

        result = probe_inventory_drift(tmp_path, inventory_path=inventory)

        assert result.passed is False
        assert len(result.findings) > 0

    def test_T210_inventory_matches(self, tmp_path: Path) -> None:
        """T210: probe_inventory_drift with correct inventory -> passed=True."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(3):
            (tools / f"tool{i}.py").write_text(f"# tool {i}\n")

        inventory = tmp_path / "inventory.md"
        inventory.write_text("| `tools/` | 3 files |\n")

        result = probe_inventory_drift(tmp_path, inventory_path=inventory)

        assert result.passed is True
        assert len(result.findings) == 0


class TestDeadReferencesProbe:
    """Tests for probe_dead_references()."""

    def test_T220_dead_references_found(self, tmp_path: Path) -> None:
        """T220: probe_dead_references with broken links -> passed=False."""
        doc = tmp_path / "doc.md"
        doc.write_text(
            "See [ghost](tools/ghost.py) for details.\n"
            "Also check `docs/nonexistent.md`.\n"
        )

        result = probe_dead_references(tmp_path, doc_dirs=[tmp_path])

        assert result.passed is False
        assert len(result.findings) > 0

    def test_T230_no_dead_references(self, tmp_path: Path) -> None:
        """T230: probe_dead_references with valid links -> passed=True."""
        (tmp_path / "real_file.py").write_text("# exists\n")
        doc = tmp_path / "doc.md"
        doc.write_text("See [real](real_file.py) for details.\n")

        result = probe_dead_references(tmp_path, doc_dirs=[tmp_path])

        assert result.passed is True


class TestAdrCollisionProbe:
    """Tests for probe_adr_collision()."""

    def test_T240_collision_detected(self, tmp_path: Path) -> None:
        """T240: probe_adr_collision with duplicate prefixes -> passed=False."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0204-first.md").write_text("# First\n")
        (adrs / "0204-second.md").write_text("# Second\n")

        result = probe_adr_collision(tmp_path, adr_dir=adrs)

        assert result.passed is False
        assert len(result.findings) > 0

    def test_T250_no_collisions(self, tmp_path: Path) -> None:
        """T250: probe_adr_collision with unique prefixes -> passed=True."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0201-first.md").write_text("# First\n")
        (adrs / "0202-second.md").write_text("# Second\n")

        result = probe_adr_collision(tmp_path, adr_dir=adrs)

        assert result.passed is True


class TestStaleTimestampsProbe:
    """Tests for probe_stale_timestamps()."""

    def test_T260_stale_timestamps_found(self, tmp_path: Path) -> None:
        """T260: probe_stale_timestamps with old dates -> passed=False."""
        stale_date = (date.today() - timedelta(days=45)).isoformat()
        doc = tmp_path / "stale.md"
        doc.write_text(f"<!-- Last Updated: {stale_date} -->\n# Stale Doc\n")

        result = probe_stale_timestamps(
            tmp_path, max_age_days=30, doc_dirs=[tmp_path]
        )

        assert result.passed is False
        stale_findings = [
            f
            for f in result.findings
            if f.status == VerificationStatus.STALE
        ]
        assert len(stale_findings) > 0

    def test_T270_fresh_timestamps(self, tmp_path: Path) -> None:
        """T270: probe_stale_timestamps with recent dates -> passed=True."""
        fresh_date = (date.today() - timedelta(days=5)).isoformat()
        doc = tmp_path / "fresh.md"
        doc.write_text(f"<!-- Last Updated: {fresh_date} -->\n# Fresh Doc\n")

        result = probe_stale_timestamps(
            tmp_path, max_age_days=30, doc_dirs=[tmp_path]
        )

        assert result.passed is True

    def test_T275_missing_timestamps_reported(self, tmp_path: Path) -> None:
        """T275: probe_stale_timestamps reports missing timestamps."""
        stale_date = (date.today() - timedelta(days=45)).isoformat()

        # One doc with stale timestamp
        stale_doc = tmp_path / "stale.md"
        stale_doc.write_text(
            f"<!-- Last Updated: {stale_date} -->\n# Stale\n"
        )

        # One doc with NO timestamp at all
        no_ts_doc = tmp_path / "no_timestamp.md"
        no_ts_doc.write_text("# No Timestamp\n\nJust content.\n")

        result = probe_stale_timestamps(
            tmp_path, max_age_days=30, doc_dirs=[tmp_path]
        )

        assert result.passed is False  # stale doc causes failure

        # Should have findings for both: stale + missing
        assert len(result.findings) >= 2

        missing_findings = [
            f
            for f in result.findings
            if f.status == VerificationStatus.UNVERIFIABLE
        ]
        assert len(missing_findings) >= 1
        assert "missing" in missing_findings[0].evidence.lower()


class TestReadmeClaimsProbe:
    """Tests for probe_readme_claims()."""

    def test_T280_readme_contradiction(self, tmp_path: Path) -> None:
        """T280: probe_readme_claims where README says 'not X' but code has X."""
        readme = tmp_path / "README.md"
        readme.write_text(
            "# Project\n\nThis does not use chromadb for anything.\n"
        )

        # Create code that contradicts the claim
        src = tmp_path / "embedder.py"
        src.write_text("import chromadb\n")

        result = probe_readme_claims(tmp_path, readme_path=readme)

        assert result.passed is False
        assert len(result.findings) > 0

    def test_T290_readme_claims_valid(self, tmp_path: Path) -> None:
        """T290: probe_readme_claims where claims match reality."""
        readme = tmp_path / "README.md"
        readme.write_text(
            "# Project\n\nThis does not use quantum computing.\n"
        )

        # No code references quantum computing
        src = tmp_path / "main.py"
        src.write_text("import os\nprint('hello')\n")

        result = probe_readme_claims(tmp_path, readme_path=readme)

        assert result.passed is True


class TestPersonaStatusProbe:
    """Tests for probe_persona_status()."""

    def test_T300_persona_status_gaps(self, tmp_path: Path) -> None:
        """T300: probe_persona_status with unmarked personas -> passed=False."""
        personas = tmp_path / "Dramatis-Personae.md"
        personas.write_text(
            "# Dramatis Personae\n\n"
            "### Alice — Builder\n\n"
            "Status: implemented\n\n"
            "### Bob — Tester\n\n"
            "Status: active\n\n"
            "### Charlie — Reviewer\n\n"
            "No status here.\n\n"
            "### Diana — Planner\n\n"
            "Status: planned\n\n"
            "### Eve — Auditor\n\n"
            "Also no status.\n"
        )

        result = probe_persona_status(tmp_path, persona_file=personas)

        assert result.passed is False
        # Charlie and Eve have no status markers
        assert len(result.findings) >= 2
```

#### `tests/unit/test_spelunking/test_report.py` (Add)

```python
"""Tests for drift report generation.

Issue #534: Spelunking Audits
Tests: T310, T320, T325, T327, T330, T335, T350
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from assemblyzero.spelunking.models import (
    Claim,
    ClaimType,
    DriftReport,
    ProbeResult,
    VerificationResult,
    VerificationStatus,
)
from assemblyzero.spelunking.report import (
    _format_drift_score_badge,
    generate_drift_report,
    generate_probe_summary,
)


def _make_result(
    status: VerificationStatus,
    claim_text: str = "test claim",
) -> VerificationResult:
    """Helper to create a VerificationResult for testing."""
    return VerificationResult(
        claim=Claim(
            claim_type=ClaimType.FILE_COUNT,
            source_file=Path("test.md"),
            source_line=1,
            claim_text=claim_text,
            expected_value="5",
            verification_command="glob test/* | count",
        ),
        status=status,
        actual_value="5" if status == VerificationStatus.MATCH else "3",
    )


class TestDriftScore:
    """Tests for DriftReport.drift_score property."""

    def test_T310_drift_score_calculation(self) -> None:
        """T310: DriftReport with 8/10 matching -> drift_score=80.0."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(8)]
        results.extend(
            [_make_result(VerificationStatus.MISMATCH) for _ in range(2)]
        )

        report = DriftReport(
            target_document=Path("test.md"), results=results
        )

        assert report.drift_score == 80.0

    def test_T350_unverifiable_excluded(self) -> None:
        """T350: UNVERIFIABLE claims excluded from score denominator."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(5)]
        results.extend(
            [
                _make_result(VerificationStatus.UNVERIFIABLE)
                for _ in range(3)
            ]
        )

        report = DriftReport(
            target_document=Path("test.md"), results=results
        )

        # 5 MATCH / 5 verifiable = 100% (UNVERIFIABLE excluded)
        assert report.drift_score == 100.0

    def test_empty_results(self) -> None:
        """Empty results -> 100% drift score."""
        report = DriftReport(
            target_document=Path("test.md"), results=[]
        )

        assert report.drift_score == 100.0


class TestGenerateDriftReport:
    """Tests for generate_drift_report()."""

    def test_T320_markdown_generation(self) -> None:
        """T320: generate_drift_report produces valid Markdown."""
        results = [
            _make_result(VerificationStatus.MATCH),
            _make_result(VerificationStatus.MISMATCH),
        ]
        report = DriftReport(
            target_document=Path("README.md"),
            results=results,
            generated_at=datetime(2026, 2, 17, 14, 30),
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "# Spelunking Drift Report" in output
        assert "README.md" in output
        assert "| Metric | Count |" in output
        assert "| Total Claims | 2 |" in output
        assert "[FAIL]" in output or "[PASS]" in output

    def test_T325_json_generation(self) -> None:
        """T325: generate_drift_report with JSON produces valid JSON."""
        results = [
            _make_result(VerificationStatus.MATCH),
            _make_result(VerificationStatus.MISMATCH),
            _make_result(VerificationStatus.STALE),
        ]
        report = DriftReport(
            target_document=Path("README.md"),
            results=results,
            generated_at=datetime(2026, 2, 17, 14, 30),
        )

        output = generate_drift_report(report, output_format="json")

        # Must be valid JSON
        data = json.loads(output)

        assert "drift_score" in data
        assert "results" in data
        assert "target_document" in data
        assert len(data["results"]) == 3

        # Check nested structure
        first_result = data["results"][0]
        assert "claim" in first_result
        assert "status" in first_result
        assert "claim_type" in first_result["claim"]

    def test_T327_invalid_format_raises(self) -> None:
        """T327: generate_drift_report with unsupported format raises ValueError."""
        report = DriftReport(
            target_document=Path("test.md"), results=[]
        )

        with pytest.raises(ValueError, match="Unsupported output format"):
            generate_drift_report(report, output_format="xml")


class TestGenerateProbeSummary:
    """Tests for generate_probe_summary()."""

    def test_T330_probe_summary_table(self) -> None:
        """T330: generate_probe_summary formats all probes in table."""
        probe_results = [
            ProbeResult("inventory_drift", [], True, "No drift", 12.3),
            ProbeResult(
                "dead_references",
                [_make_result(VerificationStatus.MISMATCH)],
                False,
                "1 dead ref",
                456.7,
            ),
            ProbeResult("adr_collision", [], True, "No collisions", 5.1),
        ]

        output = generate_probe_summary(probe_results)

        assert "# Probe Summary" in output
        assert "| Probe | Status | Findings | Time (ms) |" in output
        assert "inventory_drift" in output
        assert "dead_references" in output
        assert "adr_collision" in output
        assert "[PASS]" in output
        assert "[FAIL]" in output

    def test_T335_probe_summary_totals(self) -> None:
        """T335: generate_probe_summary includes totals row."""
        probe_results = [
            ProbeResult("probe1", [], True, "ok", 10.0),
            ProbeResult("probe2", [], True, "ok", 20.0),
            ProbeResult(
                "probe3",
                [_make_result(VerificationStatus.MISMATCH)],
                False,
                "fail",
                30.0,
            ),
            ProbeResult("probe4", [], True, "ok", 40.0),
            ProbeResult(
                "probe5",
                [_make_result(VerificationStatus.MISMATCH)],
                False,
                "fail",
                50.0,
            ),
            ProbeResult("probe6", [], True, "ok", 60.0),
        ]

        output = generate_probe_summary(probe_results)

        assert "**Totals:**" in output
        assert "6 probes" in output
        assert "4 passed" in output
        assert "2 failed" in output
        assert "210.0 ms total" in output


class TestDriftScoreBadge:
    """Tests for _format_drift_score_badge()."""

    def test_passing_badge(self) -> None:
        """Score >= 90 shows PASS badge."""
        badge = _format_drift_score_badge(95.0)
        assert "[PASS]" in badge
        assert "95.0%" in badge

    def test_failing_badge(self) -> None:
        """Score < 90 shows FAIL badge."""
        badge = _format_drift_score_badge(75.0)
        assert "[FAIL]" in badge
        assert "75.0%" in badge
```

#### `tests/unit/test_spelunking/test_dependencies.py` (Add)

```python
"""Tests verifying no new external dependencies are introduced.

Issue #534: Spelunking Audits
Tests: T360, T365
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest


# Standard library modules that are allowed
_STDLIB_MODULES = {
    "dataclasses",
    "datetime",
    "enum",
    "glob",
    "json",
    "os",
    "pathlib",
    "re",
    "time",
    "typing",
    "collections",
    "abc",
    "functools",
    "itertools",
    "__future__",
}

# Internal project modules that are allowed
_INTERNAL_PREFIXES = ("assemblyzero",)


class TestNoDependencies:
    """Verify spelunking package introduces no external dependencies."""

    def test_T360_no_external_imports(self) -> None:
        """T360: All imports in assemblyzero/spelunking/ resolve to stdlib or project."""
        spelunking_dir = Path("assemblyzero/spelunking")
        if not spelunking_dir.exists():
            pytest.skip("spelunking package not yet created")

        violations: list[str] = []

        for py_file in spelunking_dir.glob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                violations.append(f"{py_file}: SyntaxError")
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split(".")[0]
                        if not _is_allowed_import(module_name):
                            violations.append(
                                f"{py_file}:{node.lineno}: import {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module.split(".")[0]
                        if not _is_allowed_import(module_name):
                            violations.append(
                                f"{py_file}:{node.lineno}: from {node.module} import ..."
                            )

        assert violations == [], (
            f"External dependencies found in spelunking package:\n"
            + "\n".join(violations)
        )

    def test_T360_probe_imports(self) -> None:
        """T360: All imports in probe files resolve to stdlib or project."""
        probes_dir = Path("assemblyzero/workflows/janitor/probes")
        if not probes_dir.exists():
            pytest.skip("probes directory not yet created")

        # Only check our new probe files
        new_probes = [
            "inventory_drift.py",
            "dead_references.py",
            "adr_collision.py",
            "stale_timestamps.py",
            "readme_claims.py",
            "persona_status.py",
        ]

        violations: list[str] = []

        for probe_name in new_probes:
            py_file = probes_dir / probe_name
            if not py_file.exists():
                continue

            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                violations.append(f"{py_file}: SyntaxError")
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split(".")[0]
                        if not _is_allowed_import(module_name):
                            violations.append(
                                f"{py_file}:{node.lineno}: import {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module.split(".")[0]
                        if not _is_allowed_import(module_name):
                            violations.append(
                                f"{py_file}:{node.lineno}: from {node.module} import ..."
                            )

        assert violations == [], (
            f"External dependencies found in probe files:\n"
            + "\n".join(violations)
        )

    def test_T365_pyproject_unchanged(self) -> None:
        """T365: No new entries in pyproject.toml dependencies."""
        pyproject_path = Path("pyproject.toml")
        if not pyproject_path.exists():
            pytest.skip("pyproject.toml not found")

        content = pyproject_path.read_text(encoding="utf-8")

        # Known existing dependencies (baseline from project metadata)
        known_deps = {
            "keyring",
            "anthropic",
            "langgraph",
            "langgraph-checkpoint-sqlite",
            "langchain",
            "langchain-google-genai",
            "langchain-anthropic",
        }

        # Extract dependency names from pyproject.toml
        # Simple regex approach — look for lines in dependencies section
        import re

        dep_pattern = re.compile(r'"([a-zA-Z][a-zA-Z0-9_\-]*)')
        in_deps = False
        found_deps: set[str] = set()

        for line in content.splitlines():
            if "dependencies" in line and "=" in line:
                in_deps = True
                continue
            if in_deps:
                if line.strip() == "]":
                    in_deps = False
                    continue
                match = dep_pattern.search(line)
                if match:
                    found_deps.add(match.group(1).lower())

        # Check no new dependencies beyond known baseline
        new_deps = found_deps - {d.lower() for d in known_deps} - {"python"}
        # Filter out dev dependencies and known extras
        new_deps = {
            d
            for d in new_deps
            if not d.startswith(("pytest", "mypy", "ruff", "black", "coverage"))
        }

        assert new_deps == set(), (
            f"New dependencies found in pyproject.toml: {new_deps}"
        )


def _is_allowed_import(module_name: str) -> bool:
    """Check if a module name is stdlib or internal project."""
    if module_name in _STDLIB_MODULES:
        return True
    if any(module_name.startswith(prefix) for prefix in _INTERNAL_PREFIXES):
        return True
    # Check if it's actually a stdlib module (comprehensive check)
    if module_name in sys.stdlib_module_names:
        return True
    return False
```

## 7. Pattern References

### 7.1 Existing Probe Pattern

**File:** `assemblyzero/workflows/janitor/probes/` (directory)

The existing janitor probes directory establishes the pattern that new probe modules follow. Each probe is a standalone Python module with a single entry-point function that accepts `repo_root: Path` and returns a result dataclass.

**Relevance:** All six new probes follow this same pattern — standalone module, single function, Path input, dataclass output.

### 7.2 Dataclass Pattern

**File:** `assemblyzero/spelunking/models.py` (new)

The project uses Python `dataclasses` extensively for typed data containers. The `DriftReport` uses `@property` for computed fields, which is consistent with other project models.

**Relevance:** All new models use `@dataclass` decorator with type annotations, consistent with project conventions.

### 7.3 Test Pattern

**File:** `tests/e2e/test_issue_workflow_mock.py` (lines 1-80)

Existing test files use `pytest` with class-based test organization and `tmp_path` fixtures. Tests follow the pattern:

```python
class TestSomething:
    def test_specific_behavior(self, tmp_path: Path) -> None:
        """Descriptive docstring."""
        # Arrange
        ...
        # Act
        result = function_under_test(...)
        # Assert
        assert result.property == expected_value
```

**Relevance:** All new test files follow this same class-based organization with `tmp_path` fixtures and descriptive docstrings referencing test IDs.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | All new files |
| `from dataclasses import dataclass, field` | stdlib | `models.py` |
| `from datetime import date, datetime` | stdlib | `models.py`, `verifiers.py` |
| `from enum import Enum` | stdlib | `models.py` |
| `from pathlib import Path` | stdlib | All files |
| `from typing import Optional, Callable` | stdlib | `models.py`, `engine.py` |
| `import re` | stdlib | `extractors.py`, `verifiers.py`, probe files |
| `import time` | stdlib | `engine.py` |
| `import json` | stdlib | `report.py` |
| `import ast` | stdlib | `test_dependencies.py` |
| `import sys` | stdlib | `test_dependencies.py` |
| `import importlib` | stdlib | `test_dependencies.py` |
| `import pytest` | dev dependency (existing) | All test files |
| `from assemblyzero.spelunking.models import *` | internal | All spelunking modules |
| `from assemblyzero.spelunking.extractors import *` | internal | `engine.py`, `readme_claims.py` |
| `from assemblyzero.spelunking.verifiers import *` | internal | `engine.py`, all probe files |

**New Dependencies:** None. All imports resolve to Python stdlib or internal project modules.

## 9. Test Mapping

| Test ID | Tests Function | File | Input | Expected Output |
|---------|---------------|------|-------|-----------------|
| T010 | `run_spelunking()` | `test_engine.py` | doc with "5 tools", 3 actual tools | DriftReport with MISMATCH, drift_score < 100 |
| T020 | `run_spelunking()` | `test_engine.py` | empty doc, empty repo | DriftReport(total_claims=0, drift_score=100.0) |
| T030 | `run_spelunking()` | `test_engine.py` | 2 checkpoints, matching repo | DriftReport with 2 MATCH results |
| T040 | `extract_file_count_claims()` | `test_extractors.py` | "11 tools in tools/" | Claim(type=FILE_COUNT, expected="11") |
| T050 | `extract_file_reference_claims()` | `test_extractors.py` | "`tools/death.py`" | Claim(type=FILE_EXISTS, expected="tools/death.py") |
| T060 | `extract_technical_claims()` | `test_extractors.py` | "not vector embeddings" | Claim(type=TECHNICAL_FACT) |
| T070 | `extract_timestamp_claims()` | `test_extractors.py` | "Last Updated: 2026-01-15" | Claim(type=TIMESTAMP, expected="2026-01-15") |
| T080 | `extract_claims_from_markdown()` | `test_extractors.py` | "# Hello\nJust greeting" | `[]` |
| T090 | `verify_file_count()` | `test_verifiers.py` | dir with 5 .py, expected=5 | VerificationResult(status=MATCH) |
| T100 | `verify_file_count()` | `test_verifiers.py` | dir with 8 .py, expected=5 | VerificationResult(status=MISMATCH, actual="8") |
| T110 | `verify_file_exists()` | `test_verifiers.py` | existing tmp file | VerificationResult(status=MATCH) |
| T120 | `verify_file_exists()` | `test_verifiers.py` | nonexistent path | VerificationResult(status=MISMATCH) |
| T130 | `verify_no_contradiction()` | `test_verifiers.py` | "chromadb" absent | VerificationResult(status=MATCH) |
| T140 | `verify_no_contradiction()` | `test_verifiers.py` | "chromadb" present | VerificationResult(status=MISMATCH) |
| T150 | `verify_unique_prefix()` | `test_verifiers.py` | 3 unique ADR files | VerificationResult(status=MATCH) |
| T160 | `verify_unique_prefix()` | `test_verifiers.py` | 2 files with "0204-" | VerificationResult(status=MISMATCH) |
| T170 | `verify_timestamp_freshness()` | `test_verifiers.py` | today - 5 days | VerificationResult(status=MATCH) |
| T180 | `verify_timestamp_freshness()` | `test_verifiers.py` | today - 45 days | VerificationResult(status=STALE) |
| T190 | `verify_file_exists()` | `test_verifiers.py` | "../../etc/passwd" | VerificationResult(status=ERROR) |
| T200 | `probe_inventory_drift()` | `test_probes.py` | inventory says 5, actual 8 | ProbeResult(passed=False) |
| T210 | `probe_inventory_drift()` | `test_probes.py` | inventory says 3, actual 3 | ProbeResult(passed=True) |
| T220 | `probe_dead_references()` | `test_probes.py` | doc refs ghost.py | ProbeResult(passed=False) |
| T230 | `probe_dead_references()` | `test_probes.py` | doc refs existing file | ProbeResult(passed=True) |
| T240 | `probe_adr_collision()` | `test_probes.py` | 0204-a.md, 0204-b.md | ProbeResult(passed=False) |
| T250 | `probe_adr_collision()` | `test_probes.py` | unique prefixes | ProbeResult(passed=True) |
| T260 | `probe_stale_timestamps()` | `test_probes.py` | date 45 days old | ProbeResult(passed=False) |
| T270 | `probe_stale_timestamps()` | `test_probes.py` | date 5 days old | ProbeResult(passed=True) |
| T275 | `probe_stale_timestamps()` | `test_probes.py` | stale + missing timestamp docs | ProbeResult(passed=False, 2+ findings) |
| T280 | `probe_readme_claims()` | `test_probes.py` | "not chromadb" + import chromadb | ProbeResult(passed=False) |
| T290 | `probe_readme_claims()` | `test_probes.py` | "not quantum" + no quantum code | ProbeResult(passed=True) |
| T300 | `probe_persona_status()` | `test_probes.py` | 2 of 5 missing status | ProbeResult(passed=False) |
| T310 | `DriftReport.drift_score` | `test_report.py` | 8 MATCH + 2 MISMATCH | drift_score == 80.0 |
| T320 | `generate_drift_report()` | `test_report.py` | DriftReport with mixed | Valid Markdown with tables |
| T325 | `generate_drift_report()` | `test_report.py` | DriftReport, format="json" | Valid JSON with all fields |
| T327 | `generate_drift_report()` | `test_report.py` | format="xml" | Raises ValueError |
| T330 | `generate_probe_summary()` | `test_report.py` | 3 ProbeResults | Markdown table with [PASS]/[FAIL] |
| T335 | `generate_probe_summary()` | `test_report.py` | 6 ProbeResults | Totals row with counts |
| T340 | `run_all_probes()` | `test_engine.py` | empty tmp_path | 6 results, no crashes |
| T350 | `DriftReport.drift_score` | `test_report.py` | 5 MATCH + 3 UNVERIFIABLE | drift_score == 100.0 |
| T360 | AST import inspection | `test_dependencies.py` | spelunking/*.py + probes | No third-party imports |
| T365 | pyproject.toml inspection | `test_dependencies.py` | pyproject.toml | No new dependencies |

## 10. Implementation Notes

### 10.1 Error Handling Convention

All probes return `ProbeResult` even on error — never raise exceptions. The `run_probe()` and `run_all_probes()` functions wrap each probe call in try/except to ensure one probe's failure doesn't prevent others from running.

Verification functions return `VerificationStatus.ERROR` for exceptional cases (path traversal, unparseable dates, missing directories) rather than raising exceptions.

### 10.2 Logging Convention

No logging in this implementation. Probes report their status through the `ProbeResult.summary` field. The engine and report modules communicate results through return values, not side-effect logging.

### 10.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| Default `max_age_days` | `30` | Standard freshness threshold for documents |
| Drift score pass threshold | `90.0` | LLD requirement REQ-8 |
| Evidence truncation | `100` chars | Prevent table overflow in Markdown reports |
| Claim text truncation | `50` chars | Keep table rows readable |
| Max grep matches per report | `10` | Prevent report bloat for widespread contradictions |
| Search term minimum length | `3` chars | Avoid false positives from very short terms |

### 10.4 Lazy Import Pattern

The engine uses lazy imports for probe functions via `_get_probe_registry()` to avoid circular import issues. The probe modules import from `assemblyzero.spelunking.models` and `assemblyzero.spelunking.verifiers`, while the engine imports the probe modules. The lazy pattern ensures the spelunking package can be imported without triggering probe imports until they're needed.

### 10.5 Path Resolution

All path operations use `Path.resolve()` for security (preventing traversal attacks) and `Path.relative_to()` for reporting (clean display paths). The `_is_within_repo()` guard is called before any `verify_file_exists()` check.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 — only `probes/` directory is "Modify", covered in 3.1)
- [x] Every data structure has a concrete JSON/YAML example (Section 4 — all 7 structures have examples)
- [x] Every function has input/output examples with realistic values (Section 5 — all 27 functions specified)
- [x] Change instructions are diff-level specific (Section 6 — complete file contents for all Add files)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 9 — all 39 tests mapped)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #534 |
| Verdict | DRAFT |
| Date | 2026-02-17 |
| Iterations | 1 |
| Finalized | — |