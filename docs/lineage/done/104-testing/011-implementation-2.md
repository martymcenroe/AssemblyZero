# File: tools/verdict_analyzer/database.py

```python
"""SQLite operations for verdict storage."""

import sqlite3
import logging
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from .parser import VerdictRecord, BlockingIssue, PARSER_VERSION

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS verdicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    content_hash TEXT NOT NULL,
    verdict_type TEXT NOT NULL,
    title TEXT,
    verdict TEXT,
    parser_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS blocking_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verdict_id INTEGER NOT NULL,
    tier INTEGER NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    FOREIGN KEY (verdict_id) REFERENCES verdicts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verdict_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    FOREIGN KEY (verdict_id) REFERENCES verdicts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_verdicts_file_path ON verdicts(file_path);
CREATE INDEX IF NOT EXISTS idx_verdicts_content_hash ON verdicts(content_hash);
CREATE INDEX IF NOT EXISTS idx_blocking_issues_verdict_id ON blocking_issues(verdict_id);
CREATE INDEX IF NOT EXISTS idx_blocking_issues_category ON blocking_issues(category);
"""


class VerdictDatabase:
    """SQLite database for verdict storage and retrieval."""

    def __init__(self, db_path: Path):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_directory()
        self._init_db()

    def _ensure_directory(self) -> None:
        """Ensure the database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory exists: {self.db_path.parent}")

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._connection() as conn:
            conn.executescript(CREATE_TABLES_SQL)

            # Check and set schema version
            cursor = conn.execute("SELECT version FROM schema_version LIMIT 1")
            row = cursor.fetchone()
            if row is None:
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            elif row[0] < SCHEMA_VERSION:
                self._migrate(conn, row[0])

    def _migrate(self, conn: sqlite3.Connection, from_version: int) -> None:
        """Run migrations from old version to current.

        Args:
            conn: Database connection
            from_version: Current schema version in database
        """
        logger.info(f"Migrating database from version {from_version} to {SCHEMA_VERSION}")

        # Add migration logic here as schema evolves
        # Example:
        # if from_version < 2:
        #     conn.execute("ALTER TABLE verdicts ADD COLUMN new_column TEXT")

        conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))

    @contextmanager
    def _connection(self):
        """Context manager for database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def needs_update(
        self, file_path: str, content_hash: str, parser_version: str = PARSER_VERSION
    ) -> bool:
        """Check if a verdict file needs to be re-parsed.

        Args:
            file_path: Path to verdict file
            content_hash: Current content hash
            parser_version: Current parser version

        Returns:
            True if file needs update, False otherwise
        """
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT content_hash, parser_version FROM verdicts
                WHERE file_path = ?
                """,
                (file_path,),
            )
            row = cursor.fetchone()

            if row is None:
                return True

            # Update needed if hash changed or parser version is newer
            if row["content_hash"] != content_hash:
                return True
            if row["parser_version"] != parser_version:
                return True

            return False

    def upsert_verdict(self, record: VerdictRecord) -> int:
        """Insert or update a verdict record.

        Args:
            record: VerdictRecord to store

        Returns:
            Database ID of the verdict
        """
        with self._connection() as conn:
            # Check if exists
            cursor = conn.execute(
                "SELECT id FROM verdicts WHERE file_path = ?",
                (record.file_path,),
            )
            existing = cursor.fetchone()

            if existing:
                verdict_id = existing["id"]
                conn.execute(
                    """
                    UPDATE verdicts SET
                        content_hash = ?,
                        verdict_type = ?,
                        title = ?,
                        verdict = ?,
                        parser_version = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        record.content_hash,
                        record.verdict_type,
                        record.title,
                        record.verdict,
                        record.parser_version,
                        verdict_id,
                    ),
                )
                # Clear old related data
                conn.execute("DELETE FROM blocking_issues WHERE verdict_id = ?", (verdict_id,))
                conn.execute("DELETE FROM recommendations WHERE verdict_id = ?", (verdict_id,))
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO verdicts (file_path, content_hash, verdict_type, title, verdict, parser_version)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.file_path,
                        record.content_hash,
                        record.verdict_type,
                        record.title,
                        record.verdict,
                        record.parser_version,
                    ),
                )
                verdict_id = cursor.lastrowid

            # Insert blocking issues
            for issue in record.blocking_issues:
                conn.execute(
                    """
                    INSERT INTO blocking_issues (verdict_id, tier, category, description)
                    VALUES (?, ?, ?, ?)
                    """,
                    (verdict_id, issue.tier, issue.category, issue.description),
                )

            # Insert recommendations
            for rec in record.recommendations:
                conn.execute(
                    """
                    INSERT INTO recommendations (verdict_id, content)
                    VALUES (?, ?)
                    """,
                    (verdict_id, rec),
                )

            return verdict_id

    def get_verdict(self, file_path: str) -> Optional[VerdictRecord]:
        """Get a verdict by file path.

        Args:
            file_path: Path to verdict file

        Returns:
            VerdictRecord if found, None otherwise
        """
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, file_path, content_hash, verdict_type, title, verdict, parser_version
                FROM verdicts WHERE file_path = ?
                """,
                (file_path,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            verdict_id = row["id"]

            # Get blocking issues
            cursor = conn.execute(
                "SELECT tier, category, description FROM blocking_issues WHERE verdict_id = ?",
                (verdict_id,),
            )
            blocking_issues = [
                BlockingIssue(tier=r["tier"], category=r["category"], description=r["description"])
                for r in cursor.fetchall()
            ]

            # Get recommendations
            cursor = conn.execute(
                "SELECT content FROM recommendations WHERE verdict_id = ?",
                (verdict_id,),
            )
            recommendations = [r["content"] for r in cursor.fetchall()]

            return VerdictRecord(
                file_path=row["file_path"],
                content_hash=row["content_hash"],
                verdict_type=row["verdict_type"],
                title=row["title"],
                verdict=row["verdict"],
                blocking_issues=blocking_issues,
                recommendations=recommendations,
                parser_version=row["parser_version"],
            )

    def get_all_verdicts(self) -> list[VerdictRecord]:
        """Get all verdicts from the database.

        Returns:
            List of all VerdictRecords
        """
        with self._connection() as conn:
            cursor = conn.execute("SELECT file_path FROM verdicts")
            file_paths = [row["file_path"] for row in cursor.fetchall()]

        return [self.get_verdict(fp) for fp in file_paths if self.get_verdict(fp) is not None]

    def get_pattern_stats(self) -> dict:
        """Get statistics on blocking issue patterns.

        Returns:
            Dictionary with pattern statistics
        """
        with self._connection() as conn:
            # Count by category
            cursor = conn.execute(
                """
                SELECT category, COUNT(*) as count
                FROM blocking_issues
                GROUP BY category
                ORDER BY count DESC
                """
            )
            by_category = {row["category"]: row["count"] for row in cursor.fetchall()}

            # Count by tier
            cursor = conn.execute(
                """
                SELECT tier, COUNT(*) as count
                FROM blocking_issues
                GROUP BY tier
                ORDER BY tier
                """
            )
            by_tier = {row["tier"]: row["count"] for row in cursor.fetchall()}

            # Total verdicts
            cursor = conn.execute("SELECT COUNT(*) as count FROM verdicts")
            total_verdicts = cursor.fetchone()["count"]

            # Verdicts with issues
            cursor = conn.execute(
                """
                SELECT COUNT(DISTINCT verdict_id) as count FROM blocking_issues
                """
            )
            verdicts_with_issues = cursor.fetchone()["count"]

            return {
                "total_verdicts": total_verdicts,
                "verdicts_with_issues": verdicts_with_issues,
                "by_category": by_category,
                "by_tier": by_tier,
            }

    def format_stats(self) -> str:
        """Format statistics for display.

        Returns:
            Formatted statistics string
        """
        stats = self.get_pattern_stats()

        lines = [
            "Verdict Analyzer Statistics",
            "=" * 40,
            f"Total verdicts analyzed: {stats['total_verdicts']}",
            f"Verdicts with blocking issues: {stats['verdicts_with_issues']}",
            "",
            "Issues by Tier:",
        ]

        for tier in sorted(stats["by_tier"].keys()):
            lines.append(f"  Tier {tier}: {stats['by_tier'][tier]}")

        lines.extend(["", "Issues by Category:"])

        for category, count in sorted(stats["by_category"].items(), key=lambda x: -x[1]):
            lines.append(f"  {category}: {count}")

        return "\n".join(lines)
```