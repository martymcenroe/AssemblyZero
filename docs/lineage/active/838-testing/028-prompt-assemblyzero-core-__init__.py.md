# Implementation Request: assemblyzero/core/__init__.py

## Task

Write the complete contents of `assemblyzero/core/__init__.py`.

Change type: Modify
Description: Re-export `WorkspaceContext`

## Existing File Contents

The file currently contains:

```python
"""Core components for AssemblyZero state management and infrastructure."""

from assemblyzero.core.audit import (
    ReviewAuditLog,
    ReviewLogEntry,
    GeminiReviewResponse,
    create_log_entry,
)
from assemblyzero.core.config import (
    REVIEWER_MODEL,
    REVIEWER_MODEL_FALLBACKS,
    FORBIDDEN_MODELS,
    CREDENTIALS_FILE,
    ROTATION_STATE_FILE,
    MAX_RETRIES_PER_CREDENTIAL,
    BACKOFF_BASE_SECONDS,
    BACKOFF_MAX_SECONDS,
    DEFAULT_AUDIT_LOG_PATH,
    LLD_REVIEW_PROMPT_PATH,
)
from assemblyzero.core.gemini_client import (
    GeminiClient,
    GeminiCallResult,
    GeminiErrorType,
    Credential,
    RotationState,
)
from assemblyzero.core.state import AgentState

from assemblyzero.core.workspace_context import (
    WorkspaceContext,
    make_workspace_context,
)

__all__ = [
    # State
    "AgentState",
    # Config
    "REVIEWER_MODEL",
    "REVIEWER_MODEL_FALLBACKS",
    "FORBIDDEN_MODELS",
    "CREDENTIALS_FILE",
    "ROTATION_STATE_FILE",
    "MAX_RETRIES_PER_CREDENTIAL",
    "BACKOFF_BASE_SECONDS",
    "BACKOFF_MAX_SECONDS",
    "DEFAULT_AUDIT_LOG_PATH",
    "LLD_REVIEW_PROMPT_PATH",
    # Gemini Client
    "GeminiClient",
    "GeminiCallResult",
    "GeminiErrorType",
    "Credential",
    "RotationState",
    # Audit
    "ReviewAuditLog",
    "ReviewLogEntry",
    "GeminiReviewResponse",
    "create_log_entry",
    # Workspace Context
    "WorkspaceContext",
    "make_workspace_context",
]
```

Modify this file according to the LLD specification.

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### assemblyzero/core/workspace_context.py (full)

```python
"""WorkspaceContext: immutable bundle of workspace paths.

Issue #838: Eliminates path prop-drilling across workflow nodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspaceContext:
    """Immutable container for workspace path configuration.

    Constructed once at workflow entry and threaded through LangGraph
    state. Nodes read from state["workspace_ctx"] instead of accepting
    separate path parameters.

    Attributes:
        assemblyzero_root: Absolute path to the AssemblyZero repository.
        target_repo: Absolute path to the target repository being processed.
    """

    assemblyzero_root: Path
    target_repo: Path

    def __post_init__(self) -> None:
        """Validate both paths are absolute and exist."""
        for field_name in ("assemblyzero_root", "target_repo"):
            path = getattr(self, field_name)
            if not isinstance(path, Path):
                raise TypeError(
                    f"{field_name} must be a Path, got {type(path).__name__}"
                )
            if not path.is_absolute():
                raise ValueError(f"{field_name} must be absolute: {path}")
            if not path.exists():
                raise ValueError(f"{field_name} does not exist: {path}")

    @property
    def docs_dir(self) -> Path:
        """Return assemblyzero_root / 'docs'."""
        return self.assemblyzero_root / "docs"

    @property
    def lld_active_dir(self) -> Path:
        """Return docs / 'lld' / 'active'."""
        return self.docs_dir / "lld" / "active"

    @property
    def reports_dir(self) -> Path:
        """Return docs / 'reports'."""
        return self.docs_dir / "reports"

    @property
    def target_name(self) -> str:
        """Return the basename of the target repository."""
        return self.target_repo.name


def make_workspace_context(
    assemblyzero_root: str | Path,
    target_repo: str | Path,
) -> WorkspaceContext:
    """Construct a WorkspaceContext, resolving both paths to absolute.

    Args:
        assemblyzero_root: Path (str or Path) to the AssemblyZero repo.
        target_repo: Path (str or Path) to the target repository.

    Returns:
        A validated, frozen WorkspaceContext.

    Raises:
        ValueError: If either resolved path does not exist.
    """
    return WorkspaceContext(
        assemblyzero_root=Path(assemblyzero_root).resolve(),
        target_repo=Path(target_repo).resolve(),
    )
```

## Previous Attempt Failed — Fix These Specific Errors

The previous implementation failed these tests:

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\assemblyzero-tools-hxm2LnMb-py3.14\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\mcwiz\Projects\AssemblyZero-838
configfile: pyproject.toml
plugins: anyio-4.12.1, langsmith-0.6.9, cov-7.0.0
collecting ... collected 13 items

tests/unit/test_workspace_context.py::TestWorkspaceContextConstruction::test_valid_absolute_paths PASSED [  7%]
tests/unit/test_workspace_context.py::TestWorkspaceContextConstruction::test_factory_with_strings PASSED [ 15%]
tests/unit/test_workspace_context.py::TestWorkspaceContextValidation::test_missing_assemblyzero_root PASSED [ 23%]
tests/unit/test_workspace_context.py::TestWorkspaceContextValidation::test_missing_target_repo PASSED [ 30%]
tests/unit/test_workspace_context.py::TestWorkspaceContextFrozen::test_frozen_raises PASSED [ 38%]
tests/unit/test_workspace_context.py::TestWorkspaceContextProperties::test_docs_dir PASSED [ 46%]
tests/unit/test_workspace_context.py::TestWorkspaceContextProperties::test_lld_active_dir PASSED [ 53%]
tests/unit/test_workspace_context.py::TestWorkspaceContextProperties::test_reports_dir PASSED [ 61%]
tests/unit/test_workspace_context.py::TestWorkspaceContextProperties::test_target_name PASSED [ 69%]
tests/unit/test_workspace_context.py::TestWorkspaceContextImport::test_importable_from_core PASSED [ 76%]
tests/unit/test_workspace_context.py::TestStateIntegration::test_node_reads_ctx_from_state PASSED [ 84%]
tests/unit/test_workspace_context.py::TestStateIntegration::test_agent_state_has_workspace_ctx PASSED [ 92%]
tests/unit/test_gate/test_gate_workspace_context.py::TestNodeReadsWorkspaceContext::test_node_reads_ctx_from_state PASSED [100%]
ERROR: Coverage failure: total of 93 is less than fail-under=95


============================== warnings summary ===============================
..\..\AppData\Local\pypoetry\Cache\virtualenvs\assemblyzero-tools-hxm2LnMb-py3.14\Lib\site-packages\google\genai\types.py:43
..\..\AppData\Local\pypoetry\Cache\virtualenvs\assemblyzero-tools-hxm2LnMb-py3.14\Lib\site-packages\google\genai\types.py:43
tests/unit/test_workspace_context.py::TestWorkspaceContextConstruction::test_valid_absolute_paths
  C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\assemblyzero-tools-hxm2LnMb-py3.14\Lib\site-packages\google\genai\types.py:43: DeprecationWarning: '_UnionGenericAlias' is deprecated and slated for removal in Python 3.17
    VersionedUnionType = Union[builtin_types.UnionType, _UnionGenericAlias]

..\..\AppData\Local\pypoetry\Cache\virtualenvs\assemblyzero-tools-hxm2LnMb-py3.14\Lib\site-packages\langchain_core\_api\deprecation.py:25
  C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\assemblyzero-tools-hxm2LnMb-py3.14\Lib\site-packages\langchain_core\_api\deprecation.py:25: UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.
    from pydantic.v1.fields import FieldInfo as FieldInfoV1

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=============================== tests coverage ================================
_______________ coverage: platform win32, python 3.14.0-final-0 _______________

Name                                     Stmts   Miss  Cover   Missing
----------------------------------------------------------------------
assemblyzero\core\workspace_context.py      30      2    93%   33, 37
----------------------------------------------------------------------
TOTAL                                       30      2    93%
FAIL Required test coverage of 95% not reached. Total coverage: 93.33%
======================= 13 passed, 4 warnings in 0.67s ========================


```

Read the error messages carefully and fix the root cause in your implementation.

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the Python code.

```python
# Your Python code here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the Python code in a single fenced code block
