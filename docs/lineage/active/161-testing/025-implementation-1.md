# File: agentos/workflows/requirements/nodes/finalize.py

```python
"""Finalize node for requirements workflow.

Updates GitHub issue with final draft and closes workflow.
"""

import subprocess
from pathlib import Path
from typing import Any, Dict

from agentos.workflows.requirements.audit import (
    next_file_number,
    save_audit_file,
)

# Constants
GH_TIMEOUT_SECONDS = 30


def _finalize_issue(state: Dict[str, Any]) -> Dict[str, Any]:
    """Finalize issue by updating with final draft.
    
    Args:
        state: Workflow state containing issue_number, current_draft, etc.
        
    Returns:
        Updated state with finalization status
    """
    issue_number = state.get("issue_number")
    target_repo = state.get("target_repo", ".")
    audit_dir = Path(state.get("audit_dir", "."))
    current_draft = state.get("current_draft", "")
    
    if not current_draft:
        error_msg = "No draft to finalize"
        state["error_message"] = error_msg
        if audit_dir.exists():
            file_num = next_file_number(audit_dir)
            save_audit_file(audit_dir, file_num, "error", error_msg)
        return state
    
    try:
        # Update issue comment with final draft using UTF-8 encoding
        result = subprocess.run(
            ["gh", "issue", "comment", str(issue_number), "--body", current_draft],
            capture_output=True,
            text=True,
            encoding="utf-8",  # Fix for Unicode handling on Windows
            cwd=target_repo,
            timeout=GH_TIMEOUT_SECONDS,
            check=False,
        )
        
        if result.returncode != 0:
            error_msg = f"Failed to post comment to issue #{issue_number}: {result.stderr}"
            state["error_message"] = error_msg
            if audit_dir.exists():
                file_num = next_file_number(audit_dir)
                save_audit_file(audit_dir, file_num, "error", error_msg)
            return state
        
        state["error_message"] = ""
        state["finalized"] = True
        
        # Save finalization status to audit
        if audit_dir.exists():
            file_num = next_file_number(audit_dir)
            audit_content = f"# Finalized Issue #{issue_number}\n\n"
            audit_content += f"**Comment URL:** {result.stdout.strip()}\n"
            save_audit_file(audit_dir, file_num, "finalize", audit_content)
        
    except subprocess.TimeoutExpired:
        error_msg = f"Timeout posting comment to issue #{issue_number}"
        state["error_message"] = error_msg
        if audit_dir.exists():
            file_num = next_file_number(audit_dir)
            save_audit_file(audit_dir, file_num, "error", error_msg)
    except Exception as e:
        error_msg = f"Unexpected error finalizing issue: {e}"
        state["error_message"] = error_msg
        if audit_dir.exists():
            file_num = next_file_number(audit_dir)
            save_audit_file(audit_dir, file_num, "error", error_msg)
    
    return state


def finalize(state: Dict[str, Any]) -> Dict[str, Any]:
    """Public interface for finalize node.
    
    Args:
        state: Workflow state
        
    Returns:
        Updated state with finalization status
    """
    return _finalize_issue(state)
```