"""Import the requirements entry path in a clean interpreter (#2611).

Run as a subprocess by `test_spec_table_injection.py::TestNoImportCycle`. The
cycle it guards only appears on a FIRST import in the order that starts at
`requirements.nodes.generate_draft`, so the check has to happen in a process
where nothing is in `sys.modules` yet.

It lives in a file rather than inside the test because doing the same thing by
purging `sys.modules` in-process poisons every later test in the run: the purge
re-executes modules, later monkeypatching targets a different module object
than the one under test, and unrelated suites fail with AttributeError. That
was measured, not theorised -- it broke `test_step_budget.py` and
`test_stage_verdict_is_explicit.py` on the run that introduced it.

Exit 0 on success; any ImportError propagates and fails the subprocess.
"""

import sys

import assemblyzero.workflows.requirements.nodes.generate_draft  # noqa: F401
from assemblyzero.workflows.implementation_spec import table_injection

# Touch the symbol the cycle used to break on, so a lazy failure cannot pass.
assert table_injection.BEGIN_MARKER
sys.exit(0)
