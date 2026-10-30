"""The staleness guard in tools/land_2283_ci_tiers.py (#2283).

That script embeds a copy of `.github/workflows/ci.yml` and lands it through the
Contents API, which replaces the file wholesale. The embed therefore ages against
main, and it did: it sat unlanded for five weeks while main gained a
`concurrency:` block and an action bump. Landing it then would have reverted
both, the concurrency block being an active Actions-cost measure, and nothing in
the flow would have said so.

`would_drop` is what says so. These tests are how it is verified, because the
script itself cannot be run without decrypting the classic PAT.

The landing is done: PR #3459 put the embed on main on 2026-09-22. From then
on the embed is history, and every line a later change adds to `ci.yml` is a
line it "would drop". So the check against this checkout's `ci.yml` applies
only while the landing is pending, and the landing is pending while `ci.yml`
still carries a line the embed removes on purpose (#4209). Running the script
itself after the landing still refuses, because its own `would_drop` call has
no such condition.
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


def landing_pending(workflow: bytes) -> bool:
    """Whether the embed has yet to land over `workflow`.

    The script lands its change in one Contents API PUT, so the lines it
    removes on purpose (`INTENDED_REMOVALS`) leave `ci.yml` in the same commit
    that brings the lines it adds. While any of them is still on `workflow`,
    the change has not landed. Once none is, it has.

    The lines the embed adds cannot decide this. A later change may rewrite a
    line the landing wrote (#4208 rewrites the `# Issues` header and the
    coverage upload's `if: always()`), and a set of lines cannot tell a line
    that was rewritten after the landing from one that has not landed yet.
    """
    lines = set(workflow.decode("utf-8").splitlines())
    return any(line in lines for line in mod.INTENDED_REMOVALS)


def guard_failures(workflow: bytes, embed: bytes) -> list[str]:
    """The lines of `workflow` that landing `embed` now would revert.

    While the landing is pending, that is everything `would_drop` reports.
    Once it has landed, the embed is history: the lines `workflow` has gained
    since are later work, not drift the embed failed to learn about.
    """
    if not landing_pending(workflow):
        return []
    return mod.would_drop(workflow, embed)


def _replace_once(text: str, old: str, new: str) -> str:
    """`text` with `old` replaced, failing loudly if `old` is not there once."""
    assert text.count(old) == 1, f"expected exactly one {old!r} in the fixture"
    return text.replace(old, new)


#: A step a later change adds after checkout, shaped like the #4208 step.
LATER_STEP = (
    "      - name: Checkout code\n"
    "        uses: actions/checkout@v7\n"
    "        with:\n"
    "          fetch-depth: 2\n"
    "\n"
    "      - name: Handoff data only?\n"
    "        id: handoff\n"
    "        if: github.event_name == 'pull_request'\n"
    "        run: python3 tools/handoff_only.py\n"
)


def _after_a_later_change(embed: str) -> str:
    """`embed` as a later change to `ci.yml` leaves it once the embed has landed.

    The change adds lines (a step, and `fetch-depth` on checkout) and rewrites
    two lines the landing wrote, which is what #4208 does.
    """
    text = _replace_once(
        embed,
        "      - name: Checkout code\n        uses: actions/checkout@v7\n",
        LATER_STEP,
    )
    text = _replace_once(
        text,
        "# Issues #325, #116, #225, #2283\n",
        "# Issues #325, #116, #225, #2283, #4208\n",
    )
    return _replace_once(
        text,
        "        if: always()\n",
        "        if: always() && steps.handoff.outputs.only != 'true'\n",
    )


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


def test_the_shipped_embed_drops_nothing_while_its_landing_is_pending():
    """While the landing is pending, the embed must not be behind this `ci.yml`.

    Deliberately NOT an equality check. The embed is ahead of `ci.yml` by the
    tier steps until the operator runs the script, and equal to it afterwards;
    an equality assertion would fail for exactly as long as the change is
    pending, which is when it most needs to be green.

    While it is pending, the guard's own property must hold: the embed drops
    nothing the repo's workflow already has. That catches the real hazard, an
    edit to `ci.yml` that the embed does not learn about, without breaking
    while the landing is outstanding.

    Once it has landed, `ci.yml` moves on and the embed does not, so every
    later line would read as a drop. The check stands down then (#4209); the
    script's own `would_drop` call still refuses a run over those lines.

    A guard that only catches other people's drift while shipping stale content
    itself would be theatre. This is what stops that.
    """
    workflow = ROOT / ".github" / "workflows" / "ci.yml"
    if not workflow.is_file():
        pytest.skip("ci.yml not present in this checkout")

    on_disk = workflow.read_bytes().replace(b"\r\n", b"\n")
    dropped = guard_failures(on_disk, mod.WORKFLOW_YAML.encode("utf-8"))

    assert dropped == [], (
        "the embedded workflow is behind .github/workflows/ci.yml and would "
        f"revert these lines: {dropped}"
    )


def test_a_landed_embed_passes_when_the_workflow_gains_a_step():
    """A later change to `ci.yml`, after the landing, does not fail the guard.

    The workflow here is the real embed after a change shaped like #4208: a
    step added, and two lines the landing wrote rewritten. The bare
    `would_drop` reports it, which is what the guard asserted before #4209.
    """
    embed = mod.WORKFLOW_YAML.encode("utf-8")
    later = _after_a_later_change(mod.WORKFLOW_YAML).encode("utf-8")

    assert not landing_pending(later)
    assert "        id: handoff" in mod.would_drop(later, embed)
    assert guard_failures(later, embed) == []


def test_the_real_embed_still_fails_while_pending_and_behind():
    """The real embed, pending against a `ci.yml` that gained a step, fails.

    The workflow still carries the pre-landing `# Issues` header, one of the
    lines the embed removes on purpose, so the landing is pending. The step
    it gained is not in the embed, and landing would drop it.
    """
    embed = mod.WORKFLOW_YAML.encode("utf-8")
    pending = _replace_once(
        _after_a_later_change(mod.WORKFLOW_YAML),
        "# Issues #325, #116, #225, #2283, #4208\n",
        "# Issues #325, #116, #225\n",
    ).encode("utf-8")

    assert landing_pending(pending)
    failures = guard_failures(pending, embed)
    assert "      - name: Handoff data only?" in failures
    assert "          fetch-depth: 2" in failures
    assert "# Issues #325, #116, #225" not in failures  # removed on purpose


def test_a_pending_embed_with_an_addition_that_would_drop_a_line_fails():
    """An embed ahead of the workflow by an addition, and behind it by a line."""
    workflow = (
        b"# Issues #325, #116, #225\n"
        b"name: CI\n"
        b"      - name: Gained on main\n"
    )
    embed = (
        b"# Issues #325, #116, #225, #2283\n"
        b"name: CI\n"
        b"      - name: Run e2e tests\n"
    )

    assert landing_pending(workflow)
    assert guard_failures(workflow, embed) == ["      - name: Gained on main"]


def test_the_actual_regression_still_fails_while_pending():
    """The regression the guard exists for, as main stood when it happened.

    Main then still carried the pre-landing header and the main-only
    integration condition, which the embed removes on purpose, so the landing
    was pending. The stale embed lacked `concurrency:` and the action bump.
    """
    remote = (
        b"# CI Workflow - Unit tests on every push/PR, integration tests on main\n"
        b"# Issues #325, #116, #225\n"
        b"name: CI\n"
        b"concurrency:\n"
        b"  group: ${{ github.workflow }}-${{ github.ref }}\n"
        b"  cancel-in-progress: true\n"
        b"      - name: Set up Python\n"
        b"        uses: actions/setup-python@v7\n"
        b"        if: github.event_name == 'push' && github.ref == 'refs/heads/main'\n"
    )
    stale_embed = (
        b"# CI Workflow - every test tier on every push/PR\n"
        b"# Issues #325, #116, #225, #2283\n"
        b"name: CI\n"
        b"      - name: Set up Python\n"
        b"        uses: actions/setup-python@v5\n"
        b"      - name: Run e2e tests\n"
    )

    assert landing_pending(remote)
    failures = guard_failures(remote, stale_embed)
    assert "concurrency:" in failures
    assert "        uses: actions/setup-python@v7" in failures


def test_the_shipped_embed_carries_none_of_the_lines_it_removes():
    """`landing_pending` relies on this: the landed embed is never pending."""
    assert not landing_pending(mod.WORKFLOW_YAML.encode("utf-8"))
