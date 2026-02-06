"""Node implementations for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization
Issue #93: N8 Documentation Node

Nodes:
- N0: load_lld - Load LLD and extract test plan
- N1: review_test_plan - Gemini reviews test plan coverage
- N2: scaffold_tests - Generate executable test stubs
- N3: verify_red_phase - Verify all tests fail
- N4: implement_code - Claude generates implementation
- N5: verify_green_phase - Verify all tests pass
- N6: e2e_validation - Run E2E tests in sandbox
- N7: finalize - Generate reports and complete
- N8: document - Auto-generate documentation artifacts
"""

from assemblyzero.workflows.testing.nodes.document import document
from assemblyzero.workflows.testing.nodes.e2e_validation import e2e_validation
from assemblyzero.workflows.testing.nodes.finalize import finalize
from assemblyzero.workflows.testing.nodes.implement_code import implement_code
from assemblyzero.workflows.testing.nodes.load_lld import load_lld
from assemblyzero.workflows.testing.nodes.review_test_plan import review_test_plan
from assemblyzero.workflows.testing.nodes.scaffold_tests import scaffold_tests
from assemblyzero.workflows.testing.nodes.validate_commit_message import (
    validate_commit_message,
)
from assemblyzero.workflows.testing.nodes.verify_phases import (
    verify_green_phase,
    verify_red_phase,
)

__all__ = [
    "load_lld",
    "review_test_plan",
    "scaffold_tests",
    "verify_red_phase",
    "implement_code",
    "verify_green_phase",
    "e2e_validation",
    "finalize",
    "document",
    "validate_commit_message",
]
