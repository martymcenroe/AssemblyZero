#!/usr/bin/env python3
"""Fleet backfill: ensure canonical GitHub labels (implementation, lld) exist on every AZ-managed repo.

`tools/new_repo_setup.py` creates two canonical labels on newly bootstrapped
repos via `create_canonical_labels()` since #1061. Repos that predate that
change don't have these labels, so the metrics_aggregator's
"in-implementation" classifier (which filters on the `implementation` label)
reports partial/inconsistent counts across the fleet.

This script enumerates martymcenroe-owned repos and applies the canonical
label set using `gh label create --force` (idempotent — updates color and
description on existing labels rather than failing).

Single source of truth:
    Imports `_CANONICAL_LABELS` from `new_repo_setup.py` directly. If that
    constant changes, this backfill picks it up.

Auth:
    Fine-grained PAT sufficient. `gh label create` only needs "Issues: write".

Usage:
    poetry run python tools/backfill_canonical_labels.py            # dry-run, all repos
    poetry run python tools/backfill_canonical_labels.py --apply    # apply across fleet
    poetry run python tools/backfill_canonical_labels.py --repos A,B  # limit scope

Issue: #1213 | Carryover from: #1061
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from new_repo_setup import _CANONICAL_LABELS  # noqa: E402

GITHUB_USER = "martymcenroe"
ISSUE_NUMBER = 1213
FLEET_REPO_LIMIT = 200  # well above current ~62 repos


@dataclass
class RepoResult:
    repo: str
    created: int = 0
    updated: int = 0
    failed: list[str] = field(default_factory=list)
    error: str = ""


def run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
    """Run a subprocess; capture text output; default check=False."""
    return subprocess.run(
        cmd, capture_output=True, text=True, check=check, timeout=60,
    )


def list_fleet_repos() -> list[str]:
    """Enumerate non-archived, non-fork repos owned by GITHUB_USER.

    Returns names without owner prefix (e.g., "Aletheia" not
    "martymcenroe/Aletheia").
    """
    r = run([
        "gh", "repo", "list", GITHUB_USER,
        "--limit", str(FLEET_REPO_LIMIT),
        "--no-archived",
        "--source",  # exclude forks
        "--json", "name",
    ])
    if r.returncode != 0:
        print(f"ERROR listing repos: {(r.stderr or '').strip()[:200]}", file=sys.stderr)
        return []
    try:
        data = json.loads(r.stdout or "[]")
    except json.JSONDecodeError as e:
        print(f"ERROR parsing repo list: {e}", file=sys.stderr)
        return []
    return sorted(item["name"] for item in data)


def get_existing_labels(repo: str) -> dict[str, dict] | None:
    """Return {label_name: {color, description}} for the repo, or None on error."""
    r = run([
        "gh", "label", "list",
        "--repo", f"{GITHUB_USER}/{repo}",
        "--limit", "200",
        "--json", "name,color,description",
    ])
    if r.returncode != 0:
        return None
    try:
        labels = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return None
    return {
        label["name"]: {
            "color": label.get("color", ""),
            "description": label.get("description", ""),
        }
        for label in labels
    }


def label_state(
    existing: dict[str, dict], name: str, color: str, description: str,
) -> str:
    """Classify what `gh label create --force` would do.

    Returns 'create' (label absent), 'update' (label present but drifted),
    or 'noop' (label present and matches canonical).
    """
    if name not in existing:
        return "create"
    current = existing[name]
    if (
        current.get("color", "").lower() == color.lower()
        and (current.get("description") or "") == description
    ):
        return "noop"
    return "update"


def apply_label(repo: str, name: str, color: str, description: str) -> tuple[bool, str]:
    """Run `gh label create --force` for a single label. Returns (ok, error)."""
    r = run([
        "gh", "label", "create", name,
        "--color", color,
        "--description", description,
        "--force",
        "--repo", f"{GITHUB_USER}/{repo}",
    ])
    if r.returncode != 0:
        return False, (r.stderr or "").strip()[:200]
    return True, ""


def process_repo(repo: str, dry_run: bool) -> RepoResult:
    """Classify (and optionally apply) canonical labels on one repo."""
    existing = get_existing_labels(repo)
    if existing is None:
        return RepoResult(repo, error="could not list existing labels")
    result = RepoResult(repo)
    for name, color, description in _CANONICAL_LABELS:
        state = label_state(existing, name, color, description)
        if state == "noop":
            continue
        if dry_run:
            if state == "create":
                result.created += 1
            else:
                result.updated += 1
            continue
        ok, err = apply_label(repo, name, color, description)
        if not ok:
            result.failed.append(f"{name}: {err}")
        elif state == "create":
            result.created += 1
        else:
            result.updated += 1
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    parser.add_argument("--apply", action="store_true",
                        help="Actually create/update labels. Default is dry-run.")
    parser.add_argument("--repos",
                        help="Comma-separated repo names to limit scope. "
                             "Default: all non-archived, non-fork repos owned "
                             f"by {GITHUB_USER}.")
    args = parser.parse_args(argv)

    if args.repos:
        targets = [r.strip() for r in args.repos.split(",") if r.strip()]
    else:
        targets = list_fleet_repos()
        if not targets:
            print("No repos enumerated. Check gh auth.")
            return 1

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"Mode: {mode}")
    print(f"Canonical labels: {[n for n, _, _ in _CANONICAL_LABELS]}")
    print(f"Targets: {len(targets)} repo(s)")
    print()

    results: list[RepoResult] = []
    for repo in targets:
        print(f"--- {repo} ---")
        result = process_repo(repo, dry_run=not args.apply)
        results.append(result)
        if result.error:
            print(f"  ERROR: {result.error}")
            continue
        if result.failed:
            for f in result.failed:
                print(f"  FAILED: {f}")
        total_changes = result.created + result.updated
        if total_changes == 0 and not result.failed:
            print("  noop (all canonical labels already present and matching)")
        else:
            parts = []
            if result.created:
                parts.append(f"create={result.created}")
            if result.updated:
                parts.append(f"update={result.updated}")
            if result.failed:
                parts.append(f"failed={len(result.failed)}")
            verb = "would " if not args.apply else ""
            print(f"  {verb}{', '.join(parts)}")

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total_created = sum(r.created for r in results)
    total_updated = sum(r.updated for r in results)
    total_failed = sum(len(r.failed) for r in results)
    total_errors = sum(1 for r in results if r.error)
    print(f"  Repos processed: {len(results)}")
    print(f"  Labels {'would be ' if not args.apply else ''}created: {total_created}")
    print(f"  Labels {'would be ' if not args.apply else ''}updated: {total_updated}")
    print(f"  Label apply failures: {total_failed}")
    print(f"  Repo errors: {total_errors}")
    if not args.apply and (total_created + total_updated) > 0:
        print(f"\nRe-run with --apply to actually create/update labels.")
    if total_failed or total_errors:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
