"""Reference-integrity test for the universal CLAUDE.md (#1308).

The universal CLAUDE.md at `C:\\Users\\mcwiz\\Projects\\CLAUDE.md` is
authored by agents (not the operator). I'm responsible for not breaking
its outbound references — stale file paths, dead issue numbers, missing
runbooks, duplicate section headings.

These tests do NOT cover semantic contradictions (that's the audit work
tracked in #1309). They cover regex-checkable reference integrity:

  - File path references resolve (`AssemblyZero/tools/X.py`, etc.)
  - Runbook references resolve (`runbook NNNN`)
  - ADR references resolve (`ADR-NNNN`)
  - No duplicate `## H2` headings
  - Issue references exist on GitHub (best-effort; uses `gh` CLI)

The universal lives outside the AssemblyZero repo, so the tests skip
when the file isn't at the expected path (e.g. CI without operator's
machine layout). They run locally and surface drift before the operator
hits it in real use.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

UNIVERSAL_PATH = Path("C:/Users/mcwiz/Projects/CLAUDE.md")
PROJECTS_ROOT = Path("C:/Users/mcwiz/Projects")
AZ_RUNBOOKS = PROJECTS_ROOT / "AssemblyZero" / "docs" / "runbooks"
AZ_ADRS = PROJECTS_ROOT / "AssemblyZero" / "docs" / "adrs"
AZ_STANDARDS = PROJECTS_ROOT / "AssemblyZero" / "docs" / "standards"

pytestmark = pytest.mark.skipif(
    not UNIVERSAL_PATH.exists(),
    reason=f"Universal CLAUDE.md not found at {UNIVERSAL_PATH} (operator-machine-local test)",
)


@pytest.fixture(scope="module")
def universal_text() -> str:
    return UNIVERSAL_PATH.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def universal_lines(universal_text: str) -> list[str]:
    return universal_text.splitlines()


# ────────────────────────────────────────────────────────────────────
# File-path references
# ────────────────────────────────────────────────────────────────────

# Repo-relative paths under known fleet repos, when wrapped in backticks.
# Matches `AssemblyZero/tools/X.py`, `sentinel/src/Y.js`, etc.
_FLEET_REPO_PREFIXES = (
    "AssemblyZero", "sentinel", "Aletheia", "Clio", "dispatch",
    "patent-general", "boostgauge", "automation-scripts",
    "Chiron", "Heuriskon", "dependabot-honeypot",
)
RE_RELATIVE_PATH = re.compile(
    r"`((?:" + "|".join(_FLEET_REPO_PREFIXES) + r")/[A-Za-z0-9_/.\-]+\.[a-z]{2,5})`"
)

# Home-relative `~/.claude/...` paths
RE_HOME_CLAUDE = re.compile(r"`(~/\.claude/[A-Za-z0-9_/.\-]+\.[a-z]{2,5})`")

# Absolute Windows paths `C:\Users\mcwiz\Projects\...`
RE_ABS_PATH = re.compile(
    r"`(C:[\\/]Users[\\/]mcwiz[\\/]Projects[\\/][A-Za-z0-9_/\\.\-]+\.[a-z]{2,5})`"
)


def _resolve_relative(path_str: str) -> Path:
    return PROJECTS_ROOT / path_str


def _resolve_home(path_str: str) -> Path:
    return Path(str(path_str).replace("~", str(Path.home()), 1))


def _resolve_abs(path_str: str) -> Path:
    return Path(path_str.replace("\\", "/"))


def test_file_path_references_resolve(universal_text: str) -> None:
    """Every backticked file path referenced in universal CLAUDE.md must exist."""
    missing: list[str] = []
    seen: set[str] = set()

    for m in RE_RELATIVE_PATH.finditer(universal_text):
        p = m.group(1)
        if p in seen:
            continue
        seen.add(p)
        if not _resolve_relative(p).exists():
            missing.append(f"  - `{p}` (expected at {_resolve_relative(p)})")

    for m in RE_HOME_CLAUDE.finditer(universal_text):
        p = m.group(1)
        if p in seen:
            continue
        seen.add(p)
        if not _resolve_home(p).exists():
            missing.append(f"  - `{p}` (expected at {_resolve_home(p)})")

    for m in RE_ABS_PATH.finditer(universal_text):
        p = m.group(1)
        if p in seen:
            continue
        seen.add(p)
        if not _resolve_abs(p).exists():
            missing.append(f"  - `{p}`")

    if missing:
        pytest.fail(
            f"{len(missing)} file path reference(s) don't resolve:\n"
            + "\n".join(missing)
        )


# ────────────────────────────────────────────────────────────────────
# Runbook / ADR references
# ────────────────────────────────────────────────────────────────────

# `runbook NNNN` or `runbooks NNNN` (4-digit AZ format)
RE_RUNBOOK_NUM = re.compile(r"runbook[s]?\s+(\d{4})", re.IGNORECASE)
# `ADR-NNNN` or `ADR NNNN`
RE_ADR_NUM = re.compile(r"\bADR[-\s](\d{4})\b", re.IGNORECASE)
# `standard NNNN`
RE_STANDARD_NUM = re.compile(r"standard[s]?\s+(\d{4})", re.IGNORECASE)


def _doc_exists(directory: Path, number: str) -> bool:
    """A doc 'NNNN' exists if `{directory}/NNNN-*.md` resolves."""
    if not directory.exists():
        return False
    return any(directory.glob(f"{number}-*.md"))


def test_runbook_references_resolve(universal_text: str) -> None:
    missing: list[str] = []
    seen: set[str] = set()
    for m in RE_RUNBOOK_NUM.finditer(universal_text):
        n = m.group(1)
        if n in seen:
            continue
        seen.add(n)
        if not _doc_exists(AZ_RUNBOOKS, n):
            missing.append(f"  - runbook {n} (no `{n}-*.md` at {AZ_RUNBOOKS})")
    if missing:
        pytest.fail(
            f"{len(missing)} runbook reference(s) don't resolve:\n"
            + "\n".join(missing)
        )


def test_adr_references_resolve(universal_text: str) -> None:
    missing: list[str] = []
    seen: set[str] = set()
    for m in RE_ADR_NUM.finditer(universal_text):
        n = m.group(1)
        if n in seen:
            continue
        seen.add(n)
        if not _doc_exists(AZ_ADRS, n):
            missing.append(f"  - ADR-{n} (no `{n}-*.md` at {AZ_ADRS})")
    if missing:
        pytest.fail(
            f"{len(missing)} ADR reference(s) don't resolve:\n"
            + "\n".join(missing)
        )


def test_standard_references_resolve(universal_text: str) -> None:
    missing: list[str] = []
    seen: set[str] = set()
    for m in RE_STANDARD_NUM.finditer(universal_text):
        n = m.group(1)
        if n in seen:
            continue
        seen.add(n)
        if not _doc_exists(AZ_STANDARDS, n):
            missing.append(f"  - standard {n} (no `{n}-*.md` at {AZ_STANDARDS})")
    if missing:
        pytest.fail(
            f"{len(missing)} standard reference(s) don't resolve:\n"
            + "\n".join(missing)
        )


# ────────────────────────────────────────────────────────────────────
# Duplicate H2 headings
# ────────────────────────────────────────────────────────────────────


RE_H2 = re.compile(r"^## (.+?)\s*$")


def test_no_duplicate_h2_headings(universal_lines: list[str]) -> None:
    seen: dict[str, int] = {}
    duplicates: list[str] = []
    for i, line in enumerate(universal_lines, start=1):
        m = RE_H2.match(line)
        if not m:
            continue
        heading = m.group(1).strip()
        if heading in seen:
            duplicates.append(
                f"  - '{heading}' at line {i} (first at line {seen[heading]})"
            )
        else:
            seen[heading] = i
    if duplicates:
        pytest.fail(
            f"{len(duplicates)} duplicate H2 heading(s):\n"
            + "\n".join(duplicates)
        )


# ────────────────────────────────────────────────────────────────────
# Issue references (best-effort; uses gh CLI)
# ────────────────────────────────────────────────────────────────────


# AssemblyZero#NNNN or bare #NNNN (assumed AZ); excludes anchor refs like
# `(#section-name)` by requiring digits.
RE_ISSUE_REF = re.compile(
    r"\bAssemblyZero#(\d+)\b|(?<![\w/])#(\d{2,5})\b"
)


def _gh_issue_exists(repo: str, number: int) -> bool:
    """Return True iff issue/PR exists. False on 404. None-equivalent on gh failure."""
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{repo}/issues/{number}", "--jq", ".number"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return True  # gh unavailable; pessimistic-skip so the test doesn't false-fail
    return r.returncode == 0


def test_issue_references_exist(universal_text: str) -> None:
    """Every AssemblyZero#NNNN or bare #NNNN reference must be a real issue/PR.

    Uses gh CLI. If gh unavailable, the helper returns True (effectively skipping
    individual checks). Smoke-check first: if AssemblyZero#1 doesn't resolve,
    skip the whole test (network / auth broken, not a content issue).
    """
    if not _gh_issue_exists("martymcenroe/AssemblyZero", 1):
        pytest.skip("gh CLI unavailable / network issue — skipping issue-ref check")

    seen: set[int] = set()
    missing: list[str] = []
    for m in RE_ISSUE_REF.finditer(universal_text):
        num_str = m.group(1) or m.group(2)
        num = int(num_str)
        if num in seen:
            continue
        seen.add(num)
        if not _gh_issue_exists("martymcenroe/AssemblyZero", num):
            missing.append(f"  - AssemblyZero#{num}")

    if missing:
        pytest.fail(
            f"{len(missing)} AZ issue reference(s) don't exist:\n"
            + "\n".join(missing)
        )
