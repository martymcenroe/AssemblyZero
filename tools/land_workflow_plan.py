#!/usr/bin/env python3
"""Land a plan of staged workflow files across many repositories, under one classic-PAT unlock.

Issue #4713. `tools/land_staged_workflow.py` lands one workflow in one repository per
run, and every run asks once for the classic PAT's passphrase. A change that touches
workflows across the fleet (the operator's 2026-11-11 order to stop running tests on
GitHub was about twenty files in sixteen repositories) would be a run, and a passphrase,
per file. This tool takes a plan and lands every target in it inside one
`classic_pat_session()`, one pull request per target. Every GitHub call goes through
the single-repository lander's functions, so the two tools cannot drift apart.

This repository is public and some targets are not, so no repository name is written
here: the plan is the only source of them, and it lives where the staged copies live.

## The plan

    {
      "source": {"repo": "<repository holding the staged copies>", "ref": "main"},
      "reason": "<one paragraph for every pull request body>",
      "targets": [
        {"repo": "<target>", "issue": 12, "files": [
          {"staged": "<path in the source repository>",
           "workflow": ".github/workflows/<file>.yml",
           "base_blob": "<git blob sha of the live workflow the copy was built from>",
           "expect": "skipped"}
        ]}
      ]
    }

`expect` is the conclusion the landing pull request's run of that workflow must show:
`skipped` when every job in the file is `if: false`, `success` otherwise. Other keys are
ignored, so a plan may carry its own notes.

A file entry may instead remove a workflow (#4721):

    {"workflow": ".github/workflows/<file>.yml", "action": "delete",
     "base_blob": "<git blob sha of the live workflow being removed>"}

A delete entry carries no `staged` and no `expect`; an entry without `action` replaces.
A plan whose every entry is a delete needs no `source`. One target may mix the two.

## What one run does, per target, in plan order

  1. Reads each live workflow on the target's `main` and each staged copy from the
     source repository over the Contents API (bytes already LF on GitHub, as the
     single-repository lander reads them). A copy holding a carriage return stops the
     run. A file whose live text already equals its copy is done.
  2. A file not done whose live blob is not the plan's `base_blob` stops the run before
     anything is written to that target: main moved after the copy was made, and
     landing the copy would undo that change.
  3. A target whose every file is done is reported and skipped, so a rerun after a stop
     resumes where it stopped.
  4. Otherwise: one branch (`ci/staged-workflow-<issue>`), one commit per file, one pull
     request that closes the target's issue, a wait for each changed workflow's run on
     the head, then a squash merge and the branch's deletion. A run that does not
     conclude as the plan says stops the run and leaves the pull request open, unless
     --merge-on-red is given; a run still going or never started stops it always.

A delete entry is done when its file is absent on `main`. Otherwise its live blob must
be the plan's `base_blob`, or the run stops before anything is written to the target.
Its commit is a Contents-API DELETE of that blob on the target's branch. No run is
waited for (a deleted workflow starts none of its own); the pull request must still
reach a mergeable state. After the merge `main` is read back, and a file still there
stops the run.

Before any write, every target's repository is read: a target whose default branch is
not `main` stops the run, and so does a plan whose reason names a private target while
any target is public. No pull request title or body names the source repository or a
staged path, and a reason that names the source repository is refused before any
credential is asked for.

The first failure stops the whole run with a non-zero exit, naming the target and the
step, and says how many targets landed, how many were already landed and how many were
not landed (the fleet rule: a failure stops the run and says so).

## Usage

RUN THIS YOURSELF in your own shell -- never via an agent's Bash tool, per the
_pat_session operational rule: a Python process spawned by an agent is the agent's
child, and its heap is readable while the PAT is in scope.

    # from the AssemblyZero checkout; the dry run asks for no credential and writes nothing
    poetry run python tools/land_workflow_plan.py --plan <path to plan.json>
    poetry run python tools/land_workflow_plan.py --plan <path to plan.json> --apply

`--only <repo>` (repeatable) limits the run to those targets of the plan.

`--max-targets N` lands at most N targets that are not already done, then stops with a
summary and exit 0; a rerun of the same command goes on from there. Before the passphrase
is asked for, `--apply` prints how many targets it will land at most and the
contributions that adds (two per landed target: the pull request and its squash commit),
so a run can be sized to the day's contribution budget. The dry run prints the same.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import land_staged_workflow as lsw
from _pat_session import classic_pat_session

EXPECTS = ("success", "skipped")
ACTIONS = ("replace", "delete")
BLOB = re.compile(r"^[0-9a-f]{40}$")
TITLE_MAX = 256
#: What one landed target adds to the day's GitHub contribution count: the pull request,
#: and the squash commit on `main`. The branch's own commits never reach `main`.
CONTRIBUTIONS_PER_TARGET = 2


class PlanError(SystemExit):
    """The plan is malformed; raised before any credential is asked for."""


class LandingStop(Exception):
    """One target cannot land; the run stops here."""

    def __init__(self, repo: str, step: str, message: str):
        super().__init__(f"{repo}: {step}: {message}")
        self.repo, self.step, self.message = repo, step, message


def is_delete(f: dict) -> bool:
    return f.get("action") == "delete"


def _validate_file(fw: str, f: object) -> None:
    if not isinstance(f, dict):
        raise PlanError(f"{fw}: not an object")
    action = f.get("action", "replace")
    if action not in ACTIONS:
        raise PlanError(f"{fw}: `action` is {action!r}, not one of {ACTIONS}")
    if action == "delete":
        for key in ("staged", "expect"):
            if key in f:
                raise PlanError(f"{fw}: a delete entry carries `{key}`; it takes only "
                                "`workflow` and `base_blob`")
        required: tuple[str, ...] = ("workflow", "base_blob")
    else:
        required = ("staged", "workflow", "base_blob", "expect")
    for key in required:
        if not isinstance(f.get(key), str) or not f[key]:
            raise PlanError(f"{fw}: `{key}` is missing")
    wf = f["workflow"]
    if not wf.startswith(".github/workflows/") or not wf.endswith((".yml", ".yaml")):
        raise PlanError(f"{fw}: `workflow` is not a file under .github/workflows/")
    if not BLOB.match(f["base_blob"]):
        raise PlanError(f"{fw}: `base_blob` is not a 40-character git blob sha")
    if action == "replace" and f["expect"] not in EXPECTS:
        raise PlanError(f"{fw}: `expect` is {f['expect']!r}, not one of {EXPECTS}")


def validate_plan(plan: object) -> dict:
    """Return the plan if it is well formed; raise PlanError naming the first fault.

    `source` is required while any entry replaces a workflow, since the staged copies
    live there; a plan whose every entry is a delete needs none (#4721).
    """
    if not isinstance(plan, dict):
        raise PlanError("plan: the top level is not an object")
    reason = plan.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise PlanError("plan: `reason` is missing")
    targets = plan.get("targets")
    if not isinstance(targets, list) or not targets:
        raise PlanError("plan: `targets` is missing or empty")
    seen: set[str] = set()
    for i, t in enumerate(targets):
        where = f"plan: targets[{i}]"
        if not isinstance(t, dict) or not isinstance(t.get("repo"), str) or not t["repo"]:
            raise PlanError(f"{where}: `repo` is missing")
        if "/" in t["repo"]:
            raise PlanError(f"{where}: `repo` is a name, not owner/name")
        if t["repo"] in seen:
            raise PlanError(f"{where}: {t['repo']} appears twice")
        seen.add(t["repo"])
        if not isinstance(t.get("issue"), int) or isinstance(t["issue"], bool) or t["issue"] <= 0:
            raise PlanError(f"{where} ({t['repo']}): `issue` is not a positive integer")
        files = t.get("files")
        if not isinstance(files, list) or not files:
            raise PlanError(f"{where} ({t['repo']}): `files` is missing or empty")
        workflows: set[str] = set()
        for j, f in enumerate(files):
            fw = f"{where} ({t['repo']}) files[{j}]"
            _validate_file(fw, f)
            if f["workflow"] in workflows:
                raise PlanError(f"{fw}: {f['workflow']} appears twice")
            workflows.add(f["workflow"])
    needs_source = any(not is_delete(f) for t in targets for f in t["files"])
    source = plan.get("source")
    if source is None and not needs_source:
        return plan
    if not isinstance(source, dict) or not isinstance(source.get("repo"), str) or not source["repo"]:
        raise PlanError("plan: `source.repo` is missing")
    source.setdefault("ref", "main")
    if source["repo"].lower() in reason.lower():
        raise PlanError("plan: `reason` names the source repository, and every target's "
                        "pull request body carries it")
    return plan


def load_plan(path: Path) -> dict:
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PlanError(f"plan: cannot read {path}: {exc}") from exc
    return validate_plan(plan)


def target_cfg(owner: str, target: dict, merge_on_red: bool) -> SimpleNamespace:
    """The attribute bag the single-repository lander's functions read."""
    return SimpleNamespace(
        owner=owner, repo=target["repo"], issue=target["issue"],
        branch=f"ci/staged-workflow-{target['issue']}", workflow=None,
        replace=True, keep_staged=True, merge_on_red=merge_on_red, check=None,
    )


def pr_title(workflows: list[str], issue: int, removed: list[str] | tuple = ()) -> str:
    parts = []
    if workflows:
        parts.append("update " + ", ".join(Path(w).name for w in workflows))
    if removed:
        parts.append("remove " + ", ".join(Path(w).name for w in removed))
    title = f"ci: {'; '.join(parts)} (Closes #{issue})"
    if len(title) > TITLE_MAX:
        verb = "change" if workflows and removed else ("update" if workflows else "remove")
        title = f"ci: {verb} {len(workflows) + len(removed)} workflows (Closes #{issue})"
    return title


_PAT_NOTE = (
    "Landed via the classic-PAT Contents API (ADR-0216) because the fine-grained PAT every "
    "agent session uses cannot push under `.github/workflows/` -- it lacks the `workflow` "
    "scope, and that exclusion is load-bearing. "
)


def pr_body(reason: str, workflows: list[str], issue: int,
            removed: list[str] | tuple = ()) -> str:
    changed = "\n".join(f"- `{w}`" for w in workflows)
    if not removed:
        return (
            f"Closes #{issue}\n\n{reason.strip()}\n\nChanged:\n\n{changed}\n\n" + _PAT_NOTE
            + "Each file was built from the live blob on `main` that the plan names, and the "
            "lander refuses a file whose `main` has moved since.\n"
        )
    gone = "\n".join(f"- `{w}`" for w in removed)
    return (
        f"Closes #{issue}\n\n{reason.strip()}\n\n"
        + (f"Changed:\n\n{changed}\n\n" if workflows else "")
        + f"Removed:\n\n{gone}\n\n" + _PAT_NOTE
        + "Each file is changed or removed at the live blob on `main` that the plan names, "
        "the lander refuses a file whose `main` has moved since, and it reads `main` back "
        "after the merge to confirm each removed file is gone.\n"
    )


def verdict(conclusion: str, expect: str, merge_on_red: bool) -> bool:
    """True when a finished run lets the merge go ahead."""
    if conclusion in ("in_progress", "no_run"):
        return False
    return conclusion == expect or merge_on_red


def _decode(rec: dict) -> str:
    return base64.b64decode(rec["content"]).decode("utf-8")


def read_copy(pat: str, src: SimpleNamespace, path: str, ref: str, repo: str) -> str:
    rec = lsw.get_file(pat, src, path, ref)
    if rec is None:
        raise LandingStop(repo, "read", f"the staged copy {path} is not on the source's {ref}")
    text = _decode(rec)
    if "\r" in text:
        raise LandingStop(repo, "read", f"the staged copy {path} holds a carriage return")
    return text


def repo_facts(pat: str, owner: str, repo: str) -> dict:
    r = lsw.requests.get(f"{lsw.GH_API}/repos/{owner}/{repo}", headers=lsw._headers(pat),
                         timeout=lsw.HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.json()


def preflight(pat: str, plan: dict, targets: list[dict], owner: str) -> None:
    """Every target's repository is read before any write (see the module docstring)."""
    private, public = [], []
    for t in targets:
        facts = repo_facts(pat, owner, t["repo"])
        if facts.get("default_branch") != "main":
            raise LandingStop(t["repo"], "preflight",
                              f"default branch is {facts.get('default_branch')!r}, not main")
        (private if facts.get("private") else public).append(t["repo"])
    named = [n for n in private
             if re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", plan["reason"])]
    if public and named:
        raise LandingStop(named[0], "preflight",
                          f"the plan's reason names the private target(s) {named}, and "
                          f"{len(public)} target(s) are public")


def open_pr(pat: str, cfg: SimpleNamespace, title: str, body: str) -> int:
    r = lsw.requests.get(
        lsw._repo_url(cfg, "pulls"),
        params={"head": f"{cfg.owner}:{cfg.branch}", "state": "open"},
        headers=lsw._headers(pat), timeout=lsw.HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    if r.json():
        num = r.json()[0]["number"]
        print(f"  reusing open PR #{num}")
        return num
    r = lsw.requests.post(
        lsw._repo_url(cfg, "pulls"), headers=lsw._headers(pat), timeout=lsw.HTTP_TIMEOUT_S,
        json={"title": title, "head": cfg.branch, "base": "main", "body": body},
    )
    r.raise_for_status()
    num = r.json()["number"]
    print(f"  opened PR #{num}")
    return num


def land_target(
    pat: str,
    plan: dict,
    target: dict,
    owner: str,
    merge_on_red: bool,
    *,
    wait: Callable[..., lsw.WaitResult] | None = None,
) -> str:
    """Land one target; return "landed" or "already". Raise LandingStop on any fault."""
    wait = wait or lsw.wait_for_workflow
    repo = target["repo"]
    cfg = target_cfg(owner, target, merge_on_red)
    source = plan.get("source")
    src = SimpleNamespace(owner=owner, repo=source["repo"]) if source else None
    ref = source["ref"] if source else None
    pending: list[tuple[dict, str]] = []
    deletes: list[dict] = []
    for f in target["files"]:
        cfg.workflow = f["workflow"]
        live_rec = lsw.get_file(pat, cfg, f["workflow"], "main")
        if is_delete(f):
            if live_rec is None:
                print(f"  {f['workflow']}: already absent on main")
                continue
            if live_rec["sha"] != f["base_blob"]:
                raise LandingStop(repo, "base", (
                    f"{f['workflow']} on main is blob {live_rec['sha'][:10]}, not the plan's "
                    f"{f['base_blob'][:10]}: main moved after the plan was made. Re-read it."))
            deletes.append(f)
            continue
        if live_rec is None:
            raise LandingStop(repo, "read", f"{f['workflow']} is not on main")
        copy = read_copy(pat, src, f["staged"], ref, repo)
        if _decode(live_rec) == copy:
            print(f"  {f['workflow']}: main already holds the staged copy")
            continue
        if live_rec["sha"] != f["base_blob"]:
            raise LandingStop(repo, "base", (
                f"{f['workflow']} on main is blob {live_rec['sha'][:10]}, not the plan's "
                f"{f['base_blob'][:10]}: main moved after the copy was made. Restage it."))
        pending.append((f, copy))
    if not pending and not deletes:
        return "already"
    names = [lsw.workflow_name(copy, None) for _, copy in pending]
    if len(set(names)) != len(names):
        raise LandingStop(repo, "read", f"two changed workflows share a name: {names}")

    lsw.ensure_branch(pat, cfg, lsw.main_sha(pat, cfg))
    for f, copy in pending:
        cfg.workflow = f["workflow"]
        lsw.put_workflow(pat, cfg, copy)
    for f in deletes:
        remove_workflow(pat, cfg, f)
    workflows = [f["workflow"] for f, _ in pending]
    removed = [f["workflow"] for f in deletes]
    num = open_pr(pat, cfg, pr_title(workflows, cfg.issue, removed),
                  pr_body(plan["reason"], workflows, cfg.issue, removed))

    # A removed workflow starts no run of its own, so only replaced ones are waited for.
    sha = lsw.head_sha(pat, cfg, num) if pending else None
    for (f, _), name in zip(pending, names):
        print(f"  waiting for workflow `{name}` on PR #{num} ...")
        result = wait(pat, cfg, sha, name)
        print(f"  `{name}`: {result.conclusion} (the plan expects {f['expect']})"
              + (f" -- {result.url}" if result.url else ""))
        if not verdict(result.conclusion, f["expect"], merge_on_red):
            raise LandingStop(repo, "wait", (
                f"`{name}` ended `{result.conclusion}`, the plan expects `{f['expect']}`. "
                f"Nothing is merged; PR #{num} and branch {cfg.branch} are left as they are."))
    if not lsw.wait_mergeable(pat, cfg, num):
        raise LandingStop(repo, "merge", f"PR #{num} did not reach a mergeable state")
    lsw.merge_pr(pat, cfg, num)
    lsw.delete_branch(pat, cfg)
    for wf in removed:
        if lsw.get_file(pat, cfg, wf, "main") is not None:
            raise LandingStop(repo, "verify", (
                f"{wf} is still on main after PR #{num} merged; the removal did not land."))
        print(f"  {wf}: confirmed absent on main")
    return "landed"


def remove_workflow(pat: str, cfg: SimpleNamespace, f: dict) -> bool:
    """Delete one workflow on the target's branch; False when the branch already lacks it.

    A rerun after a stop finds the branch already without the file, and a second DELETE
    would fail, so it is skipped, as `put_workflow` skips an identical PUT.
    """
    wf = f["workflow"]
    on_branch = lsw.get_file(pat, cfg, wf, cfg.branch)
    if on_branch is None:
        print(f"  {wf} already absent on {cfg.branch} -- no commit")
        return False
    if on_branch["sha"] != f["base_blob"]:
        raise LandingStop(cfg.repo, "delete", (
            f"{wf} on {cfg.branch} is blob {on_branch['sha'][:10]}, not the plan's "
            f"{f['base_blob'][:10]}: the branch holds another version. Nothing is removed."))
    r = lsw.requests.delete(
        lsw._repo_url(cfg, f"contents/{wf}"), headers=lsw._headers(pat),
        timeout=lsw.HTTP_TIMEOUT_S,
        json={"message": f"ci: remove {Path(wf).name} (Closes #{cfg.issue})",
              "sha": f["base_blob"], "branch": cfg.branch},
    )
    r.raise_for_status()
    print(f"  removed {wf} on {cfg.branch}")
    return True


def select(plan: dict, only: list[str] | None) -> list[dict]:
    targets = plan["targets"]
    if not only:
        return targets
    names = {t["repo"] for t in targets}
    missing = [o for o in only if o not in names]
    if missing:
        raise PlanError(f"--only names {missing}, which the plan does not hold")
    return [t for t in targets if t["repo"] in only]


def budget(targets: list[dict], max_targets: int | None) -> tuple[int, int]:
    """(targets this run lands at most, the contributions that adds at most).

    A target already done is skipped and not counted, so a run lands at most
    `max_targets` of them, and every target when no cap is given.
    """
    most = len(targets) if max_targets is None else min(len(targets), max_targets)
    return most, CONTRIBUTIONS_PER_TARGET * most


def print_budget(targets: list[dict], max_targets: int | None) -> None:
    most, contributions = budget(targets, max_targets)
    cap = "" if max_targets is None else f" (--max-targets {max_targets})"
    print(f"  will land: at most {most} of {len(targets)} target(s){cap}; a target "
          "already done is skipped and not counted")
    print(f"  adds     : at most {contributions} contributions ({CONTRIBUTIONS_PER_TARGET} "
          "per landed target: the pull request and its squash commit)")


def dry_run(plan: dict, targets: list[dict], owner: str, merge_on_red: bool,
            max_targets: int | None = None) -> int:
    print("DRY-RUN -- no credentials requested, no writes performed.\n")
    src = plan.get("source")
    if src:
        print(f"  source   : {owner}/{src['repo']} @ {src['ref']} (staged copies)")
    else:
        print("  source   : none (every entry is a delete)")
    print(f"  targets  : {len(targets)}, files: {sum(len(t['files']) for t in targets)}")
    print(f"  on red   : {'merge anyway' if merge_on_red else 'stop the run'}")
    print_budget(targets, max_targets)
    print()
    for t in targets:
        print(f"  {owner}/{t['repo']}  PR closes #{t['issue']}  branch ci/staged-workflow-{t['issue']}")
        for f in t["files"]:
            if is_delete(f):
                print(f"      delete {f['workflow']} base {f['base_blob'][:10]}")
                continue
            print(f"      {f['workflow']}  <- {f['staged']}  base {f['base_blob'][:10]}  "
                  f"expects `{f['expect']}`")
    return 0


def run(
    plan: dict,
    targets: list[dict],
    owner: str,
    merge_on_red: bool,
    *,
    max_targets: int | None = None,
    session: Callable | None = None,
    land: Callable[..., str] = land_target,
) -> int:
    session = session or classic_pat_session
    landed: list[str] = []
    already: list[str] = []
    current = "preflight"
    capped = False

    # Printed before the session opens, so before the passphrase is asked for.
    print(f"Landing a workflow plan across {len(targets)} target(s).")
    print_budget(targets, max_targets)

    def stopped(exc: BaseException) -> None:
        done = len(landed) + len(already)
        print(f"\nSTOPPED at {current}: {exc}", file=sys.stderr)
        print(f"  landed {len(landed)}, already landed {len(already)}, not landed "
              f"{len(targets) - done} of {len(targets)}. Rerun the same command once the "
              f"cause is fixed; landed targets are skipped.", file=sys.stderr)

    with session(reason=f"land a workflow plan across {len(targets)} repositories") as pat:
        try:
            preflight(pat, plan, targets, owner)
            for t in targets:
                if max_targets is not None and len(landed) >= max_targets:
                    capped = True
                    break
                current = t["repo"]
                print(f"\n{owner}/{t['repo']} (#{t['issue']}) ...")
                outcome = land(pat, plan, t, owner, merge_on_red)
                (landed if outcome == "landed" else already).append(t["repo"])
                print(f"  {outcome}")
        except (LandingStop, requests.RequestException) as exc:
            stopped(exc)
            return 1
        except Exception as exc:
            stopped(exc)
            raise
    if capped:
        done = len(landed) + len(already)
        print(f"\nStopped at --max-targets {max_targets}: landed {len(landed)}, already "
              f"landed {len(already)}, not reached {len(targets) - done} of {len(targets)}. "
              "Rerun the same command to go on; landed targets are skipped.")
        return 0
    print(f"\nDone: landed {len(landed)}, already landed {len(already)}, of {len(targets)}.")
    return 0


def _positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be 1 or more, not {value}")
    return value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plan", required=True, type=Path, help="Path to the plan's JSON file.")
    ap.add_argument("--apply", action="store_true",
                    help="Land the plan. Without it: a dry run, no credential, no writes.")
    ap.add_argument("--merge-on-red", action="store_true",
                    help="Merge when a run ends other than the plan expects. Default: stop.")
    ap.add_argument("--only", action="append", default=None, metavar="REPO",
                    help="Limit the run to this target of the plan (repeatable).")
    ap.add_argument("--max-targets", type=_positive, default=None, metavar="N",
                    help="Land at most N targets not already done, then stop; a rerun "
                         "goes on from there.")
    ap.add_argument("--owner", default=lsw.DEFAULT_OWNER)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan = load_plan(args.plan)
    targets = select(plan, args.only)
    if not args.apply:
        return dry_run(plan, targets, args.owner, args.merge_on_red, args.max_targets)
    return run(plan, targets, args.owner, args.merge_on_red, max_targets=args.max_targets)


if __name__ == "__main__":
    sys.exit(main())
