"""#4750: the dependabot nightly acts only on public repositories.

On a private repository every approval and merge, and every @dependabot
rebase or recreate, runs workflows that spend GitHub Actions minutes. The
operator ruled on 2026-11-13 that this stays off until December, and that
public repositories may go ahead. These tests drive main() over a fleet of
one public and one private repository, with the real process_repo and
process_pr, and every action helper recorded with the repository it names.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# Load the tools/ script as a module without polluting sys.path, as
# test_dependabot_review.py does.
TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "dependabot_review", TOOLS_DIR / "dependabot_review.py"
)
dr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dr)

# #4743: no test here may start `gh`, or git against a network remote.
pytestmark = pytest.mark.usefixtures("no_network_commands")

PUBLIC = "o/public"
PRIVATE = "o/private"
SKIP_LABEL = "Skipped (private, #4750)"

# The helpers that act on a PR or read its state, each recorded with the
# repository it was called for. All but list_dependabot_prs and
# has_automated_review take (number or pr, repo, ...).
_ACTIONS = {
    "approve_pr": True,
    "squash_merge": True,
    "wait_for_mergeable": True,
    "comment_on_pr": None,
    "review_comment_on_pr": True,
    "request_dependabot_rebase": None,
    "request_dependabot_recreate": None,
    "inject_no_issue": True,
    "is_pr_branch_stale": False,
    "already_deferred_at_head": False,
}


def _pr(number: int = 1) -> dr.PRInfo:
    return dr.PRInfo(
        number=number, title=f"bump p{number}", author_login="app/dependabot",
        body="", head_ref=f"dependabot/pip/p{number}", head_oid="sha-a",
        created_at="2026-11-01T00:00:00Z",
    )


@contextmanager
def _fleet(tmp_path: Path, extra_argv: list[str], *,
           listed_visibility: dict[str, str | None],
           view_results: dict[str, tuple[int, str, str]] | None = None,
           fleet: bool = True, repo: str = PUBLIC):
    """Run main() with no network. ``listed_visibility`` is what the fleet
    listing reports per repository (None leaves the field out);
    ``view_results`` is what ``gh repo view`` returns per repository."""
    view_results = view_results or {}
    calls: list[tuple[str, str]] = []
    gh_cmds: list[list[str]] = []
    main_repo = tmp_path / "main"
    (main_repo / ".git").mkdir(parents=True)

    def fake_run(cmd, *args, **kwargs):
        gh_cmds.append(list(cmd))
        if cmd[:3] == ["gh", "repo", "list"]:
            rows = []
            for name, vis in listed_visibility.items():
                row = {"name": name.split("/")[1], "nameWithOwner": name,
                       "isArchived": False, "isFork": False}
                if vis is not None:
                    row["visibility"] = vis
                rows.append(row)
            return subprocess.CompletedProcess(cmd, 0, json.dumps(rows), "")
        if cmd[:3] == ["gh", "search", "prs"]:
            rows = [{"repository": {"nameWithOwner": n}}
                    for n in listed_visibility]
            return subprocess.CompletedProcess(cmd, 0, json.dumps(rows), "")
        if cmd[:3] == ["gh", "repo", "view"]:
            code, out, err = view_results[cmd[3]]
            return subprocess.CompletedProcess(cmd, code, out, err)
        raise AssertionError(f"command this test does not expect: {cmd}")

    def recorder(name, result):
        def fake(*args, **kwargs):
            target = args[1] if len(args) > 1 else kwargs.get("repo")
            calls.append((name, str(target)))
            return result
        return fake

    def fake_list_prs(repo_full):
        calls.append(("list_dependabot_prs", repo_full))
        return [_pr()]

    def fake_has_review(pr, repo_full):
        calls.append(("has_automated_review", repo_full))
        return False

    def fake_target(repo_full, default_parent):
        path = tmp_path / "clones" / repo_full.split("/")[1]
        path.mkdir(parents=True, exist_ok=True)
        return path

    def fake_create(target_repo, number):
        worktree = tmp_path / "wt" / f"{target_repo.name}-{number}"
        worktree.mkdir(parents=True, exist_ok=True)
        return worktree, f"dependabot-audit-{number}"

    def fake_tests(worktree):
        calls.append(("run_tests_detailed", worktree.name))
        return 0, "1 passed"

    argv = ["dependabot_review.py", "--main-repo", str(main_repo),
            "--no-run-log"]
    argv += ["--fleet"] if fleet else ["--repo", repo]
    argv += extra_argv
    with ExitStack() as stack:
        def stub(name, **kwargs):
            return stack.enter_context(patch.object(dr, name, **kwargs))

        stack.enter_context(patch.object(sys, "argv", argv))
        stub("IN_FLIGHT_LEDGER", new=tmp_path / "ledger" / "in-flight.json")
        stub("guard_not_worktree")
        stub("_force_utf8_streams")
        stub("setup_run_log")
        stub("run", side_effect=fake_run)
        stub("list_dependabot_prs", side_effect=fake_list_prs)
        stub("has_automated_review", side_effect=fake_has_review)
        stub("resolve_target_repo_dir", side_effect=fake_target)
        stub("check_for_orphan_worktrees", return_value=[])
        stub("create_audit_worktree", side_effect=fake_create)
        stub("cleanup_worktree", return_value=True)
        stub("checkout_pr_into_worktree", return_value=True)
        stub("_pr_changed_files", return_value=["poetry.lock"])
        stub("fake_root_guard_gap", return_value=([], ""))
        stub("evict_poetry_venv")
        stub("install_deps", return_value=True)
        stub("run_tests_detailed", side_effect=fake_tests)
        stub("run_baseline_gate", return_value=(0, ""))
        for name, result in _ACTIONS.items():
            stub(name, side_effect=recorder(name, result))
        stub("alert_operator")
        stack.enter_context(patch.object(dr.time, "sleep"))
        yield SimpleNamespace(calls=calls, gh_cmds=gh_cmds)


def _touched(calls: list[tuple[str, str]], repo: str) -> list[str]:
    """Every recorded call that acted on, listed or tested ``repo``."""
    short = repo.split("/")[1]
    return [name for name, target in calls
            if target == repo or target.startswith(f"{short}-")]


def _summary_lists(out: str) -> dict[str, list[str]]:
    """The lists the Summary printed, keyed by the label before the colon."""
    assert out.count("=== Summary ===") == 1, "expected exactly one Summary"
    section = out.split("=== Summary ===", 1)[1]
    lists: dict[str, list[str]] = {}
    for line in section.splitlines():
        stripped = line.strip()
        if "[" in stripped and stripped.endswith("]"):
            label = stripped.split(":", 1)[0]
            lists[label] = ast.literal_eval(stripped[stripped.index("["):])
    return lists


def _skip_lines(out: str, repo: str) -> list[str]:
    return [ln for ln in out.splitlines()
            if ln.strip().startswith(f"[SKIP] {repo}:")]


# ---------------------------------------------------------------------------
# #4750 test 1: the public repository is processed, the private one untouched
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("extra_argv", [
    pytest.param(["--workers", "3"], id="worker-pool"),
    pytest.param(["--workers", "1"], id="sequential"),
    pytest.param(["--limit", "5"], id="pre-pass-and-limit"),
])
def test_private_repo_gets_no_review_comment_merge_or_test(tmp_path, capsys,
                                                          extra_argv):
    with _fleet(tmp_path, extra_argv,
                listed_visibility={PUBLIC: "PUBLIC",
                                   PRIVATE: "PRIVATE"}) as h:
        dr.main()
    out = capsys.readouterr().out

    # The public repository went through the whole merge path.
    public = _touched(h.calls, PUBLIC)
    for name in ("list_dependabot_prs", "run_tests_detailed", "approve_pr",
                 "wait_for_mergeable", "squash_merge"):
        assert name in public, (name, public)
    # The private one was not even listed.
    assert _touched(h.calls, PRIVATE) == []
    assert not [c for c in h.gh_cmds if PRIVATE in c
                and c[:3] != ["gh", "repo", "list"]]
    assert _summary_lists(out)["Merged"] == [f"{PUBLIC}#1"]
    assert len(_skip_lines(out, PRIVATE)) == 1
    assert "visibility is PRIVATE" in _skip_lines(out, PRIVATE)[0]
    assert f"REPO: {PRIVATE}" not in out


def test_repo_mode_skips_a_private_repo(tmp_path, capsys):
    with _fleet(tmp_path, [], listed_visibility={}, fleet=False, repo=PRIVATE,
                view_results={PRIVATE: (0, "PRIVATE\n", "")}) as h:
        dr.main()
    out = capsys.readouterr().out

    assert _touched(h.calls, PRIVATE) == []
    assert len(_skip_lines(out, PRIVATE)) == 1
    assert _summary_lists(out)[SKIP_LABEL] == [PRIVATE]


# ---------------------------------------------------------------------------
# #4750 test 2: a visibility that cannot be read means skipped, reason printed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fleet", [
    pytest.param(True, id="fleet-listing-without-visibility"),
    pytest.param(False, id="repo-mode"),
])
def test_unreadable_visibility_skips_the_repo_and_says_why(tmp_path, capsys,
                                                         fleet):
    failed = (1, "", "HTTP 502: Bad Gateway")
    with _fleet(tmp_path, ["--workers", "1"], fleet=fleet, repo=PRIVATE,
                listed_visibility={PUBLIC: "PUBLIC", PRIVATE: None},
                view_results={PRIVATE: failed}) as h:
        dr.main()
    out = capsys.readouterr().out

    assert _touched(h.calls, PRIVATE) == []
    lines = _skip_lines(out, PRIVATE)
    assert len(lines) == 1, lines
    assert "visibility could not be read" in lines[0]
    assert "HTTP 502: Bad Gateway" in lines[0]
    assert "treated as private" in lines[0]
    assert _summary_lists(out)[SKIP_LABEL] == [PRIVATE]


# ---------------------------------------------------------------------------
# #4750 test 3: the switch on means the private repository is processed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("how", ["flag", "constant"])
def test_switch_on_processes_the_private_repo(tmp_path, capsys, how):
    extra = ["--workers", "1"] + (["--include-private"] if how == "flag"
                                  else [])
    with ExitStack() as stack:
        if how == "constant":
            stack.enter_context(
                patch.object(dr, "INCLUDE_PRIVATE_REPOS", True))
        h = stack.enter_context(_fleet(
            tmp_path, extra,
            listed_visibility={PUBLIC: "PUBLIC", PRIVATE: "PRIVATE"}))
        dr.main()
    out = capsys.readouterr().out

    private = _touched(h.calls, PRIVATE)
    for name in ("run_tests_detailed", "approve_pr", "squash_merge"):
        assert name in private, (name, private)
    assert _skip_lines(out, PRIVATE) == []
    lists = _summary_lists(out)
    assert sorted(lists["Merged"]) == [f"{PRIVATE}#1", f"{PUBLIC}#1"]
    assert SKIP_LABEL not in lists


def test_the_switch_defaults_off():
    assert dr.INCLUDE_PRIVATE_REPOS is False


# ---------------------------------------------------------------------------
# #4750 test 4: the zero-review pre-pass skips a private repository's PR
# ---------------------------------------------------------------------------

def test_prepass_skips_a_private_repos_pr(tmp_path, capsys):
    with _fleet(tmp_path, ["--limit", "5"],
                listed_visibility={PUBLIC: "PUBLIC",
                                   PRIVATE: "PRIVATE"}) as h:
        dr.main()
    out = capsys.readouterr().out

    prepass = out.split("Zero-review pre-pass", 1)[1].split("PRE-PASS REPO", 1)[0]
    assert f"{PUBLIC}#1" in prepass
    assert PRIVATE not in prepass
    assert f"PRE-PASS REPO: {PUBLIC}" in out
    assert f"PRE-PASS REPO: {PRIVATE}" not in out
    # The pre-pass never even read the private repository's reviews.
    assert ("has_automated_review", PRIVATE) not in h.calls
    assert ("has_automated_review", PUBLIC) in h.calls


# ---------------------------------------------------------------------------
# #4750 test 5: the Summary lists the skipped private repositories
# ---------------------------------------------------------------------------

def test_summary_lists_skipped_private_repos_apart(tmp_path, capsys):
    other = "o/private-two"
    with _fleet(tmp_path, ["--workers", "1"],
                listed_visibility={PUBLIC: "PUBLIC", PRIVATE: "PRIVATE",
                                   other: "INTERNAL"}):
        dr.main()
    out = capsys.readouterr().out

    lists = _summary_lists(out)
    assert lists[SKIP_LABEL] == [PRIVATE, other]
    assert lists["Merged"] == [f"{PUBLIC}#1"]
    for label in ("Merged", "Deferred", "Errored"):
        assert PRIVATE not in " ".join(lists[label])
        assert other not in " ".join(lists[label])
    # The skipped list sits inside the Summary, after the outcome lists.
    summary = out.split("=== Summary ===", 1)[1]
    assert summary.index("Errored") < summary.index(SKIP_LABEL)


def test_fleet_listing_visibility_needs_no_second_call(tmp_path, capsys):
    """R2: visibility is read in each run, from the fleet listing when it has
    it, so a listed repository costs no gh repo view."""
    with _fleet(tmp_path, ["--workers", "1"],
                listed_visibility={PUBLIC: "PUBLIC",
                                   PRIVATE: "PRIVATE"}) as h:
        dr.main()
    capsys.readouterr()
    assert not [c for c in h.gh_cmds if c[:3] == ["gh", "repo", "view"]]
    # main() starts each run from an empty record.
    assert dr._REPO_VISIBILITY == {PUBLIC: "PUBLIC", PRIVATE: "PRIVATE"}
    dr._REPO_VISIBILITY["o/stale"] = "PUBLIC"
    with _fleet(tmp_path / "again", ["--workers", "1"],
                listed_visibility={PUBLIC: "PUBLIC"}):
        dr.main()
    capsys.readouterr()
    assert "o/stale" not in dr._REPO_VISIBILITY
