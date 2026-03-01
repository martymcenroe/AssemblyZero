```python
"""Broken internal markdown link detection probe.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from assemblyzero.workflows.janitor.state import Finding, ProbeResult


def probe_links(repo_root: str) -> ProbeResult:
    """Scan all markdown files for broken internal links.

    Checks relative file links, anchor links, and image references.
    Does NOT check external HTTP(S) URLs or absolute paths.
    """
    md_files = find_markdown_files(repo_root)
    findings: list[Finding] = []

    for md_file in md_files:
        links = extract_internal_links(md_file)
        for line_number, link_text, link_target in links:
            if not resolve_link(md_file, link_target, repo_root):
                # Try to find a likely replacement
                likely = find_likely_target(link_target, repo_root)
                rel_file = os.path.relpath(md_file, repo_root)
                findings.append(
                    Finding(
                        probe="links",
                        category="broken_link",
                        message=f"Broken link in {rel_file} line {line_number}: {link_target} does not exist",
                        severity="warning",
                        fixable=likely is not None,
                        file_path=rel_file,
                        line_number=line_number,
                        fix_data=(
                            {"old_link": link_target, "new_link": likely}
                            if likely
                            else None
                        ),
                    )
                )

    if findings:
        return ProbeResult(probe="links", status="findings", findings=findings)
    return ProbeResult(probe="links", status="ok")


def find_markdown_files(repo_root: str) -> list[str]:
    """Find all .md files in repo, respecting .gitignore patterns.

    Uses git ls-files to only return tracked files.
    """
    result = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    files = result.stdout.strip().splitlines()
    return [os.path.join(repo_root, f) for f in files if f]


# Regex for markdown links: [text](target) and ![alt](target)
_LINK_PATTERN = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")


def extract_internal_links(file_path: str) -> list[tuple[int, str, str]]:
    """Extract internal links from a markdown file.

    Returns list of (line_number, link_text, link_target) tuples.
    Only returns relative links (not http/https URLs).
    """
    results: list[tuple[int, str, str]] = []
    try:
        with open(file_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                for match in _LINK_PATTERN.finditer(line):
                    link_text = match.group(1)
                    link_target = match.group(2)
                    # Skip external URLs
                    if link_target.startswith(("http://", "https://", "mailto:")):
                        continue
                    # Skip pure anchor links (just #heading)
                    if link_target.startswith("#"):
                        continue
                    results.append((line_num, link_text, link_target))
    except OSError:
        pass
    return results


def resolve_link(source_file: str, link_target: str, repo_root: str) -> bool:
    """Check if a relative link target resolves to an existing file.

    Strips anchor fragments before checking.
    """
    # Strip anchor fragment
    target_path = link_target.split("#")[0]
    if not target_path:
        # Pure anchor link (e.g., #heading) — assume valid within file
        return True

    source_dir = Path(source_file).parent
    resolved = (source_dir / target_path).resolve()

    # Security: ensure resolved path is within repo_root
    repo_root_resolved = Path(repo_root).resolve()
    try:
        resolved.relative_to(repo_root_resolved)
    except ValueError:
        return False

    return resolved.exists()


def find_likely_target(broken_target: str, repo_root: str) -> str | None:
    """Attempt to find the intended target of a broken link.

    Searches for files with the same basename in the repository.
    Returns the relative path to the best match, or None if ambiguous/not found.
    """
    # Strip anchor and get basename
    target_no_anchor = broken_target.split("#")[0]
    basename = os.path.basename(target_no_anchor)
    if not basename:
        return None

    # Search for files with same basename
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    candidates = [
        f
        for f in result.stdout.strip().splitlines()
        if os.path.basename(f) == basename
    ]

    if len(candidates) == 1:
        # Build relative path matching original link style
        candidate = candidates[0]
        # Preserve leading ./ if original had it
        if broken_target.startswith("./"):
            return f"./{candidate}"
        return candidate

    return None
```
