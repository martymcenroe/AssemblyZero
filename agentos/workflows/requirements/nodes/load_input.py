"""Load input node for requirements workflow.

Fetches GitHub issue details and prepares them for processing.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict

from agentos.workflows.requirements.audit import (
    create_audit_dir,
    next_file_number,
    save_audit_file,
)

# Constants
GH_TIMEOUT_SECONDS = 30


def _load_issue(state: Dict[str, Any]) -> Dict[str, Any]:
    """Load issue details from GitHub.
    
    Args:
        state: Workflow state containing issue_number and target_repo
        
    Returns:
        Updated state with issue details or error message
    """
    issue_number = state.get("issue_number")
    target_repo = state.get("target_repo", ".")
    
    # Create audit directory with issue number for unique path
    audit_dir = create_audit_dir(
        target_repo=Path(target_repo),
        workflow_type=state.get("workflow_type", "lld"),
        issue_number=issue_number,
    )
    state["audit_dir"] = str(audit_dir)
    
    try:
        # Fetch issue details from GitHub with UTF-8 encoding
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--json", "title,body"],
            capture_output=True,
            text=True,
            encoding="utf-8",  # Fix for Unicode handling on Windows
            cwd=target_repo,
            timeout=GH_TIMEOUT_SECONDS,
            check=False,
        )
        
        if result.returncode != 0:
            error_msg = f"Failed to fetch issue #{issue_number}: {result.stderr}"
            state["error_message"] = error_msg
            # Save error to audit
            file_num = next_file_number(audit_dir)
            save_audit_file(audit_dir, file_num, "error", error_msg)
            return state
        
        # Parse JSON response
        issue_data = json.loads(result.stdout)
        state["issue_title"] = issue_data.get("title", "")
        state["issue_body"] = issue_data.get("body", "")
        state["error_message"] = ""
        
        # Save issue data to audit
        file_num = next_file_number(audit_dir)
        audit_content = f"# Issue #{issue_number}\n\n"
        audit_content += f"**Title:** {state['issue_title']}\n\n"
        audit_content += f"**Body:**\n{state['issue_body']}\n"
        save_audit_file(audit_dir, file_num, "issue", audit_content)
        
    except subprocess.TimeoutExpired:
        error_msg = f"Timeout fetching issue #{issue_number}"
        state["error_message"] = error_msg
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "error", error_msg)
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse issue JSON: {e}"
        state["error_message"] = error_msg
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "error", error_msg)
    except Exception as e:
        error_msg = f"Unexpected error loading issue: {e}"
        state["error_message"] = error_msg
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "error", error_msg)
    
    return state


def load_input(state: Dict[str, Any]) -> Dict[str, Any]:
    """Public interface for load_input node.
    
    Args:
        state: Workflow state
        
    Returns:
        Updated state with issue details
    """
    return _load_issue(state)