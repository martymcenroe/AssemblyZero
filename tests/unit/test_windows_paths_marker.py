"""The windows-latest job must not pass by selecting nothing (#2431).

The Windows-only stop paths are covered by tests marked `windows_paths` and run
by a `windows-latest` CI job that selects exactly that marker. If the marker is
renamed, unregistered, or falls off the file, the job selects zero tests and
goes green -- which is the "verified by nobody" state this issue is about,
wearing a green tick.

Deliberately UNMARKED and not platform-skipped: these run on the ubuntu job
that fires on every PR, so a rename is caught by the job that always runs
rather than by the one whose emptiness is the defect.

The assertions about `ci.yml` itself land with the workflow job, in the
separate change that adds it -- a fine-grained PAT cannot push a workflow file
(ADR 0216), so the job arrives by the Contents API and its guards arrive with
it. Asserting here that a job exists which this branch cannot create would be
a test written to fail.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKER = "windows_paths"


class TestTheMarkerIsWiredEndToEnd:
    def test_it_is_registered_in_pyproject(self):
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        markers = data["tool"]["pytest"]["ini_options"]["markers"]
        assert any(m.startswith(f"{MARKER}:") for m in markers), markers

    def test_at_least_one_test_carries_the_marker(self):
        """Collection is asked of pytest itself rather than grepped for, so a
        marker applied in a way this file did not anticipate still counts."""
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest", "tests/unit/",
                "-m", MARKER, "--collect-only", "-q", "--no-header",
                "-p", "no:cacheprovider",
            ],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        combined = (result.stdout or "") + (result.stderr or "")
        assert "no tests ran" not in combined.lower(), combined[-2000:]
        assert result.returncode == 0, combined[-2000:]
