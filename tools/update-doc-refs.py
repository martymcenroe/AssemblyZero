#!/usr/bin/env python3
"""
AgentOS Documentation Reference Updater

Finds and updates references to old Aletheia 0xxx-numbered docs
with new AgentOS semantic paths.

Usage:
    python tools/update-doc-refs.py --project /path/to/project [--verbose]
    python tools/update-doc-refs.py --project /path/to/project --apply
    python tools/update-doc-refs.py --project /c/Users/mcwiz/Projects/Aletheia --apply

Options:
    --apply      Actually modify files (default is scan-only)
    --verbose    Show all matches found
    --report     Write report to file
"""

import argparse
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Mapping from old Aletheia numbers to new AgentOS paths
# Format: "old_pattern" -> "new_path"
# IMPORTANT: Keys must be the FULL filename (before .md) to avoid partial matching
REFERENCE_MAP: Dict[str, str] = {
    # Standards (00xx) - full filenames
    "0002-coding-standards": "AgentOS:standards/0002-coding-standards",
    "0004-orchestration-protocol": "AgentOS:standards/0001-orchestration-protocol",
    "0005-testing-strategy-and-protocols": "AgentOS:standards/0007-testing-strategy",
    "0005-testing-strategy": "AgentOS:standards/0007-testing-strategy",
    "0006-mermaid-diagrams": "AgentOS:standards/0004-mermaid-diagrams",
    "0009-session-closeout-protocol": "AgentOS:standards/0005-session-closeout-protocol",
    "0009-session-closeout": "AgentOS:standards/0005-session-closeout-protocol",
    "0010-standard-labels": "AgentOS:standards/0006-standard-labels",
    "0015-agent-prohibited-actions": "AgentOS:standards/0003-agent-prohibited-actions",
    "0015-agent-prohibited": "AgentOS:standards/0003-agent-prohibited-actions",

    # Templates (01xx) - full filenames
    "0100-TEMPLATE-GUIDE": "AgentOS:templates/0100-template-index",
    "0100-template-guide": "AgentOS:templates/0100-template-index",
    "0101-TEMPLATE-issue": "AgentOS:templates/0101-issue-template",
    "0102-TEMPLATE-feature-lld": "AgentOS:templates/0102-lld-template",
    "0103-TEMPLATE-implementation-report": "AgentOS:templates/0103-implementation-report-template",
    "0104-TEMPLATE-adr": "AgentOS:templates/0104-adr-template",
    "0105-TEMPLATE-implementation-plan": "AgentOS:templates/0105-implementation-plan-template",
    "0108-lld-pre-implementation-review": "AgentOS:templates/0108-lld-pre-impl-review",
    "0108-lld-pre-implementation": "AgentOS:templates/0108-lld-pre-impl-review",
    "0111-TEMPLATE-test-script": "AgentOS:templates/0106-test-script-template",
    "0113-TEMPLATE-test-report": "AgentOS:templates/0107-test-report-template",

    # ADRs (02xx) - Generic ones moved to AgentOS
    "0207-ADR-single-identity-orchestration": "AgentOS:adrs/0201-single-identity-orchestration",
    "0207-ADR-single-identity": "AgentOS:adrs/0201-single-identity-orchestration",
    "0210-ADR-git-worktree-isolation": "AgentOS:adrs/0202-git-worktree-isolation",
    "0210-ADR-git-worktree": "AgentOS:adrs/0202-git-worktree-isolation",
    "0213-ADR-adversarial-audit-philosophy": "AgentOS:adrs/0203-adversarial-audit-philosophy",
    "0213-ADR-adversarial-audit": "AgentOS:adrs/0203-adversarial-audit-philosophy",
    "0214-ADR-claude-staging-pattern": "AgentOS:adrs/0204-claude-staging-pattern",
    "0214-ADR-claude-staging": "AgentOS:adrs/0204-claude-staging-pattern",
    "0215-ADR-test-first-philosophy": "AgentOS:adrs/0205-test-first-philosophy",
    "0215-ADR-test-first": "AgentOS:adrs/0205-test-first-philosophy",

    # Skills (06xx) - full filenames
    "0600-skill-instructions-index": "AgentOS:skills/0600-skill-index",
    "0601-skill-gemini-lld-review": "AgentOS:skills/0601-gemini-lld-review",
    "0601-skill-gemini-lld": "AgentOS:skills/0601-gemini-lld-review",
    "0602-skill-gemini-dual-review": "AgentOS:skills/0602-gemini-dual-review",
    "0602-skill-gemini-dual": "AgentOS:skills/0602-gemini-dual-review",

    # Audits (08xx) - Generic ones moved to AgentOS
    "0800-common-audits": "AgentOS:audits/0800-audit-index",
    "0800-audit-index": "AgentOS:audits/0800-audit-index",
    "0807-agentos-audit": "AgentOS:audits/0807-agentos-health-audit",
    "0808-audit-permission-permissiveness": "AgentOS:audits/0816-permission-permissiveness",
    "0809-audit-security": "AgentOS:audits/0801-security-audit",
    "0810-audit-privacy": "AgentOS:audits/0802-privacy-audit",
    "0811-audit-accessibility": "AgentOS:audits/0804-accessibility-audit",
    "0813-audit-code-quality": "AgentOS:audits/0803-code-quality-audit",
    "0814-audit-license-compliance": "AgentOS:audits/0805-license-compliance",
    "0814-audit-license": "AgentOS:audits/0805-license-compliance",
    "0815-audit-claude-capabilities": "AgentOS:audits/0806-claude-capabilities",
    "0815-audit-claude": "AgentOS:audits/0806-claude-capabilities",
    "0818-audit-ai-management-system": "AgentOS:audits/0809-ai-management-system",
    "0818-audit-ai-management": "AgentOS:audits/0809-ai-management-system",
    "0819-audit-ai-supply-chain": "AgentOS:audits/0810-ai-supply-chain",
    "0819-audit-ai-supply": "AgentOS:audits/0810-ai-supply-chain",
    "0820-audit-explainability": "AgentOS:audits/0811-explainability",
    "0821-audit-agentic-ai-governance": "AgentOS:audits/0812-agentic-ai-governance",
    "0821-audit-agentic": "AgentOS:audits/0812-agentic-ai-governance",
    "0822-audit-bias-fairness": "AgentOS:audits/0813-bias-fairness",
    "0822-audit-bias": "AgentOS:audits/0813-bias-fairness",
    "0823-audit-ai-incident-post-mortem": "AgentOS:audits/0814-ai-incident-post-mortem",
    "0823-audit-ai-incident": "AgentOS:audits/0814-ai-incident-post-mortem",
    "0824-audit-permission-friction": "AgentOS:audits/0817-permission-friction",
    "0825-audit-ai-safety": "AgentOS:audits/0808-ai-safety-audit",
    "0898-horizon-scanning-protocol": "AgentOS:audits/0815-horizon-scanning",
    "0898-horizon-scanning": "AgentOS:audits/0815-horizon-scanning",
    "0899-meta-audit": "AgentOS:audits/0899-meta-audit",

    # Runbooks (09xx)
    "0900-runbook-index": "AgentOS:runbooks/0900-runbook-index",
    "0901-runbook-nightly-agentos-audit": "AgentOS:runbooks/0901-nightly-agentos-audit",
    "0901-nightly-agentos": "AgentOS:runbooks/0901-nightly-agentos-audit",
}


def find_references(content: str) -> List[Tuple[str, str, int]]:
    """Find all references to old 0xxx patterns in content.

    Returns list of (old_pattern, suggested_new, line_number)

    IMPORTANT: Uses word boundaries to avoid matching 0xxx inside 10xxx
    (Aletheia uses 10xxx for project-specific docs)
    """
    matches = []
    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        for old_pattern, new_path in REFERENCE_MAP.items():
            # Match various forms: [text](0xxx...), `0xxx...`, docs/0xxx...
            # Use (?<!\d) to ensure we don't match 0xxx inside 10xxx
            patterns = [
                rf'\[([^\]]*)\]\([^)]*(?<!\d){re.escape(old_pattern)}[^)]*\)',  # markdown link
                rf'`(?<!\d){re.escape(old_pattern)}[^`]*`',  # backtick reference
                rf'docs/(?<!\d){re.escape(old_pattern)}',  # path reference
                rf'(?<!\d){re.escape(old_pattern)}\.md',  # .md reference
            ]

            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    matches.append((old_pattern, new_path, line_num))
                    break  # Don't double-count same line

    return matches


def scan_project(project_path: Path, verbose: bool = False) -> Dict[Path, List[Tuple[str, str, int]]]:
    """Scan all markdown files in project for old references."""
    results = {}

    for md_file in project_path.rglob("*.md"):
        # Skip certain directories
        if any(skip in str(md_file) for skip in ['.git', 'node_modules', 'legacy']):
            continue

        try:
            content = md_file.read_text(encoding='utf-8')
            matches = find_references(content)

            if matches:
                results[md_file] = matches
                if verbose:
                    print(f"\n{md_file.relative_to(project_path)}:")
                    for old, new, line in matches:
                        print(f"  Line {line}: {old} -> {new}")
        except Exception as e:
            print(f"Warning: Could not read {md_file}: {e}")

    return results


def apply_fixes(file_path: Path, project_path: Path, verbose: bool = False) -> int:
    """Apply all reference fixes to a single file.

    Returns the number of replacements made.

    IMPORTANT: Uses (?<!\d) lookbehind to avoid matching 0xxx inside 10xxx
    (Aletheia uses 10xxx for project-specific docs)
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        replacements = 0

        for old_pattern, new_path in REFERENCE_MAP.items():
            # Pattern 1: Markdown links [text](path/0xxx-name.md) or [text](0xxx-name.md)
            # Use (?<!\d) to ensure we don't match 0xxx inside 10xxx
            pattern1 = rf'(\[[^\]]*\]\()([^)]*?)(?<!\d)({re.escape(old_pattern)})(\.md)?(\))'
            replacement1 = rf'\1{new_path}\5'
            new_content, count = re.subn(pattern1, replacement1, content, flags=re.IGNORECASE)
            if count > 0:
                content = new_content
                replacements += count

            # Pattern 2: Backtick references `0xxx-name` or `0xxx-name.md`
            # Use (?<!\d) to ensure we don't match 0xxx inside 10xxx
            pattern2 = rf'`([^`]*?)(?<!\d)({re.escape(old_pattern)})(\.md)?([^`]*?)`'
            def backtick_replacer(m):
                prefix = m.group(1)
                suffix = m.group(4)
                # If there's a path prefix like docs/, remove it
                if prefix.endswith('docs/') or prefix.endswith('docs\\'):
                    prefix = prefix[:-5]
                return f'`{prefix}{new_path}{suffix}`'
            new_content, count = re.subn(pattern2, backtick_replacer, content, flags=re.IGNORECASE)
            if count > 0:
                content = new_content
                replacements += count

            # Pattern 3: Plain path references docs/0xxx-name or docs/0xxx-name.md
            # Only if not already in a markdown link or backtick
            # Use (?<!\d) to ensure we don't match 0xxx inside 10xxx
            pattern3 = rf'(?<![`\(])docs/(?<!\d)({re.escape(old_pattern)})(\.md)?(?![`\)])'
            replacement3 = new_path
            new_content, count = re.subn(pattern3, replacement3, content, flags=re.IGNORECASE)
            if count > 0:
                content = new_content
                replacements += count

        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            if verbose:
                rel_path = file_path.relative_to(project_path)
                print(f"  Updated {rel_path}: {replacements} replacements")

        return replacements
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return 0


def generate_report(results: Dict[Path, List[Tuple[str, str, int]]], project_path: Path) -> str:
    """Generate a markdown report of findings."""
    lines = [
        "# Cross-Reference Update Report",
        "",
        f"**Project:** {project_path}",
        f"**Files with references:** {len(results)}",
        f"**Total references:** {sum(len(v) for v in results.values())}",
        "",
        "## Files Requiring Updates",
        "",
    ]

    for file_path, matches in sorted(results.items()):
        rel_path = file_path.relative_to(project_path)
        lines.append(f"### {rel_path}")
        lines.append("")
        lines.append("| Line | Old Reference | New Reference |")
        lines.append("|------|---------------|---------------|")
        for old, new, line_num in matches:
            lines.append(f"| {line_num} | `{old}` | `{new}` |")
        lines.append("")

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description="Update documentation cross-references")
    parser.add_argument("--project", required=True, help="Path to project to scan")
    parser.add_argument("--apply", action="store_true", help="Actually modify files (default is scan-only)")
    parser.add_argument("--verbose", action="store_true", help="Show all matches")
    parser.add_argument("--report", help="Write report to file")

    args = parser.parse_args()

    project_path = Path(args.project).resolve()
    if not project_path.exists():
        print(f"Error: Project path does not exist: {project_path}")
        return 1

    print(f"Scanning {project_path} for old references...")
    results = scan_project(project_path, verbose=args.verbose)

    if not results:
        print("\nNo old references found!")
        return 0

    total_refs = sum(len(v) for v in results.values())
    print(f"\nFound {total_refs} references in {len(results)} files")

    # Generate report
    report = generate_report(results, project_path)

    if args.report:
        Path(args.report).write_text(report)
        print(f"\nReport written to: {args.report}")

    if args.apply:
        print("\nApplying fixes...")
        total_replacements = 0
        files_modified = 0

        for file_path in results.keys():
            count = apply_fixes(file_path, project_path, verbose=args.verbose)
            if count > 0:
                total_replacements += count
                files_modified += 1

        print(f"\nDone! Modified {files_modified} files with {total_replacements} replacements.")
    else:
        print("\n" + "="*60)
        print(report)
        print("\n[SCAN ONLY] No files were modified.")
        print("Use --apply to actually update the files.")

    return 0


if __name__ == "__main__":
    exit(main())
