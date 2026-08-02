"""Acceptance tests for N0c auto-filing must-resolve issues (#2072).

The ten tests named in the issue body are the acceptance criteria. `gh` is
never actually invoked: a fake runner records the argv it is handed, so these
assert the exact commands rather than mocking away the thing under test.
"""
from __future__ import annotations

import json
import subprocess


from assemblyzero.speedrun.must_resolve import (
    MUST_RESOLVE_LABEL,
    RUN_START_ENV,
    RUN_TAG_ENV,
    build_body,
    conflict_fingerprint,
    file_all_conflicts,
    file_must_resolve,
    normalize_criterion,
    run_context,
)

CONFLICT = {
    "criterion_a": "| Handle count | GetProcessHandleCount aggregated | Every 5s |",
    "criterion_b": "The collector runs in a background thread with configurable poll interval (default 2s).",
    "diverging_situation": "Sampling all metrics on each 2s tick polls handle count every 2s.",
}
OTHER_CONFLICT = {
    "criterion_a": "The dashboard refreshes once per minute.",
    "criterion_b": "The dashboard is real-time with sub-second updates.",
    "diverging_situation": "A viewer watching a spike sees it a minute late.",
}


class FakeGh:
    """Records argv and replays scripted responses."""

    def __init__(self, *, existing=None, fail_create_until=0, remote="https://github.com/martymcenroe/boostgauge.git"):
        self.calls: list[list[str]] = []
        self.existing = existing or []
        self.fail_create_until = fail_create_until
        self.create_attempts = 0
        self.remote = remote

    def __call__(self, args):
        self.calls.append(list(args))
        joined = " ".join(args)

        if args[0] == "git" and "remote" in args:
            if self.remote is None:
                return subprocess.CompletedProcess(args, 1, "", "no remote")
            return subprocess.CompletedProcess(args, 0, self.remote, "")

        if "issue list" in joined:
            return subprocess.CompletedProcess(args, 0, json.dumps(self.existing), "")

        if "issue create" in joined:
            self.create_attempts += 1
            if self.create_attempts <= self.fail_create_until:
                return subprocess.CompletedProcess(
                    args, 1, "", "could not add label: 'must-resolve' not found"
                )
            return subprocess.CompletedProcess(
                args, 0, "https://github.com/martymcenroe/boostgauge/issues/224\n", ""
            )

        if "issue comment" in joined:
            return subprocess.CompletedProcess(args, 0, "", "")

        if "label create" in joined:
            return subprocess.CompletedProcess(args, 0, "", "")

        return subprocess.CompletedProcess(args, 0, "", "")

    def argv_for(self, fragment):
        return [c for c in self.calls if fragment in " ".join(c)]


def _body_of(call):
    return call[call.index("--body") + 1]


# --- "a conflict verdict files an issue carrying the must-resolve label" ---


def test_conflict_files_issue_with_must_resolve_label(tmp_path):
    gh = FakeGh()
    result = file_must_resolve(tmp_path, 4, CONFLICT, run_id="run-issue4-111608",
                               run_start="2026-08-01 11:16:08", runner=gh, log=lambda _m: None)

    assert result.ok and result.action == "filed"
    assert result.issue_number == 224

    create = gh.argv_for("issue create")[0]
    assert "--label" in create
    assert create[create.index("--label") + 1] == MUST_RESOLVE_LABEL
    assert "--repo" in create
    assert create[create.index("--repo") + 1] == "martymcenroe/boostgauge"


# --- "the body contains run id, source issue, verbatim A and B, fingerprint" ---


def test_filed_body_carries_every_required_field(tmp_path):
    gh = FakeGh()
    file_must_resolve(tmp_path, 4, CONFLICT, run_id="run-issue4-111608",
                      run_start="2026-08-01 11:16:08",
                      conflict_ts="2026-08-01 11:16:38", runner=gh, log=lambda _m: None)

    body = _body_of(gh.argv_for("issue create")[0])

    assert "run-issue4-111608" in body
    assert "2026-08-01 11:16:08" in body
    assert "2026-08-01 11:16:38" in body
    assert "#4" in body
    assert CONFLICT["criterion_a"] in body, "criterion A must appear verbatim"
    assert CONFLICT["criterion_b"] in body, "criterion B must appear verbatim"
    assert CONFLICT["diverging_situation"] in body
    assert conflict_fingerprint(CONFLICT["criterion_a"], CONFLICT["criterion_b"]) in body

    title = gh.argv_for("issue create")[0]
    assert title[title.index("--title") + 1].startswith("must-resolve: #4 requirements conflict")


def test_timestamps_are_local_not_utc(tmp_path):
    gh = FakeGh()
    file_must_resolve(tmp_path, 4, CONFLICT, run_id="r", run_start="2026-08-01 11:16:08",
                      conflict_ts="2026-08-01 11:16:38", runner=gh, log=lambda _m: None)
    body = _body_of(gh.argv_for("issue create")[0])
    assert "Z" not in body.split("**Run:**")[1].split("\n")[0]
    assert "UTC" not in body


# --- "a repo without the label gets it created, retried once, succeeds" ---


def test_missing_label_is_created_and_filing_retried_once(tmp_path):
    gh = FakeGh(fail_create_until=1)

    result = file_must_resolve(tmp_path, 4, CONFLICT, runner=gh, log=lambda _m: None)

    assert result.ok and result.action == "filed"
    assert gh.create_attempts == 2, "exactly one retry"
    assert gh.argv_for("label create"), "the label must be created before the retry"

    order = [" ".join(c) for c in gh.calls]
    first_create = next(i for i, c in enumerate(order) if "issue create" in c)
    label = next(i for i, c in enumerate(order) if "label create" in c)
    second_create = next(
        i for i, c in enumerate(order) if "issue create" in c and i > first_create
    )
    assert first_create < label < second_create


def test_persistent_create_failure_does_not_retry_forever(tmp_path):
    gh = FakeGh(fail_create_until=99)
    result = file_must_resolve(tmp_path, 4, CONFLICT, runner=gh, log=lambda _m: None)
    assert not result.ok and result.action == "failed"
    assert gh.create_attempts == 2


# --- "the same conflict again comments and files nothing new" -------------


def _existing_issue(number, source_issue, conflict):
    fp = conflict_fingerprint(conflict["criterion_a"], conflict["criterion_b"])
    return {
        "number": number,
        "body": build_body(source_issue, conflict, run_id="prev", run_start="x",
                           conflict_ts="y", fingerprint=fp),
    }


def test_recurrence_comments_instead_of_filing_a_duplicate(tmp_path):
    gh = FakeGh(existing=[_existing_issue(224, 4, CONFLICT)])

    result = file_must_resolve(tmp_path, 4, CONFLICT, run_id="run-issue4-999999",
                               conflict_ts="2026-08-01 12:00:00",
                               runner=gh, log=lambda _m: None)

    assert result.ok and result.action == "commented"
    assert result.issue_number == 224
    assert gh.argv_for("issue create") == [], "a redraw storm must not file duplicates"

    comment = _body_of(gh.argv_for("issue comment")[0])
    assert "run-issue4-999999" in comment
    assert "2026-08-01 12:00:00" in comment


def test_same_fingerprint_different_source_issue_files_separately(tmp_path):
    gh = FakeGh(existing=[_existing_issue(224, 4, CONFLICT)])

    result = file_must_resolve(tmp_path, 99, CONFLICT, runner=gh, log=lambda _m: None)

    assert result.action == "filed", "a different source issue is a different ambiguity"
    assert gh.argv_for("issue create")


def test_different_conflict_same_source_issue_files_separately(tmp_path):
    gh = FakeGh(existing=[_existing_issue(224, 4, CONFLICT)])

    result = file_must_resolve(tmp_path, 4, OTHER_CONFLICT, runner=gh, log=lambda _m: None)

    assert result.action == "filed"
    assert gh.argv_for("issue create")


# --- "the fingerprint is unchanged by whitespace, casing, or ordering" ----


def test_fingerprint_is_stable_across_whitespace_casing_and_order():
    base = conflict_fingerprint(CONFLICT["criterion_a"], CONFLICT["criterion_b"])

    spaced = conflict_fingerprint(
        "  " + CONFLICT["criterion_a"].replace(" ", "   ") + "\n",
        CONFLICT["criterion_b"] + "   ",
    )
    cased = conflict_fingerprint(
        CONFLICT["criterion_a"].upper(), CONFLICT["criterion_b"].lower()
    )
    swapped = conflict_fingerprint(CONFLICT["criterion_b"], CONFLICT["criterion_a"])

    assert spaced == base
    assert cased == base
    assert swapped == base, "the analysis does not guarantee stable A/B ordering"


def test_genuinely_different_conflicts_have_different_fingerprints():
    a = conflict_fingerprint(CONFLICT["criterion_a"], CONFLICT["criterion_b"])
    b = conflict_fingerprint(OTHER_CONFLICT["criterion_a"], OTHER_CONFLICT["criterion_b"])
    assert a != b


def test_fingerprint_distinguishes_a_single_digit():
    # `2s` vs `5s` is the whole conflict. Normalization must not collapse it.
    a = conflict_fingerprint("poll every 2s", "poll every 9s")
    b = conflict_fingerprint("poll every 2s", "poll every 5s")
    assert a != b


def test_normalize_keeps_punctuation_and_digits():
    assert normalize_criterion("  Every   5s.  ") == "every 5s."


# --- "a missing or failing gh returns failure without raising" ------------


def test_missing_gh_returns_failure_and_does_not_raise(tmp_path):
    def exploding_runner(args):
        if args[0] == "git":
            return subprocess.CompletedProcess(
                args, 0, "https://github.com/martymcenroe/boostgauge.git", ""
            )
        raise OSError("gh not found")

    def guarded(args):
        try:
            return exploding_runner(args)
        except OSError as exc:
            return subprocess.CompletedProcess(args, 127, "", str(exc))

    result = file_must_resolve(tmp_path, 4, CONFLICT, runner=guarded, log=lambda _m: None)
    assert not result.ok and result.action == "failed"


def test_no_github_remote_is_a_failure_not_an_exception(tmp_path):
    gh = FakeGh(remote=None)
    result = file_must_resolve(tmp_path, 4, CONFLICT, runner=gh, log=lambda _m: None)
    assert not result.ok and result.action == "failed"
    assert "remote" in result.detail


def test_filing_failure_leaves_the_halt_message_intact(monkeypatch, tmp_path):
    """The roll was already halting; a filing problem must not change that."""
    # The package re-exports the function under the module's own name, so the
    # module object has to be reached explicitly.
    import assemblyzero.core.llm_provider as llm
    import assemblyzero.speedrun.must_resolve as mr
    from assemblyzero.workflows.requirements.nodes import (
        analyze_requirements as node_mod,
    )

    if not hasattr(node_mod, "_parse_analysis"):  # imported the function, not the module
        import importlib

        node_mod = importlib.import_module(
            "assemblyzero.workflows.requirements.nodes.analyze_requirements"
        )

    monkeypatch.setattr(
        node_mod, "_parse_analysis",
        lambda _raw: {"is_consistent": False, "conflicts": [CONFLICT]},
    )

    class _Result:
        success = True
        response = "{}"
        error_message = ""

    class _Provider:
        def invoke(self, **_kw):
            return _Result()

    monkeypatch.setattr(llm, "get_provider", lambda _spec: _Provider())
    monkeypatch.setattr(llm, "GeminiProvider", type("NotGemini", (), {}))

    def boom(*_a, **_kw):
        raise RuntimeError("github is down")

    monkeypatch.setattr(mr, "file_all_conflicts", boom)

    out = node_mod.analyze_requirements({
        "issue_title": "t", "issue_body": "body", "issue_number": 4,
        "target_repo": str(tmp_path),
    })

    assert out["error_message"].startswith(node_mod.REQUIREMENTS_CONFLICT_MARKER)
    assert "Conflict 1:" in out["error_message"]


def test_conflict_halt_still_files_when_github_is_healthy(monkeypatch, tmp_path):
    import importlib

    import assemblyzero.core.llm_provider as llm
    import assemblyzero.speedrun.must_resolve as mr

    node_mod = importlib.import_module(
        "assemblyzero.workflows.requirements.nodes.analyze_requirements"
    )

    monkeypatch.setattr(
        node_mod, "_parse_analysis",
        lambda _raw: {"is_consistent": False, "conflicts": [CONFLICT]},
    )

    class _Result:
        success = True
        response = "{}"
        error_message = ""

    class _Provider:
        def invoke(self, **_kw):
            return _Result()

    monkeypatch.setattr(llm, "get_provider", lambda _spec: _Provider())
    monkeypatch.setattr(llm, "GeminiProvider", type("NotGemini", (), {}))

    seen = {}

    def record(repo, issue, conflicts, **_kw):
        seen["issue"] = issue
        seen["conflicts"] = conflicts
        return []

    monkeypatch.setattr(mr, "file_all_conflicts", record)

    node_mod.analyze_requirements({
        "issue_title": "t", "issue_body": "body", "issue_number": 4,
        "target_repo": str(tmp_path),
    })

    assert seen["issue"] == 4
    assert seen["conflicts"] == [CONFLICT]


# --- "an entry path with no issue number files nothing" ------------------


def test_entry_path_without_issue_number_files_nothing(tmp_path):
    gh = FakeGh()
    result = file_must_resolve(tmp_path, 0, CONFLICT, runner=gh, log=lambda _m: None)

    assert result.ok and result.action == "skipped"
    assert gh.calls == [], "brief and idea paths have nothing to file against"


# --- "the launcher's run tag reaches the filing through the child env" ---


def test_run_tag_travels_through_the_child_environment():
    env = {RUN_TAG_ENV: "run-issue4-111608", RUN_START_ENV: "2026-08-01 11:16:08"}
    assert run_context(env) == ("run-issue4-111608", "2026-08-01 11:16:08")


def test_absent_run_tag_is_reported_as_unknown_not_guessed():
    # A workflow invoked outside a roll has no launcher and no log triplet. A
    # guessed name would send a human to read the wrong file.
    assert run_context({}) == ("unknown", "unknown")


def test_child_env_carries_the_run_tag(monkeypatch):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import speedrun_roll

    env = speedrun_roll._child_env("run-issue4-111608", "2026-08-01 11:16:08")
    assert env[RUN_TAG_ENV] == "run-issue4-111608"
    assert env[RUN_START_ENV] == "2026-08-01 11:16:08"
    assert env["CLAUDECODE"] == ""

    bare = speedrun_roll._child_env()
    assert RUN_TAG_ENV not in bare


# --- multiple conflicts ---------------------------------------------------


def test_each_distinct_conflict_gets_its_own_issue(tmp_path):
    gh = FakeGh()
    results = file_all_conflicts(
        tmp_path, 4, [CONFLICT, OTHER_CONFLICT], runner=gh, log=lambda _m: None
    )
    assert [r.action for r in results] == ["filed", "filed"]
    assert len(gh.argv_for("issue create")) == 2


def test_file_all_conflicts_never_raises(tmp_path):
    def boom(_args):
        raise ValueError("unexpected")

    results = file_all_conflicts(tmp_path, 4, [CONFLICT], runner=boom, log=lambda _m: None)
    assert len(results) == 1 and not results[0].ok
