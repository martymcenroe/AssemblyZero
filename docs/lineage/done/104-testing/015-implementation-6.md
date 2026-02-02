# File: tools/verdict-analyzer.py

```python
#!/usr/bin/env python3
"""Verdict Analyzer CLI - Analyze Gemini governance verdicts and improve templates.

Usage:
    python tools/verdict-analyzer.py scan [--force] [--registry PATH]
    python tools/verdict-analyzer.py stats
    python tools/verdict-analyzer.py recommend [--template PATH] [--apply]
"""

import argparse
import logging
import sys
from pathlib import Path

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from verdict_analyzer import (
    VerdictDatabase,
    parse_verdict,
    PARSER_VERSION,
    find_registry_path,
    discover_repos,
    scan_for_verdicts,
    validate_verdict_path,
    generate_recommendations,
    apply_recommendations_preview,
    atomic_write_with_backup,
    validate_template_path,
)
from verdict_analyzer.parser import compute_content_hash

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(".agentos/verdicts.db")


def configure_logging(verbosity: int) -> None:
    """Configure logging based on verbosity level.

    Args:
        verbosity: 0 = WARNING, 1 = INFO, 2+ = DEBUG
    """
    if verbosity >= 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s" if verbosity < 2 else "%(levelname)s: %(name)s: %(message)s",
    )


def cmd_scan(args: argparse.Namespace) -> int:
    """Scan for and parse verdict files."""
    db = VerdictDatabase(args.db_path)

    # Find registry
    if args.registry:
        registry_path = Path(args.registry)
    else:
        registry_path = find_registry_path()

    if registry_path is None:
        logger.error("No project registry found. Use --registry to specify path.")
        return 1

    logger.info(f"Using registry: {registry_path}")

    # Discover repos
    repos = discover_repos(registry_path)
    if not repos:
        logger.warning("No repositories found in registry")
        return 0

    logger.info(f"Found {len(repos)} repositories")

    # Scan each repo
    parsed = 0
    skipped = 0
    errors = 0

    for repo in repos:
        logger.info(f"Scanning: {repo}")

        for verdict_path in scan_for_verdicts(repo):
            if not validate_verdict_path(verdict_path, repo):
                errors += 1
                continue

            try:
                content = verdict_path.read_text(encoding="utf-8")
                content_hash = compute_content_hash(content)

                if not args.force and not db.needs_update(str(verdict_path), content_hash):
                    skipped += 1
                    continue

                record = parse_verdict(verdict_path, content)
                db.upsert_verdict(record)
                parsed += 1
                logger.debug(f"Parsed: {verdict_path}")

            except Exception as e:
                logger.error(f"Error parsing {verdict_path}: {e}")
                errors += 1

    print(f"\nScan complete: {parsed} parsed, {skipped} skipped, {errors} errors")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Show verdict statistics."""
    db = VerdictDatabase(args.db_path)
    print(db.format_stats())
    return 0


def cmd_recommend(args: argparse.Namespace) -> int:
    """Generate template recommendations."""
    db = VerdictDatabase(args.db_path)

    stats = db.get_pattern_stats()
    recommendations = generate_recommendations(stats, threshold=args.threshold)

    if not recommendations:
        print("No recommendations at this time.")
        return 0

    print(f"\nGenerated {len(recommendations)} recommendations:\n")
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. [{rec.section}] {rec.content}")

    if args.template:
        template_path = Path(args.template)

        if not validate_template_path(template_path):
            logger.error("Invalid template path")
            return 1

        if not template_path.exists():
            logger.error(f"Template not found: {template_path}")
            return 1

        if args.apply:
            preview = apply_recommendations_preview(template_path, recommendations)
            success, backup = atomic_write_with_backup(template_path, preview)
            if success:
                print(f"\nUpdated template: {template_path}")
                if backup:
                    print(f"Backup saved: {backup}")
            else:
                return 1
        else:
            print("\n--- Preview (use --apply to write) ---\n")
            preview = apply_recommendations_preview(template_path, recommendations)
            print(preview)

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze Gemini governance verdicts and improve templates"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Database path (default: {DEFAULT_DB_PATH})",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # scan command
    scan_parser = subparsers.add_parser("scan", help="Scan for verdict files")
    scan_parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-parse all files (ignore hash check)",
    )
    scan_parser.add_argument(
        "--registry",
        type=str,
        help="Path to project-registry.json",
    )

    # stats command
    subparsers.add_parser("stats", help="Show statistics")

    # recommend command
    rec_parser = subparsers.add_parser("recommend", help="Generate recommendations")
    rec_parser.add_argument(
        "--template",
        type=str,
        help="Template file to update",
    )
    rec_parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply recommendations (default is dry-run/preview)",
    )
    rec_parser.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="Minimum count to generate recommendation (default: 3)",
    )

    args = parser.parse_args()
    configure_logging(args.verbose)

    if args.command == "scan":
        return cmd_scan(args)
    elif args.command == "stats":
        return cmd_stats(args)
    elif args.command == "recommend":
        return cmd_recommend(args)

    return 1


if __name__ == "__main__":
    sys.exit(main())
```