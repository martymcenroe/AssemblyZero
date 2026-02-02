I need to read the existing implementation files to understand what needs to be fixed.

Let me read the current implementation files:

```python
# File: tools/verdict_analyzer/__init__.py

"""Verdict Analyzer - Template improvement from Gemini verdicts."""

from __future__ import annotations

PARSER_VERSION = "1.0.0"

from tools.verdict_analyzer.parser import (
    BlockingIssue,
    VerdictRecord,
    compute_content_hash,
    parse_verdict,
)
from tools.verdict_analyzer.database import VerdictDatabase
from tools.verdict_analyzer.patterns import (
    CATEGORY_TO_SECTION,
    extract_patterns_from_issues,
    map_category_to_section,
    normalize_pattern,
)
from tools.verdict_analyzer.template_updater import (
    Recommendation,
    atomic_write_template,
    format_stats,
    generate_recommendations,
    parse_template_sections,
    validate_template_path,
)
from tools.verdict_analyzer.scanner import (
    discover_verdicts,
    find_registry,
    load_registry,
    scan_repos,
    validate_verdict_path,
)

__all__ = [
    "PARSER_VERSION",
    "BlockingIssue",
    "VerdictRecord",
    "compute_content_hash",
    "parse_verdict",
    "VerdictDatabase",
    "CATEGORY_TO_SECTION",
    "extract_patterns_from_issues",
    "map_category_to_section",
    "normalize_pattern",
    "Recommendation",
    "atomic_write_template",
    "format_stats",
    "generate_recommendations",
    "parse_template_sections",
    "validate_template_path",
    "discover_verdicts",
    "find_registry",
    "load_registry",
    "scan_repos",
    "validate_verdict_path",
]
```

```python
# File: tools/verdict_analyzer/parser.py

"""Parse verdict markdown files."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from tools.verdict_analyzer import PARSER_VERSION as _PARSER_VERSION


@dataclass
class BlockingIssue:
    """A blocking issue extracted from a verdict."""

    tier: int
    category: str
    description: str


@dataclass
class VerdictRecord:
    """A parsed verdict record."""

    filepath: str
    verdict_type: str
    decision: str
    content_hash: str
    parser_version: str
    blocking_issues: list[BlockingIssue] = field(default_factory=list)


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_verdict(filepath: Path) -> VerdictRecord:
    """Parse a verdict markdown file.

    Args:
        filepath: Path to the verdict markdown file.

    Returns:
        VerdictRecord with parsed data.
    """
    content = filepath.read_text(encoding="utf-8")
    content_hash = compute_content_hash(content)

    # Determine verdict type (LLD vs Issue)
    # LLD format: "# 105 - Feature: ..." or has "## 1. Context & Goal"
    # Issue format: "# Issue #42 - ..." or has "## User Story"
    verdict_type = "lld"
    if re.search(r"^#\s*Issue\s*#\d+", content, re.MULTILINE | re.IGNORECASE):
        verdict_type = "issue"
    elif "## User Story" in content or "## Acceptance Criteria" in content:
        verdict_type = "issue"

    # Extract decision (APPROVED, BLOCKED, CONDITIONAL)
    decision = "UNKNOWN"
    decision_match = re.search(
        r"##\s*Verdict:\s*(APPROVED|BLOCKED|CONDITIONAL)", content, re.IGNORECASE
    )
    if decision_match:
        decision = decision_match.group(1).upper()

    # Extract blocking issues by tier
    blocking_issues: list[BlockingIssue] = []

    # Find the Blocking Issues section
    blocking_section_match = re.search(
        r"##\s*Blocking Issues\s*(.*?)(?=^##[^#]|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )

    if blocking_section_match:
        blocking_section = blocking_section_match.group(1)

        # Parse each tier
        for tier in [1, 2, 3]:
            tier_match = re.search(
                rf"###\s*Tier\s*{tier}\s*(.*?)(?=###\s*Tier|\Z)",
                blocking_section,
                re.DOTALL | re.IGNORECASE,
            )
            if tier_match:
                tier_content = tier_match.group(1)

                # Extract bullet points
                bullets = re.findall(r"^\s*[-*]\s*(.+)$", tier_content, re.MULTILINE)
                for bullet in bullets:
                    # Clean up the bullet text
                    desc = bullet.strip()
                    # Remove bold markers
                    desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", desc)

                    # Infer category from description
                    category = _infer_category(desc)

                    blocking_issues.append(
                        BlockingIssue(tier=tier, category=category, description=desc)
                    )

    return VerdictRecord(
        filepath=str(filepath),
        verdict_type=verdict_type,
        decision=decision,
        content_hash=content_hash,
        parser_version=_PARSER_VERSION,
        blocking_issues=blocking_issues,
    )


def _infer_category(description: str) -> str:
    """Infer category from issue description."""
    desc_lower = description.lower()

    category_keywords = {
        "security": ["security", "vulnerability", "injection", "xss", "csrf", "auth"],
        "testing": ["test", "coverage", "unit test", "integration"],
        "error_handling": ["error", "exception", "handling", "try", "catch"],
        "documentation": ["doc", "comment", "readme", "example"],
        "performance": ["performance", "slow", "optimize", "cache"],
        "logging": ["log", "logging", "debug", "trace"],
        "validation": ["valid", "input", "sanitize", "check"],
        "architecture": ["architecture", "design", "pattern", "structure"],
    }

    for category, keywords in category_keywords.items():
        if any(kw in desc_lower for kw in keywords):
            return category

    return "general"
```

```python
# File: tools/verdict_analyzer/database.py

"""SQLite database operations for verdict storage."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from tools.verdict_analyzer import PARSER_VERSION
from tools.verdict_analyzer.parser import BlockingIssue, VerdictRecord

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


class VerdictDatabase:
    """SQLite database for storing parsed verdicts."""

    def __init__(self, db_path: Path | str) -> None:
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)

        # Create parent directory if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        cursor = self.conn.cursor()

        # Create schema version table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
        """)

        # Check current version
        cursor.execute("SELECT version FROM schema_version")
        row = cursor.fetchone()

        if row is None:
            # Fresh database, create tables
            cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            self._create_tables(cursor)
        elif row["version"] < SCHEMA_VERSION:
            # Need migration
            self._migrate(cursor, row["version"])

        self.conn.commit()

    def _create_tables(self, cursor: sqlite3.Cursor) -> None:
        """Create database tables."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verdicts (
                filepath TEXT PRIMARY KEY,
                verdict_type TEXT NOT NULL,
                decision TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                parser_version TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blocking_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                verdict_filepath TEXT NOT NULL,
                tier INTEGER NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                FOREIGN KEY (verdict_filepath) REFERENCES verdicts(filepath)
                    ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_issues_verdict
            ON blocking_issues(verdict_filepath)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_issues_category
            ON blocking_issues(category)
        """)

    def _migrate(self, cursor: sqlite3.Cursor, from_version: int) -> None:
        """Run database migrations."""
        # Currently no migrations needed
        cursor.execute(
            "UPDATE schema_version SET version = ?", (SCHEMA_VERSION,)
        )

    def migrate(self) -> None:
        """Public method to run migrations."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT version FROM schema_version")
        row = cursor.fetchone()
        if row and row["version"] < SCHEMA_VERSION:
            self._migrate(cursor, row["version"])
            self.conn.commit()

    def needs_update(self, filepath: str, content_hash: str) -> bool:
        """Check if a verdict needs to be re-parsed.

        Args:
            filepath: Path to verdict file.
            content_hash: Current content hash.

        Returns:
            True if verdict needs update, False otherwise.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT content_hash, parser_version FROM verdicts WHERE filepath = ?",
            (filepath,),
        )
        row = cursor.fetchone()

        if row is None:
            return True

        # Check content hash
        if row["content_hash"] != content_hash:
            return True

        # Check parser version
        if row["parser_version"] != PARSER_VERSION:
            return True

        return False

    def upsert_verdict(self, record: VerdictRecord) -> None:
        """Insert or update a verdict record.

        Args:
            record: VerdictRecord to store.
        """
        cursor = self.conn.cursor()

        # Upsert verdict
        cursor.execute(
            """
            INSERT INTO verdicts (filepath, verdict_type, decision, content_hash, parser_version, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(filepath) DO UPDATE SET
                verdict_type = excluded.verdict_type,
                decision = excluded.decision,
                content_hash = excluded.content_hash,
                parser_version = excluded.parser_version,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                record.filepath,
                record.verdict_type,
                record.decision,
                record.content_hash,
                record.parser_version,
            ),
        )

        # Delete existing blocking issues
        cursor.execute(
            "DELETE FROM blocking_issues WHERE verdict_filepath = ?",
            (record.filepath,),
        )

        # Insert new blocking issues
        for issue in record.blocking_issues:
            cursor.execute(
                """
                INSERT INTO blocking_issues (verdict_filepath, tier, category, description)
                VALUES (?, ?, ?, ?)
                """,
                (record.filepath, issue.tier, issue.category, issue.description),
            )

        self.conn.commit()

    def get_all_verdicts(self) -> list[VerdictRecord]:
        """Get all verdicts from database.

        Returns:
            List of VerdictRecord objects.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM verdicts")
        verdict_rows = cursor.fetchall()

        records = []
        for vrow in verdict_rows:
            # Get blocking issues for this verdict
            cursor.execute(
                "SELECT tier, category, description FROM blocking_issues WHERE verdict_filepath = ?",
                (vrow["filepath"],),
            )
            issue_rows = cursor.fetchall()

            issues = [
                BlockingIssue(
                    tier=irow["tier"],
                    category=irow["category"],
                    description=irow["description"],
                )
                for irow in issue_rows
            ]

            records.append(
                VerdictRecord(
                    filepath=vrow["filepath"],
                    verdict_type=vrow["verdict_type"],
                    decision=vrow["decision"],
                    content_hash=vrow["content_hash"],
                    parser_version=vrow["parser_version"],
                    blocking_issues=issues,
                )
            )

        return records

    def get_verdict(self, filepath: str) -> VerdictRecord | None:
        """Get a single verdict by filepath.

        Args:
            filepath: Path to verdict file.

        Returns:
            VerdictRecord if found, None otherwise.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM verdicts WHERE filepath = ?", (filepath,))
        row = cursor.fetchone()

        if row is None:
            return None

        # Get blocking issues
        cursor.execute(
            "SELECT tier, category, description FROM blocking_issues WHERE verdict_filepath = ?",
            (filepath,),
        )
        issue_rows = cursor.fetchall()

        issues = [
            BlockingIssue(
                tier=irow["tier"],
                category=irow["category"],
                description=irow["description"],
            )
            for irow in issue_rows
        ]

        return VerdictRecord(
            filepath=row["filepath"],
            verdict_type=row["verdict_type"],
            decision=row["decision"],
            content_hash=row["content_hash"],
            parser_version=row["parser_version"],
            blocking_issues=issues,
        )

    def delete_verdict(self, filepath: str) -> None:
        """Delete a verdict from database.

        Args:
            filepath: Path to verdict file.
        """
        cursor = self.conn.cursor()
        # Issues are deleted via CASCADE
        cursor.execute("DELETE FROM verdicts WHERE filepath = ?", (filepath,))
        self.conn.commit()

    def get_stats(self) -> dict:
        """Get statistics from database.

        Returns:
            Dictionary with statistics.
        """
        cursor = self.conn.cursor()

        # Total verdicts
        cursor.execute("SELECT COUNT(*) as count FROM verdicts")
        total_verdicts = cursor.fetchone()["count"]

        # Total issues
        cursor.execute("SELECT COUNT(*) as count FROM blocking_issues")
        total_issues = cursor.fetchone()["count"]

        # Decisions breakdown
        cursor.execute(
            "SELECT decision, COUNT(*) as count FROM verdicts GROUP BY decision"
        )
        decisions = {row["decision"]: row["count"] for row in cursor.fetchall()}

        # Tier breakdown
        cursor.execute(
            "SELECT tier, COUNT(*) as count FROM blocking_issues GROUP BY tier"
        )
        tiers = {row["tier"]: row["count"] for row in cursor.fetchall()}

        # Category breakdown
        cursor.execute(
            "SELECT category, COUNT(*) as count FROM blocking_issues GROUP BY category ORDER BY count DESC"
        )
        categories = {row["category"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_verdicts": total_verdicts,
            "total_issues": total_issues,
            "decisions": decisions,
            "tiers": tiers,
            "categories": categories,
        }

    def get_patterns_by_category(self) -> dict[str, list[str]]:
        """Get patterns grouped by category.

        Returns:
            Dictionary mapping category to list of descriptions.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT category, description FROM blocking_issues ORDER BY category"
        )

        patterns: dict[str, list[str]] = {}
        for row in cursor.fetchall():
            category = row["category"]
            if category not in patterns:
                patterns[category] = []
            patterns[category].append(row["description"])

        return patterns

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    def __enter__(self) -> "VerdictDatabase":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
```

```python
# File: tools/verdict_analyzer/patterns.py

"""Pattern extraction and normalization."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.verdict_analyzer.parser import BlockingIssue

# Mapping from categories to template sections
CATEGORY_TO_SECTION = {
    "security": "Security Considerations",
    "testing": "Testing Strategy",
    "error_handling": "Error Handling",
    "documentation": "Documentation",
    "performance": "Performance Considerations",
    "logging": "Logging & Monitoring",
    "validation": "Input Validation",
    "architecture": "Architecture & Design",
    "general": "Implementation Notes",
    "database": "Data Storage",
    "api": "API Design",
}


def normalize_pattern(description: str) -> str:
    """Normalize a description into a pattern.

    Replaces specific details with placeholders for pattern matching.

    Args:
        description: Raw description from blocking issue.

    Returns:
        Normalized pattern string.
    """
    pattern = description

    # Replace file paths and names with <file>
    # Match patterns like file.py, path/to/file.js, etc.
    pattern = re.sub(r"\b[\w./\\-]+\.(py|js|ts|md|json|yaml|yml|sh|sql)\b", "<file>", pattern)

    # Replace line numbers with <line>
    pattern = re.sub(r"\bline\s*\d+\b", "line <line>", pattern, flags=re.IGNORECASE)

    # Replace absolute paths with <path>
    pattern = re.sub(r"(/[\w./\\-]+|[A-Z]:\\[\w.\\-]+)", "<path>", pattern)

    # Replace numbers (but not tier numbers or single digits in context)
    pattern = re.sub(r"\b\d{2,}\b", "<num>", pattern)

    # Normalize whitespace
    pattern = " ".join(pattern.split())

    return pattern


def map_category_to_section(category: str) -> str:
    """Map a category to its template section.

    Args:
        category: Category name.

    Returns:
        Template section name.
    """
    return CATEGORY_TO_SECTION.get(category, "Implementation Notes")


def extract_patterns_from_issues(issues: list["BlockingIssue"]) -> dict[str, int]:
    """Extract and count patterns from blocking issues.

    Args:
        issues: List of BlockingIssue objects.

    Returns:
        Dictionary mapping normalized patterns to counts.
    """
    if not issues:
        return {}

    pattern_counts: dict[str, int] = {}

    for issue in issues:
        pattern = normalize_pattern(issue.description)
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

    return pattern_counts
```

```python
# File: tools/verdict_analyzer/template_updater.py

"""Template modification with atomic writes."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from tools.verdict_analyzer.patterns import CATEGORY_TO_SECTION


@dataclass
class Recommendation:
    """A template improvement recommendation."""

    rec_type: str  # "add_section", "add_checklist_item", "add_example"
    section: str
    content: str
    pattern_count: int


def parse_template_sections(content: str) -> dict[str, str]:
    """Parse a template into sections.

    Args:
        content: Template markdown content.

    Returns:
        Dictionary mapping section names to their content.
    """
    if not content:
        return {}

    sections: dict[str, str] = {}

    # Find all headers (## and ###)
    header_pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
    matches = list(header_pattern.finditer(content))

    if not matches:
        return {}

    for i, match in enumerate(matches):
        section_name = match.group(2).strip()
        start = match.end()

        # Find end (next header or EOF)
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(content)

        section_content = content[start:end].strip()
        sections[section_name] = section_content

    return sections


def generate_recommendations(
    pattern_stats: dict,
    existing_sections: dict[str, str],
    min_pattern_count: int = 3,
) -> list[Recommendation]:
    """Generate template improvement recommendations.

    Args:
        pattern_stats: Statistics from pattern analysis.
        existing_sections: Existing template sections.
        min_pattern_count: Minimum count to generate recommendation.

    Returns:
        List of Recommendation objects.
    """
    recommendations: list[Recommendation] = []

    categories = pattern_stats.get("categories", {})

    for category, count in categories.items():
        if count < min_pattern_count:
            continue

        section = CATEGORY_TO_SECTION.get(category, "Implementation Notes")

        if section not in existing_sections:
            # Recommend adding new section
            recommendations.append(
                Recommendation(
                    rec_type="add_section",
                    section=section,
                    content=f"Add {section} section to address common {category} issues",
                    pattern_count=count,
                )
            )
        else:
            # Recommend adding checklist item
            recommendations.append(
                Recommendation(
                    rec_type="add_checklist_item",
                    section=section,
                    content=f"Add checklist item for {category} validation",
                    pattern_count=count,
                )
            )

    return recommendations


def atomic_write_template(filepath: Path, content: str) -> Path:
    """Write template content atomically with backup.

    Args:
        filepath: Path to template file.
        content: New content to write.

    Returns:
        Path to backup file.
    """
    # Create backup
    backup_path = filepath.with_suffix(filepath.suffix + ".bak")
    shutil.copy2(filepath, backup_path)

    # Write new content
    filepath.write_text(content, encoding="utf-8")

    return backup_path


def validate_template_path(filepath: Path, base_dir: Path) -> None:
    """Validate template path is within base directory.

    Args:
        filepath: Path to validate.
        base_dir: Base directory path must be within.

    Raises:
        ValueError: If path is outside base directory.
    """
    try:
        filepath.resolve().relative_to(base_dir.resolve())
    except ValueError:
        raise ValueError(
            f"Path traversal detected: {filepath} is not within {base_dir}"
        )


def format_stats(stats: dict) -> str:
    """Format statistics for display.

    Args:
        stats: Statistics dictionary.

    Returns:
        Formatted string.
    """
    lines = [
        f"Total Verdicts: {stats.get('total_verdicts', 0)}",
        f"Total Blocking Issues: {stats.get('total_issues', 0)}",
        "",
        "Decisions:",
    ]

    for decision, count in stats.get("decisions", {}).items():
        lines.append(f"  {decision}: {count}")

    lines.append("")
    lines.append("By Tier:")

    for tier, count in stats.get("tiers", {}).items():
        lines.append(f"  Tier {tier}: {count}")

    lines.append("")
    lines.append("By Category:")

    for category, count in stats.get("categories", {}).items():
        lines.append(f"  {category}: {count}")

    return "\n".join(lines)
```

```python
# File: tools/verdict_analyzer/scanner.py

"""Multi-repo verdict discovery and scanning."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterator

from tools.verdict_analyzer.database import VerdictDatabase
from tools.verdict_analyzer.parser import compute_content_hash, parse_verdict

logger = logging.getLogger(__name__)


def find_registry(start_path: Path) -> Path | None:
    """Find project-registry.json by searching up directory tree.

    Args:
        start_path: Directory to start searching from.

    Returns:
        Path to registry file, or None if not found.
    """
    current = start_path.resolve()

    while current != current.parent:
        registry = current / "project-registry.json"
        if registry.exists():
            return registry
        current = current.parent

    # Check root
    registry = current / "project-registry.json"
    if registry.exists():
        return registry

    return None


def load_registry(registry_path: Path) -> list[Path]:
    """Load repository paths from registry.

    Args:
        registry_path: Path to project-registry.json.

    Returns:
        List of existing repository paths.
    """
    with open(registry_path, encoding="utf-8") as f:
        data = json.load(f)

    repos = []
    for repo_str in data:
        repo_path = Path(repo_str)
        if repo_path.exists():
            repos.append(repo_path)
        else:
            logger.warning(f"Repository not found: {repo_path}")

    return repos


def validate_verdict_path(verdict_path: Path, base_dir: Path) -> bool:
    """Validate verdict path is within base directory.

    Args:
        verdict_path: Path to validate.
        base_dir: Base directory path must be within.

    Returns:
        True if path is valid, False otherwise.
    """
    try:
        verdict_path.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False


def discover_verdicts(repo_path: Path) -> Iterator[Path]:
    """Discover verdict files in a repository.

    Args:
        repo_path: Path to repository root.

    Yields:
        Paths to verdict markdown files.
    """
    # Look in common verdict locations
    verdict_dirs = [
        repo_path / "docs" / "verdicts",
        repo_path / "verdicts",
        repo_path / ".verdicts",
    ]

    seen_paths: set[Path] = set()

    for verdict_dir in verdict_dirs:
        if not verdict_dir.exists():
            continue

        try:
            # Use iterdir + recursion to handle symlink loops
            yield from _scan_directory(verdict_dir, seen_paths, repo_path)
        except OSError as e:
            logger.warning(f"Error scanning {verdict_dir}: {e}")


def _scan_directory(
    directory: Path, seen: set[Path], base_dir: Path
) -> Iterator[Path]:
    """Recursively scan directory for verdict files.

    Args:
        directory: Directory to scan.
        seen: Set of already-seen real paths (for loop detection).
        base_dir: Base directory for path validation.

    Yields:
        Paths to verdict markdown files.
    """
    try:
        real_path = directory.resolve()
    except OSError:
        return

    # Check for symlink loops
    if real_path in seen:
        logger.warning(f"Symlink loop detected at {directory}")
        return

    seen.add(real_path)

    try:
        for entry in directory.iterdir():
            if entry.is_file() and entry.suffix == ".md":
                if validate_verdict_path(entry, base_dir):
                    yield entry
            elif entry.is_dir():
                yield from _scan_directory(entry, seen, base_dir)
    except OSError as e:
        logger.warning(f"Error reading directory {directory}: {e}")


def scan_repos(
    registry_path: Path,
    db_path: Path,
    force: bool = False,
) -> int:
    """Scan repositories and update database.

    Args:
        registry_path: Path to project-registry.json.
        db_path: Path to SQLite database.
        force: If True, re-parse all verdicts regardless of hash.

    Returns:
        Number of verdicts processed.
    """
    repos = load_registry(registry_path)
    db = VerdictDatabase(db_path)

    count = 0

    try:
        for repo in repos:
            logger.info(f"Scanning repository: {repo}")

            for verdict_path in discover_verdicts(repo):
                try:
                    content = verdict_path.read_text(encoding="utf-8")
                    content_hash = compute_content_hash(content)

                    if not force and not db.needs_update(str(verdict_path), content_hash):
                        logger.debug(f"Skipping unchanged: {verdict_path}")
                        continue

                    logger.debug(f"Parsing: {verdict_path}")
                    record = parse_verdict(verdict_path)
                    db.upsert_verdict(record)
                    count += 1

                except Exception as e:
                    logger.error(f"Error parsing {verdict_path}: {e}")

    finally:
        db.close()

    return count
```

Now I see the issue - there's a circular import problem. The `parser.py` imports `PARSER_VERSION` from `__init__.py`, but `__init__.py` imports from `parser.py`. Let me fix this by moving `PARSER_VERSION` to a separate constants file or defining it directly in parser.py.

```python
# File: tools/verdict_analyzer/__init__.py

"""Verdict Analyzer - Template improvement from Gemini verdicts."""

from __future__ import annotations

# Define PARSER_VERSION here first, before any imports
PARSER_VERSION = "1.0.0"

from tools.verdict_analyzer.parser import (
    BlockingIssue,
    VerdictRecord,
    compute_content_hash,
    parse_verdict,
)
from tools.verdict_analyzer.database import VerdictDatabase
from tools.verdict_analyzer.patterns import (
    CATEGORY_TO_SECTION,
    extract_patterns_from_issues,
    map_category_to_section,
    normalize_pattern,
)
from tools.verdict_analyzer.template_updater import (
    Recommendation,
    atomic_write_template,
    format_stats,
    generate_recommendations,
    parse_template_sections,
    validate_template_path,
)
from tools.verdict_analyzer.scanner import (
    discover_verdicts,
    find_registry,
    load_registry,
    scan_repos,
    validate_verdict_path,
)

__all__ = [
    "PARSER_VERSION",
    "BlockingIssue",
    "VerdictRecord",
    "compute_content_hash",
    "parse_verdict",
    "VerdictDatabase",
    "CATEGORY_TO_SECTION",
    "extract_patterns_from_issues",
    "map_category_to_section",
    "normalize_pattern",
    "Recommendation",
    "atomic_write_template",
    "format_stats",
    "generate_recommendations",
    "parse_template_sections",
    "validate_template_path",
    "discover_verdicts",
    "find_registry",
    "load_registry",
    "scan_repos",
    "validate_verdict_path",
]
```

```python
# File: tools/verdict_analyzer/parser.py

"""Parse verdict markdown files."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

# Define PARSER_VERSION locally to avoid circular import
PARSER_VERSION = "1.0.0"


@dataclass
class BlockingIssue:
    """A blocking issue extracted from a verdict."""

    tier: int
    category: str
    description: str


@dataclass
class VerdictRecord:
    """A parsed verdict record."""

    filepath: str
    verdict_type: str
    decision: str
    content_hash: str
    parser_version: str
    blocking_issues: list[BlockingIssue] = field(default_factory=list)


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_verdict(filepath: Path) -> VerdictRecord:
    """Parse a verdict markdown file.

    Args:
        filepath: Path to the verdict markdown file.

    Returns:
        VerdictRecord with parsed data.
    """
    content = filepath.read_text(encoding="utf-8")
    content_hash = compute_content_hash(content)

    # Determine verdict type (LLD vs Issue)
    # LLD format: "# 105 - Feature: ..." or has "## 1. Context & Goal"
    # Issue format: "# Issue #42 - ..." or has "## User Story"
    verdict_type = "lld"
    if re.search(r"^#\s*Issue\s*#\d+", content, re.MULTILINE | re.IGNORECASE):
        verdict_type = "issue"
    elif "## User Story" in content or "## Acceptance Criteria" in content:
        verdict_type = "issue"

    # Extract decision (APPROVED, BLOCKED, CONDITIONAL)
    decision = "UNKNOWN"
    decision_match = re.search(
        r"##\s*Verdict:\s*(APPROVED|BLOCKED|CONDITIONAL)", content, re.IGNORECASE
    )
    if decision_match:
        decision = decision_match.group(1).upper()

    # Extract blocking issues by tier
    blocking_issues: list[BlockingIssue] = []

    # Find the Blocking Issues section
    blocking_section_match = re.search(
        r"##\s*Blocking Issues\s*(.*?)(?=^##[^#]|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )

    if blocking_section_match:
        blocking_section = blocking_section_match.group(1)

        # Parse each tier
        for tier in [1, 2, 3]:
            tier_match = re.search(
                rf"###\s*Tier\s*{tier}\s*(.*?)(?=###\s*Tier|\Z)",
                blocking_section,
                re.DOTALL | re.IGNORECASE,
            )
            if tier_match:
                tier_content = tier_match.group(1)

                # Extract bullet points
                bullets = re.findall(r"^\s*[-*]\s*(.+)$", tier_content, re.MULTILINE)
                for bullet in bullets:
                    # Clean up the bullet text
                    desc = bullet.strip()
                    # Remove bold markers
                    desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", desc)

                    # Infer category from description
                    category = _infer_category(desc)

                    blocking_issues.append(
                        BlockingIssue(tier=tier, category=category, description=desc)
                    )

    return VerdictRecord(
        filepath=str(filepath),
        verdict_type=verdict_type,
        decision=decision,
        content_hash=content_hash,
        parser_version=PARSER_VERSION,
        blocking_issues=blocking_issues,
    )


def _infer_category(description: str) -> str:
    """Infer category from issue description."""
    desc_lower = description.lower()

    category_keywords = {
        "security": ["security", "vulnerability", "injection", "xss", "csrf", "auth"],
        "testing": ["test", "coverage", "unit test", "integration"],
        "error_handling": ["error", "exception", "handling", "try", "catch"],
        "documentation": ["doc", "comment", "readme", "example"],
        "performance": ["performance", "slow", "optimize", "cache"],
        "logging": ["log", "logging", "debug", "trace"],
        "validation": ["valid", "input", "sanitize", "check"],
        "architecture": ["architecture", "design", "pattern", "structure"],
    }

    for category, keywords in category_keywords.items():
        if any(kw in desc_lower for kw in keywords):
            return category

    return "general"
```

```python
# File: tools/verdict_analyzer/database.py

"""SQLite database operations for verdict storage."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from tools.verdict_analyzer.parser import PARSER_VERSION, BlockingIssue, VerdictRecord

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


class VerdictDatabase:
    """SQLite database for storing parsed verdicts."""

    def __init__(self, db_path: Path | str) -> None:
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)

        # Create parent directory if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        cursor = self.conn.cursor()

        # Create schema version table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
        """)

        # Check current version
        cursor.execute("SELECT version FROM schema_version")
        row = cursor.fetchone()

        if row is None:
            # Fresh database, create tables
            cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            self._create_tables(cursor)
        elif row["version"] < SCHEMA_VERSION:
            # Need migration
            self._migrate(cursor, row["version"])

        self.conn.commit()

    def _create_tables(self, cursor: sqlite3.Cursor) -> None:
        """Create database tables."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verdicts (
                filepath TEXT PRIMARY KEY,
                verdict_type TEXT NOT NULL,
                decision TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                parser_version TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blocking_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                verdict_filepath TEXT NOT NULL,
                tier INTEGER NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                FOREIGN KEY (verdict_filepath) REFERENCES verdicts(filepath)
                    ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_issues_verdict
            ON blocking_issues(verdict_filepath)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_issues_category
            ON blocking_issues(category)
        """)

    def _migrate(self, cursor: sqlite3.Cursor, from_version: int) -> None:
        """Run database migrations."""
        # Currently no migrations needed
        cursor.execute(
            "UPDATE schema_version SET version = ?", (SCHEMA_VERSION,)
        )

    def migrate(self) -> None:
        """Public method to run migrations."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT version FROM schema_version")
        row = cursor.fetchone()
        if row and row["version"] < SCHEMA_VERSION:
            self._migrate(cursor, row["version"])
            self.conn.commit()

    def needs_update(self, filepath: str, content_hash: str) -> bool:
        """Check if a verdict needs to be re-parsed.

        Args:
            filepath: Path to verdict file.
            content_hash: Current content hash.

        Returns:
            True if verdict needs update, False otherwise.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT content_hash, parser_version FROM verdicts WHERE filepath = ?",
            (filepath,),
        )
        row = cursor.fetchone()

        if row is None:
            return True

        # Check content hash
        if row["content_hash"] != content_hash:
            return True

        # Check parser version
        if row["parser_version"] != PARSER_VERSION:
            return True

        return False

    def upsert_verdict(self, record: VerdictRecord) -> None:
        """Insert or update a verdict record.

        Args:
            record: VerdictRecord to store.
        """
        cursor = self.conn.cursor()

        # Upsert verdict
        cursor.execute(
            """
            INSERT INTO verdicts (filepath, verdict_type, decision, content_hash, parser_version, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(filepath) DO UPDATE SET
                verdict_type = excluded.verdict_type,
                decision = excluded.decision,
                content_hash = excluded.content_hash,
                parser_version = excluded.parser_version,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                record.filepath,
                record.verdict_type,
                record.decision,
                record.content_hash,
                record.parser_version,
            ),
        )

        # Delete existing blocking issues
        cursor.execute(
            "DELETE FROM blocking_issues WHERE verdict_filepath = ?",
            (record.filepath,),
        )

        # Insert new blocking issues
        for issue in record.blocking_issues:
            cursor.execute(
                """
                INSERT INTO blocking_issues (verdict_filepath, tier, category, description)
                VALUES (?, ?, ?, ?)
                """,
                (record.filepath, issue.tier, issue.category, issue.description),
            )

        self.conn.commit()

    def get_all_verdicts(self) -> list[VerdictRecord]:
        """Get all verdicts from database.

        Returns:
            List of VerdictRecord objects.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM verdicts")
        verdict_rows = cursor.fetchall()

        records = []
        for vrow in verdict_rows:
            # Get blocking issues for this verdict
            cursor.execute(
                "SELECT tier, category, description FROM blocking_issues WHERE verdict_filepath = ?",
                (vrow["filepath"],),
            )
            issue_rows = cursor.fetchall()

            issues = [
                BlockingIssue(
                    tier=irow["tier"],
                    category=irow["category"],
                    description=irow["description"],
                )
                for irow in issue_rows
            ]

            records.append(
                VerdictRecord(
                    filepath=vrow["filepath"],
                    verdict_type=vrow["verdict_type"],
                    decision=vrow["decision"],
                    content_hash=vrow["content_hash"],
                    parser_version=vrow["parser_version"],
                    blocking_issues=issues,
                )
            )

        return records

    def get_verdict(self, filepath: str) -> VerdictRecord | None:
        """Get a single verdict by filepath.

        Args:
            filepath: Path to verdict file.

        Returns:
            VerdictRecord if found, None otherwise.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM verdicts WHERE filepath = ?", (filepath,))
        row = cursor.fetchone()

        if row is None:
            return None

        # Get blocking issues
        cursor.execute(
            "SELECT tier, category, description FROM blocking_issues WHERE verdict_filepath = ?",
            (filepath,),
        )
        issue_rows = cursor.fetchall()

        issues = [
            BlockingIssue(
                tier=irow["tier"],
                category=irow["category"],
                description=irow["description"],
            )
            for irow in issue_rows
        ]

        return VerdictRecord(
            filepath=row["filepath"],
            verdict_type=row["verdict_type"],
            decision=row["decision"],
            content_hash=row["content_hash"],
            parser_version=row["parser_version"],
            blocking_issues=issues,
        )

    def delete_verdict(self, filepath: str) -> None:
        """Delete a verdict from database.

        Args:
            filepath: Path to verdict file.
        """
        cursor = self.conn.cursor()
        # Issues are deleted via CASCADE
        cursor.execute("DELETE FROM verdicts WHERE filepath = ?", (filepath,))
        self.conn.commit()

    def get_stats(self) -> dict:
        """Get statistics from database.

        Returns:
            Dictionary with statistics.
        """
        cursor = self.conn.cursor()

        # Total verdicts
        cursor.execute("SELECT COUNT(*) as count FROM verdicts")
        total_verdicts = cursor.fetchone()["count"]

        # Total issues
        cursor.execute("SELECT COUNT(*) as count FROM blocking_issues")
        total_issues = cursor.fetchone()["count"]

        # Decisions breakdown
        cursor.execute(
            "SELECT decision, COUNT(*) as count FROM verdicts GROUP BY decision"
        )
        decisions = {row["decision"]: row["count"] for row in cursor.fetchall()}

        # Tier breakdown
        cursor.execute(
            "SELECT tier, COUNT(*) as count FROM blocking_issues GROUP BY tier"
        )
        tiers = {row["tier"]: row["count"] for row in cursor.fetchall()}

        # Category breakdown
        cursor.execute(
            "SELECT category, COUNT(*) as count FROM blocking_issues GROUP BY category ORDER BY count DESC"
        )
        categories = {row["category"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_verdicts": total_verdicts,
            "total_issues": total_issues,
            "decisions": decisions,
            "tiers": tiers,
            "categories": categories,
        }

    def get_patterns_by_category(self) -> dict[str, list[str]]:
        """Get patterns grouped by category.

        Returns:
            Dictionary mapping category to list of descriptions.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT category, description FROM blocking_issues ORDER BY category"
        )

        patterns: dict[str, list[str]] = {}
        for row in cursor.fetchall():
            category = row["category"]
            if category not in patterns:
                patterns[category] = []
            patterns[category].append(row["description"])

        return patterns

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    def __enter__(self) -> "VerdictDatabase":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
```

```python
# File: tools/verdict_analyzer/patterns.py

"""Pattern extraction and normalization."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.verdict_analyzer.parser import BlockingIssue

# Mapping from categories to template sections
CATEGORY_TO_SECTION = {
    "security": "Security Considerations",
    "testing": "Testing Strategy",
    "error_handling": "Error Handling",
    "documentation": "Documentation",
    "performance": "Performance Considerations",
    "logging": "Logging & Monitoring",
    "validation": "Input Validation",
    "architecture": "Architecture & Design",
    "general": "Implementation Notes",
    "database": "Data Storage",
    "api": "API Design",
}


def normalize_pattern(description: str) -> str:
    """Normalize a description into a pattern.

    Replaces specific details with placeholders for pattern matching.

    Args:
        description: Raw description from blocking issue.

    Returns:
        Normalized pattern string.
    """
    pattern = description

    # Replace file paths and names with <file>
    # Match patterns like file.py, path/to/file.js, etc.
    pattern = re.sub(r"\b[\w./\\-]+\.(py|js|ts|md|json|yaml|yml|sh|sql)\b", "<file>", pattern)

    # Replace line numbers with <line>
    pattern = re.sub(r"\bline\s*\d+\b", "line <line>", pattern, flags=re.IGNORECASE)

    # Replace absolute paths with <path>
    pattern = re.sub(r"(/[\w./\\-]+|[A-Z]:\\[\w.\\-]+)", "<path>", pattern)

    # Replace numbers (but not tier numbers or single digits in context)
    pattern = re.sub(r"\b\d{2,}\b", "<num>", pattern)

    # Normalize whitespace
    pattern = " ".join(pattern.split())

    return pattern


def map_category_to_section(category: str) -> str:
    """Map a category to its template section.

    Args:
        category: Category name.

    Returns:
        Template section name.
    """
    return CATEGORY_TO_SECTION.get(category, "Implementation Notes")


def extract_patterns_from_issues(issues: list["BlockingIssue"]) -> dict[str, int]:
    """Extract and count patterns from blocking issues.

    Args:
        issues: List of BlockingIssue objects.

    Returns:
        Dictionary mapping normalized patterns to counts.
    """
    if not issues:
        return {}

    pattern_counts: dict[str, int] = {}

    for issue in issues:
        pattern = normalize_pattern(issue.description)
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

    return pattern_counts
```

```python
# File: tools/verdict_analyzer/template_updater.py

"""Template modification with atomic writes."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from tools.verdict_analyzer.patterns import CATEGORY_TO_SECTION


@dataclass
class Recommendation:
    """A template improvement recommendation."""

    rec_type: str  # "add_section", "add_checklist_item", "add_example"
    section: str
    content: str
    pattern_count: int


def parse_template_sections(content: str) -> dict[str, str]:
    """Parse a template into sections.

    Args:
        content: Template markdown content.

    Returns:
        Dictionary mapping section names to their content.
    """
    if not content:
        return {}

    sections: dict[str, str] = {}

    # Find all headers (## and ###)
    header_pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
    matches = list(header_pattern.finditer(content))

    if not matches:
        return {}

    for i, match in enumerate(matches):
        section_name = match.group(2).strip()
        start = match.end()

        # Find end (next header or EOF)
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(content)

        section_content = content[start:end].strip()
        sections[section_name] = section_content

    return sections


def generate_recommendations(
    pattern_stats: dict,
    existing_sections: dict[str, str],
    min_pattern_count: int = 3,
) -> list[Recommendation]:
    """Generate template improvement recommendations.

    Args:
        pattern_stats: Statistics from pattern analysis.
        existing_sections: Existing template sections.
        min_pattern_count: Minimum count to generate recommendation.

    Returns:
        List of Recommendation objects.
    """
    recommendations: list[Recommendation] = []

    categories = pattern_stats.get("categories", {})

    for category, count in categories.items():
        if count < min_pattern_count:
            continue

        section = CATEGORY_TO_SECTION.get(category, "Implementation Notes")

        if section not in existing_sections:
            # Recommend adding new section
            recommendations.append(
                Recommendation(
                    rec_type="add_section",
                    section=section,
                    content=f"Add {section} section to address common {category} issues",
                    pattern_count=count,
                )
            )
        else:
            # Recommend adding checklist item
            recommendations.append(
                Recommendation(
                    rec_type="add_checklist_item",
                    section=section,
                    content=f"Add checklist item for {category} validation",
                    pattern_count=count,
                )
            )

    return recommendations


def atomic_write_template(filepath: Path, content: str) -> Path:
    """Write template content atomically with backup.

    Args:
        filepath: Path to template file.
        content: New content to write.

    Returns:
        Path to backup file.
    """
    # Create backup
    backup_path = filepath.with_suffix(filepath.suffix + ".bak")
    shutil.copy2(filepath, backup_path)

    # Write new content
    filepath.write_text(content, encoding="utf-8")

    return backup_path


def validate_template_path(filepath: Path, base_dir: Path) -> None:
    """Validate template path is within base directory.

    Args:
        filepath: Path to validate.
        base_dir: Base directory path must be within.

    Raises:
        ValueError: If path is outside base directory.
    """
    try:
        filepath.resolve().relative_to(base_dir.resolve())
    except ValueError:
        raise ValueError(
            f"Path traversal detected: {filepath} is not within {base_dir}"
        )


def format_stats(stats: dict) -> str:
    """Format statistics for display.

    Args:
        stats: Statistics dictionary.

    Returns:
        Formatted string.
    """
    lines = [
        f"Total Verdicts: {stats.get('total_verdicts', 0)}",
        f"Total Blocking Issues: {stats.get('total_issues', 0)}",
        "",
        "Decisions:",
    ]

    for decision, count in stats.get("decisions", {}).items():
        lines.append(f"  {decision}: {count}")

    lines.append("")
    lines.append("By Tier:")

    for tier, count in stats.get("tiers", {}).items():
        lines.append(f"  Tier {tier}: {count}")

    lines.append("")
    lines.append("By Category:")

    for category, count in stats.get("categories", {}).items():
        lines.append(f"  {category}: {count}")

    return "\n".join(lines)
```

```python
# File: tools/verdict_analyzer/scanner.py

"""Multi-repo verdict discovery and scanning."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterator

from tools.verdict_analyzer.database import VerdictDatabase
from tools.verdict_analyzer.parser import compute_content_hash, parse_verdict

logger = logging.getLogger(__name__)


def find_registry(start_path: Path) -> Path | None:
    """Find project-registry.json by searching up directory tree.

    Args:
        start_path: Directory to start searching from.

    Returns:
        Path to registry file, or None if not found.
    """
    current = start_path.resolve()

    while current != current.parent:
        registry = current / "project-registry.json"
        if registry.exists():
            return registry
        current = current.parent

    # Check root
    registry = current / "project-registry.json"
    if registry.exists():
        return registry

    return None


def load_registry(registry_path: Path) -> list[Path]:
    """Load repository paths from registry.

    Args:
        registry_path: Path to project-registry.json.

    Returns:
        List of existing repository paths.
    """
    with open(registry_path, encoding="utf-8") as f:
        data = json.load(f)

    repos = []
    for repo_str in data:
        repo_path = Path(repo_str)
        if repo_path.exists():
            repos.append(repo_path)
        else:
            logger.warning(f"Repository not found: {repo_path}")

    return repos


def validate_verdict_path(verdict_path: Path, base_dir: Path) -> bool:
    """Validate verdict path is within base directory.

    Args:
        verdict_path: Path to validate.
        base_dir: Base directory path must be within.

    Returns:
        True if path is valid, False otherwise.
    """
    try:
        verdict_path.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False


def discover_verdicts(repo_path: Path) -> Iterator[Path]:
    """Discover verdict files in a repository.

    Args:
        repo_path: Path to repository root.

    Yields:
        Paths to verdict markdown files.
    """
    # Look in common verdict locations
    verdict_dirs = [
        repo_path / "docs" / "verdicts",
        repo_path / "verdicts",
        repo_path / ".verdicts",
    ]

    seen_paths: set[Path] = set()

    for verdict_dir in verdict_dirs:
        if not verdict_dir.exists():
            continue

        try:
            # Use iterdir + recursion to handle symlink loops
            yield from _scan_directory(verdict_dir, seen_paths, repo_path)
        except OSError as e:
            logger.warning(f"Error scanning {verdict_dir}: {e}")


def _scan_directory(
    directory: Path, seen: set[Path], base_dir: Path
) -> Iterator[Path]:
    """Recursively scan directory for verdict files.

    Args:
        directory: Directory to scan.
        seen: Set of already-seen real paths (for loop detection).
        base_dir: Base directory for path validation.

    Yields:
        Paths to verdict markdown files.
    """
    try:
        real_path = directory.resolve()
    except OSError:
        return

    # Check for symlink loops
    if real_path in seen:
        logger.warning(f"Symlink loop detected at {directory}")
        return

    seen.add(real_path)

    try:
        for entry in directory.iterdir():
            if entry.is_file() and entry.suffix == ".md":
                if validate_verdict_path(entry, base_dir):
                    yield entry
            elif entry.is_dir():
                yield from _scan_directory(entry, seen, base_dir)
    except OSError as e:
        logger.warning(f"Error reading directory {directory}: {e}")


def scan_repos(
    registry_path: Path,
    db_path: Path,
    force: bool = False,
) -> int:
    """Scan repositories and update database.

    Args:
        registry_path: Path to project-registry.json.
        db_path: Path to SQLite database.
        force: If True, re-parse all verdicts regardless of hash.

    Returns:
        Number of verdicts processed.
    """
    repos = load_registry(registry_path)
    db = VerdictDatabase(db_path)

    count = 0

    try:
        for repo in repos:
            logger.info(f"Scanning repository: {repo}")

            for verdict_path in discover_verdicts(repo):
                try:
                    content = verdict_path.read_text(encoding="utf-8")
                    content_hash = compute_content_hash(content)

                    if not force and not db.needs_update(str(verdict_path), content_hash):
                        logger.debug(f"Skipping unchanged: {verdict_path}")
                        continue

                    logger.debug(f"Parsing: {verdict_path}")
                    record = parse_verdict(verdict_path)
                    db.upsert_verdict(record)
                    count += 1

                except Exception as e:
                    logger.error(f"Error parsing {verdict_path}: {e}")

    finally:
        db.close()

    return count
```