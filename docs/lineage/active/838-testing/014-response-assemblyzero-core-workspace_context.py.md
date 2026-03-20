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