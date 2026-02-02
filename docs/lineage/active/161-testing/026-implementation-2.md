# File: agentos/workflows/requirements/audit.py

```python
"""Audit utilities for requirements workflow.

Provides functions for creating audit directories and saving audit files.
"""

from pathlib import Path
from typing import Any


def create_audit_dir(repo_path: Path, workflow_type: str) -> Path:
    """Create audit directory for workflow execution.
    
    Args:
        repo_path: Repository root path
        workflow_type: Type of workflow (e.g., 'lld', 'test')
        
    Returns:
        Path to audit directory
    """
    audit_dir = repo_path / ".agentos" / "audit" / workflow_type
    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir


def next_file_number(audit_dir: Path) -> int:
    """Get next sequential file number for audit files.
    
    Args:
        audit_dir: Audit directory path
        
    Returns:
        Next available file number
    """
    if not audit_dir.exists():
        return 1
    
    existing_files = list(audit_dir.glob("*.md"))
    if not existing_files:
        return 1
    
    # Extract numbers from filenames (format: NNN-type.md)
    numbers = []
    for f in existing_files:
        try:
            num = int(f.stem.split("-")[0])
            numbers.append(num)
        except (ValueError, IndexError):
            continue
    
    return max(numbers, default=0) + 1


def save_audit_file(
    audit_dir: Path,
    file_num: int,
    file_type: str,
    content: str,
) -> Path:
    """Save audit file with sequential numbering.
    
    Args:
        audit_dir: Audit directory path
        file_num: File number
        file_type: Type of file (e.g., 'issue', 'error', 'finalize')
        content: File content
        
    Returns:
        Path to saved file
    """
    filename = f"{file_num:03d}-{file_type}.md"
    file_path = audit_dir / filename
    file_path.write_text(content, encoding="utf-8")
    return file_path
```