# Test Report: #3734

`tests/tools/test_require_status_check.py::TestVerdictLine` (7): successful write, dry run and already-required end with `OK`; no protection, checks switched off, an API error on the write and an API error on the read each end with `FAILED at:` naming the step. The existing nine tests are unchanged.

Local: `tests/unit/` plus this file, 10,840 passed, 68 skipped.

Unrelated and pre-existing: `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success` fails on unmodified `main` locally as well.
