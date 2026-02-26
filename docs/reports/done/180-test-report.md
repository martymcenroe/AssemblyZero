# Test Report: Issue #180

**Generated:** 2026-02-25 18:48:54
**LLD:** C:\Users\mcwiz\Projects\AssemblyZero\docs\lld\drafts\spec-0180-implementation-readiness.md

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | 40 |
| Passed | 40 |
| Failed | 0 |
| Coverage | 100.0% |
| Target | 95% |
| E2E Passed | No |
| Iterations | 1 |

## Test Files

- `C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_cleanup_helpers.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_cleanup.py`

## Implementation Files

- `C:\Users\mcwiz\Projects\AssemblyZero\assemblyzero\workflows\testing\state.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\assemblyzero\workflows\testing\nodes\cleanup_helpers.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\assemblyzero\workflows\testing\nodes\cleanup.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\assemblyzero\workflows\testing\nodes\__init__.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\assemblyzero\workflows\testing\graph.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tests\fixtures\mock_lineage\001-lld.md`
- `C:\Users\mcwiz\Projects\AssemblyZero\tests\fixtures\mock_lineage\005-test-scaffold.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tests\fixtures\mock_lineage\052-green-phase.txt`
- `C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_cleanup_helpers.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_cleanup.py`

## Test Output

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Scripts\python.exe
cachedir: .pytest_cache
benchmark: 5.2.3 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
rootdir: C:\Users\mcwiz\Projects\AssemblyZero
configfile: pyproject.toml
plugins: anyio-4.12.1, langsmith-0.6.9, benchmark-5.2.3, cov-7.0.0
collecting ... collected 40 items

tests/unit/test_cleanup_helpers.py::TestCheckPrMerged::test_check_pr_merged_returns_true PASSED [  2%]
tests/unit/test_cleanup_helpers.py::TestCheckPrMerged::test_check_pr_merged_returns_false_open PASSED [  5%]
tests/unit/test_cleanup_helpers.py::TestCheckPrMerged::test_check_pr_merged_invalid_url_empty PASSED [  7%]
tests/unit/test_cleanup_helpers.py::TestCheckPrMerged::test_check_pr_merged_invalid_url_malformed PASSED [ 10%]
tests/unit/test_cleanup_helpers.py::TestCheckPrMerged::test_check_pr_merged_timeout PASSED [ 12%]
tests/unit/test_cleanup_helpers.py::TestRemoveWorktree::test_remove_worktree_success PASSED [ 15%]
tests/unit/test_cleanup_helpers.py::TestRemoveWorktree::test_remove_worktree_nonexistent PASSED [ 17%]
tests/unit/test_cleanup_helpers.py::TestGetWorktreeBranch::test_get_worktree_branch_found PASSED [ 20%]
tests/unit/test_cleanup_helpers.py::TestGetWorktreeBranch::test_get_worktree_branch_not_found PASSED [ 22%]
tests/unit/test_cleanup_helpers.py::TestDeleteLocalBranch::test_delete_local_branch_success PASSED [ 25%]
tests/unit/test_cleanup_helpers.py::TestDeleteLocalBranch::test_delete_local_branch_not_found PASSED [ 27%]
tests/unit/test_cleanup_helpers.py::TestArchiveLineage::test_archive_lineage_moves_directory PASSED [ 30%]
tests/unit/test_cleanup_helpers.py::TestArchiveLineage::test_archive_lineage_active_not_found PASSED [ 32%]
tests/unit/test_cleanup_helpers.py::TestArchiveLineage::test_archive_lineage_done_already_exists PASSED [ 35%]
tests/unit/test_cleanup_helpers.py::TestExtractIterationData::test_extract_iteration_data_parses_green_phase PASSED [ 37%]
tests/unit/test_cleanup_helpers.py::TestExtractIterationData::test_extract_iteration_data_empty_dir PASSED [ 40%]
tests/unit/test_cleanup_helpers.py::TestExtractIterationData::test_extract_iteration_data_nonexistent_dir PASSED [ 42%]
tests/unit/test_cleanup_helpers.py::TestDetectStall::test_detect_stall_found PASSED [ 45%]
tests/unit/test_cleanup_helpers.py::TestDetectStall::test_detect_stall_not_found PASSED [ 47%]
tests/unit/test_cleanup_helpers.py::TestDetectStall::test_detect_stall_empty PASSED [ 50%]
tests/unit/test_cleanup_helpers.py::TestDetectStall::test_detect_stall_single PASSED [ 52%]
tests/unit/test_cleanup_helpers.py::TestBuildLearningSummary::test_build_learning_summary_full PASSED [ 55%]
tests/unit/test_cleanup_helpers.py::TestRenderLearningSummary::test_render_learning_summary_markdown PASSED [ 57%]
tests/unit/test_cleanup_helpers.py::TestRenderLearningSummary::test_render_learning_summary_with_stall PASSED [ 60%]
tests/unit/test_cleanup_helpers.py::TestWriteLearningSummary::test_write_learning_summary_creates_file PASSED [ 62%]
tests/unit/test_cleanup.py::TestRouteAfterDocument::test_route_has_issue PASSED [ 65%]
tests/unit/test_cleanup.py::TestRouteAfterDocument::test_route_no_issue PASSED [ 67%]
tests/unit/test_cleanup.py::TestRouteAfterDocument::test_route_issue_zero PASSED [ 70%]
tests/unit/test_cleanup.py::TestRouteAfterDocument::test_route_issue_none PASSED [ 72%]
tests/unit/test_cleanup.py::TestGraphWiring::test_cleanup_node_wired_in_graph PASSED [ 75%]
tests/unit/test_cleanup.py::TestCleanupHappyPath::test_cleanup_happy_path_pr_merged PASSED [ 77%]
tests/unit/test_cleanup.py::TestCleanupPrNotMerged::test_cleanup_pr_not_merged_skips_worktree_keeps_active PASSED [ 80%]
tests/unit/test_cleanup.py::TestCleanupNoPrUrl::test_cleanup_no_pr_url_skips_worktree PASSED [ 82%]
tests/unit/test_cleanup.py::TestCleanupNoLineageDir::test_cleanup_no_lineage_dir_skips_archival PASSED [ 85%]
tests/unit/test_cleanup.py::TestCleanupDirtyWorktree::test_cleanup_worktree_dirty_skips_removal PASSED [ 87%]
tests/unit/test_cleanup.py::TestCleanupErrorHandling::test_cleanup_all_errors_caught PASSED [ 90%]
tests/unit/test_cleanup.py::TestCleanupErrorHandling::test_cleanup_called_process_error_caught PASSED [ 92%]
tests/unit/test_cleanup.py::TestCleanupStateFields::test_cleanup_state_fields_updated PASSED [ 95%]
tests/unit/test_cleanup.py::TestCleanupSummaryPaths::test_cleanup_pr_not_merged_summary_in_active PASSED [ 97%]
tests/unit/test_cleanup.py::TestCleanupSummaryPaths::test_cleanup_pr_merged_summary_in_done PASSED [100%]

============================== warnings summary ===============================
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\langchain_core\_api\deprecation.py...
```

---

Generated by AssemblyZero Testing Workflow
