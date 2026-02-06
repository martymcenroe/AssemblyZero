"""N2: Draft node for Issue creation workflow.

Issue #62: Governance Workflow StateGraph
Issue #64: Use claude -p instead of API calls

Calls Claude via `claude -p` (headless mode) which uses the user's
Max subscription instead of requiring API credits.
"""

import json
import subprocess
from pathlib import Path
from typing import Any

from assemblyzero.workflows.issue.audit import (
    get_repo_root,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.issue.state import IssueWorkflowState

# Path to issue template (relative to repo root)
ISSUE_TEMPLATE_PATH = Path("docs/templates/0101-issue-template.md")


def load_issue_template(repo_root: Path | None = None) -> str:
    """Load the 0101 issue template.

    Args:
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        Template content.

    Raises:
        FileNotFoundError: If template doesn't exist.
    """
    root = repo_root or get_repo_root()
    template_path = root / ISSUE_TEMPLATE_PATH

    if not template_path.exists():
        raise FileNotFoundError(f"Issue template not found: {template_path}")

    return template_path.read_text(encoding="utf-8")


def find_claude_cli() -> str:
    """Find the claude CLI executable.

    Checks common installation locations for the claude command.

    Returns:
        Path to claude executable.

    Raises:
        RuntimeError: If claude not found.
    """
    import shutil
    import os

    # Check if claude is in PATH
    claude_path = shutil.which("claude")
    if claude_path:
        return claude_path

    # Check common npm global install locations
    home = Path.home()
    common_locations = [
        home / "AppData" / "Roaming" / "npm" / "claude.cmd",  # Windows npm
        home / "AppData" / "Roaming" / "npm" / "claude",  # Windows npm (no ext)
        home / ".npm-global" / "bin" / "claude",  # Custom npm prefix
        Path("/usr/local/bin/claude"),  # macOS/Linux global
        home / ".local" / "bin" / "claude",  # Linux local
    ]

    for loc in common_locations:
        if loc.exists():
            return str(loc)

    raise RuntimeError(
        "claude command not found. Ensure Claude Code is installed.\n"
        "Install with: npm install -g @anthropic-ai/claude-code"
    )


def call_claude_headless(prompt: str, system_prompt: str | None = None) -> str:
    """Call Claude via headless mode (claude -p).

    Uses the user's logged-in Claude Code session, which works with
    Max subscription without requiring API credits.

    Args:
        prompt: The user prompt to send.
        system_prompt: Optional system prompt to use.

    Returns:
        Claude's response text.

    Raises:
        RuntimeError: If claude command fails.
    """
    claude_path = find_claude_cli()
    # Note: prompt is passed via stdin, not as command-line arg
    # This handles long prompts better and avoids shell escaping issues
    cmd = [
        claude_path,
        "-p",
        "--output-format", "json",
        "--setting-sources", "user",  # Skip project CLAUDE.md context
        "--tools", "",  # Disable all tools - just need text generation
    ]

    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    try:
        result = subprocess.run(
            cmd,
            input=prompt,  # Pass prompt via stdin
            capture_output=True,
            text=True,
            encoding="utf-8",  # Windows defaults to cp1252 which chokes on unicode
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            raise RuntimeError(f"claude -p failed: {error_msg}")

        # Parse JSON response
        try:
            response = json.loads(result.stdout)
            return response.get("result", "")
        except json.JSONDecodeError:
            # Fall back to raw stdout if not valid JSON
            return result.stdout.strip()

    except subprocess.TimeoutExpired:
        raise RuntimeError("claude -p timed out after 5 minutes")


def draft(state: IssueWorkflowState) -> dict[str, Any]:
    """N2: Generate issue draft using Claude via headless mode.

    Steps:
    1. Increment file_counter
    2. Load issue template (0101)
    3. Combine brief + template (+ feedback if revising)
    4. Call Claude via `claude -p`
    5. Save response to NNN-draft.md
    6. Increment draft_count

    Args:
        state: Current workflow state.

    Returns:
        dict with: current_draft, current_draft_path, file_counter,
                   draft_count, user_feedback (cleared)
    """
    audit_dir = Path(state.get("audit_dir", ""))
    brief_content = state.get("brief_content", "")
    user_feedback = state.get("user_feedback", "")
    current_draft = state.get("current_draft", "")
    current_verdict = state.get("current_verdict", "")
    verdict_history = state.get("verdict_history", [])
    file_counter = state.get("file_counter", 0)
    draft_count = state.get("draft_count", 0)

    if not audit_dir or not audit_dir.exists():
        return {"error_message": "Audit directory not set or doesn't exist"}

    # Increment file counter
    file_counter = next_file_number(audit_dir)

    try:
        # Load template from AssemblyZero (NOT target repo - templates are part of AssemblyZero)
        template = load_issue_template()
    except FileNotFoundError as e:
        return {"error_message": str(e)}

    # Build prompt
    system_prompt = """You are a technical writer creating a GitHub issue.

CRITICAL FORMATTING RULES:
- Start DIRECTLY with the issue title (# heading)
- Do NOT include any preamble, explanation, or meta-commentary
- Do NOT write "I'll create..." or "Let me structure..." or similar narration
- Output ONLY the raw markdown content that will be pasted into GitHub
- First line MUST be the issue title starting with #

Use the template structure provided. Fill in all sections based on the brief.
Include Mermaid diagrams where helpful. Be specific and actionable."""

    if current_draft and verdict_history:
        # Revision mode: include ALL Gemini verdicts (cumulative) + current draft
        revision_context = ""

        # Include ALL verdicts from history
        if verdict_history:
            revision_context += "## ALL Gemini Review Feedback (CUMULATIVE - MUST COMPLY WITH EVERY ITEM)\n\n"
            for i, verdict in enumerate(verdict_history, 1):
                revision_context += f"### Gemini Review #{i}\n\n{verdict}\n\n"

        # Add human feedback if provided
        if user_feedback:
            revision_context += f"""## Additional Human Feedback (from Orchestrator)
{user_feedback}

"""

        user_content = f"""IMPORTANT: Output ONLY the markdown issue content. Start with # title. No preamble.

{revision_context}## Current Draft (to revise)
{current_draft}

## Original Brief
{brief_content}

## Issue Template (REQUIRED STRUCTURE - KEEP ALL SECTIONS)
{template}

CRITICAL REVISION INSTRUCTIONS:
1. You MUST implement EVERY change requested by Gemini, including:
   - Required changes (missing sections, formatting issues)
   - Architecture suggestions
   - Technical improvements
   - ANY item mentioned in the feedback, no matter how small

2. If ANY Gemini feedback conflicts or is unclear, you MUST:
   - Stop and ask the orchestrator for clarification
   - Do NOT guess or skip conflicting items
   - Use this exact format: "ORCHESTRATOR CLARIFICATION NEEDED: [describe conflict]"

3. Template compliance:
   - ALL sections from template MUST be present
   - PRESERVE sections that Gemini didn't flag
   - ONLY modify sections Gemini specifically mentioned

4. If you cannot fully comply with all feedback, STOP and ask orchestrator

Revise the draft to address ALL feedback above while KEEPING all template sections intact.
START YOUR RESPONSE WITH THE # HEADING. DO NOT WRITE "I'll revise" OR ANY PREAMBLE."""
    else:
        # Initial draft mode
        user_content = f"""IMPORTANT: Output ONLY the markdown issue content. Start with # title. No preamble.

## Brief (user's ideation notes)
{brief_content}

## Issue Template (follow this structure)
{template}

Create a complete GitHub issue following the template structure. START YOUR RESPONSE WITH THE # HEADING. DO NOT WRITE "I'll create" OR ANY PREAMBLE."""

    try:
        import datetime
        import time
        import re

        # Progress indicator for Claude call
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n[{timestamp}] Calling Claude to generate draft...", flush=True)
        start_time = time.time()

        # Call Claude via headless mode (uses Max subscription)
        draft_content = call_claude_headless(user_content, system_prompt)

        elapsed = int(time.time() - start_time)
        end_timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{end_timestamp}] Draft received ({elapsed}s)", flush=True)

        # Strip any preamble before the first # heading (failsafe)
        match = re.search(r'^#\s+', draft_content, re.MULTILINE)
        if match:
            # Find position of first # heading
            heading_pos = match.start()
            if heading_pos > 0:
                # There's text before the heading - strip it
                stripped = draft_content[:heading_pos].strip()
                if stripped:
                    print(f"Warning: Stripped {len(stripped)} chars of preamble")
                draft_content = draft_content[heading_pos:]

    except RuntimeError as e:
        return {"error_message": f"Claude error: {e}"}

    # Save draft to audit trail
    draft_path = save_audit_file(audit_dir, file_counter, "draft.md", draft_content)
    print(f"Draft saved to: {draft_path}")

    # Increment draft count
    draft_count += 1

    return {
        "current_draft": draft_content,
        "current_draft_path": str(draft_path),
        "file_counter": file_counter,
        "draft_count": draft_count,
        "user_feedback": "",  # Clear feedback after use
        "error_message": "",
    }
