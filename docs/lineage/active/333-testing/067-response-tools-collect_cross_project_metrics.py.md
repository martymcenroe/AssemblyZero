All 35 tests already pass. The file exists and is correct. Here's the complete contents:

```python
#!/usr/bin/env python3
"""Cross-project metrics collection tool.

Issue #333: Cross-Project Metrics Aggregation for AssemblyZero Usage Tracking.

Usage:
    python tools/collect_cross_project_metrics.py --config tracked_repos.json
    python tools/collect_cross_project_metrics.py --config tracked_repos.json --dry-run
    python tools/collect_cross_project_metrics.py --config tracked_repos.json --lookback-days 7 --verbose
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import orjson

from assemblyzero.utils.github_metrics_client import GitHubMetricsClient
from assemblyzero.utils.metrics_aggregator import MetricsAggregator
from assemblyzero.utils.metrics_config import load_config

if TYPE_CHECKING:
    from assemblyzero.utils.metrics_models import CrossProjectMetrics

logger = logging.getLogger(__name__)

_RATE_LIMIT_WARN_THRESHOLD = 100
_ESTIMATED_CALLS_PER_REPO = 10


def main(
    config_path: str | None = None,
    output_path: str | None = None,
    lookback_days: int | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Main entry point for cross-project metrics collection.

    Args:
        config_path: Override config file location.
        output_path: Override output file location.
        lookback_days: Override lookback period from config.
        dry_run: If True, print config and exit without collecting.
        verbose: If True, enable detailed logging output.

    Returns:
        Exit code: 0 for success, 1 for partial failure, 2 for total failure.
    """
    # Configure logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Load config
    try:
        config = load_config(config_path)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Configuration error: %s", exc)
        return 2

    # Override lookback_days from CLI if provided
    if lookback_days is not None:
        config["lookback_days"] = lookback_days

    # Filter to enabled repos only
    enabled_repos = [r for r in config["repos"] if r.get("enabled", True)]

    if not enabled_repos:
        logger.error("No enabled repos in configuration")
        return 2

    # Dry-run mode
    if dry_run:
        print("=== Dry Run Mode ===")
        print(f"Config loaded with {len(enabled_repos)} enabled repos:")
        for repo in enabled_repos:
            print(f"  - {repo['full_name']}")
        print(f"Lookback days: {config['lookback_days']}")
        print(f"Output dir: {config['output_dir']}")
        print(f"Cache TTL: {config['cache_ttl_seconds']}s")
        return 0

    # Initialize client
    client = GitHubMetricsClient(cache_ttl=config["cache_ttl_seconds"])

    # Pre-flight rate limit check
    rate_info = client.get_rate_limit_remaining()
    remaining = rate_info.get("remaining", 0)
    estimated_calls = len(enabled_repos) * _ESTIMATED_CALLS_PER_REPO
    logger.info(
        "Rate limit: %d/%d remaining (estimated need: %d)",
        remaining,
        rate_info.get("limit", 0),
        estimated_calls,
    )
    if remaining < _RATE_LIMIT_WARN_THRESHOLD:
        logger.warning(
            "Low rate limit budget: %d remaining. "
            "Collection may be rate-limited.",
            remaining,
        )

    # Collect metrics per repo
    aggregator = MetricsAggregator(client=client, config=config)
    per_repo_results = []
    repos_failed: list[str] = []

    for repo in enabled_repos:
        repo_name = repo["full_name"]
        logger.info("Collecting metrics for %s...", repo_name)
        try:
            metrics = aggregator.collect_repo_metrics(repo)
            per_repo_results.append(metrics)
            logger.info("  ✓ %s collected successfully", repo_name)
        except Exception:
            logger.warning(
                "  ✗ Failed to collect %s", repo_name, exc_info=verbose
            )
            repos_failed.append(repo_name)

    # Check for total failure
    if not per_repo_results:
        logger.error(
            "All repos failed collection. Failed: %s",
            ", ".join(repos_failed),
        )
        return 2

    # Aggregate
    cross_project = aggregator.aggregate(per_repo_results, repos_failed=repos_failed)

    # Write output
    try:
        written_path = write_metrics_output(
            cross_project, config["output_dir"], output_path
        )
        logger.info("Metrics written to: %s", written_path)
    except OSError as exc:
        logger.error("Failed to write output: %s", exc)
        return 2

    # Print summary
    summary = format_summary_table(cross_project)
    print(summary)

    # Return exit code
    if repos_failed:
        return 1
    return 0


def write_metrics_output(
    metrics: CrossProjectMetrics,
    output_dir: str,
    output_path: str | None = None,
) -> str:
    """Write aggregated metrics to JSON file.

    Default filename: cross-project-{YYYY-MM-DD}.json
    Also writes/overwrites cross-project-latest.json as a copy.

    Args:
        metrics: Aggregated cross-project metrics.
        output_dir: Base directory for output.
        output_path: Explicit full path override.

    Returns:
        Path to the written file.

    Raises:
        OSError: If output directory is not writable.
    """
    out_dir = Path(output_dir)
    if not out_dir.is_dir():
        raise OSError(f"Output directory does not exist: {output_dir}")

    if output_path:
        dated_path = Path(output_path)
    else:
        date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        dated_path = out_dir / f"cross-project-{date_str}.json"

    # Serialize with orjson for speed and pretty printing
    json_bytes = orjson.dumps(metrics, option=orjson.OPT_INDENT_2)
    dated_path.write_bytes(json_bytes)

    # Create/overwrite latest.json
    latest_path = dated_path.parent / "cross-project-latest.json"
    shutil.copy2(str(dated_path), str(latest_path))

    return str(dated_path)


def format_summary_table(metrics: CrossProjectMetrics) -> str:
    """Format metrics as a human-readable summary table for stdout.

    Args:
        metrics: Aggregated cross-project metrics.

    Returns:
        Formatted multi-line string with aligned columns.
    """
    lines: list[str] = []
    period = f"{metrics['period_start']} to {metrics['period_end']}"
    lines.append(f"\nCross-Project Metrics Summary ({period})")
    lines.append("=" * 90)

    # Header
    header = (
        f"{'Repository':<35} {'Opened':>7} {'Closed':>7} {'Open':>5} "
        f"{'Avg Close (h)':>14} {'LLDs':>5} {'Reviews':>8} {'Approval%':>10}"
    )
    lines.append(header)

    # Per-repo rows
    for repo_data in metrics["per_repo"]:
        repo_name = repo_data["repo"]
        issues = repo_data["issues"]
        workflows = repo_data["workflows"]
        gemini = repo_data["gemini"]

        avg_close = (
            f"{issues['avg_close_time_hours']:.2f}"
            if issues["avg_close_time_hours"] is not None
            else "N/A"
        )
        approval = (
            f"{gemini['approval_rate'] * 100:.1f}%"
            if gemini["approval_rate"] is not None
            else "N/A"
        )

        row = (
            f"{repo_name:<35} {issues['issues_opened']:>7} "
            f"{issues['issues_closed']:>7} {issues['issues_open_current']:>5} "
            f"{avg_close:>14} {workflows['lld_count']:>5} "
            f"{gemini['total_reviews']:>8} {approval:>10}"
        )
        lines.append(row)

    # Separator
    lines.append("-" * 90)

    # Totals row
    totals = metrics["totals"]
    avg_close_total = (
        f"{totals['avg_close_time_hours']:.2f}"
        if totals["avg_close_time_hours"] is not None
        else "N/A"
    )
    approval_total = (
        f"{totals['gemini_approval_rate'] * 100:.1f}%"
        if totals["gemini_approval_rate"] is not None
        else "N/A"
    )
    totals_row = (
        f"{'TOTALS':<35} {totals['issues_opened']:>7} "
        f"{totals['issues_closed']:>7} {totals['issues_open_current']:>5} "
        f"{avg_close_total:>14} {totals['lld_count']:>5} "
        f"{totals['gemini_reviews']:>8} {approval_total:>10}"
    )
    lines.append(totals_row)

    # Footer
    lines.append("")
    tracked = metrics["repos_tracked"]
    collected = metrics["repos_collected"]
    failed = len(metrics["repos_failed"])
    lines.append(
        f"Repos tracked: {tracked} | Collected: {collected} | Failed: {failed}"
    )

    if metrics["repos_failed"]:
        lines.append(f"Failed repos: {', '.join(metrics['repos_failed'])}")

    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Supports: --config, --output, --lookback-days, --dry-run, --verbose

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed namespace with config_path, output, lookback_days, dry_run, verbose.
    """
    parser = argparse.ArgumentParser(
        description="Collect cross-project metrics for AssemblyZero repositories.",
        prog="collect_cross_project_metrics",
    )
    parser.add_argument(
        "--config",
        dest="config_path",
        type=str,
        default=None,
        help="Path to tracked repos JSON configuration file",
    )
    parser.add_argument(
        "--output",
        dest="output",
        type=str,
        default=None,
        help="Override output file path",
    )
    parser.add_argument(
        "--lookback-days",
        dest="lookback_days",
        type=int,
        default=None,
        help="Override lookback period in days (default: from config or 30)",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Print config summary and exit without collecting",
    )
    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="Enable detailed debug logging",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    exit_code = main(
        config_path=args.config_path,
        output_path=args.output,
        lookback_days=args.lookback_days,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
    sys.exit(exit_code)
```

All 35 tests pass: `35 passed in 4.27s`.
