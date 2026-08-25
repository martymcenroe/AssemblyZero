"""The gate loop (#2518): render, serve, wait, dispatch the verb.

Render early -- before the spec stage spends review rounds -- directly from
the target repo's binding contract, via the repo's own renderer. Serve the
picture locally. Halt resumably: the operator's answer lands in feedback.json
whether this process is still alive or a resume reads it later.

Renderer protocol (the repo side of the contract; boostgauge's
tools/visual_contract_render.py is the reference implementation):

* invoked as ``<renderer_cmd...> --out-dir <dir> [--set key=value ...]``
  with the target repo as cwd;
* writes one or more ``*.png`` and a ``manifest.json``
  (``{"values": {key: {"value", "source", "ruled"?}}, "palette": {name: [r,g,b]},
  "samples": [{"name", "x_frac", "y_frac", "expect"}]?}``);
* exit 0 on success; exit 3 when the contract is TOO ADJECTIVAL to render,
  with stderr naming what is unrenderable -- which is the gate's finding,
  caught before any drafting, and the halt says so in those words.

Round lifecycle on disk (what makes the halt resumable):

* a round with images and no ``feedback.json`` is SERVED (again, on resume);
* a round with ``feedback.json`` is dispatched, then the file is renamed to
  ``feedback-consumed.json`` so no verb ever fires twice;
* every round records the overrides that rendered it, so a resumed gate
  re-enters with the accumulated deltas intact.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from assemblyzero.visual_gate import bundle as bundle_mod
from assemblyzero.visual_gate.config import GateConfig
from assemblyzero.visual_gate.modify import (
    ModifyPlan,
    decompose,
    default_transport,
    plan_from_items,
)
from assemblyzero.visual_gate.server import serve_bundle, wait_for_feedback

#: Renderer exit code that means "the contract cannot be drawn from" -- the
#: adjectival-contract finding, distinct from an ordinary crash.
TOO_ADJECTIVAL_EXIT = 3


@dataclass
class GateOutcome:
    status: str                 # "approved" | "halted"
    artifact_path: str = ""
    error: str = ""
    rounds: int = 0
    deltas: dict = field(default_factory=dict)


def _run(cmd, cwd, runner=subprocess.run):
    return runner(
        [str(part) for part in cmd], cwd=str(cwd),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _invoke_renderer(
    target_repo: Path, config: GateConfig, out_dir: Path, overrides: dict,
    *, runner=subprocess.run,
) -> str:
    """One renderer invocation. Returns "" or an error/finding string."""
    cmd = list(config.renderer_cmd) + ["--out-dir", str(out_dir)]
    for key, value in sorted(overrides.items()):
        cmd += ["--set", f"{key}={json.dumps(value)}"]
    result = _run(cmd, cwd=target_repo, runner=runner)
    if result.returncode == TOO_ADJECTIVAL_EXIT:
        return (
            "the binding contract is too adjectival to render -- the gate's "
            "finding, before any drafting: " + (result.stderr or "").strip()
        )
    if result.returncode != 0:
        return (
            f"renderer failed (exit {result.returncode}): "
            + ((result.stderr or "").strip() or (result.stdout or "").strip())[:600]
        )
    if not (out_dir / "manifest.json").is_file() or not sorted(out_dir.glob("*.png")):
        return (
            "renderer exited 0 but the bundle is incomplete: "
            f"manifest={'present' if (out_dir / 'manifest.json').is_file() else 'MISSING'}, "
            f"images={len(sorted(out_dir.glob('*.png')))}"
        )
    return ""


def render_round(
    target_repo: Path, config: GateConfig, round_dir: Path, overrides: dict,
    *, candidate_sets: dict | None = None, runner=subprocess.run, log=print,
) -> dict | str:
    """Render one review round: the base picture, plus every in-floor colour
    candidate side by side in the SAME bundle (the worked example's fifth
    row: an adjectival ask gets candidates and a second look, on one page).

    Returns the round's manifest dict, or an error/finding string.
    """
    (round_dir / "overrides.json").write_text(
        json.dumps(overrides, indent=2), encoding="utf-8",
    )
    error = _invoke_renderer(target_repo, config, round_dir, overrides, runner=runner)
    if error:
        return error
    manifest = json.loads((round_dir / "manifest.json").read_text(encoding="utf-8-sig"))

    for key, candidates in sorted((candidate_sets or {}).items()):
        for index, rgb in enumerate(candidates, 1):
            sub = round_dir / f"cand-{key}-{index}"
            sub.mkdir()
            variant = dict(overrides)
            variant[key] = list(rgb)
            error = _invoke_renderer(target_repo, config, sub, variant, runner=runner)
            if error:
                return error
            for png in sorted(sub.glob("*.png")):
                shutil.move(str(png), round_dir / f"candidate{index}-{key}-{png.name}")
            shutil.rmtree(sub)
        manifest.setdefault("candidates", {})[key] = [list(c) for c in candidates]
    if candidate_sets:
        (round_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8",
        )
    log(
        f"    [visual] rendered {len(bundle_mod.bundle_images(round_dir))} "
        f"image(s) into {round_dir}"
    )
    return manifest


def measure_samples(image_path: Path, manifest: dict) -> list[dict]:
    """Read the manifest's sample points off the picture (#2518 step 4).

    Expected colours downstream are MEASURED from the approved render rather
    than derived by a drafter -- the retirement of the #1866 churn class for
    visual work. No samples declared means nothing measured, honestly.
    """
    samples = manifest.get("samples") or []
    if not samples:
        return []
    from PIL import Image

    with Image.open(image_path) as img:
        rgb = img.convert("RGB")
        width, height = rgb.size
        measured = []
        for sample in samples:
            x = min(width - 1, max(0, round(float(sample["x_frac"]) * (width - 1))))
            y = min(height - 1, max(0, round(float(sample["y_frac"]) * (height - 1))))
            measured.append({
                "name": sample.get("name", f"({x},{y})"),
                "x": x, "y": y,
                "rgb": list(rgb.getpixel((x, y))),
                "expect": sample.get("expect", ""),
            })
        return measured


def _codify_on_approve(
    target_repo: Path, issue: int, config: GateConfig, *,
    deltas: dict, gaps: list[str], measurements: list[dict],
    approved_sha: str, mock: bool, runner=subprocess.run, log=print,
) -> str:
    """Fold the accumulated deltas into the binding docs via the normal
    ruling-PR flow. Returns "" on success, an error string on failure --
    a failed codification is loud, never silent: the approved render is only
    authoritative once the docs carry its values.
    """
    if not deltas and not gaps:
        return ""
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rel = Path("docs") / "design" / "rulings" / f"visual-gate-{issue}-{stamp}.md"
    lines = [
        f"# Visual-gate ruling — issue #{issue}, {stamp}",
        "",
        f"Operator-approved render (sha256 `{approved_sha}`) via the #2518 "
        f"visual gate; deltas below were applied iteratively and approved on "
        f"sight. Binding against `{config.contract}`.",
        "",
    ]
    if deltas:
        lines += ["## Contract deltas", "", "| key | approved value |", "|---|---|"]
        lines += [f"| `{k}` | `{json.dumps(v)}` |" for k, v in sorted(deltas.items())]
        lines.append("")
    if measurements:
        lines += [
            "## Measured from the approved render",
            "", "| sample | rgb | expected entry |", "|---|---|---|",
        ]
        lines += [
            f"| {m['name']} | {tuple(m['rgb'])} | {m['expect']} |"
            for m in measurements
        ]
        lines.append("")
    if gaps:
        lines += ["## Contract gaps the operator named", ""]
        lines += [f"- {gap}" for gap in gaps]
        lines.append("")
    body = "\n".join(lines)

    if mock:
        log(f"    [mock] visual-gate ruling NOT committed; would write {rel}")
        return ""

    doc = target_repo / rel
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(body, encoding="utf-8")
    branch = f"visual-gate-{issue}-ruling-{stamp}"
    steps = [
        ["git", "checkout", "-b", branch],
        ["git", "add", str(rel)],
        ["git", "commit", "-m",
         f"docs: land the visual-gate ruling for #{issue} (Ref #{issue})"],
        ["git", "push", "-u", "origin", branch],
    ]
    for step in steps:
        result = _run(step, cwd=target_repo, runner=runner)
        if result.returncode != 0:
            return (
                f"codification failed at {' '.join(step[:3])}: "
                f"{(result.stderr or '').strip()[:400]}"
            )
    pr_body = target_repo / "data" / "visual-gate" / str(issue) / "ruling-pr-body.md"
    pr_body.parent.mkdir(parents=True, exist_ok=True)
    pr_body.write_text(
        body + f"\n\nRef #{issue} — filed by the visual gate on approval.\n",
        encoding="utf-8",
    )
    result = _run(
        ["gh", "pr", "create", "--head", branch, "--base", "main",
         "--title", f"docs: visual-gate ruling for #{issue}",
         "--body-file", str(pr_body)],
        cwd=target_repo, runner=runner,
    )
    if result.returncode != 0:
        return f"codification PR failed: {(result.stderr or '').strip()[:400]}"
    log(f"    [visual] ruling PR opened: {(result.stdout or '').strip()}")
    return ""


def _file_rejection(
    target_repo: Path, issue: int, round_dir: Path, words: str, *,
    mock: bool, runner=subprocess.run, log=print,
) -> str:
    """Reject files a must-resolve-class issue carrying the operator's words."""
    title = f"must-resolve: visual gate rejection on #{issue} — redesign required"
    body_path = round_dir / "rejection-issue.md"
    body_path.write_text(
        "Found by the visual gate (#2518) during a live roll: the operator "
        "REJECTED the contract-faithful render. The roll halts for redesign; "
        "an operator ruling on the binding contract is required before any "
        "re-roll of this issue.\n\n"
        f"**Source issue:** #{issue}\n"
        f"**Review bundle:** `{round_dir}`\n\n"
        "**The operator's words, verbatim:**\n\n"
        f"> {words.strip() or '(no text given)'}\n",
        encoding="utf-8",
    )
    if mock:
        log(f"    [mock] rejection issue NOT filed; body at {body_path}")
        return ""
    result = _run(
        ["gh", "issue", "create", "--title", title,
         "--body-file", str(body_path), "--label", "must-resolve"],
        cwd=target_repo, runner=runner,
    )
    if result.returncode != 0:
        return f"could not file the rejection issue: {(result.stderr or '').strip()[:400]}"
    log(f"    [visual] rejection issue filed: {(result.stdout or '').strip()}")
    return ""


def _unconsumed_round(root: Path) -> Path | None:
    """The newest round still owed a dispatch, or None."""
    rounds = bundle_mod.round_dirs(root)
    if not rounds:
        return None
    last = rounds[-1]
    if (last / "feedback-consumed.json").is_file():
        return None
    if not bundle_mod.bundle_images(last):
        return None
    return last


def _mark_consumed(round_dir: Path) -> None:
    src = round_dir / "feedback.json"
    if src.is_file():
        src.replace(round_dir / "feedback-consumed.json")


def _latest_overrides(root: Path) -> dict:
    rounds = bundle_mod.round_dirs(root)
    for round_dir in reversed(rounds):
        path = round_dir / "overrides.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return {}


def run_gate(
    target_repo: Path, issue: int, config: GateConfig, *,
    mock: bool = False, transport=None, runner=subprocess.run,
    log=print, wait_kwargs: dict | None = None,
) -> GateOutcome:
    """The loop: render -> serve -> wait -> verb, until Approve or a halt."""
    target_repo = Path(target_repo)
    root = bundle_mod.gate_root(target_repo, issue)
    transport = transport or default_transport
    wait_kwargs = wait_kwargs or {}
    accumulated: dict = _latest_overrides(root)
    pending_candidates: dict = {}
    rounds_run = 0

    # Resume shortcut: an already-approved gate needs no ceremony.
    if (root / "approved" / "approved.json").is_file():
        log("    [visual] approved render already stamped; gate passes.")
        return GateOutcome(
            status="approved",
            artifact_path=str(root / "approved" / "approved.png"),
            deltas=accumulated,
        )

    while True:
        current = _unconsumed_round(root)
        if current is None:
            current = bundle_mod.next_round_dir(root)
            rendered = render_round(
                target_repo, config, current, accumulated,
                candidate_sets=pending_candidates, runner=runner, log=log,
            )
            if isinstance(rendered, str):
                return GateOutcome(status="halted", error=rendered, rounds=rounds_run)
            manifest = rendered
            pending_candidates = {}
        else:
            manifest = json.loads(
                (current / "manifest.json").read_text(encoding="utf-8-sig")
            )
            accumulated = _latest_overrides(root) or accumulated

        answer = bundle_mod.read_feedback(current)
        if answer is None:
            server, url = serve_bundle(current, issue)
            bundle_mod.write_pending(current, url)
            log(f"    [visual] review page: {url}")
            log(f"    [visual] bundle: {current}")
            try:
                answer = wait_for_feedback(current, log=log, **wait_kwargs)
            finally:
                server.shutdown()
        rounds_run += 1
        verb = answer["verb"]
        words = answer.get("text", "")
        log(f"    [visual] operator verb: {verb.upper()}")

        if verb == "approve":
            chosen = bundle_mod.bundle_images(current)[0]
            measurements = measure_samples(chosen, manifest)
            stamped = bundle_mod.stamp_approved(
                root, current, chosen,
                deltas=[
                    {"key": k, "value": v} for k, v in sorted(accumulated.items())
                ],
                measurements=measurements,
            )
            sha = json.loads(
                (root / "approved" / "approved.json").read_text(encoding="utf-8")
            )["sha256"]
            error = _codify_on_approve(
                target_repo, issue, config,
                deltas=accumulated, gaps=_collected_gaps(root),
                measurements=measurements, approved_sha=sha,
                mock=mock, runner=runner, log=log,
            )
            _mark_consumed(current)
            if error:
                return GateOutcome(
                    status="halted", error=error, rounds=rounds_run,
                    deltas=accumulated,
                )
            return GateOutcome(
                status="approved", artifact_path=str(stamped),
                rounds=rounds_run, deltas=accumulated,
            )

        if verb == "reject":
            error = _file_rejection(
                target_repo, issue, current, words,
                mock=mock, runner=runner, log=log,
            )
            _mark_consumed(current)
            reason = (
                f"operator REJECTED the render for redesign: "
                f"{words.strip()[:400] or '(no text)'}"
            )
            if error:
                reason += f" | {error}"
            return GateOutcome(status="halted", error=reason, rounds=rounds_run)

        # modify
        try:
            # #2521: the declaration's ruled values are contract vocabulary
            # even when a stale round's manifest predates them -- the live
            # round-001 was rendered before needle_tip joined the contract,
            # and without this merge the model would file the operator's
            # tip-extension ask as a contract gap instead of routing it to
            # the ruling surface the design demands.
            prompt_manifest = _with_declared_ruled(manifest, config.ruled)
            items = decompose(words, prompt_manifest, transport)
            plan: ModifyPlan = plan_from_items(
                items, prompt_manifest,
                separation_floor=config.separation_floor, ruled=config.ruled,
            )
        except Exception as exc:  # noqa: BLE001 -- see the ruling below
            # fail-open: in shape only -- the handler substitutes a HALTED,
            # resumable outcome, this stage's halt idiom. An infra error in
            # the model pass is not an operator verdict and not a render
            # failure (#2521): the bundle and the submitted feedback are
            # intact, feedback.json is deliberately NOT consumed, and the
            # resume re-enters this exact dispatch without re-serving the
            # page or asking the operator to click again. The first live
            # Modify let this exception kill the whole run and trigger
            # RESTORE, turning a wiring typo into a dead roll.
            return GateOutcome(
                status="halted",
                error=(
                    f"the Modify model pass failed before any verdict was "
                    f"reached: {exc}. This is an infra error, not an operator "
                    f"verdict -- the submitted feedback in {current} is "
                    f"preserved unconsumed, and a resume of the visual stage "
                    f"dispatches it without re-serving the page."
                ),
                rounds=rounds_run, deltas=accumulated,
            )
        _record_round_plan(current, plan)
        _mark_consumed(current)
        if plan.halted_on_ruling:
            return GateOutcome(
                status="halted",
                error=(
                    "a requested delta contradicts a landed ruling -- the gate "
                    "does not override rulings: "
                    + " | ".join(plan.ruling_conflicts)
                ),
                rounds=rounds_run, deltas=accumulated,
            )
        for finding in plan.floor_refusals:
            log(f"    [visual] floor refusal (computed, not rendered): {finding}")
        accumulated.update(plan.deltas)
        pending_candidates = plan.candidate_sets
        # Loop: the next iteration renders the accumulated deltas (plus any
        # candidate variants, side by side) and serves the new round.


def _with_declared_ruled(manifest: dict, ruled: dict) -> dict:
    """The manifest, plus any declaration-ruled key it does not carry (#2521).

    A round rendered before a key joined the contract has no entry for it,
    but the declaration's pinned value is still binding law -- the model
    pass must see the key (or it invents a gap), and the guardrail must see
    the pin (or a delta on it slips past the ruling surface).
    """
    merged = dict(manifest)
    values = dict(merged.get("values", {}))
    for key, value in (ruled or {}).items():
        if key not in values:
            values[key] = {
                "value": value,
                "source": "visual-gate.json ruled declaration",
                "ruled": True,
            }
    merged["values"] = values
    return merged


def _record_round_plan(round_dir: Path, plan: ModifyPlan) -> None:
    (round_dir / "plan.json").write_text(
        json.dumps({
            "deltas": plan.deltas,
            "candidate_sets": plan.candidate_sets,
            "pinned": plan.pinned,
            "gaps": plan.gaps,
            "floor_refusals": plan.floor_refusals,
            "ruling_conflicts": plan.ruling_conflicts,
        }, indent=2),
        encoding="utf-8",
    )


def _collected_gaps(root: Path) -> list[str]:
    gaps: list[str] = []
    for round_dir in bundle_mod.round_dirs(root):
        path = round_dir / "plan.json"
        if path.is_file():
            gaps.extend(json.loads(path.read_text(encoding="utf-8")).get("gaps", []))
    return gaps
