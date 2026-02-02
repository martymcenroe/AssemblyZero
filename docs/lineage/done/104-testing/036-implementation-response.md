Looking at the test failure, I can see the issue. The test expects:

```python
assert "line <N>" in norm1.lower() or "<n>" in norm1
```

But the normalized output is `'Error in file <FILE> at line <N>'`. When we call `.lower()` on this, we get `'error in file <file> at line <n>'`.

The assertion checks:
1. `"line <N>" in norm1.lower()` - This checks for `"line <N>"` (uppercase N) in the lowercased string which has `"line <n>"` (lowercase n) - **FALSE**
2. `"<n>" in norm1` - This checks for `"<n>"` (lowercase) in the original string which has `"<N>"` (uppercase) - **FALSE**

The test logic is flawed - it should be checking for the lowercase version in the lowercase string, or uppercase in the original. Let me fix the test assertion since the implementation is actually correct:

```python
# File: tests/test_issue_104.py

"""Test file for Issue #104 - Verdict Analyzer.

Tests for the verdict analyzer tool that parses Gemini governance verdicts
and helps improve LLD/issue templates.
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import logging

import pytest

# Import from tools - add to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from verdict_analyzer.parser import (
    VerdictRecord,
    BlockingIssue,
    parse_verdict,
    compute_content_hash,
    extract_blocking_issues,
    PARSER_VERSION,
)
from verdict_analyzer.database import VerdictDatabase, SCHEMA_VERSION
from verdict_analyzer.patterns import (
    normalize_pattern,
    CATEGORY_TO_SECTION,
    get_template_section,
    extract_category,
)
from verdict_analyzer.template_updater import (
    parse_template_sections,
    generate_recommendations,
    atomic_write_with_backup,
    validate_template_path,
    Recommendation,
)
from verdict_analyzer.scanner import (
    find_registry_path,
    discover_repos,
    scan_for_verdicts,
    validate_verdict_path,
)


# Sample verdict content for testing
SAMPLE_LLD_VERDICT = """# LLD Verdict: Feature Implementation

## Verdict: **APPROVED**

This LLD meets the requirements with minor recommendations.

## Blocking Issues:

- [Tier 1] - [Security] - Missing input validation for user-provided paths
- [Tier 2] - [Error Handling] - Exception handling needs improvement in parser module
- [Tier 3] - [Documentation] - Add docstrings to public API functions

## Recommendations:

- Consider adding type hints throughout
- Add integration tests for edge cases
"""

SAMPLE_ISSUE_VERDICT = """# Issue #42 Verdict

Status: **BLOCKED**

## Blocking Issues:

- [Tier 1] - [Testing] - No test coverage for new functionality
- [Tier 2] - [API Design] - Breaking change not documented

## Recommendations:

- Add unit tests before implementation
"""


# Fixtures
@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def db_path(temp_dir):
    """Create a database path in temp directory."""
    return temp_dir / ".agentos" / "verdicts.db"


@pytest.fixture
def database(db_path):
    """Create a test database with proper cleanup."""
    db = VerdictDatabase(db_path)
    yield db
    # Explicit close to release file handles on Windows
    db.close()


@pytest.fixture
def mock_external_service():
    """Mock external service for isolation."""
    yield None


# Unit Tests
# -----------

def test_010(temp_dir):
    """
    Parse LLD verdict | Auto | Sample LLD verdict markdown |
    VerdictRecord with correct fields | All fields populated, type='lld'
    """
    # TDD: Arrange
    verdict_file = temp_dir / "lld-verdict.md"
    verdict_file.write_text(SAMPLE_LLD_VERDICT)

    # TDD: Act
    record = parse_verdict(verdict_file)

    # TDD: Assert
    assert record.verdict_type == "lld"
    assert record.title == "LLD Verdict: Feature Implementation"
    assert record.verdict == "APPROVED"
    assert record.content_hash == compute_content_hash(SAMPLE_LLD_VERDICT)
    assert record.parser_version == PARSER_VERSION
    assert len(record.blocking_issues) == 3
    assert len(record.recommendations) >= 1


def test_020(temp_dir):
    """
    Parse Issue verdict | Auto | Sample Issue verdict markdown |
    VerdictRecord with correct fields | All fields populated, type='issue'
    """
    # TDD: Arrange
    verdict_file = temp_dir / "issue-verdict.md"
    verdict_file.write_text(SAMPLE_ISSUE_VERDICT)

    # TDD: Act
    record = parse_verdict(verdict_file)

    # TDD: Assert
    assert record.verdict_type == "issue"
    assert "42" in record.title or "Issue" in record.title
    assert record.verdict == "BLOCKED"
    assert len(record.blocking_issues) == 2


def test_030():
    """
    Extract blocking issues | Auto | Verdict with Tier 1/2/3 issues |
    List of BlockingIssue | Correct tier, category, description
    """
    # TDD: Arrange
    content = """
## Blocking Issues:

- [Tier 1] - [Security] - SQL injection vulnerability
- [Tier 2] - [Testing] - Missing unit tests
- [Tier 3] - [Documentation] - Incomplete API docs
"""

    # TDD: Act
    issues = extract_blocking_issues(content)

    # TDD: Assert
    assert len(issues) == 3
    
    tier1 = next((i for i in issues if i.tier == 1), None)
    assert tier1 is not None
    assert tier1.category == "Security"
    assert "SQL injection" in tier1.description

    tier2 = next((i for i in issues if i.tier == 2), None)
    assert tier2 is not None
    assert tier2.category == "Testing"


def test_040(temp_dir):
    """
    Content hash change detection | Auto | Same file, modified file |
    needs_update=False, True | Correct boolean return
    """
    # TDD: Arrange
    db_path = temp_dir / ".agentos" / "verdicts.db"
    database = VerdictDatabase(db_path)
    
    verdict_file = temp_dir / "verdict.md"
    content1 = "# Original Content\nVERDICT: APPROVED"
    content2 = "# Modified Content\nVERDICT: BLOCKED"
    
    verdict_file.write_text(content1)
    record1 = parse_verdict(verdict_file)
    database.upsert_verdict(record1)

    # TDD: Act & Assert - Same content should not need update
    hash1 = compute_content_hash(content1)
    assert database.needs_update(str(verdict_file), hash1) is False

    # Modified content should need update
    hash2 = compute_content_hash(content2)
    assert database.needs_update(str(verdict_file), hash2) is True
    
    # Cleanup
    database.close()


def test_050():
    """
    Pattern normalization | Auto | Various descriptions | Normalized
    patterns | Consistent output for similar inputs
    """
    # TDD: Arrange
    desc1 = "Error in file src/parser.py at line 42"
    desc2 = "Error in file src/database.py at line 123"
    desc3 = "Missing validation for 'user_input' variable"
    desc4 = "Missing validation for 'data_field' variable"

    # TDD: Act
    norm1 = normalize_pattern(desc1)
    norm2 = normalize_pattern(desc2)
    norm3 = normalize_pattern(desc3)
    norm4 = normalize_pattern(desc4)

    # TDD: Assert - Similar patterns should normalize to same output
    assert norm1 == norm2  # Both file/line patterns should match
    assert norm3 == norm4  # Both variable patterns should match
    assert "<FILE>" in norm1
    # Check for line number placeholder (case-insensitive)
    assert "line <n>" in norm1.lower()


def test_060():
    """
    Category mapping | Auto | All categories | Correct template sections
    | Matches CATEGORY_TO_SECTION
    """
    # TDD: Arrange
    expected_mappings = {
        "security": "Security Considerations",
        "error-handling": "Error Handling",
        "testing": "Testing Strategy",
        "documentation": "Documentation",
        "performance": "Performance Considerations",
        "api-design": "API Design",
    }

    # TDD: Act & Assert
    for category, expected_section in expected_mappings.items():
        actual_section = get_template_section(category)
        assert actual_section == expected_section, f"Category '{category}' maps to wrong section"


def test_070(temp_dir):
    """
    Template section parsing | Auto | 0102 template | Dict of 11 sections
    | All sections extracted
    """
    # TDD: Arrange
    template_content = """# LLD Template

## 1. Context & Goal

Describe the context.

## 2. Proposed Changes

List changes here.

## 3. Security Considerations

Security notes.

## 4. Error Handling

Error handling approach.

## 5. Testing Strategy

Testing plan.

## 6. Documentation

Doc requirements.

## 7. Performance Considerations

Performance notes.

## 8. API Design

API details.

## 9. Dependencies

Dependencies list.

## 10. Migration Strategy

Migration plan.

## 11. Implementation Details

Implementation notes.
"""
    template_file = temp_dir / "template.md"
    template_file.write_text(template_content)

    # TDD: Act
    sections = parse_template_sections(template_content)

    # TDD: Assert
    assert len(sections) >= 11
    assert "1. Context & Goal" in sections or any("Context" in k for k in sections)


def test_080():
    """
    Recommendation generation | Auto | Pattern stats with high counts |
    Recommendations list | Type, section, content populated
    """
    # TDD: Arrange
    pattern_stats = {
        "total_verdicts": 50,
        "verdicts_with_issues": 30,
        "by_category": {
            "security": 15,
            "testing": 10,
            "documentation": 5,
            "performance": 2,  # Below threshold
        },
        "by_tier": {1: 20, 2: 15, 3: 10},
    }

    # TDD: Act
    recommendations = generate_recommendations(pattern_stats, threshold=3)

    # TDD: Assert
    assert len(recommendations) >= 2  # security and testing above threshold
    
    for rec in recommendations:
        assert rec.type is not None
        assert rec.section is not None
        assert rec.content is not None
        assert len(rec.content) > 0


def test_090(temp_dir):
    """
    Atomic write with backup | Auto | Template path + content | .bak
    created, content written | Both files exist, content correct
    """
    # TDD: Arrange
    template_path = temp_dir / "template.md"
    original_content = "# Original Template"
    new_content = "# Updated Template"
    template_path.write_text(original_content)

    # TDD: Act
    success, backup_path = atomic_write_with_backup(template_path, new_content)

    # TDD: Assert
    assert success is True
    assert backup_path is not None
    assert backup_path.exists()
    assert template_path.exists()
    assert template_path.read_text() == new_content
    assert backup_path.read_text() == original_content


def test_100(temp_dir, mock_external_service):
    """
    Multi-repo discovery | Auto | Mock project-registry.json | List of
    repo paths | All repos found
    """
    # TDD: Arrange
    repo1 = temp_dir / "repo1"
    repo2 = temp_dir / "repo2"
    repo1.mkdir()
    repo2.mkdir()

    registry = {
        "projects": [
            str(repo1),
            str(repo2),
        ]
    }
    registry_path = temp_dir / "project-registry.json"
    registry_path.write_text(json.dumps(registry))

    # TDD: Act
    repos = discover_repos(registry_path)

    # TDD: Assert
    assert len(repos) == 2
    assert repo1.resolve() in repos
    assert repo2.resolve() in repos


def test_110(temp_dir, caplog):
    """
    Missing repo handling | Auto | Registry with nonexistent repo |
    Warning logged, continue | No crash, other repos scanned
    """
    # TDD: Arrange
    existing_repo = temp_dir / "existing"
    existing_repo.mkdir()

    registry = {
        "projects": [
            str(existing_repo),
            str(temp_dir / "nonexistent"),  # Does not exist
        ]
    }
    registry_path = temp_dir / "project-registry.json"
    registry_path.write_text(json.dumps(registry))

    # TDD: Act
    with caplog.at_level(logging.WARNING):
        repos = discover_repos(registry_path)

    # TDD: Assert
    assert len(repos) == 1
    assert existing_repo.resolve() in repos
    assert any("not found" in record.message.lower() for record in caplog.records)


def test_120(temp_dir, mock_external_service):
    """
    Database migration | Auto | Old schema DB | Updated schema | New
    columns exist
    """
    # TDD: Arrange - Create DB with old schema
    db_path = temp_dir / ".agentos" / "verdicts.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create a minimal old schema
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO schema_version VALUES (0)")  # Old version
    conn.commit()
    conn.close()

    # TDD: Act - Initialize database (should trigger migration)
    db = VerdictDatabase(db_path)

    # TDD: Assert - Check new schema exists
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT version FROM schema_version")
    version = cursor.fetchone()[0]
    conn.close()

    assert version == SCHEMA_VERSION
    
    # Cleanup
    db.close()


def test_130(temp_dir):
    """
    Dry-run mode (default) | Auto | Preview only, no file changes |
    Template unchanged
    """
    # TDD: Arrange
    template_path = temp_dir / "template.md"
    original_content = "# Original Template\n## Section 1\nContent here."
    template_path.write_text(original_content)

    recommendations = [
        Recommendation(
            type="add_guidance",
            section="Section 1",
            content="Add more details",
            priority=5,
        )
    ]

    # TDD: Act - Import and use preview function (no apply)
    from verdict_analyzer.template_updater import apply_recommendations_preview
    preview = apply_recommendations_preview(template_path, recommendations)

    # TDD: Assert - Original file unchanged
    assert template_path.read_text() == original_content
    assert "VERDICT ANALYZER RECOMMENDATIONS" in preview


def test_140(temp_dir, mock_external_service):
    """
    Stats output formatting | Auto | Database with verdicts | Formatted
    statistics | Readable output
    """
    # TDD: Arrange - Create database and add some verdicts
    db_path = temp_dir / ".agentos" / "verdicts.db"
    database = VerdictDatabase(db_path)
    
    record1 = VerdictRecord(
        file_path="/path/to/verdict1.md",
        content_hash="hash1",
        verdict_type="lld",
        title="Test 1",
        verdict="APPROVED",
        blocking_issues=[
            BlockingIssue(tier=1, category="Security", description="Issue 1"),
        ],
    )
    record2 = VerdictRecord(
        file_path="/path/to/verdict2.md",
        content_hash="hash2",
        verdict_type="issue",
        title="Test 2",
        verdict="BLOCKED",
        blocking_issues=[
            BlockingIssue(tier=2, category="Testing", description="Issue 2"),
        ],
    )
    database.upsert_verdict(record1)
    database.upsert_verdict(record2)

    # TDD: Act
    stats_output = database.format_stats()

    # TDD: Assert
    assert "Verdict Analyzer Statistics" in stats_output
    assert "Total verdicts" in stats_output
    assert "2" in stats_output  # 2 verdicts
    assert "Security" in stats_output
    assert "Testing" in stats_output
    
    # Cleanup
    database.close()


def test_150(temp_dir):
    """
    Auto | Registry found at /path/to/dir/project-registry.json | Correct
    path resolution
    """
    # TDD: Arrange
    nested_dir = temp_dir / "level1" / "level2" / "level3"
    nested_dir.mkdir(parents=True)
    
    registry_path = temp_dir / "project-registry.json"
    registry_path.write_text('{"projects": []}')

    # TDD: Act - Search from nested directory
    with patch("verdict_analyzer.scanner.Path.cwd", return_value=nested_dir):
        found_path = find_registry_path(nested_dir)

    # TDD: Assert
    assert found_path is not None
    assert found_path == registry_path


def test_160(temp_dir):
    """
    Auto | Registry found at explicit path
    """
    # TDD: Arrange
    custom_registry = temp_dir / "custom" / "my-registry.json"
    custom_registry.parent.mkdir(parents=True)
    custom_registry.write_text('{"projects": []}')

    # TDD: Act - Use explicit path
    repos = discover_repos(custom_registry)

    # TDD: Assert
    assert repos == []  # Empty but no error


def test_170(temp_dir):
    """
    Auto | DB with existing verdicts | All verdicts re-parsed | Hash
    check bypassed
    """
    # TDD: Arrange
    db_path = temp_dir / ".agentos" / "verdicts.db"
    database = VerdictDatabase(db_path)
    
    verdict_path = temp_dir / "verdict.md"
    content = "# Test\nVERDICT: APPROVED"
    verdict_path.write_text(content)
    
    record = parse_verdict(verdict_path)
    database.upsert_verdict(record)
    
    content_hash = compute_content_hash(content)

    # TDD: Act & Assert - Normal check says no update needed
    assert database.needs_update(str(verdict_path), content_hash) is False

    # But with force mode (tested via different hash), update is needed
    assert database.needs_update(str(verdict_path), "different_hash") is True
    
    # Cleanup
    database.close()


def test_180(temp_dir, caplog):
    """
    Verbose logging (-v) | Auto | Filename logged at DEBUG | Parsing
    error includes filename
    """
    # TDD: Arrange
    verdict_file = temp_dir / "test-verdict.md"
    verdict_file.write_text("# Valid Verdict\nVERDICT: APPROVED")

    # TDD: Act
    with caplog.at_level(logging.DEBUG):
        record = parse_verdict(verdict_file)

    # TDD: Assert - Debug message should include filename
    debug_messages = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
    assert any("test-verdict.md" in msg or str(verdict_file) in msg for msg in debug_messages) or record is not None


def test_190(temp_dir):
    """
    Path traversal prevention (verdict) | Auto | Verdict path with
    ../../../etc/passwd | Path rejected, error logged | is_relative_to()
    check fails
    """
    # TDD: Arrange
    repo_root = temp_dir / "repo"
    repo_root.mkdir()
    
    # Simulated traversal path
    traversal_path = repo_root / ".." / ".." / "etc" / "passwd"

    # TDD: Act
    is_valid = validate_verdict_path(traversal_path, repo_root)

    # TDD: Assert
    assert is_valid is False


def test_195(temp_dir):
    """
    Path traversal prevention (template) | Auto | Path rejected, error
    logged | validate_template_path() fails
    """
    # TDD: Arrange
    allowed_root = temp_dir / "templates"
    allowed_root.mkdir()
    
    # Path outside allowed root
    traversal_path = temp_dir / "outside" / "template.md"

    # TDD: Act
    is_valid = validate_template_path(traversal_path, allowed_roots=[allowed_root])

    # TDD: Assert
    assert is_valid is False


def test_200(temp_dir):
    """
    Parser version upgrade re-parse | Auto | DB with old parser_version |
    Verdict re-parsed despite unchanged content | needs_update returns
    True when parser_version outdated
    """
    # TDD: Arrange
    db_path = temp_dir / ".agentos" / "verdicts.db"
    database = VerdictDatabase(db_path)
    
    verdict_path = temp_dir / "verdict.md"
    content = "# Test\nVERDICT: APPROVED"
    verdict_path.write_text(content)
    
    # Insert with old parser version
    record = VerdictRecord(
        file_path=str(verdict_path),
        content_hash=compute_content_hash(content),
        verdict_type="lld",
        title="Test",
        verdict="APPROVED",
        parser_version="0.0.1",  # Old version
    )
    database.upsert_verdict(record)

    # TDD: Act - Check if update needed with current parser version
    needs_update = database.needs_update(
        str(verdict_path),
        compute_content_hash(content),
        parser_version=PARSER_VERSION,
    )

    # TDD: Assert
    assert needs_update is True  # Should need update due to parser version change
    
    # Cleanup
    database.close()


def test_210(temp_dir, caplog):
    """
    Symlink loop handling | Auto | Directory with recursive symlink |
    Scanner completes without hanging | No infinite recursion, warning
    logged
    """
    # TDD: Arrange
    repo = temp_dir / "repo"
    repo.mkdir()
    
    subdir = repo / "subdir"
    subdir.mkdir()
    
    # Create symlink loop (if supported)
    loop_link = subdir / "loop"
    try:
        loop_link.symlink_to(repo, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks not supported on this platform")

    # TDD: Act
    with caplog.at_level(logging.WARNING):
        verdicts = list(scan_for_verdicts(repo))

    # TDD: Assert - Should complete without hanging
    assert isinstance(verdicts, list)
    # Warning about loop may be logged
    # (Implementation handles loops via visited set)


def test_220(temp_dir, mock_external_service):
    """
    Database directory creation | Auto | .agentos/ does not exist |
    Directory created, DB initialized | No error, DB file exists
    """
    # TDD: Arrange
    db_path = temp_dir / "new_project" / ".agentos" / "verdicts.db"
    assert not db_path.parent.exists()

    # TDD: Act
    database = VerdictDatabase(db_path)

    # TDD: Assert
    assert db_path.parent.exists()
    assert db_path.exists()
    
    # Verify DB is functional
    stats = database.get_pattern_stats()
    assert stats["total_verdicts"] == 0
    
    # Cleanup
    database.close()
```

The only change I made is in `test_050` - I fixed the assertion from:

```python
assert "line <N>" in norm1.lower() or "<n>" in norm1
```

to:

```python
assert "line <n>" in norm1.lower()
```

This correctly checks that the lowercased version contains `"line <n>"` (also lowercase), which matches what the implementation produces (`'Error in file <FILE> at line <N>'` becomes `'error in file <file> at line <n>'` when lowercased).