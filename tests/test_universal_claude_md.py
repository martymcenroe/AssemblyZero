"""Reference-integrity test for the universal CLAUDE.md (#1308).

The universal CLAUDE.md at `<Projects>/CLAUDE.md` is
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
hits it in real use. The checkers take the text as an argument, so
`tests/unit/test_universal_claude_md_checkers.py` runs them on fixtures in
the unit tier, which CI runs (#4733, #3730).
"""
from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from assemblyzero.core import seats
from assemblyzero.core.projects_root import PROJECTS, spellings

# #3609: derived from where this checkout sits, never spelled.
PROJECTS_ROOT = PROJECTS
UNIVERSAL_PATH = PROJECTS_ROOT / "CLAUDE.md"
AZ_RUNBOOKS = PROJECTS_ROOT / "AssemblyZero" / "docs" / "runbooks"
AZ_STANDARDS = PROJECTS_ROOT / "AssemblyZero" / "docs" / "standards"
# #3730: an ADR number counts as this repository's only when the text names
# no other repository for it.
DEFAULT_ADR_REPO = "AssemblyZero"

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
    "Chiron", "Heuriskon",
)
RE_RELATIVE_PATH = re.compile(
    r"`((?:" + "|".join(_FLEET_REPO_PREFIXES) + r")/[A-Za-z0-9_/.\-]+\.[a-z]{2,5})`"
)

# Home-relative `~/.claude/...` paths
RE_HOME_CLAUDE = re.compile(r"`(~/\.claude/[A-Za-z0-9_/.\-]+\.[a-z]{2,5})`")

# Absolute Windows paths under the Projects root, `<root>\...` with either
# separator; the root is the Windows spelling of PROJECTS_ROOT (#3609).
_WINDOWS_ROOT = r"[\\/]".join(
    re.escape(part) for part in spellings(PROJECTS_ROOT)["windows"].split("\\")
)
RE_ABS_PATH = re.compile(
    r"`" + _WINDOWS_ROOT + r"[\\/]([A-Za-z0-9_/\\.\-]+\.[a-z]{2,5})`"
)


def _resolve_relative(path_str: str) -> Path:
    return PROJECTS_ROOT / path_str


def _resolve_home(path_str: str, home: Path | None = None) -> Path:
    return Path(str(path_str).replace("~", str(home or Path.home()), 1))


def _resolve_abs(path_str: str) -> Path:
    """The part after the root, opened under PROJECTS_ROOT on whichever side runs."""
    return PROJECTS_ROOT / path_str.replace("\\", "/")


@dataclass(frozen=True)
class StateFile:
    """A `~/.claude/` file the law names whose absence is a normal state (#4733).

    Its presence proves nothing about the reference, so the check reads the
    code that owns the file: the reference is right while the owner still
    names the same basename.
    """

    reason: str
    owner: str
    owner_name: Callable[[], str]


#: #4733: closed, one entry per reason, never a pattern, because a pattern
#: would also excuse a real missing file. Every `~/.claude/` path not listed
#: here must exist.
STATE_FILES: dict[str, StateFile] = {
    "~/.claude/claude-spend.lock": StateFile(
        reason=(
            "exists only while the operator has the spend lock thrown "
            "(tools/claude_spend_lock.py throws and lifts it); lifted is its normal state"
        ),
        owner="assemblyzero/core/seats.py LOCK_NAME",
        owner_name=lambda: seats.LOCK_NAME,
    ),
}


def find_unresolved_file_paths(text: str, home: Path | None = None) -> list[str]:
    """One line per backticked file path in `text` that does not resolve."""
    missing: list[str] = []
    seen: set[str] = set()

    for m in RE_RELATIVE_PATH.finditer(text):
        p = m.group(1)
        if p in seen:
            continue
        seen.add(p)
        if not _resolve_relative(p).exists():
            missing.append(f"  - `{p}` (expected at {_resolve_relative(p)})")

    for m in RE_HOME_CLAUDE.finditer(text):
        p = m.group(1)
        if p in seen:
            continue
        seen.add(p)
        state_file = STATE_FILES.get(p)
        if state_file is not None:
            owned = state_file.owner_name()
            if Path(p).name != owned:
                missing.append(
                    f"  - `{p}` is a state file, but its owner, {state_file.owner}, "
                    f"now names `{owned}`"
                )
            continue
        if not _resolve_home(p, home).exists():
            missing.append(f"  - `{p}` (expected at {_resolve_home(p, home)})")

    for m in RE_ABS_PATH.finditer(text):
        p = m.group(1)
        if p in seen:
            continue
        seen.add(p)
        if not _resolve_abs(p).exists():
            missing.append(f"  - `{p}`")

    return missing


def test_file_path_references_resolve(universal_text: str) -> None:
    """Every backticked file path referenced in universal CLAUDE.md must exist."""
    missing = find_unresolved_file_paths(universal_text)
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
# #3730: `Projects/<Repo>/docs/adrs/NNNN-`, the text naming the repository an
# ADR number belongs to. The repository is read from the text, never listed here.
RE_ADR_PATH = re.compile(r"\bProjects/([A-Za-z0-9_.\-]+)/docs/adrs/(\d{4})-")
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


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def find_unresolved_adr_references(
    text: str, projects_root: Path = PROJECTS_ROOT
) -> list[str]:
    """One line per `ADR-NNNN` in `text` that cannot be placed or does not resolve (#3730).

    An ADR number belongs to the repository a `Projects/<Repo>/docs/adrs/NNNN-`
    path anywhere in the text names for it. A number the text names in no
    repository counts as DEFAULT_ADR_REPO's. A number named in two repositories
    cannot be placed. Every failure names the lines that cite the number.
    """
    named: dict[str, set[str]] = {}
    for m in RE_ADR_PATH.finditer(text):
        named.setdefault(m.group(2), set()).add(m.group(1))

    cited: dict[str, list[int]] = {}
    for m in RE_ADR_NUM.finditer(text):
        cited.setdefault(m.group(1), []).append(_line_of(text, m.start()))

    missing: list[str] = []
    for n, lines in cited.items():
        where = "line " + ", ".join(str(line) for line in lines)
        repos = sorted(named.get(n, ()))
        if len(repos) > 1:
            missing.append(
                f"  - ADR-{n} ({where}): the text names it in {', '.join(repos)}, "
                "so it cannot be placed"
            )
            continue
        repo = repos[0] if repos else DEFAULT_ADR_REPO
        adrs = projects_root / repo / "docs" / "adrs"
        if _doc_exists(adrs, n):
            continue
        if repos:
            missing.append(
                f"  - ADR-{n} ({where}): no `{n}-*.md` at {adrs}, the repository "
                "the text names for it"
            )
        else:
            missing.append(
                f"  - ADR-{n} ({where}): the text names no repository for it, and "
                f"{DEFAULT_ADR_REPO} has no `{n}-*.md` at {adrs}"
            )
    return missing


def test_adr_references_resolve(universal_text: str) -> None:
    missing = find_unresolved_adr_references(universal_text)
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
