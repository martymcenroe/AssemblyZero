# File: tools/verdict-analyzer.py

```python
#!/usr/bin/env python3
"""Verdict Analyzer - CLI for analyzing Gemini governance verdicts."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.verdict_analyzer import (
    PARSER_VERSION,
    VerdictDatabase,
    parse_verdict,
    find_registry,
    scan_repos,
    parse_template_sections,
    generate_recommendations,
    atomic_write_template,
    validate_template_path,
)
from tools.verdict_analyzer.parser import compute_content_hash
from tools.verdict_analyzer.template_updater import format_stats

logger = logging.getLogger(__name__)


def configure_logging(verbosity: int) -> None:
    """Configure logging based on -v/-vv flags.
    
    Args:
        verbosity: 0 = WARNING, 1 = INFO, 2+ = DEBUG
    """
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


def cmd_scan(args: argparse.Namespace) -> int:
    """Scan repositories and populate database."""
    db_path = Path(args.db)
    db = VerdictDatabase(db_path)
    
    try:
        registry_path = None
        if args.registry:
            registry_path = Path(args.registry)
        elif not args.repos:
            registry_path = find_registry()
        
        repos = [Path(r) for r in args.repos] if args.repos else None
        
        count = 0
        for repo_path, verdict_path in scan_repos(registry_path, repos):
            try:
                content = verdict_path.read_text(encoding="utf-8")
                content_hash = compute_content_hash(content)
                
                if args.force or db.needs_update(str(verdict_path), content_hash):
                    logger.info(f"Parsing: {verdict_path}")
                    record = parse_verdict(verdict_path, content)
                    db.upsert_verdict(record)
                    count += 1
                else:
                    logger.debug(f"Skipping (unchanged): {verdict_path}")
            except Exception as e:
                logger.error(f"Error parsing {verdict_path}: {e}")
        
        print(f"Processed {count} verdict(s)")
        return 0
    finally:
        db.close()


def cmd_stats(args: argparse.Namespace) -> int:
    """Show verdict statistics."""
    db_path = Path(args.db)
    db = VerdictDatabase(db_path)
    
    try:
        stats = db.get_pattern_stats()
        print(format_stats(stats))
        return 0
    finally:
        db.close()


def cmd_recommend(args: argparse.Namespace) -> int:
    """Generate template recommendations."""
    db_path = Path(args.db)
    db = VerdictDatabase(db_path)
    
    try:
        template_path = Path(args.template)
        
        if not template_path.exists():
            logger.error(f"Template not found: {template_path}")
            return 1
        
        content = template_path.read_text(encoding="utf-8")
        sections = parse_template_sections(content)
        stats = db.get_pattern_stats()
        
        recommendations = generate_recommendations(
            stats,
            sections,
            min_pattern_count=args.min_count,
        )
        
        if not recommendations:
            print("No recommendations at this time.")
            return 0
        
        print(f"Found {len(recommendations)} recommendation(s):\n")
        
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. [{rec.rec_type}] {rec.section}")
            print(f"   Reason: {rec.reason}")
            print(f"   Content: {rec.content}")
            print()
        
        if args.apply and not args.dry_run:
            # Apply recommendations
            validate_template_path(template_path)
            
            for rec in recommendations:
                if rec.rec_type == "add_section":
                    content += f"\n\n{rec.content}"
            
            atomic_write_template(template_path, content)
            print(f"Applied changes to: {template_path}")
        elif args.apply:
            print("(dry-run mode - no changes made)")
        
        return 0
    finally:
        db.close()


def cmd_clear(args: argparse.Namespace) -> int:
    """Clear database."""
    db_path = Path(args.db)
    db = VerdictDatabase(db_path)
    
    try:
        db.clear_all()
        print("Database cleared.")
        return 0
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze Gemini governance verdicts and improve templates",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
    )
    parser.add_argument(
        "--db",
        default=".agentos/verdicts.db",
        help="Path to SQLite database (default: .agentos/verdicts.db)",
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # scan command
    scan_parser = subparsers.add_parser("scan", help="Scan repositories for verdicts")
    scan_parser.add_argument(
        "--registry",
        help="Path to project-registry.json",
    )
    scan_parser.add_argument(
        "--repos",
        nargs="*",
        help="Explicit repository paths to scan",
    )
    scan_parser.add_argument(
        "--force",
        action="store_true",
        help="Re-parse all verdicts (ignore hash check)",
    )
    scan_parser.set_defaults(func=cmd_scan)
    
    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show verdict statistics")
    stats_parser.set_defaults(func=cmd_stats)
    
    # recommend command
    rec_parser = subparsers.add_parser("recommend", help="Generate template recommendations")
    rec_parser.add_argument(
        "template",
        help="Path to template file",
    )
    rec_parser.add_argument(
        "--min-count",
        type=int,
        default=3,
        help="Minimum pattern occurrences for recommendation",
    )
    rec_parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply recommendations to template",
    )
    rec_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview changes without modifying files (default)",
    )
    rec_parser.add_argument(
        "--no-dry-run",
        action="store_false",
        dest="dry_run",
        help="Actually modify files",
    )
    rec_parser.set_defaults(func=cmd_recommend)
    
    # clear command
    clear_parser = subparsers.add_parser("clear", help="Clear database")
    clear_parser.set_defaults(func=cmd_clear)
    
    args = parser.parse_args(argv)
    configure_logging(args.verbose)
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```