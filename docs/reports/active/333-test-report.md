# Test Report: Issue #333

**Generated:** 2026-02-24 18:37:47
**LLD:** C:\Users\mcwiz\Projects\AssemblyZero\docs\lld\drafts\spec-0333-implementation-readiness.md

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | 35 |
| Passed | 35 |
| Failed | 0 |
| Coverage | 100.0% |
| Target | 95% |
| E2E Passed | No |
| Iterations | 1 |

## Test Files

- `C:\Users\mcwiz\Projects\AssemblyZero\tests\test_issue_333.py`

## Implementation Files

- `C:\Users\mcwiz\Projects\AssemblyZero\docs\metrics\.gitkeep`
- `C:\Users\mcwiz\Projects\AssemblyZero\tests\fixtures\metrics\tracked_repos.json`
- `C:\Users\mcwiz\Projects\AssemblyZero\tests\fixtures\metrics\mock_issues_assemblyzero.json`
- `C:\Users\mcwiz\Projects\AssemblyZero\tests\fixtures\metrics\mock_issues_rca_pdf.json`
- `C:\Users\mcwiz\Projects\AssemblyZero\tests\fixtures\metrics\expected_aggregated_output.json`
- `C:\Users\mcwiz\Projects\AssemblyZero\assemblyzero\utils\metrics_models.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\assemblyzero\utils\metrics_config.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\assemblyzero\utils\github_metrics_client.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\assemblyzero\utils\metrics_aggregator.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tools\collect_cross_project_metrics.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_metrics_config.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_github_metrics_client.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_metrics_aggregator.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_collect_cross_project_metrics.py`
- `C:\Users\mcwiz\Projects\AssemblyZero\tests\integration\test_github_metrics_integration.py`

## Test Output

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Scripts\python.exe
cachedir: .pytest_cache
benchmark: 5.2.3 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
rootdir: C:\Users\mcwiz\Projects\AssemblyZero
configfile: pyproject.toml
plugins: anyio-4.12.1, langsmith-0.6.9, benchmark-5.2.3, cov-7.0.0
collecting ... collected 35 items

tests/test_issue_333.py::test_id PASSED                                  [  2%]
tests/test_issue_333.py::test_t010 PASSED                                [  5%]
tests/test_issue_333.py::test_t020 PASSED                                [  8%]
tests/test_issue_333.py::test_t030 PASSED                                [ 11%]
tests/test_issue_333.py::test_t040 PASSED                                [ 14%]
tests/test_issue_333.py::test_t050 PASSED                                [ 17%]
tests/test_issue_333.py::test_t060 PASSED                                [ 20%]
tests/test_issue_333.py::test_t070 PASSED                                [ 22%]
tests/test_issue_333.py::test_t080 PASSED                                [ 25%]
tests/test_issue_333.py::test_t090 PASSED                                [ 28%]
tests/test_issue_333.py::test_t100 PASSED                                [ 31%]
tests/test_issue_333.py::test_t110 PASSED                                [ 34%]
tests/test_issue_333.py::test_t120 PASSED                                [ 37%]
tests/test_issue_333.py::test_t130 PASSED                                [ 40%]
tests/test_issue_333.py::test_t140 PASSED                                [ 42%]
tests/test_issue_333.py::test_t150 PASSED                                [ 45%]
tests/test_issue_333.py::test_t160 PASSED                                [ 48%]
tests/test_issue_333.py::test_t170 PASSED                                [ 51%]
tests/test_issue_333.py::test_t180 PASSED                                [ 54%]
tests/test_issue_333.py::test_t190 PASSED                                [ 57%]
tests/test_issue_333.py::test_t200 PASSED                                [ 60%]
tests/test_issue_333.py::test_t210 PASSED                                [ 62%]
tests/test_issue_333.py::test_t220 PASSED                                [ 65%]
tests/test_issue_333.py::test_t230 PASSED                                [ 68%]
tests/test_issue_333.py::test_t240 PASSED                                [ 71%]
tests/test_issue_333.py::test_t250 PASSED                                [ 74%]
tests/test_issue_333.py::test_t260 PASSED                                [ 77%]
tests/test_issue_333.py::test_t270 PASSED                                [ 80%]
tests/test_issue_333.py::test_t280 PASSED                                [ 82%]
tests/test_issue_333.py::test_t290 PASSED                                [ 85%]
tests/test_issue_333.py::test_t300 PASSED                                [ 88%]
tests/test_issue_333.py::test_t310 PASSED                                [ 91%]
tests/test_issue_333.py::test_t320 PASSED                                [ 94%]
tests/test_issue_333.py::test_t330 PASSED                                [ 97%]
tests/test_issue_333.py::test_t340 PASSED                                [100%]

=============================== tests coverage ================================
_______________ coverage: platform win32, python 3.14.0-final-0 _______________

Name                                   Stmts   Miss  Cover   Missing
--------------------------------------------------------------------
assemblyzero\utils\metrics_models.py      59      0   100%
--------------------------------------------------------------------
TOTAL                                     59      0   100%
Required test coverage of 95% reached. Total coverage: 100.00%
============================= 35 passed in 4.31s ==============================


```

---

Generated by AssemblyZero Testing Workflow
