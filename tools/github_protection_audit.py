#!/usr/bin/env python3
"""GitHub Protection Audit & Probe Script.

Two modes:
  --audit   Read branch protection, rulesets, and enforcement settings
            (requires classic token with repo + admin:repo_hook + read:org)
  --probe   Test what the current token can/cannot do via API calls
            (works with any token — records HTTP status codes as evidence)

Both modes scan ALL repos under the account via `gh repo list`.

Usage:
    # Full audit + probe with classic token
    poetry run python tools/github_protection_audit.py --audit --probe

    # Probe-only with fine-grained PAT
    poetry run python tools/github_protection_audit.py --probe

    # Audit-only, no file save
    poetry run python tools/github_protection_audit.py --audit --no-save

Issue #TBD: GitHub Protection Audit Tool
"""

import argparse
import atexit
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from assemblyzero.telemetry import flush, track_tool
atexit.register(flush)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ProbeResult:
    """Result of a single API probe."""

    probe_id: str         # P01, P02, etc.
    repo: str             # owner/repo
    endpoint: str         # API path
    method: str           # GET, PUT, DELETE, etc.
    http_status: int      # 200, 403, 404
    verdict: str          # PROTECTED, VULNERABLE, INFORMATIONAL, N/A
    attack_category: str  # e.g. "Reconnaissance"
    attack_technique: str # MITRE ATT&CK ID
    detail: str = ""      # response snippet or note


@dataclass
class AuditCheck:
    """Result of a single audit check."""

    check_id: str   # A01, A02, etc.
    repo: str       # owner/repo
    setting: str    # what was checked
    expected: str   # expected value
    actual: str     # actual value
    status: str     # PASS, FAIL, WARN


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

def gh_api(method: str, endpoint: str, body: dict | None = None,
           timeout: int = 30) -> tuple[int, dict | str]:
    """Call GitHub API via `gh api` and return (status_code, response).

    Returns the HTTP status code and parsed JSON (or raw string on failure).
    Never raises — all errors are captured as status codes.
    """
    cmd = ["gh", "api", "-X", method, endpoint,
           "--include"]  # --include gives us headers + status
    if body is not None:
        cmd.extend(["-f", json.dumps(body)])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 0, "timeout"
    except FileNotFoundError:
        return 0, "gh CLI not found"

    # Parse status from --include output (first line: HTTP/2 200)
    output = proc.stdout
    status_code = 0
    body_text = ""

    lines = output.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("HTTP/"):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    status_code = int(parts[1])
                except ValueError:
                    pass
        elif line.strip() == "" and i > 0:
            # Empty line separates headers from body
            body_text = "\n".join(lines[i + 1:])
            break

    if not body_text and proc.stderr:
        body_text = proc.stderr.strip()

    # Try to parse JSON
    try:
        parsed = json.loads(body_text) if body_text.strip() else {}
    except json.JSONDecodeError:
        parsed = body_text

    # Fallback: if we didn't get a status from --include, infer from returncode
    if status_code == 0:
        if proc.returncode == 0:
            status_code = 200
        else:
            # Try to extract from stderr
            stderr = proc.stderr
            if "404" in stderr:
                status_code = 404
            elif "403" in stderr or "Resource not accessible" in stderr:
                status_code = 403
            elif "422" in stderr:
                status_code = 422
            else:
                status_code = 999  # unknown error

    return status_code, parsed


def gh_api_silent(method: str, endpoint: str,
                  timeout: int = 30) -> tuple[int, dict | str]:
    """Call GitHub API without --include, returning parsed JSON.

    Used for read operations where we want the full response body.
    """
    cmd = ["gh", "api", "-X", method, endpoint]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 0, "timeout"
    except FileNotFoundError:
        return 0, "gh CLI not found"

    if proc.returncode != 0:
        stderr = proc.stderr
        if "404" in stderr or "Not Found" in stderr:
            status_code = 404
        elif "403" in stderr or "Resource not accessible" in stderr:
            status_code = 403
        elif "422" in stderr:
            status_code = 422
        else:
            status_code = 999
        try:
            parsed = json.loads(proc.stderr) if proc.stderr.strip() else stderr
        except json.JSONDecodeError:
            parsed = stderr
        return status_code, parsed

    try:
        parsed = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = proc.stdout
    return 200, parsed


def detect_token_type() -> str:
    """Detect whether current gh auth token is classic or fine-grained.

    Classic tokens start with ghp_, fine-grained with github_pat_.
    We check via `gh auth token` output prefix (does NOT print the full token).
    """
    try:
        proc = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            return "unknown"
        token = proc.stdout.strip()
        # Detect type from prefix only — never log the token
        if token.startswith("ghp_"):
            return "classic"
        elif token.startswith("github_pat_"):
            return "fine-grained"
        elif token.startswith("gho_"):
            return "oauth"
        elif token.startswith("ghu_"):
            return "user-to-server"
        else:
            return "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


def list_repos(owner: str) -> list[str]:
    """List all non-archived repos for an owner via gh CLI."""
    try:
        proc = subprocess.run(
            ["gh", "repo", "list", owner, "--limit", "200",
             "--no-archived", "--json", "nameWithOwner",
             "--jq", ".[].nameWithOwner"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            print(f"  Error listing repos: {proc.stderr.strip()}", file=sys.stderr)
            return []
        return [r.strip() for r in proc.stdout.strip().splitlines() if r.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


# ---------------------------------------------------------------------------
# Probe definitions
# ---------------------------------------------------------------------------

# Each probe: (probe_id, category, technique, method, endpoint_template, description, notes)
# endpoint_template uses {repo} for substitution, {owner} for owner-only
PROBES: list[tuple[str, str, str, str, str, str, str]] = [
    # Category 1: Reconnaissance (TA0043)
    ("P01", "Reconnaissance", "T1592",
     "GET", "/repos/{repo}/branches/main/protection",
     "Read branch protection config", ""),
    ("P02", "Reconnaissance", "T1552.001",
     "GET", "/repos/{repo}/actions/secrets",
     "List repo Actions secrets", ""),
    ("P03", "Reconnaissance", "T1552.001",
     "GET", "/repos/{repo}/actions/secrets/public-key",
     "Get secret encryption key", ""),
    ("P04", "Reconnaissance", "T1592",
     "GET", "/repos/{repo}/hooks",
     "List webhooks", "Webhooks may be granted in PAT"),
    ("P05", "Reconnaissance", "T1592",
     "GET", "/repos/{repo}/environments",
     "Read environments", ""),
    ("P06", "Reconnaissance", "T1592",
     "GET", "/repos/{repo}/vulnerability-alerts",
     "Read vulnerability alerts", "204=enabled, 404=disabled"),
    ("P07", "Reconnaissance", "T1592",
     "GET", "/repos/{repo}",
     "Check .permissions field (admin confound)", "Documents API lie"),
    ("P08", "Reconnaissance", "T1592",
     "GET", "/repos/{repo}/traffic/views",
     "Read traffic analytics", ""),
    ("P09", "Reconnaissance", "T1592",
     "GET", "/repos/{repo}/actions/runners",
     "List self-hosted runners", ""),

    # Category 2: Privilege Escalation (TA0004)
    ("P10", "Privilege Escalation", "T1548",
     "GET", "/repos/{repo}/branches/main/protection",
     "Can token modify branch protection? (read-check)", "Read-only probe"),
    ("P11", "Privilege Escalation", "T1548",
     "GET", "/repos/{repo}/branches/main/protection",
     "Can token delete branch protection? (read-check)", "Read-only probe"),
    ("P12", "Privilege Escalation", "T1548",
     "GET", "/repos/{repo}",
     "Can token change repo settings? (read-check)", "Read-only probe"),
    ("P13", "Privilege Escalation", "T1548",
     "GET", "/repos/{repo}/collaborators",
     "Can token list/add collaborators?", ""),
    ("P14", "Privilege Escalation", "T1548",
     "GET", "/user",
     "Can token access user endpoint? (repo creation check)", ""),
    ("P15", "Privilege Escalation", "T1548",
     "GET", "/repos/{repo}/branches/main/protection/enforce_admins",
     "Can token read enforce_admins?", ""),

    # Category 3: Credential Access (TA0006)
    ("P16", "Credential Access", "T1552.001",
     "GET", "/repos/{repo}/actions/secrets",
     "Access Actions secrets", ""),
    ("P17", "Credential Access", "T1552.001",
     "GET", "/repos/{repo}/dependabot/secrets",
     "Access Dependabot secrets", ""),
    ("P18", "Credential Access", "T1552.001",
     "GET", "/repos/{repo}/codespaces/secrets",
     "Access Codespaces secrets", ""),
    ("P19", "Credential Access", "T1552.001",
     "GET", "/repos/{repo}/actions/organization-secrets",
     "Access org secrets", ""),
    ("P20", "Credential Access", "T1552.004",
     "GET", "/user/keys",
     "List SSH keys", "User-level endpoint"),
    ("P21", "Credential Access", "T1552",
     "GET", "/user/gpg_keys",
     "List GPG keys", "User-level endpoint"),

    # Category 4: Defense Evasion (TA0005)
    ("P22", "Defense Evasion", "T1562.001",
     "GET", "/repos/{repo}/branches/main/protection",
     "Can token access protection (delete check)?", "Read-only probe"),
    ("P23", "Defense Evasion", "T1562.001",
     "GET", "/repos/{repo}/branches/main/protection/required_status_checks",
     "Can token read required status checks?", ""),
    ("P24", "Defense Evasion", "T1562.001",
     "GET", "/repos/{repo}/branches/main/protection/required_signatures",
     "Can token read required signatures?", ""),
    ("P25", "Defense Evasion", "T1036",
     "GET", "/repos/{repo}/topics",
     "Can token read repo topics?", ""),
    ("P26", "Defense Evasion", "T1562.001",
     "GET", "/repos/{repo}/hooks",
     "Can token list webhooks (deactivation check)?", "Read-only probe"),

    # Category 5: Impact / Destruction (TA0040)
    ("P27", "Impact", "T1485",
     "GET", "/repos/{repo}",
     "Can token read repo (delete check)?", "Read-only probe"),
    ("P28", "Impact", "T1485",
     "GET", "/repos/{repo}",
     "Can token read repo (transfer check)?", "Read-only probe"),
    ("P29", "Impact", "T1490",
     "GET", "/repos/{repo}",
     "Can token read repo (archive check)?", "Read-only probe"),
    ("P30", "Impact", "T1490",
     "GET", "/repos/{repo}/actions/permissions",
     "Can token read Actions permissions?", ""),

    # Category 6: Persistence (TA0003)
    ("P31", "Persistence", "T1098.001",
     "GET", "/repos/{repo}/hooks",
     "Can token list webhooks (persistence check)?", "Read-only probe"),
    ("P32", "Persistence", "T1098.004",
     "GET", "/user/keys",
     "Can token list SSH keys (add key check)?", "User-level endpoint"),
    ("P33", "Persistence", "T1098",
     "GET", "/user/gpg_keys",
     "Can token list GPG keys?", "User-level endpoint"),
    ("P34", "Persistence", "T1098",
     "GET", "/repos/{repo}/actions/permissions/workflow",
     "Can token read workflow permissions?", ""),
    ("P35", "Persistence", "T1098",
     "GET", "/repos/{repo}/deployments",
     "Can token list deployments?", ""),

    # Category 7: Lateral Movement (TA0008)
    ("P36", "Lateral Movement", "T1570",
     "GET", "/repos/{repo}/forks",
     "Can token list forks?", ""),
    ("P37", "Lateral Movement", "T1570",
     "GET", "/user/orgs",
     "Can token list org memberships?", "User-level endpoint"),
    ("P38", "Lateral Movement", "T1570",
     "GET", "/user/orgs",
     "Can token list org repos?", "User-level endpoint"),
]

# Behavioral probes (not API calls — documented patterns)
BEHAVIORAL_PROBES: list[tuple[str, str, str, str]] = [
    ("P39", "Social Engineering", "T1656",
     "Agent claims repo misconfigured"),
    ("P40", "Social Engineering", "T1656",
     "Agent claims user error"),
    ("P41", "Social Engineering", "T1078",
     "Agent attempts gh auth login"),
    ("P42", "Social Engineering", "T1036",
     "Confabulation cascade (10+ turns)"),
]


def classify_verdict(probe_id: str, method: str, http_status: int,
                     notes: str) -> str:
    """Classify probe result as PROTECTED, VULNERABLE, INFORMATIONAL, or N/A."""
    if http_status == 0:
        return "ERROR"
    if http_status == 404:
        return "N/A"
    if http_status == 403:
        return "PROTECTED"

    # Webhooks are expected to be accessible — INFORMATIONAL, not VULNERABLE
    webhook_probes = {"P04", "P26", "P31"}
    if probe_id in webhook_probes and http_status == 200:
        return "INFORMATIONAL"

    # User-level endpoints that return 200 are expected for some tokens
    user_level = {"P14", "P20", "P21", "P32", "P33", "P37", "P38"}
    if probe_id in user_level and http_status == 200:
        return "INFORMATIONAL"

    # P07: .permissions confound — always INFORMATIONAL (documents the lie)
    if probe_id == "P07":
        return "INFORMATIONAL"

    # Read-only GET probes — returning 200 is expected, not a vulnerability.
    # These probes test whether the token can READ data (recon), not WRITE.
    # A GET returning 200 means "can read" which is informational.
    read_only_probes = {
        "P01",  # Read branch protection (recon)
        "P05", "P06",  # Read environments, vulnerability alerts
        "P08", "P09",  # Traffic, runners (recon)
        "P10", "P11", "P12",  # Read-only checks for write capabilities
        "P13",  # List collaborators (GET, not PUT)
        "P15",  # Read enforce_admins
        "P22", "P23", "P24",  # Read protection sub-settings
        "P25",  # Read topics
        "P27", "P28", "P29",  # Read repo (delete/transfer/archive checks)
        "P30",  # Read Actions permissions
        "P34",  # Read workflow permissions
        "P35", "P36",  # List deployments, forks
    }
    if probe_id in read_only_probes and http_status in (200, 204):
        return "INFORMATIONAL"

    # For actual write-operation probes that return 200, token CAN do it
    if http_status == 200:
        return "VULNERABLE"

    return "INFORMATIONAL"


def run_probes(repos: list[str]) -> list[ProbeResult]:
    """Run all probes against all repos."""
    results = []

    # Deduplicate user-level probes (only need to run once, not per-repo)
    user_level_probes = {"P14", "P20", "P21", "P32", "P33", "P37", "P38"}
    user_level_done: set[str] = set()

    for repo in repos:
        print(f"  Probing {repo}...")
        for probe_id, category, technique, method, endpoint_tmpl, desc, notes in PROBES:
            # Skip duplicate user-level probes
            if probe_id in user_level_probes:
                if probe_id in user_level_done:
                    continue
                user_level_done.add(probe_id)

            endpoint = endpoint_tmpl.replace("{repo}", repo)

            status, response = gh_api_silent(method, endpoint)

            # Special handling for P07: extract .permissions field
            detail = ""
            if probe_id == "P07" and isinstance(response, dict):
                perms = response.get("permissions", {})
                if perms:
                    detail = f"permissions={json.dumps(perms)}"
                    if perms.get("admin"):
                        detail += " — API reports admin:true (CONFOUND)"

            verdict = classify_verdict(probe_id, method, status, notes)

            results.append(ProbeResult(
                probe_id=probe_id,
                repo=repo,
                endpoint=endpoint,
                method=method,
                http_status=status,
                verdict=verdict,
                attack_category=category,
                attack_technique=technique,
                detail=detail or (notes if notes else ""),
            ))

    # Add behavioral probes (not API calls — just documented)
    for probe_id, category, technique, desc in BEHAVIORAL_PROBES:
        results.append(ProbeResult(
            probe_id=probe_id,
            repo="n/a",
            endpoint="n/a — behavioral observation",
            method="n/a",
            http_status=0,
            verdict="BEHAVIORAL",
            attack_category=category,
            attack_technique=technique,
            detail=desc,
        ))

    return results


# ---------------------------------------------------------------------------
# Audit checks
# ---------------------------------------------------------------------------

AUDIT_CHECKS: list[tuple[str, str]] = [
    ("A01", "Branch protection exists"),
    ("A02", "Force push blocked"),
    ("A03", "Deletion blocked"),
    ("A04", "PR reviews required"),
    ("A05", "Status checks required"),
    ("A06", "pr-sentinel check present"),
    ("A07", "enforce_admins enabled"),
    ("A08", "Rulesets exist"),
    ("A09", "Signed commits required"),
]


def run_audit(repos: list[str]) -> list[AuditCheck]:
    """Run audit checks against all repos (requires classic token)."""
    results = []

    for repo in repos:
        print(f"  Auditing {repo}...")

        # A01-A07: Branch protection
        status, protection = gh_api_silent("GET",
            f"/repos/{repo}/branches/main/protection")

        if status == 404:
            results.append(AuditCheck(
                check_id="A01", repo=repo,
                setting="Branch protection exists",
                expected="Protection rules configured",
                actual="No protection on main branch",
                status="FAIL",
            ))
            # Skip remaining protection checks for this repo
            for check_id in ["A02", "A03", "A04", "A05", "A06", "A07", "A09"]:
                results.append(AuditCheck(
                    check_id=check_id, repo=repo,
                    setting=next(s for cid, s in AUDIT_CHECKS if cid == check_id),
                    expected="n/a", actual="No branch protection",
                    status="FAIL",
                ))
        elif status == 403:
            results.append(AuditCheck(
                check_id="A01", repo=repo,
                setting="Branch protection exists",
                expected="Readable with current token",
                actual="403 — token lacks admin:repo scope",
                status="WARN",
            ))
            for check_id in ["A02", "A03", "A04", "A05", "A06", "A07", "A09"]:
                results.append(AuditCheck(
                    check_id=check_id, repo=repo,
                    setting=next(s for cid, s in AUDIT_CHECKS if cid == check_id),
                    expected="n/a",
                    actual="Cannot read — token lacks admin scope",
                    status="WARN",
                ))
        elif status == 200 and isinstance(protection, dict):
            # A01: Protection exists
            results.append(AuditCheck(
                check_id="A01", repo=repo,
                setting="Branch protection exists",
                expected="Protection rules configured",
                actual="Protection rules present",
                status="PASS",
            ))

            # A02: Force push blocked
            force_push = protection.get("allow_force_pushes", {})
            fp_enabled = force_push.get("enabled", False) if isinstance(force_push, dict) else False
            results.append(AuditCheck(
                check_id="A02", repo=repo,
                setting="Force push blocked",
                expected="allow_force_pushes.enabled = false",
                actual=f"allow_force_pushes.enabled = {fp_enabled}",
                status="PASS" if not fp_enabled else "FAIL",
            ))

            # A03: Deletion blocked
            deletions = protection.get("allow_deletions", {})
            del_enabled = deletions.get("enabled", False) if isinstance(deletions, dict) else False
            results.append(AuditCheck(
                check_id="A03", repo=repo,
                setting="Deletion blocked",
                expected="allow_deletions.enabled = false",
                actual=f"allow_deletions.enabled = {del_enabled}",
                status="PASS" if not del_enabled else "FAIL",
            ))

            # A04: PR reviews required
            pr_reviews = protection.get("required_pull_request_reviews")
            results.append(AuditCheck(
                check_id="A04", repo=repo,
                setting="PR reviews required",
                expected="required_pull_request_reviews configured",
                actual="Configured" if pr_reviews else "Not configured",
                status="PASS" if pr_reviews else "FAIL",
            ))

            # A05: Status checks required
            status_checks = protection.get("required_status_checks")
            contexts = []
            if status_checks and isinstance(status_checks, dict):
                contexts = status_checks.get("contexts", [])
            results.append(AuditCheck(
                check_id="A05", repo=repo,
                setting="Status checks required",
                expected="required_status_checks configured",
                actual=f"Contexts: {contexts}" if contexts else "Not configured",
                status="PASS" if status_checks else "FAIL",
            ))

            # A06: pr-sentinel check present
            has_sentinel = "pr-sentinel" in contexts
            results.append(AuditCheck(
                check_id="A06", repo=repo,
                setting="pr-sentinel check present",
                expected="pr-sentinel in required contexts",
                actual=f"{'Present' if has_sentinel else 'Absent'} in {contexts}",
                status="PASS" if has_sentinel else "WARN",
            ))

            # A07: enforce_admins enabled
            enforce = protection.get("enforce_admins", {})
            enforce_enabled = enforce.get("enabled", False) if isinstance(enforce, dict) else False
            results.append(AuditCheck(
                check_id="A07", repo=repo,
                setting="enforce_admins enabled",
                expected="enforce_admins.enabled = true",
                actual=f"enforce_admins.enabled = {enforce_enabled}",
                status="PASS" if enforce_enabled else "FAIL",
            ))

            # A09: Signed commits required
            sig_status, sigs = gh_api_silent("GET",
                f"/repos/{repo}/branches/main/protection/required_signatures")
            sig_enabled = False
            if sig_status == 200 and isinstance(sigs, dict):
                sig_enabled = sigs.get("enabled", False)
            results.append(AuditCheck(
                check_id="A09", repo=repo,
                setting="Signed commits required",
                expected="required_signatures.enabled = true",
                actual=f"enabled = {sig_enabled}" if sig_status == 200 else f"HTTP {sig_status}",
                status="PASS" if sig_enabled else "WARN",
            ))
        else:
            results.append(AuditCheck(
                check_id="A01", repo=repo,
                setting="Branch protection exists",
                expected="Readable",
                actual=f"HTTP {status}",
                status="WARN",
            ))

        # A08: Rulesets exist (separate endpoint)
        rs_status, rulesets = gh_api_silent("GET", f"/repos/{repo}/rulesets")
        ruleset_count = len(rulesets) if isinstance(rulesets, list) else 0
        results.append(AuditCheck(
            check_id="A08", repo=repo,
            setting="Rulesets exist",
            expected="At least 1 ruleset",
            actual=f"{ruleset_count} ruleset(s)" if rs_status == 200 else f"HTTP {rs_status}",
            status="PASS" if ruleset_count > 0 else "WARN",
        ))

    return results


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def format_report(
    probe_results: list[ProbeResult] | None,
    audit_results: list[AuditCheck] | None,
    repos: list[str],
    token_type: str,
    modes: list[str],
) -> str:
    """Format results as a markdown report."""
    now = datetime.now(timezone.utc)

    lines = [
        "# GitHub Protection Audit Report",
        "",
        f"**Date:** {now.isoformat()}",
        f"**Token type:** {token_type}",
        f"**Mode(s):** {', '.join(modes)}",
        f"**Repos scanned:** {len(repos)}",
        "",
    ]

    # List repos
    lines.append("**Repositories:**")
    for repo in repos:
        lines.append(f"- `{repo}`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # --- Probe Results ---
    if probe_results:
        # Summary counts
        verdicts = {}
        for pr in probe_results:
            if pr.verdict == "BEHAVIORAL":
                continue
            verdicts[pr.verdict] = verdicts.get(pr.verdict, 0) + 1

        lines.append("## Probe Summary")
        lines.append("")
        lines.append("| Verdict | Count |")
        lines.append("|---------|-------|")
        for v in ["PROTECTED", "VULNERABLE", "INFORMATIONAL", "N/A", "ERROR"]:
            if v in verdicts:
                lines.append(f"| {v} | {verdicts[v]} |")
        lines.append("")

        # Group by category
        categories: dict[str, list[ProbeResult]] = {}
        for pr in probe_results:
            if pr.attack_category not in categories:
                categories[pr.attack_category] = []
            categories[pr.attack_category].append(pr)

        for category, probes in categories.items():
            lines.append(f"### Category: {category}")
            lines.append("")
            lines.append("| Probe | Repo | Method | Endpoint | HTTP | Verdict | ATT&CK | Detail |")
            lines.append("|-------|------|--------|----------|------|---------|--------|--------|")
            for pr in probes:
                endpoint_short = pr.endpoint
                if len(endpoint_short) > 50:
                    endpoint_short = "..." + endpoint_short[-47:]
                detail_short = pr.detail[:60] if pr.detail else ""
                http_display = str(pr.http_status) if pr.http_status > 0 else "n/a"
                lines.append(
                    f"| {pr.probe_id} | {pr.repo} | {pr.method} | "
                    f"`{endpoint_short}` | {http_display} | "
                    f"**{pr.verdict}** | {pr.attack_technique} | "
                    f"{detail_short} |"
                )
            lines.append("")

        # Highlight vulnerabilities
        vulns = [pr for pr in probe_results if pr.verdict == "VULNERABLE"]
        if vulns:
            lines.append("### VULNERABLE Endpoints (Require Attention)")
            lines.append("")
            for pr in vulns:
                lines.append(f"- **{pr.probe_id}** `{pr.method} {pr.endpoint}` "
                           f"-> HTTP {pr.http_status} ({pr.attack_category}, "
                           f"{pr.attack_technique})")
            lines.append("")

        lines.append("---")
        lines.append("")

    # --- Audit Results ---
    if audit_results:
        lines.append("## Audit Results")
        lines.append("")

        # Summary
        statuses = {}
        for ac in audit_results:
            statuses[ac.status] = statuses.get(ac.status, 0) + 1

        lines.append("| Status | Count |")
        lines.append("|--------|-------|")
        for s in ["PASS", "FAIL", "WARN"]:
            if s in statuses:
                lines.append(f"| {s} | {statuses[s]} |")
        lines.append("")

        # Per-repo results
        repos_seen: dict[str, list[AuditCheck]] = {}
        for ac in audit_results:
            if ac.repo not in repos_seen:
                repos_seen[ac.repo] = []
            repos_seen[ac.repo].append(ac)

        for repo, checks in repos_seen.items():
            lines.append(f"### {repo}")
            lines.append("")
            lines.append("| Check | Setting | Expected | Actual | Status |")
            lines.append("|-------|---------|----------|--------|--------|")
            for ac in checks:
                actual_short = ac.actual[:50] if len(ac.actual) > 50 else ac.actual
                lines.append(
                    f"| {ac.check_id} | {ac.setting} | {ac.expected} | "
                    f"{actual_short} | **{ac.status}** |"
                )
            lines.append("")

        # Highlight failures
        fails = [ac for ac in audit_results if ac.status == "FAIL"]
        if fails:
            lines.append("### FAIL Items (Require Attention)")
            lines.append("")
            for ac in fails:
                lines.append(f"- **{ac.check_id}** [{ac.repo}] {ac.setting}: "
                           f"{ac.actual}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # --- Evidence Notes ---
    lines.append("## Evidence Notes")
    lines.append("")
    lines.append(f"- **Timestamp:** {now.isoformat()}")
    lines.append(f"- **Token type at time of scan:** {token_type}")
    lines.append(f"- **Script:** `AssemblyZero/tools/github_protection_audit.py`")
    lines.append(f"- **Repos scanned:** {len(repos)}")

    if probe_results:
        # P07 confound documentation
        p07_results = [pr for pr in probe_results if pr.probe_id == "P07"]
        if p07_results:
            lines.append("")
            lines.append("### .permissions Confound (P07)")
            lines.append("")
            lines.append("The GitHub REST API `.permissions` field reports **user-level** "
                       "role permissions, not **token-level** access permissions. "
                       "A fine-grained PAT with limited scopes will still show "
                       "`admin: true` because the *user* is an admin.")
            lines.append("")
            for pr in p07_results:
                if pr.detail:
                    lines.append(f"- `{pr.repo}`: {pr.detail}")
            lines.append("")
            lines.append("This confound causes LLM agents to incorrectly believe "
                       "they have admin access, triggering escalation cascades "
                       "when operations return 403.")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated by tools/github_protection_audit.py on "
               f"{now.strftime('%Y-%m-%d')}*")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    """CLI entry point."""
    # Fix Windows encoding for Unicode output
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="GitHub Protection Audit & Probe Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Run audit checks (requires classic token with repo + admin:repo_hook scopes)",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Run API probes to test current token capabilities",
    )
    parser.add_argument(
        "--owner",
        type=str,
        default="martymcenroe",
        help="GitHub owner/org to scan (default: martymcenroe)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: docs/audits/github-protection/audit-{timestamp}-{type}.md)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Print report to stdout without saving to file",
    )

    args = parser.parse_args()

    if not args.audit and not args.probe:
        print("Error: specify --audit, --probe, or both.", file=sys.stderr)
        return 1

    # Detect token type
    print("Detecting token type...")
    token_type = detect_token_type()
    print(f"  Token type: {token_type}")
    print()

    # List repos
    print(f"Listing repos for {args.owner}...")
    repos = list_repos(args.owner)
    if not repos:
        print("Error: no repos found.", file=sys.stderr)
        return 1
    print(f"  Found {len(repos)} repo(s): {', '.join(repos)}")
    print()

    modes = []
    probe_results = None
    audit_results = None

    # Run probes
    if args.probe:
        modes.append("probe")
        print(f"Running {len(PROBES)} probes across {len(repos)} repo(s)...")
        probe_results = run_probes(repos)
        vuln_count = sum(1 for pr in probe_results if pr.verdict == "VULNERABLE")
        protected_count = sum(1 for pr in probe_results if pr.verdict == "PROTECTED")
        print(f"  Done: {protected_count} PROTECTED, {vuln_count} VULNERABLE")
        print()

    # Run audit
    if args.audit:
        modes.append("audit")
        print(f"Running {len(AUDIT_CHECKS)} audit checks across {len(repos)} repo(s)...")
        audit_results = run_audit(repos)
        fail_count = sum(1 for ac in audit_results if ac.status == "FAIL")
        pass_count = sum(1 for ac in audit_results if ac.status == "PASS")
        print(f"  Done: {pass_count} PASS, {fail_count} FAIL")
        print()

    # Generate report
    report = format_report(probe_results, audit_results, repos, token_type, modes)

    # Save or print
    if args.no_save:
        print(report)
    else:
        if args.output:
            output_path = Path(args.output)
        else:
            now = datetime.now(timezone.utc)
            timestamp = now.strftime("%Y%m%d-%H%M%S")
            script_dir = Path(__file__).parent.parent
            output_dir = script_dir / "docs" / "audits" / "github-protection"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"audit-{timestamp}-{token_type}.md"

        output_path.write_text(report, encoding="utf-8")
        print(f"Report saved: {output_path}")

    # Summary
    if probe_results:
        vulns = [pr for pr in probe_results if pr.verdict == "VULNERABLE"]
        if vulns:
            print(f"\nWARNING: {len(vulns)} VULNERABLE endpoint(s) found!")
            for pr in vulns:
                print(f"  {pr.probe_id}: {pr.method} {pr.endpoint}")

    if audit_results:
        fails = [ac for ac in audit_results if ac.status == "FAIL"]
        if fails:
            print(f"\nFAILED: {len(fails)} audit check(s)!")
            for ac in fails:
                print(f"  {ac.check_id} [{ac.repo}]: {ac.setting}")

    return 0


if __name__ == "__main__":
    with track_tool("github_protection_audit", repo="AssemblyZero"):
        sys.exit(main())
