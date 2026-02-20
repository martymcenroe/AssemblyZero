#!/usr/bin/env python3
"""
tools/audit_schedule_check.py - Audit Schedule Compliance Check

Enforces audit schedule from the project's audit index (Section 5.1):
- Quarterly audits: Block if > 90 days overdue, warn at 67 days (75%)
- Monthly audits: Block if > 30 days overdue, warn at 22 days (75%)
- Weekly audits: Block if > 7 days overdue, warn at 5 days (75%)
- Per PR / On Event / Ultimate: Skip (handled separately)

Auto-detects project numbering prefix from the audit-index file,
so it works for both AssemblyZero (0xxx) and Aletheia (10xxx).

Reference: Issue #250, #407
"""

import re
import sys
from datetime import datetime
from pathlib import Path

# Thresholds in days
THRESHOLDS = {
    "quarterly": {"block": 90, "warn": 67},  # 75% of 90
    "monthly": {"block": 30, "warn": 22},    # ~75% of 30
    "weekly": {"block": 7, "warn": 5},        # ~75% of 7
}

# Frequencies we enforce (everything else is skipped)
ENFORCED_FREQUENCIES = {"weekly", "monthly", "quarterly"}


def detect_audit_index(docs_dir: Path) -> tuple[Path | None, int | None, int | None]:
    """
    Find the audit index file and extract the base number.

    Returns (index_path, index_base, pad_length) or (None, None, None).
    Example: 0800-audit-index.md → (path, 800, 4)
             10800-audit-index.md → (path, 10800, 5)
    """
    audits_dir = docs_dir / "audits"
    if not audits_dir.exists():
        return None, None, None

    index_files = list(audits_dir.glob("*audit-index.md"))
    if not index_files:
        return None, None, None

    index_path = index_files[0]
    match = re.match(r"(\d+)-audit-index", index_path.stem)
    if not match:
        return None, None, None

    num_str = match.group(1)
    return index_path, int(num_str), len(num_str)


def parse_frequency_matrix(content: str) -> dict[str, str]:
    """
    Parse Section 5.1 "By Frequency" table from the audit index.

    Expected format:
    | Frequency | Audits |
    |-----------|--------|
    | **Weekly** | 0816, 0828, 0834 |
    | **Monthly** | 0804, 0809, ... |

    Returns dict mapping base audit number (str) to normalized frequency.
    Example: {"0816": "weekly", "0809": "monthly", ...}
    """
    result = {}

    # Find Section 5.1 content
    section_match = re.search(r"### 5\.1\s+By Frequency", content)
    if not section_match:
        # Try without subsection numbering
        section_match = re.search(r"## 5\.\s*Frequency", content)
    if not section_match:
        return result

    section_content = content[section_match.end():]

    # Stop at next section
    next_section = re.search(r"\n##[# ]", section_content)
    if next_section:
        section_content = section_content[:next_section.start()]

    # Parse table rows: | **Frequency** | audit_list |
    for line in section_content.split("\n"):
        if not line.strip().startswith("|"):
            continue
        if re.match(r"\|\s*-+", line):
            continue

        # Extract frequency name and audit list
        row_match = re.match(
            r"\|\s*\*?\*?([^*|]+?)\*?\*?\s*\|\s*([^|]+)\|",
            line,
        )
        if not row_match:
            continue

        freq_raw = row_match.group(1).strip().lower()
        audits_raw = row_match.group(2).strip()

        # Normalize frequency to our enforced categories
        if "weekly" in freq_raw:
            freq = "weekly"
        elif "monthly" in freq_raw:
            freq = "monthly"
        elif "quarterly" in freq_raw:
            freq = "quarterly"
        else:
            # Skip: per pr, continuous, on event, on demand, ultimate
            continue

        # Extract audit numbers (e.g., "0816, 0828*, 0834")
        for num_match in re.finditer(r"(\d{3,5})\*?", audits_raw):
            audit_num = num_match.group(1)
            result[audit_num] = freq

    return result


def to_project_number(base_num: str, index_base: int, pad_len: int) -> str:
    """
    Convert a base audit number to a project-specific file number.

    For AssemblyZero (index_base=800, pad=4):
      0809 → offset 9 → 800+9=809 → "0809"
    For Aletheia (index_base=10800, pad=5):
      0809 → offset 9 → 10800+9=10809 → "10809"
    """
    # The base in the frequency table is always 08xx format
    offset = int(base_num) - 800
    return str(index_base + offset).zfill(pad_len)


def get_latest_audit_date(content: str) -> datetime | None:
    """
    Extract the most recent audit date from the audit record table.

    Expected format:
    | Date | Auditor | Findings Summary | Issues Created |
    |------|---------|------------------|----------------|
    | 2026-01-10 | Claude Opus 4.5 | PASS: ... | None |
    """
    audit_record_match = re.search(r"## \d+\.\s*Audit Record", content)
    if not audit_record_match:
        return None

    section_content = content[audit_record_match.end():]

    next_section = re.search(r"\n## ", section_content)
    if next_section:
        section_content = section_content[:next_section.start()]

    dates = []
    in_table = False

    for line in section_content.strip().split("\n"):
        if not line.strip().startswith("|"):
            continue

        if re.match(r"\|\s*-+", line):
            in_table = True
            continue

        if not in_table:
            continue

        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]

        if len(cells) >= 1:
            try:
                date = datetime.strptime(cells[0], "%Y-%m-%d")
                dates.append(date)
            except ValueError:
                continue

    return max(dates) if dates else None


def check_audit_schedule(
    project_num: str,
    frequency: str,
    file_path: Path,
    today: datetime,
) -> dict:
    """
    Check if an audit is overdue.

    Returns dict with:
    - status: "ok", "warn", "block"
    - days_since: days since last audit
    - threshold: applicable threshold
    - frequency: weekly/monthly/quarterly
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return {"status": "block", "reason": "cannot read file"}

    last_audit = get_latest_audit_date(content)
    if not last_audit:
        return {
            "status": "warn",
            "reason": "new audit - needs initial execution",
            "frequency": frequency,
            "days_since": None,
        }

    days_since = (today - last_audit).days
    thresholds = THRESHOLDS[frequency]

    if days_since > thresholds["block"]:
        return {
            "status": "block",
            "days_since": days_since,
            "threshold": thresholds["block"],
            "frequency": frequency,
            "last_audit": last_audit.strftime("%Y-%m-%d"),
        }
    elif days_since > thresholds["warn"]:
        return {
            "status": "warn",
            "days_since": days_since,
            "threshold": thresholds["block"],
            "frequency": frequency,
            "last_audit": last_audit.strftime("%Y-%m-%d"),
        }
    else:
        return {
            "status": "ok",
            "days_since": days_since,
            "frequency": frequency,
            "last_audit": last_audit.strftime("%Y-%m-%d"),
        }


def main() -> int:
    """Run audit schedule compliance check."""
    print("=== Audit Schedule Compliance Check ===")

    docs_dir = Path("docs")
    if not docs_dir.exists():
        print("  No docs/ directory found, skipping...")
        return 0

    # Auto-detect project numbering
    index_path, index_base, pad_len = detect_audit_index(docs_dir)
    if not index_path or index_base is None or pad_len is None:
        print("  No audit index file found, skipping...")
        return 0

    print(f"  Index: {index_path.name} (base: {index_base})")

    # Parse frequency mapping from the index
    content = index_path.read_text(encoding="utf-8")
    freq_map = parse_frequency_matrix(content)

    if not freq_map:
        print("  No frequency matrix found in index (Section 5.1), skipping...")
        return 0

    print(f"  Scheduled audits: {len(freq_map)}")

    today = datetime.now()
    blocks = []
    warns = []
    oks = []

    audits_dir = docs_dir / "audits"

    for base_num, frequency in sorted(freq_map.items()):
        project_num = to_project_number(base_num, index_base, pad_len)

        # Find the audit file
        pattern = f"{project_num}-audit-*.md"
        matches = list(audits_dir.glob(pattern))

        if not matches:
            # Try alternate patterns (e.g., horizon scanning, meta-audit)
            alt_pattern = f"{project_num}-*.md"
            matches = list(audits_dir.glob(alt_pattern))

        if not matches:
            blocks.append({
                "audit": project_num,
                "base": base_num,
                "status": "block",
                "reason": f"audit file not found (pattern: {pattern})",
            })
            continue

        file_path = matches[0]
        result = check_audit_schedule(project_num, frequency, file_path, today)
        result["audit"] = project_num
        result["base"] = base_num
        result["file"] = file_path.name

        if result["status"] == "block":
            blocks.append(result)
        elif result["status"] == "warn":
            warns.append(result)
        elif result["status"] == "ok":
            oks.append(result)

    # Print results
    print(f"\n  Today: {today.strftime('%Y-%m-%d')}")
    print(f"  Checked: {len(freq_map)} scheduled audits\n")

    if oks:
        print("  OK:")
        for item in oks:
            print(f"    {item['audit']} ({item['frequency']}): "
                  f"last run {item['last_audit']} ({item['days_since']}d ago)")

    if warns:
        print("\n  WARNING (approaching deadline or needs attention):")
        for item in warns:
            if item.get("days_since") is not None:
                days_left = item["threshold"] - item["days_since"]
                print(f"    {item['audit']} ({item['frequency']}): "
                      f"last run {item['last_audit']} ({item['days_since']}d ago) - "
                      f"{days_left}d until overdue")
            else:
                print(f"    {item['audit']} ({item['frequency']}): "
                      f"{item.get('reason', 'needs attention')}")

    if blocks:
        print("\n  BLOCKED (overdue):")
        for item in blocks:
            days_since_val = item.get("days_since")
            threshold_val = item.get("threshold")
            if isinstance(days_since_val, int) and isinstance(threshold_val, int):
                overdue = days_since_val - threshold_val
                print(f"    {item['audit']} ({item['frequency']}): "
                      f"last run {item['last_audit']} ({days_since_val}d ago) - "
                      f"{overdue}d OVERDUE")
            else:
                print(f"    {item['audit']}: {item.get('reason', 'unknown error')}")

    print()

    if blocks:
        print(f"FAILED: {len(blocks)} audit(s) overdue. Run these audits before merging.")
        print("See audit index Section 5 for audit schedule requirements.")
        return 1

    if warns:
        print(f"PASSED with {len(warns)} warning(s). Consider running these audits soon.")
    else:
        print("=== AUDIT SCHEDULE CHECK PASSED ===")

    return 0


if __name__ == "__main__":
    sys.exit(main())
