# File: tools/verdict_analyzer/database.py

```python
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