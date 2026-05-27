#!/usr/bin/env python3
"""tools/lint_per_repo_claude_md.py — Drift detector for per-repo CLAUDE.md files.

Surfaced by #1290 (split from #1259). ADR 0219 (#1258) sets the rule for what
may and may not appear in a per-repo CLAUDE.md. This tool flags drift without
acting on it (read-only audit) so per-repo remediation can be triaged
deliberately.

The 9 drift markers (severity in parens):

  1 [ERROR]   False AssemblyZero/CLAUDE.md rules list (the fabricated list
              signature observed in gh-link-auditor pre-#328 and boostgauge)
  2 [ERROR]   PRE-MERGE GATE references nonexistent orchestrator
  3 [ERROR]   Wrong report filename format ("1{IssueID}" vs "10{IssueID:04d}")
  4 [WARNING] docs/session-logs/ named as cross-session source (should be
              data/handoff-log.md)
  5 [ERROR]   "FIRST: Read AssemblyZero Core Rules" or any variant (per ADR
              0219 Consequence #2, auto-load handles inheritance)
  6 [WARNING] References AssemblyZero in a repo whose .unleashed.json has
              "assemblyZero": false (drift; AZ refs are only legitimate when
              the repo opts in). If .unleashed.json doesn't exist at all, we
              skip this marker — no signal to determine intent.
  7 [WARNING] May duplicate universal CLAUDE.md content (matches phrases
              like "merge sequence" / "enforce_admins" / "banned commands"
              WITHOUT a nearby "override" qualifier). Advisory: legitimate
              per-repo workflow overrides ARE allowed and use the same
              phrases, so this marker hedges via the "override" check.
  8 [ERROR]   Stub (line count < 20)
  9 [WARNING] Hardcoded C:\\Users\\mcwiz\\... path (should be parameterized
              via config.projects_root())

Heuristic notes:

- Markers 6 + 7 are WARNING (not ERROR) because both have legitimate
  override paths (Aletheia overrides the merge-sequence rule deliberately
  per its CLAUDE.md). Operator decides whether each WARNING is real drift.
- Marker 7 specifically checks that "override" doesn't appear within ±200
  chars of any match. Designed to NOT false-positive on Aletheia's
  documented override.

Output:

  - text (default): one line per repo + summary + marker totals
  - json: machine-readable, designed for piping into per-repo issue filers

Exit codes:

  0  — all repos pass (no drift, no missing, no stub)
  1  — argument error (projects root not found, allowlist unreadable)
  2  — one or more repos have drift / missing / stub status

Usage:

  poetry run python tools/lint_per_repo_claude_md.py
  poetry run python tools/lint_per_repo_claude_md.py --json
  poetry run python tools/lint_per_repo_claude_md.py --allowlist allowlist.txt

Related:

  - ADR 0219 (#1258) — the rule this enforces
  - #1259 (parent, split into per-concern issues)
  - #1290 — this tool
  - unleashed#656 — private fleet audit queue (downstream consumer)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Import AssemblyZero config for projects-root resolution.
try:
    from assemblyzero_config import config
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from assemblyzero_config import config

# ────────────────────────────────────────────────────────────────────
# Detector regexes
# ────────────────────────────────────────────────────────────────────

# Marker 1: the fabricated AZ-rules-list signature observed in drifted repos.
# Targets the "claims AZ/CLAUDE.md contains <X>" pattern where <X> is one of
# the false-claim items historically listed.
RE_FALSE_AZ_RULES = re.compile(
    r"AssemblyZero[/\\]CLAUDE\.md.*"
    r"(bash-command rules|visible self-check|worktree isolation|"
    r"decision-making protocol)",
    re.IGNORECASE | re.DOTALL,
)

# Marker 2: PRE-MERGE GATE references nonexistent orchestrator wait.
RE_ORCHESTRATOR_GATE = re.compile(
    r"PRE[-_ ]MERGE GATE.*orchestrator|"
    r"wait for orchestrator.*review",
    re.IGNORECASE | re.DOTALL,
)

# Marker 3: wrong report filename format.
# Real format is 10{IssueID:04d}; wrong is 1{IssueID}. We match the bare
# wrong pattern (e.g. "1{IssueID}" in a path or string template).
RE_WRONG_REPORT_FORMAT = re.compile(
    r"`?1\{IssueID\}|1\{issue_id\}",
    re.IGNORECASE,
)

# Marker 4: docs/session-logs/ named as cross-session source.
RE_SESSION_LOGS_AS_SOURCE = re.compile(
    r"docs/session-logs/.*(cross.session|previous session|continuity)|"
    r"(cross.session|previous session|continuity).*docs/session-logs/",
    re.IGNORECASE | re.DOTALL,
)

# Marker 5: "FIRST: Read AssemblyZero Core Rules" or variant.
RE_FIRST_READ_AZ = re.compile(
    r"FIRST[:\s]+Read AssemblyZero|"
    r"FIRST.*read.*AssemblyZero.*(rules|CLAUDE)",
    re.IGNORECASE,
)

# Marker 9: hardcoded user-specific paths.
RE_HARDCODED_MCWIZ = re.compile(r"C:[\\/]Users[\\/]mcwiz[\\/]")

# Project Identifiers block boundaries — used by marker 9 to skip the
# scaffolder-emitted literal path in the Identifiers section, which is
# load-bearing (it IS the project root on this dev machine) and not drift.
RE_IDENTIFIERS_HEADING = re.compile(r"^## Project Identifiers\s*$", re.MULTILINE)
RE_NEXT_H2 = re.compile(r"^## ", re.MULTILINE)

# Marker 7: phrases that indicate restated universal-CLAUDE.md content.
# These are ADVISORY — legitimate per-repo overrides use the same phrases
# (e.g., Aletheia overrides the merge sequence), so we hedge via the
# "override" proximity check below.
UNIVERSAL_DUPE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"merge sequence", re.IGNORECASE),
    re.compile(r"Closes #N must appear in ALL THREE", re.IGNORECASE),
    re.compile(r"enforce_admins.*?true", re.IGNORECASE),
    re.compile(r"\bbanned commands\b", re.IGNORECASE),
]

# How far to look on either side of a dupe match for the "override" qualifier
# that legitimizes the restatement.
OVERRIDE_PROXIMITY_CHARS = 200
RE_OVERRIDE = re.compile(r"override", re.IGNORECASE)

# #1307: second hedge — explanatory-paragraph exception. A paragraph that
# names the auto-load mechanism, ADR 0219, or the universal CLAUDE.md is
# explaining what lives elsewhere, not restating it. Same proximity window
# as the override hedge.
RE_EXPLANATORY = re.compile(
    r"auto-loaded|ADR\s*0219|universal\s+CLAUDE\.md",
    re.IGNORECASE,
)

STUB_LINE_THRESHOLD = 20


# ────────────────────────────────────────────────────────────────────
# Data classes
# ────────────────────────────────────────────────────────────────────


@dataclass
class Finding:
    marker: int
    severity: str  # 'ERROR' | 'WARNING'
    description: str
    evidence: Optional[str] = None  # short excerpt from the file


@dataclass
class RepoResult:
    repo_name: str
    claude_md_path: Path
    status: str  # 'PASS' | 'DRIFT' | 'MISSING' | 'STUB' | 'SKIPPED'
    line_count: int = 0
    findings: list[Finding] = field(default_factory=list)
    unleashed_assemblyzero: Optional[bool] = None  # from .unleashed.json
    # #1343: when SKIPPED, names why (allowlisted | not-a-git-repo | worktree | wiki-sidecar)
    skipped_reason: Optional[str] = None


# ────────────────────────────────────────────────────────────────────
# Detectors
# ────────────────────────────────────────────────────────────────────


def load_unleashed_assemblyzero(repo_root: Path) -> Optional[bool]:
    """Read `.unleashed.json:assemblyZero`. Returns None if file or key missing."""
    cfg = repo_root / ".unleashed.json"
    if not cfg.exists():
        return None
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    val = data.get("assemblyZero")
    return val if isinstance(val, bool) else None


def _match_excerpt(text: str, m: re.Match[str], context: int = 60) -> str:
    """Return a short excerpt around a regex match for evidence display."""
    start = max(0, m.start() - context)
    end = min(len(text), m.end() + context)
    excerpt = text[start:end].replace("\n", " ").strip()
    return f"...{excerpt}..."


def _strip_identifiers_block(text: str) -> str:
    """Return text with the `## Project Identifiers` section removed.

    Used by marker 9 to ignore the scaffolder-emitted literal Windows path
    that appears in every per-repo CLAUDE.md's Identifiers block (e.g.
    `C:\\Users\\mcwiz\\Projects\\boostgauge`). That literal IS the project
    root on this dev machine — load-bearing, not drift. Marker 9 should
    only fire on `C:\\Users\\mcwiz\\...` occurrences OUTSIDE this block
    (in body prose, example commands, etc.).

    If the file has no `## Project Identifiers` heading, returns the
    original text unchanged (no exception to apply).

    Block boundaries: starts at the `## Project Identifiers` line, ends
    at the next `## ` heading or EOF.
    """
    m = RE_IDENTIFIERS_HEADING.search(text)
    if not m:
        return text
    start = m.start()
    rest = text[m.end():]
    next_m = RE_NEXT_H2.search(rest)
    end = m.end() + next_m.start() if next_m else len(text)
    return text[:start] + text[end:]


def detect_drift(claude_md: Path, repo_root: Path) -> RepoResult:
    """Run all 9 detectors against a single CLAUDE.md and return findings."""
    result = RepoResult(
        repo_name=repo_root.name,
        claude_md_path=claude_md,
        status="PASS",
    )

    if not claude_md.exists():
        result.status = "MISSING"
        return result

    text = claude_md.read_text(encoding="utf-8", errors="replace")
    result.line_count = len(text.splitlines())
    result.unleashed_assemblyzero = load_unleashed_assemblyzero(repo_root)

    # Marker 8: stub (line count < 20). Don't return early — continue
    # detection on stub files; multiple markers can coexist.
    if result.line_count < STUB_LINE_THRESHOLD:
        result.findings.append(Finding(
            8, "ERROR",
            f"Stub (line count {result.line_count} < {STUB_LINE_THRESHOLD})",
        ))

    # Marker 1: false AZ-rules-list signature.
    m = RE_FALSE_AZ_RULES.search(text)
    if m:
        result.findings.append(Finding(
            1, "ERROR",
            "False AssemblyZero/CLAUDE.md rules list",
            _match_excerpt(text, m),
        ))

    # Marker 2: PRE-MERGE GATE / orchestrator wait.
    m = RE_ORCHESTRATOR_GATE.search(text)
    if m:
        result.findings.append(Finding(
            2, "ERROR",
            "PRE-MERGE GATE references nonexistent orchestrator",
            _match_excerpt(text, m),
        ))

    # Marker 3: wrong report filename format.
    m = RE_WRONG_REPORT_FORMAT.search(text)
    if m:
        result.findings.append(Finding(
            3, "ERROR",
            "Wrong report filename format (1{IssueID} vs 10{IssueID:04d})",
            _match_excerpt(text, m),
        ))

    # Marker 4: docs/session-logs/ as cross-session source.
    m = RE_SESSION_LOGS_AS_SOURCE.search(text)
    if m:
        result.findings.append(Finding(
            4, "WARNING",
            "docs/session-logs/ named as cross-session source "
            "(should be data/handoff-log.md)",
            _match_excerpt(text, m),
        ))

    # Marker 5: "FIRST: Read AssemblyZero..."
    m = RE_FIRST_READ_AZ.search(text)
    if m:
        result.findings.append(Finding(
            5, "ERROR",
            'Tells agent to "FIRST: Read AssemblyZero..." '
            "(per ADR 0219 Consequence #2, auto-load handles inheritance)",
            _match_excerpt(text, m),
        ))

    # Marker 6: AZ refs in a repo that has explicitly opted OUT of AZ
    # workflow. Skip if .unleashed.json doesn't exist at all (no signal).
    if result.unleashed_assemblyzero is False:
        m = re.search(r"\bAssemblyZero\b", text)
        if m:
            result.findings.append(Finding(
                6, "WARNING",
                "References AssemblyZero but .unleashed.json:assemblyZero=false",
                _match_excerpt(text, m),
            ))

    # Marker 7: duplication of universal-CLAUDE.md content. Each pattern is
    # checked; for each match, we look ±200 chars for an "override"
    # qualifier. Only fire if no override is nearby — legitimate per-repo
    # overrides (Aletheia's documented merge-sequence override) won't trip.
    for pattern in UNIVERSAL_DUPE_PATTERNS:
        for m in pattern.finditer(text):
            window_start = max(0, m.start() - OVERRIDE_PROXIMITY_CHARS)
            window_end = m.end() + OVERRIDE_PROXIMITY_CHARS
            window = text[window_start:window_end]
            # Existing hedge: "override" qualifier nearby = legitimate per-repo override
            if RE_OVERRIDE.search(window):
                continue
            # #1307 hedge: explanatory keyword nearby ("auto-loaded" / "ADR 0219" /
            # "universal CLAUDE.md") = paragraph is describing what lives elsewhere,
            # not restating it
            if RE_EXPLANATORY.search(window):
                continue
            result.findings.append(Finding(
                7, "WARNING",
                f"May duplicate universal CLAUDE.md content "
                f"(pattern: {pattern.pattern!r})",
                _match_excerpt(text, m),
            ))
            break  # one finding per pattern is enough

    # Marker 9: hardcoded mcwiz paths. Skip the Project Identifiers block —
    # the literal Windows path there is scaffolder-emitted (load-bearing),
    # not drift. Only fires on occurrences OUTSIDE the Identifiers block.
    text_excl_identifiers = _strip_identifiers_block(text)
    m = RE_HARDCODED_MCWIZ.search(text_excl_identifiers)
    if m:
        result.findings.append(Finding(
            9, "WARNING",
            "Hardcoded C:\\Users\\mcwiz\\... path outside Project "
            "Identifiers block (should be parameterized via "
            "config.projects_root())",
            _match_excerpt(text_excl_identifiers, m),
        ))

    # Decide final status. STUB takes precedence over DRIFT for display
    # (an under-threshold file is more fundamentally broken than a drifted
    # one), but stub-AND-drifted files keep both findings.
    if result.line_count < STUB_LINE_THRESHOLD:
        result.status = "STUB"
    elif result.findings:
        result.status = "DRIFT"

    return result


# ────────────────────────────────────────────────────────────────────
# Fleet scan + output
# ────────────────────────────────────────────────────────────────────


def load_allowlist(allowlist_path: Optional[Path]) -> set[str]:
    """Load repo names to skip. Blank lines and # comments ignored."""
    if allowlist_path is None:
        return set()
    if not allowlist_path.exists():
        raise FileNotFoundError(f"Allowlist file not found: {allowlist_path}")
    out: set[str] = set()
    for raw in allowlist_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line)
    return out


def scan_fleet(
    projects_root: Path,
    allowlist: set[str],
    show_skipped: bool = False,
) -> list[RepoResult]:
    """Scan every {projects_root}/*/CLAUDE.md (one level deep) and return results.

    #1343 filters (silently excluded unless show_skipped=True):
    - Non-git directories (no .git present) — not a repo
    - Worktree directories (.git is a file, not a dir) — already linted via parent
    - Wiki sidecar repos (name ends in .wiki) — out of ADR 0219 scope

    Existing behavior (visible regardless of show_skipped):
    - Allowlisted repos — explicit operator-curated skip, shown as SKIPPED
    """
    results: list[RepoResult] = []
    for repo_dir in sorted(projects_root.iterdir()):
        if not repo_dir.is_dir():
            continue
        if repo_dir.name.startswith("."):
            continue

        # #1343: filter non-git directories (not a repo at all)
        git_path = repo_dir / ".git"
        if not git_path.exists():
            if show_skipped:
                results.append(RepoResult(
                    repo_name=repo_dir.name,
                    claude_md_path=repo_dir / "CLAUDE.md",
                    status="SKIPPED",
                    skipped_reason="not-a-git-repo",
                ))
            continue

        # #1343: filter worktrees (.git is a file pointing at parent's gitdir)
        if git_path.is_file():
            if show_skipped:
                results.append(RepoResult(
                    repo_name=repo_dir.name,
                    claude_md_path=repo_dir / "CLAUDE.md",
                    status="SKIPPED",
                    skipped_reason="worktree",
                ))
            continue

        # #1343: filter wiki sidecars (name ends in .wiki)
        if repo_dir.name.endswith(".wiki"):
            if show_skipped:
                results.append(RepoResult(
                    repo_name=repo_dir.name,
                    claude_md_path=repo_dir / "CLAUDE.md",
                    status="SKIPPED",
                    skipped_reason="wiki-sidecar",
                ))
            continue

        # Existing: allowlist (always visible)
        if repo_dir.name in allowlist:
            results.append(RepoResult(
                repo_name=repo_dir.name,
                claude_md_path=repo_dir / "CLAUDE.md",
                status="SKIPPED",
                skipped_reason="allowlisted",
            ))
            continue

        claude_md = repo_dir / "CLAUDE.md"
        results.append(detect_drift(claude_md, repo_dir))
    return results


def format_text(results: list[RepoResult]) -> str:
    lines: list[str] = []
    for r in results:
        if r.status == "PASS":
            tag = "PASS"
        elif r.status == "MISSING":
            tag = "MISSING"
        elif r.status == "SKIPPED":
            reason = r.skipped_reason or "allowlisted"
            tag = f"SKIPPED ({reason})"
        elif r.status == "STUB":
            marker_ids = ",".join(str(f.marker) for f in r.findings)
            tag = f"STUB({r.line_count} lines; markers: {marker_ids})"
        elif r.status == "DRIFT":
            marker_ids = ",".join(str(f.marker) for f in r.findings)
            errs = sum(1 for f in r.findings if f.severity == "ERROR")
            warns = sum(1 for f in r.findings if f.severity == "WARNING")
            tag = f"DRIFT(markers: {marker_ids}; E:{errs}/W:{warns})"
        else:
            tag = r.status
        lines.append(f"{r.repo_name}: {tag}")
    # Summary
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    lines.append("")
    lines.append(
        f"Summary: {counts.get('PASS', 0)} pass, "
        f"{counts.get('DRIFT', 0)} drift, "
        f"{counts.get('MISSING', 0)} missing, "
        f"{counts.get('STUB', 0)} stub, "
        f"{counts.get('SKIPPED', 0)} skipped "
        f"(total {len(results)})"
    )
    # Marker totals
    marker_totals: dict[int, int] = {}
    for r in results:
        for f in r.findings:
            marker_totals[f.marker] = marker_totals.get(f.marker, 0) + 1
    if marker_totals:
        lines.append(
            "Marker counts: "
            + ", ".join(f"M{k}={v}" for k, v in sorted(marker_totals.items()))
        )
    return "\n".join(lines)


def format_json(results: list[RepoResult]) -> str:
    out = []
    for r in results:
        out.append({
            "repo": r.repo_name,
            "status": r.status,
            "line_count": r.line_count,
            "unleashed_assemblyzero": r.unleashed_assemblyzero,
            "skipped_reason": r.skipped_reason,
            "findings": [
                {
                    "marker": f.marker,
                    "severity": f.severity,
                    "description": f.description,
                    "evidence": f.evidence,
                }
                for f in r.findings
            ],
            "claude_md_path": str(r.claude_md_path),
        })
    return json.dumps(out, indent=2)


# ────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Drift detector for per-repo CLAUDE.md files (ADR 0219).",
    )
    parser.add_argument(
        "--projects-root",
        type=Path,
        default=None,
        help="Override projects root (default from config.projects_root())",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help="File with line-separated repo names to skip "
             "(blank lines and # comments ignored)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--show-skipped",
        action="store_true",
        help="Include silently-filtered entries (non-git dirs, worktrees, "
             "wiki sidecars) in the output with skipped_reason populated. "
             "Default: silently exclude these. Allowlisted repos are "
             "always shown regardless of this flag.",
    )
    args = parser.parse_args(argv)

    projects_root = args.projects_root or Path(config.projects_root())
    if not projects_root.exists():
        print(f"ERROR: projects root not found: {projects_root}", file=sys.stderr)
        return 1

    try:
        allowlist = load_allowlist(args.allowlist)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    results = scan_fleet(projects_root, allowlist, show_skipped=args.show_skipped)

    if args.format == "json":
        print(format_json(results))
    else:
        print(format_text(results))

    has_drift = any(
        r.status in ("DRIFT", "STUB", "MISSING") for r in results
    )
    return 2 if has_drift else 0


if __name__ == "__main__":
    sys.exit(main())
