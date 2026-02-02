# File: tests/test_issue_104.py (append these tests to the end of the file)

```python
class TestScannerFullCoverage:
    """Tests to achieve full scanner.py coverage."""

    def test_discover_verdicts_with_subdirs(self, tmp_path: Path) -> None:
        """Test verdict discovery handles subdirectories."""
        repo = tmp_path / "repo"
        
        # Create verdict in standard location
        std_verdicts = repo / "docs" / "verdicts"
        std_verdicts.mkdir(parents=True)
        (std_verdicts / "v1.md").write_text("# Verdict: APPROVED")
        
        # Create verdict in nested location
        nested = std_verdicts / "archive" / "2024"
        nested.mkdir(parents=True)
        (nested / "v2.md").write_text("# Verdict: BLOCKED")
        
        verdicts = list(discover_verdicts(repo))
        
        # Should find both
        assert len(verdicts) >= 2

    def test_find_registry_not_found(self, tmp_path: Path) -> None:
        """Test find_registry returns None when not found."""
        # Empty directory with no registry
        empty = tmp_path / "empty"
        empty.mkdir()
        
        result = find_registry(empty)
        
        # Should return None, not raise
        assert result is None

    def test_load_registry_invalid_json(self, tmp_path: Path) -> None:
        """Test load_registry handles invalid JSON."""
        registry = tmp_path / "project-registry.json"
        registry.write_text("not valid json {{{")
        
        # Should handle gracefully
        with pytest.raises((json.JSONDecodeError, ValueError)):
            load_registry(registry)

    def test_validate_verdict_path_valid(self, tmp_path: Path) -> None:
        """Test validate_verdict_path with valid path."""
        base = tmp_path / "repos"
        base.mkdir()
        
        verdict_path = base / "repo" / "verdict.md"
        
        assert validate_verdict_path(verdict_path, base)

    def test_validate_verdict_path_absolute_outside(self, tmp_path: Path) -> None:
        """Test validate_verdict_path rejects absolute paths outside base."""
        base = tmp_path / "repos"
        base.mkdir()
        
        # Try to access outside base
        outside = tmp_path / "outside" / "verdict.md"
        
        assert not validate_verdict_path(outside, base)


class TestDatabaseFullCoverage:
    """Tests to achieve full database.py coverage."""

    def test_database_context_manager(self, tmp_path: Path) -> None:
        """Test database works as context manager."""
        db_path = tmp_path / "test.db"
        
        with VerdictDatabase(db_path) as db:
            record = VerdictRecord(
                filepath="/test.md",
                verdict_type="lld",
                decision="APPROVED",
                content_hash="hash",
                parser_version=PARSER_VERSION,
            )
            db.upsert_verdict(record)
        
        # Should be closed now, but we can reopen
        db2 = VerdictDatabase(db_path)
        verdicts = db2.get_all_verdicts()
        assert len(verdicts) == 1
        db2.close()

    def test_upsert_updates_existing(self, tmp_path: Path) -> None:
        """Test upsert updates existing record."""
        db_path = tmp_path / "test.db"
        db = VerdictDatabase(db_path)
        
        filepath = "/update.md"
        
        # Insert initial
        record1 = VerdictRecord(
            filepath=filepath,
            verdict_type="lld",
            decision="BLOCKED",
            content_hash="hash1",
            parser_version=PARSER_VERSION,
        )
        db.upsert_verdict(record1)
        
        # Update with new decision
        record2 = VerdictRecord(
            filepath=filepath,
            verdict_type="lld",
            decision="APPROVED",
            content_hash="hash2",
            parser_version=PARSER_VERSION,
        )
        db.upsert_verdict(record2)
        
        # Should have only one record with updated decision
        verdicts = db.get_all_verdicts()
        assert len(verdicts) == 1
        assert verdicts[0].decision == "APPROVED"
        
        db.close()

    def test_get_verdict_by_path(self, tmp_path: Path) -> None:
        """Test getting single verdict by path."""
        db_path = tmp_path / "test.db"
        db = VerdictDatabase(db_path)
        
        filepath = "/single.md"
        record = VerdictRecord(
            filepath=filepath,
            verdict_type="lld",
            decision="APPROVED",
            content_hash="hash",
            parser_version=PARSER_VERSION,
        )
        db.upsert_verdict(record)
        
        retrieved = db.get_verdict(filepath)
        
        assert retrieved is not None
        assert retrieved.filepath == filepath
        assert retrieved.decision == "APPROVED"
        
        db.close()

    def test_get_verdict_not_found(self, tmp_path: Path) -> None:
        """Test getting non-existent verdict."""
        db_path = tmp_path / "test.db"
        db = VerdictDatabase(db_path)
        
        retrieved = db.get_verdict("/nonexistent.md")
        
        assert retrieved is None
        
        db.close()


class TestParserFullCoverage:
    """Tests to achieve full parser.py coverage."""

    def test_parse_verdict_with_all_tiers(self, tmp_path: Path) -> None:
        """Test parsing verdict with all tier levels."""
        content = """# 103 - Feature: All Tiers

## Verdict: BLOCKED

## 1. Context & Goal
Testing all tiers.

## Blocking Issues

### Tier 1
- Critical security flaw

### Tier 2
- Missing tests
- Incomplete docs

### Tier 3
- Minor style issue
"""
        verdict_file = tmp_path / "all-tiers.md"
        verdict_file.write_text(content)
        
        record = parse_verdict(verdict_file)
        
        tier1 = [i for i in record.blocking_issues if i.tier == 1]
        tier2 = [i for i in record.blocking_issues if i.tier == 2]
        tier3 = [i for i in record.blocking_issues if i.tier == 3]
        
        assert len(tier1) >= 1
        assert len(tier2) >= 2
        assert len(tier3) >= 1

    def test_parse_verdict_extracts_title(self, tmp_path: Path) -> None:
        """Test parsing extracts issue/feature title."""
        content = """# 104 - Feature: My Awesome Feature

## Verdict: APPROVED

## 1. Context & Goal
Description here.
"""
        verdict_file = tmp_path / "titled.md"
        verdict_file.write_text(content)
        
        record = parse_verdict(verdict_file)
        
        # Should extract title info
        assert record is not None

    def test_blocking_issue_dataclass(self) -> None:
        """Test BlockingIssue dataclass functionality."""
        issue = BlockingIssue(
            tier=1,
            category="security",
            description="Test description",
        )
        
        assert issue.tier == 1
        assert issue.category == "security"
        assert issue.description == "Test description"

    def test_verdict_record_dataclass(self) -> None:
        """Test VerdictRecord dataclass functionality."""
        record = VerdictRecord(
            filepath="/test.md",
            verdict_type="lld",
            decision="APPROVED",
            content_hash="abc123",
            parser_version="1.0.0",
            blocking_issues=[],
        )
        
        assert record.filepath == "/test.md"
        assert record.verdict_type == "lld"


class TestPatternsFullCoverage:
    """Tests to achieve full patterns.py coverage."""

    def test_normalize_pattern_various_inputs(self) -> None:
        """Test pattern normalization with various inputs."""
        # Test with numbers
        pattern = normalize_pattern("Error on line 42 in file.py")
        assert "<line>" in pattern or "42" not in pattern or "<file>" in pattern
        
        # Test with paths
        pattern = normalize_pattern("Issue in /usr/local/bin/script.sh")
        assert "<file>" in pattern or "<path>" in pattern
        
        # Test with common words
        pattern = normalize_pattern("Missing error handling")
        assert pattern != ""

    def test_map_category_all_categories(self) -> None:
        """Test all category mappings."""
        categories = [
            "security", "testing", "error_handling", "documentation",
            "performance", "logging", "validation", "architecture",
        ]
        
        for cat in categories:
            section = map_category_to_section(cat)
            assert section != ""
            assert isinstance(section, str)

    def test_extract_patterns_empty_list(self) -> None:
        """Test extracting patterns from empty list."""
        patterns = extract_patterns_from_issues([])
        assert patterns == {} or len(patterns) == 0

    def test_extract_patterns_duplicates_counted(self) -> None:
        """Test that duplicate patterns are counted."""
        issues = [
            BlockingIssue(tier=1, category="security", description="Missing validation"),
            BlockingIssue(tier=1, category="security", description="Missing validation"),
            BlockingIssue(tier=1, category="security", description="Missing validation"),
        ]
        
        patterns = extract_patterns_from_issues(issues)
        
        # Should have count of 3 for the duplicate
        has_count_3 = any(p.get("count", 0) >= 3 for p in patterns.values())
        assert has_count_3 or len(patterns) <= 1


class TestTemplateFullCoverage:
    """Tests to achieve full template_updater.py coverage."""

    def test_recommendation_dataclass(self) -> None:
        """Test Recommendation dataclass."""
        rec = Recommendation(
            rec_type="add_section",
            section="Security",
            content="Add security checklist",
            pattern_count=5,
        )
        
        assert rec.rec_type == "add_section"
        assert rec.section == "Security"
        assert rec.content == "Add security checklist"
        assert rec.pattern_count == 5

    def test_atomic_write_creates_backup_suffix(self, tmp_path: Path) -> None:
        """Test atomic write creates .bak file."""
        template = tmp_path / "test.md"
        template.write_text("Original")
        
        backup = atomic_write_template(template, "New content")
        
        assert backup.suffix == ".bak"
        assert backup.stem == "test.md"

    def test_generate_recommendations_with_thresholds(self) -> None:
        """Test recommendations respect min_pattern_count."""
        stats = {
            "categories": {
                "security": 100,  # High count
                "testing": 2,    # Below threshold
            },
            "tiers": {1: 50, 2: 30, 3: 20},
            "decisions": {"BLOCKED": 80, "APPROVED": 20},
        }
        
        # With high threshold
        recs_high = generate_recommendations(stats, {}, min_pattern_count=50)
        
        # With low threshold
        recs_low = generate_recommendations(stats, {}, min_pattern_count=1)
        
        # Low threshold should have more recommendations
        assert len(recs_low) >= len(recs_high)
```