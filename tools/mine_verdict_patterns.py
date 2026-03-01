#!/usr/bin/env python3
"""Mine verdict patterns from lineage to suggest new Ponder auto-fix rules.

Issue #308: Scans docs/lineage/active/*/  for verdict files, extracts
blocking issues, groups by pattern, and suggests new Ponder rules.

Usage:
    poetry run python tools/mine_verdict_patterns.py [OPTIONS]

Options:
    --lineage-dir PATH   Lineage root (default: docs/lineage/active)
    --min-occurrences N  Minimum times a pattern must appear (default: 2)
    --dry-run            Print report without writing files
    --output PATH        Write report to file (default: stdout)
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VerdictInfo:
    """Parsed information from a single verdict file."""

    path: Path
    issue_id: str
    verdict: str  # "PASS", "BLOCK", "REVISE", etc.
    blocking_issues: list[str] = field(default_factory=list)
    missing_tests: list[str] = field(default_factory=list)
    coverage_pct: float | None = None


@dataclass
class Pattern:
    """A recurring pattern found across multiple verdicts."""

    category: str
    description: str
    occurrences: int
    example_verdicts: list[str] = field(default_factory=list)
    suggested_rule: str | None = None


def parse_verdict_file(path: Path) -> VerdictInfo | None:
    """Parse a verdict markdown file and extract key information."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    # Extract issue ID from parent directory
    issue_id = path.parent.name

    # Extract verdict
    verdict_match = re.search(
        r"\*\*Verdict:\*\*\s*\*?\*?(\w+)", content, re.IGNORECASE
    )
    verdict = verdict_match.group(1).upper() if verdict_match else "UNKNOWN"

    # Extract coverage percentage
    coverage_match = re.search(
        r"(\d+(?:\.\d+)?)\s*%", content[content.find("Coverage Calculation"):] if "Coverage Calculation" in content else ""
    )
    coverage_pct = float(coverage_match.group(1)) if coverage_match else None

    # Extract blocking issues (lines after "Tier 1: BLOCKING")
    blocking_issues: list[str] = []
    tier1_match = re.search(r"## Tier 1.*?\n(.*?)(?=\n## Tier 2|\n## |$)", content, re.DOTALL)
    if tier1_match:
        tier1_text = tier1_match.group(1)
        # Find specific issue items (lines starting with - [ ] or - [x] or numbered)
        for line in tier1_text.split("\n"):
            line = line.strip()
            if line.startswith(("- ", "* ", "1.", "2.", "3.")) and len(line) > 10:
                if "no issues found" not in line.lower() and "no blocking" not in line.lower():
                    blocking_issues.append(line)

    # Extract missing test scenarios
    missing_tests: list[str] = []
    missing_match = re.search(
        r"Missing Test Scenarios.*?\n(.*?)(?=\n## |\n---|\Z)",
        content,
        re.DOTALL,
    )
    if missing_match:
        for line in missing_match.group(1).split("\n"):
            line = line.strip()
            if line.startswith(("1.", "2.", "3.", "4.", "5.", "-", "*")) and len(line) > 10:
                missing_tests.append(line)

    return VerdictInfo(
        path=path,
        issue_id=issue_id,
        verdict=verdict,
        blocking_issues=blocking_issues,
        missing_tests=missing_tests,
        coverage_pct=coverage_pct,
    )


# Pattern classifiers: each returns (category, description) if matched
PATTERN_CLASSIFIERS = [
    (
        r"coverage.*(?:below|under|less than|<)\s*\d*%?|coverage.*(?:gap|threshold)|requirement.*not covered",
        "low_coverage",
        "Requirement coverage below threshold",
    ),
    (
        r"missing.*test.*(?:scenario|case)|test.*(?:scenario|case).*missing",
        "missing_test_scenarios",
        "Missing test scenarios for requirements",
    ),
    (
        r"section\s*(?:heading|header|format)|###?\s+\d+[^.]|heading.*level",
        "section_heading_format",
        "Section heading format issues",
    ),
    (
        r"(?:section\s+)?3.*numbered|numbered\s+list|bullet.*instead.*number",
        "requirements_format",
        "Section 3 requirements not in numbered list format",
    ),
    (
        r"REQ-\d+.*missing|missing.*REQ-|test.*scenario.*\(REQ-",
        "req_references",
        "Missing REQ-N references in test scenarios",
    ),
    (
        r"vague.*assert|assert.*vague|should.*work|works correctly|behaves as expected",
        "vague_assertions",
        "Vague test assertions",
    ),
    (
        r"human.*delegat|manual.*test|cannot.*automat",
        "human_delegation",
        "Tests delegated to human instead of automated",
    ),
    (
        r"path.*(?:not found|doesn.t exist|invalid)|file.*(?:not found|missing)",
        "invalid_paths",
        "Invalid file paths in LLD",
    ),
    (
        r"architectural.*(?:risk|concern|issue)|design.*(?:issue|concern)",
        "architecture",
        "Architectural concerns raised by reviewer",
    ),
]


def classify_issue(text: str) -> list[tuple[str, str]]:
    """Classify a blocking issue into categories."""
    matches = []
    text_lower = text.lower()
    for regex, category, description in PATTERN_CLASSIFIERS:
        if re.search(regex, text_lower):
            matches.append((category, description))
    if not matches:
        matches.append(("uncategorized", text[:80]))
    return matches


def mine_patterns(
    verdicts: list[VerdictInfo], min_occurrences: int = 2
) -> list[Pattern]:
    """Find recurring patterns across verdicts."""
    category_counts: Counter[str] = Counter()
    category_examples: dict[str, list[str]] = defaultdict(list)
    category_descriptions: dict[str, str] = {}

    for v in verdicts:
        if v.verdict == "PASS":
            continue

        # Classify blocking issues
        seen_categories: set[str] = set()
        for issue_text in v.blocking_issues:
            for category, description in classify_issue(issue_text):
                if category not in seen_categories:
                    category_counts[category] += 1
                    seen_categories.add(category)
                    category_descriptions[category] = description
                if len(category_examples[category]) < 5:
                    category_examples[category].append(
                        f"{v.issue_id}: {issue_text[:120]}"
                    )

        # Also check missing tests
        if v.missing_tests:
            category = "missing_test_scenarios"
            if category not in seen_categories:
                category_counts[category] += 1
                seen_categories.add(category)
                category_descriptions[category] = "Missing test scenarios for requirements"
            if len(category_examples[category]) < 5:
                category_examples[category].append(
                    f"{v.issue_id}: {len(v.missing_tests)} missing scenarios"
                )

    # Build patterns above threshold
    patterns = []
    for category, count in category_counts.most_common():
        if count >= min_occurrences:
            # Suggest Ponder rules for fixable patterns
            suggested = _suggest_ponder_rule(category)
            patterns.append(
                Pattern(
                    category=category,
                    description=category_descriptions.get(category, category),
                    occurrences=count,
                    example_verdicts=category_examples[category],
                    suggested_rule=suggested,
                )
            )

    return patterns


def _suggest_ponder_rule(category: str) -> str | None:
    """Suggest a Ponder auto-fix rule for a pattern category."""
    suggestions = {
        "section_heading_format": (
            "Already implemented in ponder_rules.py: fix_section_heading_format"
        ),
        "requirements_format": (
            "Potential rule: detect bullet/table format in Section 3, "
            "convert to numbered list"
        ),
        "req_references": (
            "Potential rule: scan test scenarios for missing (REQ-N) suffix, "
            "auto-add based on requirement mapping"
        ),
        "vague_assertions": (
            "Not auto-fixable — requires content judgment"
        ),
        "human_delegation": (
            "Not auto-fixable — requires test design judgment"
        ),
        "low_coverage": (
            "Not auto-fixable — requires new test scenarios"
        ),
        "invalid_paths": (
            "Potential rule: detect common path prefixes and normalize "
            "(e.g., scripts/ -> tools/)"
        ),
    }
    return suggestions.get(category)


def format_report(
    verdicts: list[VerdictInfo], patterns: list[Pattern]
) -> str:
    """Format the mining results as a human-readable report."""
    lines = [
        "# Verdict Pattern Mining Report",
        "",
        "## Summary",
        "",
        f"- Total verdicts scanned: {len(verdicts)}",
        f"- BLOCK verdicts: {sum(1 for v in verdicts if v.verdict == 'BLOCK')}",
        f"- PASS verdicts: {sum(1 for v in verdicts if v.verdict == 'PASS')}",
        f"- Other verdicts: {sum(1 for v in verdicts if v.verdict not in ('BLOCK', 'PASS'))}",
        f"- Unique patterns found: {len(patterns)}",
        "",
    ]

    # Coverage distribution
    coverages = [v.coverage_pct for v in verdicts if v.coverage_pct is not None]
    if coverages:
        avg_coverage = sum(coverages) / len(coverages)
        lines.extend([
            "## Coverage Distribution",
            "",
            f"- Average: {avg_coverage:.1f}%",
            f"- Min: {min(coverages):.1f}%",
            f"- Max: {max(coverages):.1f}%",
            f"- Below 95%: {sum(1 for c in coverages if c < 95)}",
            "",
        ])

    # Patterns
    lines.extend([
        "## Recurring Patterns (by frequency)",
        "",
    ])

    if not patterns:
        lines.append("No recurring patterns found above the threshold.")
        lines.append("")
    else:
        for p in patterns:
            lines.extend([
                f"### {p.category} ({p.occurrences} occurrences)",
                "",
                f"**Description:** {p.description}",
                "",
            ])
            if p.suggested_rule:
                lines.append(f"**Ponder rule:** {p.suggested_rule}")
                lines.append("")
            lines.append("**Examples:**")
            for ex in p.example_verdicts:
                lines.append(f"- {ex}")
            lines.append("")

    # Suggestions
    fixable = [p for p in patterns if p.suggested_rule and "Already" not in (p.suggested_rule or "")]
    already_fixed = [p for p in patterns if p.suggested_rule and "Already" in (p.suggested_rule or "")]
    not_fixable = [p for p in patterns if p.suggested_rule and "Not auto-fixable" in (p.suggested_rule or "")]

    lines.extend([
        "## Recommendations",
        "",
    ])

    if already_fixed:
        lines.append("### Already handled by Ponder")
        for p in already_fixed:
            lines.append(f"- **{p.category}**: {p.suggested_rule}")
        lines.append("")

    if fixable:
        lines.append("### Candidates for new Ponder rules")
        for p in fixable:
            lines.append(f"- **{p.category}** ({p.occurrences}x): {p.suggested_rule}")
        lines.append("")

    if not_fixable:
        lines.append("### Requires human judgment (not auto-fixable)")
        for p in not_fixable:
            lines.append(f"- **{p.category}** ({p.occurrences}x): {p.suggested_rule}")
        lines.append("")

    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mine verdict patterns from lineage for Ponder rules"
    )
    parser.add_argument(
        "--lineage-dir",
        default="docs/lineage/active",
        help="Lineage root directory (default: docs/lineage/active)",
    )
    parser.add_argument(
        "--min-occurrences",
        type=int,
        default=2,
        help="Minimum occurrences to report a pattern (default: 2)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print report to stdout (default behavior)",
    )
    parser.add_argument(
        "--output",
        help="Write report to file instead of stdout",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    lineage_dir = Path(args.lineage_dir)
    if not lineage_dir.exists():
        print(f"Error: lineage directory not found: {lineage_dir}", file=sys.stderr)
        return 1

    # Find all verdict files
    verdict_files = sorted(lineage_dir.glob("*/*verdict*.md"))
    if not verdict_files:
        print(f"No verdict files found in {lineage_dir}", file=sys.stderr)
        return 1

    print(f"Scanning {len(verdict_files)} verdict files...")

    # Parse all verdicts
    verdicts = []
    for vf in verdict_files:
        info = parse_verdict_file(vf)
        if info:
            verdicts.append(info)

    print(f"Parsed {len(verdicts)} verdicts successfully")

    # Mine patterns
    patterns = mine_patterns(verdicts, min_occurrences=args.min_occurrences)

    # Format report
    report = format_report(verdicts, patterns)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
