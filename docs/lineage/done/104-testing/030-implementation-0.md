# File: tools/verdict_analyzer/database.py

```python
"""SQLite database operations for verdict analyzer."""

import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from .parser import VerdictRecord, BlockingIssue, PARSER_VERSION

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


class VerdictDatabase:
    """SQLite database for storing and querying verdict records."""

    def __init__(self, db_path: Path):
        """Initialize database connection.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_directory()
        self._initialize_schema()

    def _ensure_directory(self) -> None:
        """Create database directory if it doesn't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize_schema(self) -> None:
        """Initialize or migrate database schema."""
        with self._get_connection() as conn:
            # Check if schema_version table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            )
            has_schema_table = cursor.fetchone() is not None

            if has_schema_table:
                cursor = conn.execute("SELECT version FROM schema_version")
                row = cursor.fetchone()
                current_version = row[0] if row else 0
            else:
                current_version = 0

            if current_version < SCHEMA_VERSION:
                self._migrate_schema(conn, current_version)

    def _migrate_schema(self, conn: sqlite3.Connection, from_version: int) -> None:
        """Apply schema migrations.
        
        Args:
            conn: Database connection.
            from_version: Current schema version.
        """
        logger.info(f"Migrating database from version {from_version} to {SCHEMA_VERSION}")

        # Drop and recreate for simplicity in v1
        conn.execute("DROP TABLE IF EXISTS verdicts")
        conn.execute("DROP TABLE IF EXISTS blocking_issues")
        conn.execute("DROP TABLE IF EXISTS schema_version")

        # Create tables
        conn.execute("""
            CREATE TABLE schema_version (
                version INTEGER PRIMARY KEY
            )
        """)
        conn.execute(f"INSERT INTO schema_version VALUES ({SCHEMA_VERSION})")

        conn.execute("""
            CREATE TABLE verdicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                content_hash TEXT NOT NULL,
                verdict_type TEXT NOT NULL,
                title TEXT,
                verdict TEXT,
                parser_version TEXT,
                recommendations TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE blocking_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                verdict_id INTEGER NOT NULL,
                tier INTEGER NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                normalized_pattern TEXT,
                FOREIGN KEY (verdict_id) REFERENCES verdicts(id) ON DELETE CASCADE
            )
        """)

        conn.execute("CREATE INDEX idx_verdicts_file_path ON verdicts(file_path)")
        conn.execute("CREATE INDEX idx_blocking_issues_category ON blocking_issues(category)")
        conn.execute("CREATE INDEX idx_blocking_issues_tier ON blocking_issues(tier)")

    def upsert_verdict(self, record: VerdictRecord) -> int:
        """Insert or update a verdict record.
        
        Args:
            record: The verdict record to store.
            
        Returns:
            The database ID of the verdict.
        """
        with self._get_connection() as conn:
            # Check if exists
            cursor = conn.execute(
                "SELECT id FROM verdicts WHERE file_path = ?",
                (record.file_path,)
            )
            existing = cursor.fetchone()

            recommendations_json = json.dumps(record.recommendations) if record.recommendations else "[]"

            if existing:
                verdict_id = existing[0]
                conn.execute("""
                    UPDATE verdicts SET
                        content_hash = ?,
                        verdict_type = ?,
                        title = ?,
                        verdict = ?,
                        parser_version = ?,
                        recommendations = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    record.content_hash,
                    record.verdict_type,
                    record.title,
                    record.verdict,
                    record.parser_version,
                    recommendations_json,
                    verdict_id,
                ))
                # Delete old blocking issues
                conn.execute("DELETE FROM blocking_issues WHERE verdict_id = ?", (verdict_id,))
            else:
                cursor = conn.execute("""
                    INSERT INTO verdicts (file_path, content_hash, verdict_type, title, verdict, parser_version, recommendations)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.file_path,
                    record.content_hash,
                    record.verdict_type,
                    record.title,
                    record.verdict,
                    record.parser_version,
                    recommendations_json,
                ))
                verdict_id = cursor.lastrowid

            # Insert blocking issues
            for issue in record.blocking_issues:
                from .patterns import normalize_pattern
                normalized = normalize_pattern(issue.description)
                conn.execute("""
                    INSERT INTO blocking_issues (verdict_id, tier, category, description, normalized_pattern)
                    VALUES (?, ?, ?, ?, ?)
                """, (verdict_id, issue.tier, issue.category, issue.description, normalized))

            return verdict_id

    def needs_update(self, file_path: str, content_hash: str, parser_version: str = None) -> bool:
        """Check if a verdict needs to be updated.
        
        Args:
            file_path: Path to the verdict file.
            content_hash: Hash of the current content.
            parser_version: Current parser version (defaults to PARSER_VERSION).
            
        Returns:
            True if the verdict needs to be re-parsed.
        """
        if parser_version is None:
            parser_version = PARSER_VERSION

        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT content_hash, parser_version FROM verdicts WHERE file_path = ?",
                (file_path,)
            )
            row = cursor.fetchone()

            if row is None:
                return True  # New file

            stored_hash = row[0]
            stored_version = row[1]

            # Need update if content changed or parser version is newer
            if stored_hash != content_hash:
                return True
            if stored_version != parser_version:
                return True

            return False

    def get_pattern_stats(self) -> dict:
        """Get statistics about patterns in the database.
        
        Returns:
            Dictionary with pattern statistics.
        """
        with self._get_connection() as conn:
            # Total verdicts
            cursor = conn.execute("SELECT COUNT(*) FROM verdicts")
            total_verdicts = cursor.fetchone()[0]

            # Verdicts with issues
            cursor = conn.execute("""
                SELECT COUNT(DISTINCT verdict_id) FROM blocking_issues
            """)
            verdicts_with_issues = cursor.fetchone()[0]

            # By category
            cursor = conn.execute("""
                SELECT category, COUNT(*) as count
                FROM blocking_issues
                GROUP BY category
                ORDER BY count DESC
            """)
            by_category = {row[0]: row[1] for row in cursor.fetchall()}

            # By tier
            cursor = conn.execute("""
                SELECT tier, COUNT(*) as count
                FROM blocking_issues
                GROUP BY tier
                ORDER BY tier
            """)
            by_tier = {row[0]: row[1] for row in cursor.fetchall()}

            return {
                "total_verdicts": total_verdicts,
                "verdicts_with_issues": verdicts_with_issues,
                "by_category": by_category,
                "by_tier": by_tier,
            }

    def format_stats(self) -> str:
        """Format statistics as readable output.
        
        Returns:
            Formatted statistics string.
        """
        stats = self.get_pattern_stats()

        lines = [
            "=" * 50,
            "Verdict Analyzer Statistics",
            "=" * 50,
            f"Total verdicts: {stats['total_verdicts']}",
            f"Verdicts with issues: {stats['verdicts_with_issues']}",
            "",
            "Issues by Category:",
        ]

        for category, count in stats["by_category"].items():
            lines.append(f"  {category}: {count}")

        lines.append("")
        lines.append("Issues by Tier:")
        for tier, count in stats["by_tier"].items():
            lines.append(f"  Tier {tier}: {count}")

        lines.append("=" * 50)

        return "\n".join(lines)

    def close(self) -> None:
        """Close database connection (no-op with context manager pattern)."""
        pass  # Connections are closed per-operation

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
```