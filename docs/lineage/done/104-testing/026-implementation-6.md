# File: tools/verdict-analyzer.py

```python
#!/usr/bin/env python3
"""Verdict Analyzer CLI - Analyze Gemini governance verdicts.

Usage:
    python verdict-analyzer.py scan [--registry PATH] [--force]
    python verdict-analyzer.py stats
    python verdict-analyzer.py recommend [--template PATH] [--apply]
"""

import argparse
import logging
import sys
from pathlib import Path

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from verdict_analyzer import (
    VerdictDatabase,
    discover_repos,
    scan_for_verdicts,
    parse_verdict,
)
from verdict_analyzer.scanner import find_registry_path


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
        format="%(levelname)s: %(message)s"
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze Gemini governance verdicts"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v for INFO, -vv for DEBUG)"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan for verdicts")
    scan_parser.add_argument(
        "--registry",
        type=Path,
        help="Path to project-registry.json"
    )
    scan_parser.add_argument(
        "--force",
        action="store_true",
        help="Re-parse all verdicts regardless of cache"
    )
    
    # Stats command
    subparsers.add_parser("stats", help="Show verdict statistics")
    
    # Recommend command
    rec_parser = subparsers.add_parser("recommend", help="Generate recommendations")
    rec_parser.add_argument(
        "--template",
        type=Path,
        help="Path to template file"
    )
    rec_parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply recommendations (default is dry-run)"
    )
    
    args = parser.parse_args()
    configure_logging(args.verbose)
    
    if args.command is None:
        parser.print_help()
        return 1
    
    # Initialize database
    db_path = Path.cwd() / ".agentos" / "verdicts.db"
    db = VerdictDatabase(db_path)
    
    if args.command == "scan":
        # Find registry
        registry_path = args.registry or find_registry_path()
        if registry_path is None:
            logging.error("Could not find project-registry.json")
            return 1
        
        # Discover and scan repos
        repos = discover_repos(registry_path)
        for repo in repos:
            logging.info(f"Scanning {repo}")
            for verdict_path in scan_for_verdicts(repo):
                record = parse_verdict(verdict_path)
                db.upsert_verdict(record)
                logging.info(f"  Processed: {verdict_path.name}")
    
    elif args.command == "stats":
        print(db.format_stats())
    
    elif args.command == "recommend":
        from verdict_analyzer.template_updater import (
            generate_recommendations,
            apply_recommendations_preview,
        )
        
        stats = db.get_pattern_stats()
        recommendations = generate_recommendations(stats)
        
        if args.template:
            preview = apply_recommendations_preview(args.template, recommendations)
            print(preview)
        else:
            print("Recommendations based on verdict patterns:")
            for rec in recommendations:
                print(f"  - [{rec.section}] {rec.content}")
    
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```