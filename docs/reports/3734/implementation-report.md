# Implementation Report: #3734

`tools/require_status_check.py`: `run()` now calls `_run()`, which returns the step that stopped it or `None`, and prints one verdict line after it: `OK`, or `FAILED at: <step> -- paste this output to the agent`. A `requests.RequestException` while reading or writing protection is caught and named as the failed step instead of ending in a traceback. The refusals, the dry run and the already-required path keep their informative lines above the verdict.
