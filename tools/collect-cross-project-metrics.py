#!/usr/bin/env python3
"""Collect cross-project metrics for AssemblyZero usage tracking.

Issue #333: CLI entry point for cross-project metrics aggregation.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Project root on sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from assemblyzero.metrics.aggregator import aggregate_metrics
from assemblyzero.metrics.cache import (
    load_cached_metrics,
    save_cached_metrics,
)
from assemblyzero.metrics.collector import CollectionError, collect_repo_metrics
from assemblyzero.metrics.config import ConfigError, load_config
from assemblyzero.metrics.formatters import (
    format_json_snapshot,
    format_markdown_table,
    write_snapshot,
)
from assemblyzero.metrics.models import RepoMetrics

logger = logging.getLogger("metrics")


def _setup_logging(verbose: bool) -> None:
    """Configure logging to stderr with [metrics] prefix."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[metrics] %(message)s"))
    level = logging.DEBUG if verbose else logging.INFO
    root_logger = logging.getLogger("metrics")
    root_logger.setLevel(level)
    root_logger.addHandler(handler)
    # Also configure the assemblyzero.metrics loggers
    lib_logger = logging.getLogger("assemblyzero.metrics")
    lib_logger.setLevel(level)
    lib_logger.addHandler(handler)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Collect cross-project AssemblyZero usage metrics.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Config file path (default: ~/.assemblyzero/tracked_repos.json)",
    )
    parser.add_argument(
        "--period-days",
        type=int,
        default=30,
        help="Lookback period in days (default: 30)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/metrics"),
        help="Output directory (default: docs/metrics/)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown", "both"],
        default="both",
        dest="output_format",
        help="Output format (default: both)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass cache, fetch fresh data",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Returns 0 on success, 1 on partial failure, 2 on complete failure.
    """
    args = _parse_args(argv)
    _setup_logging(args.verbose)

    # Load config
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        logger.error("Configuration error: %s", exc)
        return 2

    # Resolve GitHub token
    token_env = config["github_token_env"]
    github_token = os.environ.get(token_env, "")
    if not github_token:
        logger.warning(
            "No token found in env var '%s'. Only public repos will be accessible.",
            token_env,
        )

    # Collect per-repo metrics
    collected: list[RepoMetrics] = []
    failed_repos: list[str] = []

    for repo_name in config["repos"]:
        # Check cache unless --no-cache
        if not args.no_cache:
            cached = load_cached_metrics(repo_name)
            if cached is not None:
                logger.info("Cache hit for %s", repo_name)
                collected.append(cached)
                continue

        logger.info("Collecting metrics for %s...", repo_name)
        try:
            metrics = collect_repo_metrics(
                repo_name,
                github_token,
                period_days=args.period_days,
            )
            collected.append(metrics)
            # Save to cache
            if not args.no_cache:
                save_cached_metrics(
                    repo_name, metrics, config["cache_ttl_minutes"]
                )
        except CollectionError as exc:
            logger.warning("Failed to collect %s: %s", repo_name, exc)
            failed_repos.append(repo_name)

    # Check for complete failure
    if not collected:
        logger.error(
            "Complete failure: could not collect metrics from any of %d repos",
            len(config["repos"]),
        )
        return 2

    # Aggregate
    now = datetime.now(tz=timezone.utc)
    period_start = (now - timedelta(days=args.period_days)).isoformat()
    period_end = now.isoformat()

    aggregated = aggregate_metrics(collected, period_start, period_end)
    # Adjust repos_tracked to include failed repos
    aggregated["repos_tracked"] = len(config["repos"])

    # Output
    if args.output_format in ("json", "both"):
        json_output = format_json_snapshot(aggregated)
        sys.stdout.write(json_output + "\n")
        snapshot_path = write_snapshot(aggregated, args.output_dir)
        logger.info("Snapshot written to %s", snapshot_path)

    if args.output_format in ("markdown", "both"):
        md_output = format_markdown_table(aggregated)
        md_path = args.output_dir / "cross-project-latest.md"
        args.output_dir.mkdir(parents=True, exist_ok=True)
        md_path.write_text(md_output, encoding="utf-8")
        logger.info("Markdown report written to %s", md_path)

    # Summary
    logger.info(
        "Collected %d of %d repos (%d failed)",
        len(collected),
        len(config["repos"]),
        len(failed_repos),
    )

    if failed_repos:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())