```python
"""Cross-project drift detection via assemblyzero-harvest.py.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

import os
import subprocess

from assemblyzero.workflows.janitor.state import Finding, ProbeResult


def probe_harvest(repo_root: str) -> ProbeResult:
    """Run assemblyzero-harvest.py and parse output for cross-project drift.

    Shells out to the harvest script and parses its stdout.
    If the harvest script is not found, returns a single info-level finding.
    All findings from harvest are unfixable (require human judgment).
    """
    script_path = find_harvest_script(repo_root)
    if script_path is None:
        return ProbeResult(
            probe="harvest",
            status="findings",
            findings=[
                Finding(
                    probe="harvest",
                    category="harvest_missing",
                    message="assemblyzero-harvest.py not found in repository",
                    severity="info",
                    fixable=False,
                )
            ],
        )

    try:
        result = subprocess.run(
            ["python", script_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        findings = parse_harvest_output(result.stdout)
        if findings:
            return ProbeResult(
                probe="harvest", status="findings", findings=findings
            )
        return ProbeResult(probe="harvest", status="ok")
    except subprocess.TimeoutExpired:
        return ProbeResult(
            probe="harvest",
            status="error",
            error_message="Harvest script timed out after 120 seconds",
        )
    except Exception as e:
        return ProbeResult(
            probe="harvest",
            status="error",
            error_message=f"{type(e).__name__}: {e}",
        )


def find_harvest_script(repo_root: str) -> str | None:
    """Locate the assemblyzero-harvest.py script.

    Searches in repo_root and tools/ directory.
    Returns absolute path or None.
    """
    candidates = [
        os.path.join(repo_root, "assemblyzero-harvest.py"),
        os.path.join(repo_root, "tools", "assemblyzero-harvest.py"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def parse_harvest_output(output: str) -> list[Finding]:
    """Parse harvest script stdout into structured findings.

    Looks for lines starting with 'DRIFT:' and creates findings for each.
    Lines starting with 'OK:' are ignored.
    """
    findings: list[Finding] = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("DRIFT:"):
            findings.append(
                Finding(
                    probe="harvest",
                    category="cross_project_drift",
                    message=line,
                    severity="warning",
                    fixable=False,
                )
            )
    return findings
```
