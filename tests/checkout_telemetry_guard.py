"""No test writes into the checkout's telemetry logs (#4161).

Three writers append to logs under the repository's own ``data/``, and every
report built from those logs reads them as real runs:

- ``data/speedrun/telemetry/run-records.jsonl``: stage telemetry
  (``assemblyzero.speedrun.convergence``);
- ``data/speedrun/telemetry/prompt-failures.jsonl``: drafter validation
  failures (``assemblyzero.speedrun.prompt_telemetry``, #2074);
- ``data/telemetry/hallucination-log.jsonl``: invented-API checks
  (``assemblyzero.workflows.telemetry.hallucination_log``, #1812).

Each takes the root it writes under from its caller, and a test that runs a
node or a graph from the checkout hands it the checkout. The home-state guard
(#3531) never covered them, because they are not in the home directory.

The root is often relative. Three nodes write under ``state["target_repo"] or
"."``, so a test whose state names no repository writes under the directory
pytest was started from (#4202). From the checkout that is the checkout; from
anywhere else it is that directory, and a run started from another
repository's checkout left its prompt-failure log there, rows reading
``"repo": "."``. So the guarded roots are two: the checkout, and the directory
the run started in.

Two pieces here, matching the home-state guard:

- ``redirect``: the autouse fixture's body. A write whose root is the checkout
  (or inside it), or is the directory the run started in, lands under a
  per-test directory instead; a write under any other root (a test's own
  ``tmp_path``, or the directory a test moved into) goes where it was sent.
- ``GUARDED_FILES``: the session guard's paths, each writer's file under each
  guarded root. ``conftest.py`` snapshots them at session start and fails the
  session if any of them appeared or changed.
"""

from __future__ import annotations

from pathlib import Path

#: The checkout this suite runs from: a worktree is its own checkout.
CHECKOUT = Path(__file__).resolve().parents[1]

#: The directory pytest was started from (#4202), where a relative root such
#: as ``"."`` points. Read when ``conftest.py`` first imports this module, in
#: ``pytest_sessionstart``, before any test can change directory.
START_DIR = Path.cwd().resolve()

#: Where each writer puts its log under the root it is handed.
TELEMETRY_FILES: tuple[Path, ...] = (
    Path("data") / "speedrun" / "telemetry" / "run-records.jsonl",
    Path("data") / "speedrun" / "telemetry" / "prompt-failures.jsonl",
    Path("data") / "telemetry" / "hallucination-log.jsonl",
)

#: What a real run writes under the checkout's ``data/``, or under the start
#: directory's, and a test must not. One entry when the two roots coincide.
GUARDED_FILES: tuple[Path, ...] = tuple(
    dict.fromkeys(
        root / relative
        for root in (CHECKOUT, START_DIR)
        for relative in TELEMETRY_FILES
    )
)


def _is_checkout(root: Path | str) -> bool:
    """Whether a write under ``root`` would land in a guarded root.

    The checkout and everything inside it, and the start directory itself.
    Only the start directory itself, not what is under it: a test's own
    ``tmp_path`` lies under it when a run starts from ``/tmp``, and those
    writes are the test's.
    """
    resolved = Path(root).resolve()
    return (
        resolved == START_DIR
        or resolved == CHECKOUT
        or resolved.is_relative_to(CHECKOUT)
    )


def redirect(monkeypatch, sink: Path) -> None:
    """Send every telemetry write aimed at a guarded root to ``sink`` instead.

    ``convergence`` and ``prompt_telemetry`` look up their path functions as
    module globals at call time, so replacing the attribute reaches every
    caller. ``record_hallucination_event`` is imported by name into the
    telemetry package and the completeness node, so each of those bindings is
    replaced too. A test that patches one of these itself still wins: its
    monkeypatch runs after this one.
    """
    import importlib

    # The completeness node's MODULE: the nodes package re-exports a function
    # of the same name. It is imported first, because importing the telemetry
    # package first runs into a circular import through the requirements
    # package, which a real run never meets: the node imports the package.
    validate_completeness = importlib.import_module(
        "assemblyzero.workflows.implementation_spec.nodes.validate_completeness"
    )
    import assemblyzero.workflows.telemetry as telemetry_package
    from assemblyzero.speedrun import convergence, prompt_telemetry
    from assemblyzero.workflows.telemetry import hallucination_log

    real_records_path = convergence.records_path
    real_telemetry_path = prompt_telemetry.telemetry_path
    real_record_event = hallucination_log.record_hallucination_event

    def records_path(repo_root):
        return real_records_path(sink if _is_checkout(repo_root) else repo_root)

    def telemetry_path(repo_root):
        return real_telemetry_path(sink if _is_checkout(repo_root) else repo_root)

    def record_hallucination_event(event, audit_dir, assemblyzero_root):
        if assemblyzero_root is not None and _is_checkout(assemblyzero_root):
            assemblyzero_root = sink
        return real_record_event(event, audit_dir, assemblyzero_root)

    monkeypatch.setattr(convergence, "records_path", records_path)
    monkeypatch.setattr(prompt_telemetry, "telemetry_path", telemetry_path)
    for module in (hallucination_log, telemetry_package, validate_completeness):
        monkeypatch.setattr(
            module, "record_hallucination_event", record_hallucination_event
        )
