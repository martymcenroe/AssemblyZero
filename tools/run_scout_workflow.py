#!/usr/bin/env python3
"""CLI entry point for Scout Workflow.

Issue #93: The Scout - External Intelligence Gathering Workflow

Usage:
    # Basic search
    python tools/run_scout_workflow.py --topic "langgraph"

    # With internal code comparison
    python tools/run_scout_workflow.py --topic "async" --internal src/core.py

    # Offline mode (uses fixtures)
    python tools/run_scout_workflow.py --topic "test" --offline --yes

    # Auto-confirm and specify output
    python tools/run_scout_workflow.py --topic "testing" --yes --output ideas/active/

    # JSON output format
    python tools/run_scout_workflow.py --topic "testing" --format json --yes
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from assemblyzero.workflows.scout.graph import create_initial_state
from assemblyzero.workflows.scout.nodes import (
    confirmation_node,
    explorer_node,
    extractor_node,
    gap_analyst_node,
    scribe_node,
)
from assemblyzero.workflows.scout.security import get_safe_write_path, validate_read_path
from assemblyzero.workflows.scout.templates import generate_innovation_brief, generate_json_output


def main():
    parser = argparse.ArgumentParser(
        description="Scout Workflow - External Intelligence Gathering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Required arguments
    parser.add_argument(
        "--topic",
        type=str,
        required=True,
        help="Search topic (e.g., 'langgraph', 'async patterns')",
    )

    # Optional arguments
    parser.add_argument(
        "--internal",
        type=str,
        help="Path to internal code file for comparison",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="ideas/active",
        help="Output directory for Innovation Brief (default: ideas/active)",
    )
    parser.add_argument(
        "--min-stars",
        type=int,
        default=100,
        help="Minimum stars for repository search (default: 100)",
    )
    parser.add_argument(
        "--max-repos",
        type=int,
        default=3,
        help="Maximum repositories to analyze (default: 3)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=30000,
        help="Maximum token budget (default: 30000)",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Offline mode - use fixtures instead of API calls",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompts (auto-confirm data privacy)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output files",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    print(f"Scout Workflow - External Intelligence Gathering")
    print(f"=" * 50)
    print(f"Topic: {args.topic}")
    print(f"Mode: {'offline' if args.offline else 'live'}")
    if args.internal:
        print(f"Internal file: {args.internal}")
    print()

    # Validate internal file if provided
    internal_code = None
    if args.internal:
        try:
            validated_path = validate_read_path(args.internal)
            internal_code = Path(validated_path).read_text(encoding="utf-8")
            print(f"[OK] Internal file loaded ({len(internal_code)} chars)")
        except (ValueError, FileNotFoundError) as e:
            print(f"[ERROR] Error loading internal file: {e}")
            return 1

    # Check confirmation for internal code
    if internal_code and not args.yes:
        print()
        print("[WARNING]  DATA PRIVACY WARNING")
        print("The internal code will be sent to an external LLM for analysis.")
        print("This may expose sensitive information.")
        print()
        response = input("Continue? [y/N]: ").strip().lower()
        if response != "y":
            print("Aborted by user.")
            return 0

    # Create initial state
    state = create_initial_state(
        topic=args.topic,
        internal_file_path=args.internal,
        min_stars=args.min_stars,
        max_tokens=args.max_tokens,
        repo_limit=args.max_repos,
        offline_mode=args.offline,
        confirmed=args.yes,
    )

    if internal_code:
        state["internal_code_content"] = internal_code

    # Run workflow nodes
    print("\n[1/5] Checking confirmation...")
    result = confirmation_node(state)
    if result.get("errors"):
        print(f"[ERROR] {result['errors'][0]}")
        return 1
    print("[OK] Confirmed")

    print("\n[2/5] Searching repositories...")
    result = explorer_node(state)
    state["found_repos"] = result["found_repos"]
    print(f"[OK] Found {len(state['found_repos'])} repositories (limited to top {args.max_repos})")

    if args.verbose:
        for repo in state["found_repos"]:
            print(f"    - {repo['name']} (* {repo['stars']})")

    if not state["found_repos"]:
        print("[WARNING]  No repositories found. Try adjusting search parameters.")
        return 0

    print("\n[3/5] Extracting content...")
    result = extractor_node(state)
    state.update(result)
    print(f"[OK] Extracted content from {len(state['found_repos'])} repositories")
    print(f"    Token usage: {state.get('current_token_usage', 0)}/{args.max_tokens}")

    print("\n[4/5] Analyzing gaps...")
    result = gap_analyst_node(state)
    state.update(result)
    print("[OK] Gap analysis complete")

    print("\n[5/5] Generating Innovation Brief...")
    result = scribe_node(state)
    state.update(result)

    # Determine output path
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    topic_slug = args.topic.lower().replace(" ", "-")[:30]
    if args.format == "json":
        filename = f"innovation-{topic_slug}.json"
    else:
        filename = f"innovation-{topic_slug}.md"

    output_path = get_safe_write_path(filename, str(output_dir), overwrite=args.force)

    # Generate output content
    if args.format == "json":
        content = json.dumps(
            generate_json_output(
                args.topic,
                state["found_repos"],
                state.get("gap_analysis", ""),
            ),
            indent=2,
        )
    else:
        content = generate_innovation_brief(
            args.topic,
            state["found_repos"],
            state.get("gap_analysis", ""),
        )

    # Write output
    Path(output_path).write_text(content, encoding="utf-8")
    print(f"[OK] Innovation Brief saved to: {output_path}")

    print()
    print("=" * 50)
    print("Scout workflow complete!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
