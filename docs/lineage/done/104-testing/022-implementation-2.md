# File: tools/verdict_analyzer/database.py

```python
"""Database module for verdict analyzer.

Handles SQLite storage of parsed verdicts and pattern statistics.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from .parser import VerdictRecord, BlockingIssue, PARSER_VERSION

SCHEMA_VERSION = 1

logger = logging.getLogger(__name__)


class VerdictDatabase:
    """SQLite database for storing verdict data."""
    
    def __init__(self, db_path: Path):
        """Initialize database connection.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        
        # Create parent directories if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        
        self._init_schema()
        self._migrate_if_needed()
    
    def _init_schema(self):
        """Initialize database schema."""
        cursor = self.conn.cursor()
        
        # Schema version table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
        """)
        
        # Check if schema_version has a row
        row = cursor.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            cursor.execute("INSERT INTO schema_version VALUES (?)", (SCHEMA_VERSION,))
        
        # Verdicts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verdicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                content_hash TEXT NOT NULL,
                verdict_type TEXT NOT NULL,
                title TEXT,
                verdict TEXT,
                parser_version TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Blocking issues table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blocking_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                verdict_id INTEGER NOT NULL,
                tier INTEGER NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                FOREIGN KEY (verdict_id) REFERENCES verdicts(id) ON DELETE CASCADE
            )
        """)
        
        self.conn.commit()
    
    def _migrate_if_needed(self):
        """Run migrations if schema version is outdated."""
        cursor = self.conn.cursor()
        row = cursor.execute("SELECT version FROM schema_version").fetchone()
        current_version = row[0] if row else 0
        
        if current_version < SCHEMA_VERSION:
            logger.info(f"Migrating database from version {current_version} to {SCHEMA_VERSION}")
            
            # Migration logic here
            # For now, just update the version
            cursor.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
            self.conn.commit()
    
    def needs_update(self, file_path: str, content_hash: str, parser_version: Optional[str] = None) -> bool:
        """Check if a verdict needs to be re-parsed.
        
        Args:
            file_path: Path to the verdict file
            content_hash: Hash of current file content
            parser_version: Current parser version to check against stored version
            
        Returns:
            True if the verdict needs to be updated
        """
        cursor = self.conn.cursor()
        row = cursor.execute(
            "SELECT content_hash, parser_version FROM verdicts WHERE file_path = ?",
            (file_path,)
        ).fetchone()
        
        if row is None:
            return True
        
        # Check content hash
        if row[0] != content_hash:
            return True
        
        # Check parser version if provided
        if parser_version is not None:
            stored_version = row[1] if row[1] else "0.0.0"
            if stored_version != parser_version:
                return True
        
        return False
    
    def upsert_verdict(self, record: VerdictRecord):
        """Insert or update a verdict record.
        
        Args:
            record: The verdict record to store
        """
        cursor = self.conn.cursor()
        
        # Check if exists
        existing = cursor.execute(
            "SELECT id FROM verdicts WHERE file_path = ?",
            (record.file_path,)
        ).fetchone()
        
        if existing:
            verdict_id = existing[0]
            cursor.execute("""
                UPDATE verdicts SET
                    content_hash = ?,
                    verdict_type = ?,
                    title = ?,
                    verdict = ?,
                    parser_version = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (record.content_hash, record.verdict_type, record.title,
                  record.verdict, record.parser_version, verdict_id))
            
            # Delete old blocking issues
            cursor.execute("DELETE FROM blocking_issues WHERE verdict_id = ?", (verdict_id,))
        else:
            cursor.execute("""
                INSERT INTO verdicts (file_path, content_hash, verdict_type, title, verdict, parser_version)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (record.file_path, record.content_hash, record.verdict_type,
                  record.title, record.verdict, record.parser_version))
            verdict_id = cursor.lastrowid
        
        # Insert blocking issues
        for issue in record.blocking_issues:
            cursor.execute("""
                INSERT INTO blocking_issues (verdict_id, tier, category, description)
                VALUES (?, ?, ?, ?)
            """, (verdict_id, issue.tier, issue.category, issue.description))
        
        self.conn.commit()
    
    def get_pattern_stats(self) -> Dict[str, Any]:
        """Get statistics about patterns in the database.
        
        Returns:
            Dictionary with pattern statistics
        """
        cursor = self.conn.cursor()
        
        # Total verdicts
        total = cursor.execute("SELECT COUNT(*) FROM verdicts").fetchone()[0]
        
        # Verdicts with issues
        with_issues = cursor.execute("""
            SELECT COUNT(DISTINCT verdict_id) FROM blocking_issues
        """).fetchone()[0]
        
        # Issues by category
        by_category = {}
        for row in cursor.execute("""
            SELECT category, COUNT(*) as count FROM blocking_issues
            GROUP BY category ORDER BY count DESC
        """):
            by_category[row[0]] = row[1]
        
        # Issues by tier
        by_tier = {}
        for row in cursor.execute("""
            SELECT tier, COUNT(*) as count FROM blocking_issues
            GROUP BY tier ORDER BY tier
        """):
            by_tier[row[0]] = row[1]
        
        return {
            "total_verdicts": total,
            "verdicts_with_issues": with_issues,
            "by_category": by_category,
            "by_tier": by_tier,
        }
    
    def format_stats(self) -> str:
        """Format statistics as a readable string.
        
        Returns:
            Formatted statistics string
        """
        stats = self.get_pattern_stats()
        
        lines = [
            "=" * 50,
            "Verdict Analyzer Statistics",
            "=" * 50,
            f"Total verdicts: {stats['total_verdicts']}",
            f"Verdicts with blocking issues: {stats['verdicts_with_issues']}",
            "",
            "Issues by Category:",
        ]
        
        for category, count in stats['by_category'].items():
            lines.append(f"  {category}: {count}")
        
        lines.append("")
        lines.append("Issues by Tier:")
        for tier, count in stats['by_tier'].items():
            lines.append(f"  Tier {tier}: {count}")
        
        return "\n".join(lines)
    
    def close(self):
        """Close database connection."""
        self.conn.close()
```