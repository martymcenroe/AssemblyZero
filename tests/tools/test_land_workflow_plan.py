"""Unit tests for tools/land_workflow_plan.py (#4713).

GitHub is replaced by a fake `requests` on the single-repository lander's module, through
which every call of the plan lander goes, and the token is a dummy string: nothing is
decrypted, because per the _pat_session operational rule that decrypt belongs to the
operator, never to a test or an agent.
"""

from __future__ import annotations

import base64
import copy
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

import land_staged_workflow as lsw
import land_workflow_plan as lwp

API = "https://api.github.com/repos/o"
SOURCE = "SOURCEREPO"
LIVE = "name: Tests\non:\n  pull_request:\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
COPY = "# off\n\nname: Tests\non:\n  pull_request:\njobs:\n  test:\n    if: false\n    runs-on: ubuntu-latest\n"
LIVE2 = "name: Lint\non:\n  pull_request:\njobs:\n  lint:\n    runs-on: ubuntu-latest\n"
COPY2 = "name: Lint\non:\n  pull_request:\njobs:\n  lint:\n    if: false\n    runs-on: ubuntu-latest\n"
BLOB = "a" * 40
BLOB2 = "b" * 40


def plan_for(*targets: dict) -> dict:
    return {
        "source": {"repo": SOURCE, "ref": "main"},
        "reason": "Turns the test jobs off, by the operator's order.",
        "targets": list(targets) or [target("alpha", 7)],
    }


def target(repo: str, issue: int, files: list[dict] | None = None) -> dict:
    return {"repo": repo, "issue": issue, "files": files or [
        {"staged": f"docs/ci/{repo}/tests.yml", "workflow": ".github/workflows/tests.yml",
         "base_blob": BLOB, "expect": "skipped"}]}


class Resp:
    def __init__(self, payload: object = None, status: int = 200):
        self.payload, self.status_code, self.text = payload, status, json.dumps(payload)

    def json(self) -> object:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeGitHub:
    """Just enough of the REST API for one plan run, recording every write."""

    def __init__(self, conclusion: str = "skipped"):
        self.files: dict[tuple[str, str, str], tuple[str, str]] = {}  # (repo, ref, path) -> (text, sha)
        self.repos: dict[str, dict] = {}
        self.writes: list[tuple[str, str]] = []
        self.prs: dict[str, list[dict]] = {}
        self.conclusion = conclusion

    def put_file(self, repo: str, ref: str, path: str, text: str, sha: str) -> None:
        self.files[(repo, ref, path)] = (text, sha)
        self.repos.setdefault(repo, {"private": True, "default_branch": "main"})

    def _rec(self, text: str, sha: str) -> dict:
        return {"content": base64.b64encode(text.encode()).decode(), "sha": sha}

    def get(self, url, params=None, headers=None, timeout=None):
        params = params or {}
        if m := re.fullmatch(rf"{API}/([^/]+)", url):
            return Resp(self.repos[m.group(1)])
        if m := re.fullmatch(rf"{API}/([^/]+)/contents/(.+)", url):
            hit = self.files.get((m.group(1), params.get("ref"), m.group(2)))
            return Resp(self._rec(*hit)) if hit else Resp({}, 404)
        if m := re.fullmatch(rf"{API}/([^/]+)/git/ref/heads/main", url):
            return Resp({"object": {"sha": "m" * 40}})
        if m := re.fullmatch(rf"{API}/([^/]+)/pulls", url):
            return Resp([p for p in self.prs.get(m.group(1), []) if p["state"] == "open"])
        if m := re.fullmatch(rf"{API}/([^/]+)/pulls/(\d+)", url):
            return Resp({"head": {"sha": "h" * 40}, "mergeable_state": "clean"})
        if m := re.fullmatch(rf"{API}/([^/]+)/actions/runs", url):
            names = [lsw.workflow_name(t, None) for (r, ref, _), (t, _) in self.files.items()
                     if r == m.group(1) and ref.startswith("ci/")]
            return Resp({"workflow_runs": [
                {"name": n, "status": "completed", "conclusion": self.conclusion,
                 "created_at": "2026-11-11T00:00:00Z", "html_url": "https://x/run"} for n in names]})
        raise AssertionError(f"unexpected GET {url}")

    def post(self, url, headers=None, json=None, timeout=None):
        if m := re.fullmatch(rf"{API}/([^/]+)/git/refs", url):
            self.writes.append(("branch", f"{m.group(1)}:{json['ref']}"))
            return Resp({}, 201)
        if m := re.fullmatch(rf"{API}/([^/]+)/pulls", url):
            pr = {"number": 41, "state": "open", **json}
            self.prs.setdefault(m.group(1), []).append(pr)
            self.writes.append(("pr", f"{m.group(1)}:{json['title']}"))
            return Resp({"number": 41}, 201)
        raise AssertionError(f"unexpected POST {url}")

    def put(self, url, headers=None, json=None, timeout=None):
        if m := re.fullmatch(rf"{API}/([^/]+)/contents/(.+)", url):
            text = base64.b64decode(json["content"]).decode()
            self.files[(m.group(1), json["branch"], m.group(2))] = (text, "n" * 40)
            self.writes.append(("commit", f"{m.group(1)}:{m.group(2)}"))
            return Resp({}, 200)
        if m := re.fullmatch(rf"{API}/([^/]+)/pulls/(\d+)/merge", url):
            for p in self.prs[m.group(1)]:
                p["state"] = "merged"
            self.writes.append(("merge", m.group(1)))
            return Resp({}, 200)
        raise AssertionError(f"unexpected PUT {url}")

    def delete(self, url, headers=None, json=None, timeout=None):
        if m := re.fullmatch(rf"{API}/([^/]+)/git/refs/heads/(.+)", url):
            self.writes.append(("delete-branch", f"{m.group(1)}:{m.group(2)}"))
            return Resp({}, 204)
        raise AssertionError(f"unexpected DELETE {url}")


@pytest.fixture
def gh(monkeypatch):
    fake = FakeGitHub()
    monkeypatch.setattr(lsw, "requests", SimpleNamespace(
        get=fake.get, post=fake.post, put=fake.put, delete=fake.delete))
    monkeypatch.setattr(lsw.time, "sleep", lambda s: None)
    return fake


def stage(gh: FakeGitHub, repo: str, live: str = LIVE, copy_: str = COPY, blob: str = BLOB,
          workflow: str = ".github/workflows/tests.yml", staged: str | None = None) -> None:
    gh.put_file(repo, "main", workflow, live, blob)
    gh.put_file(SOURCE, "main", staged or f"docs/ci/{repo}/tests.yml", copy_, "s" * 40)


# --- T1: the plan's contract ---------------------------------------------------------


class TestValidatePlan:
    def test_a_well_formed_plan_passes(self):
        assert lwp.validate_plan(plan_for())["source"]["ref"] == "main"

    @pytest.mark.parametrize("path, value, needle", [
        (("source",), None, "source.repo"),
        (("reason",), "", "reason"),
        (("targets",), [], "targets"),
        (("targets", 0, "issue"), 0, "issue"),
        (("targets", 0, "repo"), "o/alpha", "a name"),
        (("targets", 0, "files", 0, "workflow"), "docs/tests.yml", ".github/workflows/"),
        (("targets", 0, "files", 0, "base_blob"), "abc", "base_blob"),
        (("targets", 0, "files", 0, "expect"), "failure", "expect"),
        (("targets", 0, "files", 0, "staged"), "", "staged"),
    ])
    def test_each_fault_is_refused_by_name(self, path, value, needle):
        plan = plan_for()
        node = plan
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        with pytest.raises(lwp.PlanError) as e:
            lwp.validate_plan(plan)
        assert needle in str(e.value)

    def test_a_duplicate_target_is_refused(self):
        with pytest.raises(lwp.PlanError, match="twice"):
            lwp.validate_plan(plan_for(target("alpha", 7), target("alpha", 8)))

    def test_a_reason_naming_the_source_is_refused(self):
        plan = plan_for()
        plan["reason"] = f"Staged in {SOURCE.lower()}."
        with pytest.raises(lwp.PlanError, match="source repository"):
            lwp.validate_plan(plan)

    def test_no_repository_is_baked_in(self):
        """This repo is public; every name arrives in the plan, at run time."""
        with pytest.raises(SystemExit):
            lwp.parse_args([])


class TestPrText:
    def test_title_and_body_close_the_issue_and_name_no_source(self):
        workflows = [".github/workflows/tests.yml", ".github/workflows/lint.yml"]
        title = lwp.pr_title(workflows, 7)
        body = lwp.pr_body("Turns the tests off.", workflows, 7)
        assert title == "ci: update tests.yml, lint.yml (Closes #7)"
        assert body.startswith("Closes #7\n")
        for text in (title, body):
            assert SOURCE not in text and "docs/ci" not in text

    def test_a_title_past_the_limit_counts_the_files(self):
        workflows = [f".github/workflows/{'w' * 40}{i}.yml" for i in range(8)]
        assert lwp.pr_title(workflows, 7) == "ci: update 8 workflows (Closes #7)"


class TestVerdict:
    @pytest.mark.parametrize("conclusion, expect, red, ok", [
        ("skipped", "skipped", False, True),
        ("success", "success", False, True),
        ("success", "skipped", False, False),
        ("failure", "success", False, False),
        ("failure", "success", True, True),
        ("in_progress", "skipped", True, False),
        ("no_run", "skipped", True, False),
    ])
    def test_verdict(self, conclusion, expect, red, ok):
        assert lwp.verdict(conclusion, expect, red) is ok


# --- T2 and T3: what one run does to a target ----------------------------------------


class TestLandTarget:
    def test_a_target_lands_as_one_branch_one_pr_then_merge_and_delete(self, gh):
        files = [
            {"staged": "docs/ci/alpha/tests.yml", "workflow": ".github/workflows/tests.yml",
             "base_blob": BLOB, "expect": "skipped"},
            {"staged": "docs/ci/alpha/lint.yml", "workflow": ".github/workflows/lint.yml",
             "base_blob": BLOB2, "expect": "skipped"},
        ]
        stage(gh, "alpha")
        stage(gh, "alpha", LIVE2, COPY2, BLOB2, ".github/workflows/lint.yml", "docs/ci/alpha/lint.yml")
        plan = lwp.validate_plan(plan_for(target("alpha", 7, files)))
        assert lwp.land_target("pat", plan, plan["targets"][0], "o", False) == "landed"
        assert [w[0] for w in gh.writes] == ["branch", "commit", "commit", "pr", "merge", "delete-branch"]
        assert gh.files[("alpha", "ci/staged-workflow-7", ".github/workflows/tests.yml")][0] == COPY
        pr = gh.prs["alpha"][0]
        assert pr["title"] == "ci: update tests.yml, lint.yml (Closes #7)"
        assert SOURCE not in pr["body"] and "docs/ci" not in pr["body"]

    def test_a_moved_base_blob_stops_before_any_write(self, gh):
        stage(gh, "alpha", blob="c" * 40)
        plan = lwp.validate_plan(plan_for())
        with pytest.raises(lwp.LandingStop) as e:
            lwp.land_target("pat", plan, plan["targets"][0], "o", False)
        assert e.value.step == "base" and gh.writes == []

    def test_a_target_already_landed_is_skipped_without_a_write(self, gh):
        stage(gh, "alpha", live=COPY)
        plan = lwp.validate_plan(plan_for())
        assert lwp.land_target("pat", plan, plan["targets"][0], "o", False) == "already"
        assert gh.writes == []

    def test_a_conclusion_other_than_the_plan_stops_and_leaves_the_pr_open(self, gh):
        gh.conclusion = "failure"
        stage(gh, "alpha")
        plan = lwp.validate_plan(plan_for())
        with pytest.raises(lwp.LandingStop) as e:
            lwp.land_target("pat", plan, plan["targets"][0], "o", False)
        assert e.value.step == "wait"
        assert ("merge", "alpha") not in gh.writes and gh.prs["alpha"][0]["state"] == "open"

    def test_a_copy_with_a_carriage_return_is_refused(self, gh):
        stage(gh, "alpha", copy_=COPY.replace("\n", "\r\n"))
        plan = lwp.validate_plan(plan_for())
        with pytest.raises(lwp.LandingStop, match="carriage return"):
            lwp.land_target("pat", plan, plan["targets"][0], "o", False)
        assert gh.writes == []


# --- T3, T4: the whole run -------------------------------------------------------------


class Session:
    def __init__(self):
        self.calls = 0

    def __call__(self, reason=None):
        self.calls += 1
        outer = self

        class Ctx:
            def __enter__(self):
                return "pat"

            def __exit__(self, *exc):
                return False

        outer.reason = reason
        return Ctx()


class TestRun:
    def test_one_session_covers_every_target(self, gh):
        for repo in ("alpha", "beta"):
            stage(gh, repo)
        plan = lwp.validate_plan(plan_for(target("alpha", 7), target("beta", 9)))
        session = Session()
        assert lwp.run(plan, plan["targets"], "o", False, session=session) == 0
        assert session.calls == 1
        assert [w[1] for w in gh.writes if w[0] == "merge"] == ["alpha", "beta"]

    def test_the_first_failure_stops_the_run_and_counts(self, gh, capsys):
        stage(gh, "alpha")
        stage(gh, "beta", blob="c" * 40)
        stage(gh, "gamma")
        plan = lwp.validate_plan(plan_for(target("alpha", 7), target("beta", 9), target("gamma", 11)))
        assert lwp.run(plan, plan["targets"], "o", False, session=Session()) == 1
        err = capsys.readouterr().err
        assert "STOPPED at beta" in err and "landed 1, already landed 0, not landed 2 of 3" in err
        assert not any(w[1].startswith("gamma") for w in gh.writes)

    def test_a_reason_naming_a_private_target_stops_when_any_target_is_public(self, gh, capsys):
        stage(gh, "alpha")
        stage(gh, "beta")
        gh.repos["beta"]["private"] = False
        plan = lwp.validate_plan(plan_for(target("alpha", 7), target("beta", 9)))
        plan["reason"] = "Same as alpha did."
        assert lwp.run(plan, plan["targets"], "o", False, session=Session()) == 1
        assert gh.writes == [] and "private target" in capsys.readouterr().err

    def test_a_default_branch_other_than_main_stops_before_any_write(self, gh):
        stage(gh, "alpha")
        gh.repos["alpha"]["default_branch"] = "master"
        plan = lwp.validate_plan(plan_for())
        assert lwp.run(plan, plan["targets"], "o", False, session=Session()) == 1
        assert gh.writes == []

    def test_the_dry_run_asks_for_no_credential(self, tmp_path, monkeypatch, capsys):
        path = tmp_path / "plan.json"
        path.write_text(json.dumps(plan_for()), encoding="utf-8")

        def refuse(*a, **k):
            raise AssertionError("the dry run asked for the PAT")

        monkeypatch.setattr(lwp, "classic_pat_session", refuse)
        monkeypatch.setattr(lwp, "run", refuse)
        assert lwp.main(["--plan", str(path)]) == 0
        out = capsys.readouterr().out
        assert "DRY-RUN" in out and "#7" in out

    def test_only_limits_the_run_and_refuses_a_name_not_in_the_plan(self):
        plan = lwp.validate_plan(plan_for(target("alpha", 7), target("beta", 9)))
        assert [t["repo"] for t in lwp.select(plan, ["beta"])] == ["beta"]
        with pytest.raises(lwp.PlanError):
            lwp.select(copy.deepcopy(plan), ["delta"])


# --- T5: the delete action, --max-targets and the contribution count (#4721) ----------

CALLER = ".github/workflows/auto-reviewer.yml"
CALLER_TEXT = ("name: Auto Review\non:\n  pull_request:\njobs:\n  auto-review:\n"
               "    uses: o/r/.github/workflows/auto-reviewer.yml@main\n")
CALLER_BLOB = "d" * 40


def delete_target(repo: str, issue: int, blob: str = CALLER_BLOB) -> dict:
    return {"repo": repo, "issue": issue, "files": [
        {"workflow": CALLER, "action": "delete", "base_blob": blob}]}


def delete_plan(*targets: dict) -> dict:
    """The shape the fleet half writes: no `source`, delete entries only."""
    return {"reason": "Removes the retired Auto Review caller.",
            "targets": list(targets) or [delete_target("alpha", 7)]}


class MergingGitHub(FakeGitHub):
    """FakeGitHub plus what a delete needs.

    A new branch starts from main's files, a Contents-API DELETE removes a file on a
    branch (and must name the blob the branch holds), and a squash merge carries the
    branch's removals to main, unless `merge_lands` is False, which stands for a merge
    whose change never reached main.
    """

    def __init__(self):
        super().__init__()
        self.removed: dict[tuple[str, str], list[str]] = {}
        self.merge_lands = True
        self.calls: list[tuple[str, str]] = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(("GET", url))
        return super().get(url, params=params, headers=headers, timeout=timeout)

    def post(self, url, headers=None, json=None, timeout=None):
        if m := re.fullmatch(rf"{API}/([^/]+)/git/refs", url):
            repo, branch = m.group(1), json["ref"].removeprefix("refs/heads/")
            for (r, ref, path), rec in list(self.files.items()):
                if r == repo and ref == "main":
                    self.files.setdefault((repo, branch, path), rec)
        return super().post(url, headers=headers, json=json, timeout=timeout)

    def put(self, url, headers=None, json=None, timeout=None):
        if self.merge_lands and (m := re.fullmatch(rf"{API}/([^/]+)/pulls/(\d+)/merge", url)):
            for (repo, _branch), paths in self.removed.items():
                if repo == m.group(1):
                    for path in paths:
                        self.files.pop((repo, "main", path), None)
        return super().put(url, headers=headers, json=json, timeout=timeout)

    def delete(self, url, headers=None, json=None, timeout=None):
        if m := re.fullmatch(rf"{API}/([^/]+)/contents/(.+)", url):
            repo, path = m.group(1), m.group(2)
            key = (repo, json["branch"], path)
            assert json["sha"] == self.files[key][1], "DELETE names a blob the branch does not hold"
            del self.files[key]
            self.removed.setdefault((repo, json["branch"]), []).append(path)
            self.writes.append(("remove", f"{repo}:{path}"))
            return Resp({}, 200)
        return super().delete(url, headers=headers, json=json, timeout=timeout)


@pytest.fixture
def mgh(monkeypatch):
    fake = MergingGitHub()
    monkeypatch.setattr(lsw, "requests", SimpleNamespace(
        get=fake.get, post=fake.post, put=fake.put, delete=fake.delete))
    monkeypatch.setattr(lsw.time, "sleep", lambda s: None)
    return fake


def live_caller(gh: FakeGitHub, repo: str, blob: str = CALLER_BLOB) -> None:
    gh.put_file(repo, "main", CALLER, CALLER_TEXT, blob)


class TestDeletePlan:
    def test_the_fleet_halfs_plan_validates_without_source(self, tmp_path):  # T5g
        path = tmp_path / "plan.json"
        path.write_text(json.dumps({
            "reason": "Removes the retired Auto Review caller.",
            "targets": [{"repo": "alpha", "issue": 7, "files": [
                {"workflow": CALLER, "action": "delete", "base_blob": CALLER_BLOB}]}],
        }), encoding="utf-8")
        plan = lwp.load_plan(path)
        assert "source" not in plan and plan["targets"][0]["files"][0]["action"] == "delete"

    def test_a_plan_with_any_replace_entry_still_needs_source(self):
        with pytest.raises(lwp.PlanError, match="source.repo"):
            lwp.validate_plan(delete_plan(delete_target("alpha", 7), target("beta", 9)))

    @pytest.mark.parametrize("extra", [{"staged": "docs/x.yml"}, {"expect": "skipped"}])
    def test_a_delete_entry_carrying_a_replace_key_is_refused(self, extra):
        plan = delete_plan()
        plan["targets"][0]["files"][0].update(extra)
        with pytest.raises(lwp.PlanError, match=f"carries `{next(iter(extra))}`"):
            lwp.validate_plan(plan)

    @pytest.mark.parametrize("key, value, needle", [
        ("action", "rename", "action"),
        ("base_blob", "abc", "base_blob"),
        ("workflow", "docs/x.yml", ".github/workflows/"),
    ])
    def test_a_bad_delete_entry_is_refused_by_name(self, key, value, needle):
        plan = delete_plan()
        plan["targets"][0]["files"][0][key] = value
        with pytest.raises(lwp.PlanError) as e:
            lwp.validate_plan(plan)
        assert needle in str(e.value)


class TestDeleteTarget:
    def test_a_file_absent_on_main_is_already(self, mgh):  # T5a
        plan = lwp.validate_plan(delete_plan())
        assert lwp.land_target("pat", plan, plan["targets"][0], "o", False) == "already"
        assert mgh.writes == []

    def test_a_moved_blob_stops_with_no_write(self, mgh):  # T5b
        live_caller(mgh, "alpha", blob="e" * 40)
        plan = lwp.validate_plan(delete_plan())
        with pytest.raises(lwp.LandingStop) as e:
            lwp.land_target("pat", plan, plan["targets"][0], "o", False)
        assert e.value.step == "base" and gh_writes(mgh) == []

    def test_a_delete_opens_one_pr_merges_and_deletes_the_branch(self, mgh):  # T5c
        live_caller(mgh, "alpha")
        plan = lwp.validate_plan(delete_plan())

        def no_wait(*a, **k):
            raise AssertionError("waited for a run of a removed workflow")

        assert lwp.land_target("pat", plan, plan["targets"][0], "o", False, wait=no_wait) == "landed"
        assert gh_writes(mgh) == ["branch", "remove", "pr", "merge", "delete-branch"]
        assert len(mgh.prs["alpha"]) == 1
        pr = mgh.prs["alpha"][0]
        assert pr["title"] == "ci: remove auto-reviewer.yml (Closes #7)"
        assert pr["body"].startswith("Closes #7\n") and f"Removed:\n\n- `{CALLER}`" in pr["body"]
        assert ("alpha", "main", CALLER) not in mgh.files
        assert not any("/actions/runs" in url for _, url in mgh.calls)

    def test_a_read_back_that_still_finds_the_file_stops_the_run(self, mgh):  # T5d
        live_caller(mgh, "alpha")
        mgh.merge_lands = False
        plan = lwp.validate_plan(delete_plan())
        with pytest.raises(lwp.LandingStop) as e:
            lwp.land_target("pat", plan, plan["targets"][0], "o", False)
        assert e.value.step == "verify" and "still on main" in e.value.message

    def test_a_mixed_target_lands_in_one_pr_and_waits_only_for_the_replaced_file(self, mgh):
        stage(mgh, "alpha")
        live_caller(mgh, "alpha")
        files = [{"staged": "docs/ci/alpha/tests.yml", "workflow": ".github/workflows/tests.yml",
                  "base_blob": BLOB, "expect": "skipped"},
                 {"workflow": CALLER, "action": "delete", "base_blob": CALLER_BLOB}]
        plan = lwp.validate_plan(plan_for(target("alpha", 7, files)))
        waited: list[str] = []

        def wait(pat, cfg, sha, name):
            waited.append(name)
            return lsw.WaitResult("skipped")

        assert lwp.land_target("pat", plan, plan["targets"][0], "o", False, wait=wait) == "landed"
        assert waited == ["Tests"]
        assert gh_writes(mgh) == ["branch", "commit", "remove", "pr", "merge", "delete-branch"]
        assert mgh.prs["alpha"][0]["title"] == "ci: update tests.yml; remove auto-reviewer.yml (Closes #7)"

    def test_a_branch_left_without_the_file_by_an_earlier_run_takes_no_second_delete(self, mgh):
        live_caller(mgh, "alpha")  # on main; the branch an earlier run left already lacks it
        plan = lwp.validate_plan(delete_plan())
        cfg = lwp.target_cfg("o", plan["targets"][0], False)
        assert lwp.remove_workflow("pat", cfg, plan["targets"][0]["files"][0]) is False
        assert mgh.writes == []


def gh_writes(gh: FakeGitHub) -> list[str]:
    return [w[0] for w in gh.writes]


class TestDeleteRun:
    def _fleet(self, gh: FakeGitHub, *repos: str) -> None:
        for repo in repos:
            live_caller(gh, repo)

    def test_a_rerun_after_a_stop_skips_the_done_targets(self, mgh, capsys):  # T5e
        self._fleet(mgh, "alpha", "gamma")
        live_caller(mgh, "beta", blob="e" * 40)
        plan = lwp.validate_plan(delete_plan(
            delete_target("alpha", 7), delete_target("beta", 9), delete_target("gamma", 11)))
        assert lwp.run(plan, plan["targets"], "o", False, session=Session()) == 1
        assert [w[1] for w in mgh.writes if w[0] == "merge"] == ["alpha"]

        live_caller(mgh, "beta")  # the cause is fixed
        mgh.writes.clear()
        assert lwp.run(plan, plan["targets"], "o", False, session=Session()) == 0
        assert [w[1] for w in mgh.writes if w[0] == "merge"] == ["beta", "gamma"]
        assert not any(w[1].startswith("alpha") for w in mgh.writes)
        assert "landed 2, already landed 1, of 3" in capsys.readouterr().out

    def test_max_targets_two_lands_exactly_two(self, mgh, capsys):  # T5f
        self._fleet(mgh, "alpha", "beta", "gamma", "delta")
        plan = lwp.validate_plan(delete_plan(*(delete_target(r, i) for r, i in
                                               (("alpha", 7), ("beta", 9), ("gamma", 11), ("delta", 13)))))
        assert lwp.run(plan, plan["targets"], "o", False, max_targets=2, session=Session()) == 0
        assert [w[1] for w in mgh.writes if w[0] == "merge"] == ["alpha", "beta"]
        out = capsys.readouterr().out
        assert "Stopped at --max-targets 2: landed 2, already landed 0, not reached 2 of 4" in out

        mgh.writes.clear()
        assert lwp.run(plan, plan["targets"], "o", False, max_targets=2, session=Session()) == 0
        assert [w[1] for w in mgh.writes if w[0] == "merge"] == ["gamma", "delta"]

    def test_already_done_targets_do_not_count_toward_the_cap(self, mgh):
        self._fleet(mgh, "gamma")
        mgh.repos.update({r: {"private": True, "default_branch": "main"} for r in ("alpha", "beta")})
        plan = lwp.validate_plan(delete_plan(
            delete_target("alpha", 7), delete_target("beta", 9), delete_target("gamma", 11)))
        assert lwp.run(plan, plan["targets"], "o", False, max_targets=1, session=Session()) == 0
        assert [w[1] for w in mgh.writes if w[0] == "merge"] == ["gamma"]

    def test_max_targets_must_be_positive(self):
        assert lwp.parse_args(["--plan", "p.json", "--max-targets", "3"]).max_targets == 3
        with pytest.raises(SystemExit):
            lwp.parse_args(["--plan", "p.json", "--max-targets", "0"])

    def test_apply_prints_the_count_before_the_passphrase(self, mgh, capsys, tmp_path, monkeypatch):
        self._fleet(mgh, "alpha", "beta", "gamma")
        path = tmp_path / "plan.json"
        path.write_text(json.dumps(delete_plan(
            delete_target("alpha", 7), delete_target("beta", 9), delete_target("gamma", 11))),
            encoding="utf-8")
        before_passphrase: list[str] = []

        class Ctx:
            def __enter__(self):
                before_passphrase.append(capsys.readouterr().out)
                return "pat"

            def __exit__(self, *exc):
                return False

        monkeypatch.setattr(lwp, "classic_pat_session", lambda reason=None: Ctx())
        assert lwp.main(["--plan", str(path), "--apply", "--max-targets", "2", "--owner", "o"]) == 0
        assert len(before_passphrase) == 1
        out = before_passphrase[0]
        assert "will land: at most 2 of 3 target(s) (--max-targets 2)" in out
        assert "adds     : at most 4 contributions" in out

    def test_the_dry_run_prints_delete_lines_and_the_count(self, tmp_path, monkeypatch, capsys):
        path = tmp_path / "plan.json"
        path.write_text(json.dumps(delete_plan(delete_target("alpha", 7), delete_target("beta", 9))),
                        encoding="utf-8")

        def refuse(*a, **k):
            raise AssertionError("the dry run asked for the PAT")

        monkeypatch.setattr(lwp, "classic_pat_session", refuse)
        monkeypatch.setattr(lwp, "run", refuse)
        assert lwp.main(["--plan", str(path)]) == 0
        out = capsys.readouterr().out
        assert out.count(f"delete {CALLER} base {CALLER_BLOB[:10]}") == 2
        assert "source   : none (every entry is a delete)" in out
        assert "will land: at most 2 of 2 target(s)" in out
        assert "adds     : at most 4 contributions" in out


# --- #4725: a target whose issue lives in another repository ---------------------------

#: Every closing directive GitHub honours (the fleet's pre-flight check 2).
DIRECTIVE = re.compile(
    r"\b(close[sd]?|fix(es|ed)?|resolve[sd]?)\s*:?\s*([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)?#[0-9]+",
    re.IGNORECASE)


def homed(t: dict, home: str = "home") -> dict:
    t["issue_repo"] = home
    return t


def record_messages(monkeypatch, fake: FakeGitHub) -> list[str]:
    """Route the fake's Contents-API PUT and DELETE through a recorder of commit messages."""
    messages: list[str] = []

    def put(url, headers=None, json=None, timeout=None):
        if "/contents/" in url:
            messages.append(json["message"])
        return fake.put(url, headers=headers, json=json, timeout=timeout)

    def delete(url, headers=None, json=None, timeout=None):
        if "/contents/" in url:
            messages.append(json["message"])
        return fake.delete(url, headers=headers, json=json, timeout=timeout)

    monkeypatch.setattr(lsw, "requests", SimpleNamespace(
        get=fake.get, post=fake.post, put=put, delete=delete))
    return messages


def directives(text: str) -> list[str]:
    return [m.group(0) for m in DIRECTIVE.finditer(text)]


class TestIssueRepo:
    def test_a_target_naming_its_issue_repo_validates(self):  # T1
        plan = lwp.validate_plan(delete_plan(homed(delete_target("alpha", 7)), delete_target("beta", 9)))
        assert plan["targets"][0]["issue_repo"] == "home" and "issue_repo" not in plan["targets"][1]

    @pytest.mark.parametrize("value, needle", [
        ("", "is not a repository name"),
        (12, "is not a repository name"),
        (None, "is not a repository name"),
        ("ho me", "is not a repository name"),
        ("o/home", "is a name, not owner/name"),
    ])
    def test_a_bad_issue_repo_is_refused_by_name(self, value, needle):  # T1
        with pytest.raises(lwp.PlanError) as e:
            lwp.validate_plan(delete_plan(homed(delete_target("alpha", 7), value)))
        assert "`issue_repo`" in str(e.value) and needle in str(e.value)

    def test_the_reference_names_the_home_only_when_one_is_given(self):
        assert lwp.closes_ref("o", delete_target("alpha", 7)) == "#7"
        assert lwp.closes_ref("o", homed(delete_target("alpha", 7))) == "o/home#7"

    def test_a_delete_closes_the_issue_in_its_home_with_one_directive(self, mgh, monkeypatch):  # T2, T4
        live_caller(mgh, "alpha")
        messages = record_messages(monkeypatch, mgh)
        plan = lwp.validate_plan(delete_plan(homed(delete_target("alpha", 7))))
        assert lwp.land_target("pat", plan, plan["targets"][0], "o", False) == "landed"
        assert len(mgh.prs["alpha"]) == 1
        pr = mgh.prs["alpha"][0]
        assert pr["title"] == "ci: remove auto-reviewer.yml (Closes o/home#7)"
        assert pr["body"].startswith("Closes o/home#7\n")
        assert directives(pr["body"]) == ["Closes o/home#7"]
        assert directives(pr["title"]) == ["Closes o/home#7"]
        assert pr["head"] == "ci/staged-workflow-7"
        assert messages == ["ci: remove auto-reviewer.yml (Closes o/home#7)"]
        assert ("alpha", "main", CALLER) not in mgh.files

    def test_the_long_title_fallback_keeps_the_home_reference(self):  # T3
        workflows = [f".github/workflows/{'w' * 40}{i}.yml" for i in range(8)]
        assert lwp.pr_title(workflows, "o/home#7") == "ci: update 8 workflows (Closes o/home#7)"
        assert lwp.pr_title([], "o/home#7", workflows) == "ci: remove 8 workflows (Closes o/home#7)"

    def test_a_replaced_workflow_commit_closes_the_issue_in_its_home(self, gh, monkeypatch):  # T4
        stage(gh, "alpha")
        messages = record_messages(monkeypatch, gh)
        plan = lwp.validate_plan(plan_for(homed(target("alpha", 7))))
        assert lwp.land_target("pat", plan, plan["targets"][0], "o", False) == "landed"
        pr = gh.prs["alpha"][0]
        assert pr["title"] == "ci: update tests.yml (Closes o/home#7)"
        assert directives(pr["body"]) == ["Closes o/home#7"]
        assert messages == ["ci: update tests.yml (Closes o/home#7)"]

    def test_a_target_without_issue_repo_still_closes_its_own_issue(self, mgh, monkeypatch):  # T6
        live_caller(mgh, "alpha")
        messages = record_messages(monkeypatch, mgh)
        plan = lwp.validate_plan(delete_plan())
        assert lwp.land_target("pat", plan, plan["targets"][0], "o", False) == "landed"
        pr = mgh.prs["alpha"][0]
        assert pr["title"] == "ci: remove auto-reviewer.yml (Closes #7)"
        assert directives(pr["body"]) == ["Closes #7"]
        assert messages == ["ci: remove auto-reviewer.yml (Closes #7)"]

    def test_the_single_repository_lander_still_closes_its_own_issue(self):  # T6
        cfg = SimpleNamespace(issue=7)
        assert lsw._closes(cfg) == "#7"
        cfg.closes = "o/home#7"
        assert lsw._closes(cfg) == "o/home#7"

    def test_the_dry_run_names_the_home(self, tmp_path, monkeypatch, capsys):  # T5
        path = tmp_path / "plan.json"
        path.write_text(json.dumps(delete_plan(homed(delete_target("alpha", 7)),
                                               delete_target("beta", 9))), encoding="utf-8")

        def refuse(*a, **k):
            raise AssertionError("the dry run asked for the PAT")

        monkeypatch.setattr(lwp, "classic_pat_session", refuse)
        monkeypatch.setattr(lwp, "run", refuse)
        assert lwp.main(["--plan", str(path), "--owner", "o"]) == 0
        out = capsys.readouterr().out
        assert "o/alpha  PR closes o/home#7  branch ci/staged-workflow-7" in out
        assert "o/beta  PR closes #9  branch ci/staged-workflow-9" in out


# --- #4729: a line before every step that waits, so a run is never silent -------------


class Timeline:
    """stdout, every GitHub call and the session's entry, in the order they happen.

    It stands in for `sys.stdout`, so every `print` of both landers lands here, and the
    fake GitHub below appends each call to the same list. A test can then ask what was
    printed between one network call and the next.
    """

    def __init__(self):
        self.events: list[tuple[str, str]] = []

    def write(self, text: str) -> int:
        if text:
            self.events.append(("out", text))
        return len(text)

    def flush(self) -> None:
        pass

    def reconfigure(self, **kwargs) -> None:
        self.events.append(("reconfigure", json.dumps(kwargs, sort_keys=True)))

    def index(self, kind: str) -> int:
        return next(i for i, (k, _) in enumerate(self.events) if k == kind)

    def calls(self) -> list[tuple[int, str]]:
        return [(i, v) for i, (k, v) in enumerate(self.events) if k == "net"]

    def printed(self, start: int, end: int) -> str:
        return "".join(v for k, v in self.events[start:end] if k == "out")

    def said_before(self, i: int) -> str:
        """What was printed after the network call before event `i`, and before `i`."""
        start = max((j + 1 for j, _ in self.calls() if j < i), default=0)
        return self.printed(start, i)


@pytest.fixture
def timeline(monkeypatch):
    tl, fake = Timeline(), MergingGitHub()

    def recorded(method: str, call):
        def go(url, params=None, **kwargs):
            ref = (params or {}).get("ref")
            tl.events.append(("net", f"{method} {url}" + (f"?ref={ref}" if ref else "")))
            return call(url, params=params, **kwargs) if method == "GET" else call(url, **kwargs)
        return go

    monkeypatch.setattr(lsw, "requests", SimpleNamespace(
        get=recorded("GET", fake.get), post=recorded("POST", fake.post),
        put=recorded("PUT", fake.put), delete=recorded("DELETE", fake.delete)))
    monkeypatch.setattr(lsw.time, "sleep", lambda s: None)
    return tl, fake


def watch_stdout(monkeypatch, tl: Timeline) -> None:
    """Point stdout at the timeline. Called in the test body: pytest puts its own capture
    stream back on `sys.stdout` when the test starts, over anything a fixture set."""
    monkeypatch.setattr(sys, "stdout", tl)


class TimedSession:
    """A session that marks on the timeline the moment it yields the PAT."""

    def __init__(self, tl: Timeline):
        self.tl = tl

    def __call__(self, reason=None):
        tl = self.tl

        class Ctx:
            def __enter__(self):
                tl.events.append(("session", "entered"))
                return "pat"

            def __exit__(self, *exc):
                return False

        return Ctx()


class TestProgress:
    def test_each_target_is_announced_before_its_pre_read(self, timeline, monkeypatch):  # T1
        tl, gh = timeline
        watch_stdout(monkeypatch, tl)
        for repo in ("alpha", "beta", "gamma"):
            stage(gh, repo)
        plan = lwp.validate_plan(plan_for(target("alpha", 7), target("beta", 9), target("gamma", 11)))
        assert lwp.run(plan, plan["targets"], "o", False, session=TimedSession(tl)) == 0
        pre_reads = [(i, v) for i, v in tl.calls() if re.fullmatch(rf"GET {API}/[^/?]+", v)]
        assert [v.rsplit("/", 1)[1] for _, v in pre_reads] == ["alpha", "beta", "gamma"]
        for n, (i, v) in enumerate(pre_reads, 1):
            repo = v.rsplit("/", 1)[1]
            assert f"[{n}/3] o/{repo}" in tl.said_before(i), (
                f"the pre-read of {repo} ran before any line named it")
        entered, first_call = tl.index("session"), tl.calls()[0][0]
        assert entered < first_call
        opened = tl.printed(entered, first_call)
        assert "classic PAT is open" in opened and "3 target repositories" in opened

    def test_the_pre_read_line_ends_with_what_it_read(self, timeline, monkeypatch):  # T1
        tl, gh = timeline
        watch_stdout(monkeypatch, tl)
        stage(gh, "alpha")
        gh.repos["alpha"]["private"] = False
        plan = lwp.validate_plan(plan_for())
        assert lwp.run(plan, plan["targets"], "o", False, session=TimedSession(tl)) == 0
        out = tl.printed(0, len(tl.events))
        assert "  [1/1] o/alpha ... default branch main, public\n" in out

    def test_each_file_is_announced_before_its_first_read(self, timeline, monkeypatch):  # T2
        tl, gh = timeline
        watch_stdout(monkeypatch, tl)
        stage(gh, "alpha")
        live_caller(gh, "beta")
        plan = lwp.validate_plan(plan_for(target("alpha", 7), delete_target("beta", 9)))
        assert lwp.run(plan, plan["targets"], "o", False, session=TimedSession(tl)) == 0
        first_main_read: dict[str, int] = {}
        for i, v in tl.calls():
            if m := re.fullmatch(rf"GET {API}/(alpha|beta)/contents/(.+)\?ref=main", v):
                first_main_read.setdefault(m.group(2), i)
        assert set(first_main_read) == {".github/workflows/tests.yml", CALLER}
        for workflow, i in first_main_read.items():
            assert workflow in tl.said_before(i), (
                f"{workflow} was read on main before any line named it")
        said = tl.printed(0, len(tl.events))
        assert ".github/workflows/tests.yml: reading main and the staged copy ..." in said
        assert f"{CALLER}: reading main ..." in said

    def test_main_names_the_plan_and_counts_before_the_passphrase(  # T3, T4
            self, timeline, tmp_path, monkeypatch):
        tl, gh = timeline
        watch_stdout(monkeypatch, tl)
        stage(gh, "alpha")
        stage(gh, "beta")
        path = tmp_path / "plan.json"
        path.write_text(json.dumps(plan_for(target("alpha", 7), target("beta", 9))),
                        encoding="utf-8")
        monkeypatch.setattr(lwp, "classic_pat_session", TimedSession(tl))
        assert lwp.main(["--plan", str(path), "--apply", "--only", "beta", "--owner", "o"]) == 0
        assert tl.events[0] == ("reconfigure", '{"line_buffering": true}'), (
            "stdout was not line-buffered before the first line")
        before = tl.printed(0, tl.index("session"))
        lines = before.splitlines()
        assert lines[0] == f"Reading the plan {path} ..."
        assert lines[1] == "  plan     : 2 target(s), 2 file(s); 1 selected"
        assert "passphrase" in lines[-1].lower()

    def test_the_dry_run_names_the_plan_and_counts_first(self, timeline, tmp_path, monkeypatch):  # T3
        tl, _ = timeline
        watch_stdout(monkeypatch, tl)
        path = tmp_path / "plan.json"
        path.write_text(json.dumps(plan_for()), encoding="utf-8")

        def refuse(*a, **k):
            raise AssertionError("the dry run asked for the PAT")

        monkeypatch.setattr(lwp, "classic_pat_session", refuse)
        assert lwp.main(["--plan", str(path)]) == 0
        lines = tl.printed(0, len(tl.events)).splitlines()
        assert lines[:3] == [f"Reading the plan {path} ...",
                             "  plan     : 1 target(s), 1 file(s); 1 selected",
                             "DRY-RUN -- no credentials requested, no writes performed."]
        assert tl.calls() == []
