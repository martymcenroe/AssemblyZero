# File: tools/verdict_analyzer/database.py

```python
"""SQLite operations for verdict storage."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

from tools.verdict_analyzer import PARSER_VERSION
from tools.verdict_analyzer.parser import VerdictRecord, BlockingIssue

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS verdicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT UNIQUE NOT NULL,
    verdict_type TEXT NOT NULL,
    decision TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    repo_name TEXT,
    issue_number INTEGER,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS blocking_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verdict_id INTEGER NOT NULL,
    tier INTEGER NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    raw_text TEXT,
    FOREIGN KEY (verdict_id) REFERENCES verdicts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_verdicts_filepath ON verdicts(filepath);
CREATE INDEX IF NOT EXISTS idx_verdicts_content_hash ON verdicts(content_hash);
CREATE INDEX IF NOT EXISTS idx_blocking_issues_category ON blocking_issues(category);
CREATE INDEX IF NOT EXISTS idx_blocking_issues_tier ON blocking_issues(tier);
"""


class VerdictDatabase:
    """SQLite database for storing verdict records."""
    
    def __init__(self, db_path: Path | str):
        """Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._ensure_directory()
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._initialize_schema()
    
    def _ensure_directory(self) -> None:
        """Ensure the database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _initialize_schema(self) -> None:
        """Initialize database schema."""
        cursor = self.conn.cursor()
        cursor.executescript(CREATE_TABLES_SQL)
        
        # Check/set schema version
        cursor.execute("SELECT version FROM schema_version LIMIT 1")
        row = cursor.fetchone()
        if row is None:
            cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        
        self.conn.commit()
    
    def migrate(self) -> None:
        """Run any pending migrations."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT version FROM schema_version LIMIT 1")
        row = cursor.fetchone()
        current_version = row["version"] if row else 0
        
        if current_version < SCHEMA_VERSION:
            # Add any migration logic here
            cursor.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
            self.conn.commit()
            logger.info(f"Migrated database from version {current_version} to {SCHEMA_VERSION}")
    
    def needs_update(self, filepath: str, content_hash: str) -> bool:
        """Check if a verdict needs to be re-parsed.
        
        Args:
            filepath: Path to verdict file
            content_hash: Hash of current file content
            
        Returns:
            True if the verdict needs updating
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT content_hash, parser_version FROM verdicts WHERE filepath = ?",
            (filepath,)
        )
        row = cursor.fetchone()
        
        if row is None:
            return True
        
        # Re-parse if content changed or parser version updated
        if row["content_hash"] != content_hash:
            return True
        if row["parser_version"] != PARSER_VERSION:
            return True
        
        return False
    
    def upsert_verdict(self, record: VerdictRecord) -> int:
        """Insert or update a verdict record.
        
        Args:
            record: VerdictRecord to store
            
        Returns:
            ID of the verdict record
        """
        cursor = self.conn.cursor()
        
        # Check if exists
        cursor.execute("SELECT id FROM verdicts WHERE filepath = ?", (record.filepath,))
        existing = cursor.fetchone()
        
        if existing:
            verdict_id = existing["id"]
            cursor.execute("""
                UPDATE verdicts SET
                    verdict_type = ?,
                    decision = ?,
                    content_hash = ?,
                    parser_version = ?,
                    repo_name = ?,
                    issue_number = ?,
                    title = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                record.verdict_type,
                record.decision,
                record.content_hash,
                record.parser_version,
                record.repo_name,
                record.issue_number,
                record.title,
                verdict_id,
            ))
            
            # Delete old blocking issues
            cursor.execute("DELETE FROM blocking_issues WHERE verdict_id = ?", (verdict_id,))
        else:
            cursor.execute("""
                INSERT INTO verdicts (
                    filepath, verdict_type, decision, content_hash,
                    parser_version, repo_name, issue_number, title
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.filepath,
                record.verdict_type,
                record.decision,
                record.content_hash,
                record.parser_version,
                record.repo_name,
                record.issue_number,
                record.title,
            ))
            verdict_id = cursor.lastrowid
        
        # Insert blocking issues
        for issue in record.blocking_issues:
            cursor.execute("""
                INSERT INTO blocking_issues (verdict_id, tier, category, description, raw_text)
                VALUES (?, ?, ?, ?, ?)
            """, (verdict_id, issue.tier, issue.category, issue.description, issue.raw_text))
        
        self.conn.commit()
        return verdict_id
    
    def get_all_verdicts(self) -> list[VerdictRecord]:
        """Get all verdict records from the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM verdicts")
        
        records = []
        for row in cursor.fetchall():
            # Get blocking issues
            cursor.execute(
                "SELECT * FROM blocking_issues WHERE verdict_id = ?",
                (row["id"],)
            )
            issues = [
                BlockingIssue(
                    tier=issue_row["tier"],
                    category=issue_row["category"],
                    description=issue_row["description"],
                    raw_text=issue_row["raw_text"] or "",
                )
                for issue_row in cursor.fetchall()
            ]
            
            records.append(VerdictRecord(
                filepath=row["filepath"],
                verdict_type=row["verdict_type"],
                decision=row["decision"],
                content_hash=row["content_hash"],
                parser_version=row["parser_version"],
                repo_name=row["repo_name"] or "",
                issue_number=row["issue_number"],
                title=row["title"] or "",
                blocking_issues=issues,
            ))
        
        return records
    
    def get_pattern_stats(self) -> dict:
        """Get statistics on blocking issue patterns.
        
        Returns:
            Dictionary with category counts and tier breakdown
        """
        cursor = self.conn.cursor()
        
        # Category counts
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM blocking_issues
            GROUP BY category
            ORDER BY count DESC
        """)
        category_counts = {row["category"]: row["count"] for row in cursor.fetchall()}
        
        # Tier breakdown
        cursor.execute("""
            SELECT tier, COUNT(*) as count
            FROM blocking_issues
            GROUP BY tier
            ORDER BY tier
        """)
        tier_counts = {row["tier"]: row["count"] for row in cursor.fetchall()}
        
        # Decision breakdown
        cursor.execute("""
            SELECT decision, COUNT(*) as count
            FROM verdicts
            GROUP BY decision
        """)
        decision_counts = {row["decision"]: row["count"] for row in cursor.fetchall()}
        
        return {
            "categories": category_counts,
            "tiers": tier_counts,
            "decisions": decision_counts,
            "total_verdicts": sum(decision_counts.values()),
            "total_issues": sum(category_counts.values()),
        }
    
    def clear_all(self) -> None:
        """Clear all data from database."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM blocking_issues")
        cursor.execute("DELETE FROM verdicts")
        self.conn.commit()
    
    def close(self) -> None:
        """Close database connection."""
        self.conn.close()
```