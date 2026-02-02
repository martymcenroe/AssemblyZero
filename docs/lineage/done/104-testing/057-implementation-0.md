# File: tests/test_issue_104.py (additions to be appended)

```python
class TestParserEdgeCases:
    """Additional parser tests for edge cases."""

    def test_parse_verdict_no_blocking_issues(self, tmp_path: Path) -> None:
        """Test parsing verdict with no blocking issues section."""
        content = """# 100 - Feature: Simple Feature

## Verdict: APPROVED

## 1. Context & Goal
Simple feature with no issues.

## 2. Proposed Changes
Nothing complex.
"""
        verdict_file = tmp_path / "simple-verdict.md"
        verdict_file.write_text(content)
        
        record = parse_verdict(verdict_file)
        
        assert record.verdict_type == "lld"
        assert record.decision == "APPROVED"
        assert len(record.blocking_issues) == 0

    def test_parse_verdict_unknown_type(self, tmp_path: Path) -> None:
        """Test parsing verdict with ambiguous type defaults to lld."""
        content = """# Some Document

## Verdict: APPROVED

Some content without clear type markers.
"""
        verdict_file = tmp_path / "unknown-verdict.md"
        verdict_file.write_text(content)
        
        record = parse_verdict(verdict_file)
        
        # Should default to lld type
        assert record.verdict_type == "lld"

    def test_parse_verdict_conditional_approval(self, tmp_path: Path) -> None:
        """Test parsing verdict with CONDITIONAL status."""
        content = """# 101 - Feature: Conditional Feature

## Verdict: CONDITIONAL

## 1. Context & Goal
Feature needs work.

## Blocking Issues

### Tier 1
- Fix the critical bug
"""
        verdict_file = tmp_path / "conditional-verdict.md"
        verdict_file.write_text(content)
        
        record = parse_verdict(verdict_file)
        
        assert record.decision == "CONDITIONAL"

    def test_parse_verdict_malformed_tier(self, tmp_path: Path) -> None:
        """Test parsing verdict with malformed tier markers."""
        content = """# 102 - Feature: Malformed

## Verdict: BLOCKED

## Blocking Issues

### Invalid Tier
- Some issue without proper tier
- Another issue
"""
        verdict_file = tmp_path / "malformed-verdict.md"
        verdict_file.write_text(content)
        
        record = parse_verdict(verdict_file)
        
        # Should still parse but may have tier 0 or handle gracefully
        assert record is not None


class TestDatabaseOperations:
    """Additional database operation tests."""

    def test_get_all_verdicts(self, tmp_path: Path) -> None:
        """Test retrieving all verdicts from database."""
        db_path = tmp_path / "test.db"
        db = VerdictDatabase(db_path)
        
        # Add multiple verdicts
        for i in range(3):
            record = VerdictRecord(
                filepath=f"/path/to/verdict{i}.md",
                verdict_type="lld",
                decision="APPROVED",
                content_hash=f"hash{i}",
                parser_version=PARSER_VERSION,
            )
            db.upsert_verdict(record)
        
        verdicts = db.get_all_verdicts()
        
        assert len(verdicts) == 3
        
        db.close()

    def test_get_stats(self, tmp_path: Path) -> None:
        """Test getting statistics from database."""
        db_path = tmp_path / "test.db"
        db = VerdictDatabase(db_path)
        
        # Add verdicts with different decisions
        for decision in ["APPROVED", "BLOCKED", "BLOCKED"]:
            record = VerdictRecord(
                filepath=f"/path/to/{decision.lower()}.md",
                verdict_type="lld",
                decision=decision,
                content_hash=f"hash_{decision}",
                parser_version=PARSER_VERSION,
            )
            db.upsert_verdict(record)
        
        stats = db.get_stats()
        
        assert stats["total_verdicts"] == 3
        assert stats["decisions"]["APPROVED"] == 1
        assert stats["decisions"]["BLOCKED"] == 2
        
        db.close()

    def test_delete_verdict(self, tmp_path: Path) -> None:
        """Test deleting a verdict from database."""
        db_path = tmp_path / "test.db"
        db = VerdictDatabase(db_path)
        
        # Add a verdict
        filepath = "/path/to/delete.md"
        record = VerdictRecord(
            filepath=filepath,
            verdict_type="lld",
            decision="APPROVED",
            content_hash="hash",
            parser_version=PARSER_VERSION,
        )
        db.upsert_verdict(record)
        
        # Verify it exists
        assert not db.needs_update(filepath, "hash")
        
        # Delete it
        db.delete_verdict(filepath)
        
        # Verify it's gone (needs_update returns True for missing)
        assert db.needs_update(filepath, "hash")
        
        db.close()

    def test_upsert_verdict_with_issues(self, tmp_path: Path) -> None:
        """Test upserting verdict with blocking issues."""
        db_path = tmp_path / "test.db"
        db = VerdictDatabase(db_path)
        
        issues = [
            BlockingIssue(tier=1, category="security", description="Security issue"),
            BlockingIssue(tier=2, category="testing", description="Missing tests"),
        ]
        
        record = VerdictRecord(
            filepath="/path/to/issues.md",
            verdict_type="lld",
            decision="BLOCKED",
            content_hash="hash",
            parser_version=PARSER_VERSION,
            blocking_issues=issues,
        )
        db.upsert_verdict(record)
        
        # Retrieve and verify
        verdicts = db.get_all_verdicts()
        assert len(verdicts) == 1
        assert len(verdicts[0].blocking_issues) == 2
        
        db.close()

    def test_get_patterns_by_category(self, tmp_path: Path) -> None:
        """Test getting patterns grouped by category."""
        db_path = tmp_path / "test.db"
        db = VerdictDatabase(db_path)
        
        # Add verdict with issues
        issues = [
            BlockingIssue(tier=1, category="security", description="SQL injection"),
            BlockingIssue(tier=1, category="security", description="XSS vulnerability"),
            BlockingIssue(tier=2, category="testing", description="Missing tests"),
        ]
        
        record = VerdictRecord(
            filepath="/path/to/issues.md",
            verdict_type="lld",
            decision="BLOCKED",
            content_hash="hash",
            parser_version=PARSER_VERSION,
            blocking_issues=issues,
        )
        db.upsert_verdict(record)
        
        patterns = db.get_patterns_by_category()
        
        assert "security" in patterns
        assert "testing" in patterns
        assert len(patterns["security"]) == 2
        
        db.close()


class TestPatternsExtraction:
    """Tests for pattern extraction functions."""

    def test_extract_patterns_from_issues(self) -> None:
        """Test extracting patterns from blocking issues."""
        issues = [
            BlockingIssue(tier=1, category="security", description="Missing input validation"),
            BlockingIssue(tier=1, category="security", description="Missing input validation"),
            BlockingIssue(tier=2, category="testing", description="No unit tests"),
        ]
        
        patterns = extract_patterns_from_issues(issues)
        
        assert len(patterns) >= 2
        # Duplicate should be counted
        assert any(p["count"] == 2 for p in patterns.values())


class TestScannerOperations:
    """Additional scanner tests."""

    def test_scan_repos_integration(self, tmp_path: Path) -> None:
        """Test scanning multiple repos."""
        # Create repos with verdicts
        for i in range(2):
            repo = tmp_path / f"repo{i}"
            verdict_dir = repo / "docs" / "verdicts"
            verdict_dir.mkdir(parents=True)
            (verdict_dir / "verdict.md").write_text(f"""# Feature {i}

## Verdict: APPROVED

## 1. Context & Goal
Feature {i} description.
""")
        
        repos = [tmp_path / "repo0", tmp_path / "repo1"]
        
        all_verdicts = []
        for repo in repos:
            verdicts = list(discover_verdicts(repo))
            all_verdicts.extend(verdicts)
        
        assert len(all_verdicts) == 2

    def test_discover_verdicts_nested(self, tmp_path: Path) -> None:
        """Test discovering verdicts in nested directories."""
        repo = tmp_path / "repo"
        
        # Create nested verdict structure
        nested = repo / "docs" / "verdicts" / "2024" / "01"
        nested.mkdir(parents=True)
        (nested / "verdict.md").write_text("# Verdict: APPROVED")
        
        verdicts = list(discover_verdicts(repo))
        
        assert len(verdicts) >= 1

    def test_discover_verdicts_no_verdicts_dir(self, tmp_path: Path) -> None:
        """Test discovering verdicts when no verdicts directory exists."""
        repo = tmp_path / "empty_repo"
        repo.mkdir()
        
        verdicts = list(discover_verdicts(repo))
        
        assert len(verdicts) == 0

    def test_scan_repos_with_database(self, tmp_path: Path) -> None:
        """Test scan_repos function with database integration."""
        # Create a repo with verdicts
        repo = tmp_path / "repo"
        verdict_dir = repo / "docs" / "verdicts"
        verdict_dir.mkdir(parents=True)
        (verdict_dir / "lld-verdict.md").write_text(LLD_VERDICT_CONTENT)
        
        # Create registry
        registry = tmp_path / "project-registry.json"
        registry.write_text(json.dumps([str(repo)]))
        
        # Create database
        db_path = tmp_path / "verdicts.db"
        
        # Run scan
        count = scan_repos(registry, db_path)
        
        assert count >= 1
        
        # Verify database has records
        db = VerdictDatabase(db_path)
        verdicts = db.get_all_verdicts()
        assert len(verdicts) >= 1
        db.close()

    def test_scan_repos_force_reparse(self, tmp_path: Path) -> None:
        """Test scan_repos with force flag."""
        # Create a repo with verdicts
        repo = tmp_path / "repo"
        verdict_dir = repo / "docs" / "verdicts"
        verdict_dir.mkdir(parents=True)
        (verdict_dir / "verdict.md").write_text(LLD_VERDICT_CONTENT)
        
        # Create registry
        registry = tmp_path / "project-registry.json"
        registry.write_text(json.dumps([str(repo)]))
        
        db_path = tmp_path / "verdicts.db"
        
        # First scan
        count1 = scan_repos(registry, db_path)
        
        # Second scan without force - should skip
        count2 = scan_repos(registry, db_path, force=False)
        
        # Third scan with force - should reparse
        count3 = scan_repos(registry, db_path, force=True)
        
        assert count1 >= 1
        assert count3 >= 1


class TestTemplateUpdaterEdgeCases:
    """Additional template updater tests."""

    def test_parse_template_sections_empty(self) -> None:
        """Test parsing empty template."""
        sections = parse_template_sections("")
        assert sections == {}

    def test_parse_template_sections_no_headers(self) -> None:
        """Test parsing template with no headers."""
        content = "Just some text without any headers."
        sections = parse_template_sections(content)
        assert len(sections) == 0

    def test_generate_recommendations_empty_stats(self) -> None:
        """Test generating recommendations with empty stats."""
        pattern_stats = {
            "categories": {},
            "tiers": {},
            "decisions": {},
        }
        
        recommendations = generate_recommendations(pattern_stats, {})
        
        assert len(recommendations) == 0

    def test_validate_template_path_valid(self, tmp_path: Path) -> None:
        """Test validate_template_path with valid path."""
        template = tmp_path / "templates" / "template.md"
        template.parent.mkdir(parents=True)
        template.write_text("# Template")
        
        # Should not raise
        validate_template_path(template, tmp_path)

    def test_format_stats_empty(self) -> None:
        """Test formatting empty stats."""
        stats = {
            "total_verdicts": 0,
            "total_issues": 0,
            "decisions": {},
            "tiers": {},
            "categories": {},
        }
        
        output = format_stats(stats)
        
        assert "Total Verdicts: 0" in output


class TestContentHashEdgeCases:
    """Tests for content hash edge cases."""

    def test_content_hash_empty_string(self) -> None:
        """Test hashing empty string."""
        hash_empty = compute_content_hash("")
        assert hash_empty != ""
        assert len(hash_empty) == 64  # SHA-256 hex length

    def test_content_hash_unicode(self) -> None:
        """Test hashing unicode content."""
        content = "Unicode: café, naïve, 日本語"
        hash_result = compute_content_hash(content)
        assert len(hash_result) == 64

    def test_content_hash_large_content(self) -> None:
        """Test hashing large content."""
        content = "x" * 1_000_000
        hash_result = compute_content_hash(content)
        assert len(hash_result) == 64
```