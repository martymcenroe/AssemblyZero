# Implementation Request

## Context

You are implementing code for Issue #104 using TDD.
This is iteration 6 of the implementation.

## Requirements

The tests have been scaffolded and need implementation code to pass.

### LLD Summary

# 105 - Feature: Verdict Analyzer - Template Improvement from Gemini Verdicts

## 1. Context & Goal
* **Issue:** #105
* **Objective:** Create a Python CLI tool that analyzes Gemini governance verdicts across repositories, extracts blocking patterns, and automatically improves LLD/issue templates.
* **Status:** Draft
* **Related Issues:** #94 (Janitor integration), #77 (Issue template)

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `tools/verdict-analyzer.py` | Add | Main CLI entry point with argparse interface |
| `tools/verdict_analyzer/__init__.py` | Add | Package initialization |
| `tools/verdict_analyzer/parser.py` | Add | Parse verdict markdown files (LLD + Issue formats) |
| `tools/verdict_analyzer/database.py` | Add | SQLite operations (CRUD, migrations) |
| `tools/verdict_analyzer/patterns.py` | Add | Pattern extraction, normalization, and category mapping |
| `tools/verdict_analyzer/template_updater.py` | Add | Safe template modification with atomic writes |
| `tools/verdict_analyzer/scanner.py` | Add | Multi-repo verdict discovery |
| `tests/test_verdict_analyzer.py` | Add | Unit tests for all modules |
| `.agentos/verdicts.db` | Add | SQLite database (git-ignored, project-local) |

### 2.2 Dependencies

*New packages, APIs, or services required.*

```toml
# pyproject.toml additions (if any)
# No new dependencies - uses stdlib only
# sqlite3 - built-in
# hashlib - built-in
# argparse - built-in
# pathlib - built-in
# re - built-in
# json - built-in
# logging - built-in
```

**Logging Configuration:**

```python
# Configured in verdict-analyzer.py
import logging

def configure_logging(verbosity: int) -> None:
    """Configure logging based on -v/-vv flags.
    
    Args:
        verbosity: 0 = WARNING, 1 = INFO, 2+ = DEBUG
    """
    level = logging.WARNING
    if verbosity == 1:
  ...

### Test Scenarios

- **test_010**: Parse LLD verdict | Auto | Sample LLD verdict markdown | VerdictRecord with correct fields | All fields populated, type='lld'
  - Requirement: 
  - Type: unit

- **test_020**: Parse Issue verdict | Auto | Sample Issue verdict markdown | VerdictRecord with correct fields | All fields populated, type='issue'
  - Requirement: 
  - Type: unit

- **test_030**: Extract blocking issues | Auto | Verdict with Tier 1/2/3 issues | List of BlockingIssue | Correct tier, category, description
  - Requirement: 
  - Type: unit

- **test_040**: Content hash change detection | Auto | Same file, modified file | needs_update=False, True | Correct boolean return
  - Requirement: 
  - Type: unit

- **test_050**: Pattern normalization | Auto | Various descriptions | Normalized patterns | Consistent output for similar inputs
  - Requirement: 
  - Type: unit

- **test_060**: Category mapping | Auto | All categories | Correct template sections | Matches CATEGORY_TO_SECTION
  - Requirement: 
  - Type: unit

- **test_070**: Template section parsing | Auto | 0102 template | Dict of 11 sections | All sections extracted
  - Requirement: 
  - Type: unit

- **test_080**: Recommendation generation | Auto | Pattern stats with high counts | Recommendations list | Type, section, content populated
  - Requirement: 
  - Type: unit

- **test_090**: Atomic write with backup | Auto | Template path + content | .bak created, content written | Both files exist, content correct
  - Requirement: 
  - Type: unit

- **test_100**: Multi-repo discovery | Auto | Mock project-registry.json | List of repo paths | All repos found
  - Requirement: 
  - Type: unit

- **test_110**: Missing repo handling | Auto | Registry with nonexistent repo | Warning logged, continue | No crash, other repos scanned
  - Requirement: 
  - Type: unit

- **test_120**: Database migration | Auto | Old schema DB | Updated schema | New columns exist
  - Requirement: 
  - Type: unit

- **test_130**: Dry-run mode (default) | Auto | Preview only, no file changes | Template unchanged
  - Requirement: 
  - Type: unit

- **test_140**: Stats output formatting | Auto | Database with verdicts | Formatted statistics | Readable output
  - Requirement: 
  - Type: unit

- **test_150**: Auto | Registry found at /path/to/dir/project-registry.json | Correct path resolution
  - Requirement: 
  - Type: unit

- **test_160**: Auto | Registry found at explicit path
  - Requirement: 
  - Type: unit

- **test_170**: Auto | DB with existing verdicts | All verdicts re-parsed | Hash check bypassed
  - Requirement: 
  - Type: unit

- **test_180**: Verbose logging (-v) | Auto | Filename logged at DEBUG | Parsing error includes filename
  - Requirement: 
  - Type: unit

- **test_190**: Path traversal prevention (verdict) | Auto | Verdict path with ../../../etc/passwd | Path rejected, error logged | is_relative_to() check fails
  - Requirement: 
  - Type: unit

- **test_195**: Path traversal prevention (template) | Auto | Path rejected, error logged | validate_template_path() fails
  - Requirement: 
  - Type: unit

- **test_200**: Parser version upgrade re-parse | Auto | DB with old parser_version | Verdict re-parsed despite unchanged content | needs_update returns True when parser_version outdated
  - Requirement: 
  - Type: unit

- **test_210**: Symlink loop handling | Auto | Directory with recursive symlink | Scanner completes without hanging | No infinite recursion, warning logged
  - Requirement: 
  - Type: unit

- **test_220**: Database directory creation | Auto | .agentos/ does not exist | Directory created, DB initialized | No error, DB file exists
  - Requirement: 
  - Type: unit

### Test File: C:\Users\mcwiz\Projects\AgentOS\tests\test_issue_104.py

```python
"""Tests for Issue #104 - Verdict Analyzer."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the modules under test
from tools.verdict_analyzer import PARSER_VERSION
from tools.verdict_analyzer.parser import (
    BlockingIssue,
    VerdictRecord,
    compute_content_hash,
    parse_verdict,
)
from tools.verdict_analyzer.database import VerdictDatabase
from tools.verdict_analyzer.patterns import (
    CATEGORY_TO_SECTION,
    map_category_to_section,
    normalize_pattern,
    extract_patterns_from_issues,
)
from tools.verdict_analyzer.template_updater import (
    Recommendation,
    atomic_write_template,
    format_stats,
    generate_recommendations,
    parse_template_sections,
    validate_template_path,
)
from tools.verdict_analyzer.scanner import (
    discover_verdicts,
    find_registry,
    load_registry,
    scan_repos,
    validate_verdict_path,
)


# Sample verdict content for testing
LLD_VERDICT_CONTENT = """# 105 - Feature: Verdict Analyzer

## Verdict: APPROVED

## 1. Context & Goal
Building a verdict analyzer tool.

## 2. Proposed Changes

### 2.1 Files Changed
- tools/verdict_analyzer/parser.py

## Blocking Issues

### Tier 1
- **Missing error handling** for file operations
- No input validation for paths

### Tier 2  
- Missing unit tests for parser
- Documentation incomplete
"""

ISSUE_VERDICT_CONTENT = """# Issue #42 - Add User Authentication

## Verdict: BLOCKED

## User Story
As a user, I want to authenticate.

## Acceptance Criteria
- User can log in
- User can log out

## Blocking Issues

### Tier 1
- **Security vulnerability** in token handling
- Missing CSRF protection

### Tier 2
- No rate limiting on login endpoint

### Tier 3
- Documentation needs examples
"""


class TestParser:
    """Tests for parser module."""

    def test_010_parse_lld_verdict(self, tmp_path: Path) -> None:
        """Test parsing LLD verdict markdown."""
        verdict_file = tmp_path / "lld-verdict.md"
        verdict_file.write_text(LLD_VERDICT_CONTENT)
        
        record = parse_verdict(verdict_file)
        
        assert record.verdict_type == "lld"
        assert record.decision == "APPROVED"
        assert record.filepath == str(verdict_file)
        assert record.content_hash != ""
        assert record.parser_version == PARSER_VERSION
        assert len(record.blocking_issues) >= 2

    def test_020_parse_issue_verdict(self, tmp_path: Path) -> None:
        """Test parsing Issue verdict markdown."""
        verdict_file = tmp_path / "issue-verdict.md"
        verdict_file.write_text(ISSUE_VERDICT_CONTENT)
        
        record = parse_verdict(verdict_file)
        
        assert record.verdict_type == "issue"
        assert record.decision == "BLOCKED"
        assert len(record.blocking_issues) >= 3
        
        # Check tier extraction
        tier1_issues = [i for i in record.blocking_issues if i.tier == 1]
        assert len(tier1_issues) >= 1

    def test_030_extract_blocking_issues(self, tmp_path: Path) -> None:
        """Test extraction of blocking issues by tier."""
        verdict_file = tmp_path / "verdict.md"
        verdict_file.write_text(ISSUE_VERDICT_CONTENT)
        
        record = parse_verdict(verdict_file)
        
        # Verify tier, category, description populated
        for issue in record.blocking_issues:
            assert issue.tier in (1, 2, 3)
            assert issue.category != ""
            assert issue.description != ""

    def test_040_content_hash_change_detection(self, tmp_path: Path) -> None:
        """Test content hash detects changes."""
        content1 = "Original content"
        content2 = "Modified content"
        
        hash1 = compute_content_hash(content1)
        hash2 = compute_content_hash(content2)
        hash1_again = compute_content_hash(content1)
        
        assert hash1 != hash2  # Different content = different hash
        assert hash1 == hash1_again  # Same content = same hash


class TestPatterns:
    """Tests for patterns module."""

    def test_050_pattern_normalization(self) -> None:
        """Test pattern normalization produces consistent output."""
        # Similar descriptions should normalize to similar patterns
        desc1 = "Missing error handling for file_operations.py"
        desc2 = "Missing error handling for database.py"
        
        pattern1 = normalize_pattern(desc1)
        pattern2 = normalize_pattern(desc2)
        
        # Both should normalize the filename
        assert "<file>" in pattern1
        assert "<file>" in pattern2

    def test_060_category_mapping(self) -> None:
        """Test category to section mapping."""
        # Verify all expected categories map correctly
        assert map_category_to_section("security") == "Security Considerations"
        assert map_category_to_section("testing") == "Testing Strategy"
        assert map_category_to_section("error_handling") == "Error Handling"
        assert map_category_to_section("unknown") == "Implementation Notes"
        
        # Verify CATEGORY_TO_SECTION has expected entries
        assert len(CATEGORY_TO_SECTION) >= 10


class TestTemplateUpdater:
    """Tests for template_updater module."""

    def test_070_template_section_parsing(self) -> None:
        """Test parsing template into sections."""
        template_content = """# Template

## Section 1
Content for section 1.

## Section 2
Content for section 2.

### Subsection 2.1
Nested content.

## Section 3
More content.
"""
        sections = parse_template_sections(template_content)
        
        assert "Section 1" in sections
        assert "Section 2" in sections
        assert "Section 3" in sections
        assert "Subsection 2.1" in sections
        assert len(sections) >= 4

    def test_080_recommendation_generation(self) -> None:
        """Test generating recommendations from pattern stats."""
        pattern_stats = {
            "categories": {
                "security": 10,
                "testing": 5,
                "logging": 1,  # Below threshold
            },
            "tiers": {1: 8, 2: 6, 3: 2},
            "decisions": {"BLOCKED": 10, "APPROVED": 5},
        }
        
        existing_sections = {
            "Testing Strategy": "Content here",
        }
        
        recommendations = generate_recommendations(
            pattern_stats,
            existing_sections,
            min_pattern_count=3,
        )
        
        # Should recommend for security (no section) and testing (exists but high count)
        assert len(recommendations) >= 1
        
        for rec in recommendations:
            assert rec.rec_type in ("add_section", "add_checklist_item", "add_example")
            assert rec.section != ""
            assert rec.content != ""
            assert rec.pattern_count >= 3

    def test_090_atomic_write_with_backup(self, tmp_path: Path) -> None:
        """Test atomic write creates backup and writes content."""
        template = tmp_path / "template.md"
        template.write_text("Original content")
        
        new_content = "Updated content"
        backup_path = atomic_write_template(template, new_content)
        
        # Backup should exist
        assert backup_path.exists()
        assert backup_path.read_text() == "Original content"
        
        # Template should have new content
        assert template.read_text() == new_content

    def test_130_dry_run_mode(self, tmp_path: Path) -> None:
        """Test dry-run mode doesn't modify files."""
        template = tmp_path / "template.md"
        original = "Original content"
        template.write_text(original)
        
        # In dry-run mode, we just don't call atomic_write_template
        # This tests the function exists and backup is optional
        new_content = "New content"
        
        # Simulate dry-run by not calling atomic_write
        # Just verify template unchanged
        assert template.read_text() == original

    def test_140_stats_output_formatting(self) -> None:
        """Test statistics formatting."""
        stats = {
            "total_verdicts": 15,
            "total_issues": 42,
            "decisions": {"APPROVED": 5, "BLOCKED": 10},
            "tiers": {1: 10, 2: 20, 3: 12},
            "categories": {"security": 15, "testing": 10},
        }
        
        output = format_stats(stats)
        
        assert "Total Verdicts: 15" in output
        assert "Total Blocking Issues: 42" in output
        assert "APPROVED: 5" in output
        assert "Tier 1: 10" in output
        assert "security: 15" in output


class TestScanner:
    """Tests for scanner module."""

    def test_100_multi_repo_discovery(self, tmp_path: Path) -> None:
        """Test discovering repos from registry."""
        # Create mock repos with verdicts
        repo1 = tmp_path / "repo1"
        repo1.mkdir()
        (repo1 / "docs" / "verdicts").mkdir(parents=True)
        verdict1 = repo1 / "docs" / "verdicts" / "verdict.md"
        verdict1.write_text("# Verdict\n## Verdict: APPROVED")
        
        repo2 = tmp_path / "repo2"
        repo2.mkdir()
        (repo2 / "docs" / "verdicts").mkdir(parents=True)
        verdict2 = repo2 / "docs" / "verdicts" / "verdict.md"
        verdict2.write_text("# Verdict\n## Verdict: BLOCKED")
        
        # Create registry
        registry = tmp_path / "project-registry.json"
        registry.write_text(json.dumps([str(repo1), str(repo2)]))
        
        repos = load_registry(registry)
        
        assert len(repos) == 2
        assert repo1 in repos
        assert repo2 in repos

    def test_110_missing_repo_handling(self, tmp_path: Path, caplog) -> None:
        """Test handling of missing repositories."""
        # Create registry with nonexistent repo
        registry = tmp_path / "project-registry.json"
        registry.write_text(json.dumps([
            str(tmp_path / "exists"),
            str(tmp_path / "nonexistent"),
        ]))
        
        # Create one real repo
        exists = tmp_path / "exists"
        exists.mkdir()
        
        repos = load_registry(registry)
        
        # Should only include existing repo
        assert len(repos) == 1
        assert exists in repos

    def test_150_find_registry_parent_dir(self, tmp_path: Path) -> None:
        """Test finding registry in parent directory."""
        # Create nested structure
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        
        # Put registry at top level
        registry = tmp_path / "project-registry.json"
        registry.write_text(json.dumps([]))
        
        found = find_registry(nested)
        
        assert found is not None
        assert found == registry

    def test_160_find_registry_explicit_path(self, tmp_path: Path) -> None:
        """Test finding registry at explicit path."""
        registry = tmp_path / "custom" / "project-registry.json"
        registry.parent.mkdir(parents=True)
        registry.write_text(json.dumps([]))
        
        # Pass explicit path (simulating CLI usage)
        repos = load_registry(registry)
        assert repos == []


class TestDatabase:
    """Tests for database module."""

    def test_120_database_migration(self, tmp_path: Path) -> None:
        """Test database schema migration."""
        db_path = tmp_path / "test.db"
        
        # Create database
        db = VerdictDatabase(db_path)
        
        # Verify schema
        cursor = db.conn.cursor()
        cursor.execute("SELECT version FROM schema_version")
        version = cursor.fetchone()["version"]
        
        assert version >= 1
        
        # Run migration (should be idempotent)
        db.migrate()
        
        db.close()

    def test_170_force_reparse(self, tmp_path: Path) -> None:
        """Test --force flag bypasses hash check."""
        db_path = tmp_path / "test.db"
        db = VerdictDatabase(db_path)
        
        # Add a verdict
        record = VerdictRecord(
            filepath="/path/to/verdict.md",
            verdict_type="lld",
            decision="APPROVED",
            content_hash="abc123",
            parser_version=PARSER_VERSION,
        )
        db.upsert_verdict(record)
        
        # Same hash - normally wouldn't need update
        assert not db.needs_update("/path/to/verdict.md", "abc123")
        
        # Different hash - needs update
        assert db.needs_update("/path/to/verdict.md", "different")
        
        db.close()

    def test_200_parser_version_reparse(self, tmp_path: Path) -> None:
        """Test parser version change triggers re-parse."""
        db_path = tmp_path / "test.db"
        db = VerdictDatabase(db_path)
        
        # Add verdict with old parser version
        record = VerdictRecord(
            filepath="/path/to/verdict.md",
            verdict_type="lld",
            decision="APPROVED",
            content_hash="abc123",
            parser_version="0.9.0",  # Old version
        )
        db.upsert_verdict(record)
        
        # Same content hash but different parser version
        assert db.needs_update("/path/to/verdict.md", "abc123")
        
        db.close()

    def test_220_database_directory_creation(self, tmp_path: Path) -> None:
        """Test database creates directory if needed."""
        db_path = tmp_path / "nested" / "dir" / "verdicts.db"
        
        # Directory doesn't exist yet
        assert not db_path.parent.exists()
        
        db = VerdictDatabase(db_path)
        
        # Now it should exist
        assert db_path.parent.exists()
        assert db_path.exists()
        
        db.close()


class TestSecurity:
    """Security-related tests."""

    def test_190_path_traversal_verdict(self, tmp_path: Path) -> None:
        """Test path traversal prevention for verdicts."""
        base_dir = tmp_path / "repos"
        base_dir.mkdir()
        
        # Attempt path traversal
        malicious_path = base_dir / ".." / ".." / "etc" / "passwd"
        
        # validate_verdict_path should reject this
        is_valid = validate_verdict_path(malicious_path, base_dir)
        
        assert not is_valid

    def test_195_path_traversal_template(self, tmp_path: Path) -> None:
        """Test path traversal prevention for templates."""
        base_dir = tmp_path / "templates"
        base_dir.mkdir()
        
        # Attempt path traversal
        malicious_path = base_dir / ".." / ".." / "etc" / "passwd"
        
        with pytest.raises(ValueError, match="traversal|not within"):
            validate_template_path(malicious_path, base_dir)

    def test_210_symlink_loop_handling(self, tmp_path: Path) -> None:
        """Test scanner handles symlink loops without hanging."""
        repo = tmp_path / "repo"
        repo.mkdir()
        verdicts_dir = repo / "docs" / "verdicts"
        verdicts_dir.mkdir(parents=True)
        
        # Create a verdict file
        (verdicts_dir / "verdict.md").write_text("# Verdict: APPROVED")
        
        # Try to create symlink loop (may fail on Windows)
        try:
            loop_link = verdicts_dir / "loop"
            loop_link.symlink_to(verdicts_dir)
        except OSError:
            pytest.skip("Symlinks not supported on this platform")
        
        # Scanner should complete without hanging
        verdicts = list(discover_verdicts(repo))
        
        # Should find at least the one real verdict
        assert len(verdicts) >= 1


class TestLogging:
    """Tests for logging configuration."""

    def test_180_verbose_logging(self, tmp_path: Path, caplog) -> None:
        """Test verbose logging includes filename on errors."""
        import logging
        
        # Configure logging at DEBUG level
        caplog.set_level(logging.DEBUG)
        
        # Create a verdict file that will be parsed
        verdict_file = tmp_path / "test-verdict.md"
        verdict_file.write_text(LLD_VERDICT_CONTENT)
        
        # Parse should work but we can test the logging infrastructure
        from tools.verdict_analyzer.scanner import logger as scanner_logger
        
        scanner_logger.debug(f"Parsing: {verdict_file}")
        
        assert str(verdict_file) in caplog.text or "test-verdict" in str(verdict_file)


# Ensure pytest collects these tests
def test_module_imports() -> None:
    """Verify all modules can be imported."""
    from tools.verdict_analyzer import (
        VerdictRecord,
        BlockingIssue,
        parse_verdict,
        VerdictDatabase,
        normalize_pattern,
        map_category_to_section,
        CATEGORY_TO_SECTION,
        parse_template_sections,
        generate_recommendations,
        atomic_write_template,
        validate_template_path,
        scan_repos,
        find_registry,
        discover_verdicts,
        PARSER_VERSION,
    )
    
    assert PARSER_VERSION is not None
```

### Previous Test Run (FAILED)

The previous implementation attempt failed. Here's the test output:

```
st_150_find_registry_parent_dir PASSED [ 58%]
tests/test_issue_104.py::TestScanner::test_160_find_registry_explicit_path PASSED [ 62%]
tests/test_issue_104.py::TestDatabase::test_120_database_migration PASSED [ 66%]
tests/test_issue_104.py::TestDatabase::test_170_force_reparse PASSED     [ 70%]
tests/test_issue_104.py::TestDatabase::test_200_parser_version_reparse PASSED [ 75%]
tests/test_issue_104.py::TestDatabase::test_220_database_directory_creation PASSED [ 79%]
tests/test_issue_104.py::TestSecurity::test_190_path_traversal_verdict PASSED [ 83%]
tests/test_issue_104.py::TestSecurity::test_195_path_traversal_template PASSED [ 87%]
tests/test_issue_104.py::TestSecurity::test_210_symlink_loop_handling SKIPPED [ 91%]
tests/test_issue_104.py::TestLogging::test_180_verbose_logging PASSED    [ 95%]
tests/test_issue_104.py::test_module_imports PASSED                      [100%]

---------- coverage: platform win32, python 3.14.0-final-0 -----------
Name                                         Stmts   Miss  Cover   Missing
--------------------------------------------------------------------------
tools\verdict_analyzer\__init__.py               8      0   100%
tools\verdict_analyzer\database.py              87     28    68%   95-97, 117, 143-167, 188, 198-230, 238-266, 276-279
tools\verdict_analyzer\parser.py               114     22    81%   99-102, 121, 125-130, 161-163, 195, 204-205, 210, 220, 227, 238-242
tools\verdict_analyzer\patterns.py              25      5    80%   96-103
tools\verdict_analyzer\scanner.py              123     78    37%   33, 47-58, 79-82, 87-90, 94, 120, 136-189, 201-224, 240-258
tools\verdict_analyzer\template_updater.py      81      4    95%   45, 56-59
--------------------------------------------------------------------------
TOTAL                                          438    137    69%

FAIL Required test coverage of 95% not reached. Total coverage: 68.72%

======================== 23 passed, 1 skipped in 0.54s ========================


```

Please fix the issues and provide updated implementation.

## Instructions

1. Generate implementation code that makes all tests pass
2. Follow the patterns established in the codebase
3. Ensure proper error handling
4. Add type hints where appropriate
5. Keep the implementation minimal - only what's needed to pass tests

## Output Format

Provide the implementation in a code block with the file path:

```python
# File: path/to/implementation.py

def function_name():
    ...
```

If multiple files are needed, provide each in a separate code block.
