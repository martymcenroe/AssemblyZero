# Test Report: Issue #104

**Generated:** 2026-02-01 20:35:20
**LLD:** C:\Users\mcwiz\Projects\AssemblyZero\docs\lld\active\LLD-104.md

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | 60 |
| Passed | 60 |
| Failed | 0 |
| Coverage | 95.0% |
| Target | 95% |
| E2E Passed | Skipped |
| Iterations | 7 |

## Test Files

- `C:\Users\mcwiz\Projects\AssemblyZero\tests\test_issue_104.py`

## Implementation Files

- `C:\Users\mcwiz\Projects\AssemblyZero\tools\verdict_analyzer\__init__.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tools\verdict_analyzer\parser.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tools\verdict_analyzer\database.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tools\verdict_analyzer\patterns.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tools\verdict_analyzer\template_updater.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tools\verdict_analyzer\scanner.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tools\verdict_analyzer\__init__.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tools\verdict_analyzer\parser.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tools\verdict_analyzer\database.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tools\verdict_analyzer\patterns.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tools\verdict_analyzer\template_updater.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tools\verdict_analyzer\scanner.py`

## Test Output

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\mcwiz\Projects\AssemblyZero
configfile: pyproject.toml
plugins: anyio-4.12.1, langsmith-0.6.4, cov-4.1.0
collecting ... collected 61 items

tests/test_issue_104.py::TestParser::test_010_parse_lld_verdict PASSED   [  1%]
tests/test_issue_104.py::TestParser::test_020_parse_issue_verdict PASSED [  3%]
tests/test_issue_104.py::TestParser::test_030_extract_blocking_issues PASSED [  4%]
tests/test_issue_104.py::TestParser::test_040_content_hash_change_detection PASSED [  6%]
tests/test_issue_104.py::TestParser::test_parse_verdict_no_blocking_issues PASSED [  8%]
tests/test_issue_104.py::TestParser::test_parse_verdict_conditional PASSED [  9%]
tests/test_issue_104.py::TestParser::test_parse_verdict_all_tiers PASSED [ 11%]
tests/test_issue_104.py::TestParser::test_content_hash_empty_string PASSED [ 13%]
tests/test_issue_104.py::TestParser::test_content_hash_unicode PASSED    [ 14%]
tests/test_issue_104.py::TestParser::test_blocking_issue_dataclass PASSED [ 16%]
tests/test_issue_104.py::TestParser::test_verdict_record_dataclass PASSED [ 18%]
tests/test_issue_104.py::TestPatterns::test_050_pattern_normalization PASSED [ 19%]
tests/test_issue_104.py::TestPatterns::test_060_category_mapping PASSED  [ 21%]
tests/test_issue_104.py::TestPatterns::test_normalize_pattern_various_inputs PASSED [ 22%]
tests/test_issue_104.py::TestPatterns::test_map_category_all_categories PASSED [ 24%]
tests/test_issue_104.py::TestPatterns::test_extract_patterns_from_issues PASSED [ 26%]
tests/test_issue_104.py::TestPatterns::test_extract_patterns_empty_list PASSED [ 27%]
tests/test_issue_104.py::TestTemplateUpdater::test_070_template_section_parsing PASSED [ 29%]
tests/test_issue_104.py::TestTemplateUpdater::test_080_recommendation_generation PASSED [ 31%]
tests/test_issue_104.py::TestTemplateUpdater::test_090_atomic_write_with_backup PASSED [ 32%]
tests/test_issue_104.py::TestTemplateUpdater::test_130_dry_run_mode PASSED [ 34%]
tests/test_issue_104.py::TestTemplateUpdater::test_140_stats_output_formatting PASSED [ 36%]
tests/test_issue_104.py::TestTemplateUpdater::test_parse_template_sections_empty PASSED [ 37%]
tests/test_issue_104.py::TestTemplateUpdater::test_parse_template_sections_no_headers PASSED [ 39%]
tests/test_issue_104.py::TestTemplateUpdater::test_generate_recommendations_empty_stats PASSED [ 40%]
tests/test_issue_104.py::TestTemplateUpdater::test_validate_template_path_valid PASSED [ 42%]
tests/test_issue_104.py::TestTemplateUpdater::test_format_stats_empty PASSED [ 44%]
tests/test_issue_104.py::TestTemplateUpdater::test_recommendation_dataclass PASSED [ 45%]
tests/test_issue_104.py::TestTemplateUpdater::test_atomic_write_creates_backup_suffix PASSED [ 47%]
tests/test_issue_104.py::TestTemplateUpdater::test_generate_recommendations_with_thresholds PASSED [ 49%]
tests/test_issue_104.py::TestScanner::test_100_multi_repo_discovery PASSED [ 50%]
tests/test_issue_104.py::TestScanner::test_110_missing_repo_handling PASSED [ 52%]
tests/test_issue_104.py::TestScanner::test_150_find_registry_parent_dir PASSED [ 54%]
tests/test_issue_104.py::TestScanner::test_160_find_registry_explicit_path PASSED [ 55%]
tests/test_issue_104.py::TestScanner::test_discover_verdicts_nested PASSED [ 57%]
tests/test_issue_104.py::TestScanner::test_discover_verdicts_no_verdicts_dir PASSED [ 59%]
tests/test_issue_104.py::TestScanner::test_scan_repos_with_database PASSED [ 60%]
tests/test_issue_104.py::TestScanner::test_scan_repos_force_reparse PASSED [ 62%]
tests/test_issue_104.py::TestScanner::test_find_registry_not_found PASSED [ 63%]
tests/test_issue_104.py::TestScanner::test_validate_verdict_path_valid PASSED [ 65%]
tests/test_issue_104.py::TestScanner::test_validate_verdict_path_absolute_outside PASSED [ 67%]
tests/test_issue_104.py::TestScanner::test_discover_verdicts_with_subdirs PASSED [ 68%]
tests/test_issue_104.py::TestScanner::test_scan_repos_multiple_repos PASSED [ 70%]
tests/test_issue_104.py::TestDatabase::test_120_database_migration PASSED [ 72%]
tests/test_issue_104.py::TestDatabase::test_170_force_reparse PASSED     [ 73%]
tests/test_issue_104.py::TestDatabase::test_200_parser_version_reparse PASSED [ 75%]
tests/test_issue_104.py::TestDatabase::test_220_database_directory_creation PASSED [ 77%]
tests/test_issue_104.py::TestDatabase::test_get_all_verdicts PASSED      [ 78%]
tests/test_issue_104.py::TestDatabase::test_get_stats PASSED             [ 80%]
tests/test_issue_104.py::TestDatabase::test_delete_verdict PASSED        [ 81%]
tests/test_issue_104.py::TestDatabase::test_upsert_verdict_with_issues PASSED [ 83%]
tests/test_issue_104.py::TestDatabase::test_get_patterns_by_category PASSED [ 85%]
tests/test_issue_104.py::TestDatabase::test_database_context_manager PASS...
```

---

Generated by AssemblyZero Testing Workflow
