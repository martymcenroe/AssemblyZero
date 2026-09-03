#!/usr/bin/env python
"""Replay a recorded run through the current graph (#2724).

The launch gate. Twelve launches were allowed on boostgauge #421 and all twelve
are spent; the operator's ruling of 2026-09-02 is that nothing relaunches until
the recorded runs replay past the walls that killed them. This tool is how that
is measured, in seconds, for free, with no network.

Only the LLM transport is replaced (`ScriptedProvider`, #2567). The graph, the
routers, the gates, the pinning enforcement, the file writes and the halt path
all run for real against a throwaway clone.

    poetry run python tools/replay_run.py \\
        --recording C:/Users/mcwiz/Projects/boostgauge \\
        --clone data/replay/boostgauge \\
        --issue 4 --base hardening-run-20

Add `--run run-issue4-183941` (repeatable) to replay named runs instead of every
recorded run for the issue.

The table this prints is what a PR touching `assemblyzero/workflows/` carries in
its body. `--markdown` prints only the table, for pasting.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assemblyzero.core.utf8_console import install as _install_utf8_console  # noqa: E402

_install_utf8_console()

from assemblyzero.core.scripted_provider import (  # noqa: E402
    ScriptedProvider,
    set_active,
)
from assemblyzero.speedrun.factory_report import (  # noqa: E402
    classify_cause,
    runs_dir,
    scan_run_log,
)
from assemblyzero.speedrun.replay import (  # noqa: E402
    CALLER_REVIEWER,
    KIND_LLD,
    KIND_SPEC,
    ReplayResult,
    audit_dirs_for_run,
    build_spec_rules,
    classify,
    discover_audit_dirs,
    render_table,
    responses_in,
    run_window,
)

#: The provider's own refusals all carry this head. It is how a divergence is
#: told apart from a gate: a gate is the pipeline saying no to content, and this
#: is the recording no longer fitting the prompt the code now sends.
DIVERGENCE_MARK = "ScriptedProvider:"

#: The stage this tool can replay today. Runs that died in `impl` need the
#: testing graph, whose responses the recordings do not carry in call order;
#: `--issue 4` reports those rather than pretending to replay them.
REPLAYABLE_STAGES = (KIND_SPEC,)


def _final_lld(lld_dir: Path) -> str:
    """The LLD the recorded spec stage was handed.

    `004-final.md` is the approved document; the draft before it is not what the
    spec stage read. A recording with no final has nothing to hand the stage and
    says so instead of substituting a draft.
    """
    finals = [r for r in responses_in(lld_dir) if r.suffix == "final"]
    return finals[-1].text if finals else ""


def replay_spec_stage(
    *,
    tag: str,
    issue: int,
    clone: Path,
    base_branch: str,
    lld_dir: Path,
    spec_dir: Path,
    out_dir: Path,
    recorded_cause: str,
    recorded_progress: int,
    max_iterations: int,
) -> ReplayResult:
    """Run the real spec graph on one recording's responses."""
    from assemblyzero.workflows.implementation_spec.graph import (
        create_implementation_spec_graph,
    )
    from assemblyzero.workflows.implementation_spec.spec_step_budget import (
        recursion_limit,
    )

    rules, recon = build_spec_rules(spec_dir)
    result = ReplayResult(
        tag=tag,
        stage=KIND_SPEC,
        recorded_cause=recorded_cause,
        recorded_progress=recorded_progress,
        reconstruction=recon,
    )

    lld_text = _final_lld(lld_dir)
    if not lld_text.strip():
        result.divergence = (
            f"the recorded LLD lineage {lld_dir.name} holds no final document, "
            f"so the spec stage cannot be handed the input it actually read"
        )
        return result

    # A FRESH lineage directory per replay, never a reused one. `generate_spec`
    # recovers a draft by globbing `*-spec-draft.md` out of the directory it is
    # handed, so a second replay into the same directory skips the initial
    # drafter call and starts mid-loop -- the replay silently stops being a
    # replay of the recording. The run-scoped naming is the same reason #1467
    # gave the pipeline itself.
    out_dir = out_dir / datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    lld_path = out_dir / f"LLD-{issue:03d}.md"
    lld_path.write_text(lld_text, encoding="utf-8")
    audit_dir = out_dir / "lineage"
    audit_dir.mkdir(parents=True, exist_ok=True)

    provider = ScriptedProvider(rules, model="replay")
    set_active(provider)
    state = {
        "issue_number": issue,
        "lld_path": str(lld_path),
        "repo_root": str(clone),
        "assemblyzero_root": str(ROOT),
        "audit_dir": str(audit_dir),
        "base_branch": base_branch,
        "lld_content": "",
        "files_to_modify": [],
        "current_state_snapshots": {},
        "pattern_references": [],
        "spec_draft": "",
        "spec_path": "",
        "completeness_issues": [],
        "validation_passed": False,
        "review_verdict": "BLOCKED",
        "review_feedback": "",
        "review_iteration": 0,
        "review_feedback_history": [],
        "max_iterations": max_iterations,
        "human_gate_enabled": False,
        "next_node": "",
        "error_message": "",
        "cost_budget_usd": 0.0,
        "config_reviewer": "scripted:reviewer",
        "config_drafter": "scripted:drafter",
        "config_mock_mode": False,
        "config_effort": "",
        "node_costs": {},
        "node_tokens": {},
    }

    final = dict(state)
    try:
        graph = create_implementation_spec_graph()
        config = {"recursion_limit": recursion_limit(max_iterations)}
        for event in graph.stream(state, config):
            for node_name, node_output in event.items():
                if node_name == "__end__" or not node_output:
                    continue
                final.update(node_output)
    except Exception as exc:  # noqa: BLE001
        # Loud, not swallowed: the replay reports the exception as its outcome
        # rather than continuing with a state that never finished. A silent
        # handler here would let a crashed replay be read as a clean one.
        result.divergence = f"the graph raised {type(exc).__name__}: {exc}"
        result.path = list(provider.stages_called)
        set_active(None)
        return result
    finally:
        set_active(None)

    result.path = list(provider.stages_called)
    # Counted from the calls the reviewer actually received, not from
    # `review_iteration`: the state key is a node's write, and a run that dies
    # inside the drafter never gets to update it, which reads as round 0 for a
    # loop that plainly ran. The recording's side of this comparison is counted
    # the same way, from the review rounds the log shows.
    result.replay_progress = max(
        provider.stages_called.count(CALLER_REVIEWER),
        int(final.get("review_iteration", 0) or 0),
    )
    error = str(final.get("error_message", "") or "")

    unmatched = [c for c in provider.calls if not c.answered]
    if DIVERGENCE_MARK in error or unmatched:
        result.divergence = error if DIVERGENCE_MARK in error else (
            f"{len(unmatched)} call(s) the recording could not answer"
        )
    elif error:
        result.replay_cause = classify_cause(error.splitlines()[0])
        result.notes.append(error.splitlines()[0][:200])

    result.verdict = classify(
        recorded_cause=recorded_cause,
        recorded_progress=recorded_progress,
        replay_cause=result.replay_cause,
        replay_progress=result.replay_progress,
        divergence=result.divergence,
        finished=bool(final.get("spec_path")),
    )
    return result


def collect(args: argparse.Namespace) -> tuple[list[ReplayResult], list[str]]:
    """Replay every requested run; return results and the skipped ones."""
    recording = Path(args.recording).resolve()
    clone = Path(args.clone).resolve()
    out_root = Path(args.out).resolve()
    dirs = discover_audit_dirs(recording, args.issue)

    logs = sorted(runs_dir(recording).glob(f"run-issue{args.issue}-*.log"))
    logs = [p for p in logs if not p.name.endswith(("-events.log", "-heartbeat.log"))]
    if args.run:
        wanted = set(args.run)
        logs = [p for p in logs if p.stem in wanted]

    results: list[ReplayResult] = []
    skipped: list[str] = []
    for log in logs:
        facts = scan_run_log(log)
        tag = facts.run_id
        if facts.failed_stage not in REPLAYABLE_STAGES:
            skipped.append(
                f"{tag}: ended in `{facts.failed_stage or facts.outcome}`, and "
                f"only the {'/'.join(REPLAYABLE_STAGES)} stage can be replayed "
                f"from what the recordings hold"
            )
            continue
        start, end = run_window(log)
        chosen, notes = audit_dirs_for_run(dirs, start, end)
        if KIND_SPEC not in chosen or KIND_LLD not in chosen:
            have = ", ".join(sorted(chosen)) or "none"
            skipped.append(
                f"{tag}: needs both an lld and a spec lineage directory; "
                f"found {have}. " + " ".join(notes)
            )
            continue
        result = replay_spec_stage(
            tag=tag,
            issue=args.issue,
            clone=clone,
            base_branch=args.base,
            lld_dir=chosen[KIND_LLD].path,
            spec_dir=chosen[KIND_SPEC].path,
            out_dir=out_root / tag,
            recorded_cause=facts.cause,
            recorded_progress=facts.review_rounds.get("spec", 0),
            max_iterations=args.max_iterations,
        )
        result.notes.extend(notes)
        results.append(result)
    return results, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--recording", required=True,
        help="the repo whose run logs and lineage hold the recordings",
    )
    parser.add_argument(
        "--clone", required=True,
        help="a throwaway clone of that repo -- never a worktree of it",
    )
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument(
        "--base", default="",
        help="the integration branch the recorded runs were built on",
    )
    parser.add_argument(
        "--run", action="append", default=[],
        help="a run tag to replay; repeatable. Default: every run for the issue",
    )
    parser.add_argument("--max-iterations", type=int, default=3)
    parser.add_argument(
        "--out", default=str(ROOT / "data" / "replay" / "out"),
        help="where each replay's lineage and inputs are written",
    )
    parser.add_argument(
        "--markdown", action="store_true",
        help="print only the table, for pasting into a PR body",
    )
    args = parser.parse_args(argv)

    if not Path(args.clone).is_dir():
        parser.error(
            f"--clone {args.clone} is not a directory. Clone the target repo "
            f"fresh into a gitignored directory; a worktree of the live "
            f"checkout is never the right base for a replay."
        )

    results, skipped = collect(args)
    if not results and not skipped:
        print("No recorded runs matched.")
        return 1

    table = render_table(results) if results else "_No run was replayable._"
    if args.markdown:
        print(table)
        return 0

    print(f"# Replay — issue #{args.issue}, {datetime.now():%Y-%m-%d %H:%M:%S}")
    print()
    print(table)
    print()
    for result in results:
        recon = result.reconstruction
        print(f"## {result.tag}")
        print(
            f"  reconstruction: {recon.drafts} draft(s), {recon.verdicts} "
            f"verdict(s), {recon.edit_scripts} edit script(s) synthesised, "
            f"{recon.edit_script_degraded} degraded to a whole document"
        )
        print(f"  calls: {len(result.path)} ({', '.join(result.path) or 'none'})")
        if result.divergence:
            print(f"  divergence: {result.divergence[:400]}")
        for note in [*recon.notes, *result.notes]:
            print(f"  note: {note}")
        print()
    if skipped:
        print("## Not replayed")
        for line in skipped:
            print(f"- {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
