

```python
#!/usr/bin/env python3
"""Pytest wrapper that enforces skipped test auditing.

Issue #225: Hard gate wrapper for skipped test enforcement.

Usage:
    python tools/test-gate.py [pytest-args...] [--audit-file PATH] [--strict] [--skip-gate-bypass "reason"]

Examples:
    python tools/test-gate.py tests/unit/ -v --tb=short
    python tools/test-gate.py tests/ --audit-file .skip-audit.md
    python tools/test-gate.py tests/ --skip-gate-bypass "Emergency hotfix for #500"
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure the project root is on sys.path so `tools.test_gate` resolves
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.test_gate.auditor import find_audit_block, validate_audit
from tools.test_gate.parser import (
    detect_critical_tests,
    ensure_verbose_flag,
    parse_skipped_tests,
    run_pytest,
)


def _parse_gate_args(
    args: list[str],
) -> tuple[list[str], Path | None, bool, str | None]:
    """Separate gate-specific flags from pytest args.

    Returns (pytest_args, audit_file, strict, bypass_reason).
    """
    pytest_args: list[str] = []
    audit_file: Path | None = None
    strict: bool = False
    bypass_reason: str | None = None

    i = 0
    while i < len(args):
        arg = args[i]

        if arg == "--audit-file":
            if i + 1 < len(args):
                audit_file = Path(args[i + 1])
                i += 2
                continue
            else:
                print("ERROR: --audit-file requires a path argument", file=sys.stderr)
                sys.exit(2)

        elif arg == "--strict":
            strict = True
            i += 1
            continue

        elif arg == "--skip-gate-bypass":
            if i + 1 < len(args):
                bypass_reason = args[i + 1]
                i += 2
                continue
            else:
                print(
                    "ERROR: --skip-gate-bypass requires a justification string",
                    file=sys.stderr,
                )
                sys.exit(2)

        pytest_args.append(arg)
        i += 1

    return (pytest_args, audit_file, strict, bypass_reason)


def main(args: list[str] | None = None) -> int:
    """Main entry point - wraps pytest and enforces skip audit gate."""
    if args is None:
        args = sys.argv[1:]

    pytest_args, audit_file, strict, bypass_reason = _parse_gate_args(list(args))

    # Validate bypass reason if provided
    if bypass_reason is not None:
        if not bypass_reason.strip():
            print(
                "ERROR: --skip-gate-bypass requires a non-empty justification string",
                file=sys.stderr,
            )
            return 2

    # Ensure verbose flag for skip detection
    pytest_args = ensure_verbose_flag(pytest_args)

    # Run pytest
    exit_code, stdout, stderr = run_pytest(pytest_args)

    # Print pytest output through
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)

    # Parse skipped tests
    skipped = parse_skipped_tests(stdout)
    skipped = detect_critical_tests(skipped)

    # If no skips, return pytest exit code directly
    if not skipped:
        return exit_code

    # Handle bypass
    if bypass_reason is not None:
        timestamp = datetime.now(timezone.utc).isoformat()
        print(
            f"\nWARNING: Test gate bypassed at {timestamp}",
            file=sys.stderr,
        )
        print(
            f"WARNING: Bypass reason: {bypass_reason}",
            file=sys.stderr,
        )
        print(
            f"WARNING: {len(skipped)} skipped test(s) were NOT audited",
            file=sys.stderr,
        )
        return exit_code

    # Find audit block
    audit = find_audit_block(stdout, audit_file=audit_file)

    if audit is None:
        print("\n" + "=" * 60, file=sys.stderr)
        print("TEST GATE FAILED: No SKIPPED TEST AUDIT block found", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(
            f"\n{len(skipped)} skipped test(s) require an audit block.",
            file=sys.stderr,
        )
        print(
            "\nCreate a .skip-audit.md file with the following format:",
            file=sys.stderr,
        )
        print("", file=sys.stderr)
        print("  <!-- SKIPPED TEST AUDIT -->", file=sys.stderr)
        print(
            "  | Test | Status | Justification | Owner | Expires |",
            file=sys.stderr,
        )
        print(
            "  |------|--------|---------------|-------|---------|",
            file=sys.stderr,
        )
        for test in skipped:
            print(
                f"  | {test['name']} | VERIFIED | TODO | TODO | |",
                file=sys.stderr,
            )
        print("  <!-- END SKIPPED TEST AUDIT -->", file=sys.stderr)
        print(
            "\nOr use --skip-gate-bypass \"reason\" for emergencies.",
            file=sys.stderr,
        )
        return 1

    # Validate audit
    unaudited, unverified = validate_audit(skipped, audit)

    if unaudited:
        print("\n" + "=" * 60, file=sys.stderr)
        print("TEST GATE FAILED: Unaudited skipped tests", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(
            f"\n{len(unaudited)} skipped test(s) have no matching audit entry:\n",
            file=sys.stderr,
        )
        for test in unaudited:
            critical_tag = " [CRITICAL]" if test["is_critical"] else ""
            print(
                f"  ✗ {test['name']}{critical_tag}",
                file=sys.stderr,
            )
            print(f"    Reason: {test['reason']}", file=sys.stderr)
        print(
            "\nAdd entries to your audit block for these tests.",
            file=sys.stderr,
        )
        return 1

    if unverified:
        print("\n" + "=" * 60, file=sys.stderr)
        print(
            "TEST GATE FAILED: Unverified critical skipped tests",
            file=sys.stderr,
        )
        print("=" * 60, file=sys.stderr)
        print(
            f"\n{len(unverified)} critical test(s) have UNVERIFIED status:\n",
            file=sys.stderr,
        )
        for test in unverified:
            print(f"  ✗ {test['name']} [CRITICAL]", file=sys.stderr)
            print(f"    Reason: {test['reason']}", file=sys.stderr)
        print(
            "\nChange status to VERIFIED or EXPECTED after review.",
            file=sys.stderr,
        )
        return 1

    # Gate passed
    print(f"\n✓ Test gate passed: {len(skipped)} skip(s) audited", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
```
