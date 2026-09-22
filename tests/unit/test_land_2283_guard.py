"""The staleness guard in tools/land_2283_ci_tiers.py (#2283).

That script embeds a copy of `.github/workflows/ci.yml` and lands it through the
Contents API, which replaces the file wholesale. The embed therefore ages against
main, and it did: it sat unlanded for five weeks while main gained a
`concurrency:` block and an action bump. Landing it then would have reverted
both, the concurrency block being an active Actions-cost measure, and nothing in
the flow would have said so.

`would_drop` is what says so. These tests are how it is verified, because the
script itself cannot be run without decrypting the classic PAT.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "land_2283_ci_tiers.py"


def _module():
    spec = importlib.util.spec_from_file_location("land_2283_ci_tiers", SCRIPT)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot load {SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _module()


def test_identical_content_drops_nothing():
    same = b"name: CI\njobs:\n  test:\n"
    assert mod.would_drop(same, same) == []


def test_a_line_on_main_that_the_embed_lacks_is_reported():
    remote = b"name: CI\nconcurrency:\n  cancel-in-progress: true\n"
    local = b"name: CI\n"
    assert mod.would_drop(remote, local) == [
        "concurrency:",
        "  cancel-in-progress: true",
    ]


def test_intended_removals_are_not_reported():
    """The lines this change removes on purpose must not trip the guard."""
    remote = "\n".join(sorted(mod.INTENDED_REMOVALS)).encode("utf-8")
    assert mod.would_drop(remote, b"name: CI\n") == []


def test_blank_lines_are_ignored():
    remote = b"name: CI\n\n\n   \n"
    assert mod.would_drop(remote, b"name: CI\n") == []


def test_reordering_alone_does_not_trip_it():
    """Line sets, not a diff -- moving a step must not read as dropping it."""
    remote = b"alpha\nbeta\ngamma\n"
    local = b"gamma\nalpha\nbeta\n"
    assert mod.would_drop(remote, local) == []


def test_the_actual_regression_this_guard_exists_for():
    """The pre-refresh embed against the main it would have reverted.

    Reproduces the real case: main carried `concurrency:` and
    `actions/setup-python@v7`; the embed carried neither and would have
    replaced the file wholesale.
    """
    remote = (
        b"name: CI\n"
        b"concurrency:\n"
        b"  group: ${{ github.workflow }}-${{ github.ref }}\n"
        b"  cancel-in-progress: true\n"
        b"      - name: Set up Python\n"
        b"        uses: actions/setup-python@v7\n"
    )
    stale_embed = (
        b"name: CI\n"
        b"      - name: Set up Python\n"
        b"        uses: actions/setup-python@v5\n"
    )
    dropped = mod.would_drop(remote, stale_embed)

    assert "concurrency:" in dropped
    assert "        uses: actions/setup-python@v7" in dropped


def test_the_shipped_embed_drops_nothing_from_the_repos_own_workflow():
    """The embed must never be behind the `ci.yml` in this checkout.

    Deliberately NOT an equality check. The embed is ahead of `ci.yml` by the
    tier steps until the operator runs the script, and equal to it afterwards;
    an equality assertion would fail for exactly as long as the change is
    pending, which is when it most needs to be green.

    What must hold in both states is the guard's own property: the embed drops
    nothing the repo's workflow already has. That catches the real hazard — a
    future edit to `ci.yml` that the embed does not learn about — without
    breaking while the landing is outstanding.

    A guard that only catches other people's drift while shipping stale content
    itself would be theatre. This is what stops that.
    """
    workflow = ROOT / ".github" / "workflows" / "ci.yml"
    if not workflow.is_file():
        pytest.skip("ci.yml not present in this checkout")

    on_disk = workflow.read_bytes().replace(b"\r\n", b"\n")
    dropped = mod.would_drop(on_disk, mod.WORKFLOW_YAML.encode("utf-8"))

    assert dropped == [], (
        "the embedded workflow is behind .github/workflows/ci.yml and would "
        f"revert these lines: {dropped}"
    )
