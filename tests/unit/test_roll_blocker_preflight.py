"""Acceptance tests for the roll-blocker launch gate (#2436).

The operator's 2026-08-15 ruling is the specification: refuse when an open
`roll-blocker` exists in EITHER the target repo or AssemblyZero, let
``--ignore-blockers`` override it explicitly, leave a trace in the launch record
when it is used, and print the result on every launch including the clean case.

The gate is exercised through `speedrun_roll.main` wherever the claim is about
the launcher's behaviour, so "nothing is spent" and "the refusal beats the
detach hand-off" are assertions about what the launcher did rather than claims
about a helper.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import speedrun_roll  # noqa: E402

from assemblyzero.speedrun.roll_blockers import (  # noqa: E402
    OVERRIDE_FLAG,
    ROLL_BLOCKER_LABEL,
    Blocker,
    BlockerScan,
    blocker_refusal_message,
    blocker_report_lines,
    blocker_trace_line,
    scan_roll_blockers,
)

TARGET = "martymcenroe/boostgauge"
AZ = "martymcenroe/AssemblyZero"

IN_TARGET = Blocker(TARGET, 341, "the renderer writes no PNG, so every roll ships blind")
IN_AZ = Blocker(AZ, 2311, "the resume gate reads a spec the reset already cleared")


def scan(*blockers: Blocker, errors: tuple[str, ...] = ()) -> BlockerScan:
    return BlockerScan(tuple(blockers), (TARGET, AZ), errors)


class FakeGh:
    """A `gh`/`git` runner with a distinct board per repository.

    Keyed by checkout path for the remote lookups and by slug for the issue
    lists, so the two-repo behaviour can be exercised without a network.
    """

    def __init__(
        self,
        *,
        remotes: dict[str, str] | None = None,
        boards: dict[str, list[dict]] | None = None,
        fails: tuple[str, ...] = (),
    ) -> None:
        self.remotes = remotes or {}
        self.boards = boards or {}
        self.fails = fails
        self.calls: list[list[str]] = []

    def __call__(self, args):
        self.calls.append(list(args))
        if args[0] == "git":
            root = args[args.index("-C") + 1]
            url = self.remotes.get(str(root))
            if not url:
                return subprocess.CompletedProcess(args, 1, "", "no remote")
            return subprocess.CompletedProcess(args, 0, url, "")
        if args[0] == "gh":
            slug = args[args.index("--repo") + 1]
            if slug in self.fails:
                return subprocess.CompletedProcess(
                    args, 1, "", "could not connect to github.com"
                )
            rows = self.boards.get(slug, [])
            return subprocess.CompletedProcess(args, 0, json.dumps(rows), "")
        return subprocess.CompletedProcess(args, 0, "", "")


@pytest.fixture
def target_repo(tmp_path) -> Path:
    """The launcher validates --repo is a git repository root before the gate."""
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "Test"],
    ):
        subprocess.run(["git", "-C", str(tmp_path), *args], capture_output=True, text=True)
    (tmp_path / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-qm", "base"], capture_output=True
    )
    return tmp_path


@pytest.fixture
def launcher(monkeypatch, target_repo):
    """speedrun_roll.main with everything past the gate stubbed out."""
    state = {"rolls": [], "detached": 0, "base_calls": 0}

    monkeypatch.setattr(speedrun_roll, "check_assemblyzero_tree", lambda _root: [])
    monkeypatch.setattr(
        speedrun_roll, "sweep_pipeline_worktrees",
        lambda *_a, **_k: type("Sweep", (), {"problems": []})(),
    )
    monkeypatch.setattr(speedrun_roll, "install_signal_handlers", lambda _s: None)
    # The sibling gate is not under test here; it must never be what refuses.
    monkeypatch.setattr(
        speedrun_roll, "open_must_resolve_issues", lambda _r: ([], None)
    )

    def fake_roll(repo_root, issue, log_dir, az_root, extra):
        state["rolls"].append(issue)
        return 0

    def fake_ensure_base(*_a, **_kw):
        state["base_calls"] += 1
        return "hardening-run-1"

    def fake_detach(*_a, **_kw):
        state["detached"] += 1
        return 0

    monkeypatch.setattr(speedrun_roll, "roll_issue", fake_roll)
    monkeypatch.setattr(speedrun_roll, "ensure_base", fake_ensure_base)
    monkeypatch.setattr(speedrun_roll, "launch_detached", fake_detach)
    return state


def _argv(target_repo, *issues, detach=False, ignore=False):
    args = ["--repo", str(target_repo), "--log-dir", str(target_repo / "logs")]
    for issue in issues:
        args += ["--issue", str(issue)]
    if detach:
        args.append("--detach")
    if ignore:
        args.append("--ignore-blockers")
    return args


def _session_log(target_repo) -> str:
    path = target_repo / "logs" / "session-events.log"
    return path.read_text(encoding="utf-8") if path.exists() else ""


# --- "surfaces every one of them, by number and title" --------------------


def test_open_blocker_refuses_with_91_naming_number_and_title(
    launcher, monkeypatch, target_repo, capsys
):
    monkeypatch.setattr(
        speedrun_roll, "scan_roll_blockers", lambda *_a, **_k: scan(IN_TARGET, IN_AZ)
    )

    code = speedrun_roll.main(_argv(target_repo, 331))

    assert code == 91
    out = capsys.readouterr().out
    assert "341" in out and "ships blind" in out
    assert "2311" in out and "already cleared" in out


def test_a_blocker_in_assemblyzero_alone_refuses(
    launcher, monkeypatch, target_repo, capsys
):
    """The roll executes both trees, so a killer in either one kills it."""
    monkeypatch.setattr(
        speedrun_roll, "scan_roll_blockers", lambda *_a, **_k: scan(IN_AZ)
    )

    code = speedrun_roll.main(_argv(target_repo, 331))

    assert code == 91
    assert "2311" in capsys.readouterr().out
    assert launcher["rolls"] == []


# --- "a launch with none prints that it checked and found none" -----------


def test_the_clean_case_says_it_checked_and_found_none(
    launcher, monkeypatch, target_repo, capsys
):
    """Silence is not evidence -- #2381's complaint about box health."""
    monkeypatch.setattr(speedrun_roll, "scan_roll_blockers", lambda *_a, **_k: scan())

    code = speedrun_roll.main(_argv(target_repo, 331))

    assert code == 0
    assert launcher["rolls"] == [331]
    out = capsys.readouterr().out
    assert "ROLL BLOCKERS" in out
    assert "none open" in out
    assert TARGET in out and AZ in out, "it must say WHICH boards it checked"


def test_the_clean_case_is_recorded_in_the_launch_record(
    launcher, monkeypatch, target_repo
):
    monkeypatch.setattr(speedrun_roll, "scan_roll_blockers", lambda *_a, **_k: scan())

    speedrun_roll.main(_argv(target_repo, 331))

    record = _session_log(target_repo)
    assert "ROLL-BLOCKERS checked" in record and "none open" in record


# --- "--ignore-blockers overrides it explicitly" --------------------------


def test_ignore_blockers_proceeds_and_names_what_it_rolled_past(
    launcher, monkeypatch, target_repo, capsys
):
    monkeypatch.setattr(
        speedrun_roll, "scan_roll_blockers", lambda *_a, **_k: scan(IN_TARGET)
    )

    code = speedrun_roll.main(_argv(target_repo, 331, ignore=True))

    assert code == 0
    assert launcher["rolls"] == [331]
    out = capsys.readouterr().out
    assert "OVERRIDDEN" in out
    assert "341" in out, "an override that does not name the blocker is silent"


def test_the_override_leaves_a_trace_in_the_launch_record(
    launcher, monkeypatch, target_repo
):
    """An override that leaves no trace is the accident the ruling stops."""
    monkeypatch.setattr(
        speedrun_roll, "scan_roll_blockers", lambda *_a, **_k: scan(IN_TARGET, IN_AZ)
    )

    speedrun_roll.main(_argv(target_repo, 331, ignore=True))

    record = _session_log(target_repo)
    assert "OVERRIDDEN" in record
    assert OVERRIDE_FLAG in record
    assert f"{TARGET}#341" in record and f"{AZ}#2311" in record


def test_the_override_rides_the_detached_relaunch():
    """Otherwise the detached run re-refuses where nothing can answer it."""
    args = speedrun_roll.build_parser().parse_args(
        ["--repo", ".", "--issue", "331", "--ignore-blockers"]
    )
    argv = speedrun_roll.detached_argv(
        args, [], Path("/repo"), Path("/az"), Path("/logs")
    )
    assert "--ignore-blockers" in argv

    without = speedrun_roll.build_parser().parse_args(["--repo", ".", "--issue", "331"])
    assert "--ignore-blockers" not in speedrun_roll.detached_argv(
        without, [], Path("/repo"), Path("/az"), Path("/logs")
    )


# --- "before the first paid model call" ----------------------------------


def test_refusal_spends_nothing_and_creates_no_branch(
    launcher, monkeypatch, target_repo
):
    monkeypatch.setattr(
        speedrun_roll, "scan_roll_blockers", lambda *_a, **_k: scan(IN_TARGET)
    )

    code = speedrun_roll.main(_argv(target_repo, 331))

    assert code == 91
    assert launcher["base_calls"] == 0, "ensure_base must not have been reached"
    assert launcher["rolls"] == []


def test_refusal_happens_before_the_detach_handoff(launcher, monkeypatch, target_repo):
    # Otherwise the refusal lands inside a scheduled task nobody is watching.
    monkeypatch.setattr(
        speedrun_roll, "scan_roll_blockers", lambda *_a, **_k: scan(IN_TARGET)
    )

    code = speedrun_roll.main(_argv(target_repo, 331, detach=True))

    assert code == 91
    assert launcher["detached"] == 0


def test_a_batch_is_refused_as_a_whole(launcher, monkeypatch, target_repo):
    monkeypatch.setattr(
        speedrun_roll, "scan_roll_blockers", lambda *_a, **_k: scan(IN_TARGET)
    )

    code = speedrun_roll.main(_argv(target_repo, 331, 332, 2))

    assert code == 91
    assert launcher["rolls"] == [], "no issue in the batch may roll"


# --- "GitHub being unreachable is reported, never fatal" ------------------


def test_an_unreachable_board_is_named_and_does_not_brick_the_launch(
    launcher, monkeypatch, target_repo, capsys
):
    monkeypatch.setattr(
        speedrun_roll, "scan_roll_blockers",
        lambda *_a, **_k: BlockerScan(
            (), (AZ,), (f"{TARGET}: could not connect to github.com",)
        ),
    )

    code = speedrun_roll.main(_argv(target_repo, 331))

    assert code == 0, "GitHub being unreachable must not brick a local roll"
    out = capsys.readouterr().out
    assert "WARNING" in out and TARGET in out


# --- the scan itself ------------------------------------------------------


def test_the_query_asks_for_open_roll_blocker_issues(tmp_path):
    gh = FakeGh(
        remotes={
            str(tmp_path / "bg"): f"https://github.com/{TARGET}.git",
            str(tmp_path / "az"): f"https://github.com/{AZ}.git",
        },
    )
    scan_roll_blockers(tmp_path / "bg", tmp_path / "az", runner=gh)

    listings = [c for c in gh.calls if c[0] == "gh"]
    assert len(listings) == 2
    for listing in listings:
        assert listing[listing.index("--label") + 1] == ROLL_BLOCKER_LABEL
        assert listing[listing.index("--state") + 1] == "open"


def test_both_boards_are_read_and_merged(tmp_path):
    gh = FakeGh(
        remotes={
            str(tmp_path / "bg"): f"https://github.com/{TARGET}.git",
            str(tmp_path / "az"): f"https://github.com/{AZ}.git",
        },
        boards={
            TARGET: [{"number": 341, "title": "target side"}],
            AZ: [{"number": 2311, "title": "pipeline side"}],
        },
    )
    result = scan_roll_blockers(tmp_path / "bg", tmp_path / "az", runner=gh)

    assert result.refuses
    assert [(b.repo, b.number) for b in result.blockers] == [
        (AZ, 2311), (TARGET, 341),
    ]
    assert result.consulted == (TARGET, AZ)
    assert result.errors == ()


def test_one_repo_rolling_itself_is_consulted_once(tmp_path):
    """AssemblyZero rolling its own issues must not list every blocker twice."""
    gh = FakeGh(
        remotes={
            str(tmp_path / "az"): f"https://github.com/{AZ}.git",
        },
        boards={AZ: [{"number": 2311, "title": "pipeline side"}]},
    )
    result = scan_roll_blockers(tmp_path / "az", tmp_path / "az", runner=gh)

    assert result.consulted == (AZ,)
    assert len(result.blockers) == 1
    assert len([c for c in gh.calls if c[0] == "gh"]) == 1


def test_an_unreachable_board_is_an_error_not_a_clean_pass(tmp_path):
    gh = FakeGh(
        remotes={
            str(tmp_path / "bg"): f"https://github.com/{TARGET}.git",
            str(tmp_path / "az"): f"https://github.com/{AZ}.git",
        },
        boards={AZ: []},
        fails=(TARGET,),
    )
    result = scan_roll_blockers(tmp_path / "bg", tmp_path / "az", runner=gh)

    assert result.errors and TARGET in result.errors[0]
    assert result.consulted == (AZ,), "a board that failed was not consulted"
    assert not result.refuses, "could-not-ask is not knowledge of a blocker"


def test_a_checkout_without_a_remote_is_reported_not_skipped_silently(tmp_path):
    gh = FakeGh(remotes={str(tmp_path / "az"): f"https://github.com/{AZ}.git"})
    result = scan_roll_blockers(tmp_path / "bg", tmp_path / "az", runner=gh)

    assert result.errors and "no GitHub remote" in result.errors[0]
    assert result.consulted == (AZ,)


def test_the_scan_costs_no_model_call(tmp_path):
    gh = FakeGh(
        remotes={
            str(tmp_path / "bg"): f"https://github.com/{TARGET}.git",
            str(tmp_path / "az"): f"https://github.com/{AZ}.git",
        },
    )
    scan_roll_blockers(tmp_path / "bg", tmp_path / "az", runner=gh)

    assert gh.calls, "the scan must actually ask something"
    assert {c[0] for c in gh.calls} <= {"git", "gh"}


def test_a_row_without_a_number_is_dropped_rather_than_crashing(tmp_path):
    gh = FakeGh(
        remotes={str(tmp_path / "az"): f"https://github.com/{AZ}.git"},
        boards={AZ: [{"title": "no number"}, {"number": 7, "title": "real"}]},
    )
    result = scan_roll_blockers(tmp_path / "az", tmp_path / "az", runner=gh)

    assert [b.number for b in result.blockers] == [7]


# --- the messages ---------------------------------------------------------


def test_the_refusal_message_is_plain_english():
    message = blocker_refusal_message(scan(IN_TARGET, IN_AZ))

    # Names them so the operator can act without looking anything up.
    assert "341" in message and "2311" in message
    assert "ships blind" in message
    # Says what to do, and that the override exists.
    assert "close" in message.lower()
    assert OVERRIDE_FLAG in message

    titles = {IN_TARGET.title, IN_AZ.title}
    prose = "\n".join(
        line for line in message.splitlines()
        if not any(t in line for t in titles)
    ).lower()
    for jargon in ("preflight", "gate", "exit 91", "#2436", "#2381", "scan",
                   "stage", "argv", "n0c"):
        assert jargon not in prose, f"{jargon!r} is internal jargon in the prose"


def test_the_refusal_message_singular_and_plural_read_correctly():
    one = blocker_refusal_message(scan(IN_TARGET))
    many = blocker_refusal_message(scan(IN_TARGET, IN_AZ))
    assert "1 known problem is open" in one
    assert "2 known problems are open" in many


def test_the_report_names_the_boards_it_checked_in_every_case():
    clean = "\n".join(blocker_report_lines(scan()))
    blocked = "\n".join(blocker_report_lines(scan(IN_TARGET)))
    for text in (clean, blocked):
        assert TARGET in text and AZ in text


def test_the_report_marks_an_override_differently_from_a_refusal():
    refused = "\n".join(blocker_report_lines(scan(IN_TARGET), overridden=False))
    overridden = "\n".join(blocker_report_lines(scan(IN_TARGET), overridden=True))
    assert "OPEN" in refused and "OVERRIDDEN" not in refused
    assert "OVERRIDDEN" in overridden


def test_the_trace_line_distinguishes_all_three_outcomes():
    clean = blocker_trace_line(scan(), overridden=False)
    refused = blocker_trace_line(scan(IN_TARGET), overridden=False)
    overridden = blocker_trace_line(scan(IN_TARGET), overridden=True)

    assert "none open" in clean
    assert "refused" in refused and "341" in refused
    assert "OVERRIDDEN" in overridden and OVERRIDE_FLAG in overridden
    assert len({clean, refused, overridden}) == 3
