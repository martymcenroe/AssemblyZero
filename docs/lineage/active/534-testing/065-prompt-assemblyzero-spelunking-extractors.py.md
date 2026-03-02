# Implementation Request: assemblyzero/spelunking/extractors.py

## Task

Write the complete contents of `assemblyzero/spelunking/extractors.py`.

Change type: Add
Description: Claim extractors from Markdown

## LLD Specification

# Implementation Spec: Spelunking Audits — Deep Verification That Reality Matches Claims

| Field | Value |
|-------|-------|
| Issue | #534 |
| LLD | `docs/lld/active/534-spelunking-audits.md` |
| Generated | 2026-02-17 |
| Status | DRAFT |


## 1. Overview

**Objective:** Build a two-layer spelunking system (automated probes + engine-driven deep dives) that verifies documentation claims against codebase reality, preventing documentation drift discovered during Issue #114 (DEATH).

**Success Criteria:** Six automated probes detect inventory drift, dead references, ADR collisions, stale timestamps, README contradictions, and persona status gaps. Drift score calculated as percentage of verifiable claims matching reality; score below 90% is flagged. All implementation uses stdlib only — no new external dependencies.


## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `docs/standards/0015-spelunking-audit-standard.md` | Add | Standard defining spelunking protocol |
| 2 | `assemblyzero/spelunking/__init__.py` | Add | Package init |
| 3 | `assemblyzero/spelunking/models.py` | Add | Data models: Claim, VerificationResult, DriftReport, etc. |
| 4 | `assemblyzero/spelunking/extractors.py` | Add | Claim extractors from Markdown |
| 5 | `assemblyzero/spelunking/verifiers.py` | Add | Verification strategies |
| 6 | `assemblyzero/spelunking/report.py` | Add | Drift report generation (Markdown + JSON) |
| 7 | `assemblyzero/spelunking/engine.py` | Add | Core engine: run_spelunking, run_probe, run_all_probes |
| 8 | `assemblyzero/workflows/janitor/probes/inventory_drift.py` | Add | Probe: inventory count drift |
| 9 | `assemblyzero/workflows/janitor/probes/dead_references.py` | Add | Probe: dead file references |
| 10 | `assemblyzero/workflows/janitor/probes/adr_collision.py` | Add | Probe: ADR prefix collisions |
| 11 | `assemblyzero/workflows/janitor/probes/stale_timestamps.py` | Add | Probe: stale/missing timestamps |
| 12 | `assemblyzero/workflows/janitor/probes/readme_claims.py` | Add | Probe: README contradictions |
| 13 | `assemblyzero/workflows/janitor/probes/persona_status.py` | Add | Probe: persona status gaps |
| 14 | `tests/fixtures/spelunking/mock_inventory.md` | Add | Mock inventory with known drift |
| 15 | `tests/fixtures/spelunking/mock_readme.md` | Add | Mock README with testable claims |
| 16 | `tests/fixtures/spelunking/mock_docs_with_dead_refs.md` | Add | Mock doc with dead references |
| 17 | `tests/fixtures/spelunking/mock_personas.md` | Add | Mock personas with status gaps |
| 18 | `tests/unit/test_spelunking/__init__.py` | Add | Test package init |
| 19 | `tests/unit/test_spelunking/test_engine.py` | Add | Engine tests |
| 20 | `tests/unit/test_spelunking/test_extractors.py` | Add | Extractor tests |
| 21 | `tests/unit/test_spelunking/test_verifiers.py` | Add | Verifier tests |
| 22 | `tests/unit/test_spelunking/test_probes.py` | Add | Probe tests |
| 23 | `tests/unit/test_spelunking/test_report.py` | Add | Report tests |
| 24 | `tests/unit/test_spelunking/test_dependencies.py` | Add | Dependency verification tests |

**Implementation Order Rationale:** Models first (no dependencies), then extractors and verifiers (depend on models), then report (depends on models), then engine (depends on all), then probes (depend on engine/models/verifiers/extractors), then fixtures, then tests.


## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/workflows/janitor/probes/` (Modify — Directory)

**Current state:** This directory exists and contains existing probe modules. We are adding new files to this directory, not modifying existing ones.

**Listing of current directory** (representative):

```
assemblyzero/workflows/janitor/probes/
├── __init__.py
├── ... (existing probe files)
```

**What changes:** Six new probe modules are added as siblings to existing probes. No existing files are modified. The new probes follow the same return pattern as existing probes (returning result dataclasses). The existing `__init__.py` is NOT modified — the new probes are standalone modules imported directly by the engine.


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
    "source_line": 14,
    "claim_text": "11 tools in tools/",
    "expected_value": "11",
    "verification_command": "glob tools/*.py | count"
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

**Concrete Example:**

```json
{
    "claim": {
        "claim_type": "file_count",
        "source_file": "docs/standards/0003-file-inventory.md",
        "source_line": 14,
        "claim_text": "11 tools in tools/",
        "expected_value": "11",
        "verification_command": "glob tools/*.py | count"
    },
    "status": "mismatch",
    "actual_value": "36",
    "evidence": "Found 36 .py files in tools/",
    "verified_at": "2026-02-17T10:30:00",
    "error_message": null
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
    def total_claims(self) -> int:
        return len(self.results)

    @property
    def matching_claims(self) -> int:
        return sum(1 for r in self.results if r.status == VerificationStatus.MATCH)

    @property
    def drift_score(self) -> float:
        verifiable = [r for r in self.results if r.status != VerificationStatus.UNVERIFIABLE]
        if not verifiable:
            return 100.0
        matching = sum(1 for r in verifiable if r.status == VerificationStatus.MATCH)
        return round((matching / len(verifiable)) * 100, 1)
```

**Concrete Example:**

```json
{
    "target_document": "docs/standards/0003-file-inventory.md",
    "results": [
        {
            "claim": {"claim_type": "file_count", "source_file": "docs/standards/0003-file-inventory.md", "source_line": 14, "claim_text": "11 tools", "expected_value": "11", "verification_command": "glob tools/*.py | count"},
            "status": "mismatch",
            "actual_value": "36",
            "evidence": "Found 36 .py files in tools/",
            "verified_at": "2026-02-17T10:30:00",
            "error_message": null
        },
        {
            "claim": {"claim_type": "file_exists", "source_file": "docs/standards/0003-file-inventory.md", "source_line": 22, "claim_text": "tools/death.py", "expected_value": "tools/death.py", "verification_command": "path_exists tools/death.py"},
            "status": "match",
            "actual_value": "tools/death.py",
            "evidence": "File exists at tools/death.py",
            "verified_at": "2026-02-17T10:30:01",
            "error_message": null
        }
    ],
    "generated_at": "2026-02-17T10:30:01",
    "total_claims": 2,
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

**Concrete Example:**

```yaml
claim: "11 tools exist in tools/ directory"
verify_command: "glob tools/*.py | count"
source_file: "docs/standards/0003-file-inventory.md"
last_verified: "2026-02-15T08:00:00"
last_status: "match"
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

**Concrete Example:**

```json
{
    "probe_name": "inventory_drift",
    "findings": [
        {
            "claim": {"claim_type": "file_count", "source_file": "docs/standards/0003-file-inventory.md", "source_line": 14, "claim_text": "11 tools", "expected_value": "11", "verification_command": "glob tools/*.py | count"},
            "status": "mismatch",
            "actual_value": "36",
            "evidence": "Found 36 .py files in tools/",
            "verified_at": "2026-02-17T10:30:00",
            "error_message": null
        }
    ],
    "passed": false,
    "summary": "1 inventory mismatch found: tools/ claims 11, actual 36",
    "execution_time_ms": 45.2
}
```


## 5. Function Specifications

### 5.1 `run_spelunking()`

**File:** `assemblyzero/spelunking/engine.py`

**Signature:**

```python
def run_spelunking(
    target_document: Path,
    repo_root: Path,
    checkpoints: list[SpelunkingCheckpoint] | None = None,
) -> DriftReport:
    """Run full spelunking analysis on a target document."""
    ...
```

**Input Example:**

```python
target_document = Path("docs/standards/0003-file-inventory.md")
repo_root = Path("/home/user/assemblyzero")
checkpoints = None
```

**Output Example:**

```python
DriftReport(
    target_document=Path("docs/standards/0003-file-inventory.md"),
    results=[
        VerificationResult(
            claim=Claim(claim_type=ClaimType.FILE_COUNT, source_file=Path("docs/standards/0003-file-inventory.md"), source_line=14, claim_text="11 tools", expected_value="11", verification_command="glob tools/*.py | count"),
            status=VerificationStatus.MISMATCH,
            actual_value="36",
            evidence="Found 36 .py files in tools/",
        )
    ],
)
# drift_score == 0.0 (0 of 1 verifiable claims match)
```

**Edge Cases:**
- Empty document (no claims) -> `DriftReport(results=[], drift_score=100.0)`
- `checkpoints` provided -> uses those instead of auto-extraction, converts each to `Claim`
- Nonexistent `target_document` -> `DriftReport(results=[], drift_score=100.0)` (no claims to extract)

### 5.2 `run_probe()`

**File:** `assemblyzero/spelunking/engine.py`

**Signature:**

```python
def run_probe(
    probe_name: str,
    repo_root: Path,
) -> ProbeResult:
    """Run a single named spelunking probe."""
    ...
```

**Input Example:**

```python
probe_name = "inventory_drift"
repo_root = Path("/home/user/assemblyzero")
```

**Output Example:**

```python
ProbeResult(
    probe_name="inventory_drift",
    findings=[...],
    passed=False,
    summary="1 inventory mismatch found",
    execution_time_ms=45.2,
)
```

**Edge Cases:**
- Unknown `probe_name` -> raises `ValueError("Unknown probe: xyz")`
- Probe function raises exception -> returns `ProbeResult(passed=False, summary="Error: <message>", execution_time_ms=...)`

### 5.3 `run_all_probes()`

**File:** `assemblyzero/spelunking/engine.py`

**Signature:**

```python
def run_all_probes(
    repo_root: Path,
) -> list[ProbeResult]:
    """Run all registered spelunking probes and return results."""
    ...
```

**Input Example:**

```python
repo_root = Path("/tmp/pytest-xyz/test_empty_repo")
```

**Output Example:**

```python
[
    ProbeResult(probe_name="inventory_drift", findings=[], passed=True, summary="No inventory drift detected", execution_time_ms=12.3),
    ProbeResult(probe_name="dead_references", findings=[], passed=True, summary="No dead references found", execution_time_ms=8.1),
    ProbeResult(probe_name="adr_collision", findings=[], passed=True, summary="No ADR collisions found", execution_time_ms=5.4),
    ProbeResult(probe_name="stale_timestamps", findings=[], passed=True, summary="No stale timestamps found", execution_time_ms=7.2),
    ProbeResult(probe_name="readme_claims", findings=[], passed=True, summary="No README contradictions found", execution_time_ms=3.8),
    ProbeResult(probe_name="persona_status", findings=[], passed=True, summary="No persona status gaps found", execution_time_ms=4.1),
]
```

**Edge Cases:**
- One probe throws RuntimeError -> that probe returns `ProbeResult(passed=False)`, all other probes still run, returns 6 results total
- Empty repo (no docs) -> all probes return `passed=True` with empty findings

### 5.4 `_get_probe_registry()`

**File:** `assemblyzero/spelunking/engine.py`

**Signature:**

```python
def _get_probe_registry() -> dict[str, Callable[[Path], ProbeResult]]:
    """Return mapping of probe names to their functions. Lazy imports."""
    ...
```

**Input Example:** (no arguments)

**Output Example:**

```python
{
    "inventory_drift": <function probe_inventory_drift>,
    "dead_references": <function probe_dead_references>,
    "adr_collision": <function probe_adr_collision>,
    "stale_timestamps": <function probe_stale_timestamps>,
    "readme_claims": <function probe_readme_claims>,
    "persona_status": <function probe_persona_status>,
}
```

**Edge Cases:** None — static registry.

### 5.5 `extract_claims_from_markdown()`

**File:** `assemblyzero/spelunking/extractors.py`

**Signature:**

```python
def extract_claims_from_markdown(
    file_path: Path,
    claim_types: list[ClaimType] | None = None,
) -> list[Claim]:
    """Parse a Markdown file and extract verifiable factual claims."""
    ...
```

**Input Example:**

```python
file_path = Path("/tmp/test/mock_inventory.md")
# File content: "There are 11 tools in `tools/`\nSee `tools/death.py` for details."
claim_types = None  # extract all types
```

**Output Example:**

```python
[
    Claim(claim_type=ClaimType.FILE_COUNT, source_file=Path("/tmp/test/mock_inventory.md"), source_line=1, claim_text="11 tools in `tools/`", expected_value="11", verification_command="glob tools/*.py | count"),
    Claim(claim_type=ClaimType.FILE_EXISTS, source_file=Path("/tmp/test/mock_inventory.md"), source_line=2, claim_text="tools/death.py", expected_value="tools/death.py", verification_command="path_exists tools/death.py"),
]
```

**Edge Cases:**
- File with no verifiable claims -> `[]`
- `claim_types=[ClaimType.FILE_COUNT]` -> only returns FILE_COUNT claims
- Nonexistent file -> `[]` (graceful handling)

### 5.6 `extract_file_count_claims()`

**File:** `assemblyzero/spelunking/extractors.py`

**Signature:**

```python
def extract_file_count_claims(
    content: str,
    source_file: Path,
) -> list[Claim]:
    """Extract claims about file/directory counts from document content."""
    ...
```

**Input Example:**

```python
content = "There are 11 tools in tools/\nWe have 6 ADRs in docs/adrs/"
source_file = Path("docs/standards/0003-file-inventory.md")
```

**Output Example:**

```python
[
    Claim(claim_type=ClaimType.FILE_COUNT, source_file=Path("docs/standards/0003-file-inventory.md"), source_line=1, claim_text="11 tools in tools/", expected_value="11", verification_command="glob tools/*.py | count"),
    Claim(claim_type=ClaimType.FILE_COUNT, source_file=Path("docs/standards/0003-file-inventory.md"), source_line=2, claim_text="6 ADRs in docs/adrs/", expected_value="6", verification_command="glob docs/adrs/*.md | count"),
]
```

**Edge Cases:**
- Content with no numeric counts -> `[]`
- Pattern: `r"(\d+)\s+(files?|tools?|ADRs?|standards?|probes?|workflows?)\s+(?:in\s+)?[`]?([a-zA-Z0-9_/.-]+)[`]?"`

### 5.7 `extract_file_reference_claims()`

**File:** `assemblyzero/spelunking/extractors.py`

**Signature:**

```python
def extract_file_reference_claims(
    content: str,
    source_file: Path,
) -> list[Claim]:
    """Extract file path references that can be verified for existence."""
    ...
```

**Input Example:**

```python
content = "See `tools/death.py` for implementation details.\nAlso check [the config](config/settings.yaml)."
source_file = Path("README.md")
```

**Output Example:**

```python
[
    Claim(claim_type=ClaimType.FILE_EXISTS, source_file=Path("README.md"), source_line=1, claim_text="tools/death.py", expected_value="tools/death.py", verification_command="path_exists tools/death.py"),
    Claim(claim_type=ClaimType.FILE_EXISTS, source_file=Path("README.md"), source_line=2, claim_text="config/settings.yaml", expected_value="config/settings.yaml", verification_command="path_exists config/settings.yaml"),
]
```

**Edge Cases:**
- URL references (https://...) -> skipped (not file paths)
- Fragment-only references (#section) -> skipped
- Patterns: backtick paths `` `path/to/file.ext` ``, markdown links `[text](path/to/file.ext)`, bare paths with extensions

### 5.8 `extract_timestamp_claims()`

**File:** `assemblyzero/spelunking/extractors.py`

**Signature:**

```python
def extract_timestamp_claims(
    content: str,
    source_file: Path,
) -> list[Claim]:
    """Extract 'Last Updated' or date-stamped claims."""
    ...
```

**Input Example:**

```python
content = "<!-- Last Updated: 2026-01-15 -->\n# Document Title"
source_file = Path("docs/standards/0010-example.md")
```

**Output Example:**

```python
[
    Claim(claim_type=ClaimType.TIMESTAMP, source_file=Path("docs/standards/0010-example.md"), source_line=1, claim_text="Last Updated: 2026-01-15", expected_value="2026-01-15", verification_command="check_freshness 2026-01-15"),
]
```

**Edge Cases:**
- No timestamp in document -> `[]`
- Pattern: `r"[Ll]ast\s+[Uu]pdated:?\s*(\d{4}-\d{2}-\d{2})"` and `r"[Dd]ate:?\s*(\d{4}-\d{2}-\d{2})"`

### 5.9 `extract_technical_claims()`

**File:** `assemblyzero/spelunking/extractors.py`

**Signature:**

```python
def extract_technical_claims(
    content: str,
    source_file: Path,
    negation_patterns: list[str] | None = None,
) -> list[Claim]:
    """Extract technical assertions that can be grep-verified. Focuses on negation claims."""
    ...
```

**Input Example:**

```python
content = "This project uses deterministic techniques, not vector embeddings or chromadb."
source_file = Path("README.md")
negation_patterns = None
```

**Output Example:**

```python
[
    Claim(claim_type=ClaimType.TECHNICAL_FACT, source_file=Path("README.md"), source_line=1, claim_text="not vector embeddings", expected_value="vector embeddings", verification_command="grep_absent vector embeddings"),
    Claim(claim_type=ClaimType.TECHNICAL_FACT, source_file=Path("README.md"), source_line=1, claim_text="not chromadb", expected_value="chromadb", verification_command="grep_absent chromadb"),
]
```

**Edge Cases:**
- No negation claims -> `[]`
- Pattern: `r"(?:not|without|no)\s+([a-zA-Z][a-zA-Z0-9_ ]{2,})"` (minimum 3 chars for the term)
- Custom `negation_patterns` are appended to the default list

### 5.10 `verify_claim()`

**File:** `assemblyzero/spelunking/verifiers.py`

**Signature:**

```python
def verify_claim(
    claim: Claim,
    repo_root: Path,
) -> VerificationResult:
    """Verify a single claim against filesystem/codebase reality. Dispatches by claim type."""
    ...
```

**Input Example:**

```python
claim = Claim(claim_type=ClaimType.FILE_EXISTS, source_file=Path("README.md"), source_line=5, claim_text="tools/death.py", expected_value="tools/death.py", verification_command="path_exists tools/death.py")
repo_root = Path("/home/user/assemblyzero")
```

**Output Example:**

```python
VerificationResult(
    claim=claim,
    status=VerificationStatus.MATCH,
    actual_value="tools/death.py",
    evidence="File exists at tools/death.py",
)
```

**Edge Cases:**
- `ClaimType.STATUS_MARKER` -> returns `VerificationResult(status=VerificationStatus.UNVERIFIABLE)` (complex check)
- Unknown claim type -> returns `VerificationResult(status=VerificationStatus.UNVERIFIABLE)`

### 5.11 `verify_file_count()`

**File:** `assemblyzero/spelunking/verifiers.py`

**Signature:**

```python
def verify_file_count(
    directory: Path,
    expected_count: int,
    glob_pattern: str = "*.py",
) -> VerificationResult:
    """Count files matching pattern in directory and compare to expected."""
    ...
```

**Input Example:**

```python
directory = Path("/tmp/pytest-xyz/tools")
expected_count = 5
glob_pattern = "*.py"
# Directory contains: a.py, b.py, c.py, d.py, e.py
```

**Output Example:**

```python
VerificationResult(
    claim=Claim(claim_type=ClaimType.FILE_COUNT, source_file=Path(""), source_line=0, claim_text="5 files in tools/", expected_value="5", verification_command="glob tools/*.py | count"),
    status=VerificationStatus.MATCH,
    actual_value="5",
    evidence="Found 5 files matching *.py in tools/",
)
```

**Input Example (mismatch):**

```python
directory = Path("/tmp/pytest-xyz/tools")
expected_count = 5
# Directory contains: a.py, b.py, c.py, d.py, e.py, f.py, g.py, h.py
```

**Output Example (mismatch):**

```python
VerificationResult(
    claim=Claim(...),
    status=VerificationStatus.MISMATCH,
    actual_value="8",
    evidence="Found 8 files matching *.py in tools/, expected 5",
)
```

**Edge Cases:**
- Nonexistent directory -> `VerificationResult(status=VerificationStatus.ERROR, error_message="Directory not found: ...")`
- Empty directory -> actual_value="0"

### 5.12 `verify_file_exists()`

**File:** `assemblyzero/spelunking/verifiers.py`

**Signature:**

```python
def verify_file_exists(
    file_path: Path,
    repo_root: Path,
) -> VerificationResult:
    """Verify that a referenced file exists on disk. Path traversal protected."""
    ...
```

**Input Example (exists):**

```python
file_path = Path("tools/death.py")
repo_root = Path("/tmp/pytest-xyz/repo")
# /tmp/pytest-xyz/repo/tools/death.py exists
```

**Output Example (exists):**

```python
VerificationResult(
    claim=Claim(claim_type=ClaimType.FILE_EXISTS, ...),
    status=VerificationStatus.MATCH,
    actual_value="tools/death.py",
    evidence="File exists at tools/death.py",
)
```

**Input Example (path traversal):**

```python
file_path = Path("../../etc/passwd")
repo_root = Path("/tmp/pytest-xyz/repo")
```

**Output Example (path traversal):**

```python
VerificationResult(
    claim=Claim(claim_type=ClaimType.FILE_EXISTS, ...),
    status=VerificationStatus.ERROR,
    error_message="Path traversal detected: ../../etc/passwd resolves outside repo root",
)
```

**Edge Cases:**
- Nonexistent file -> `VerificationStatus.MISMATCH`
- Path traversal -> `VerificationStatus.ERROR`

### 5.13 `verify_no_contradiction()`

**File:** `assemblyzero/spelunking/verifiers.py`

**Signature:**

```python
def verify_no_contradiction(
    negated_term: str,
    repo_root: Path,
    exclude_dirs: list[str] | None = None,
) -> VerificationResult:
    """Grep codebase for presence of something claimed to be absent."""
    ...
```

**Input Example (clean):**

```python
negated_term = "chromadb"
repo_root = Path("/tmp/pytest-xyz/repo")
exclude_dirs = [".git", "__pycache__"]
# No files contain "chromadb"
```

**Output Example (clean):**

```python
VerificationResult(
    claim=Claim(claim_type=ClaimType.TECHNICAL_FACT, ...),
    status=VerificationStatus.MATCH,
    evidence="Term 'chromadb' not found in codebase",
)
```

**Input Example (contradiction):**

```python
negated_term = "chromadb"
repo_root = Path("/tmp/pytest-xyz/repo")
# File src/db.py contains "import chromadb"
```

**Output Example (contradiction):**

```python
VerificationResult(
    claim=Claim(claim_type=ClaimType.TECHNICAL_FACT, ...),
    status=VerificationStatus.MISMATCH,
    actual_value="chromadb",
    evidence="Found 'chromadb' in src/db.py:3: import chromadb",
)
```

**Edge Cases:**
- Term shorter than 3 chars -> `VerificationStatus.UNVERIFIABLE` (too likely to be a false positive)
- Default `exclude_dirs`: `[".git", "__pycache__", "node_modules", ".venv", ".mypy_cache"]`
- Max 10 matches reported in evidence to prevent report bloat

### 5.14 `verify_unique_prefix()`

**File:** `assemblyzero/spelunking/verifiers.py`

**Signature:**

```python
def verify_unique_prefix(
    directory: Path,
    prefix_pattern: str = r"^(\d{4})-",
) -> VerificationResult:
    """Verify that no two files in a directory share the same numeric prefix."""
    ...
```

**Input Example (unique):**

```python
directory = Path("/tmp/pytest-xyz/docs/adrs")
# Contains: 0201-first.md, 0202-second.md, 0203-third.md
```

**Output Example (unique):**

```python
VerificationResult(
    claim=Claim(claim_type=ClaimType.UNIQUE_ID, ...),
    status=VerificationStatus.MATCH,
    evidence="All 3 ADR prefixes are unique",
)
```

**Input Example (collision):**

```python
directory = Path("/tmp/pytest-xyz/docs/adrs")
# Contains: 0204-first.md, 0204-second.md, 0205-third.md
```

**Output Example (collision):**

```python
VerificationResult(
    claim=Claim(claim_type=ClaimType.UNIQUE_ID, ...),
    status=VerificationStatus.MISMATCH,
    actual_value="1 collision(s)",
    evidence="Prefix 0204 used by: 0204-first.md, 0204-second.md",
)
```

**Edge Cases:**
- Nonexistent directory -> `VerificationStatus.ERROR`
- Empty directory -> `VerificationStatus.MATCH` (no collisions possible)
- Files without a matching prefix -> ignored

### 5.15 `verify_timestamp_freshness()`

**File:** `assemblyzero/spelunking/verifiers.py`

**Signature:**

```python
def verify_timestamp_freshness(
    claimed_date: str,
    max_age_days: int = 30,
) -> VerificationResult:
    """Check whether a claimed date is within the freshness threshold."""
    ...
```

**Input Example (fresh):**

```python
claimed_date = "2026-02-12"  # 5 days ago from 2026-02-17
max_age_days = 30
```

**Output Example (fresh):**

```python
VerificationResult(
    claim=Claim(claim_type=ClaimType.TIMESTAMP, ...),
    status=VerificationStatus.MATCH,
    actual_value="5 days old",
    evidence="Date 2026-02-12 is 5 days old (threshold: 30 days)",
)
```

**Input Example (stale):**

```python
claimed_date = "2026-01-03"  # 45 days ago
max_age_days = 30
```

**Output Example (stale):**

```python
VerificationResult(
    claim=Claim(claim_type=ClaimType.TIMESTAMP, ...),
    status=VerificationStatus.STALE,
    actual_value="45 days old",
    evidence="Date 2026-01-03 is 45 days old (threshold: 30 days)",
)
```

**Edge Cases:**
- Unparseable date string -> `VerificationStatus.ERROR` with `error_message="Cannot parse date: ..."`
- Future date -> `VerificationStatus.MATCH` (0 days old)

### 5.16 `_is_within_repo()`

**File:** `assemblyzero/spelunking/verifiers.py`

**Signature:**

```python
def _is_within_repo(file_path: Path, repo_root: Path) -> bool:
    """Check that resolved path is within repo_root boundary."""
    ...
```

**Input Example (within):**

```python
file_path = Path("/tmp/repo/tools/death.py")
repo_root = Path("/tmp/repo")
# Returns: True
```

**Input Example (outside):**

```python
file_path = Path("/tmp/repo/../../etc/passwd").resolve()  # resolves to /etc/passwd
repo_root = Path("/tmp/repo")
# Returns: False
```

**Implementation:**

```python
def _is_within_repo(file_path: Path, repo_root: Path) -> bool:
    try:
        file_path.resolve().relative_to(repo_root.resolve())
        return True
    except ValueError:
        return False
```

### 5.17 `generate_drift_report()`

**File:** `assemblyzero/spelunking/report.py`

**Signature:**

```python
def generate_drift_report(
    report: DriftReport,
    output_format: str = "markdown",
) -> str:
    """Generate a human-readable drift report from verification results."""
    ...
```

**Input Example:**

```python
report = DriftReport(
    target_document=Path("README.md"),
    results=[
        VerificationResult(claim=Claim(claim_type=ClaimType.FILE_COUNT, source_file=Path("README.md"), source_line=5, claim_text="11 tools", expected_value="11", verification_command="glob tools/*.py | count"), status=VerificationStatus.MISMATCH, actual_value="36"),
        VerificationResult(claim=Claim(claim_type=ClaimType.FILE_EXISTS, source_file=Path("README.md"), source_line=10, claim_text="tools/death.py", expected_value="tools/death.py", verification_command="path_exists"), status=VerificationStatus.MATCH, actual_value="tools/death.py"),
    ],
)
output_format = "markdown"
```

**Output Example (markdown):**

```
# Spelunking Drift Report

**Target:** README.md
**Generated:** 2026-02-17T10:30:00
**Drift Score:** [FAIL] 50.0%

## Summary

| Metric | Value |
|--------|-------|
| Total Claims | 2 |
| Matching | 1 |
| Mismatches | 1 |
| Stale | 0 |
| Errors | 0 |

## Claim Details

| Source | Line | Claim | Status | Expected | Actual | Evidence |
|--------|------|-------|--------|----------|--------|----------|
| README.md | 5 | 11 tools | MISMATCH | 11 | 36 |  |
| README.md | 10 | tools/death.py | MATCH | tools/death.py | tools/death.py |  |
```

**Input Example (json):**

```python
output_format = "json"
```

**Output Example (json):**

```json
{
    "target_document": "README.md",
    "generated_at": "2026-02-17T10:30:00",
    "drift_score": 50.0,
    "total_claims": 2,
    "matching_claims": 1,
    "results": [
        {
            "claim_type": "file_count",
            "source_file": "README.md",
            "source_line": 5,
            "claim_text": "11 tools",
            "status": "mismatch",
            "expected_value": "11",
            "actual_value": "36",
            "evidence": ""
        }
    ]
}
```

**Edge Cases:**
- `output_format="xml"` -> raises `ValueError("Unsupported output format: xml. Use 'markdown' or 'json'.")`
- Empty results list -> produces report with "No claims found" and drift score 100.0

### 5.18 `generate_probe_summary()`

**File:** `assemblyzero/spelunking/report.py`

**Signature:**

```python
def generate_probe_summary(
    probe_results: list[ProbeResult],
) -> str:
    """Generate a summary of all probe results in Markdown table format."""
    ...
```

**Input Example:**

```python
probe_results = [
    ProbeResult(probe_name="inventory_drift", findings=[], passed=True, summary="No drift", execution_time_ms=45.2),
    ProbeResult(probe_name="dead_references", findings=[...], passed=False, summary="3 dead refs", execution_time_ms=123.4),
    ProbeResult(probe_name="adr_collision", findings=[], passed=True, summary="No collisions", execution_time_ms=12.1),
]
```

**Output Example:**

```
# Probe Summary

| Probe | Status | Findings | Time (ms) |
|-------|--------|----------|-----------|
| inventory_drift | [PASS] | 0 | 45.2 |
| dead_references | [FAIL] | 3 | 123.4 |
| adr_collision | [PASS] | 0 | 12.1 |
| **Totals** | **2 passed, 1 failed** | **3** | **180.7** |
```

**Edge Cases:**
- Empty list -> returns header with empty table body and "0 passed, 0 failed" totals row

### 5.19 `_format_verification_row()`

**File:** `assemblyzero/spelunking/report.py`

**Signature:**

```python
def _format_verification_row(result: VerificationResult) -> str:
    """Format a single VerificationResult as a Markdown table row."""
    ...
```

**Input Example:**

```python
result = VerificationResult(
    claim=Claim(claim_type=ClaimType.FILE_COUNT, source_file=Path("README.md"), source_line=5, claim_text="11 tools in tools/ directory for processing", expected_value="11", verification_command="glob tools/*.py | count"),
    status=VerificationStatus.MISMATCH,
    actual_value="36",
    evidence="Found 36 .py files in tools/ — significantly more than the claimed 11 files documented in the README",
)
```

**Output Example:**

```
| README.md | 5 | 11 tools in tools/ directory for processin... | MISMATCH | 11 | 36 | Found 36 .py files in tools/ — significantly more than the claimed 11 files documented in the R... |
```

**Edge Cases:**
- Claim text > 50 chars -> truncated with `...`
- Evidence > 100 chars -> truncated with `...`
- `None` actual_value -> displays as `-`

### 5.20 `_format_drift_score_badge()`

**File:** `assemblyzero/spelunking/report.py`

**Signature:**

```python
def _format_drift_score_badge(score: float) -> str:
    """Format drift score with pass/fail indicator."""
    ...
```

**Input Example:**

```python
score = 95.0
```

**Output Example:**

```python
"[PASS] 95.0%"
```

**Input Example (fail):**

```python
score = 75.0
```

**Output Example (fail):**

```python
"[FAIL] 75.0%"
```

**Edge Cases:**
- Exactly 90.0 -> `"[PASS] 90.0%"` (threshold is >=90)

### 5.21 `probe_inventory_drift()`

**File:** `assemblyzero/workflows/janitor/probes/inventory_drift.py`

**Signature:**

```python
def probe_inventory_drift(
    repo_root: Path,
    inventory_path: Path | None = None,
) -> ProbeResult:
    """Count files in key directories and compare to 0003-file-inventory.md."""
    ...
```

**Input Example (drift):**

```python
repo_root = Path("/tmp/pytest-xyz/repo")
inventory_path = Path("/tmp/pytest-xyz/repo/mock_inventory.md")
# mock_inventory.md says "5 tools in tools/"
# repo has tools/a.py, tools/b.py, ..., tools/h.py (8 files)
```

**Output Example (drift):**

```python
ProbeResult(
    probe_name="inventory_drift",
    findings=[VerificationResult(claim=..., status=VerificationStatus.MISMATCH, actual_value="8", evidence="Found 8 files matching *.py in tools/, expected 5")],
    passed=False,
    summary="1 inventory mismatch: tools/ claims 5, actual 8",
    execution_time_ms=23.4,
)
```

**Input Example (match):**

```python
# mock_inventory.md says "3 tools in tools/"
# repo has tools/a.py, tools/b.py, tools/c.py (3 files)
```

**Output Example (match):**

```python
ProbeResult(
    probe_name="inventory_drift",
    findings=[],
    passed=True,
    summary="No inventory drift detected",
    execution_time_ms=18.7,
)
```

**Edge Cases:**
- Missing inventory file -> `ProbeResult(passed=True, summary="Inventory file not found, skipping")` with empty findings
- Inventory file has no parseable count claims -> `passed=True`

### 5.22 `probe_dead_references()`

**File:** `assemblyzero/workflows/janitor/probes/dead_references.py`

**Signature:**

```python
def probe_dead_references(
    repo_root: Path,
    doc_dirs: list[Path] | None = None,
) -> ProbeResult:
    """Grep all Markdown files for file path references and verify each exists."""
    ...
```

**Input Example (dead ref):**

```python
repo_root = Path("/tmp/pytest-xyz/repo")
# docs/guide.md contains: "See `tools/ghost.py` for details"
# tools/ghost.py does NOT exist
```

**Output Example (dead ref):**

```python
ProbeResult(
    probe_name="dead_references",
    findings=[VerificationResult(claim=Claim(claim_type=ClaimType.FILE_EXISTS, ..., claim_text="tools/ghost.py"), status=VerificationStatus.MISMATCH)],
    passed=False,
    summary="1 dead reference found: tools/ghost.py referenced in docs/guide.md",
    execution_time_ms=67.3,
)
```

**Edge Cases:**
- No markdown files -> `passed=True`, empty findings
- All references valid -> `passed=True`

### 5.23 `probe_adr_collision()`

**File:** `assemblyzero/workflows/janitor/probes/adr_collision.py`

**Signature:**

```python
def probe_adr_collision(
    repo_root: Path,
    adr_dir: Path | None = None,
) -> ProbeResult:
    """Scan docs/adrs/ for duplicate numeric prefixes."""
    ...
```

**Input Example (collision):**

```python
repo_root = Path("/tmp/pytest-xyz/repo")
# docs/adrs/ contains: 0204-first.md, 0204-second.md, 0205-third.md
```

**Output Example (collision):**

```python
ProbeResult(
    probe_name="adr_collision",
    findings=[VerificationResult(claim=..., status=VerificationStatus.MISMATCH, evidence="Prefix 0204 used by: 0204-first.md, 0204-second.md")],
    passed=False,
    summary="1 ADR prefix collision: 0204",
    execution_time_ms=8.9,
)
```

**Edge Cases:**
- Missing adr_dir -> `passed=True`, summary notes directory not found
- All unique prefixes -> `passed=True`

### 5.24 `probe_stale_timestamps()`

**File:** `assemblyzero/workflows/janitor/probes/stale_timestamps.py`

**Signature:**

```python
def probe_stale_timestamps(
    repo_root: Path,
    max_age_days: int = 30,
    doc_dirs: list[Path] | None = None,
) -> ProbeResult:
    """Flag documents with 'Last Updated' more than max_age_days old. Reports missing timestamps."""
    ...
```

**Input Example (stale + missing):**

```python
repo_root = Path("/tmp/pytest-xyz/repo")
max_age_days = 30
# docs/old.md: "Last Updated: 2026-01-03" (45 days old)
# docs/fresh.md: "Last Updated: 2026-02-12" (5 days old)
# docs/missing.md: No "Last Updated" field at all
```

**Output Example (stale + missing):**

```python
ProbeResult(
    probe_name="stale_timestamps",
    findings=[
        VerificationResult(claim=Claim(claim_type=ClaimType.TIMESTAMP, source_file=Path("docs/old.md"), ...), status=VerificationStatus.STALE, actual_value="45 days old"),
        VerificationResult(claim=Claim(claim_type=ClaimType.TIMESTAMP, source_file=Path("docs/missing.md"), ..., claim_text="missing timestamp"), status=VerificationStatus.MISMATCH, evidence="No 'Last Updated' timestamp found"),
    ],
    passed=False,
    summary="1 stale document, 1 missing timestamp",
    execution_time_ms=34.5,
)
```

**Edge Cases:**
- All fresh -> `passed=True`
- Only missing timestamps, no stale -> `passed=False` (missing timestamps are findings)
- No markdown files -> `passed=True`

### 5.25 `probe_readme_claims()`

**File:** `assemblyzero/workflows/janitor/probes/readme_claims.py`

**Signature:**

```python
def probe_readme_claims(
    repo_root: Path,
    readme_path: Path | None = None,
) -> ProbeResult:
    """Extract technical claims from README and verify against codebase."""
    ...
```

**Input Example (contradiction):**

```python
repo_root = Path("/tmp/pytest-xyz/repo")
# README.md says "not chromadb"
# src/db.py contains "import chromadb"
```

**Output Example (contradiction):**

```python
ProbeResult(
    probe_name="readme_claims",
    findings=[VerificationResult(claim=Claim(claim_type=ClaimType.TECHNICAL_FACT, ..., claim_text="not chromadb"), status=VerificationStatus.MISMATCH, evidence="Found 'chromadb' in src/db.py:1: import chromadb")],
    passed=False,
    summary="1 README contradiction: 'chromadb' found despite negation claim",
    execution_time_ms=89.2,
)
```

**Edge Cases:**
- No README -> `passed=True`, summary notes README not found
- No negation claims -> `passed=True`
- Claims all verified -> `passed=True`

### 5.26 `probe_persona_status()`

**File:** `assemblyzero/workflows/janitor/probes/persona_status.py`

**Signature:**

```python
def probe_persona_status(
    repo_root: Path,
    persona_file: Path | None = None,
) -> ProbeResult:
    """Cross-reference Dramatis-Personae.md implementation markers against code."""
    ...
```

**Input Example (gaps):**

```python
repo_root = Path("/tmp/pytest-xyz/repo")
# mock_personas.md has 5 personas: 3 have "Status: implemented", 2 have no status
```

**Output Example (gaps):**

```python
ProbeResult(
    probe_name="persona_status",
    findings=[
        VerificationResult(claim=Claim(claim_type=ClaimType.STATUS_MARKER, ..., claim_text="Persona 'Architect' missing status"), status=VerificationStatus.MISMATCH),
        VerificationResult(claim=Claim(claim_type=ClaimType.STATUS_MARKER, ..., claim_text="Persona 'Tester' missing status"), status=VerificationStatus.MISMATCH),
    ],
    passed=False,
    summary="2 of 5 personas missing status markers",
    execution_time_ms=15.6,
)
```

**Edge Cases:**
- Missing persona file -> `passed=True`, summary notes file not found
- All personas have status -> `passed=True`

### 5.27 `test_T360_no_external_imports()`

**File:** `tests/unit/test_spelunking/test_dependencies.py`

**Signature:**

```python
def test_T360_no_external_imports() -> None:
    """Verify all imports in spelunking package resolve to stdlib or internal modules."""
    ...
```

**Input Example:**

```python
# The function takes no arguments. It scans these files at runtime:
# assemblyzero/spelunking/__init__.py
# assemblyzero/spelunking/models.py
# assemblyzero/spelunking/extractors.py
# assemblyzero/spelunking/verifiers.py
# assemblyzero/spelunking/report.py
# assemblyzero/spelunking/engine.py
# assemblyzero/workflows/janitor/probes/inventory_drift.py
# assemblyzero/workflows/janitor/probes/dead_references.py
# assemblyzero/workflows/janitor/probes/adr_collision.py
# assemblyzero/workflows/janitor/probes/stale_timestamps.py
# assemblyzero/workflows/janitor/probes/readme_claims.py
# assemblyzero/workflows/janitor/probes/persona_status.py
```

**Output Example:**

```python
# On success: test passes (no assertion errors)
# On failure: AssertionError("Third-party import found: 'chromadb' in assemblyzero/spelunking/engine.py")
```

**Implementation approach:**

```python
import ast
import sys
from pathlib import Path

STDLIB_MODULES = set(sys.stdlib_module_names)  # Python 3.10+
INTERNAL_PREFIXES = ("assemblyzero",)

def test_T360_no_external_imports() -> None:
    """Verify all imports in spelunking package resolve to stdlib or internal modules."""
    repo_root = Path(__file__).resolve().parents[3]  # tests/unit/test_spelunking -> repo root
    spelunking_files = list((repo_root / "assemblyzero" / "spelunking").glob("*.py"))
    probe_files = [
        repo_root / "assemblyzero" / "workflows" / "janitor" / "probes" / name
        for name in [
            "inventory_drift.py", "dead_references.py", "adr_collision.py",
            "stale_timestamps.py", "readme_claims.py", "persona_status.py",
        ]
    ]
    all_files = spelunking_files + [f for f in probe_files if f.exists()]

    third_party = []
    for file_path in all_files:
        tree = ast.parse(file_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top not in STDLIB_MODULES and not any(alias.name.startswith(p) for p in INTERNAL_PREFIXES):
                        third_party.append(f"'{alias.name}' in {file_path.relative_to(repo_root)}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top not in STDLIB_MODULES and not any(node.module.startswith(p) for p in INTERNAL_PREFIXES):
                    third_party.append(f"'{node.module}' in {file_path.relative_to(repo_root)}")

    assert not third_party, f"Third-party imports found: {', '.join(third_party)}"
```

**Edge Cases:**
- `__future__` imports -> allowed (part of stdlib)
- Relative imports within assemblyzero -> allowed (internal)
- `pytest` in test files -> this test only scans source files, not test files


## 6. Change Instructions

### 6.1 `assemblyzero/spelunking/__init__.py` (Add)

**Complete file contents:**

```python
"""Spelunking engine package — deep verification that documentation matches reality.

Issue #534: Spelunking Audits
"""

from __future__ import annotations
```

### 6.2 `assemblyzero/spelunking/models.py` (Add)

**Complete file contents:**

```python
"""Data models for the spelunking audit system.

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
        """Percentage of verifiable claims that match reality. Target: >90%."""
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

### 6.3 `assemblyzero/spelunking/extractors.py` (Add)

**Complete file contents:**

```python
"""Claim extractors — parse Markdown documents to identify verifiable factual claims.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import re
from pathlib import Path

from assemblyzero.spelunking.models import Claim, ClaimType


# Compiled regex patterns for claim extraction
_FILE_COUNT_PATTERN = re.compile(
    r"(\d+)\s+(files?|tools?|ADRs?|standards?|probes?|workflows?)"
    r"(?:\s+in\s+)?[`\s]*([a-zA-Z0-9_/.:-]+/?)[`]?",
    re.IGNORECASE,
)

_FILE_REF_BACKTICK_PATTERN = re.compile(
    r"`([a-zA-Z0-9_/.:-]+\.[a-zA-Z0-9]+)`"
)

_FILE_REF_LINK_PATTERN = re.compile(
    r"\[(?:[^\]]*)\]\(([a-zA-Z0-9_/.:-]+\.[a-zA-Z0-9]+)\)"
)

_TIMESTAMP_PATTERN = re.compile(
    r"[Ll]ast\s+[Uu]pdated:?\s*(\d{4}-\d{2}-\d{2})"
)

_DATE_PATTERN = re.compile(
    r"[Dd]ate:?\s*(\d{4}-\d{2}-\d{2})"
)

_NEGATION_PATTERN = re.compile(
    r"(?:not|without|no)\s+([a-zA-Z][a-zA-Z0-9_ ]{2,})",
    re.IGNORECASE,
)


def extract_claims_from_markdown(
    file_path: Path,
    claim_types: list[ClaimType] | None = None,
) -> list[Claim]:
    """Parse a Markdown file and extract verifiable factual claims."""
    if not file_path.exists():
        return []

    content = file_path.read_text(encoding="utf-8")
    claims: list[Claim] = []

    extractors = {
        ClaimType.FILE_COUNT: extract_file_count_claims,
        ClaimType.FILE_EXISTS: extract_file_reference_claims,
        ClaimType.TIMESTAMP: extract_timestamp_claims,
        ClaimType.TECHNICAL_FACT: extract_technical_claims,
    }

    active_types = claim_types if claim_types else list(extractors.keys())

    for claim_type in active_types:
        if claim_type in extractors:
            claims.extend(extractors[claim_type](content, file_path))

    return claims


def extract_file_count_claims(
    content: str,
    source_file: Path,
) -> list[Claim]:
    """Extract claims about file/directory counts from document content."""
    claims: list[Claim] = []
    for line_num, line in enumerate(content.splitlines(), start=1):
        for match in _FILE_COUNT_PATTERN.finditer(line):
            count_str = match.group(1)
            item_type = match.group(2)
            directory = match.group(3).rstrip("/")
            claim_text = match.group(0).strip()

            # Determine glob pattern based on item type
            item_lower = item_type.lower().rstrip("s")
            if item_lower in ("adr",):
                glob_pat = "*.md"
            else:
                glob_pat = "*.py"

            claims.append(
                Claim(
                    claim_type=ClaimType.FILE_COUNT,
                    source_file=source_file,
                    source_line=line_num,
                    claim_text=claim_text,
                    expected_value=count_str,
                    verification_command=f"glob {directory}/{glob_pat} | count",
                )
            )
    return claims


def extract_file_reference_claims(
    content: str,
    source_file: Path,
) -> list[Claim]:
    """Extract file path references that can be verified for existence."""
    claims: list[Claim] = []
    seen_paths: set[str] = set()

    for line_num, line in enumerate(content.splitlines(), start=1):
        # Backtick references
        for match in _FILE_REF_BACKTICK_PATTERN.finditer(line):
            path_str = match.group(1)
            if path_str not in seen_paths and not path_str.startswith(("http://", "https://")):
                seen_paths.add(path_str)
                claims.append(
                    Claim(
                        claim_type=ClaimType.FILE_EXISTS,
                        source_file=source_file,
                        source_line=line_num,
                        claim_text=path_str,
                        expected_value=path_str,
                        verification_command=f"path_exists {path_str}",
                    )
                )

        # Markdown link references
        for match in _FILE_REF_LINK_PATTERN.finditer(line):
            path_str = match.group(1)
            if path_str not in seen_paths and not path_str.startswith(("http://", "https://", "#")):
                seen_paths.add(path_str)
                claims.append(
                    Claim(
                        claim_type=ClaimType.FILE_EXISTS,
                        source_file=source_file,
                        source_line=line_num,
                        claim_text=path_str,
                        expected_value=path_str,
                        verification_command=f"path_exists {path_str}",
                    )
                )
    return claims


def extract_timestamp_claims(
    content: str,
    source_file: Path,
) -> list[Claim]:
    """Extract 'Last Updated' or date-stamped claims."""
    claims: list[Claim] = []
    for line_num, line in enumerate(content.splitlines(), start=1):
        for pattern in (_TIMESTAMP_PATTERN, _DATE_PATTERN):
            match = pattern.search(line)
            if match:
                date_str = match.group(1)
                claims.append(
                    Claim(
                        claim_type=ClaimType.TIMESTAMP,
                        source_file=source_file,
                        source_line=line_num,
                        claim_text=match.group(0).strip(),
                        expected_value=date_str,
                        verification_command=f"check_freshness {date_str}",
                    )
                )
    return claims


def extract_technical_claims(
    content: str,
    source_file: Path,
    negation_patterns: list[str] | None = None,
) -> list[Claim]:
    """Extract technical assertions that can be grep-verified. Focuses on negations."""
    claims: list[Claim] = []
    patterns = [_NEGATION_PATTERN]

    if negation_patterns:
        for pat in negation_patterns:
            patterns.append(re.compile(pat, re.IGNORECASE))

    seen_terms: set[str] = set()

    for line_num, line in enumerate(content.splitlines(), start=1):
        for pattern in patterns:
            for match in pattern.finditer(line):
                term = match.group(1).strip().lower()
                if len(term) >= 3 and term not in seen_terms:
                    seen_terms.add(term)
                    claims.append(
                        Claim(
                            claim_type=ClaimType.TECHNICAL_FACT,
                            source_file=source_file,
                            source_line=line_num,
                            claim_text=match.group(0).strip(),
                            expected_value=term,
                            verification_command=f"grep_absent {term}",
                        )
                    )
    return claims
```

### 6.4 `assemblyzero/spelunking/verifiers.py` (Add)

**Complete file contents:**

```python
"""Verification strategies — check claims against filesystem/codebase reality.

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


_DEFAULT_EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", ".venv", ".mypy_cache", ".tox", ".pytest_cache"}
_MAX_GREP_MATCHES = 10
_MIN_SEARCH_TERM_LENGTH = 3


def verify_claim(
    claim: Claim,
    repo_root: Path,
) -> VerificationResult:
    """Verify a single claim against filesystem/codebase reality."""
    dispatch = {
        ClaimType.FILE_COUNT: _verify_file_count_claim,
        ClaimType.FILE_EXISTS: _verify_file_exists_claim,
        ClaimType.TECHNICAL_FACT: _verify_technical_claim,
        ClaimType.UNIQUE_ID: _verify_unique_id_claim,
        ClaimType.TIMESTAMP: _verify_timestamp_claim,
    }

    handler = dispatch.get(claim.claim_type)
    if handler is None:
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.UNVERIFIABLE,
            evidence=f"No verification strategy for claim type: {claim.claim_type.value}",
        )

    try:
        return handler(claim, repo_root)
    except Exception as exc:
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.ERROR,
            error_message=str(exc),
        )


def _verify_file_count_claim(claim: Claim, repo_root: Path) -> VerificationResult:
    """Dispatch for FILE_COUNT claims."""
    # Parse verification_command: "glob dir/pattern | count"
    parts = claim.verification_command.replace(" | count", "").replace("glob ", "")
    directory = repo_root / Path(parts).parent
    glob_pattern = Path(parts).name
    expected = int(claim.expected_value)
    return verify_file_count(directory, expected, glob_pattern, claim)


def _verify_file_exists_claim(claim: Claim, repo_root: Path) -> VerificationResult:
    """Dispatch for FILE_EXISTS claims."""
    file_path = Path(claim.expected_value)
    return verify_file_exists(file_path, repo_root, claim)


def _verify_technical_claim(claim: Claim, repo_root: Path) -> VerificationResult:
    """Dispatch for TECHNICAL_FACT claims."""
    return verify_no_contradiction(claim.expected_value, repo_root, claim=claim)


def _verify_unique_id_claim(claim: Claim, repo_root: Path) -> VerificationResult:
    """Dispatch for UNIQUE_ID claims."""
    directory = repo_root / Path(claim.expected_value)
    return verify_unique_prefix(directory, claim=claim)


def _verify_timestamp_claim(claim: Claim, repo_root: Path) -> VerificationResult:
    """Dispatch for TIMESTAMP claims."""
    return verify_timestamp_freshness(claim.expected_value, claim=claim)


def verify_file_count(
    directory: Path,
    expected_count: int,
    glob_pattern: str = "*.py",
    claim: Optional[Claim] = None,
) -> VerificationResult:
    """Count files matching pattern in directory and compare to expected."""
    if claim is None:
        claim = Claim(
            claim_type=ClaimType.FILE_COUNT,
            source_file=Path(""),
            source_line=0,
            claim_text=f"{expected_count} files in {directory.name}/",
            expected_value=str(expected_count),
            verification_command=f"glob {directory}/{glob_pattern} | count",
        )

    if not directory.exists():
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.ERROR,
            error_message=f"Directory not found: {directory}",
        )

    actual_files = list(directory.glob(glob_pattern))
    actual_count = len(actual_files)

    if actual_count == expected_count:
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.MATCH,
            actual_value=str(actual_count),
            evidence=f"Found {actual_count} files matching {glob_pattern} in {directory.name}/",
        )

    return VerificationResult(
        claim=claim,
        status=VerificationStatus.MISMATCH,
        actual_value=str(actual_count),
        evidence=f"Found {actual_count} files matching {glob_pattern} in {directory.name}/, expected {expected_count}",
    )


def verify_file_exists(
    file_path: Path,
    repo_root: Path,
    claim: Optional[Claim] = None,
) -> VerificationResult:
    """Verify that a referenced file actually exists on disk. Path traversal protected."""
    if claim is None:
        claim = Claim(
            claim_type=ClaimType.FILE_EXISTS,
            source_file=Path(""),
            source_line=0,
            claim_text=str(file_path),
            expected_value=str(file_path),
            verification_command=f"path_exists {file_path}",
        )

    resolved = (repo_root / file_path).resolve()

    if not _is_within_repo(resolved, repo_root):
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.ERROR,
            error_message=f"Path traversal detected: {file_path} resolves outside repo root",
        )

    if resolved.exists():
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.MATCH,
            actual_value=str(file_path),
            evidence=f"File exists at {file_path}",
        )

    return VerificationResult(
        claim=claim,
        status=VerificationStatus.MISMATCH,
        evidence=f"File not found: {file_path}",
    )


def verify_no_contradiction(
    negated_term: str,
    repo_root: Path,
    exclude_dirs: list[str] | None = None,
    claim: Optional[Claim] = None,
) -> VerificationResult:
    """Grep codebase for presence of something claimed to be absent."""
    if claim is None:
        claim = Claim(
            claim_type=ClaimType.TECHNICAL_FACT,
            source_file=Path(""),
            source_line=0,
            claim_text=f"not {negated_term}",
            expected_value=negated_term,
            verification_command=f"grep_absent {negated_term}",
        )

    if len(negated_term) < _MIN_SEARCH_TERM_LENGTH:
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.UNVERIFIABLE,
            evidence=f"Search term '{negated_term}' too short (min {_MIN_SEARCH_TERM_LENGTH} chars)",
        )

    excluded = set(exclude_dirs) if exclude_dirs else _DEFAULT_EXCLUDE_DIRS
    matches: list[str] = []

    for py_file in repo_root.rglob("*.py"):
        # Check if file is in an excluded directory
        if any(part in excluded for part in py_file.parts):
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for line_num, line in enumerate(content.splitlines(), start=1):
            if re.search(re.escape(negated_term), line, re.IGNORECASE):
                rel_path = py_file.relative_to(repo_root)
                truncated_line = line.strip()[:100]
                matches.append(f"{rel_path}:{line_num}: {truncated_line}")
                if len(matches) >= _MAX_GREP_MATCHES:
                    break
        if len(matches) >= _MAX_GREP_MATCHES:
            break

    if not matches:
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.MATCH,
            evidence=f"Term '{negated_term}' not found in codebase",
        )

    return VerificationResult(
        claim=claim,
        status=VerificationStatus.MISMATCH,
        actual_value=negated_term,
        evidence=f"Found '{negated_term}' in {matches[0]}"
        + (f" (+{len(matches) - 1} more)" if len(matches) > 1 else ""),
    )


def verify_unique_prefix(
    directory: Path,
    prefix_pattern: str = r"^(\d{4})-",
    claim: Optional[Claim] = None,
) -> VerificationResult:
    """Verify that no two files in a directory share the same numeric prefix."""
    if claim is None:
        claim = Claim(
            claim_type=ClaimType.UNIQUE_ID,
            source_file=Path(""),
            source_line=0,
            claim_text=f"Unique prefixes in {directory.name}/",
            expected_value=str(directory),
            verification_command=f"check_unique_prefix {directory}",
        )

    if not directory.exists():
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.ERROR,
            error_message=f"Directory not found: {directory}",
        )

    prefix_map: dict[str, list[str]] = {}
    compiled_pattern = re.compile(prefix_pattern)

    for file_path in sorted(directory.iterdir()):
        if file_path.is_file():
            match = compiled_pattern.match(file_path.name)
            if match:
                prefix = match.group(1)
                prefix_map.setdefault(prefix, []).append(file_path.name)

    collisions = {
        prefix: files for prefix, files in prefix_map.items() if len(files) > 1
    }

    if not collisions:
        total = sum(len(files) for files in prefix_map.values())
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.MATCH,
            evidence=f"All {total} prefixes are unique",
        )

    collision_details = []
    for prefix, files in sorted(collisions.items()):
        collision_details.append(f"Prefix {prefix} used by: {', '.join(files)}")

    return VerificationResult(
        claim=claim,
        status=VerificationStatus.MISMATCH,
        actual_value=f"{len(collisions)} collision(s)",
        evidence="; ".join(collision_details),
    )


def verify_timestamp_freshness(
    claimed_date: str,
    max_age_days: int = 30,
    claim: Optional[Claim] = None,
) -> VerificationResult:
    """Check whether a claimed date is within the freshness threshold."""
    if claim is None:
        claim = Claim(
            claim_type=ClaimType.TIMESTAMP,
            source_file=Path(""),
            source_line=0,
            claim_text=f"Date: {claimed_date}",
            expected_value=claimed_date,
            verification_command=f"check_freshness {claimed_date}",
        )

    try:
        parsed_date = datetime.strptime(claimed_date, "%Y-%m-%d").date()
    except ValueError:
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.ERROR,
            error_message=f"Cannot parse date: {claimed_date}",
        )

    age_days = (date.today() - parsed_date).days
    if age_days < 0:
        age_days = 0

    if age_days <= max_age_days:
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.MATCH,
            actual_value=f"{age_days} days old",
            evidence=f"Date {claimed_date} is {age_days} days old (threshold: {max_age_days} days)",
        )

    return VerificationResult(
        claim=claim,
        status=VerificationStatus.STALE,
        actual_value=f"{age_days} days old",
        evidence=f"Date {claimed_date} is {age_days} days old (threshold: {max_age_days} days)",
    )


def _is_within_repo(file_path: Path, repo_root: Path) -> bool:
    """Check that resolved path is within repo_root boundary."""
    try:
        file_path.resolve().relative_to(repo_root.resolve())
        return True
    except ValueError:
        return False
```

### 6.5 `assemblyzero/spelunking/report.py` (Add)

**Complete file contents:**

```python
"""Report generator — produces Markdown and JSON drift reports.

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


_DRIFT_PASS_THRESHOLD = 90.0
_CLAIM_TEXT_MAX_LEN = 50
_EVIDENCE_MAX_LEN = 100


def generate_drift_report(
    report: DriftReport,
    output_format: str = "markdown",
) -> str:
    """Generate a human-readable drift report from verification results."""
    if output_format == "markdown":
        return _generate_markdown_report(report)
    elif output_format == "json":
        return _generate_json_report(report)
    else:
        raise ValueError(
            f"Unsupported output format: {output_format}. Use 'markdown' or 'json'."
        )


def _generate_markdown_report(report: DriftReport) -> str:
    """Generate Markdown formatted drift report."""
    lines: list[str] = []

    # Header
    lines.append("# Spelunking Drift Report")
    lines.append("")
    lines.append(f"**Target:** {report.target_document}")
    lines.append(f"**Generated:** {report.generated_at.isoformat()}")
    lines.append(f"**Drift Score:** {_format_drift_score_badge(report.drift_score)}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
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

    lines.append(f"| Mismatches | {mismatch_count} |")
    lines.append(f"| Stale | {stale_count} |")
    lines.append(f"| Errors | {error_count} |")
    lines.append("")

    # Detail table
    if report.results:
        lines.append("## Claim Details")
        lines.append("")
        lines.append("| Source | Line | Claim | Status | Expected | Actual | Evidence |")
        lines.append("|--------|------|-------|--------|----------|--------|----------|")
        for result in report.results:
            lines.append(_format_verification_row(result))
        lines.append("")

    return "\n".join(lines)


def _generate_json_report(report: DriftReport) -> str:
    """Generate JSON formatted drift report."""
    data = {
        "target_document": str(report.target_document),
        "generated_at": report.generated_at.isoformat(),
        "drift_score": report.drift_score,
        "total_claims": report.total_claims,
        "matching_claims": report.matching_claims,
        "results": [
            {
                "claim_type": r.claim.claim_type.value,
                "source_file": str(r.claim.source_file),
                "source_line": r.claim.source_line,
                "claim_text": r.claim.claim_text,
                "status": r.status.value,
                "expected_value": r.claim.expected_value,
                "actual_value": r.actual_value,
                "evidence": r.evidence,
                "error_message": r.error_message,
            }
            for r in report.results
        ],
    }
    return json.dumps(data, indent=2)


def generate_probe_summary(
    probe_results: list[ProbeResult],
) -> str:
    """Generate a summary of all probe results in Markdown table format."""
    lines: list[str] = []

    lines.append("# Probe Summary")
    lines.append("")
    lines.append("| Probe | Status | Findings | Time (ms) |")
    lines.append("|-------|--------|----------|-----------|")

    total_findings = 0
    total_time = 0.0
    passed_count = 0
    failed_count = 0

    for result in probe_results:
        status_badge = "[PASS]" if result.passed else "[FAIL]"
        finding_count = len(result.findings)
        total_findings += finding_count
        total_time += result.execution_time_ms

        if result.passed:
            passed_count += 1
        else:
            failed_count += 1

        lines.append(
            f"| {result.probe_name} | {status_badge} | {finding_count} | {result.execution_time_ms} |"
        )

    # Totals row
    lines.append(
        f"| **Totals** | **{passed_count} passed, {failed_count} failed** "
        f"| **{total_findings}** | **{round(total_time, 1)}** |"
    )
    lines.append("")

    return "\n".join(lines)


def _format_verification_row(result: VerificationResult) -> str:
    """Format a single VerificationResult as a Markdown table row."""
    source = str(result.claim.source_file)
    line = str(result.claim.source_line)
    claim_text = result.claim.claim_text
    if len(claim_text) > _CLAIM_TEXT_MAX_LEN:
        claim_text = claim_text[: _CLAIM_TEXT_MAX_LEN - 3] + "..."
    status = result.status.value.upper()
    expected = result.claim.expected_value
    actual = result.actual_value if result.actual_value is not None else "-"
    evidence = result.evidence
    if len(evidence) > _EVIDENCE_MAX_LEN:
        evidence = evidence[: _EVIDENCE_MAX_LEN - 3] + "..."

    return f"| {source} | {line} | {claim_text} | {status} | {expected} | {actual} | {evidence} |"


def _format_drift_score_badge(score: float) -> str:
    """Format drift score with pass/fail indicator."""
    if score >= _DRIFT_PASS_THRESHOLD:
        return f"[PASS] {score}%"
    return f"[FAIL] {score}%"
```

### 6.6 `assemblyzero/spelunking/engine.py` (Add)

**Complete file contents:**

```python
"""Core spelunking engine — orchestrates claim extraction, verification, and probe execution.

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
    VerificationStatus,
)
from assemblyzero.spelunking.verifiers import verify_claim


def run_spelunking(
    target_document: Path,
    repo_root: Path,
    checkpoints: list[SpelunkingCheckpoint] | None = None,
) -> DriftReport:
    """Run full spelunking analysis on a target document."""
    if checkpoints:
        claims = _checkpoints_to_claims(checkpoints)
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


def _checkpoints_to_claims(
    checkpoints: list[SpelunkingCheckpoint],
) -> list[Claim]:
    """Convert SpelunkingCheckpoints to Claim objects."""
    claims: list[Claim] = []
    for cp in checkpoints:
        # Determine claim type from verify_command
        if "glob" in cp.verify_command and "count" in cp.verify_command:
            claim_type = ClaimType.FILE_COUNT
        elif "path_exists" in cp.verify_command:
            claim_type = ClaimType.FILE_EXISTS
        elif "grep_absent" in cp.verify_command:
            claim_type = ClaimType.TECHNICAL_FACT
        elif "check_freshness" in cp.verify_command:
            claim_type = ClaimType.TIMESTAMP
        elif "check_unique_prefix" in cp.verify_command:
            claim_type = ClaimType.UNIQUE_ID
        else:
            claim_type = ClaimType.STATUS_MARKER

        # Extract expected value from verify_command
        parts = cp.verify_command.split()
        expected = parts[-1] if len(parts) > 1 else cp.claim

        claims.append(
            Claim(
                claim_type=claim_type,
                source_file=Path(cp.source_file),
                source_line=0,
                claim_text=cp.claim,
                expected_value=expected,
                verification_command=cp.verify_command,
            )
        )
    return claims


def _get_probe_registry() -> dict[str, Callable[[Path], ProbeResult]]:
    """Return mapping of probe names to their functions. Lazy imports."""
    from assemblyzero.workflows.janitor.probes.inventory_drift import (
        probe_inventory_drift,
    )
    from assemblyzero.workflows.janitor.probes.dead_references import (
        probe_dead_references,
    )
    from assemblyzero.workflows.janitor.probes.adr_collision import (
        probe_adr_collision,
    )
    from assemblyzero.workflows.janitor.probes.stale_timestamps import (
        probe_stale_timestamps,
    )
    from assemblyzero.workflows.janitor.probes.readme_claims import (
        probe_readme_claims,
    )
    from assemblyzero.workflows.janitor.probes.persona_status import (
        probe_persona_status,
    )

    return {
        "inventory_drift": probe_inventory_drift,
        "dead_references": probe_dead_references,
        "adr_collision": probe_adr_collision,
        "stale_timestamps": probe_stale_timestamps,
        "readme_claims": probe_readme_claims,
        "persona_status": probe_persona_status,
    }


def run_probe(
    probe_name: str,
    repo_root: Path,
) -> ProbeResult:
    """Run a single named spelunking probe."""
    registry = _get_probe_registry()

    if probe_name not in registry:
        raise ValueError(f"Unknown probe: {probe_name}")

    probe_fn = registry[probe_name]
    start = time.monotonic()

    try:
        result = probe_fn(repo_root)
    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return ProbeResult(
            probe_name=probe_name,
            findings=[],
            passed=False,
            summary=f"Error: {exc}",
            execution_time_ms=round(elapsed_ms, 1),
        )

    # Update execution time with actual measured time
    elapsed_ms = (time.monotonic() - start) * 1000
    result.execution_time_ms = round(elapsed_ms, 1)
    return result


def run_all_probes(
    repo_root: Path,
) -> list[ProbeResult]:
    """Run all registered spelunking probes and return results."""
    registry = _get_probe_registry()
    results: list[ProbeResult] = []

    for probe_name in registry:
        start = time.monotonic()
        try:
            result = registry[probe_name](repo_root)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            result = ProbeResult(
                probe_name=probe_name,
                findings=[],
                passed=False,
                summary=f"Error: {exc}",
                execution_time_ms=round(elapsed_ms, 1),
            )
        else:
            elapsed_ms = (time.monotonic() - start) * 1000
            result.execution_time_ms = round(elapsed_ms, 1)

        results.append(result)

    return results
```

### 6.7 `assemblyzero/workflows/janitor/probes/inventory_drift.py` (Add)

**Complete file contents:**

```python
"""Probe: Inventory Drift — counts files vs. 0003-file-inventory.md claims.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import time
from pathlib import Path

from assemblyzero.spelunking.extractors import extract_file_count_claims
from assemblyzero.spelunking.models import (
    ProbeResult,
    VerificationResult,
    VerificationStatus,
)
from assemblyzero.spelunking.verifiers import verify_file_count


def probe_inventory_drift(
    repo_root: Path,
    inventory_path: Path | None = None,
) -> ProbeResult:
    """Count files in key directories and compare to 0003-file-inventory.md."""
    start = time.monotonic()

    if inventory_path is None:
        inventory_path = repo_root / "docs" / "standards" / "0003-file-inventory.md"

    if not inventory_path.exists():
        elapsed_ms = (time.monotonic() - start) * 1000
        return ProbeResult(
            probe_name="inventory_drift",
            findings=[],
            passed=True,
            summary="Inventory file not found, skipping",
            execution_time_ms=round(elapsed_ms, 1),
        )

    content = inventory_path.read_text(encoding="utf-8")
    claims = extract_file_count_claims(content, inventory_path)

    findings: list[VerificationResult] = []

    for claim in claims:
        # Parse the verification command to get directory and pattern
        cmd = claim.verification_command.replace(" | count", "").replace("glob ", "")
        directory = repo_root / Path(cmd).parent
        glob_pattern = Path(cmd).name
        expected = int(claim.expected_value)

        result = verify_file_count(directory, expected, glob_pattern, claim)
        if result.status != VerificationStatus.MATCH:
            findings.append(result)

    elapsed_ms = (time.monotonic() - start) * 1000
    passed = len(findings) == 0

    if passed:
        summary = "No inventory drift detected"
    else:
        mismatch_details = []
        for f in findings:
            mismatch_details.append(
                f"{f.claim.claim_text}: expected {f.claim.expected_value}, actual {f.actual_value}"
            )
        summary = f"{len(findings)} inventory mismatch(es): {'; '.join(mismatch_details[:3])}"

    return ProbeResult(
        probe_name="inventory_drift",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=round(elapsed_ms, 1),
    )
```

### 6.8 `assemblyzero/workflows/janitor/probes/dead_references.py` (Add)

**Complete file contents:**

```python
"""Probe: Dead References — finds file path references pointing to nonexistent files.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import time
from pathlib import Path

from assemblyzero.spelunking.extractors import extract_file_reference_claims
from assemblyzero.spelunking.models import (
    ProbeResult,
    VerificationResult,
    VerificationStatus,
)
from assemblyzero.spelunking.verifiers import verify_file_exists


def probe_dead_references(
    repo_root: Path,
    doc_dirs: list[Path] | None = None,
) -> ProbeResult:
    """Grep all Markdown files for file path references and verify each exists."""
    start = time.monotonic()

    if doc_dirs is None:
        doc_dirs = [repo_root / "docs"]
        # Also check root-level markdown
        doc_dirs.append(repo_root)

    md_files: list[Path] = []
    for doc_dir in doc_dirs:
        if not doc_dir.exists():
            continue
        if doc_dir == repo_root:
            md_files.extend(doc_dir.glob("*.md"))
        else:
            md_files.extend(doc_dir.rglob("*.md"))

    findings: list[VerificationResult] = []

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8", errors="ignore")
        claims = extract_file_reference_claims(content, md_file)

        for claim in claims:
            result = verify_file_exists(Path(claim.expected_value), repo_root, claim)
            if result.status == VerificationStatus.MISMATCH:
                findings.append(result)

    elapsed_ms = (time.monotonic() - start) * 1000
    passed = len(findings) == 0

    if passed:
        summary = "No dead references found"
    else:
        dead_paths = [f.claim.expected_value for f in findings[:5]]
        summary = f"{len(findings)} dead reference(s) found: {', '.join(dead_paths)}"

    return ProbeResult(
        probe_name="dead_references",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=round(elapsed_ms, 1),
    )
```

### 6.9 `assemblyzero/workflows/janitor/probes/adr_collision.py` (Add)

**Complete file contents:**

```python
"""Probe: ADR Collision — detects duplicate numeric prefixes in docs/adrs/.

Issue #534: Spelunking Audits
"""

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


_ADR_PREFIX_PATTERN = re.compile(r"^(\d{4})-")


def probe_adr_collision(
    repo_root: Path,
    adr_dir: Path | None = None,
) -> ProbeResult:
    """Scan docs/adrs/ for duplicate numeric prefixes."""
    start = time.monotonic()

    if adr_dir is None:
        adr_dir = repo_root / "docs" / "adrs"

    if not adr_dir.exists():
        elapsed_ms = (time.monotonic() - start) * 1000
        return ProbeResult(
            probe_name="adr_collision",
            findings=[],
            passed=True,
            summary="ADR directory not found, skipping",
            execution_time_ms=round(elapsed_ms, 1),
        )

    # Group files by prefix
    prefix_map: dict[str, list[str]] = {}
    for file_path in sorted(adr_dir.iterdir()):
        if file_path.is_file() and file_path.suffix == ".md":
            match = _ADR_PREFIX_PATTERN.match(file_path.name)
            if match:
                prefix = match.group(1)
                prefix_map.setdefault(prefix, []).append(file_path.name)

    findings: list[VerificationResult] = []
    for prefix, files in sorted(prefix_map.items()):
        if len(files) > 1:
            claim = Claim(
                claim_type=ClaimType.UNIQUE_ID,
                source_file=adr_dir,
                source_line=0,
                claim_text=f"ADR prefix {prefix} should be unique",
                expected_value="1",
                verification_command=f"check_unique_prefix {adr_dir}",
            )
            findings.append(
                VerificationResult(
                    claim=claim,
                    status=VerificationStatus.MISMATCH,
                    actual_value=str(len(files)),
                    evidence=f"Prefix {prefix} used by: {', '.join(files)}",
                )
            )

    elapsed_ms = (time.monotonic() - start) * 1000
    passed = len(findings) == 0

    if passed:
        summary = "No ADR collisions found"
    else:
        prefixes = [f.claim.claim_text.split()[2] for f in findings]
        summary = f"{len(findings)} ADR prefix collision(s): {', '.join(prefixes)}"

    return ProbeResult(
        probe_name="adr_collision",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=round(elapsed_ms, 1),
    )
```

### 6.10 `assemblyzero/workflows/janitor/probes/stale_timestamps.py` (Add)

**Complete file contents:**

```python
"""Probe: Stale Timestamps — flags documents with old or missing timestamps.

Issue #534: Spelunking Audits
"""

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
from assemblyzero.spelunking.verifiers import verify_timestamp_freshness


_TIMESTAMP_PATTERN = re.compile(
    r"[Ll]ast\s+[Uu]pdated:?\s*(\d{4}-\d{2}-\d{2})"
)


def probe_stale_timestamps(
    repo_root: Path,
    max_age_days: int = 30,
    doc_dirs: list[Path] | None = None,
) -> ProbeResult:
    """Flag documents with 'Last Updated' more than max_age_days old. Reports missing timestamps."""
    start = time.monotonic()

    if doc_dirs is None:
        doc_dirs = [repo_root / "docs", repo_root]

    md_files: list[Path] = []
    for doc_dir in doc_dirs:
        if not doc_dir.exists():
            continue
        if doc_dir == repo_root:
            md_files.extend(doc_dir.glob("*.md"))
        else:
            md_files.extend(doc_dir.rglob("*.md"))

    findings: list[VerificationResult] = []

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8", errors="ignore")
        match = _TIMESTAMP_PATTERN.search(content)

        if match is None:
            # Missing timestamp — report as finding
            claim = Claim(
                claim_type=ClaimType.TIMESTAMP,
                source_file=md_file,
                source_line=0,
                claim_text="missing timestamp",
                expected_value="",
                verification_command="check_timestamp_exists",
            )
            findings.append(
                VerificationResult(
                    claim=claim,
                    status=VerificationStatus.MISMATCH,
                    evidence="No 'Last Updated' timestamp found",
                )
            )
        else:
            date_str = match.group(1)
            claim = Claim(
                claim_type=ClaimType.TIMESTAMP,
                source_file=md_file,
                source_line=0,
                claim_text=f"Last Updated: {date_str}",
                expected_value=date_str,
                verification_command=f"check_freshness {date_str}",
            )
            result = verify_timestamp_freshness(date_str, max_age_days, claim)
            if result.status != VerificationStatus.MATCH:
                findings.append(result)

    elapsed_ms = (time.monotonic() - start) * 1000
    passed = len(findings) == 0

    stale_count = sum(
        1 for f in findings if f.status == VerificationStatus.STALE
    )
    missing_count = sum(
        1 for f in findings
        if f.status == VerificationStatus.MISMATCH
        and f.claim.claim_text == "missing timestamp"
    )

    parts = []
    if stale_count:
        parts.append(f"{stale_count} stale document(s)")
    if missing_count:
        parts.append(f"{missing_count} missing timestamp(s)")
    summary = ", ".join(parts) if parts else "No stale timestamps found"

    return ProbeResult(
        probe_name="stale_timestamps",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=round(elapsed_ms, 1),
    )
```

### 6.11 `assemblyzero/workflows/janitor/probes/readme_claims.py` (Add)

**Complete file contents:**

```python
"""Probe: README Claims — extracts technical claims and verifies against codebase.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import time
from pathlib import Path

from assemblyzero.spelunking.extractors import extract_technical_claims
from assemblyzero.spelunking.models import (
    ProbeResult,
    VerificationResult,
    VerificationStatus,
)
from assemblyzero.spelunking.verifiers import verify_no_contradiction


def probe_readme_claims(
    repo_root: Path,
    readme_path: Path | None = None,
) -> ProbeResult:
    """Extract technical claims from README and verify against codebase."""
    start = time.monotonic()

    if readme_path is None:
        readme_path = repo_root / "README.md"

    if not readme_path.exists():
        elapsed_ms = (time.monotonic() - start) * 1000
        return ProbeResult(
            probe_name="readme_claims",
            findings=[],
            passed=True,
            summary="README not found, skipping",
            execution_time_ms=round(elapsed_ms, 1),
        )

    content = readme_path.read_text(encoding="utf-8")
    claims = extract_technical_claims(content, readme_path)

    findings: list[VerificationResult] = []

    for claim in claims:
        result = verify_no_contradiction(
            claim.expected_value, repo_root, claim=claim
        )
        if result.status == VerificationStatus.MISMATCH:
            findings.append(result)

    elapsed_ms = (time.monotonic() - start) * 1000
    passed = len(findings) == 0

    if passed:
        summary = "No README contradictions found"
    else:
        terms = [f.claim.expected_value for f in findings[:3]]
        summary = f"{len(findings)} README contradiction(s): {', '.join(terms)}"

    return ProbeResult(
        probe_name="readme_claims",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=round(elapsed_ms, 1),
    )
```

### 6.12 `assemblyzero/workflows/janitor/probes/persona_status.py` (Add)

**Complete file contents:**

```python
"""Probe: Persona Status — cross-references persona markers against code existence.

Issue #534: Spelunking Audits
"""

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


_PERSONA_HEADER_PATTERN = re.compile(r"^##\s+(.+)", re.MULTILINE)
_STATUS_PATTERN = re.compile(
    r"[Ss]tatus:?\s*(implemented|active|planned|deprecated|draft)",
    re.IGNORECASE,
)


def probe_persona_status(
    repo_root: Path,
    persona_file: Path | None = None,
) -> ProbeResult:
    """Cross-reference Dramatis-Personae.md implementation markers against code."""
    start = time.monotonic()

    if persona_file is None:
        persona_file = repo_root / "docs" / "Dramatis-Personae.md"
        if not persona_file.exists():
            persona_file = repo_root / "Dramatis-Personae.md"

    if not persona_file.exists():
        elapsed_ms = (time.monotonic() - start) * 1000
        return ProbeResult(
            probe_name="persona_status",
            findings=[],
            passed=True,
            summary="Persona file not found, skipping",
            execution_time_ms=round(elapsed_ms, 1),
        )

    content = persona_file.read_text(encoding="utf-8")

    # Split content into sections by ## headers
    sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)

    findings: list[VerificationResult] = []
    total_personas = 0

    for section in sections:
        header_match = _PERSONA_HEADER_PATTERN.match(section)
        if not header_match:
            continue

        persona_name = header_match.group(1).strip()
        total_personas += 1

        # Check for status marker
        status_match = _STATUS_PATTERN.search(section)
        if not status_match:
            claim = Claim(
                claim_type=ClaimType.STATUS_MARKER,
                source_file=persona_file,
                source_line=0,
                claim_text=f"Persona '{persona_name}' missing status",
                expected_value="status marker present",
                verification_command="check_persona_status",
            )
            findings.append(
                VerificationResult(
                    claim=claim,
                    status=VerificationStatus.MISMATCH,
                    evidence=f"Persona '{persona_name}' has no status marker",
                )
            )

    elapsed_ms = (time.monotonic() - start) * 1000
    passed = len(findings) == 0

    if passed:
        summary = f"All {total_personas} personas have status markers"
    else:
        summary = f"{len(findings)} of {total_personas} personas missing status markers"

    return ProbeResult(
        probe_name="persona_status",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=round(elapsed_ms, 1),
    )
```

### 6.13 `tests/fixtures/spelunking/mock_inventory.md` (Add)

**Complete file contents:**

```markdown
# File Inventory

## Directory Counts

| Directory | Count |
|-----------|-------|
| `tools/` | 5 tools in tools/ |
| `docs/adrs/` | 3 ADRs in docs/adrs/ |
```

### 6.14 `tests/fixtures/spelunking/mock_readme.md` (Add)

**Complete file contents:**

```markdown
# Assembly Zero

A deterministic system, not vector embeddings or chromadb.

## Architecture

Built without machine learning. Uses simple file-based storage, not quantum computing.

See `tools/death.py` for the DEATH methodology.
```

### 6.15 `tests/fixtures/spelunking/mock_docs_with_dead_refs.md` (Add)

**Complete file contents:**

```markdown
# Documentation Guide

For implementation details, see `tools/ghost.py`.

Also check [the nonexistent doc](docs/nonexistent.md) for more info.

The real file is at `tools/real.py`.
```

### 6.16 `tests/fixtures/spelunking/mock_personas.md` (Add)

**Complete file contents:**

```markdown
# Dramatis Personae

## The Architect

Status: implemented

Designs system architecture.

## The Builder

Status: implemented

Builds components.

## The Tester

Status: implemented

Tests everything.

## The Reviewer

Reviews code quality.

## The Planner

Plans sprints and milestones.
```

### 6.17 `tests/unit/test_spelunking/__init__.py` (Add)

**Complete file contents:**

```python
"""Test package for spelunking audit system."""
```

### 6.18 `tests/unit/test_spelunking/test_extractors.py` (Add)

**Complete file contents:**

```python
"""Tests for spelunking claim extraction logic.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.spelunking.extractors import (
    extract_claims_from_markdown,
    extract_file_count_claims,
    extract_file_reference_claims,
    extract_technical_claims,
    extract_timestamp_claims,
)
from assemblyzero.spelunking.models import ClaimType


class TestExtractFileCountClaims:
    """Tests for file count claim extraction."""

    def test_T040_extracts_file_count(self) -> None:
        """T040: Extract '11 tools in tools/' as FILE_COUNT claim."""
        content = "There are 11 tools in tools/"
        source = Path("inventory.md")

        claims = extract_file_count_claims(content, source)

        assert len(claims) >= 1
        claim = claims[0]
        assert claim.claim_type == ClaimType.FILE_COUNT
        assert claim.expected_value == "11"
        assert claim.source_line == 1

    def test_extracts_multiple_counts(self) -> None:
        """Extract multiple count claims from multi-line content."""
        content = "11 tools in tools/\n6 ADRs in docs/adrs/"
        source = Path("inventory.md")

        claims = extract_file_count_claims(content, source)

        assert len(claims) >= 2


class TestExtractFileReferenceClaims:
    """Tests for file reference claim extraction."""

    def test_T050_extracts_backtick_reference(self) -> None:
        """T050: Extract backtick file reference."""
        content = "See `tools/death.py` for details."
        source = Path("README.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 1
        assert claims[0].claim_type == ClaimType.FILE_EXISTS
        assert claims[0].expected_value == "tools/death.py"

    def test_extracts_link_reference(self) -> None:
        """Extract markdown link file reference."""
        content = "Check [config](config/settings.yaml) for options."
        source = Path("README.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 1
        assert claims[0].expected_value == "config/settings.yaml"

    def test_skips_urls(self) -> None:
        """Skip http/https URLs."""
        content = "See `https://example.com/file.py` for details."
        source = Path("README.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 0


class TestExtractTechnicalClaims:
    """Tests for technical claim extraction."""

    def test_T060_extracts_negation(self) -> None:
        """T060: Extract 'not vector embeddings' as TECHNICAL_FACT."""
        content = "This system uses deterministic techniques, not vector embeddings."
        source = Path("README.md")

        claims = extract_technical_claims(content, source)

        assert len(claims) >= 1
        found = any(
            c.claim_type == ClaimType.TECHNICAL_FACT
            and "vector embeddings" in c.expected_value
            for c in claims
        )
        assert found


class TestExtractTimestampClaims:
    """Tests for timestamp claim extraction."""

    def test_T070_extracts_last_updated(self) -> None:
        """T070: Extract 'Last Updated: 2026-01-15' as TIMESTAMP."""
        content = "<!-- Last Updated: 2026-01-15 -->"
        source = Path("doc.md")

        claims = extract_timestamp_claims(content, source)

        assert len(claims) == 1
        assert claims[0].claim_type == ClaimType.TIMESTAMP
        assert claims[0].expected_value == "2026-01-15"


class TestExtractClaimsFromMarkdown:
    """Tests for the top-level extraction function."""

    def test_T080_no_claims_in_simple_doc(self, tmp_path: Path) -> None:
        """T080: Return empty list for non-factual document."""
        doc = tmp_path / "hello.md"
        doc.write_text("# Hello\n\nJust a greeting.")

        claims = extract_claims_from_markdown(doc)

        assert claims == []

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Return empty list for nonexistent file."""
        claims = extract_claims_from_markdown(tmp_path / "nope.md")

        assert claims == []

    def test_filtered_claim_types(self, tmp_path: Path) -> None:
        """Only extract specified claim types."""
        doc = tmp_path / "mixed.md"
        doc.write_text("11 tools in tools/\nSee `tools/death.py`\nLast Updated: 2026-01-15")

        claims = extract_claims_from_markdown(doc, claim_types=[ClaimType.FILE_COUNT])

        assert all(c.claim_type == ClaimType.FILE_COUNT for c in claims)
```

### 6.19 `tests/unit/test_spelunking/test_verifiers.py` (Add)

**Complete file contents:**

```python
"""Tests for spelunking verification strategies.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from assemblyzero.spelunking.models import VerificationStatus
from assemblyzero.spelunking.verifiers import (
    _is_within_repo,
    verify_file_count,
    verify_file_exists,
    verify_no_contradiction,
    verify_timestamp_freshness,
    verify_unique_prefix,
)


class TestVerifyFileCount:
    """Tests for file count verification."""

    def test_T090_count_match(self, tmp_path: Path) -> None:
        """T090: File count matches expected."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(5):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        result = verify_file_count(tools, 5, "*.py")

        assert result.status == VerificationStatus.MATCH
        assert result.actual_value == "5"

    def test_T100_count_mismatch(self, tmp_path: Path) -> None:
        """T100: File count does not match expected."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(8):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        result = verify_file_count(tools, 5, "*.py")

        assert result.status == VerificationStatus.MISMATCH
        assert result.actual_value == "8"

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """Nonexistent directory returns ERROR."""
        result = verify_file_count(tmp_path / "nope", 5)

        assert result.status == VerificationStatus.ERROR


class TestVerifyFileExists:
    """Tests for file existence verification."""

    def test_T110_file_exists(self, tmp_path: Path) -> None:
        """T110: Existing file returns MATCH."""
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "real.py").write_text("# real")

        result = verify_file_exists(Path("tools/real.py"), tmp_path)

        assert result.status == VerificationStatus.MATCH

    def test_T120_file_not_found(self, tmp_path: Path) -> None:
        """T120: Nonexistent file returns MISMATCH."""
        result = verify_file_exists(Path("tools/ghost.py"), tmp_path)

        assert result.status == VerificationStatus.MISMATCH

    def test_T190_path_traversal_rejected(self, tmp_path: Path) -> None:
        """T190: Path traversal attempt returns ERROR."""
        result = verify_file_exists(Path("../../etc/passwd"), tmp_path)

        assert result.status == VerificationStatus.ERROR
        assert "traversal" in (result.error_message or "").lower()


class TestVerifyNoContradiction:
    """Tests for contradiction detection."""

    def test_T130_term_absent(self, tmp_path: Path) -> None:
        """T130: Term not found in codebase returns MATCH."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("import os\nprint('hello')")

        result = verify_no_contradiction("chromadb", tmp_path)

        assert result.status == VerificationStatus.MATCH

    def test_T140_contradiction_found(self, tmp_path: Path) -> None:
        """T140: Term found in codebase returns MISMATCH."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "db.py").write_text("import chromadb\nclient = chromadb.Client()")

        result = verify_no_contradiction("chromadb", tmp_path)

        assert result.status == VerificationStatus.MISMATCH
        assert "chromadb" in result.evidence

    def test_short_term_unverifiable(self, tmp_path: Path) -> None:
        """Search term shorter than 3 chars is UNVERIFIABLE."""
        result = verify_no_contradiction("ab", tmp_path)

        assert result.status == VerificationStatus.UNVERIFIABLE


class TestVerifyUniquePrefix:
    """Tests for unique prefix verification."""

    def test_T150_all_unique(self, tmp_path: Path) -> None:
        """T150: All unique prefixes returns MATCH."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0201-first.md").write_text("# ADR 0201")
        (adrs / "0202-second.md").write_text("# ADR 0202")
        (adrs / "0203-third.md").write_text("# ADR 0203")

        result = verify_unique_prefix(adrs)

        assert result.status == VerificationStatus.MATCH

    def test_T160_prefix_collision(self, tmp_path: Path) -> None:
        """T160: Duplicate prefix returns MISMATCH."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0204-first.md").write_text("# ADR 0204a")
        (adrs / "0204-second.md").write_text("# ADR 0204b")
        (adrs / "0205-third.md").write_text("# ADR 0205")

        result = verify_unique_prefix(adrs)

        assert result.status == VerificationStatus.MISMATCH
        assert "0204" in result.evidence

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """Nonexistent directory returns ERROR."""
        result = verify_unique_prefix(tmp_path / "nope")

        assert result.status == VerificationStatus.ERROR


class TestVerifyTimestampFreshness:
    """Tests for timestamp freshness verification."""

    def test_T170_fresh_timestamp(self) -> None:
        """T170: Date within threshold returns MATCH."""
        fresh_date = (date.today() - timedelta(days=5)).isoformat()

        result = verify_timestamp_freshness(fresh_date, max_age_days=30)

        assert result.status == VerificationStatus.MATCH

    def test_T180_stale_timestamp(self) -> None:
        """T180: Date beyond threshold returns STALE."""
        stale_date = (date.today() - timedelta(days=45)).isoformat()

        result = verify_timestamp_freshness(stale_date, max_age_days=30)

        assert result.status == VerificationStatus.STALE

    def test_unparseable_date(self) -> None:
        """Unparseable date returns ERROR."""
        result = verify_timestamp_freshness("not-a-date")

        assert result.status == VerificationStatus.ERROR


class TestIsWithinRepo:
    """Tests for path boundary checking."""

    def test_within_repo(self, tmp_path: Path) -> None:
        """Path within repo returns True."""
        child = tmp_path / "sub" / "file.py"
        assert _is_within_repo(child, tmp_path) is True

    def test_outside_repo(self, tmp_path: Path) -> None:
        """Path outside repo returns False."""
        outside = tmp_path / ".." / ".." / "etc" / "passwd"
        assert _is_within_repo(outside, tmp_path) is False
```

### 6.20 `tests/unit/test_spelunking/test_probes.py` (Add)

**Complete file contents:**

```python
"""Tests for all six automated spelunking probes.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from assemblyzero.workflows.janitor.probes.inventory_drift import (
    probe_inventory_drift,
)
from assemblyzero.workflows.janitor.probes.dead_references import (
    probe_dead_references,
)
from assemblyzero.workflows.janitor.probes.adr_collision import (
    probe_adr_collision,
)
from assemblyzero.workflows.janitor.probes.stale_timestamps import (
    probe_stale_timestamps,
)
from assemblyzero.workflows.janitor.probes.readme_claims import (
    probe_readme_claims,
)
from assemblyzero.workflows.janitor.probes.persona_status import (
    probe_persona_status,
)


class TestInventoryDriftProbe:
    """Tests for inventory drift probe."""

    def test_T200_drift_detected(self, tmp_path: Path) -> None:
        """T200: Inventory says 5, actual 8 -> passed=False."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(8):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        inventory = tmp_path / "inventory.md"
        inventory.write_text("5 tools in tools/")

        result = probe_inventory_drift(tmp_path, inventory_path=inventory)

        assert result.passed is False
        assert len(result.findings) >= 1

    def test_T210_inventory_matches(self, tmp_path: Path) -> None:
        """T210: Inventory says 3, actual 3 -> passed=True."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(3):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        inventory = tmp_path / "inventory.md"
        inventory.write_text("3 tools in tools/")

        result = probe_inventory_drift(tmp_path, inventory_path=inventory)

        assert result.passed is True

    def test_missing_inventory(self, tmp_path: Path) -> None:
        """Missing inventory file -> passed=True, skipping."""
        result = probe_inventory_drift(tmp_path)

        assert result.passed is True
        assert "not found" in result.summary.lower() or "skipping" in result.summary.lower()


class TestDeadReferencesProbe:
    """Tests for dead references probe."""

    def test_T220_dead_ref_found(self, tmp_path: Path) -> None:
        """T220: Doc references ghost.py -> passed=False."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("See `tools/ghost.py` for details.")

        result = probe_dead_references(tmp_path, doc_dirs=[docs])

        assert result.passed is False
        assert len(result.findings) >= 1

    def test_T230_all_refs_valid(self, tmp_path: Path) -> None:
        """T230: Doc references existing file -> passed=True."""
        tools = tmp_path / "tools"
        tools.mkdir()
        (tools / "real.py").write_text("# real")

        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("See `tools/real.py` for details.")

        result = probe_dead_references(tmp_path, doc_dirs=[docs])

        assert result.passed is True


class TestAdrCollisionProbe:
    """Tests for ADR collision probe."""

    def test_T240_collision_detected(self, tmp_path: Path) -> None:
        """T240: Duplicate prefix 0204 -> passed=False."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0204-first.md").write_text("# First")
        (adrs / "0204-second.md").write_text("# Second")

        result = probe_adr_collision(tmp_path, adr_dir=adrs)

        assert result.passed is False
        assert len(result.findings) >= 1

    def test_T250_no_collisions(self, tmp_path: Path) -> None:
        """T250: All unique prefixes -> passed=True."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0201-first.md").write_text("# First")
        (adrs / "0202-second.md").write_text("# Second")

        result = probe_adr_collision(tmp_path, adr_dir=adrs)

        assert result.passed is True


class TestStaleTimestampsProbe:
    """Tests for stale timestamps probe."""

    def test_T260_stale_found(self, tmp_path: Path) -> None:
        """T260: Document with old date -> passed=False."""
        docs = tmp_path / "docs"
        docs.mkdir()
        stale_date = (date.today() - timedelta(days=45)).isoformat()
        (docs / "old.md").write_text(f"<!-- Last Updated: {stale_date} -->\n# Old")

        result = probe_stale_timestamps(tmp_path, doc_dirs=[docs])

        assert result.passed is False

    def test_T270_all_fresh(self, tmp_path: Path) -> None:
        """T270: Document with recent date -> passed=True."""
        docs = tmp_path / "docs"
        docs.mkdir()
        fresh_date = (date.today() - timedelta(days=5)).isoformat()
        (docs / "fresh.md").write_text(f"<!-- Last Updated: {fresh_date} -->\n# Fresh")

        result = probe_stale_timestamps(tmp_path, doc_dirs=[docs])

        assert result.passed is True

    def test_T275_stale_and_missing_timestamps(self, tmp_path: Path) -> None:
        """T275: Stale doc + missing timestamp doc -> passed=False with 2+ findings."""
        docs = tmp_path / "docs"
        docs.mkdir()

        stale_date = (date.today() - timedelta(days=45)).isoformat()
        (docs / "stale.md").write_text(f"<!-- Last Updated: {stale_date} -->\n# Stale")
        (docs / "missing.md").write_text("# No Timestamp Here\n\nJust content.")

        result = probe_stale_timestamps(tmp_path, doc_dirs=[docs])

        assert result.passed is False
        assert len(result.findings) >= 2


class TestReadmeClaimsProbe:
    """Tests for README claims probe."""

    def test_T280_contradiction_found(self, tmp_path: Path) -> None:
        """T280: README says 'not chromadb' but code has it -> passed=False."""
        readme = tmp_path / "README.md"
        readme.write_text("This system does not use chromadb for storage.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "db.py").write_text("import chromadb\nclient = chromadb.Client()")

        result = probe_readme_claims(tmp_path, readme_path=readme)

        assert result.passed is False

    def test_T290_claims_valid(self, tmp_path: Path) -> None:
        """T290: README says 'not quantum' and no quantum code -> passed=True."""
        readme = tmp_path / "README.md"
        readme.write_text("This system does not use quantum computing.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("import os\nprint('hello')")

        result = probe_readme_claims(tmp_path, readme_path=readme)

        assert result.passed is True


class TestPersonaStatusProbe:
    """Tests for persona status probe."""

    def test_T300_persona_gaps(self, tmp_path: Path) -> None:
        """T300: 2 of 5 personas missing status -> passed=False."""
        persona = tmp_path / "personas.md"
        persona.write_text(
            "# Dramatis Personae\n\n"
            "## The Architect\n\nStatus: implemented\n\nDesigns things.\n\n"
            "## The Builder\n\nStatus: implemented\n\nBuilds things.\n\n"
            "## The Tester\n\nStatus: implemented\n\nTests things.\n\n"
            "## The Reviewer\n\nReviews code.\n\n"
            "## The Planner\n\nPlans things.\n"
        )

        result = probe_persona_status(tmp_path, persona_file=persona)

        assert result.passed is False
        assert len(result.findings) == 2

    def test_all_personas_have_status(self, tmp_path: Path) -> None:
        """All personas with status markers -> passed=True."""
        persona = tmp_path / "personas.md"
        persona.write_text(
            "# Dramatis Personae\n\n"
            "## The Architect\n\nStatus: implemented\n\n"
            "## The Builder\n\nStatus: active\n\n"
        )

        result = probe_persona_status(tmp_path, persona_file=persona)

        assert result.passed is True
```

### 6.21 `tests/unit/test_spelunking/test_engine.py` (Add)

**Complete file contents:**

```python
"""Tests for the core spelunking engine.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from assemblyzero.spelunking.engine import run_all_probes, run_probe, run_spelunking
from assemblyzero.spelunking.models import (
    SpelunkingCheckpoint,
    VerificationStatus,
)


class TestRunSpelunking:
    """Tests for the run_spelunking engine function."""

    def test_T010_known_drift(self, tmp_path: Path) -> None:
        """T010: Document claiming '5 tools' with 3 actual tools -> drift_score < 100."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(3):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        doc = tmp_path / "inventory.md"
        doc.write_text("There are 5 tools in tools/")

        report = run_spelunking(doc, tmp_path)

        assert report.total_claims >= 1
        assert report.drift_score < 100.0
        # Should have MISMATCH findings
        mismatches = [
            r for r in report.results if r.status == VerificationStatus.MISMATCH
        ]
        assert len(mismatches) >= 1

    def test_T020_empty_document(self, tmp_path: Path) -> None:
        """T020: Empty document -> 0 claims, drift_score 100.0."""
        doc = tmp_path / "empty.md"
        doc.write_text("")

        report = run_spelunking(doc, tmp_path)

        assert report.total_claims == 0
        assert report.drift_score == 100.0

    def test_T030_checkpoints_override(self, tmp_path: Path) -> None:
        """T030: Provided checkpoints used instead of auto-extraction."""
        tools = tmp_path / "tools"
        tools.mkdir()
        (tools / "a.py").write_text("# a")
        (tools / "b.py").write_text("# b")

        doc = tmp_path / "doc.md"
        doc.write_text("Irrelevant content")

        checkpoints = [
            SpelunkingCheckpoint(
                claim="2 tools exist",
                verify_command="path_exists tools/a.py",
                source_file="doc.md",
            ),
            SpelunkingCheckpoint(
                claim="tools/b.py exists",
                verify_command="path_exists tools/b.py",
                source_file="doc.md",
            ),
        ]

        report = run_spelunking(doc, tmp_path, checkpoints=checkpoints)

        assert len(report.results) == 2
        assert all(r.status == VerificationStatus.MATCH for r in report.results)


class TestRunProbe:
    """Tests for the run_probe function."""

    def test_unknown_probe_raises(self, tmp_path: Path) -> None:
        """Unknown probe name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown probe"):
            run_probe("nonexistent_probe", tmp_path)


class TestRunAllProbes:
    """Tests for the run_all_probes function."""

    def test_T340_all_probes_run(self, tmp_path: Path) -> None:
        """T340: All 6 probes run without crashing on empty repo."""
        results = run_all_probes(tmp_path)

        assert len(results) == 6
        # All should have probe names
        names = {r.probe_name for r in results}
        assert "inventory_drift" in names
        assert "dead_references" in names
        assert "adr_collision" in names
        assert "stale_timestamps" in names
        assert "readme_claims" in names
        assert "persona_status" in names
```

### 6.22 `tests/unit/test_spelunking/test_report.py` (Add)

**Complete file contents:**

```python
"""Tests for drift report generation.

Issue #534: Spelunking Audits
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


def _make_result(status: VerificationStatus, claim_text: str = "test claim") -> VerificationResult:
    """Helper to create a VerificationResult with minimal boilerplate."""
    return VerificationResult(
        claim=Claim(
            claim_type=ClaimType.FILE_COUNT,
            source_file=Path("test.md"),
            source_line=1,
            claim_text=claim_text,
            expected_value="5",
            verification_command="test",
        ),
        status=status,
        actual_value="5" if status == VerificationStatus.MATCH else "8",
    )


class TestDriftScore:
    """Tests for drift score calculation."""

    def test_T310_drift_score_calculation(self) -> None:
        """T310: 8 MATCH + 2 MISMATCH -> drift_score == 80.0."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(8)]
        results += [_make_result(VerificationStatus.MISMATCH) for _ in range(2)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.drift_score == 80.0

    def test_T350_unverifiable_excluded(self) -> None:
        """T350: 5 MATCH + 3 UNVERIFIABLE -> drift_score == 100.0."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(5)]
        results += [_make_result(VerificationStatus.UNVERIFIABLE) for _ in range(3)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.drift_score == 100.0


class TestGenerateDriftReport:
    """Tests for drift report generation."""

    def test_T320_markdown_report(self) -> None:
        """T320: Generate valid Markdown with tables."""
        results = [
            _make_result(VerificationStatus.MATCH, "match claim"),
            _make_result(VerificationStatus.MISMATCH, "mismatch claim"),
        ]
        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "# Spelunking Drift Report" in output
        assert "| Metric | Value |" in output
        assert "Total Claims | 2" in output
        assert "[FAIL]" in output or "[PASS]" in output

    def test_T325_json_report(self) -> None:
        """T325: Generate valid JSON with all fields."""
        results = [
            _make_result(VerificationStatus.MATCH),
            _make_result(VerificationStatus.MISMATCH),
            _make_result(VerificationStatus.STALE),
        ]
        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        output = generate_drift_report(report, output_format="json")
        data = json.loads(output)

        assert "drift_score" in data
        assert "results" in data
        assert "target_document" in data
        assert len(data["results"]) == 3

    def test_T327_invalid_format_raises(self) -> None:
        """T327: Invalid format raises ValueError."""
        report = DriftReport(
            target_document=Path("test.md"),
            results=[],
        )

        with pytest.raises(ValueError, match="Unsupported output format"):
            generate_drift_report(report, output_format="xml")


class TestGenerateProbeSummary:
    """Tests for probe summary generation."""

    def test_T330_probe_summary_table(self) -> None:
        """T330: 3 ProbeResults -> Markdown table with [PASS]/[FAIL]."""
        probes = [
            ProbeResult(probe_name="probe_a", findings=[], passed=True, summary="OK", execution_time_ms=10.0),
            ProbeResult(probe_name="probe_b", findings=[_make_result(VerificationStatus.MISMATCH)], passed=False, summary="Bad", execution_time_ms=20.0),
            ProbeResult(probe_name="probe_c", findings=[], passed=True, summary="OK", execution_time_ms=15.0),
        ]

        output = generate_probe_summary(probes)

        assert "[PASS]" in output
        assert "[FAIL]" in output
        assert "probe_a" in output
        assert "probe_b" in output
        assert "probe_c" in output

    def test_T335_totals_row(self) -> None:
        """T335: 6 ProbeResults -> totals row with counts."""
        probes = [
            ProbeResult(probe_name=f"probe_{i}", findings=[], passed=(i < 4), summary="", execution_time_ms=10.0 * (i + 1))
            for i in range(6)
        ]

        output = generate_probe_summary(probes)

        assert "**Totals**" in output
        assert "4 passed" in output
        assert "2 failed" in output


class TestFormatDriftScoreBadge:
    """Tests for drift score badge formatting."""

    def test_pass_badge(self) -> None:
        """Score >= 90 gets [PASS] badge."""
        assert _format_drift_score_badge(95.0) == "[PASS] 95.0%"

    def test_fail_badge(self) -> None:
        """Score < 90 gets [FAIL] badge."""
        assert _format_drift_score_badge(75.0) == "[FAIL] 75.0%"

    def test_threshold_boundary(self) -> None:
        """Exactly 90.0 gets [PASS] badge."""
        assert _format_drift_score_badge(90.0) == "[PASS] 90.0%"
```

### 6.23 `tests/unit/test_spelunking/test_dependencies.py` (Add)

**Complete file contents:**

```python
"""Tests verifying no new external dependencies are introduced.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest


# Python 3.10+ provides sys.stdlib_module_names
STDLIB_MODULES = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()
INTERNAL_PREFIXES = ("assemblyzero",)

# Fallback for pre-3.10: list well-known stdlib top-level modules
if not STDLIB_MODULES:
    STDLIB_MODULES = {
        "__future__", "abc", "ast", "asyncio", "collections", "contextlib",
        "copy", "csv", "dataclasses", "datetime", "decimal", "enum",
        "functools", "glob", "hashlib", "importlib", "inspect", "io",
        "itertools", "json", "logging", "math", "os", "pathlib", "pickle",
        "platform", "pprint", "re", "shutil", "signal", "socket",
        "sqlite3", "string", "struct", "subprocess", "sys", "tempfile",
        "textwrap", "threading", "time", "traceback", "typing", "unittest",
        "urllib", "uuid", "warnings", "xml",
    }


def _get_repo_root() -> Path:
    """Find repo root from test file location."""
    return Path(__file__).resolve().parents[3]


class TestNoDependencyCreep:
    """Tests that spelunking introduces no external dependencies."""

    def test_T360_no_external_imports(self) -> None:
        """T360: All imports in spelunking/*.py and new probes resolve to stdlib or internal.

        Scans all Python files in:
        - assemblyzero/spelunking/*.py
        - assemblyzero/workflows/janitor/probes/{inventory_drift,dead_references,
          adr_collision,stale_timestamps,readme_claims,persona_status}.py

        For each file, parses the AST and checks every import statement.
        Any import whose top-level module is not in sys.stdlib_module_names
        and does not start with 'assemblyzero' is flagged as third-party.

        Input: No arguments (scans files on disk).
        Output on success: Test passes (no assertion errors).
        Output on failure: AssertionError listing the third-party imports found.
          Example: AssertionError("Third-party imports found: 'chromadb' in assemblyzero/spelunking/engine.py")
        """
        repo_root = _get_repo_root()

        spelunking_dir = repo_root / "assemblyzero" / "spelunking"
        spelunking_files = list(spelunking_dir.glob("*.py")) if spelunking_dir.exists() else []

        probe_names = [
            "inventory_drift.py",
            "dead_references.py",
            "adr_collision.py",
            "stale_timestamps.py",
            "readme_claims.py",
            "persona_status.py",
        ]
        probe_dir = repo_root / "assemblyzero" / "workflows" / "janitor" / "probes"
        probe_files = [
            probe_dir / name for name in probe_names
            if (probe_dir / name).exists()
        ]

        all_files = spelunking_files + probe_files
        third_party: list[str] = []

        for file_path in all_files:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if (
                            top not in STDLIB_MODULES
                            and not any(alias.name.startswith(p) for p in INTERNAL_PREFIXES)
                        ):
                            rel = file_path.relative_to(repo_root)
                            third_party.append(f"'{alias.name}' in {rel}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    top = node.module.split(".")[0]
                    if (
                        top not in STDLIB_MODULES
                        and not any(node.module.startswith(p) for p in INTERNAL_PREFIXES)
                    ):
                        rel = file_path.relative_to(repo_root)
                        third_party.append(f"'{node.module}' in {rel}")

        assert not third_party, f"Third-party imports found: {', '.join(third_party)}"

    def test_T365_pyproject_unchanged(self) -> None:
        """T365: No new entries in pyproject.toml dependencies.

        This test reads pyproject.toml and checks that the
        [tool.poetry.dependencies] section has not grown. Since we add
        zero new dependencies, the count should remain stable.
        """
        repo_root = _get_repo_root()
        pyproject = repo_root / "pyproject.toml"

        if not pyproject.exists():
            pytest.skip("pyproject.toml not found")

        content = pyproject.read_text(encoding="utf-8")

        # Simple check: ensure no 'chromadb', 'numpy', 'pandas', etc.
        # are present as new additions
        suspicious_deps = [
            "chromadb", "numpy", "pandas", "scikit", "tensorflow",
            "torch", "transformers", "langchain", "openai",
        ]

        found = []
        for dep in suspicious_deps:
            if dep in content.lower():
                found.append(dep)

        assert not found, (
            f"Suspicious new dependencies found in pyproject.toml: {', '.join(found)}"
        )
```

### 6.24 `docs/standards/0015-spelunking-audit-standard.md` (Add)

**Complete file contents:**

```markdown
<!-- Last Updated: 2026-02-17 -->
<!-- Updated By: Issue #534 -->

# Standard 0015: Spelunking Audit Protocol

## Purpose

Define the protocol for spelunking audits — deep verification that documentation claims match codebase reality.

## Scope

All documentation files in the repository, including README.md, standards, ADRs, wiki pages, and persona files.

## Definitions

- **Claim**: A verifiable factual assertion in a document (e.g., "11 tools in tools/")
- **Drift**: When a claim no longer matches reality
- **Drift Score**: Percentage of verifiable claims that match reality (target: >90%)
- **Probe**: An automated check that verifies a specific category of claims
- **Spelunking Checkpoint**: A YAML-declared verification point for manual audit integration

## Protocol

### Automated Probes

Six probes run automatically:

1. **Inventory Drift** — file counts vs. inventory document
2. **Dead References** — file path references to nonexistent files
3. **ADR Collision** — duplicate numeric prefixes in ADR files
4. **Stale Timestamps** — documents with outdated "Last Updated" dates
5. **README Claims** — technical assertions contradicted by code
6. **Persona Status** — persona markers without status declarations

### Drift Score Calculation

```
drift_score = (matching_claims / verifiable_claims) * 100
```

- UNVERIFIABLE claims are excluded from the denominator
- Score >= 90%: PASS
- Score < 90%: FAIL

### Checkpoint Format

Existing audits can declare spelunking checkpoints in YAML:

```yaml
checkpoints:
  - claim: "11 tools exist in tools/"
    verify_command: "glob tools/*.py | count"
    source_file: "docs/standards/0003-file-inventory.md"
```

## Compliance

All documentation files SHOULD have a "Last Updated" timestamp. All file path references in documentation MUST point to existing files. ADR numeric prefixes MUST be unique.
```

### 6.25 Test Fixtures Directories (Add)

Create the following directories (no content needed beyond the files already specified):

- `tests/fixtures/spelunking/` — already populated by mock files above
- `tests/fixtures/spelunking/mock_repo/` — created dynamically by tests using `tmp_path`
- `tests/fixtures/spelunking/mock_repo/tools/` — created dynamically
- `tests/fixtures/spelunking/mock_repo/docs/` — created dynamically
- `tests/fixtures/spelunking/mock_repo/docs/adrs/` — created dynamically

**Note:** The mock_repo directories are primarily created via `tmp_path` in tests. The fixtures directory holds only the static mock files (inventory, readme, dead refs, personas).


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
| `from datetime import timedelta` | stdlib | Test files |
| `from enum import Enum` | stdlib | `models.py` |
| `from pathlib import Path` | stdlib | All files |
| `from typing import Optional, Callable` | stdlib | `models.py`, `engine.py` |
| `import re` | stdlib | `extractors.py`, `verifiers.py`, probe files |
| `import time` | stdlib | `engine.py`, probe files |
| `import json` | stdlib | `report.py`, `test_report.py` |
| `import ast` | stdlib | `test_dependencies.py` |
| `import sys` | stdlib | `test_dependencies.py` |
| `import pytest` | dev dependency (existing) | All test files |
| `from assemblyzero.spelunking.models import *` | internal | All spelunking modules, probes |
| `from assemblyzero.spelunking.extractors import *` | internal | `engine.py`, `inventory_drift.py`, `dead_references.py`, `readme_claims.py` |
| `from assemblyzero.spelunking.verifiers import *` | internal | `engine.py`, `inventory_drift.py`, `dead_references.py`, `stale_timestamps.py` |
| `from assemblyzero.spelunking.report import *` | internal | `test_report.py` |
| `from assemblyzero.spelunking.engine import *` | internal | `test_engine.py` |
| `from assemblyzero.workflows.janitor.probes.* import *` | internal | `test_probes.py`, `engine.py` (lazy) |

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
| T360 | `test_T360_no_external_imports()` | `test_dependencies.py` | Scans spelunking/*.py + probe files on disk | No assertion errors (pass) or AssertionError listing third-party imports (fail) |
| T365 | `test_T365_pyproject_unchanged()` | `test_dependencies.py` | pyproject.toml | No new suspicious dependencies |


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
| `_DRIFT_PASS_THRESHOLD` | `90.0` | LLD requirement REQ-8 |
| `_EVIDENCE_MAX_LEN` | `100` chars | Prevent table overflow in Markdown reports |
| `_CLAIM_TEXT_MAX_LEN` | `50` chars | Keep table rows readable |
| `_MAX_GREP_MATCHES` | `10` | Prevent report bloat for widespread contradictions |
| `_MIN_SEARCH_TERM_LENGTH` | `3` chars | Avoid false positives from very short terms |

### 10.4 Lazy Import Pattern

The engine uses lazy imports for probe functions via `_get_probe_registry()` to avoid circular import issues. The probe modules import from `assemblyzero.spelunking.models` and `assemblyzero.spelunking.verifiers`, while the engine imports the probe modules. The lazy pattern ensures the spelunking package can be imported without triggering probe imports until they're needed.

### 10.5 Path Resolution

All path operations use `Path.resolve()` for security (preventing traversal attacks) and `Path.relative_to()` for reporting (clean display paths). The `_is_within_repo()` guard is called before any `verify_file_exists()` check.

---


## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 — only `probes/` directory is "Modify", covered in 3.1)
- [x] Every data structure has a concrete JSON/YAML example (Section 4 — all 7 structures have examples)
- [x] Every function has input/output examples with realistic values (Section 5 — all 27 functions specified, including `test_T360_no_external_imports()`)
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
| Iterations | 2 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #534 |
| Verdict | APPROVED |
| Date | 2026-03-01 |
| Iterations | 1 |
| Finalized | 2026-03-01T23:21:38Z |

### Review Feedback Summary

The Implementation Spec is exceptional in its completeness and executability. By providing the full source code for all 25 files—including implementation logic, data models, and comprehensive tests—it eliminates ambiguity for the implementing agent. The logic follows the specified constraints (stdlib only) and integrates cleanly with the existing architecture via the lazy-import registry pattern. The test coverage is explicitly mapped and implemented.

## Suggestions
- The lazy import strategy i...


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
tests/
  accessibility/
  adversarial/
  benchmark/
  compliance/
  contract/
  e2e/
  fixtures/
    issue_workflow/
    janitor/
      mock_repo/
    lld_tracking/
    metrics/
    mock_lineage/
    mock_repo/
      src/
    rag/
    scout/
    scraper/
    spelunking/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_gate/
    test_janitor/
    test_metrics/
    test_rag/
    test_spelunking/
  visual/
  __init__.py
  conftest.py
  test_assemblyzero_config.py
  test_audit.py
  test_audit_sharding.py
  test_credentials.py
  test_designer.py
  test_gemini_client.py
  test_gemini_credentials_v2.py
  test_integration_workflow.py
  ... and 13 more files
assemblyzero/
  core/
    validation/
  graphs/
  hooks/
  metrics/
  nodes/
  rag/
  spelunking/
  telemetry/
  utils/
  workflows/
    implementation_spec/
      nodes/
    issue/
      nodes/
    janitor/
      probes/
    lld/
    orchestrator/
    parallel/
    requirements/
      nodes/
      parsers/
    scout/
    testing/
      completeness/
      knowledge/
      nodes/
      runners/
      templates/
  __init__.py
  tracing.py
dashboard/
  src/
    client/
      components/
      pages/
  package.json
  tsconfig.client.json
  tsconfig.json
  tsconfig.worker.json
  wrangler.toml
data/
  unleashed/
  handoff-log.md
```

Use these real paths — do NOT invent paths that don't exist.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_spelunking\test_engine.py
"""Tests for the core spelunking engine.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.spelunking.engine import run_all_probes, run_probe, run_spelunking
from assemblyzero.spelunking.models import (
    SpelunkingCheckpoint,
    VerificationStatus,
)


class TestRunSpelunking:
    """Tests for the run_spelunking engine function."""

    def test_T010_known_drift(self, tmp_path: Path) -> None:
        """T010: Document claiming '5 tools' with 3 actual tools -> drift_score < 100."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(3):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        doc = tmp_path / "inventory.md"
        doc.write_text("There are 5 tools in tools/")

        report = run_spelunking(doc, tmp_path)

        assert report.total_claims >= 1
        assert report.drift_score < 100.0
        # Should have MISMATCH findings
        mismatches = [
            r for r in report.results if r.status == VerificationStatus.MISMATCH
        ]
        assert len(mismatches) >= 1

    def test_T020_empty_document(self, tmp_path: Path) -> None:
        """T020: Empty document -> 0 claims, drift_score 100.0."""
        doc = tmp_path / "empty.md"
        doc.write_text("")

        report = run_spelunking(doc, tmp_path)

        assert report.total_claims == 0
        assert report.drift_score == 100.0

    def test_T030_checkpoints_override(self, tmp_path: Path) -> None:
        """T030: Provided checkpoints used instead of auto-extraction."""
        tools = tmp_path / "tools"
        tools.mkdir()
        (tools / "a.py").write_text("# a")
        (tools / "b.py").write_text("# b")

        doc = tmp_path / "doc.md"
        doc.write_text("Irrelevant content")

        checkpoints = [
            SpelunkingCheckpoint(
                claim="2 tools exist",
                verify_command="path_exists tools/a.py",
                source_file="doc.md",
            ),
            SpelunkingCheckpoint(
                claim="tools/b.py exists",
                verify_command="path_exists tools/b.py",
                source_file="doc.md",
            ),
        ]

        report = run_spelunking(doc, tmp_path, checkpoints=checkpoints)

        assert len(report.results) == 2
        assert all(r.status == VerificationStatus.MATCH for r in report.results)

    def test_nonexistent_document(self, tmp_path: Path) -> None:
        """Nonexistent target document -> 0 claims, drift_score 100.0."""
        doc = tmp_path / "nonexistent.md"

        report = run_spelunking(doc, tmp_path)

        assert report.total_claims == 0
        assert report.drift_score == 100.0

    def test_matching_claims(self, tmp_path: Path) -> None:
        """Document with accurate claims -> drift_score 100.0."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(5):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        doc = tmp_path / "inventory.md"
        doc.write_text("There are 5 tools in tools/")

        report = run_spelunking(doc, tmp_path)

        assert report.total_claims >= 1
        assert report.drift_score == 100.0


class TestRunProbe:
    """Tests for the run_probe function."""

    def test_unknown_probe_raises(self, tmp_path: Path) -> None:
        """Unknown probe name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown probe"):
            run_probe("nonexistent_probe", tmp_path)

    def test_known_probe_runs(self, tmp_path: Path) -> None:
        """Known probe name runs without error."""
        result = run_probe("inventory_drift", tmp_path)

        assert result.probe_name == "inventory_drift"
        assert isinstance(result.execution_time_ms, float)

    def test_probe_measures_time(self, tmp_path: Path) -> None:
        """Probe execution time is measured."""
        result = run_probe("dead_references", tmp_path)

        assert result.execution_time_ms >= 0.0


class TestRunAllProbes:
    """Tests for the run_all_probes function."""

    def test_T340_all_probes_run(self, tmp_path: Path) -> None:
        """T340: All 6 probes run without crashing on empty repo."""
        results = run_all_probes(tmp_path)

        assert len(results) == 6
        # All should have probe names
        names = {r.probe_name for r in results}
        assert "inventory_drift" in names
        assert "dead_references" in names
        assert "adr_collision" in names
        assert "stale_timestamps" in names
        assert "readme_claims" in names
        assert "persona_status" in names

    def test_all_probes_have_timing(self, tmp_path: Path) -> None:
        """All probes report execution time."""
        results = run_all_probes(tmp_path)

        for result in results:
            assert result.execution_time_ms >= 0.0

    def test_all_probes_pass_on_empty_repo(self, tmp_path: Path) -> None:
        """Empty repo produces all passing probes (nothing to flag)."""
        results = run_all_probes(tmp_path)

        for result in results:
            assert result.passed is True, (
                f"Probe {result.probe_name} failed on empty repo: {result.summary}"
            )

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_spelunking\test_extractors.py
"""Tests for spelunking claim extraction logic.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.spelunking.extractors import (
    extract_claims_from_markdown,
    extract_file_count_claims,
    extract_file_reference_claims,
    extract_technical_claims,
    extract_timestamp_claims,
)
from assemblyzero.spelunking.models import ClaimType


class TestExtractFileCountClaims:
    """Tests for file count claim extraction."""

    def test_T040_extracts_file_count(self) -> None:
        """T040: Extract '11 tools in tools/' as FILE_COUNT claim."""
        content = "There are 11 tools in tools/"
        source = Path("inventory.md")

        claims = extract_file_count_claims(content, source)

        assert len(claims) >= 1
        claim = claims[0]
        assert claim.claim_type == ClaimType.FILE_COUNT
        assert claim.expected_value == "11"
        assert claim.source_line == 1

    def test_extracts_multiple_counts(self) -> None:
        """Extract multiple count claims from multi-line content."""
        content = "11 tools in tools/\n6 ADRs in docs/adrs/"
        source = Path("inventory.md")

        claims = extract_file_count_claims(content, source)

        assert len(claims) >= 2

    def test_extracts_count_with_backticks(self) -> None:
        """Extract count claims where directory is in backticks."""
        content = "5 tools in `tools/`"
        source = Path("inventory.md")

        claims = extract_file_count_claims(content, source)

        assert len(claims) >= 1
        assert claims[0].expected_value == "5"

    def test_no_counts_returns_empty(self) -> None:
        """Content with no numeric counts returns empty list."""
        content = "This is just a regular paragraph with no numbers or directories."
        source = Path("doc.md")

        claims = extract_file_count_claims(content, source)

        assert claims == []

    def test_correct_line_numbers(self) -> None:
        """Line numbers are correctly tracked across multiple lines."""
        content = "Header line\nAnother line\n3 files in src/"
        source = Path("doc.md")

        claims = extract_file_count_claims(content, source)

        assert len(claims) >= 1
        assert claims[0].source_line == 3

    def test_adr_uses_md_glob(self) -> None:
        """ADR count claims use *.md glob pattern."""
        content = "6 ADRs in docs/adrs/"
        source = Path("inventory.md")

        claims = extract_file_count_claims(content, source)

        assert len(claims) >= 1
        assert "*.md" in claims[0].verification_command

    def test_tools_uses_py_glob(self) -> None:
        """Tool count claims use *.py glob pattern."""
        content = "11 tools in tools/"
        source = Path("inventory.md")

        claims = extract_file_count_claims(content, source)

        assert len(claims) >= 1
        assert "*.py" in claims[0].verification_command

    def test_source_file_preserved(self) -> None:
        """Source file path is preserved in extracted claims."""
        content = "5 files in src/"
        source = Path("docs/standards/0003-file-inventory.md")

        claims = extract_file_count_claims(content, source)

        assert len(claims) >= 1
        assert claims[0].source_file == source


class TestExtractFileReferenceClaims:
    """Tests for file reference claim extraction."""

    def test_T050_extracts_backtick_reference(self) -> None:
        """T050: Extract backtick file reference."""
        content = "See `tools/death.py` for details."
        source = Path("README.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 1
        assert claims[0].claim_type == ClaimType.FILE_EXISTS
        assert claims[0].expected_value == "tools/death.py"

    def test_extracts_link_reference(self) -> None:
        """Extract markdown link file reference."""
        content = "Check [config](config/settings.yaml) for options."
        source = Path("README.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 1
        assert claims[0].expected_value == "config/settings.yaml"

    def test_skips_urls(self) -> None:
        """Skip http/https URLs."""
        content = "See `https://example.com/file.py` for details."
        source = Path("README.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 0

    def test_deduplicates_paths(self) -> None:
        """Same path referenced twice is only extracted once."""
        content = "See `tools/death.py` here.\nAnd `tools/death.py` again."
        source = Path("README.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 1

    def test_multiple_references_on_same_line(self) -> None:
        """Multiple references on one line are all extracted."""
        content = "See `tools/a.py` and `tools/b.py` for details."
        source = Path("README.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 2
        paths = {c.expected_value for c in claims}
        assert "tools/a.py" in paths
        assert "tools/b.py" in paths

    def test_no_references_returns_empty(self) -> None:
        """Content with no file references returns empty list."""
        content = "This is just plain text without any file paths."
        source = Path("doc.md")

        claims = extract_file_reference_claims(content, source)

        assert claims == []

    def test_verification_command_format(self) -> None:
        """Verification command uses path_exists format."""
        content = "See `tools/death.py` for details."
        source = Path("README.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 1
        assert claims[0].verification_command == "path_exists tools/death.py"

    def test_correct_line_numbers(self) -> None:
        """Line numbers are tracked correctly for file references."""
        content = "Line one.\nLine two.\nSee `tools/thing.py` here."
        source = Path("doc.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 1
        assert claims[0].source_line == 3


class TestExtractTechnicalClaims:
    """Tests for technical claim extraction."""

    def test_T060_extracts_negation(self) -> None:
        """T060: Extract 'not vector embeddings' as TECHNICAL_FACT."""
        content = "This system uses deterministic techniques, not vector embeddings."
        source = Path("README.md")

        claims = extract_technical_claims(content, source)

        assert len(claims) >= 1
        found = any(
            c.claim_type == ClaimType.TECHNICAL_FACT
            and "vector embeddings" in c.expected_value
            for c in claims
        )
        assert found

    def test_extracts_without_negation(self) -> None:
        """Extract 'without chromadb' as TECHNICAL_FACT."""
        content = "Built without chromadb for storage."
        source = Path("README.md")

        claims = extract_technical_claims(content, source)

        assert len(claims) >= 1
        found = any(
            "chromadb" in c.expected_value for c in claims
        )
        assert found

    def test_extracts_no_negation(self) -> None:
        """Extract 'no machine learning' as TECHNICAL_FACT."""
        content = "Uses no machine learning techniques."
        source = Path("README.md")

        claims = extract_technical_claims(content, source)

        assert len(claims) >= 1
        found = any(
            "machine learning" in c.expected_value for c in claims
        )
        assert found

    def test_no_negations_returns_empty(self) -> None:
        """Content without negation patterns returns empty list."""
        content = "This system uses Python and pytest for testing."
        source = Path("README.md")

        claims = extract_technical_claims(content, source)

        assert claims == []

    def test_short_terms_excluded(self) -> None:
        """Terms shorter than 3 chars after 'not' are excluded."""
        content = "This is not an issue."
        source = Path("doc.md")

        claims = extract_technical_claims(content, source)

        # "an" is only 2 chars, should be excluded
        short_claims = [c for c in claims if len(c.expected_value) < 3]
        assert len(short_claims) == 0

    def test_deduplicates_terms(self) -> None:
        """Same negated term mentioned twice is only extracted once."""
        content = "not chromadb here.\nAlso not chromadb there."
        source = Path("doc.md")

        claims = extract_technical_claims(content, source)

        chromadb_claims = [c for c in claims if "chromadb" in c.expected_value]
        assert len(chromadb_claims) == 1

    def test_custom_negation_patterns(self) -> None:
        """Custom negation patterns are appended to defaults."""
        content = "excludes tensorflow from the stack."
        source = Path("README.md")

        claims = extract_technical_claims(
            content, source, negation_patterns=[r"excludes\s+([a-zA-Z][a-zA-Z0-9_ ]{2,})"]
        )

        found = any("tensorflow" in c.expected_value for c in claims)
        assert found

    def test_verification_command_format(self) -> None:
        """Verification command uses grep_absent format."""
        content = "This system does not use chromadb."
        source = Path("README.md")

        claims = extract_technical_claims(content, source)

        chromadb_claims = [c for c in claims if "chromadb" in c.expected_value]
        assert len(chromadb_claims) >= 1
        assert "grep_absent" in chromadb_claims[0].verification_command


class TestExtractTimestampClaims:
    """Tests for timestamp claim extraction."""

    def test_T070_extracts_last_updated(self) -> None:
        """T070: Extract 'Last Updated: 2026-01-15' as TIMESTAMP."""
        content = "<!-- Last Updated: 2026-01-15 -->"
        source = Path("doc.md")

        claims = extract_timestamp_claims(content, source)

        assert len(claims) == 1
        assert claims[0].claim_type == ClaimType.TIMESTAMP
        assert claims[0].expected_value == "2026-01-15"

    def test_extracts_date_field(self) -> None:
        """Extract 'Date: 2026-02-17' as TIMESTAMP."""
        content = "Date: 2026-02-17"
        source = Path("doc.md")

        claims = extract_timestamp_claims(content, source)

        assert len(claims) >= 1
        assert claims[0].expected_value == "2026-02-17"

    def test_no_timestamp_returns_empty(self) -> None:
        """Content without timestamps returns empty list."""
        content = "# Just a title\n\nSome content."
        source = Path("doc.md")

        claims = extract_timestamp_claims(content, source)

        assert claims == []

    def test_verification_command_format(self) -> None:
        """Verification command uses check_freshness format."""
        content = "Last Updated: 2026-01-15"
        source = Path("doc.md")

        claims = extract_timestamp_claims(content, source)

        assert len(claims) >= 1
        assert claims[0].verification_command == "check_freshness 2026-01-15"

    def test_correct_line_number(self) -> None:
        """Line number is tracked correctly for timestamp claims."""
        content = "# Title\n\n<!-- Last Updated: 2026-01-15 -->"
        source = Path("doc.md")

        claims = extract_timestamp_claims(content, source)

        assert len(claims) >= 1
        assert claims[0].source_line == 3

    def test_case_insensitive_last_updated(self) -> None:
        """Case variations of 'Last Updated' are matched."""
        content = "last updated: 2026-01-15"
        source = Path("doc.md")

        claims = extract_timestamp_claims(content, source)

        assert len(claims) >= 1
        assert claims[0].expected_value == "2026-01-15"


class TestExtractClaimsFromMarkdown:
    """Tests for the top-level extraction function."""

    def test_T080_no_claims_in_simple_doc(self, tmp_path: Path) -> None:
        """T080: Return empty list for non-factual document."""
        doc = tmp_path / "hello.md"
        doc.write_text("# Hello\n\nJust a greeting.")

        claims = extract_claims_from_markdown(doc)

        assert claims == []

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Return empty list for nonexistent file."""
        claims = extract_claims_from_markdown(tmp_path / "nope.md")

        assert claims == []

    def test_filtered_claim_types(self, tmp_path: Path) -> None:
        """Only extract specified claim types."""
        doc = tmp_path / "mixed.md"
        doc.write_text("11 tools in tools/\nSee `tools/death.py`\nLast Updated: 2026-01-15")

        claims = extract_claims_from_markdown(doc, claim_types=[ClaimType.FILE_COUNT])

        assert all(c.claim_type == ClaimType.FILE_COUNT for c in claims)

    def test_extracts_all_types_by_default(self, tmp_path: Path) -> None:
        """Without claim_types filter, extracts all supported types."""
        doc = tmp_path / "mixed.md"
        doc.write_text(
            "11 tools in tools/\n"
            "See `tools/death.py` for details.\n"
            "Last Updated: 2026-01-15\n"
            "This project does not use chromadb."
        )

        claims = extract_claims_from_markdown(doc)

        claim_types = {c.claim_type for c in claims}
        assert ClaimType.FILE_COUNT in claim_types
        assert ClaimType.FILE_EXISTS in claim_types
        assert ClaimType.TIMESTAMP in claim_types
        assert ClaimType.TECHNICAL_FACT in claim_types

    def test_multiple_claim_types_filter(self, tmp_path: Path) -> None:
        """Filter to multiple claim types simultaneously."""
        doc = tmp_path / "mixed.md"
        doc.write_text(
            "11 tools in tools/\n"
            "See `tools/death.py` for details.\n"
            "Last Updated: 2026-01-15"
        )

        claims = extract_claims_from_markdown(
            doc, claim_types=[ClaimType.FILE_COUNT, ClaimType.TIMESTAMP]
        )

        claim_types = {c.claim_type for c in claims}
        assert ClaimType.FILE_EXISTS not in claim_types
        assert len(claims) >= 2

    def test_source_file_matches_input(self, tmp_path: Path) -> None:
        """All extracted claims reference the correct source file."""
        doc = tmp_path / "inventory.md"
        doc.write_text("5 tools in tools/\nSee `tools/real.py`.")

        claims = extract_claims_from_markdown(doc)

        for claim in claims:
            assert claim.source_file == doc

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_spelunking\test_verifiers.py
"""Tests for spelunking verification strategies.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from assemblyzero.spelunking.models import VerificationStatus
from assemblyzero.spelunking.verifiers import (
    _is_within_repo,
    verify_file_count,
    verify_file_exists,
    verify_no_contradiction,
    verify_timestamp_freshness,
    verify_unique_prefix,
)


class TestVerifyFileCount:
    """Tests for file count verification."""

    def test_T090_count_match(self, tmp_path: Path) -> None:
        """T090: File count matches expected."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(5):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        result = verify_file_count(tools, 5, "*.py")

        assert result.status == VerificationStatus.MATCH
        assert result.actual_value == "5"

    def test_T100_count_mismatch(self, tmp_path: Path) -> None:
        """T100: File count does not match expected."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(8):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        result = verify_file_count(tools, 5, "*.py")

        assert result.status == VerificationStatus.MISMATCH
        assert result.actual_value == "8"

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """Nonexistent directory returns ERROR."""
        result = verify_file_count(tmp_path / "nope", 5)

        assert result.status == VerificationStatus.ERROR

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns actual_value='0'."""
        empty = tmp_path / "empty"
        empty.mkdir()

        result = verify_file_count(empty, 0, "*.py")

        assert result.status == VerificationStatus.MATCH
        assert result.actual_value == "0"

    def test_empty_directory_mismatch(self, tmp_path: Path) -> None:
        """Empty directory with expected > 0 returns MISMATCH."""
        empty = tmp_path / "empty"
        empty.mkdir()

        result = verify_file_count(empty, 5, "*.py")

        assert result.status == VerificationStatus.MISMATCH
        assert result.actual_value == "0"

    def test_glob_pattern_filters(self, tmp_path: Path) -> None:
        """Glob pattern only counts matching files."""
        mixed = tmp_path / "mixed"
        mixed.mkdir()
        (mixed / "a.py").write_text("# python")
        (mixed / "b.py").write_text("# python")
        (mixed / "c.md").write_text("# markdown")
        (mixed / "d.txt").write_text("text")

        result = verify_file_count(mixed, 2, "*.py")

        assert result.status == VerificationStatus.MATCH
        assert result.actual_value == "2"

    def test_evidence_includes_pattern(self, tmp_path: Path) -> None:
        """Evidence string mentions the glob pattern used."""
        tools = tmp_path / "tools"
        tools.mkdir()
        (tools / "a.py").write_text("# a")

        result = verify_file_count(tools, 1, "*.py")

        assert "*.py" in result.evidence

    def test_error_message_on_missing_dir(self, tmp_path: Path) -> None:
        """Error message includes the directory path."""
        missing = tmp_path / "nonexistent"

        result = verify_file_count(missing, 5)

        assert result.status == VerificationStatus.ERROR
        assert "nonexistent" in (result.error_message or "")


class TestVerifyFileExists:
    """Tests for file existence verification."""

    def test_T110_file_exists(self, tmp_path: Path) -> None:
        """T110: Existing file returns MATCH."""
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "real.py").write_text("# real")

        result = verify_file_exists(Path("tools/real.py"), tmp_path)

        assert result.status == VerificationStatus.MATCH

    def test_T120_file_not_found(self, tmp_path: Path) -> None:
        """T120: Nonexistent file returns MISMATCH."""
        result = verify_file_exists(Path("tools/ghost.py"), tmp_path)

        assert result.status == VerificationStatus.MISMATCH

    def test_T190_path_traversal_rejected(self, tmp_path: Path) -> None:
        """T190: Path traversal attempt returns ERROR."""
        result = verify_file_exists(Path("../../etc/passwd"), tmp_path)

        assert result.status == VerificationStatus.ERROR
        assert "traversal" in (result.error_message or "").lower()

    def test_existing_file_evidence(self, tmp_path: Path) -> None:
        """Evidence confirms the file exists."""
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "real.py").write_text("# real")

        result = verify_file_exists(Path("tools/real.py"), tmp_path)

        assert "exists" in result.evidence.lower()

    def test_missing_file_evidence(self, tmp_path: Path) -> None:
        """Evidence mentions file not found."""
        result = verify_file_exists(Path("tools/ghost.py"), tmp_path)

        assert "not found" in result.evidence.lower()

    def test_nested_path(self, tmp_path: Path) -> None:
        """Nested file paths resolve correctly."""
        (tmp_path / "src" / "deep" / "nested").mkdir(parents=True)
        (tmp_path / "src" / "deep" / "nested" / "module.py").write_text("# nested")

        result = verify_file_exists(Path("src/deep/nested/module.py"), tmp_path)

        assert result.status == VerificationStatus.MATCH

    def test_actual_value_on_match(self, tmp_path: Path) -> None:
        """Actual value is set to the file path on match."""
        (tmp_path / "file.py").write_text("# file")

        result = verify_file_exists(Path("file.py"), tmp_path)

        assert result.actual_value == "file.py"


class TestVerifyNoContradiction:
    """Tests for contradiction detection."""

    def test_T130_term_absent(self, tmp_path: Path) -> None:
        """T130: Term not found in codebase returns MATCH."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("import os\nprint('hello')")

        result = verify_no_contradiction("chromadb", tmp_path)

        assert result.status == VerificationStatus.MATCH

    def test_T140_contradiction_found(self, tmp_path: Path) -> None:
        """T140: Term found in codebase returns MISMATCH."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "db.py").write_text("import chromadb\nclient = chromadb.Client()")

        result = verify_no_contradiction("chromadb", tmp_path)

        assert result.status == VerificationStatus.MISMATCH
        assert "chromadb" in result.evidence

    def test_short_term_unverifiable(self, tmp_path: Path) -> None:
        """Search term shorter than 3 chars is UNVERIFIABLE."""
        result = verify_no_contradiction("ab", tmp_path)

        assert result.status == VerificationStatus.UNVERIFIABLE

    def test_excludes_git_directory(self, tmp_path: Path) -> None:
        """Files in .git directory are excluded from search."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config.py").write_text("chromadb = True")

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("import os")

        result = verify_no_contradiction("chromadb", tmp_path)

        assert result.status == VerificationStatus.MATCH

    def test_excludes_pycache(self, tmp_path: Path) -> None:
        """Files in __pycache__ are excluded from search."""
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "cached.py").write_text("chromadb = True")

        (tmp_path / "main.py").write_text("import os")

        result = verify_no_contradiction("chromadb", tmp_path)

        assert result.status == VerificationStatus.MATCH

    def test_custom_exclude_dirs(self, tmp_path: Path) -> None:
        """Custom exclude_dirs are respected."""
        vendor = tmp_path / "vendor"
        vendor.mkdir()
        (vendor / "lib.py").write_text("import chromadb")

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("import os")

        result = verify_no_contradiction("chromadb", tmp_path, exclude_dirs=["vendor"])

        assert result.status == VerificationStatus.MATCH

    def test_evidence_includes_file_location(self, tmp_path: Path) -> None:
        """Evidence mentions the file where the term was found."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "db.py").write_text("import chromadb")

        result = verify_no_contradiction("chromadb", tmp_path)

        assert "db.py" in result.evidence

    def test_case_insensitive_search(self, tmp_path: Path) -> None:
        """Search is case-insensitive."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "db.py").write_text("import ChromaDB")

        result = verify_no_contradiction("chromadb", tmp_path)

        assert result.status == VerificationStatus.MISMATCH

    def test_empty_repo_returns_match(self, tmp_path: Path) -> None:
        """Empty repo (no .py files) returns MATCH."""
        result = verify_no_contradiction("chromadb", tmp_path)

        assert result.status == VerificationStatus.MATCH

    def test_max_matches_limited(self, tmp_path: Path) -> None:
        """At most 10 matches are reported in evidence."""
        (tmp_path / "src").mkdir()
        for i in range(15):
            (tmp_path / "src" / f"file_{i}.py").write_text("chromadb everywhere")

        result = verify_no_contradiction("chromadb", tmp_path)

        assert result.status == VerificationStatus.MISMATCH
        # Evidence should mention "+X more" if there are more than 1 match
        # The exact count depends on processing order, but the function caps at 10


class TestVerifyUniquePrefix:
    """Tests for unique prefix verification."""

    def test_T150_all_unique(self, tmp_path: Path) -> None:
        """T150: All unique prefixes returns MATCH."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0201-first.md").write_text("# ADR 0201")
        (adrs / "0202-second.md").write_text("# ADR 0202")
        (adrs / "0203-third.md").write_text("# ADR 0203")

        result = verify_unique_prefix(adrs)

        assert result.status == VerificationStatus.MATCH

    def test_T160_prefix_collision(self, tmp_path: Path) -> None:
        """T160: Duplicate prefix returns MISMATCH."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0204-first.md").write_text("# ADR 0204a")
        (adrs / "0204-second.md").write_text("# ADR 0204b")
        (adrs / "0205-third.md").write_text("# ADR 0205")

        result = verify_unique_prefix(adrs)

        assert result.status == VerificationStatus.MISMATCH
        assert "0204" in result.evidence

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """Nonexistent directory returns ERROR."""
        result = verify_unique_prefix(tmp_path / "nope")

        assert result.status == VerificationStatus.ERROR

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns MATCH (no collisions possible)."""
        empty = tmp_path / "empty"
        empty.mkdir()

        result = verify_unique_prefix(empty)

        assert result.status == VerificationStatus.MATCH

    def test_files_without_prefix_ignored(self, tmp_path: Path) -> None:
        """Files without matching prefix pattern are ignored."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "README.md").write_text("# ADRs")
        (adrs / "0201-first.md").write_text("# ADR 0201")
        (adrs / "notes.txt").write_text("notes")

        result = verify_unique_prefix(adrs)

        assert result.status == VerificationStatus.MATCH

    def test_multiple_collisions(self, tmp_path: Path) -> None:
        """Multiple prefix collisions are all reported."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0201-a.md").write_text("# a")
        (adrs / "0201-b.md").write_text("# b")
        (adrs / "0202-c.md").write_text("# c")
        (adrs / "0202-d.md").write_text("# d")
        (adrs / "0203-e.md").write_text("# e")

        result = verify_unique_prefix(adrs)

        assert result.status == VerificationStatus.MISMATCH
        assert "2 collision(s)" in (result.actual_value or "")

    def test_collision_evidence_lists_files(self, tmp_path: Path) -> None:
        """Collision evidence lists the conflicting filenames."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0204-first.md").write_text("# first")
        (adrs / "0204-second.md").write_text("# second")

        result = verify_unique_prefix(adrs)

        assert "0204-first.md" in result.evidence
        assert "0204-second.md" in result.evidence

    def test_custom_prefix_pattern(self, tmp_path: Path) -> None:
        """Custom prefix pattern is used for matching."""
        standards = tmp_path / "standards"
        standards.mkdir()
        (standards / "STD-001-first.md").write_text("# first")
        (standards / "STD-001-second.md").write_text("# second")

        result = verify_unique_prefix(standards, prefix_pattern=r"^STD-(\d{3})-")

        assert result.status == VerificationStatus.MISMATCH


class TestVerifyTimestampFreshness:
    """Tests for timestamp freshness verification."""

    def test_T170_fresh_timestamp(self) -> None:
        """T170: Date within threshold returns MATCH."""
        fresh_date = (date.today() - timedelta(days=5)).isoformat()

        result = verify_timestamp_freshness(fresh_date, max_age_days=30)

        assert result.status == VerificationStatus.MATCH

    def test_T180_stale_timestamp(self) -> None:
        """T180: Date beyond threshold returns STALE."""
        stale_date = (date.today() - timedelta(days=45)).isoformat()

        result = verify_timestamp_freshness(stale_date, max_age_days=30)

        assert result.status == VerificationStatus.STALE

    def test_unparseable_date(self) -> None:
        """Unparseable date returns ERROR."""
        result = verify_timestamp_freshness("not-a-date")

        assert result.status == VerificationStatus.ERROR

    def test_future_date_is_match(self) -> None:
        """Future date returns MATCH (0 days old)."""
        future_date = (date.today() + timedelta(days=10)).isoformat()

        result = verify_timestamp_freshness(future_date, max_age_days=30)

        assert result.status == VerificationStatus.MATCH

    def test_exactly_at_threshold(self) -> None:
        """Date exactly at threshold returns MATCH."""
        threshold_date = (date.today() - timedelta(days=30)).isoformat()

        result = verify_timestamp_freshness(threshold_date, max_age_days=30)

        assert result.status == VerificationStatus.MATCH

    def test_one_day_past_threshold(self) -> None:
        """Date one day past threshold returns STALE."""
        stale_date = (date.today() - timedelta(days=31)).isoformat()

        result = verify_timestamp_freshness(stale_date, max_age_days=30)

        assert result.status == VerificationStatus.STALE

    def test_evidence_includes_age(self, tmp_path: Path) -> None:
        """Evidence includes the age in days and threshold."""
        fresh_date = (date.today() - timedelta(days=5)).isoformat()

        result = verify_timestamp_freshness(fresh_date, max_age_days=30)

        assert "5 days old" in result.evidence
        assert "30 days" in result.evidence

    def test_actual_value_includes_age(self) -> None:
        """Actual value reports age in human-readable format."""
        test_date = (date.today() - timedelta(days=10)).isoformat()

        result = verify_timestamp_freshness(test_date, max_age_days=30)

        assert result.actual_value == "10 days old"

    def test_error_message_on_bad_date(self) -> None:
        """Error message includes the unparseable date string."""
        result = verify_timestamp_freshness("2026-99-99")

        assert result.status == VerificationStatus.ERROR
        assert "2026-99-99" in (result.error_message or "")

    def test_custom_max_age(self) -> None:
        """Custom max_age_days threshold is respected."""
        test_date = (date.today() - timedelta(days=10)).isoformat()

        result_short = verify_timestamp_freshness(test_date, max_age_days=5)
        result_long = verify_timestamp_freshness(test_date, max_age_days=30)

        assert result_short.status == VerificationStatus.STALE
        assert result_long.status == VerificationStatus.MATCH

    def test_today_returns_match(self) -> None:
        """Today's date returns MATCH with 0 days old."""
        today = date.today().isoformat()

        result = verify_timestamp_freshness(today, max_age_days=30)

        assert result.status == VerificationStatus.MATCH
        assert result.actual_value == "0 days old"


class TestIsWithinRepo:
    """Tests for path boundary checking."""

    def test_within_repo(self, tmp_path: Path) -> None:
        """Path within repo returns True."""
        child = tmp_path / "sub" / "file.py"
        assert _is_within_repo(child, tmp_path) is True

    def test_outside_repo(self, tmp_path: Path) -> None:
        """Path outside repo returns False."""
        outside = tmp_path / ".." / ".." / "etc" / "passwd"
        assert _is_within_repo(outside, tmp_path) is False

    def test_repo_root_itself(self, tmp_path: Path) -> None:
        """Repo root path itself returns True."""
        assert _is_within_repo(tmp_path, tmp_path) is True

    def test_deeply_nested_path(self, tmp_path: Path) -> None:
        """Deeply nested path within repo returns True."""
        deep = tmp_path / "a" / "b" / "c" / "d" / "e.py"
        assert _is_within_repo(deep, tmp_path) is True

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_spelunking\test_probes.py
"""Tests for all six automated spelunking probes.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from assemblyzero.workflows.janitor.probes.inventory_drift import (
    probe_inventory_drift,
)
from assemblyzero.workflows.janitor.probes.dead_references import (
    probe_dead_references,
)
from assemblyzero.workflows.janitor.probes.adr_collision import (
    probe_adr_collision,
)
from assemblyzero.workflows.janitor.probes.stale_timestamps import (
    probe_stale_timestamps,
)
from assemblyzero.workflows.janitor.probes.readme_claims import (
    probe_readme_claims,
)
from assemblyzero.workflows.janitor.probes.persona_status import (
    probe_persona_status,
)


class TestInventoryDriftProbe:
    """Tests for inventory drift probe."""

    def test_T200_drift_detected(self, tmp_path: Path) -> None:
        """T200: Inventory says 5, actual 8 -> passed=False."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(8):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        inventory = tmp_path / "inventory.md"
        inventory.write_text("5 tools in tools/")

        result = probe_inventory_drift(tmp_path, inventory_path=inventory)

        assert result.passed is False
        assert len(result.findings) >= 1

    def test_T210_inventory_matches(self, tmp_path: Path) -> None:
        """T210: Inventory says 3, actual 3 -> passed=True."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(3):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        inventory = tmp_path / "inventory.md"
        inventory.write_text("3 tools in tools/")

        result = probe_inventory_drift(tmp_path, inventory_path=inventory)

        assert result.passed is True

    def test_missing_inventory(self, tmp_path: Path) -> None:
        """Missing inventory file -> passed=True, skipping."""
        result = probe_inventory_drift(tmp_path)

        assert result.passed is True
        assert "not found" in result.summary.lower() or "skipping" in result.summary.lower()

    def test_probe_name(self, tmp_path: Path) -> None:
        """Probe result has correct probe_name."""
        result = probe_inventory_drift(tmp_path)

        assert result.probe_name == "inventory_drift"

    def test_execution_time_measured(self, tmp_path: Path) -> None:
        """Execution time is a positive number."""
        result = probe_inventory_drift(tmp_path)

        assert result.execution_time_ms >= 0

    def test_no_count_claims_in_inventory(self, tmp_path: Path) -> None:
        """Inventory file with no parseable count claims -> passed=True."""
        inventory = tmp_path / "inventory.md"
        inventory.write_text("# Inventory\n\nJust some text, no counts.")

        result = probe_inventory_drift(tmp_path, inventory_path=inventory)

        assert result.passed is True

    def test_multiple_mismatches(self, tmp_path: Path) -> None:
        """Multiple directory count mismatches are all reported."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(8):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        docs_adrs = tmp_path / "docs" / "adrs"
        docs_adrs.mkdir(parents=True)
        for i in range(5):
            (docs_adrs / f"000{i}-adr.md").write_text(f"# ADR {i}")

        inventory = tmp_path / "inventory.md"
        inventory.write_text("5 tools in tools/\n3 ADRs in docs/adrs/")

        result = probe_inventory_drift(tmp_path, inventory_path=inventory)

        assert result.passed is False
        assert len(result.findings) >= 1

    def test_summary_contains_mismatch_details(self, tmp_path: Path) -> None:
        """Summary string includes mismatch details when drift detected."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(8):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        inventory = tmp_path / "inventory.md"
        inventory.write_text("5 tools in tools/")

        result = probe_inventory_drift(tmp_path, inventory_path=inventory)

        assert "mismatch" in result.summary.lower()


class TestDeadReferencesProbe:
    """Tests for dead references probe."""

    def test_T220_dead_ref_found(self, tmp_path: Path) -> None:
        """T220: Doc references ghost.py -> passed=False."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("See `tools/ghost.py` for details.")

        result = probe_dead_references(tmp_path, doc_dirs=[docs])

        assert result.passed is False
        assert len(result.findings) >= 1

    def test_T230_all_refs_valid(self, tmp_path: Path) -> None:
        """T230: Doc references existing file -> passed=True."""
        tools = tmp_path / "tools"
        tools.mkdir()
        (tools / "real.py").write_text("# real")

        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("See `tools/real.py` for details.")

        result = probe_dead_references(tmp_path, doc_dirs=[docs])

        assert result.passed is True

    def test_probe_name(self, tmp_path: Path) -> None:
        """Probe result has correct probe_name."""
        result = probe_dead_references(tmp_path, doc_dirs=[tmp_path])

        assert result.probe_name == "dead_references"

    def test_no_markdown_files(self, tmp_path: Path) -> None:
        """No markdown files -> passed=True, empty findings."""
        docs = tmp_path / "docs"
        docs.mkdir()

        result = probe_dead_references(tmp_path, doc_dirs=[docs])

        assert result.passed is True
        assert len(result.findings) == 0

    def test_multiple_dead_refs(self, tmp_path: Path) -> None:
        """Multiple dead references are all reported."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text(
            "See `tools/ghost1.py` and `tools/ghost2.py` for details."
        )

        result = probe_dead_references(tmp_path, doc_dirs=[docs])

        assert result.passed is False
        assert len(result.findings) >= 2

    def test_summary_lists_dead_paths(self, tmp_path: Path) -> None:
        """Summary includes the dead reference paths."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("See `tools/ghost.py` for details.")

        result = probe_dead_references(tmp_path, doc_dirs=[docs])

        assert "dead reference" in result.summary.lower()

    def test_execution_time_measured(self, tmp_path: Path) -> None:
        """Execution time is a positive number."""
        result = probe_dead_references(tmp_path, doc_dirs=[tmp_path])

        assert result.execution_time_ms >= 0

    def test_nonexistent_doc_dir(self, tmp_path: Path) -> None:
        """Nonexistent doc directory is handled gracefully."""
        result = probe_dead_references(
            tmp_path, doc_dirs=[tmp_path / "nonexistent"]
        )

        assert result.passed is True


class TestAdrCollisionProbe:
    """Tests for ADR collision probe."""

    def test_T240_collision_detected(self, tmp_path: Path) -> None:
        """T240: Duplicate prefix 0204 -> passed=False."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0204-first.md").write_text("# First")
        (adrs / "0204-second.md").write_text("# Second")

        result = probe_adr_collision(tmp_path, adr_dir=adrs)

        assert result.passed is False
        assert len(result.findings) >= 1

    def test_T250_no_collisions(self, tmp_path: Path) -> None:
        """T250: All unique prefixes -> passed=True."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0201-first.md").write_text("# First")
        (adrs / "0202-second.md").write_text("# Second")

        result = probe_adr_collision(tmp_path, adr_dir=adrs)

        assert result.passed is True

    def test_probe_name(self, tmp_path: Path) -> None:
        """Probe result has correct probe_name."""
        result = probe_adr_collision(tmp_path)

        assert result.probe_name == "adr_collision"

    def test_missing_adr_dir(self, tmp_path: Path) -> None:
        """Missing ADR directory -> passed=True, skipping."""
        result = probe_adr_collision(tmp_path)

        assert result.passed is True
        assert "not found" in result.summary.lower() or "skipping" in result.summary.lower()

    def test_empty_adr_dir(self, tmp_path: Path) -> None:
        """Empty ADR directory -> passed=True."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()

        result = probe_adr_collision(tmp_path, adr_dir=adrs)

        assert result.passed is True

    def test_multiple_collisions(self, tmp_path: Path) -> None:
        """Multiple prefix collisions are all detected."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0201-a.md").write_text("# a")
        (adrs / "0201-b.md").write_text("# b")
        (adrs / "0202-c.md").write_text("# c")
        (adrs / "0202-d.md").write_text("# d")

        result = probe_adr_collision(tmp_path, adr_dir=adrs)

        assert result.passed is False
        assert len(result.findings) >= 2

    def test_collision_evidence_includes_prefix(self, tmp_path: Path) -> None:
        """Collision evidence mentions the colliding prefix."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0204-first.md").write_text("# First")
        (adrs / "0204-second.md").write_text("# Second")

        result = probe_adr_collision(tmp_path, adr_dir=adrs)

        assert any("0204" in f.evidence for f in result.findings)

    def test_execution_time_measured(self, tmp_path: Path) -> None:
        """Execution time is a positive number."""
        result = probe_adr_collision(tmp_path)

        assert result.execution_time_ms >= 0


class TestStaleTimestampsProbe:
    """Tests for stale timestamps probe."""

    def test_T260_stale_found(self, tmp_path: Path) -> None:
        """T260: Document with old date -> passed=False."""
        docs = tmp_path / "docs"
        docs.mkdir()
        stale_date = (date.today() - timedelta(days=45)).isoformat()
        (docs / "old.md").write_text(f"<!-- Last Updated: {stale_date} -->\n# Old")

        result = probe_stale_timestamps(tmp_path, doc_dirs=[docs])

        assert result.passed is False

    def test_T270_all_fresh(self, tmp_path: Path) -> None:
        """T270: Document with recent date -> passed=True."""
        docs = tmp_path / "docs"
        docs.mkdir()
        fresh_date = (date.today() - timedelta(days=5)).isoformat()
        (docs / "fresh.md").write_text(f"<!-- Last Updated: {fresh_date} -->\n# Fresh")

        result = probe_stale_timestamps(tmp_path, doc_dirs=[docs])

        assert result.passed is True

    def test_T275_stale_and_missing_timestamps(self, tmp_path: Path) -> None:
        """T275: Stale doc + missing timestamp doc -> passed=False with 2+ findings."""
        docs = tmp_path / "docs"
        docs.mkdir()

        stale_date = (date.today() - timedelta(days=45)).isoformat()
        (docs / "stale.md").write_text(f"<!-- Last Updated: {stale_date} -->\n# Stale")
        (docs / "missing.md").write_text("# No Timestamp Here\n\nJust content.")

        result = probe_stale_timestamps(tmp_path, doc_dirs=[docs])

        assert result.passed is False
        assert len(result.findings) >= 2

    def test_probe_name(self, tmp_path: Path) -> None:
        """Probe result has correct probe_name."""
        result = probe_stale_timestamps(tmp_path, doc_dirs=[tmp_path])

        assert result.probe_name == "stale_timestamps"

    def test_no_markdown_files(self, tmp_path: Path) -> None:
        """No markdown files -> passed=True."""
        docs = tmp_path / "docs"
        docs.mkdir()

        result = probe_stale_timestamps(tmp_path, doc_dirs=[docs])

        assert result.passed is True

    def test_missing_timestamp_only(self, tmp_path: Path) -> None:
        """Document with missing timestamp -> passed=False."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "missing.md").write_text("# No Timestamp\n\nJust content.")

        result = probe_stale_timestamps(tmp_path, doc_dirs=[docs])

        assert result.passed is False
        assert any(
            f.claim.claim_text == "missing timestamp" for f in result.findings
        )

    def test_custom_max_age(self, tmp_path: Path) -> None:
        """Custom max_age_days threshold is respected."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_date = (date.today() - timedelta(days=10)).isoformat()
        (docs / "doc.md").write_text(f"<!-- Last Updated: {test_date} -->\n# Doc")

        result_short = probe_stale_timestamps(tmp_path, max_age_days=5, doc_dirs=[docs])
        result_long = probe_stale_timestamps(tmp_path, max_age_days=30, doc_dirs=[docs])

        assert result_short.passed is False
        assert result_long.passed is True

    def test_summary_counts_stale_and_missing(self, tmp_path: Path) -> None:
        """Summary distinguishes stale vs missing timestamps."""
        docs = tmp_path / "docs"
        docs.mkdir()

        stale_date = (date.today() - timedelta(days=45)).isoformat()
        (docs / "stale.md").write_text(f"<!-- Last Updated: {stale_date} -->\n# Stale")
        (docs / "missing.md").write_text("# No Timestamp\n\nJust content.")

        result = probe_stale_timestamps(tmp_path, doc_dirs=[docs])

        assert "stale" in result.summary.lower() or "missing" in result.summary.lower()

    def test_execution_time_measured(self, tmp_path: Path) -> None:
        """Execution time is a positive number."""
        result = probe_stale_timestamps(tmp_path, doc_dirs=[tmp_path])

        assert result.execution_time_ms >= 0


class TestReadmeClaimsProbe:
    """Tests for README claims probe."""

    def test_T280_contradiction_found(self, tmp_path: Path) -> None:
        """T280: README says 'not chromadb' but code has it -> passed=False."""
        readme = tmp_path / "README.md"
        readme.write_text("This system does not use chromadb for storage.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "db.py").write_text("import chromadb\nclient = chromadb.Client()")

        result = probe_readme_claims(tmp_path, readme_path=readme)

        assert result.passed is False

    def test_T290_claims_valid(self, tmp_path: Path) -> None:
        """T290: README says 'not quantum' and no quantum code -> passed=True."""
        readme = tmp_path / "README.md"
        readme.write_text("This system does not use quantum computing.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("import os\nprint('hello')")

        result = probe_readme_claims(tmp_path, readme_path=readme)

        assert result.passed is True

    def test_probe_name(self, tmp_path: Path) -> None:
        """Probe result has correct probe_name."""
        result = probe_readme_claims(tmp_path)

        assert result.probe_name == "readme_claims"

    def test_missing_readme(self, tmp_path: Path) -> None:
        """Missing README -> passed=True, skipping."""
        result = probe_readme_claims(tmp_path)

        assert result.passed is True
        assert "not found" in result.summary.lower() or "skipping" in result.summary.lower()

    def test_no_negation_claims(self, tmp_path: Path) -> None:
        """README with no negation claims -> passed=True."""
        readme = tmp_path / "README.md"
        readme.write_text("# My Project\n\nThis is a great project.")

        result = probe_readme_claims(tmp_path, readme_path=readme)

        assert result.passed is True

    def test_summary_lists_contradicted_terms(self, tmp_path: Path) -> None:
        """Summary includes the contradicted terms."""
        readme = tmp_path / "README.md"
        readme.write_text("This system does not use chromadb for storage.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "db.py").write_text("import chromadb")

        result = probe_readme_claims(tmp_path, readme_path=readme)

        assert "contradiction" in result.summary.lower()

    def test_execution_time_measured(self, tmp_path: Path) -> None:
        """Execution time is a positive number."""
        result = probe_readme_claims(tmp_path)

        assert result.execution_time_ms >= 0


class TestPersonaStatusProbe:
    """Tests for persona status probe."""

    def test_T300_persona_gaps(self, tmp_path: Path) -> None:
        """T300: 2 of 5 personas missing status -> passed=False."""
        persona = tmp_path / "personas.md"
        persona.write_text(
            "# Dramatis Personae\n\n"
            "## The Architect\n\nStatus: implemented\n\nDesigns things.\n\n"
            "## The Builder\n\nStatus: implemented\n\nBuilds things.\n\n"
            "## The Tester\n\nStatus: implemented\n\nTests things.\n\n"
            "## The Reviewer\n\nReviews code.\n\n"
            "## The Planner\n\nPlans things.\n"
        )

        result = probe_persona_status(tmp_path, persona_file=persona)

        assert result.passed is False
        assert len(result.findings) == 2

    def test_all_personas_have_status(self, tmp_path: Path) -> None:
        """All personas with status markers -> passed=True."""
        persona = tmp_path / "personas.md"
        persona.write_text(
            "# Dramatis Personae\n\n"
            "## The Architect\n\nStatus: implemented\n\n"
            "## The Builder\n\nStatus: active\n\n"
        )

        result = probe_persona_status(tmp_path, persona_file=persona)

        assert result.passed is True

    def test_probe_name(self, tmp_path: Path) -> None:
        """Probe result has correct probe_name."""
        result = probe_persona_status(tmp_path)

        assert result.probe_name == "persona_status"

    def test_missing_persona_file(self, tmp_path: Path) -> None:
        """Missing persona file -> passed=True, skipping."""
        result = probe_persona_status(tmp_path)

        assert result.passed is True
        assert "not found" in result.summary.lower() or "skipping" in result.summary.lower()

    def test_summary_counts_gaps(self, tmp_path: Path) -> None:
        """Summary reports how many personas are missing status."""
        persona = tmp_path / "personas.md"
        persona.write_text(
            "# Dramatis Personae\n\n"
            "## The Architect\n\nStatus: implemented\n\n"
            "## The Reviewer\n\nReviews code.\n\n"
            "## The Planner\n\nPlans things.\n"
        )

        result = probe_persona_status(tmp_path, persona_file=persona)

        assert "2" in result.summary
        assert "3" in result.summary

    def test_findings_reference_persona_names(self, tmp_path: Path) -> None:
        """Findings mention the specific persona names that are missing status."""
        persona = tmp_path / "personas.md"
        persona.write_text(
            "# Dramatis Personae\n\n"
            "## The Architect\n\nStatus: implemented\n\n"
            "## The Reviewer\n\nReviews code.\n\n"
        )

        result = probe_persona_status(tmp_path, persona_file=persona)

        assert result.passed is False
        finding_texts = [f.claim.claim_text for f in result.findings]
        assert any("Reviewer" in t for t in finding_texts)

    def test_execution_time_measured(self, tmp_path: Path) -> None:
        """Execution time is a positive number."""
        result = probe_persona_status(tmp_path)

        assert result.execution_time_ms >= 0

    def test_various_status_values_accepted(self, tmp_path: Path) -> None:
        """All valid status values (implemented, active, planned, deprecated, draft) are accepted."""
        persona = tmp_path / "personas.md"
        persona.write_text(
            "# Dramatis Personae\n\n"
            "## Alpha\n\nStatus: implemented\n\n"
            "## Beta\n\nStatus: active\n\n"
            "## Gamma\n\nStatus: planned\n\n"
            "## Delta\n\nStatus: deprecated\n\n"
            "## Epsilon\n\nStatus: draft\n\n"
        )

        result = probe_persona_status(tmp_path, persona_file=persona)

        assert result.passed is True
        assert len(result.findings) == 0

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_spelunking\test_report.py
"""Tests for drift report generation.

Issue #534: Spelunking Audits
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
    _format_verification_row,
    generate_drift_report,
    generate_probe_summary,
)


def _make_result(status: VerificationStatus, claim_text: str = "test claim") -> VerificationResult:
    """Helper to create a VerificationResult with minimal boilerplate."""
    return VerificationResult(
        claim=Claim(
            claim_type=ClaimType.FILE_COUNT,
            source_file=Path("test.md"),
            source_line=1,
            claim_text=claim_text,
            expected_value="5",
            verification_command="test",
        ),
        status=status,
        actual_value="5" if status == VerificationStatus.MATCH else "8",
    )


class TestDriftScore:
    """Tests for drift score calculation."""

    def test_T310_drift_score_calculation(self) -> None:
        """T310: 8 MATCH + 2 MISMATCH -> drift_score == 80.0."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(8)]
        results += [_make_result(VerificationStatus.MISMATCH) for _ in range(2)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.drift_score == 80.0

    def test_T350_unverifiable_excluded(self) -> None:
        """T350: 5 MATCH + 3 UNVERIFIABLE -> drift_score == 100.0."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(5)]
        results += [_make_result(VerificationStatus.UNVERIFIABLE) for _ in range(3)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.drift_score == 100.0

    def test_all_match(self) -> None:
        """All matching claims -> drift_score == 100.0."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(5)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.drift_score == 100.0

    def test_all_mismatch(self) -> None:
        """All mismatched claims -> drift_score == 0.0."""
        results = [_make_result(VerificationStatus.MISMATCH) for _ in range(5)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.drift_score == 0.0

    def test_empty_results(self) -> None:
        """No results -> drift_score == 100.0."""
        report = DriftReport(
            target_document=Path("test.md"),
            results=[],
        )

        assert report.drift_score == 100.0

    def test_only_unverifiable(self) -> None:
        """Only UNVERIFIABLE results -> drift_score == 100.0."""
        results = [_make_result(VerificationStatus.UNVERIFIABLE) for _ in range(3)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.drift_score == 100.0

    def test_total_claims(self) -> None:
        """total_claims returns count of all results."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(3)]
        results += [_make_result(VerificationStatus.MISMATCH) for _ in range(2)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.total_claims == 5

    def test_matching_claims(self) -> None:
        """matching_claims returns count of MATCH results only."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(3)]
        results += [_make_result(VerificationStatus.MISMATCH) for _ in range(2)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.matching_claims == 3

    def test_stale_counted_as_non_match(self) -> None:
        """STALE results count against drift score."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(4)]
        results += [_make_result(VerificationStatus.STALE)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.drift_score == 80.0

    def test_error_counted_as_non_match(self) -> None:
        """ERROR results count against drift score."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(4)]
        results += [_make_result(VerificationStatus.ERROR)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.drift_score == 80.0


class TestGenerateDriftReport:
    """Tests for drift report generation."""

    def test_T320_markdown_report(self) -> None:
        """T320: Generate valid Markdown with tables."""
        results = [
            _make_result(VerificationStatus.MATCH, "match claim"),
            _make_result(VerificationStatus.MISMATCH, "mismatch claim"),
        ]
        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "# Spelunking Drift Report" in output
        assert "| Metric | Value |" in output
        assert "Total Claims | 2" in output
        assert "[FAIL]" in output or "[PASS]" in output

    def test_T325_json_report(self) -> None:
        """T325: Generate valid JSON with all fields."""
        results = [
            _make_result(VerificationStatus.MATCH),
            _make_result(VerificationStatus.MISMATCH),
            _make_result(VerificationStatus.STALE),
        ]
        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        output = generate_drift_report(report, output_format="json")
        data = json.loads(output)

        assert "drift_score" in data
        assert "results" in data
        assert "target_document" in data
        assert len(data["results"]) == 3

    def test_T327_invalid_format_raises(self) -> None:
        """T327: Invalid format raises ValueError."""
        report = DriftReport(
            target_document=Path("test.md"),
            results=[],
        )

        with pytest.raises(ValueError, match="Unsupported output format"):
            generate_drift_report(report, output_format="xml")

    def test_markdown_includes_target(self) -> None:
        """Markdown report includes target document path."""
        report = DriftReport(
            target_document=Path("README.md"),
            results=[],
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "README.md" in output

    def test_markdown_includes_generated_timestamp(self) -> None:
        """Markdown report includes generated timestamp."""
        report = DriftReport(
            target_document=Path("test.md"),
            results=[],
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "**Generated:**" in output

    def test_markdown_includes_drift_score(self) -> None:
        """Markdown report includes drift score with badge."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(5)]
        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "[PASS]" in output
        assert "100.0%" in output

    def test_markdown_fail_badge_for_low_score(self) -> None:
        """Markdown report shows [FAIL] for low drift score."""
        results = [_make_result(VerificationStatus.MATCH)]
        results += [_make_result(VerificationStatus.MISMATCH) for _ in range(9)]
        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "[FAIL]" in output

    def test_markdown_summary_table_counts(self) -> None:
        """Markdown summary table includes correct counts."""
        results = [
            _make_result(VerificationStatus.MATCH),
            _make_result(VerificationStatus.MISMATCH),
            _make_result(VerificationStatus.STALE),
            _make_result(VerificationStatus.ERROR),
        ]
        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "Matching | 1" in output
        assert "Mismatches | 1" in output
        assert "Stale | 1" in output
        assert "Errors | 1" in output

    def test_markdown_claim_details_section(self) -> None:
        """Markdown report includes Claim Details section with table rows."""
        results = [
            _make_result(VerificationStatus.MATCH, "match claim"),
            _make_result(VerificationStatus.MISMATCH, "mismatch claim"),
        ]
        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "## Claim Details" in output
        assert "match claim" in output
        assert "mismatch claim" in output

    def test_markdown_empty_results_no_details(self) -> None:
        """Markdown report with empty results has no Claim Details section."""
        report = DriftReport(
            target_document=Path("test.md"),
            results=[],
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "## Claim Details" not in output
        assert "Total Claims | 0" in output

    def test_json_includes_all_result_fields(self) -> None:
        """JSON report includes all expected fields per result."""
        result = VerificationResult(
            claim=Claim(
                claim_type=ClaimType.FILE_EXISTS,
                source_file=Path("README.md"),
                source_line=10,
                claim_text="tools/death.py",
                expected_value="tools/death.py",
                verification_command="path_exists tools/death.py",
            ),
            status=VerificationStatus.MATCH,
            actual_value="tools/death.py",
            evidence="File exists at tools/death.py",
        )
        report = DriftReport(
            target_document=Path("README.md"),
            results=[result],
        )

        output = generate_drift_report(report, output_format="json")
        data = json.loads(output)

        r = data["results"][0]
        assert r["claim_type"] == "file_exists"
        assert r["source_file"] == "README.md"
        assert r["source_line"] == 10
        assert r["claim_text"] == "tools/death.py"
        assert r["status"] == "match"
        assert r["expected_value"] == "tools/death.py"
        assert r["actual_value"] == "tools/death.py"
        assert r["evidence"] == "File exists at tools/death.py"

    def test_json_empty_results(self) -> None:
        """JSON report with no results has empty results array."""
        report = DriftReport(
            target_document=Path("test.md"),
            results=[],
        )

        output = generate_drift_report(report, output_format="json")
        data = json.loads(output)

        assert data["results"] == []
        assert data["drift_score"] == 100.0
        assert data["total_claims"] == 0

    def test_json_drift_score_value(self) -> None:
        """JSON report drift_score matches DriftReport property."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(8)]
        results += [_make_result(VerificationStatus.MISMATCH) for _ in range(2)]
        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        output = generate_drift_report(report, output_format="json")
        data = json.loads(output)

        assert data["drift_score"] == 80.0

    def test_default_format_is_markdown(self) -> None:
        """Default output format is markdown."""
        report = DriftReport(
            target_document=Path("test.md"),
            results=[_make_result(VerificationStatus.MATCH)],
        )

        output = generate_drift_report(report)

        assert "# Spelunking Drift Report" in output


class TestGenerateProbeSummary:
    """Tests for probe summary generation."""

    def test_T330_probe_summary_table(self) -> None:
        """T330: 3 ProbeResults -> Markdown table with [PASS]/[FAIL]."""
        probes = [
            ProbeResult(probe_name="probe_a", findings=[], passed=True, summary="OK", execution_time_ms=10.0),
            ProbeResult(probe_name="probe_b", findings=[_make_result(VerificationStatus.MISMATCH)], passed=False, summary="Bad", execution_time_ms=20.0),
            ProbeResult(probe_name="probe_c", findings=[], passed=True, summary="OK", execution_time_ms=15.0),
        ]

        output = generate_probe_summary(probes)

        assert "[PASS]" in output
        assert "[FAIL]" in output
        assert "probe_a" in output
        assert "probe_b" in output
        assert "probe_c" in output

    def test_T335_totals_row(self) -> None:
        """T335: 6 ProbeResults -> totals row with counts."""
        probes = [
            ProbeResult(probe_name=f"probe_{i}", findings=[], passed=(i < 4), summary="", execution_time_ms=10.0 * (i + 1))
            for i in range(6)
        ]

        output = generate_probe_summary(probes)

        assert "**Totals**" in output
        assert "4 passed" in output
        assert "2 failed" in output

    def test_empty_probe_list(self) -> None:
        """Empty list produces header with zero totals."""
        output = generate_probe_summary([])

        assert "# Probe Summary" in output
        assert "0 passed" in output
        assert "0 failed" in output

    def test_all_passed(self) -> None:
        """All probes passed shows correct totals."""
        probes = [
            ProbeResult(probe_name=f"probe_{i}", findings=[], passed=True, summary="OK", execution_time_ms=10.0)
            for i in range(3)
        ]

        output = generate_probe_summary(probes)

        assert "3 passed" in output
        assert "0 failed" in output

    def test_all_failed(self) -> None:
        """All probes failed shows correct totals."""
        probes = [
            ProbeResult(probe_name=f"probe_{i}", findings=[_make_result(VerificationStatus.MISMATCH)], passed=False, summary="Bad", execution_time_ms=10.0)
            for i in range(3)
        ]

        output = generate_probe_summary(probes)

        assert "0 passed" in output
        assert "3 failed" in output

    def test_findings_count_in_table(self) -> None:
        """Finding count is shown in the table."""
        findings = [_make_result(VerificationStatus.MISMATCH) for _ in range(3)]
        probes = [
            ProbeResult(probe_name="probe_a", findings=findings, passed=False, summary="Bad", execution_time_ms=20.0),
        ]

        output = generate_probe_summary(probes)

        # The table row should contain "3" as findings count
        lines = output.splitlines()
        probe_line = [l for l in lines if "probe_a" in l]
        assert len(probe_line) == 1
        assert "3" in probe_line[0]

    def test_execution_time_in_table(self) -> None:
        """Execution time is shown in the table."""
        probes = [
            ProbeResult(probe_name="probe_a", findings=[], passed=True, summary="OK", execution_time_ms=45.2),
        ]

        output = generate_probe_summary(probes)

        assert "45.2" in output

    def test_total_time_summed(self) -> None:
        """Total execution time is the sum of all probe times."""
        probes = [
            ProbeResult(probe_name="probe_a", findings=[], passed=True, summary="OK", execution_time_ms=10.0),
            ProbeResult(probe_name="probe_b", findings=[], passed=True, summary="OK", execution_time_ms=20.0),
            ProbeResult(probe_name="probe_c", findings=[], passed=True, summary="OK", execution_time_ms=30.0),
        ]

        output = generate_probe_summary(probes)

        assert "60.0" in output

    def test_total_findings_summed(self) -> None:
        """Total findings count is sum of all probe findings."""
        probes = [
            ProbeResult(probe_name="probe_a", findings=[_make_result(VerificationStatus.MISMATCH)], passed=False, summary="Bad", execution_time_ms=10.0),
            ProbeResult(probe_name="probe_b", findings=[_make_result(VerificationStatus.MISMATCH), _make_result(VerificationStatus.MISMATCH)], passed=False, summary="Bad", execution_time_ms=10.0),
        ]

        output = generate_probe_summary(probes)

        # Totals row should contain total findings of 3
        lines = output.splitlines()
        totals_line = [l for l in lines if "**Totals**" in l]
        assert len(totals_line) == 1
        assert "**3**" in totals_line[0]

    def test_header_present(self) -> None:
        """Output starts with # Probe Summary header."""
        output = generate_probe_summary([])

        assert output.startswith("# Probe Summary")

    def test_table_header_present(self) -> None:
        """Output includes table header row."""
        output = generate_probe_summary([])

        assert "| Probe | Status | Findings | Time (ms) |" in output


class TestFormatVerificationRow:
    """Tests for verification row formatting."""

    def test_basic_row(self) -> None:
        """Basic row formatting includes all fields."""
        result = VerificationResult(
            claim=Claim(
                claim_type=ClaimType.FILE_COUNT,
                source_file=Path("README.md"),
                source_line=5,
                claim_text="11 tools",
                expected_value="11",
                verification_command="glob tools/*.py | count",
            ),
            status=VerificationStatus.MISMATCH,
            actual_value="36",
            evidence="Found 36 .py files",
        )

        row = _format_verification_row(result)

        assert "README.md" in row
        assert "5" in row
        assert "11 tools" in row
        assert "MISMATCH" in row
        assert "11" in row
        assert "36" in row

    def test_long_claim_text_truncated(self) -> None:
        """Claim text longer than 50 chars is truncated with ..."""
        long_text = "a" * 60
        result = VerificationResult(
            claim=Claim(
                claim_type=ClaimType.FILE_COUNT,
                source_file=Path("test.md"),
                source_line=1,
                claim_text=long_text,
                expected_value="5",
                verification_command="test",
            ),
            status=VerificationStatus.MATCH,
            actual_value="5",
        )

        row = _format_verification_row(result)

        assert long_text not in row
        assert "..." in row

    def test_long_evidence_truncated(self) -> None:
        """Evidence longer than 100 chars is truncated with ..."""
        long_evidence = "b" * 120
        result = VerificationResult(
            claim=Claim(
                claim_type=ClaimType.FILE_COUNT,
                source_file=Path("test.md"),
                source_line=1,
                claim_text="test",
                expected_value="5",
                verification_command="test",
            ),
            status=VerificationStatus.MATCH,
            actual_value="5",
            evidence=long_evidence,
        )

        row = _format_verification_row(result)

        assert long_evidence not in row
        assert "..." in row

    def test_none_actual_value_shows_dash(self) -> None:
        """None actual_value displays as '-'."""
        result = VerificationResult(
            claim=Claim(
                claim_type=ClaimType.FILE_EXISTS,
                source_file=Path("test.md"),
                source_line=1,
                claim_text="tools/ghost.py",
                expected_value="tools/ghost.py",
                verification_command="path_exists tools/ghost.py",
            ),
            status=VerificationStatus.MISMATCH,
            actual_value=None,
            evidence="File not found",
        )

        row = _format_verification_row(result)

        # Row has pipe-delimited fields; the "actual" field should be "-"
        parts = [p.strip() for p in row.split("|")]
        # Filter out empty strings from leading/trailing pipes
        parts = [p for p in parts if p]
        # parts: [source, line, claim, status, expected, actual, evidence]
        assert parts[5] == "-"

    def test_status_uppercase(self) -> None:
        """Status is displayed in uppercase."""
        result = _make_result(VerificationStatus.MATCH)

        row = _format_verification_row(result)

        assert "MATCH" in row

    def test_short_claim_not_truncated(self) -> None:
        """Claim text shorter than 50 chars is not truncated."""
        short_text = "short claim"
        result = VerificationResult(
            claim=Claim(
                claim_type=ClaimType.FILE_COUNT,
                source_file=Path("test.md"),
                source_line=1,
                claim_text=short_text,
                expected_value="5",
                verification_command="test",
            ),
            status=VerificationStatus.MATCH,
            actual_value="5",
        )

        row = _format_verification_row(result)

        assert short_text in row


class TestFormatDriftScoreBadge:
    """Tests for drift score badge formatting."""

    def test_pass_badge(self) -> None:
        """Score >= 90 gets [PASS] badge."""
        assert _format_drift_score_badge(95.0) == "[PASS] 95.0%"

    def test_fail_badge(self) -> None:
        """Score < 90 gets [FAIL] badge."""
        assert _format_drift_score_badge(75.0) == "[FAIL] 75.0%"

    def test_threshold_boundary(self) -> None:
        """Exactly 90.0 gets [PASS] badge."""
        assert _format_drift_score_badge(90.0) == "[PASS] 90.0%"

    def test_zero_score(self) -> None:
        """Score of 0.0 gets [FAIL] badge."""
        assert _format_drift_score_badge(0.0) == "[FAIL] 0.0%"

    def test_100_score(self) -> None:
        """Score of 100.0 gets [PASS] badge."""
        assert _format_drift_score_badge(100.0) == "[PASS] 100.0%"

    def test_just_below_threshold(self) -> None:
        """Score of 89.9 gets [FAIL] badge."""
        assert _format_drift_score_badge(89.9) == "[FAIL] 89.9%"

    def test_just_above_threshold(self) -> None:
        """Score of 90.1 gets [PASS] badge."""
        assert _format_drift_score_badge(90.1) == "[PASS] 90.1%"

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_spelunking\test_dependencies.py
"""Tests verifying no new external dependencies are introduced.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest


# Python 3.10+ provides sys.stdlib_module_names
STDLIB_MODULES = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()
INTERNAL_PREFIXES = ("assemblyzero",)

# Fallback for pre-3.10: list well-known stdlib top-level modules
if not STDLIB_MODULES:
    STDLIB_MODULES = {
        "__future__", "abc", "ast", "asyncio", "collections", "contextlib",
        "copy", "csv", "dataclasses", "datetime", "decimal", "enum",
        "functools", "glob", "hashlib", "importlib", "inspect", "io",
        "itertools", "json", "logging", "math", "os", "pathlib", "pickle",
        "platform", "pprint", "re", "shutil", "signal", "socket",
        "sqlite3", "string", "struct", "subprocess", "sys", "tempfile",
        "textwrap", "threading", "time", "traceback", "typing", "unittest",
        "urllib", "uuid", "warnings", "xml",
    }


def _get_repo_root() -> Path:
    """Find repo root from test file location."""
    return Path(__file__).resolve().parents[3]


class TestNoDependencyCreep:
    """Tests that spelunking introduces no external dependencies."""

    def test_T360_no_external_imports(self) -> None:
        """T360: All imports in spelunking/*.py and new probes resolve to stdlib or internal.

        Scans all Python files in:
        - assemblyzero/spelunking/*.py
        - assemblyzero/workflows/janitor/probes/{inventory_drift,dead_references,
          adr_collision,stale_timestamps,readme_claims,persona_status}.py

        For each file, parses the AST and checks every import statement.
        Any import whose top-level module is not in sys.stdlib_module_names
        and does not start with 'assemblyzero' is flagged as third-party.

        Input: No arguments (scans files on disk).
        Output on success: Test passes (no assertion errors).
        Output on failure: AssertionError listing the third-party imports found.
          Example: AssertionError("Third-party imports found: 'chromadb' in assemblyzero/spelunking/engine.py")
        """
        repo_root = _get_repo_root()

        spelunking_dir = repo_root / "assemblyzero" / "spelunking"
        spelunking_files = list(spelunking_dir.glob("*.py")) if spelunking_dir.exists() else []

        probe_names = [
            "inventory_drift.py",
            "dead_references.py",
            "adr_collision.py",
            "stale_timestamps.py",
            "readme_claims.py",
            "persona_status.py",
        ]
        probe_dir = repo_root / "assemblyzero" / "workflows" / "janitor" / "probes"
        probe_files = [
            probe_dir / name for name in probe_names
            if (probe_dir / name).exists()
        ]

        all_files = spelunking_files + probe_files
        third_party: list[str] = []

        for file_path in all_files:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if (
                            top not in STDLIB_MODULES
                            and not any(alias.name.startswith(p) for p in INTERNAL_PREFIXES)
                        ):
                            rel = file_path.relative_to(repo_root)
                            third_party.append(f"'{alias.name}' in {rel}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    top = node.module.split(".")[0]
                    if (
                        top not in STDLIB_MODULES
                        and not any(node.module.startswith(p) for p in INTERNAL_PREFIXES)
                    ):
                        rel = file_path.relative_to(repo_root)
                        third_party.append(f"'{node.module}' in {rel}")

        assert not third_party, f"Third-party imports found: {', '.join(third_party)}"

    def test_T365_pyproject_unchanged(self) -> None:
        """T365: No new entries in pyproject.toml dependencies.

        This test reads pyproject.toml and checks that the
        [tool.poetry.dependencies] section has not grown. Since we add
        zero new dependencies, the count should remain stable.
        """
        repo_root = _get_repo_root()
        pyproject = repo_root / "pyproject.toml"

        if not pyproject.exists():
            pytest.skip("pyproject.toml not found")

        content = pyproject.read_text(encoding="utf-8")

        # Simple check: ensure no 'chromadb', 'numpy', 'pandas', etc.
        # are present as new additions
        suspicious_deps = [
            "chromadb", "numpy", "pandas", "scikit", "tensorflow",
            "torch", "transformers", "langchain", "openai",
        ]

        found = []
        for dep in suspicious_deps:
            if dep in content.lower():
                found.append(dep)

        assert not found, (
            f"Suspicious new dependencies found in pyproject.toml: {', '.join(found)}"
        )


```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### docs/standards/0015-spelunking-audit-standard.md (signatures)

```python
<!-- Last Updated: 2026-02-17 -->
<!-- Updated By: Issue #534 -->

# Standard 0015: Spelunking Audit Protocol

## Purpose

Define the protocol for spelunking audits — deep verification that documentation claims match codebase reality.

## Scope

All documentation files in the repository, including README.md, standards, ADRs, wiki pages, and persona files.

## Definitions

- **Claim**: A verifiable factual assertion in a document (e.g., "11 tools in tools/")
- **Drift**: When a claim no longer matches reality
- **Drift Score**: Percentage of verifiable claims that match reality (target: >90%)
- **Probe**: An automated check that verifies a specific category of claims
- **Spelunking Checkpoint**: A YAML-declared verification point for manual audit integration

## Protocol

### Automated Probes

Six probes run automatically:

1. **Inventory Drift** — file counts vs. inventory document
2. **Dead References** — file path references to nonexistent files
3. **ADR Collision** — duplicate numeric prefixes in ADR files
4. **Stale Timestamps** — documents with outdated "Last Updated" dates
5. **README Claims** — technical assertions contradicted by code
6. **Persona Status** — persona markers without status declarations

### Drift Score Calculation

```
drift_score = (matching_claims / verifiable_claims) * 100
```

- UNVERIFIABLE claims are excluded from the denominator
- Score >= 90%: PASS
- Score < 90%: FAIL

### Checkpoint Format

Existing audits can declare spelunking checkpoints in YAML:

```yaml
checkpoints:
# ... (truncated, syntax error in original)

```

### assemblyzero/spelunking/__init__.py (signatures)

```python
"""Spelunking engine package — deep verification that documentation matches reality.

Issue #534: Spelunking Audits
"""

from __future__ import annotations
```

### assemblyzero/spelunking/models.py (full)

```python
"""Data models for the spelunking audit system.

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
        """Percentage of verifiable claims that match reality. Target: >90%."""
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

## Previous Attempt Failed — Fix These Specific Errors

The previous implementation failed these tests:

```
FAILED tests/unit/test_spelunking/test_extractors.py::TestExtractTechnicalClaims::test_deduplicates_terms
FAILED tests/unit/test_spelunking/test_probes.py::TestReadmeClaimsProbe::test_T280_contradiction_found
FAILED tests/unit/test_spelunking/test_dependencies.py::TestNoDependencyCreep::test_T365_pyproject_unchanged
3 failed, 190 passed, 1 warning in 1.09s
```

Read the error messages carefully and fix the root cause in your implementation.

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the Python code.

```python
# Your Python code here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the Python code in a single fenced code block
