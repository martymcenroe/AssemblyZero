"""N8: Document node for TDD Testing Workflow.

Issue #93: N8 Documentation Node

Auto-generates documentation artifacts after successful implementation:
- Wiki page (for significant features)
- Runbook (for operational features)
- Lessons learned (always)
- README updates (for major features)
- c/p documentation (for CLI tools)
"""

import re
from pathlib import Path
from typing import Any

from assemblyzero.workflows.testing.audit import (
    get_repo_root,
    log_workflow_execution,
)
from assemblyzero.workflows.testing.state import TestingWorkflowState
from assemblyzero.workflows.testing.templates import (
    generate_cli_doc,
    generate_lessons_learned,
    generate_prompt_doc,
    generate_runbook,
    generate_wiki_page,
    update_wiki_sidebar,
)


def detect_doc_scope(lld_content: str) -> str:
    """Detect documentation scope from LLD content.

    Args:
        lld_content: Full LLD content.

    Returns:
        "full", "minimal", or "none".
    """
    content_lower = lld_content.lower()

    # Check for explicit markers
    if "<!-- doc-scope: full -->" in lld_content:
        return "full"
    if "<!-- doc-scope: none -->" in lld_content:
        return "none"
    if "<!-- doc-scope: minimal -->" in lld_content:
        return "minimal"

    # Heuristics
    is_bugfix = any(kw in content_lower for kw in ["bugfix", "hotfix", "fix #", "bug fix"])
    is_new_feature = any(kw in content_lower for kw in ["new feature", "implement ", "add feature"])
    is_workflow = any(kw in content_lower for kw in ["workflow", "state machine", "langgraph"])
    is_significant = any(kw in content_lower for kw in ["major", "significant", "breaking"])

    if is_bugfix and not is_new_feature:
        return "minimal"
    if is_workflow or is_new_feature or is_significant:
        return "full"
    return "minimal"


def should_generate_wiki(state: TestingWorkflowState) -> bool:
    """Check if wiki page should be generated.

    Args:
        state: Current workflow state.

    Returns:
        True if wiki page should be generated.
    """
    lld_content = state.get("lld_content", "")

    # Skip for bugfixes
    if "bugfix" in lld_content.lower() or "hotfix" in lld_content.lower():
        return False

    # Generate for features with significant scope
    has_new_feature = "new feature" in lld_content.lower()
    has_workflow = "workflow" in lld_content.lower()
    has_architecture = "architecture" in lld_content.lower()

    return has_new_feature or has_workflow or has_architecture


def is_operational_feature(state: TestingWorkflowState) -> bool:
    """Check if this feature needs a runbook.

    Args:
        state: Current workflow state.

    Returns:
        True if runbook should be generated.
    """
    lld_content = state.get("lld_content", "").lower()
    impl_files = state.get("implementation_files", [])

    has_workflow = "workflow" in lld_content or "langgraph" in lld_content
    has_cli = any("tools/" in f for f in impl_files)
    has_runbook_indicator = "runbook" in lld_content or "operational" in lld_content

    return has_workflow or has_cli or has_runbook_indicator


def is_cli_tool(state: TestingWorkflowState) -> bool:
    """Check if implementation includes a CLI tool.

    Args:
        state: Current workflow state.

    Returns:
        True if c/p documentation should be generated.
    """
    impl_files = state.get("implementation_files", [])
    return any("tools/" in f or "cli" in f.lower() for f in impl_files)


def should_update_readme(state: TestingWorkflowState) -> bool:
    """Check if README should be updated.

    Args:
        state: Current workflow state.

    Returns:
        True if README should be updated.
    """
    lld_content = state.get("lld_content", "")

    # Check for explicit marker
    if "<!-- update-readme: true -->" in lld_content:
        return True
    if "<!-- update-readme: false -->" in lld_content:
        return False

    # Heuristics: major features warrant README update
    is_major = any(kw in lld_content.lower() for kw in [
        "major feature", "breaking change", "new workflow", "new tool"
    ])

    return is_major


def extract_feature_name(state: TestingWorkflowState) -> str:
    """Extract feature name from LLD content.

    Args:
        state: Current workflow state.

    Returns:
        Feature name string.
    """
    lld_content = state.get("lld_content", "")

    # Try to extract from title
    title_match = re.search(r"#\s*(?:\d+\s*-\s*)?(.*?)(?:\n|$)", lld_content)
    if title_match:
        title = title_match.group(1).strip()
        # Clean up common prefixes
        title = re.sub(r"^(?:LLD|Feature|Issue)[\s:]*", "", title, flags=re.IGNORECASE)
        if title and len(title) > 3:
            return title

    # Fallback to issue number
    issue_number = state.get("issue_number", 0)
    return f"Feature-{issue_number}"


def update_readme(state: TestingWorkflowState, repo_root: Path) -> bool:
    """Update README.md with new feature entry.

    Args:
        state: Current workflow state.
        repo_root: Repository root path.

    Returns:
        True if README was updated.
    """
    readme_path = repo_root / "README.md"
    if not readme_path.exists():
        return False

    feature_name = extract_feature_name(state)
    issue_number = state.get("issue_number", 0)

    readme_content = readme_path.read_text(encoding="utf-8")

    # Check if feature already mentioned
    if feature_name.lower() in readme_content.lower():
        return False

    # Find Features section and add entry
    features_pattern = r"(##\s*Features\s*\n)(.*?)(?=\n##|\Z)"
    match = re.search(features_pattern, readme_content, re.DOTALL | re.IGNORECASE)

    if match:
        features_header = match.group(1)
        features_content = match.group(2)
        new_entry = f"- **{feature_name}** - See [Issue #{issue_number}](https://github.com/issues/{issue_number})\n"

        # Add at end of features list
        if features_content.strip():
            new_features_content = features_content.rstrip() + "\n" + new_entry
        else:
            new_features_content = new_entry

        readme_content = readme_content.replace(
            match.group(0),
            features_header + new_features_content,
        )
        readme_path.write_text(readme_content, encoding="utf-8")
        return True

    return False


def document(state: TestingWorkflowState) -> dict[str, Any]:
    """N8: Generate documentation artifacts.

    Args:
        state: Current workflow state.

    Returns:
        State updates with documentation paths.
    """
    print("\n[N8] Generating documentation...")

    issue_number = state.get("issue_number", 0)
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()
    lld_content = state.get("lld_content", "")
    implementation_files = state.get("implementation_files", [])
    audit_dir = Path(state.get("audit_dir", ""))

    # Ensure audit dir exists
    if not audit_dir.exists():
        audit_dir.mkdir(parents=True, exist_ok=True)

    # 1. Analyze LLD for doc scope
    doc_scope = state.get("doc_scope", "auto")
    if doc_scope == "auto":
        doc_scope = detect_doc_scope(lld_content)
    print(f"    Doc scope: {doc_scope}")

    # 2. Generate lessons learned (always)
    lessons_path = generate_lessons_learned(
        issue_number=issue_number,
        audit_dir=audit_dir,
        state=dict(state),
        repo_root=repo_root,
    )
    print(f"    Lessons learned: {lessons_path}")

    if doc_scope == "none":
        # Log and return early
        log_workflow_execution(
            target_repo=repo_root,
            issue_number=issue_number,
            workflow_type="testing",
            event="doc_complete",
            details={"scope": "none", "lessons_path": str(lessons_path)},
        )
        return {
            "doc_lessons_path": str(lessons_path),
            "doc_wiki_path": "",
            "doc_runbook_path": "",
            "doc_readme_updated": False,
            "doc_cp_paths": [],
        }

    feature_name = extract_feature_name(state)

    # 3. Generate wiki page (if full scope and appropriate)
    wiki_path = ""
    if doc_scope == "full" and should_generate_wiki(state):
        try:
            wiki_path_obj = generate_wiki_page(
                feature_name=feature_name,
                lld_content=lld_content,
                issue_number=issue_number,
                repo_root=repo_root,
            )
            update_wiki_sidebar(wiki_path_obj)
            wiki_path = str(wiki_path_obj)
            print(f"    Wiki page: {wiki_path}")
        except Exception as e:
            print(f"    Wiki page: SKIPPED ({e})")

    # 4. Generate runbook (if operational feature)
    runbook_path = ""
    if is_operational_feature(state):
        try:
            runbook_path_obj = generate_runbook(
                feature_name=feature_name,
                lld_content=lld_content,
                issue_number=issue_number,
                repo_root=repo_root,
                implementation_files=implementation_files,
            )
            runbook_path = str(runbook_path_obj)
            print(f"    Runbook: {runbook_path}")
        except Exception as e:
            print(f"    Runbook: SKIPPED ({e})")

    # 5. Generate c/p docs (if new CLI tool)
    cp_paths: list[str] = []
    if is_cli_tool(state):
        try:
            cli_path = generate_cli_doc(
                tool_name=feature_name,
                lld_content=lld_content,
                issue_number=issue_number,
                repo_root=repo_root,
                implementation_files=implementation_files,
            )
            cp_paths.append(str(cli_path))

            prompt_path = generate_prompt_doc(
                tool_name=feature_name,
                lld_content=lld_content,
                issue_number=issue_number,
                repo_root=repo_root,
                implementation_files=implementation_files,
            )
            cp_paths.append(str(prompt_path))
            print(f"    c/p docs: {len(cp_paths)} files")
        except Exception as e:
            print(f"    c/p docs: SKIPPED ({e})")

    # 6. Update README (if major feature)
    readme_updated = False
    if should_update_readme(state):
        try:
            readme_updated = update_readme(state, repo_root)
            if readme_updated:
                print("    README: updated")
            else:
                print("    README: no update needed")
        except Exception as e:
            print(f"    README: SKIPPED ({e})")

    # Log completion
    log_workflow_execution(
        target_repo=repo_root,
        issue_number=issue_number,
        workflow_type="testing",
        event="doc_complete",
        details={
            "scope": doc_scope,
            "lessons_path": str(lessons_path),
            "wiki_path": wiki_path,
            "runbook_path": runbook_path,
            "readme_updated": readme_updated,
            "cp_paths": cp_paths,
        },
    )

    print("\n    Documentation COMPLETE!")

    return {
        "doc_wiki_path": wiki_path,
        "doc_runbook_path": runbook_path,
        "doc_lessons_path": str(lessons_path),
        "doc_readme_updated": readme_updated,
        "doc_cp_paths": cp_paths,
    }
