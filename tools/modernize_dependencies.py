#!/usr/bin/env python3
"""Dependency Modernization Tool.

Issue #351: Automates the tedious cycle of checking outdated dependencies,
updating them one-by-one, running tests, and committing or rolling back.

Usage:
    poetry run python tools/modernize_dependencies.py [OPTIONS]

Options:
    --dry-run       Show what would be updated without making changes
    --package NAME  Update only a specific package
    --report-only   Only generate the outdated report, don't update
    --report-file   Path for JSON report (default: docs/reports/dep-modernization-{timestamp}.json)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def discover_outdated(repo_root: Path) -> list[dict]:
    """Parse `poetry show --outdated --top-level` for outdated packages.

    Args:
        repo_root: Repository root (where pyproject.toml lives).

    Returns:
        List of dicts with keys: name, current, latest, description.
    """
    result = subprocess.run(
        ["poetry", "show", "--outdated", "--top-level"],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        timeout=120,
    )

    if result.returncode != 0:
        print(f"Warning: poetry show --outdated failed: {result.stderr.strip()}")
        return []

    packages = []
    for line in result.stdout.strip().splitlines():
        # Format: "package-name    current    latest    description..."
        # Some lines may have (!) markers for semver-incompatible updates
        parts = line.split()
        if len(parts) >= 3:
            name = parts[0]
            # Skip header-like lines
            if name.startswith("-") or name == "name":
                continue
            current = parts[1]
            # Handle (!) marker: latest might be at index 2 or 3
            latest_idx = 2
            if parts[latest_idx] == "(!)":
                latest_idx = 3
            if latest_idx < len(parts):
                latest = parts[latest_idx]
            else:
                continue
            description = " ".join(parts[latest_idx + 1:]) if len(parts) > latest_idx + 1 else ""
            packages.append({
                "name": name,
                "current": current,
                "latest": latest,
                "description": description,
            })

    return packages


def save_lockfiles(repo_root: Path) -> tuple[str, str]:
    """Save current pyproject.toml and poetry.lock content for rollback.

    Returns:
        Tuple of (pyproject_content, lock_content).
    """
    pyproject = repo_root / "pyproject.toml"
    lock = repo_root / "poetry.lock"
    return (
        pyproject.read_text(encoding="utf-8"),
        lock.read_text(encoding="utf-8") if lock.exists() else "",
    )


def restore_lockfiles(repo_root: Path, pyproject_content: str, lock_content: str) -> None:
    """Restore pyproject.toml and poetry.lock from saved content."""
    (repo_root / "pyproject.toml").write_text(pyproject_content, encoding="utf-8")
    lock_path = repo_root / "poetry.lock"
    if lock_content:
        lock_path.write_text(lock_content, encoding="utf-8")

    # Reinstall to sync the venv with restored lockfile
    subprocess.run(
        ["poetry", "install", "--no-interaction"],
        capture_output=True,
        cwd=str(repo_root),
        timeout=300,
    )


def update_package(repo_root: Path, package_name: str) -> tuple[bool, str]:
    """Run `poetry add package@latest` for a single package.

    Returns:
        Tuple of (success, output_or_error).
    """
    result = subprocess.run(
        ["poetry", "add", f"{package_name}@latest", "--no-interaction"],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        timeout=300,
    )
    output = result.stdout + result.stderr
    return result.returncode == 0, output.strip()


def run_tests(repo_root: Path) -> tuple[bool, str]:
    """Run the test suite to verify the update didn't break anything.

    Returns:
        Tuple of (passed, output).
    """
    result = subprocess.run(
        ["poetry", "run", "pytest", "--tb=short", "-q"],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        timeout=600,
    )
    output = result.stdout + result.stderr
    return result.returncode == 0, output.strip()


def commit_update(repo_root: Path, package_name: str, old_version: str, new_version: str) -> bool:
    """Commit the updated pyproject.toml and poetry.lock.

    Returns:
        True if commit succeeded.
    """
    # Stage files
    subprocess.run(
        ["git", "add", "pyproject.toml", "poetry.lock"],
        capture_output=True,
        cwd=str(repo_root),
    )

    # Commit
    msg = f"deps: update {package_name} {old_version} -> {new_version}"
    result = subprocess.run(
        ["git", "commit", "-m", msg],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    return result.returncode == 0


def modernize(
    repo_root: Path,
    *,
    dry_run: bool = False,
    package_filter: str | None = None,
    report_only: bool = False,
    report_file: Path | None = None,
) -> dict:
    """Main modernization loop.

    Args:
        repo_root: Repository root path.
        dry_run: If True, only show what would be done.
        package_filter: If set, only update this package.
        report_only: If True, only generate the report.
        report_file: Path for the JSON report.

    Returns:
        Report dict with results.
    """
    print("Discovering outdated dependencies...")
    outdated = discover_outdated(repo_root)

    if package_filter:
        outdated = [p for p in outdated if p["name"] == package_filter]

    if not outdated:
        print("All dependencies are up to date!")
        return {"packages": [], "summary": {"total": 0, "updated": 0, "failed": 0, "skipped": 0}}

    print(f"Found {len(outdated)} outdated package(s):")
    for pkg in outdated:
        print(f"  {pkg['name']}: {pkg['current']} -> {pkg['latest']}")

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo": str(repo_root),
        "packages": [],
        "summary": {"total": len(outdated), "updated": 0, "failed": 0, "skipped": 0},
    }

    if dry_run or report_only:
        for pkg in outdated:
            report["packages"].append({
                "name": pkg["name"],
                "current": pkg["current"],
                "latest": pkg["latest"],
                "status": "dry_run" if dry_run else "report_only",
            })
        report["summary"]["skipped"] = len(outdated)
        _save_report(report, repo_root, report_file)
        return report

    # Sequential update loop
    for pkg in outdated:
        name = pkg["name"]
        print(f"\nUpdating {name} ({pkg['current']} -> {pkg['latest']})...")

        # Save state for rollback
        pyproject_saved, lock_saved = save_lockfiles(repo_root)

        # Try to update
        success, add_output = update_package(repo_root, name)
        if not success:
            print(f"  SKIP: poetry add failed: {add_output[:200]}")
            restore_lockfiles(repo_root, pyproject_saved, lock_saved)
            report["packages"].append({
                "name": name,
                "current": pkg["current"],
                "latest": pkg["latest"],
                "status": "add_failed",
                "error": add_output[:500],
            })
            report["summary"]["failed"] += 1
            continue

        # Run tests
        tests_passed, test_output = run_tests(repo_root)
        if not tests_passed:
            print(f"  ROLLBACK: tests failed after updating {name}")
            restore_lockfiles(repo_root, pyproject_saved, lock_saved)
            report["packages"].append({
                "name": name,
                "current": pkg["current"],
                "latest": pkg["latest"],
                "status": "tests_failed",
                "error": test_output[-500:],
            })
            report["summary"]["failed"] += 1
            continue

        # Commit
        committed = commit_update(repo_root, name, pkg["current"], pkg["latest"])
        status = "updated" if committed else "update_no_commit"
        print(f"  OK: {name} updated to {pkg['latest']}")

        report["packages"].append({
            "name": name,
            "current": pkg["current"],
            "latest": pkg["latest"],
            "status": status,
        })
        report["summary"]["updated"] += 1

    _save_report(report, repo_root, report_file)

    # Print summary
    s = report["summary"]
    print(f"\nSummary: {s['updated']} updated, {s['failed']} failed, {s['skipped']} skipped out of {s['total']}")

    return report


def _save_report(report: dict, repo_root: Path, report_file: Path | None) -> None:
    """Save the JSON report to disk."""
    if report_file is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        reports_dir = repo_root / "docs" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_file = reports_dir / f"dep-modernization-{timestamp}.json"

    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Report saved to: {report_file}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Dependency Modernization Tool")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated")
    parser.add_argument("--package", type=str, help="Update only this package")
    parser.add_argument("--report-only", action="store_true", help="Only generate outdated report")
    parser.add_argument("--report-file", type=Path, help="Path for JSON report")
    args = parser.parse_args()

    # Find repo root (assume we're running from it or a subdirectory)
    repo_root = Path.cwd()
    if not (repo_root / "pyproject.toml").exists():
        print("Error: pyproject.toml not found in current directory", file=sys.stderr)
        sys.exit(1)

    report = modernize(
        repo_root,
        dry_run=args.dry_run,
        package_filter=args.package,
        report_only=args.report_only,
        report_file=args.report_file,
    )

    # Exit with non-zero if any updates failed
    if report["summary"]["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
