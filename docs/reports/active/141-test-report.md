# Test Report: Issue #141

**Generated:** 2026-02-02 19:01:53
**LLD:** C:\Users\mcwiz\Projects\AssemblyZero\docs\lld\active\LLD-141.md

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | 15 |
| Passed | 15 |
| Failed | 0 |
| Coverage | 100.0% |
| Target | 95% |
| E2E Passed | Skipped |
| Iterations | 2 |

## Test Files

- `C:\Users\mcwiz\Projects\AssemblyZero\tests\test_issue_141.py`

## Implementation Files

- `C:\Users\mcwiz\Projects\AssemblyZero\assemblyzero\workflows\testing\nodes\finalize.py`

## Test Output

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Scripts\python.exe
cachedir: .pytest_cache
benchmark: 5.2.3 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
rootdir: C:\Users\mcwiz\Projects\AssemblyZero
configfile: pyproject.toml
plugins: anyio-4.12.1, langsmith-0.6.4, benchmark-5.2.3, cov-7.0.0
collecting ... collected 15 items

tests/test_issue_141.py::test_070 PASSED                                 [  6%]
tests/test_issue_141.py::test_100 PASSED                                 [ 13%]
tests/test_issue_141.py::test_110 PASSED                                 [ 20%]
tests/test_issue_141.py::test_120 PASSED                                 [ 26%]
tests/test_issue_141.py::test_130 PASSED                                 [ 33%]
tests/test_issue_141.py::test_010 PASSED                                 [ 40%]
tests/test_issue_141.py::test_020 PASSED                                 [ 46%]
tests/test_issue_141.py::test_030 PASSED                                 [ 53%]
tests/test_issue_141.py::test_040 PASSED                                 [ 60%]
tests/test_issue_141.py::test_050 PASSED                                 [ 66%]
tests/test_issue_141.py::test_060 PASSED                                 [ 73%]
tests/test_issue_141.py::test_080 PASSED                                 [ 80%]
tests/test_issue_141.py::test_090 PASSED                                 [ 86%]
tests/test_issue_141.py::test_140 PASSED                                 [ 93%]
tests/test_issue_141.py::test_150 PASSED                                 [100%]

============================== warnings summary ===============================
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\langchain_core\_api\deprecation.py:27
  C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\langchain_core\_api\deprecation.py:27: UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.
    from pydantic.v1.fields import FieldInfo as FieldInfoV1

..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\pydantic\v1\typing.py:77
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\pydantic\v1\typing.py:77
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\pydantic\v1\typing.py:77
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\pydantic\v1\typing.py:77
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\pydantic\v1\typing.py:77
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\pydantic\v1\typing.py:77
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\pydantic\v1\typing.py:77
  C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\pydantic\v1\typing.py:77: DeprecationWarning: ForwardRef._evaluate is a private API and is retained for compatibility, but will be removed in Python 3.16. Use ForwardRef.evaluate() or typing.evaluate_forward_ref() instead.
    return cast(Any, type_)._evaluate(globalns, localns, type_params=(), recursive_guard=set())

assemblyzero\workflows\testing\audit.py:25
  C:\Users\mcwiz\Projects\AssemblyZero\assemblyzero\workflows\testing\audit.py:25: PytestCollectionWarning: cannot collect test class 'TestReportMetadata' because it has a __init__ constructor (from: tests/test_issue_141.py)
    class TestReportMetadata(TypedDict):

assemblyzero\workflows\testing\state.py:36
  C:\Users\mcwiz\Projects\AssemblyZero\assemblyzero\workflows\testing\state.py:36: PytestCollectionWarning: cannot collect test class 'TestingWorkflowState' because it has a __init__ constructor (from: tests/test_issue_141.py)
    class TestingWorkflowState(TypedDict, total=False):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=============================== tests coverage ================================
_______________ coverage: platform win32, python 3.14.0-final-0 _______________

Name                                          Stmts   Miss  Cover   Missing
---------------------------------------------------------------------------
assemblyzero\workflows\testing\nodes\finalize.py     100      0   100%
---------------------------------------------------------------------------
TOTAL                                           100      0   100%
Required test coverage of 95% reached. Total coverage: 100.00%
======================= 15 passed, 10 warnings in 0.36s =======================


```

---

Generated by AssemblyZero Testing Workflow
