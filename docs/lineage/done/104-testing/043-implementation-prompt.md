# Implementation Request

## Context

You are implementing code for Issue #104 using TDD.
This is iteration 5 of the implementation.

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
# Add this at the top of the file, after the imports, to configure coverage properly

# Coverage configuration for this test module
# This ensures coverage measures the correct package
import coverage

# Configure pytest to measure the correct module
def pytest_configure(config):
    """Configure coverage to measure tools/verdict_analyzer instead of agentos."""
    pass
```

### Previous Test Run (FAILED)

The previous implementation attempt failed. Here's the test output:

```
     2     0%   8-10
agentos\workflows\testing\knowledge\patterns.py           60     60     0%   7-193
agentos\workflows\testing\nodes\__init__.py                9      9     0%   19-31
agentos\workflows\testing\nodes\document.py              140    140     0%   13-360
agentos\workflows\testing\nodes\e2e_validation.py         84     84     0%   9-280
agentos\workflows\testing\nodes\finalize.py               46     46     0%   9-140
agentos\workflows\testing\nodes\implement_code.py        143    143     0%   7-450
agentos\workflows\testing\nodes\load_lld.py              192    192     0%   10-548
agentos\workflows\testing\nodes\review_test_plan.py      107    107     0%   9-391
agentos\workflows\testing\nodes\scaffold_tests.py        157    157     0%   9-372
agentos\workflows\testing\nodes\verify_phases.py         139    139     0%   7-455
agentos\workflows\testing\state.py                         9      9     0%   12-36
agentos\workflows\testing\templates\__init__.py            5      5     0%   12-23
agentos\workflows\testing\templates\cp_docs.py            73     73     0%   9-296
agentos\workflows\testing\templates\lessons.py           115    115     0%   8-304
agentos\workflows\testing\templates\runbook.py            94     94     0%   8-259
agentos\workflows\testing\templates\wiki_page.py          74     74     0%   8-207
------------------------------------------------------------------------------------
TOTAL                                                   4669   4669     0%

FAIL Required test coverage of 95% not reached. Total coverage: 0.00%
============================ no tests ran in 0.34s ============================

C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\coverage\control.py:958: CoverageWarning: No data was collected. (no-data-collected); see https://coverage.readthedocs.io/en/7.13.2/messages.html#warning-no-data-collected
  self._warn("No data was collected.", slug="no-data-collected")

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
