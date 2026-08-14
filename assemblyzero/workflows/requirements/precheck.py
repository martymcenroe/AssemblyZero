"""Call the N0c requirements-consistency gate without a roll (#2221).

The gate lives in ``nodes/analyze_requirements.py`` and runs as node 3 of the
LLD workflow, so the only way to ask it a question used to be a launch. On
boostgauge #7 that meant five operator rulings each verified by the next roll:
edit the issue text, launch, wait for the codebase-analysis node, and learn
three minutes in whether the edit introduced a fresh contradiction. Every
defect cost a full iteration to discover.

This module gives the same gate a second caller. It **imports**
``analyze_requirements``; it does not reimplement it. A separate
implementation would drift, and a clean result from a drifted checker is false
confidence, which is worse than no pre-check at all.

Fail-open does not carry over
-----------------------------

In a roll the gate fails open by design: a provider storm must not brick a
launch, so an analysis that cannot run prints a warning and the workflow
proceeds to drafting. Standalone, a human explicitly asked for the check, so
an analysis that cannot run is an error rather than a pass.

The node signals every one of those outcomes the same way — an empty state
update — so a caller cannot tell "consistent" from "skipped" by return value
alone. This module therefore requires *positive* evidence of a clean verdict,
the node's own ``CLEAN_MARKER`` line, and treats its absence as failure. Every
unknown resolves to a nonzero exit; nothing resolves to a silent pass.

Side effects are the gate's own
-------------------------------

On conflict the node files must-resolve issues on the target repo and records
prompt telemetry, exactly as it does in a roll. That is the imported
behavior and it is not suppressed here: the conflicts are real, and a blocked
launcher is the correct state for an issue whose text still contradicts
itself.
"""

from __future__ import annotations

import io
import json
import subprocess
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from assemblyzero.workflows.requirements.nodes.analyze_requirements import (
    analyze_requirements,
)

#: Exit code: the gate ran and found no contradictions.
EXIT_CLEAN = 0
#: Exit code: the gate ran and found at least one contradiction.
EXIT_CONFLICT = 1
#: Exit code: the check could not run. Nothing was verified.
EXIT_ERROR = 2

#: The sentence the node prints when the analysis ran and found nothing. The
#: node returns an empty state update for a clean verdict AND for every
#: fail-open skip, so this line is the only positive evidence a caller has.
#: ``tests/unit/test_check_requirements.py`` drives the live node and asserts
#: this string still appears, so a wording change fails the suite rather than
#: silently turning every clean result into an error.
CLEAN_MARKER = "Requirements internally consistent."

#: Matches ``--drafter`` in ``tools/run_requirements_workflow.py``.
#:
#: It does NOT match what a roll's gate asks, despite what this comment claimed
#: until #2375. A roll reaches the requirements graph through the orchestrator's
#: lld stage, whose ``StageConfig`` has carried ``drafter="gemini:3.1-pro"``
#: since #1434, and nothing on the roll path overrides it -- ``load_config``
#: merges only ``skip_existing_*``, ``gates`` and ``mock_mode``. Measured
#: 2026-08-14.
#:
#: So this pre-check predicts the roll's gate on every dimension except the
#: model, and the model is the dimension #2375 found mattered most: sonnet timed
#: out three consecutive times on a document opus answered on its first attempt.
#: Which model the two paths should share is a decision, tracked in #2384.
DEFAULT_DRAFTER = "claude:sonnet"

_GATE_PATH = "assemblyzero/workflows/requirements/nodes/analyze_requirements.py"
_FILING_FAILED_MARKER = "must-resolve filing failed"


class PrecheckError(RuntimeError):
    """The pre-check could not reach a verdict. Never a degraded result."""


@dataclass
class PrecheckResult:
    """Outcome of one gate call.

    Attributes:
        status: ``clean``, ``conflict`` or ``error``.
        detail: The verbatim conflict message, or the reason no verdict came.
        node_output: Everything the gate printed, captured.
    """

    status: str
    detail: str
    node_output: str

    @property
    def exit_code(self) -> int:
        """Exit code for this outcome. Only ``clean`` is zero."""
        if self.status == "clean":
            return EXIT_CLEAN
        if self.status == "conflict":
            return EXIT_CONFLICT
        return EXIT_ERROR

    @property
    def filing_failed(self) -> bool:
        """True when the gate reported that must-resolve filing failed."""
        return _FILING_FAILED_MARKER in self.node_output


class _Tee(io.TextIOBase):
    """Write to a capture buffer and, optionally, a live stream."""

    def __init__(self, capture: io.StringIO, live: TextIO | None) -> None:
        self._capture = capture
        self._live = live

    def write(self, text: str) -> int:
        self._capture.write(text)
        if self._live is not None:
            self._live.write(text)
        return len(text)

    def flush(self) -> None:
        if self._live is not None:
            self._live.flush()


def fetch_issue(repo: Path, issue_number: int, timeout: int = 60) -> tuple[str, str]:
    """Read an issue's title and body via ``gh``, from the target repo.

    Args:
        repo: Target repository checkout; supplies the gh CLI's repo context.
        issue_number: Issue to read.
        timeout: Seconds to wait for gh.

    Returns:
        ``(title, body)``.

    Raises:
        PrecheckError: gh is missing, failed, timed out, or returned something
            that is not an issue payload. Per standard 0028 a read that cannot
            be trusted raises rather than returning a degraded value.
    """
    if not repo.is_dir():
        raise PrecheckError(f"--repo is not a directory: {repo}")

    try:
        proc = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--json", "title,body"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            cwd=str(repo),
        )
    except FileNotFoundError as exc:
        raise PrecheckError(
            "gh CLI not found. Install it from https://cli.github.com/"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise PrecheckError(
            f"gh issue view timed out after {timeout}s reading #{issue_number}"
        ) from exc

    if proc.returncode != 0:
        stderr = proc.stderr.strip() or "no stderr"
        raise PrecheckError(
            f"gh issue view #{issue_number} failed in {repo}: {stderr}"
        )

    try:
        payload = json.loads(proc.stdout)
    except ValueError as exc:
        excerpt = proc.stdout.strip()[:200]
        raise PrecheckError(
            f"gh returned output that is not JSON for #{issue_number}: {excerpt!r}"
        ) from exc

    if not isinstance(payload, dict) or "body" not in payload:
        raise PrecheckError(
            f"gh returned no issue body for #{issue_number}; got keys "
            f"{sorted(payload) if isinstance(payload, dict) else type(payload).__name__}"
        )

    return str(payload.get("title") or ""), str(payload.get("body") or "")


def _explain_missing_verdict(output: str) -> str:
    """Name why the gate returned without a verdict, from what it printed."""
    warnings = [line.strip() for line in output.splitlines() if "WARNING" in line]
    if warnings:
        return " / ".join(warnings)
    return (
        "the gate returned without reporting a conflict and without printing "
        f"{CLEAN_MARKER!r}, so no verdict was reached"
    )


def run_gate(
    repo: Path,
    issue_number: int,
    issue_title: str,
    issue_body: str,
    *,
    drafter: str = DEFAULT_DRAFTER,
    echo_stream: TextIO | None = None,
) -> PrecheckResult:
    """Run the imported N0c gate against one issue's text.

    Args:
        repo: Target repository; the gate files must-resolve issues here.
        issue_number: Issue under analysis.
        issue_title: Issue title.
        issue_body: Issue body. The whole document is the gate's input.
        drafter: Provider spec for the analysis call.
        echo_stream: Stream to mirror the gate's output to while it runs.

    Returns:
        The verdict.

    Raises:
        PrecheckError: The body is empty, or the gate raised.
    """
    if not issue_body.strip():
        raise PrecheckError(
            f"issue #{issue_number} has an empty body; there is nothing to analyze"
        )

    # config_mock_mode is deliberately absent: the node returns early on it,
    # which standalone would be an unverified pass wearing a clean exit code.
    state: dict[str, Any] = {
        "issue_title": issue_title,
        "issue_body": issue_body,
        "issue_number": issue_number,
        "target_repo": str(repo),
        "config_drafter": drafter,
        # #2290: this run's failure is reported by its own exit code and
        # report. Writing a roll-scoped unverified record here would leave a
        # line in the ledger that mislabels whichever roll happens to run next.
        "standalone_precheck": True,
    }

    capture = io.StringIO()
    try:
        with redirect_stdout(_Tee(capture, echo_stream)):
            update = analyze_requirements(state)
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        raise PrecheckError(
            f"the gate raised {type(exc).__name__}: {exc}"
        ) from exc

    output = capture.getvalue()
    conflict = str((update or {}).get("error_message") or "")

    if conflict:
        return PrecheckResult("conflict", conflict, output)
    if CLEAN_MARKER in output:
        return PrecheckResult("clean", "", output)
    return PrecheckResult("error", _explain_missing_verdict(output), output)


def render_report(
    result: PrecheckResult,
    repo: Path,
    issue_number: int,
    drafter: str,
) -> str:
    """Render the operator-facing report for one verdict."""
    rule = "=" * 70
    lines = [
        rule,
        f"Requirements pre-check -- {repo.name} #{issue_number}",
        rule,
        f"Gate:    {_GATE_PATH}",
        f"Drafter: {drafter}",
        "",
    ]

    if result.status == "clean":
        lines += [
            "CLEAN -- the gate found no internal contradictions.",
            "",
            "Verified: the issue's behavior text, acceptance criteria and test",
            "  plan were read as one document, and no two statements were found",
            "  to specify different outcomes for the same situation.",
            "Not verified: whether any requirement is correct, complete, or",
            "  implementable. This gate finds contradictions; it does not rule",
            "  on content. The roll runs it again and remains authoritative.",
        ]
    elif result.status == "conflict":
        lines += [
            "CONFLICT -- the gate's message follows verbatim:",
            "",
            result.detail,
            "",
        ]
        if result.filing_failed:
            lines.append(
                "The gate could not file must-resolve issues (see its output "
                "above); the conflicts stand regardless."
            )
        else:
            lines.append(
                f"Must-resolve issues were filed on {repo.name}, exactly as a "
                "roll would file them."
            )
        lines.append(
            "Rule on the text, edit the issue, and run this pre-check again."
        )
    else:
        lines += [
            "ERROR -- no verdict. Nothing about this issue was verified.",
            "",
            f"Reason: {result.detail}",
            "",
            "In a roll this is a warning and the workflow proceeds, because the",
            "  gate fails open by design so a provider storm cannot brick a",
            "  launch. Standalone it is an error: you asked for the check and it",
            "  did not run, so a clean exit here would be a lie.",
        ]

    lines += ["", rule]
    return "\n".join(lines) + "\n"
